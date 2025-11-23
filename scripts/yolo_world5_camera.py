import carla
import util
import numpy as np
import cv2
import subprocess
from queue import Queue, Empty
from ultralytics import YOLO
from collections import defaultdict
import time
import math
import threading

# Hardcoded camera ID - change this to process different cameras
CAMERA_ID = 4

# Import camera configurations from util
CAMERA_CONFIGS = util.CAMERA_CONFIGS

# scaling factor to detect distant cars
SCALE_FACTOR = 2.0

class VehicleKalmanFilter:
    def __init__(self, initial_pos_x, initial_pos_y, initial_time):
        self.kf = cv2.KalmanFilter(4, 2)
        
        # pos = pos + vel*dt, [x, y, v_x, v_y]
        self.kf.transitionMatrix = np.array([
            [1, 0, 0.05, 0], # 0.05 is placeholder dt
            [0, 1, 0, 0.05],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], np.float32)

        # measure position
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0], #x
            [0, 1, 0, 0] #y
        ], np.float32)

        # uncertainty in physics model
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.1 # 1e-2

        # uncertainty in yolo
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.3 # 1e0

        # initial error
        self.kf.errorCovPost = np.eye(4, dtype=np.float32) * 1.0

        # initialize state
        self.kf.statePost = np.array([
            [initial_pos_x], 
            [initial_pos_y], 
            [0], 
            [0]
        ], np.float32)
        
        self.last_time = initial_time

    # predict next state
    def predict(self, current_time):
        dt = current_time - self.last_time
        if dt <= 0: dt = 0.03 # fallback to ~30fps
        
        # update transition matrix with actual dt
        self.kf.transitionMatrix[0, 2] = dt
        self.kf.transitionMatrix[1, 3] = dt
        
        self.last_time = current_time
        return self.kf.predict()

    #correct predicted state with new measurements
    def update(self, measurement_x, measurement_y):
        measurement = np.array([[measurement_x], [measurement_y]], np.float32)
        self.kf.correct(measurement)
        
        return self.kf.statePost

# helper functions
def get_world_from_pixels(u, v, ground_z, K, cam_transform):
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    
    # convert pixel to normalized camer frame
    x_nd = (u - cx) / fx
    y_nd = (v - cy) / fy
    
    # camera to carla
    point_carla_local = np.array([1.0, x_nd, -y_nd, 1.0]) 

    M_cam_to_world = np.array(cam_transform.get_matrix())
    cam_pos_w = M_cam_to_world[:3, 3]
    ray_dir_w = np.dot(M_cam_to_world[:3, :3], point_carla_local[:3])
    
    # ray-plane intersection with ground
    if abs(ray_dir_w[2]) < 1e-6: return None
    t = (ground_z - cam_pos_w[2]) / ray_dir_w[2]
    if t < 0: return None
    
    return cam_pos_w + t * ray_dir_w

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

def create_ffmpeg_decoder(port):
    """Create ffmpeg command to decode HEVC stream from UDP port."""
    return [
        "ffmpeg",
        "-loglevel", "error",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-i", f"udp://127.0.0.1:{port}?pkt_size=1316",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{util.WIDTH}x{util.HEIGHT}",
        "-"
    ]

