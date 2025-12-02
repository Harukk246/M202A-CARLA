"""
Thresholding-based car detection from encrypted 802.11 frames.

This script analyzes packet patterns in pcap files to detect when cars pass
in front of cameras. The approach leverages the fact that:
- ffmpeg encodes video in I, P, and B frames
- I-frames (keyframes) are larger and occur when scene changes
- When a car enters the frame, there's more motion, leading to more/larger packets
- Static backgrounds produce relatively constant packet patterns

By thresholding packet counts and sizes over sliding windows, we can detect
when activity increases, indicating a car is in the camera's field of view.
"""

import numpy as np
from scapy.all import rdpcap
from scapy.layers.dot11 import Dot11
import os
import sys
from pathlib import Path
from tqdm import tqdm

# Add parent directory to path to import util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from util import FPS

# ----------------------------
# CONFIG
# ----------------------------

# Pcap file to analyze
PCAP_PATH = "/home/ubuntu/M202A-CARLA/scripts/mininet/test_pcaps/TEST_camera_25.pcap"

# Output path for detection results (None = auto-generate from pcap name)
OUTPUT_PATH = None

# Detection parameters
MIN_VIDEO_PACKET_SIZE = 1000  # Minimum packet size to consider as video transmission packet
WINDOW_SIZE_SECONDS = 1.0  # Sliding window size in seconds
BASELINE_WINDOW_SECONDS = 5.0  # Initial window to establish baseline (static background)
PACKET_COUNT_THRESHOLD_MULTIPLIER = 1.5  # Threshold = baseline_mean * multiplier
PACKET_SIZE_THRESHOLD_MULTIPLIER = 1.5  # Threshold = baseline_mean * multiplier
MIN_DETECTION_DURATION_SECONDS = 0.5  # Minimum duration to consider as valid detection
SKIP_INITIAL_PACKETS = 1000  # Number of initial packets to skip in analysis


def load_pcap_data(pcap_path):
    """
    Load pcap file and extract 802.11 data frames with timestamps.
    
    Args:
        pcap_path: Path to the pcap file (string or Path object)
    
    Returns:
        data_frames: List of dicts with 'timestamp', 'size', 'relative_time', 'original_index'
        first_video_timestamp: Timestamp of the first video packet
    """
    # Convert Path to string if needed
    pcap_path_str = str(pcap_path)
    
    # Load pcap file
    packets = rdpcap(pcap_path_str)
    
    if len(packets) == 0:
        raise RuntimeError(f"No packets found in {pcap_path}")
    
    print(f"Loaded {len(packets)} total packets from {pcap_path}")
    
    # Skip initial packets
    start_index = SKIP_INITIAL_PACKETS
    if start_index >= len(packets):
        raise RuntimeError(f"Cannot skip {start_index} packets - only {len(packets)} packets available")
    
    print(f"Skipping first {start_index} packets in analysis")
    packets_to_analyze = packets[start_index:]
    
    # Find the first video transmission packet (802.11 data frame with larger size)
    first_video_packet = None
    first_video_timestamp = None
    first_video_packet_index = None
    
    for idx, pkt in enumerate(packets_to_analyze):
        # Check if it's an 802.11 data frame (type == 2)
        if pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            # Type 2 = Data frame
            if dot11.type == 2:
                packet_size = len(pkt)
                if packet_size >= MIN_VIDEO_PACKET_SIZE:
                    first_video_packet = pkt
                    first_video_timestamp = float(pkt.time)
                    first_video_packet_index = idx + start_index  # Adjust index to account for skipped packets
                    break
    
    if first_video_packet is None:
        raise RuntimeError(f"No video transmission packet found in {pcap_path}")
    
    print(f"Found first video packet at timestamp: {first_video_timestamp:.6f}, index: {first_video_packet_index}")
    
    # Collect all 802.11 data frames with their timestamps and sizes
    data_frames = []
    for idx, pkt in enumerate(tqdm(packets_to_analyze, desc="Collecting 802.11 data frames", leave=False)):
        # Check if it's an 802.11 data frame
        if pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            if dot11.type == 2:  # Data frame
                timestamp = float(pkt.time)
                # Only consider packets after the first video packet
                if timestamp >= first_video_timestamp:
                    packet_size = len(pkt)
                    data_frames.append({
                        'timestamp': timestamp,
                        'size': packet_size,
                        'relative_time': timestamp - first_video_timestamp,
                        'original_index': idx + start_index  # Adjust index to account for skipped packets
                    })
    
    if len(data_frames) == 0:
        raise RuntimeError(f"No 802.11 data frames found after first video packet in {pcap_path}")
    
    print(f"Collected {len(data_frames)} 802.11 data frames")
    print(f"Duration: {data_frames[-1]['relative_time']:.2f} seconds")
    
    return data_frames, first_video_timestamp


