import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
from tqdm import tqdm

# ----------------------------
# CONFIG
# ----------------------------

VIDEOS_DIR = "/home/ubuntu/M202A-CARLA/scripts/videos"
YOLO_MODEL = "/home/ubuntu/M202A-CARLA/scripts/yolov8n.pt"   # COCO-pretrained
CONF_THRESH = 0.5           # detection confidence threshold
OUTPUT_DIR = "/home/ubuntu/M202A-CARLA/scripts/mininet/video_features"

# COCO class IDs for vehicles (approx):
# 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASS_IDS = {2, 3, 5, 7}

# ----------------------------
# Frame-level labeling function
# ----------------------------

def label_frames_with_yolo(video_path, model):
    """
    Process a video and label each frame as 0 (no car) or 1 (car present).
    
    Args:
        video_path: Path to the video file
        model: YOLO model instance
    
    Returns:
        frame_labels: list[int] (0 or 1) of length num_frames
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    # Get total number of frames for progress bar
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frame_labels = []

    # Use tqdm to show progress
    with tqdm(total=total_frames, desc="Processing frames", unit="frame") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Run YOLO on the frame
            results = model(frame, verbose=False)[0]  # first result

            has_vehicle = False
            if results.boxes is not None and len(results.boxes) > 0:
                classes = results.boxes.cls.cpu().numpy().astype(int)
                confs = results.boxes.conf.cpu().numpy()

                # Check if any detection is a vehicle with sufficient confidence
                for cls_id, conf in zip(classes, confs):
                    if conf >= CONF_THRESH and cls_id in VEHICLE_CLASS_IDS:
                        has_vehicle = True
                        break

            frame_labels.append(1 if has_vehicle else 0)
            pbar.update(1)

    cap.release()
    return frame_labels

# ----------------------------
# Main processing function
# ----------------------------

def process_all_videos():
    """
    Process all videos in the videos directory sequentially.
    For each video, generate a feature vector (0/1 per frame) indicating car presence.
    """
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load YOLO model once
    print(f"Loading YOLO model from {YOLO_MODEL}...")
    model = YOLO(YOLO_MODEL)
    print("Model loaded successfully.")
    
    # Get all video files
    video_dir = Path(VIDEOS_DIR)
    video_files = sorted(video_dir.glob("*.mp4"))
    
    if not video_files:
        print(f"No video files found in {VIDEOS_DIR}")
        return
    
    print(f"Found {len(video_files)} video files to process.\n")
    
    # Process each video sequentially
    for video_path in video_files:
        video_name = video_path.stem  # e.g., "camera_1"
        print(f"Processing {video_name}...")
        
        try:
            # Get frame-level labels
            frame_labels = label_frames_with_yolo(str(video_path), model)
            
            # Save feature vector as numpy array
            output_path = os.path.join(OUTPUT_DIR, f"{video_name}_features.npy")
            np.save(output_path, np.array(frame_labels, dtype=np.int8))
            
            # Print summary
            num_frames = len(frame_labels)
            num_frames_with_cars = sum(frame_labels)
            print(f"  Completed: {num_frames} frames total, {num_frames_with_cars} frames with cars")
            print(f"  Saved to: {output_path}\n")
            
        except Exception as e:
            print(f"  ERROR processing {video_name}: {e}\n")
            continue
    
    print("All videos processed!")

# ----------------------------
# MAIN
# ----------------------------

if __name__ == "__main__":
    process_all_videos()