def main():
    # Find camera configuration
    config = next((c for c in CAMERA_CONFIGS if c["id"] == CAMERA_ID), None)
    if config is None:
        raise ValueError(f"Camera ID {CAMERA_ID} not found in CAMERA_CONFIGS")
    port = 5000 + CAMERA_ID
    
    print(f"Connecting to camera {CAMERA_ID} on UDP port {port}...")
    
    # Connect to CARLA to get vehicle positions for ground truth
    util.common_init()
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    util.check_sync(world)
    
    # Get camera transform for world coordinate projection
    pos = config["pos"]
    rot = config["rot"]
    cam_loc = carla.Location(x=pos[0], y=pos[1], z=pos[2])
    cam_rot = carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2])
    cam_tf = carla.Transform(cam_loc, cam_rot)
    
    # Setup camera intrinsics for projecting to world frame
    K = build_intrinsic_matrix(util.WIDTH, util.HEIGHT, util.FOV)
    ground_z = 0.0
    
    # Fetch all vehicles in world for ground truth
    vehicles = world.get_actors().filter('vehicle.*')
    
    # Setup ffmpeg decoder
    proc = subprocess.Popen(
        create_ffmpeg_decoder(port),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=util.WIDTH * util.HEIGHT * 3  # BGR24 = 3 bytes per pixel
    )
    
    print("Loading YOLOv8m...")
    model = YOLO("yolov8m.pt")
    ALLOWED_CLASSES = {"car", "truck", "bus", "motorbike"}
    
    # Kalman filter
    track_filters = {}
    smoothed_boxes = {}
    IMG_ALPHA = 0.15
    
    print("YOLO tracking started...")
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            # Read frame from ffmpeg decoder
            raw_frame = proc.stdout.read(util.WIDTH * util.HEIGHT * 3)
            if len(raw_frame) != util.WIDTH * util.HEIGHT * 3:
                if proc.poll() is not None:
                    stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')
                    print(f"ffmpeg decoder exited: {stderr_output}")
                    break
                continue
            
            # Convert to numpy array
            arr = np.frombuffer(raw_frame, np.uint8).reshape((util.HEIGHT, util.WIDTH, 3))
            scaled_arr = cv2.resize(arr, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
            
            # Get current simulation time for Kalman filter
            snapshot = world.wait_for_tick()
            current_time = snapshot.timestamp.elapsed_seconds
            
            # YOLO
            results = model.track(scaled_arr, persist=True, tracker="bytetrack.yaml", conf=0.35, iou=0.5, verbose=False)
            
            active_ids = set()
            
            for result in results:
                if result.boxes is None or result.boxes.id is None: continue
                
                boxes = result.boxes.cpu().numpy()
                for box_data, cls_id, tid in zip(boxes.xyxy, boxes.cls, boxes.id):
                    if model.names[int(cls_id)] not in ALLOWED_CLASSES: continue
                    
                    active_ids.add(tid)
                    x1, y1, x2, y2 = box_data / SCALE_FACTOR
                    
                    # smooth bounding boxes
                    if tid in smoothed_boxes:
                        smoothed_box = IMG_ALPHA * smoothed_boxes[tid] + (1 - IMG_ALPHA) * np.array([x1, y1, x2, y2])
                    else:
                        smoothed_box = np.array([x1, y1, x2, y2])
                    smoothed_boxes[tid] = smoothed_box
                    sx1, sy1, sx2, sy2 = smoothed_box.astype(int)
                    
                    # project bottom center of box to world
                    u_c, v_b = (sx1 + sx2) / 2.0, sy2
                    raw_world_pos = get_world_from_pixels(u_c, v_b, ground_z, K, cam_tf)
                    
                    state_text = "Init"
                    truth_text = "" # for ground truth
                    color = (0, 255, 255)
                    
                    if raw_world_pos is not None:
                        wx, wy = raw_world_pos[0], raw_world_pos[1]
                        
                        # initialize Kalman filter if new
                        if tid not in track_filters:
                            track_filters[tid] = VehicleKalmanFilter(wx, wy, current_time)
                        
                        # predict next state
                        track_filters[tid].predict(current_time)
                        
                        # update with measurement
                        estimated_state = track_filters[tid].update(wx, wy)
                        
                        smooth_x = estimated_state[0][0]
                        smooth_y = estimated_state[1][0]
                        smooth_vx = estimated_state[2][0]
                        smooth_vy = estimated_state[3][0]
                        
                        speed_kmh = np.sqrt(smooth_vx**2 + smooth_vy**2) * 3.6
                        
                        # remove 0.5km/h drift on stopped cars
                        if speed_kmh < 1.5: speed_kmh = 0.0
                        
                        state_text = f"Pos:({smooth_x:.1f}, {smooth_y:.1f}) Vel:{speed_kmh:.0f}km/h"
                        color = (0, 255, 0) # green for active tracking
                        
                        #  ground truth
                        smooth_pos = np.asarray([smooth_x, smooth_y])
                        ground_truth_pos, min_dist = util.get_closest_carla_vehicle(smooth_pos, vehicles)
                        ground_truth_text = f"CARLA: ({ground_truth_pos[0]:.1f}, {ground_truth_pos[1]:.1f}), Err: {min_dist:.2f}"
                        cv2.putText(arr, ground_truth_text, (sx1, sy2+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    # draw bounding box and label
                    cv2.rectangle(arr, (sx1, sy1), (sx2, sy2), color, 2)
                    cv2.putText(arr, f"ID:{int(tid)} {state_text}", (sx1, sy1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # remove filters for tracks that disappeared
            for old_id in list(track_filters.keys()):
                if old_id not in active_ids:
                    del track_filters[old_id]
            
            cv2.imshow(f"YOLO Camera {CAMERA_ID}", arr)
            
            # exit on escape
            if cv2.waitKey(1) == 27: break
            
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"Processed {frame_count} frames, FPS: {fps:.2f}")
    
    except KeyboardInterrupt: 
        pass
    finally:
        print("\nShutting down...")
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        cv2.destroyAllWindows()
        client = None

if __name__ == "__main__":
    main()