def compute_window_metrics(data_frames, window_start_time, window_end_time):
    """
    Compute packet count and total size for packets within a time window.
    
    Args:
        data_frames: List of packet dicts
        window_start_time: Start of window (relative time)
        window_end_time: End of window (relative time)
    
    Returns:
        packet_count: Number of packets in window
        total_size: Sum of packet sizes in window
        avg_packet_size: Average packet size in window
    """
    packet_count = 0
    total_size = 0
    
    for pkt in data_frames:
        rel_time = pkt['relative_time']
        if window_start_time <= rel_time < window_end_time:
            packet_count += 1
            total_size += pkt['size']
    
    avg_packet_size = total_size / packet_count if packet_count > 0 else 0
    
    return packet_count, total_size, avg_packet_size


def establish_baseline(data_frames, baseline_duration, window_size):
    """
    Establish baseline metrics from initial static background period.
    
    Args:
        data_frames: List of packet dicts
        baseline_duration: Duration in seconds to use for baseline
        window_size: Size of each window in seconds
    
    Returns:
        baseline_packet_count_mean: Mean packet count per window
        baseline_packet_count_std: Std of packet count per window
        baseline_total_size_mean: Mean total size per window
        baseline_total_size_std: Std of total size per window
    """
    baseline_windows = []
    
    # Sample windows from the baseline period
    num_baseline_windows = int(baseline_duration / window_size)
    
    for i in range(num_baseline_windows):
        window_start = i * window_size
        window_end = window_start + window_size
        
        packet_count, total_size, _ = compute_window_metrics(
            data_frames, window_start, window_end
        )
        
        baseline_windows.append({
            'packet_count': packet_count,
            'total_size': total_size
        })
    
    if len(baseline_windows) == 0:
        raise RuntimeError("Could not establish baseline - no windows in baseline period")
    
    packet_counts = [w['packet_count'] for w in baseline_windows]
    total_sizes = [w['total_size'] for w in baseline_windows]
    
    baseline_packet_count_mean = np.mean(packet_counts)
    baseline_packet_count_std = np.std(packet_counts)
    baseline_total_size_mean = np.mean(total_sizes)
    baseline_total_size_std = np.std(total_sizes)
    
    print(f"\nBaseline established from {num_baseline_windows} windows:")
    print(f"  Packet count: mean={baseline_packet_count_mean:.2f}, std={baseline_packet_count_std:.2f}")
    print(f"  Total size: mean={baseline_total_size_mean:.2f}, std={baseline_total_size_std:.2f}")
    
    return (
        baseline_packet_count_mean,
        baseline_packet_count_std,
        baseline_total_size_mean,
        baseline_total_size_std
    )


