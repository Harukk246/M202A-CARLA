import carla
import util
import numpy as np
import time, sys, subprocess, random, select, os, sys
from queue import Queue, Empty

HEVC_CMD = [
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
    "-b:v", "5M",                  # ★ target bitrate for 720p30
    "-maxrate", "5M",              # cap peak
    "-bufsize", "1M",              # ★ ~200ms VBV at 5 Mb/s
    "-rc-lookahead", "0",          # no lookahead queue
    "-g", str(util.FPS),           # ★ 1s GOP (e.g., 30 at 30fps)
    "-bf", "0",                    # ★ no B-frames
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
    "udp://127.0.0.1:5000?pkt_size=1316"
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
                frame = q.get(timeout=0.05)
            except Empty:
                continue

            # let ffmpeg handle color space conversion.
            proc.stdin.write(frame.raw_data)

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
