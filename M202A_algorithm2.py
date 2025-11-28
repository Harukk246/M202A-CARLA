import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from scapy.all import rdpcap
import os

# Paths
CSV_PATH = r"C:\Users\fasts\Downloads\visible_ground_truth.csv"
PCAP_PATH = r"C:\Users\fasts\Downloads\encrypted.pcap"
OUTPUT_PATH = r"C:\Users\fasts\Downloads\solved_identities_final.csv"

# Camera Locations (x, y, z)
CAMERAS = {
    4:  np.array([35.000, -210.000, 7.500]),
    5:  np.array([27.500, 212.500, 7.500]),
    1:  np.array([25.000, -167.500, 2.500]),
    2:  np.array([65.000, -75.000, 5.000]),
    3:  np.array([67.500, -10.000, 2.500]),
    6:  np.array([20.000, -40.000, 5.000]),
    7:  np.array([20.000, 35.000, 5.000]),
    8:  np.array([-17.500, -77.500, 7.500]),
    9:  np.array([-7.500, 77.500, 7.500]),
    10: np.array([-12.500, -10.000, 2.500]),
    11: np.array([-35.000, -40.000, 7.500]),
    12: np.array([-35.000, 42.500, 5.000]),
    13: np.array([-65.000, 125.000, 5.000]),
    14: np.array([-87.500, -130.000, 7.500]),
    15: np.array([-92.500, -77.500, 7.500]),
    16: np.array([-82.500, -12.500, 7.500]),
    17: np.array([-85.000, 77.500, 7.500]),
    18: np.array([-157.500, -10.000, 7.500]),
    19: np.array([-115.000, -40.000, 15.000]),
    20: np.array([-115.000, 50.000, 15.000]),
    21: np.array([-157.500, -100.000, 15.000]),
    22: np.array([-157.500, 77.500, 12.500]),
    23: np.array([75.000, 70.000, 2.500]),
    24: np.array([130.000, -7.500, 2.500]),
    25: np.array([42.500, 140.000, 7.500])
}

class KalmanFilter:
    # Need to fix, might remove entirely
    def __init__(self, car_id, start_pos, start_time, start_vel):
        self.id = car_id
        self.last_time = start_time
        
        self.x = np.zeros(6)
        self.x[0:3] = start_pos
        self.x[3:6] = start_vel

        self.P = np.eye(6) * 100.0
        self.P[0:3, 0:3] *= 0.01 
        self.P[3:6, 3:6] *= 1.0 

        self.Q = np.eye(6)
        self.Q[0:3, 0:3] *= 0.1
        self.Q[3:6, 3:6] *= 25.0

        # Camera error
        self.R = np.eye(3) * 5.0 
        self.H = np.array([
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0]
        ])
        
        self.I = np.eye(6)
        self.x_pred = self.x.copy()
        self.P_pred = self.P.copy()

    def predict(self, t):
        dt = t - self.last_time
        self.F = np.eye(6)
        self.F[0, 3] = dt
        self.F[1, 4] = dt
        self.F[2, 5] = dt
        
        self.x_pred = self.F @ self.x
        self.P_pred = (self.F @ self.P @ self.F.T) + self.Q
        self.P_pred += np.eye(6) * 0.1

        return self.x_pred[0:3]

    #  Compare what camera sees vs what we predict to correct position + velocity
    def update(self, t, measurement):
        # Calculate Error (Residual): y = z - H * x
        z = measurement 
        y = z - (self.H @ self.x_pred)
        
        # Calculate System Uncertainty: S = H * P * H_transpose + R
        S = (self.H @ self.P_pred @ self.H.T) + self.R
        
        # Calculate Kalman Gain: K = P * H_transpose * Inverse(S)
        try:
            K = self.P_pred @ self.H.T @ np.linalg.inv(S)
        except:
            K = np.zeros((6, 3))

        # Update State: x = x + K * y
        self.x = self.x_pred + (K @ y)
        
        # Update Uncertainty: P = (I - K * H) * P
        self.P = (self.I - (K @ self.H)) @ self.P_pred
        
        self.last_time = t

