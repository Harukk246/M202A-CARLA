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

# ---------- Pixel to world ----------
def pixel_to_world(u, v, K, cam_transform, ground_z=0.0):
    """
    Map a pixel (u, v) in the image to a 3D point on the plane z = ground_z
    in CARLA world coordinates, using camera intrinsics K and extrinsics
    cam_transform (carla.Transform).
    """

    # 1) Ray in camera coordinates
    K_inv = np.linalg.inv(K)
    uv1 = np.array([u, v, 1.0], dtype=np.float32)
    d_cam = K_inv @ uv1  # [x_c, y_c, z_c] direction (up to scale)

    # We want a direction vector; enforce z_c = 1
    d_cam = np.array([d_cam[0], d_cam[1], 1.0], dtype=np.float32)
    d_cam /= np.linalg.norm(d_cam)

    # 2) Convert camera direction to world direction using CARLA transform
    # Camera origin in world frame
    cam_loc = cam_transform.location
    o_world = np.array([cam_loc.x, cam_loc.y, cam_loc.z], dtype=np.float32)

    # To get the direction in world:
    #   - Take a point 1 unit along the direction in camera space
    #   - Transform it to world
    #   - Subtract origin -> direction
    p_cam = carla.Location(x=float(d_cam[0]),
                           y=float(d_cam[1]),
                           z=float(d_cam[2]))
    p_world = cam_transform.transform(p_cam)

    p_world_vec = np.array([p_world.x, p_world.y, p_world.z], dtype=np.float32)
    d_world = p_world_vec - o_world
    d_world /= np.linalg.norm(d_world)

    # 3) Ray-plane intersection with z = ground_z
    # ray: o_world + s * d_world
    # Solve for s where z == ground_z
    o_z = o_world[2]
    d_z = d_world[2]

    # Handle edge case: ray parallel to plane
    if abs(d_z) < 1e-6:
        return None  # No intersection (or it's almost parallel)

    s = (ground_z - o_z) / d_z
    if s < 0:
        # Intersection is "behind" the camera
        return None

    hit = o_world + s * d_world
    return carla.Location(x=float(hit[0]), y=float(hit[1]), z=float(hit[2]))

# ---------- YOLO bbox → world helper ----------
def bbox_bottom_center_to_world(bbox, K, cam_transform, ground_z=0.0):
    """
    bbox: (x1, y1, x2, y2) in pixel coordinates
    Returns a carla.Location (or None) of where the center bottom of the bbox
    hits the ground plane.
    """
    x1, y1, x2, y2 = bbox
    u = 0.5 * (x1 + x2)  # center x
    v = y2               # bottom y

    return pixel_to_world(u, v, K, cam_transform, ground_z=ground_z)
