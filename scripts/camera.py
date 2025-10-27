# static_security_cam.py
import carla
import numpy as np
import cv2
import time
from queue import Queue, Empty
import random

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    # --- Camera blueprint ---
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", "1280")
    cam_bp.set_attribute("image_size_y", "720")
    cam_bp.set_attribute("fov", "90")
    cam_bp.set_attribute("sensor_tick", "0.05")  # 20 FPS target in sync mode

    # --- Pick a reasonable world-space location and aim it down the road ---
    sp = random.choice(world.get_map().get_spawn_points())
    cam_loc = sp.location + carla.Location(x=8.0, y=0.0, z=8.0)
    cam_rot = carla.Rotation(pitch=-15.0, yaw=sp.rotation.yaw)  # look along lane
    cam_tf = carla.Transform(cam_loc, cam_rot)

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
                image = q.get(timeout=1.0)  # get the latest frame
            except Empty:
                continue

            # Convert BGRA -> BGR for OpenCV
            arr = np.frombuffer(image.raw_data, np.uint8)
            arr = arr.reshape((image.height, image.width, 4))[:, :, :3]

            cv2.imshow("Static Security Camera", arr)
            # Use a small waitKey so the window stays responsive
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
