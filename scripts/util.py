import random
import carla
import numpy as np

WIDTH = 1280
HEIGHT = 720
FOV = 90
FPS = 20

# Camera configurations
CAMERA_CONFIGS = [
    # Visible cameras
    {"id": 4, "pos": (35.000, -210.000, 7.500), "rot": (-28.00, 86.00, 0.00)},
    {"id": 5, "pos": (27.500, 212.500, 7.500), "rot": (-28.00, 268.00, 0.00)},
    
    # Encrypted cameras
    {"id": 1, "pos": (25.000, -167.500, 2.500), "rot": (-28.00, 0.00, 0.00)},
    {"id": 2, "pos": (65.000, -75.000, 5.000), "rot": (-20.00, 292.00, 0.00)},
    {"id": 3, "pos": (67.500, -10.000, 2.500), "rot": (-10.00, 90.00, 0.00)},
    {"id": 6, "pos": (20.000, -40.000, 5.000), "rot": (-28.00, 0.00, 0.00)},
    {"id": 7, "pos": (20.000, 35.000, 5.000), "rot": (-28.00, 0.00, 0.00)},
    {"id": 8, "pos": (-17.500, -77.500, 7.500), "rot": (-38.00, 276.00, 0.00)},
    {"id": 9, "pos": (-7.500, 77.500, 7.500), "rot": (-34.00, 90.00, 0.00)},
    {"id": 10, "pos": (-12.500, -10.000, 2.500), "rot": (-14.00, 90.00, 0.00)},
    {"id": 11, "pos": (-35.000, -40.000, 7.500), "rot": (-26.00, 180.00, 0.00)},
    {"id": 12, "pos": (-35.000, 42.500, 5.000), "rot": (-24.00, 180.00, 0.00)},
    {"id": 13, "pos": (-65.000, 125.000, 5.000), "rot": (-26.00, 38.00, 0.00)},
    {"id": 14, "pos": (-87.500, -130.000, 7.500), "rot": (-28.00, 316.00, 0.00)},
    {"id": 15, "pos": (-92.500, -77.500, 7.500), "rot": (-38.00, 276.00, 0.00)},
    {"id": 16, "pos": (-82.500, -12.500, 7.500), "rot": (-36.00, 90.00, 0.00)},
    {"id": 17, "pos": (-85.000, 77.500, 7.500), "rot": (-44.00, 90.00, 0.00)},
    {"id": 18, "pos": (-157.500, -10.000, 7.500), "rot": (-46.00, 90.00, 0.00)},
    {"id": 19, "pos": (-115.000, -40.000, 15.000), "rot": (-50.00, 182.00, 0.00)},
    {"id": 20, "pos": (-115.000, 50.000, 15.000), "rot": (-54.00, 180.00, 0.00)},
    {"id": 21, "pos": (-157.500, -100.000, 15.000), "rot": (-58.00, 90.00, 0.00)},
    {"id": 22, "pos": (-157.500, 77.500, 12.500), "rot": (-52.00, 90.00, 0.00)},
    {"id": 23, "pos": (75.000, 70.000, 2.500), "rot": (-8.00, 54.00, 0.00)},
    {"id": 24, "pos": (130.000, -7.500, 2.500), "rot": (-26.00, 90.00, 0.00)},
    {"id": 25, "pos": (42.500, 140.000, 7.500), "rot": (-30.00, 180.00, 0.00)},

    # Overhead spectator
    {"id": "overhead", "pos": (-50, 0, 260), "rot": (-90, 0, 0)}
]

def common_init():
    random.seed(42)

def check_sync(world):
    # Detect sync mode & set up a safe tick loop
    settings = world.get_settings()

    print(f"Sync mode: {settings.synchronous_mode}")

    if settings.synchronous_mode == False:
        print("CARLA is in async mode! Setting to synchronous mode...")

        settings.synchronous_mode = True        # Enable synchronous mode
        settings.fixed_delta_seconds = 1 / FPS      # 20 FPS simulation step (adjust as needed)

        world.apply_settings(settings)

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

def get_closest_carla_vehicle(pos, vehicles):
    closest_act_pos = np.zeros(2)
    min_dist = float('inf')

    for vehicle in vehicles:
        act_pos_raw = vehicle.get_location()
        act_pos = np.asarray([act_pos_raw.x, act_pos_raw.y])
        dist = np.linalg.norm(act_pos - pos)

        if dist < min_dist:
            min_dist = dist
            closest_act_pos = act_pos

    return closest_act_pos, min_dist