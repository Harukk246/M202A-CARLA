import carla
import util
import numpy as np
import time, sys, subprocess, random, select, os, sys
from queue import Queue, Empty
import threading

# Camera configurations from README.md
CAMERA_CONFIGS = [
    # Visible cameras
    {"id": 4, "pos": (35.000, -210.000, 7.500), "rot": (-28.00, 86.00, 0.00)},
    {"id": 5, "pos": (27.500, 212.500, 7.500), "rot": (-28.00, 268.00, 0.00)},
    
    # Encrypted cameras
    {"id": 1, "pos": (20.000, 2.500, 7.500), "rot": (-28.00, 0.00, 0.00)},
    {"id": 2, "pos": (20.000, -90.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    {"id": 3, "pos": (20.000, 87.500, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 6, "pos": (-67.500, 0.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 7, "pos": (-70.000, -90.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 8, "pos": (-70.000, 87.500, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 9, "pos": (82.500, 0.000, 7.500), "rot": (-28.00, 358.00, 0.00)},
    # {"id": 10, "pos": (-147.500, 0.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 11, "pos": (-147.500, -90.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 12, "pos": (-147.500, 90.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 13, "pos": (-210.000, 0.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 14, "pos": (-210.000, -90.000, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 15, "pos": (-210.000, 87.500, 7.500), "rot": (-28.00, 0.00, 0.00)},
    # {"id": 16, "pos": (137.500, 0.000, 7.500), "rot": (-28.00, 358.00, 0.00)},
    # {"id": 17, "pos": (35.000, -150.000, 7.500), "rot": (-28.00, 2.00, 0.00)},
    # {"id": 18, "pos": (35.000, 142.500, 7.500), "rot": (-28.00, 0.00, 0.00)},
]

def create_hevc_command(port):
    """Create ffmpeg command for HEVC streaming to specified port."""
    return [
        "ffmpeg", "-loglevel", "error",
        
        # Raw CARLA frames
        "-f", "rawvideo",
        "-pix_fmt", "bgra",
        "-s", f"{util.WIDTH}x{util.HEIGHT}",
        "-r", str(util.FPS),
        "-i", "-",
        
        "-an",
        
        # NVENC HEVC tuned for low latency
        "-c:v", "hevc_nvenc",
        "-tune", "ll",                 # low-latency path
        "-preset", "p1",               # fastest
        "-rc", "cbr",                  # constant bitrate (stable)
        "-b:v", "5M",                  # target bitrate for 720p30
        "-maxrate", "5M",              # cap peak
        "-bufsize", "1M",              # ~200ms VBV at 5 Mb/s
        "-rc-lookahead", "0",          # no lookahead queue
        "-g", str(util.FPS),           # 1s GOP (e.g., 30 at 30fps)
        "-bf", "0",                    # no B-frames
        "-refs", "1",                  # minimal refs
        "-forced-idr", "1",            # make GOP boundaries IDR
        "-spatial_aq", "0",
        "-temporal_aq", "0",
        
        # Transport/mux: minimize buffering
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-flush_packets", "1",
        "-max_delay", "0",
        "-muxdelay", "0",
        "-muxpreload", "0",
        
        "-f", "mpegts",
        f"udp://127.0.0.1:{port}?pkt_size=1316"
    ]

def camera_stream_worker(camera, camera_id, port):
    """Worker thread to handle frames from a single camera and stream via ffmpeg."""
    q: Queue = Queue(maxsize=1)
    proc = None
    
    def on_frame(frame):
        try:
            q.get_nowait()
        except Empty:
            pass
        q.put_nowait(frame)
    
    try:
        camera.listen(on_frame)
        print(f"Camera {camera_id} started, streaming to port {port}...")
        
        # Small delay to avoid overwhelming system with simultaneous subprocess creation
        time.sleep(0.1)
        
        proc = subprocess.Popen(
            create_hevc_command(port),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        
        # Give ffmpeg a moment to start
        time.sleep(0.1)
        
        # Check if process started successfully
        if proc.poll() is not None:
            stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"ffmpeg for camera {camera_id} failed to start: {stderr_output}")
        
        while True:
            try:
                frame = q.get(timeout=0.05)
            except Empty:
                # Check if process is still alive
                if proc.poll() is not None:
                    stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')
                    print(f"ffmpeg for camera {camera_id} exited unexpectedly: {stderr_output}")
                    break
                continue
            
            # Check if process is still alive before writing
            if proc.poll() is not None:
                stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')
                print(f"ffmpeg for camera {camera_id} exited: {stderr_output}")
                break
            
            # Write frame to ffmpeg with error handling
            try:
                proc.stdin.write(frame.raw_data)
                proc.stdin.flush()
            except BrokenPipeError:
                print(f"Broken pipe for camera {camera_id} - ffmpeg may have crashed")
                break
            except OSError as e:
                print(f"OS error writing to camera {camera_id}: {e}")
                break
            
    except Exception as e:
        print(f"Error in camera {camera_id} stream: {e}")
    finally:
        camera.stop()
        camera.destroy()
        if proc is not None:
            print(f"Stopping HEVC encoder for camera {camera_id}...")
            try:
                proc.stdin.close()
            except:
                pass
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

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
    threads = []
    
    # Spawn all cameras with small delays to avoid overwhelming system
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
        
        cameras.append((camera, camera_id))
        port = 5000 + camera_id  # Incrementing ports based on camera ID
        
        # Start streaming thread for this camera
        thread = threading.Thread(
            target=camera_stream_worker,
            args=(camera, camera_id, port),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        
        # Small delay between spawning to avoid resource exhaustion
        time.sleep(0.05)
    
    print(f"\nSpawned {len(cameras)} cameras. Streaming started.")
    print("Press Ctrl+C to quit.\n")
    
    # Print port mappings
    print("Camera ID -> Port mappings:")
    for config in CAMERA_CONFIGS:
        print(f"  Camera {config['id']} -> UDP port {5000 + config['id']}")
    print()
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down cameras...")
        for camera, camera_id in cameras:
            camera.stop()
            camera.destroy()
        print("All cameras stopped.")

if __name__ == "__main__":
    main()
