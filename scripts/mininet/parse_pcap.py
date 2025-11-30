import numpy as np
from scapy.all import rdpcap
from scapy.layers.dot11 import Dot11
import os
from pathlib import Path
import sys

# Add parent directory to path to import util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from util import FPS

# ----------------------------
# CONFIG
# ----------------------------

PCAPS_DIR = "/home/ubuntu/M202A-CARLA/scripts/mininet/pcaps"
OUTPUT_DIR = "/home/ubuntu/M202A-CARLA/scripts/mininet/pcap_features"
MIN_VIDEO_PACKET_SIZE = 1000  # Minimum packet size to consider as video transmission packet

# ----------------------------
# Frame-level feature extraction function
# ----------------------------

def extract_frame_features_from_pcap(pcap_path):
    """
    Process a pcap file and extract frame-level features.
    
    Args:
        pcap_path: Path to the pcap file
    
    Returns:
        frame_features: numpy array of shape (num_frames, 6) containing:
            - num_packets
            - sum_packet_length
            - packet_size_mean
            - packet_size_std
            - inter_arrival_time_mean
            - inter_arrival_time_std
    """
    # Load pcap file
    packets = rdpcap(pcap_path)
    
    if len(packets) == 0:
        raise RuntimeError(f"No packets found in {pcap_path}")
    
    # Find the first video transmission packet (802.11 data frame with larger size)
    first_video_packet = None
    first_video_timestamp = None
    
    for pkt in packets:
        # Check if it's an 802.11 data frame (type == 2)
        if pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            # Type 2 = Data frame
            if dot11.type == 2:
                packet_size = len(pkt)
                if packet_size >= MIN_VIDEO_PACKET_SIZE:
                    first_video_packet = pkt
                    first_video_timestamp = float(pkt.time)
                    break
    
    if first_video_packet is None:
        raise RuntimeError(f"No video transmission packet found in {pcap_path}")
    
    print(f"  Found first video packet at timestamp: {first_video_timestamp:.6f}")
    
    # Calculate frame time window
    frame_duration = 1.0 / FPS  # seconds per frame
    
    # Collect all 802.11 data frames with their timestamps and sizes
    data_frames = []
    for pkt in packets:
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
                        'relative_time': timestamp - first_video_timestamp
                    })
    
    if len(data_frames) == 0:
        raise RuntimeError(f"No 802.11 data frames found after first video packet in {pcap_path}")
    
    # Determine number of frames based on the last packet timestamp
    last_packet_time = data_frames[-1]['relative_time']
    num_frames = int(np.ceil(last_packet_time / frame_duration)) + 1
    
    print(f"  Processing {len(data_frames)} 802.11 data frames into {num_frames} frames")
    
    # Initialize feature array: (num_frames, 6)
    # Features: [num_packets, sum_packet_length, packet_size_mean, packet_size_std, 
    #            inter_arrival_time_mean, inter_arrival_time_std]
    frame_features = np.zeros((num_frames, 6), dtype=np.float32)
    
    # Initialize frame buckets to store packets
    frame_packets = [[] for _ in range(num_frames)]
    
    # Group packets into frame buckets
    for i in range(len(data_frames)):
        pkt = data_frames[i]
        relative_time = pkt['relative_time']
        
        # Determine which frame this packet belongs to
        frame_idx = int(relative_time / frame_duration)
        
        # Ensure frame_idx is within bounds
        if frame_idx >= num_frames:
            frame_idx = num_frames - 1
        
        # Store packet info for this frame
        frame_packets[frame_idx].append({
            'size': pkt['size'],
            'timestamp': pkt['timestamp']
        })
    
    # Calculate features for each frame
    for frame_idx in range(num_frames):
        frame_pkt_list = frame_packets[frame_idx]
        
        if len(frame_pkt_list) == 0:
            # No packets in this frame - all features are 0
            frame_features[frame_idx] = [0, 0, 0, 0, 0, 0]
        else:
            # Extract packet sizes and timestamps
            packet_sizes = [pkt['size'] for pkt in frame_pkt_list]
            packet_timestamps = sorted([pkt['timestamp'] for pkt in frame_pkt_list])
            
            # Calculate features
            num_packets = len(frame_pkt_list)
            sum_packet_length = sum(packet_sizes)
            packet_size_mean = np.mean(packet_sizes)
            packet_size_std = np.std(packet_sizes) if len(packet_sizes) > 1 else 0.0
            
            # Calculate inter-arrival times
            if len(packet_timestamps) > 1:
                inter_arrival_times = np.diff(packet_timestamps)
                inter_arrival_time_mean = np.mean(inter_arrival_times)
                inter_arrival_time_std = np.std(inter_arrival_times)
            else:
                inter_arrival_time_mean = 0.0
                inter_arrival_time_std = 0.0
            
            frame_features[frame_idx] = [
                num_packets,
                sum_packet_length,
                packet_size_mean,
                packet_size_std,
                inter_arrival_time_mean,
                inter_arrival_time_std
            ]
    
    return frame_features

# ----------------------------
# Main processing function
# ----------------------------

def process_all_pcaps():
    """
    Process all pcap files in the pcaps directory sequentially.
    For each pcap, generate frame-level feature vectors.
    """
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get all pcap files
    pcap_dir = Path(PCAPS_DIR)
    pcap_files = sorted(pcap_dir.glob("*.pcap"))
    
    if not pcap_files:
        print(f"No pcap files found in {PCAPS_DIR}")
        return
    
    print(f"Found {len(pcap_files)} pcap files to process.")
    print(f"Using FPS: {FPS} (frame duration: {1.0/FPS:.4f} seconds)\n")
    
    # Process each pcap file sequentially
    for pcap_path in pcap_files:
        pcap_name = pcap_path.stem  # e.g., "camera_10"
        print(f"Processing {pcap_name}...")
        
        try:
            # Extract frame-level features
            frame_features = extract_frame_features_from_pcap(str(pcap_path))
            
            # Save feature array as numpy file
            output_path = os.path.join(OUTPUT_DIR, f"{pcap_name}_features.npy")
            np.save(output_path, frame_features)
            
            # Print summary
            num_frames = len(frame_features)
            total_packets = int(np.sum(frame_features[:, 0]))  # Sum of num_packets column
            avg_packets_per_frame = total_packets / num_frames if num_frames > 0 else 0
            
            print(f"  Completed: {num_frames} frames, {total_packets} total packets")
            print(f"  Average packets per frame: {avg_packets_per_frame:.2f}")
            print(f"  Saved to: {output_path}\n")
            
        except Exception as e:
            print(f"  ERROR processing {pcap_name}: {e}\n")
            import traceback
            traceback.print_exc()
            continue
    
    print("All pcap files processed!")

# ----------------------------
# MAIN
# ----------------------------

if __name__ == "__main__":
    process_all_pcaps()

