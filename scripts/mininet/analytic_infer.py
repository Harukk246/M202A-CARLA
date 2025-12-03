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
import matplotlib.pyplot as plt

# Add parent directory to path to import util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from util import FPS

# ----------------------------
# CONFIG
# ----------------------------

# Pcap file to analyze
PCAP_PATH = "/home/ubuntu/M202A-CARLA/scripts/mininet/test_pcaps/TEST_camera_25.pcap"

# Output base path for results (None = auto-generate from pcap name)
OUTPUT_PATH = None

# Packet filtering / window parameters
MIN_VIDEO_PACKET_SIZE = 1000  # Minimum packet size to consider as video transmission packet
WINDOW_SIZE_SECONDS = 1.0  # Sliding window size in seconds
# Hardcoded threshold used to identify and remove outlier windows based on total size.
# Any window with total_size > OUTLIER_THRESHOLD_BYTES will be omitted.
OUTLIER_THRESHOLD_BYTES = 200000


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
    
    # Find the first video transmission packet (802.11 data frame with larger size)
    first_video_packet = None
    first_video_timestamp = None
    first_video_packet_index = None
    
    for idx, pkt in enumerate(packets):
        # Check if it's an 802.11 data frame (type == 2)
        if pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            # Type 2 = Data frame
            if dot11.type == 2:
                packet_size = len(pkt)
                if packet_size >= MIN_VIDEO_PACKET_SIZE:
                    first_video_packet = pkt
                    first_video_timestamp = float(pkt.time)
                    first_video_packet_index = idx
                    break
    
    if first_video_packet is None:
        raise RuntimeError(f"No video transmission packet found in {pcap_path}")
    
    print(f"Found first video packet at timestamp: {first_video_timestamp:.6f}, index: {first_video_packet_index}")
    
    # Collect all 802.11 data frames with their timestamps and sizes
    data_frames = []
    for idx, pkt in enumerate(tqdm(packets, desc="Collecting 802.11 data frames", leave=False)):
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
                        'original_index': idx
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


def compute_window_totals(data_frames, window_size):
    """
    Compute total packet size for each sliding time window.

    Args:
        data_frames: List of packet dicts
        window_size: Size of each window in seconds

    Returns:
        window_totals: list of dicts with:
            - frame: integer window index (0-based)
            - start_time: window start time (seconds, relative)
            - end_time: window end time (seconds, relative)
            - total_size: total packet size (bytes) in the window
    """
    total_duration = data_frames[-1]['relative_time']
    num_windows = int(np.ceil(total_duration / window_size))

    window_totals = []
    print(f"\nComputing totals for {num_windows} windows...")

    for i in tqdm(range(num_windows), desc="Computing window totals"):
        window_start = i * window_size
        window_end = min(window_start + window_size, total_duration)

        _, total_size, _ = compute_window_metrics(
            data_frames, window_start, window_end
        )

        window_totals.append(
            {
                "frame": i,
                "start_time": window_start,
                "end_time": window_end,
                "total_size": total_size,
            }
        )

    return window_totals


def main():
    # Set base output path (used for both CSV and plot)
    pcap_path = Path(PCAP_PATH)
    if OUTPUT_PATH is None:
        base_output_path = pcap_path.parent / f"{pcap_path.stem}_window_totals"
    else:
        base_output_path = Path(OUTPUT_PATH)
    
    # Load pcap data
    print(f"Loading pcap file: {pcap_path}")
    data_frames, first_video_timestamp = load_pcap_data(pcap_path)

    # Compute total packet size for each time window
    window_totals = compute_window_totals(
        data_frames,
        window_size=WINDOW_SIZE_SECONDS,
    )

    # Compute mean total_size across all windows (for reporting)
    total_sizes_all = np.array([w["total_size"] for w in window_totals], dtype=float)
    mean_total_size = float(total_sizes_all.mean()) if len(total_sizes_all) > 0 else 0.0
    print(f"Mean window total size: {mean_total_size:.2f} bytes")

    # Filter outlier windows whose total_size exceeds the hardcoded threshold.
    if OUTLIER_THRESHOLD_BYTES is not None:
        filtered_window_totals = [
            w for w in window_totals if w["total_size"] <= OUTLIER_THRESHOLD_BYTES
        ]
        num_removed = len(window_totals) - len(filtered_window_totals)
        print(
            f"Filtering out {num_removed} outlier windows "
            f"(threshold = {OUTLIER_THRESHOLD_BYTES} bytes)"
        )
        window_totals = filtered_window_totals

    # Prepare data for CSV and plotting
    frames = np.array([w["frame"] for w in window_totals], dtype=int)
    total_sizes = np.array([w["total_size"] for w in window_totals], dtype=int)

    # Save CSV: frame, total_size_bytes
    csv_path = base_output_path.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_data = np.column_stack((frames, total_sizes))
    np.savetxt(
        csv_path,
        csv_data,
        delimiter=",",
        header="frame,total_size_bytes",
        comments="",
        fmt=["%d", "%d"],
    )
    print(f"CSV saved to: {csv_path}")

    # Create and save plot: frame number vs total packet size
    plot_path = base_output_path.with_suffix(".png")
    plt.figure(figsize=(10, 4))
    plt.plot(frames, total_sizes, marker="o", linestyle="-")
    plt.xlabel("Frame (window index)")
    plt.ylabel("Total packet size (bytes)")
    plt.title("Total packet size per window")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    print(f"Plot saved to: {plot_path}")

    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()

