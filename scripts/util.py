import random
import carla
import numpy as np

WIDTH = 1280
HEIGHT = 720
FOV = 90
FPS = 30

def common_init():
    random.seed(42)

def check_sync(world):
    # Detect sync mode & set up a safe tick loop
    settings = world.get_settings()
    sync = settings.synchronous_mode
    if settings.synchronous_mode == True:
        raise RuntimeError("CARLA is not in async mode!")

def create_camera(world):
    bp_lib = world.get_blueprint_library()

    # Camera blueprint
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(WIDTH))
    cam_bp.set_attribute("image_size_y", str(HEIGHT))
    cam_bp.set_attribute("fov", str(FOV))
    cam_bp.set_attribute("sensor_tick", str(1.0 / FPS))

    # Pick a reasonable world-space location and aim it down the road
    # sp = random.choice(world.get_map().get_spawn_points())
    # cam_loc = sp.location + carla.Location(x=8.0, y=0.0, z=8.0)
    # cam_rot = carla.Rotation(pitch=-15.0, yaw=sp.rotation.yaw)  # look along lane

    # Hardcoded coordinates
    cam_loc = carla.Location(x=151.105438, y=-200.910126, z=8.275307)
    cam_rot = carla.Rotation(pitch=-15.000000, yaw=-178.560471, roll=0.000000)  # look along lane
    cam_tf = carla.Transform(cam_loc, cam_rot)

    return((cam_bp, cam_tf))

# ---------- Camera intrinsics ----------
def build_intrinsic_matrix(width, height, fov_deg):
    """Build camera intrinsic matrix K from FOV + resolution."""
    fov_rad = np.deg2rad(fov_deg)
    f = width / (2.0 * np.tan(fov_rad / 2.0))  # fx = fy

    cx = width / 2.0
    cy = height / 2.0

    K = np.array([
        [f, 0, cx],
        [0, f, cy],
        [0, 0, 1]
    ], dtype=np.float32)

    return K
