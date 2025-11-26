import carla
import util
import numpy as np
import cv2
from queue import Queue, Empty

# Import camera configurations from util
CAMERA_CONFIGS = util.CAMERA_CONFIGS

def main():
    util.common_init()
    
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    util.check_sync(world)
    
    bp_lib = world.get_blueprint_library()
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(util.WIDTH))
    cam_bp.set_attribute("image_size_y", str(util.HEIGHT))
    cam_bp.set_attribute("fov", str(util.FOV))
    cam_bp.set_attribute("sensor_tick", str(1.0 / util.FPS))
    
    cameras = []
    camera_queues = []
    
    # Spawn all cameras and set up queues
    for config in CAMERA_CONFIGS:
        camera_id = config["id"]
        pos = config["pos"]
        rot = config["rot"]
        
        cam_loc = carla.Location(x=pos[0], y=pos[1], z=pos[2])
        cam_rot = carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2])
        cam_tf = carla.Transform(cam_loc, cam_rot)
        
        camera = world.try_spawn_actor(cam_bp, cam_tf)
        if camera is None:
            print(f"Warning: Failed to spawn camera {camera_id} (position occupied). Skipping.")
            continue
        
        # Create queue for this camera and set up listener
        q = Queue()
        camera.listen(q.put)
        cameras.append((camera, camera_id))
        camera_queues.append((q, camera_id))
    
    print(f"\nSpawned {len(cameras)} cameras. Viewers started.")
    print("Press Ctrl+C or ESC to quit.\n")
    
    try:
        while True:
            # Advance the simulation by one fixed step
            world_frame = world.tick()
            
            # Get frames from all cameras
            for q, camera_id in camera_queues:
                try:
                    frame = q.get(timeout=0.1)
                except Empty:
                    continue
                
                # Convert frame to numpy array (BGRA -> BGR)
                arr = np.frombuffer(frame.raw_data, np.uint8).reshape(
                    (frame.height, frame.width, 4)
                )[:, :, :3].copy()
                
                # Display frame in window named after camera ID
                window_name = f"Camera {camera_id}"
                cv2.imshow(window_name, arr)
            
            # Process window events and check for ESC key
            if cv2.waitKey(1) == 27:  # ESC key
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down cameras...")
        for camera, camera_id in cameras:
            camera.stop()
            camera.destroy()
        cv2.destroyAllWindows()
        print("All cameras stopped.")

if __name__ == "__main__":
    main()
