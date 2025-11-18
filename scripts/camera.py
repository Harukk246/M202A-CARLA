import carla
import util
import numpy as np
import cv2
from queue import Queue, Empty
from ultralytics import YOLO

# YOLO("yolo11n").download()

# Smoothing factor for world coordinates
ALPHA = 0.7
# Smoothing factor for image-space boxes
IMG_ALPHA = 0.6
# Input scaling factor to detect distant cars
SCALE_FACTOR = 2.0

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
    # Store smoothed image-space bounding boxes per track ID
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

            # Convert BGRA -> BGR and make writable
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

                # Batch filter by allowed classes
                allowed_mask = np.array([model.names[c] in ALLOWED_CLASSES for c in cls_ids])
                cls_ids = cls_ids[allowed_mask]
                track_ids = track_ids[allowed_mask]
                xyxy = xyxy[allowed_mask]

                # Draw all boxes
                for cls_id, tid, (x1, y1, x2, y2) in zip(cls_ids, track_ids, xyxy):
                    class_name = model.names[cls_id]

                    # Skip very small boxes (optional)
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
                        print(f"Track {tid} smoothed world pos: {smoothed_pos}")
                    else:
                        print(f"Track {tid} bbox could not be projected to world coordinates")

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
