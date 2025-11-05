import carla
import util
import numpy as np
import cv2
import time, sys
from queue import Queue, Empty
import random
from ultralytics import YOLO

def main():
    util.common_init()

    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    util.check_sync(world)

    cam_bp, cam_tf = util.create_camera(world)
    camera = world.try_spawn_actor(cam_bp, cam_tf)
    if camera is None:
        raise RuntimeError("Failed to spawn camera (position occupied). Try again.")

    q: Queue = Queue()
    camera.listen(q.put)

    # LOAD YOLO MODEL
    print("Loading YOLO model...")

    model = YOLO("yolov8n.pt")
    ALLOWED_CLASSES = ["car", "truck", "bus", "motorbike", "traffic light", "person"]

    try:
        print("Static camera streaming. Press Ctrl+C to quit.")
        while True:
            world.wait_for_tick()

            try:
                frame = q.get(timeout=1.0)  # get the latest frame
            except Empty:
                continue

            # Convert BGRA -> BGR for OpenCV
            arr = np.frombuffer(frame.raw_data, np.uint8)
            arr = arr.reshape((frame.height, frame.width, 4))[:, :, :3]

            # Make a writable copy for drawing
            # TODO: this is slow, we should use a faster way to draw the bounding boxes
            arr = arr.copy()

            # the yolo model input dim is (720, 1280, 3)
            results = model.track(arr, persist=True, tracker="bytetrack.yaml", verbose=False)
            
            for result in results:
                boxes = result.boxes
                if boxes is None or boxes.id is None:
                    continue
                
                # Draw bounding boxes on the image
                for i, box in enumerate(boxes):

                    # Get class name
                    class_id = int(box.cls[0])
                    class_name = model.names[class_id]
                    
                    # Only draw boxes for allowed classes
                    if class_name in ALLOWED_CLASSES:
                        # Get bounding box coordinates
                        # TODO: this is slow, try to perform all ops on the GPU
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        track_id = int(box.id[0])
                        
                        # Draw bounding box
                        cv2.rectangle(arr, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # Draw label with track ID
                        label = f"{class_name} ID:{track_id}"
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        cv2.rectangle(arr, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), (0, 255, 0), -1)
                        cv2.putText(arr, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

            cv2.imshow("Static Security Camera", arr)

            # Use a small waitKey so the window stays responsive
            # TODO: the code breaks when I delete below, why???
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
