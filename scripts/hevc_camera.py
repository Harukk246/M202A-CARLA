import carla
import numpy as np
import time, sys, subprocess, random, select, os
from queue import Queue, Empty

random.seed(42)

WIDTH = 1280
HEIGHT = 720
FPS = 30
HEVC_CMD = [
    "ffmpeg", "-loglevel", "error",
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-r", str(FPS),
    "-i", "-",
    "-an",
    "-c:v", "libx265", "-preset", "ultrafast", "-tune", "zerolatency",
    "-x265-params", "keyint=50:no-scenecut=1",
    "-f", "mpegts",
    "udp://127.0.0.1:5000?pkt_size=1316",
]

def main():

    proc = subprocess.Popen(
        HEVC_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    print("Started HEVC encoder...")

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

    # If sim is async but very fast, we can wait for server ticks
    # If sim is sync, we must call world.tick() to advance frames
    try:
        print("HEVC camera streaming. Press Ctrl+C to quit.")
        while True:
            if sync:
                world.tick()  # advance one frame so sensors produce data
            else:
                # FIXME: remove this and change to a dequeue of size 1.
                # drop frames as needed and don't link the camera speed
                # to the simulation speed.
                world.wait_for_tick()

            try:
                frame = q.get(timeout=1.0)  # get the latest frame
            except Empty:
                continue

            # CARLA gives BGRA; ffmpeg expects BGR24 (3 bytes/pixel)
            arr = np.frombuffer(frame.raw_data, np.uint8).reshape((frame.height, frame.width, 4))[:, :, :3]
            proc.stdin.write(arr.tobytes())

    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        camera.destroy()

        # shutdown hevc encoder
        print("Stopping HEVC encoder...")
        proc.stdin.close()
        proc.wait()
        print("HEVC encoder stopped.")

if __name__ == "__main__":
    main()