def load_data():
    if not os.path.exists(CSV_PATH): raise FileNotFoundError("Missing CSV")
    if not os.path.exists(PCAP_PATH): raise FileNotFoundError("Missing PCAP")
    
    print("Loading Data...")
    df = pd.read_csv(CSV_PATH)
    packets = rdpcap(PCAP_PATH)
    
    # Extract packet events
    events = []
    for pkt in packets:
        if pkt.haslayer('UDP'):
            try:
                ts = float(pkt.time)
                cam_id = int(pkt['UDP'].dport) - 5000
                if cam_id in CAMERAS:
                    events.append({'timestamp': ts, 'camera_id': cam_id, 'camera_pos': CAMERAS[cam_id]})
            except: continue
            
    return df, pd.DataFrame(events)

# For each car find first and last positions, estimate velocity
# Separates left turning cars from right turning cars
# Convert encrypted packets into ordered time events 
def run_tracking(df_vis, df_enc):
    results = []
    trackers = {}
    
    for car_id, group in df_vis.groupby('car_id'):
        group = group.sort_values('timestamp')
        start = group.iloc[0]
        end = group.iloc[-1]
        
        p1 = np.array([start['x'], start['y'], start['z']])
        p2 = np.array([end['x'], end['y'], end['z']])
        total_time = end['timestamp'] - start['timestamp']
        
        vel = (p2 - p1) / total_time if total_time > 0 else np.zeros(3)
        
        trackers[car_id] = KalmanFilter(car_id, p1, start['timestamp'], vel)

    cars = list(trackers.keys())
    
    events = []
    for idx, row in df_enc.iterrows():
        events.append({
            'type': 'encrypted', 'time': row['timestamp'],
            'pos': row['camera_pos'], 'id': row['camera_id']
        })
    events.sort(key=lambda x: x['time'])
    
    window = 0.5
    start_time = 0.0
    batch = []
    
    for e in events:
        if e['time'] > start_time + window:
            match_and_update(batch, trackers, cars, results)
            batch = []
            start_time = float(e['time']) 
        batch.append(e)
        
    if batch: match_and_update(batch, trackers, cars, results)

    return pd.DataFrame(results)

def match_and_update(batch, trackers, cars, results):
    if not batch: return
    
    # Cost matrix for distance between predicted car position + camera location
    matrix = np.zeros((len(cars), len(batch)))
    
    for r, car_id in enumerate(cars):
        kf = trackers[car_id]
        for c, event in enumerate(batch):
            pred = kf.predict(event['time'])
            # 2D distance (iggnore z height)
            dist = np.linalg.norm(pred[0:2] - event['pos'][0:2])
            matrix[r, c] = dist
            
    # Softmax Confidence based on distance
    sigma = 20.0
    neg = -matrix / sigma
    neg -= np.max(neg, axis=0)
    probs = np.exp(neg) / np.sum(np.exp(neg), axis=0)
    
    # Hungarian for finding best assignment between cars and events
    # One car <-> one event
    rows, cols = linear_sum_assignment(matrix)
    
    # Update Trackers
    for r, c in zip(rows, cols):
        dist = matrix[r, c]
        conf = probs[r, c]
        event = batch[c]
        car_id = cars[r]
        kf = trackers[car_id]

        if dist < 150.0:
            results.append({
                'timestamp': event['time'],
                'encrypted_camera_id': event['id'],
                'assigned_car_id': car_id,
                'distance_error': round(dist, 2),
                'softmax_confidence': f"{conf:.2%}"
            })
            
            kf.predict(event['time'])
            kf.update(event['time'], event['pos'])

if __name__ == "__main__":
    try:
        vis_df, enc_df = load_data()
        final = run_tracking(vis_df, enc_df)
        final.sort_values('timestamp').to_csv(OUTPUT_PATH, index=False)
        print("DONE. Results saved.")
        print(final.head(20))
    except Exception as e:
        print(f"Error: {e}")