def detect_cars_with_thresholding(data_frames, window_size, baseline_duration, 
                                  packet_count_multiplier, packet_size_multiplier,
                                  min_detection_duration, output_path=None):
    """
    Detect cars by thresholding packet activity over sliding windows.
    
    Args:
        data_frames: List of packet dicts
        window_size: Size of sliding window in seconds
        baseline_duration: Duration in seconds to use for baseline
        packet_count_multiplier: Multiplier for packet count threshold
        packet_size_multiplier: Multiplier for packet size threshold
        min_detection_duration: Minimum duration for valid detection
        output_path: Optional path to save detection results
    
    Returns:
        detections: List of (start_time, end_time) tuples for detected car periods
    """
    total_duration = data_frames[-1]['relative_time']
    
    # Establish baseline from initial period (assumed to be static background)
    baseline_duration = min(baseline_duration, total_duration * 0.2)  # Use up to 20% of total duration
    print(f"\nEstablishing baseline from first {baseline_duration:.2f} seconds...")
    
    (
        baseline_packet_count_mean,
        baseline_packet_count_std,
        baseline_total_size_mean,
        baseline_total_size_std
    ) = establish_baseline(data_frames, baseline_duration, window_size)
    
    # Set thresholds
    packet_count_threshold = baseline_packet_count_mean * packet_count_multiplier
    total_size_threshold = baseline_total_size_mean * packet_size_multiplier
    
    print(f"\nThresholds:")
    print(f"  Packet count threshold: {packet_count_threshold:.2f}")
    print(f"  Total size threshold: {total_size_threshold:.2f}")
    
    # Slide window over entire duration
    num_windows = int(np.ceil(total_duration / window_size))
    window_metrics = []
    
    print(f"\nAnalyzing {num_windows} windows...")
    for i in tqdm(range(num_windows), desc="Computing window metrics"):
        window_start = i * window_size
        window_end = min(window_start + window_size, total_duration)
        
        packet_count, total_size, avg_packet_size = compute_window_metrics(
            data_frames, window_start, window_end
        )
        
        window_metrics.append({
            'start_time': window_start,
            'end_time': window_end,
            'packet_count': packet_count,
            'total_size': total_size,
            'avg_packet_size': avg_packet_size,
            'exceeds_packet_count_threshold': packet_count > packet_count_threshold,
            'exceeds_size_threshold': total_size > total_size_threshold
        })
    
    # Detect periods where thresholds are exceeded
    # A car is detected if either packet count OR total size exceeds threshold
    active_detections = []
    detections = []
    
    for i, metrics in enumerate(window_metrics):
        is_active = (metrics['exceeds_packet_count_threshold'] or 
                     metrics['exceeds_size_threshold'])
        
        if is_active:
            if not active_detections:
                # Start of new detection period
                active_detections.append(i)
        else:
            if active_detections:
                # End of detection period
                start_idx = active_detections[0]
                end_idx = i - 1
                
                start_time = window_metrics[start_idx]['start_time']
                end_time = window_metrics[end_idx]['end_time']
                duration = end_time - start_time
                
                # Only keep detections that last at least min_detection_duration
                if duration >= min_detection_duration:
                    detections.append((start_time, end_time))
                
                active_detections = []
    
    # Handle case where detection extends to end of data
    if active_detections:
        start_idx = active_detections[0]
        start_time = window_metrics[start_idx]['start_time']
        end_time = window_metrics[-1]['end_time']
        duration = end_time - start_time
        
        if duration >= min_detection_duration:
            detections.append((start_time, end_time))
    
    # Print results
    print(f"\n{'='*60}")
    print(f"Detection Results:")
    print(f"{'='*60}")
    print(f"Total detections: {len(detections)}")
    
    if len(detections) > 0:
        print(f"\nDetected car periods:")
        for i, (start, end) in enumerate(detections, 1):
            duration = end - start
            print(f"  {i}. Time: {start:.2f}s - {end:.2f}s (duration: {duration:.2f}s)")
    else:
        print("\nNo cars detected.")
    
    # Save results if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save detections as text file
        with open(output_path, 'w') as f:
            f.write(f"# Car Detection Results\n")
            f.write(f"# Total detections: {len(detections)}\n")
            f.write(f"# Format: start_time(s) end_time(s) duration(s)\n")
            f.write(f"# Thresholds: packet_count={packet_count_threshold:.2f}, total_size={total_size_threshold:.2f}\n\n")
            
            for start, end in detections:
                duration = end - start
                f.write(f"{start:.6f} {end:.6f} {duration:.6f}\n")
        
        # Also save window metrics for analysis
        metrics_path = output_path.with_suffix('.metrics.txt')
        with open(metrics_path, 'w') as f:
            f.write("# Window Metrics\n")
            f.write("# Format: start_time(s) end_time(s) packet_count total_size avg_packet_size exceeds_packet_count exceeds_size\n")
            for m in window_metrics:
                f.write(f"{m['start_time']:.6f} {m['end_time']:.6f} "
                       f"{m['packet_count']} {m['total_size']} {m['avg_packet_size']:.2f} "
                       f"{int(m['exceeds_packet_count_threshold'])} {int(m['exceeds_size_threshold'])}\n")
        
        print(f"\nResults saved to: {output_path}")
        print(f"Window metrics saved to: {metrics_path}")
    
    return detections


def main():
    # Set output path
    pcap_path = Path(PCAP_PATH)
    if OUTPUT_PATH is None:
        output_path = pcap_path.parent / f"{pcap_path.stem}_detections.txt"
    else:
        output_path = Path(OUTPUT_PATH)
    
    # Load pcap data
    print(f"Loading pcap file: {pcap_path}")
    data_frames, first_video_timestamp = load_pcap_data(pcap_path)
    
    # Detect cars
    detections = detect_cars_with_thresholding(
        data_frames,
        window_size=WINDOW_SIZE_SECONDS,
        baseline_duration=BASELINE_WINDOW_SECONDS,
        packet_count_multiplier=PACKET_COUNT_THRESHOLD_MULTIPLIER,
        packet_size_multiplier=PACKET_SIZE_THRESHOLD_MULTIPLIER,
        min_detection_duration=MIN_DETECTION_DURATION_SECONDS,
        output_path=output_path
    )
    
    print(f"\nAnalysis complete!")


if __name__ == "__main__":
    main()

