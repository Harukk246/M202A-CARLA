import carla
import util
import numpy as np
import time, sys, subprocess, random, select, os, sys
from queue import Queue, Empty

HEVC_CMD = [
    "ffmpeg", "-loglevel", "error",
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{util.WIDTH}x{util.HEIGHT}",
    "-r", str(util.FPS),
    "-i", "-",
    "-an",
    "-c:v", "libx265", "-preset", "ultrafast", "-tune", "zerolatency",
    "-x265-params", "keyint=50:no-scenecut=1",
    "-f", "mpegts",
    "udp://127.0.0.1:5000?pkt_size=1316",
]

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

    # FIXME: this needs to be checked.
    q: Queue = Queue(maxsize=1)
    def on_frame(frame):
        try:
            q.get_nowait()
        except Empty:
            pass
        q.put_nowait(frame)
    
    # this is an async callback, a background thread is spawned
    camera.listen(on_frame) 
    print("Started camera...")

    proc = subprocess.Popen(
        HEVC_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    print("HEVC camera streaming. Press Ctrl+C to quit.")
    
    try:
        while True:
            '''
            # FIXME: remove this and change to a dequeue of size 1.
            # drop frames as needed and don't link the camera speed
            # to the simulation speed.
            world.wait_for_tick()
            '''

            try:
                frame = q.get(block=True)  # get the latest frame
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

if __name__ == "__main__":
    main()
