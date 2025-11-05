import carla
import numpy as np
import cv2
import time, sys
from queue import Queue, Empty
import random
from ultralytics import YOLO

random.seed(42)

WIDTH = 1280
HEIGHT = 720
FPS = 30

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    # --- Camera blueprint ---
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(WIDTH))
    cam_bp.set_attribute("image_size_y", str(HEIGHT))
    cam_bp.set_attribute("fov", "90")
    cam_bp.set_attribute("sensor_tick", str(1.0 / FPS))

    # --- Pick a reasonable world-space location and aim it down the road ---
    # sp = random.choice(world.get_map().get_spawn_points())
    # cam_loc = sp.location + carla.Location(x=8.0, y=0.0, z=8.0)
    # cam_rot = carla.Rotation(pitch=-15.0, yaw=sp.rotation.yaw)  # look along lane

    # Hardcoded coordinates
    cam_loc = carla.Location(x=151.105438, y=-200.910126, z=8.275307)
    cam_rot = carla.Rotation(pitch=-15.000000, yaw=-178.560471, roll=0.000000)  # look along lane

    cam_tf = carla.Transform(cam_loc, cam_rot)

    print(cam_tf)

    camera = world.try_spawn_actor(cam_bp, cam_tf)
    if camera is None:
        raise RuntimeError("Failed to spawn camera (position occupied). Try again.")

    # Let you visually verify placement
    world.get_spectator().set_transform(cam_tf)

    # --- Use a queue so we can drive the world tick safely ---
    q: Queue = Queue()
    camera.listen(q.put)

    # Detect sync mode & set up a safe tick loop
    settings = world.get_settings()
    sync = settings.synchronous_mode
    print(f"Synchronous mode: {sync}")

    # LOAD YOLO MODEL
    print("Loading YOLO model...")

    model = YOLO("yolov8n.pt")
    ALLOWED_CLASSES = ["car", "truck", "bus", "motorbike", "traffic light", "person"]

    # If sim is async but very fast, we can wait for server ticks
    # If sim is sync, we must call world.tick() to advance frames
    try:
        print("Static camera streaming. Press Ctrl+C to quit.")
        while True:
            if sync:
                world.tick()  # advance one frame so sensors produce data
            else:
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
            
            # sys.exit(0)

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
