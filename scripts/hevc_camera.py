import carla
import numpy as np
import cv2
import time, sys, subprocess, random, select, os
from queue import Queue, Empty

random.seed(42)

WIDTH = 1280
HEIGHT = 720
FPS = 30
HEVC_CMD = [
    "ffmpeg",
    "-loglevel", "error",
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-r", str(FPS),
    "-i", "-",
    "-an",
    "-c:v", "libx265",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-x265-params", "keyint=50:no-scenecut=1",
    "-f", "hevc",
    "pipe:1",
]

# ------------ HEVC NAL helpers (same as before, just simplified) ---------
START_CODE_3 = b"\x00\x00\x01"
START_CODE_4 = b"\x00\x00\x00\x01"

def hevc_nal_type(b1: int) -> int:
    return (b1 & 0b01111110) >> 1

def classify(n):
    if n in (19, 20):
        return "IDR"
    if n == 21:
        return "CRA"
    if n in (32, 33, 34):
        return "PARAM"
    return f"TYPE_{n}"

hevc_buf = bytearray()
frame_counter = 0

def feed_hevc_bytes(data: bytes):
    """append data to buffer and try to parse complete NALs"""
    global hevc_buf, frame_counter
    hevc_buf.extend(data)

    # find start codes
    buf = hevc_buf
    L = len(buf)
    starts = []
    i = 0
    while i < L - 3:
        if buf[i:i+4] == START_CODE_4:
            starts.append((i, 4))
            i += 4
        elif buf[i:i+3] == START_CODE_3:
            starts.append((i, 3))
            i += 3
        else:
            i += 1

    if not starts:
        return

    # sentinel
    starts.append((L, 0))

    for idx in range(len(starts) - 1):
        s_idx, sc_len = starts[idx]
        e_idx, _      = starts[idx + 1]
        nal = buf[s_idx:e_idx]
        if len(nal) < sc_len + 1:
            continue
        first = nal[sc_len]
        ntype = hevc_nal_type(first)
        cls = classify(ntype)

        # crude frame count: count VCL-ish
        if cls in ("IDR", "CRA") or (ntype <= 31 and cls.startswith("TYPE_") is False):
            frame_counter += 1

        print(f"{time.time():.3f} | NAL size={len(nal)} | type={ntype} ({cls}) | frame_guess={frame_counter}")
        sys.stdout.flush()

    # keep tail
    last_start_idx, _ = starts[-2]
    hevc_buf = bytearray(buf[last_start_idx:])

def main():

    proc = subprocess.Popen(
        HEVC_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
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
    cam_bp.set_attribute("sensor_tick", str(1.0 / FPS))  # 20 FPS target in sync mode

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
                world.wait_for_tick()

            try:
                frame = q.get(timeout=1.0)  # get the latest frame
            except Empty:
                continue

            # write to hevc encoder
            proc.stdin.write(frame.raw_data)

            # Convert BGRA -> BGR for OpenCV
            arr = np.frombuffer(frame.raw_data, np.uint8)
            arr = arr.reshape((frame.height, frame.width, 4))[:, :, :3]

            cv2.imshow("HEVC Security Camera", arr)

            # ----- read from stdout and analyze (non-blocking) -----
            # use select to check if data is ready on proc.stdout
            rlist, _, _ = select.select([proc.stdout], [], [], 0)
            if rlist:
                # read what's available (don't block)
                # read a modest chunk to keep up
                print("found some data")
                chunk = os.read(proc.stdout.fileno(), 4096)
                if chunk:
                    feed_hevc_bytes(chunk)
            else:
                print("found no data")

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

        # shutdown hevc encoder
        print("Stopping HEVC encoder...")
        proc.stdin.close()
        proc.stdout.close() # make sure no other script is reading stdout.
        proc.wait()
        print("HEVC encoder stopped.")

if __name__ == "__main__":
    main()
