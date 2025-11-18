import carla
import util
import numpy as np
import cv2
from queue import Queue, Empty
from ultralytics import YOLO
from scipy.optimize import linear_sum_assignment
from collections import defaultdict

# Smoothing factor for world coordinates
ALPHA = 0.7
# Smoothing factor for image-space boxes
IMG_ALPHA = 0.6
# Input scaling factor to detect distant cars
SCALE_FACTOR = 2.0

# Initialize variables for MOTA calculation
TP, FP, FN, IDSW = 0, 0, 0, 0
track_history = defaultdict(list)  # Store history of tracked objects

def compute_mota():
    """Compute Multiple Object Tracking Accuracy (MOTA)."""
    global TP, FP, FN, IDSW
    if TP + FP + FN == 0:
        return 0  # Avoid division by zero if no objects are detected
    return 1 - (FP + FN + IDSW) / (TP + FP + FN)

def associate_tracks(tracks, detections):
    """Associate detected boxes with existing tracks using the Hungarian algorithm."""
    cost_matrix = np.zeros((len(tracks), len(detections)))
    for i, track in enumerate(tracks):
        for j, detection in enumerate(detections):
            cost_matrix[i, j] = 1 - compute_iou(track, detection)  # Cost = 1 - IoU
    
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return row_ind, col_ind, cost_matrix

def compute_iou(box1, box2):
    """Compute Intersection over Union (IoU) between two boxes."""
    x1, y1, x2, y2 = box1
    bx1, by1, bx2, by2 = box2

    inter_area = max(0, min(x2, bx2) - max(x1, bx1)) * max(0, min(y2, by2) - max(y1, by1))
    box1_area = (x2 - x1) * (y2 - y1)
    box2_area = (bx2 - bx1) * (by2 - by1)
    
    union_area = box1_area + box2_area - inter_area
    return inter_area / union_area if union_area > 0 else 0

def update_tracking_info(frame_tracks, frame_detections):
    """Update TP, FP, FN, IDSW based on matching."""
    global TP, FP, FN, IDSW

    # Associate tracks with detections
    row_ind, col_ind, cost_matrix = associate_tracks(frame_tracks, frame_detections)

    matched_tracks = set()
    matched_detections = set()

    # Print debugging information
    print(f"Tracking {len(frame_tracks)} tracks, {len(frame_detections)} detections.")
    print(f"Matching {len(row_ind)} pairs.")
    print(f"Cost matrix:\n{cost_matrix}")
    
    for t, d in zip(row_ind, col_ind):
        if cost_matrix[t, d] < 0.5:  # IoU threshold for matching
            TP += 1
            matched_tracks.add(t)
            matched_detections.add(d)

    FN += len(frame_detections) - len(matched_detections)
    FP += len(frame_tracks) - len(matched_tracks)

    # Count ID swaps by checking track IDs that are mismatched across frames
    for t in range(len(frame_tracks)):
        if t not in matched_tracks:
            IDSW += 1

def main():
    util.common_init()

    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    util.check_sync(world)

    ground_z = 0.0
    cam_bp, cam_tf = util.create_camera(world)
    camera = world.try_spawn_actor(cam_bp, cam_tf)
    if camera is None:
        raise RuntimeError("Failed to spawn camera (position occupied). Try again.")

    # build projection matrix
    K = util.build_intrinsic_matrix(util.WIDTH, util.HEIGHT, util.FOV)

    q: Queue = Queue()
    camera.listen(q.put)

    # LOAD YOLO MODEL
    print("Loading YOLOv8m model...")
    model = YOLO("yolov8m.pt")
    ALLOWED_CLASSES = {"car", "truck", "bus", "motorbike"}

    # Store smoothed world positions per track ID
    smoothed_tracks = {}
    smoothed_boxes = {}

    frame_count = 0
    print("Static camera streaming. Press Ctrl+C to quit.")
    try:
        while True:
            world.wait_for_tick()

            try:
                frame = q.get(timeout=1.0)  # get latest frame
            except Empty:
                continue

            arr = np.frombuffer(frame.raw_data, np.uint8).reshape((frame.height, frame.width, 4))[:, :, :3].copy()

            # Upscale image for better distant car detection
            scaled_arr = cv2.resize(arr, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)

            # Track vehicles using YOLOv8m + ByteTrack
            results = model.track(
                scaled_arr,
                persist=True,
                tracker="bytetrack.yaml",
                conf=0.35,  # confidence threshold
                iou=0.5,    # NMS IoU threshold
                verbose=False
            )

            frame_tracks = []  # List of tracked objects in this frame
            frame_detections = []  # List of detected objects in this frame

            # Iterate over tracked results
            for result in results:
                if result.boxes is None or result.boxes.id is None:
                    continue

                boxes = result.boxes
                cls_ids = boxes.cls.cpu().numpy().astype(int)
                track_ids = boxes.id.cpu().numpy().astype(int)
                xyxy = boxes.xyxy.cpu().numpy().astype(float)

                # Rescale boxes back to original image size
                xyxy /= SCALE_FACTOR

                # Filter by allowed classes
                allowed_mask = np.array([model.names[c] in ALLOWED_CLASSES for c in cls_ids])
                cls_ids = cls_ids[allowed_mask]
                track_ids = track_ids[allowed_mask]
                xyxy = xyxy[allowed_mask]

                # Draw all boxes
                for cls_id, tid, (x1, y1, x2, y2) in zip(cls_ids, track_ids, xyxy):
                    class_name = model.names[cls_id]

                    # Skip small boxes
                    if (x2 - x1) < 10 or (y2 - y1) < 10:
                        continue

                    # Smooth bounding boxes in image space
                    if tid in smoothed_boxes:
                        prev_box = smoothed_boxes[tid]
                        smoothed_box = IMG_ALPHA * prev_box + (1 - IMG_ALPHA) * np.array([x1, y1, x2, y2])
                    else:
                        smoothed_box = np.array([x1, y1, x2, y2])
                    smoothed_boxes[tid] = smoothed_box
                    x1, y1, x2, y2 = smoothed_box.astype(int)

                    # Draw bounding box + label
                    cv2.rectangle(arr, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"{class_name} ID:{tid}"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                    cv2.rectangle(arr, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), (0, 255, 0), -1)
                    cv2.putText(arr, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

                    # Convert bbox to world coordinates
                    bbox_center = util.bbox_bottom_center_to_world((x1, y1, x2, y2), K, cam_tf, ground_z)

                    # Only smooth if bbox_center is valid
                    if bbox_center is not None:
                        if tid in smoothed_tracks:
                            prev_pos = smoothed_tracks[tid]
                            smoothed_pos = ALPHA * prev_pos + (1 - ALPHA) * bbox_center
                        else:
                            smoothed_pos = bbox_center
                        smoothed_tracks[tid] = smoothed_pos

                    # Add track and detection for matching
                    frame_tracks.append([x1, y1, x2, y2])  # Add the bounding box as track
                    frame_detections.append([x1, y1, x2, y2])  # Add detection box for comparison

            # Update tracking info for MOTA calculation
            update_tracking_info(frame_tracks, frame_detections)

            # Compute MOTA (for tracking accuracy)
            mota_score = compute_mota()
            print(f"MOTA: {mota_score}")

            # Display every frame (or adjust modulo for faster)
            frame_count += 1
            if frame_count % 1 == 0:
                cv2.imshow("Static Security Camera", arr)

            # Keep window responsive
            if cv2.waitKey(1) == 27:  # ESC to exit
                break

    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        camera.destroy()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
