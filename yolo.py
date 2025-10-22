from ultralytics import YOLO
import cv2
import numpy as np
import os

video_path = r"C:\Users\fasts\Desktop\carla\traffic1.mp4"
save_vehicle_dir = r"C:\Users\fasts\Desktop\carla\detected_vehicles"
os.makedirs(save_vehicle_dir, exist_ok=True)

model = YOLO("yolov8n.pt") 
paused = False

ALLOWED_CLASSES = ["car", "truck", "person"]

# doesn't really work
def classify_color(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return "unknown"
    
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].flatten()
    s = hsv[:, :, 1].flatten()
    v = hsv[:, :, 2].flatten()
    mask = (s > 50) & (v > 50)
    if np.sum(mask) == 0:
        return "unknown"
    hue = np.median(h[mask])
    if hue < 10 or hue > 160:
        return "red"
    elif hue < 25:
        return "orange"
    elif hue < 35:
        return "yellow"
    elif hue < 85:
        return "green"
    elif hue < 135:
        return "blue"
    else:
        return "purple"


cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print("Error opening video")
    exit()

while True:
    if not paused:
        ret, frame = cap.read()
        if not ret:
            print("Video ended")
            break

        # YOLO detection
        results = model(frame)

        for cls_id, det, conf in zip(results[0].boxes.cls, results[0].boxes.xyxy, results[0].boxes.conf):
            class_name = model.names[int(cls_id)]
            if class_name not in ALLOWED_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, det)
            label = class_name
            if class_name in ["car", "truck"]:
                color_label = classify_color(frame, [x1, y1, x2, y2])
                label += f" ({color_label})"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Save snapshot
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                filename = f"{label}_{x1}_{y1}.png".replace(" ", "_")
                cv2.imwrite(os.path.join(save_vehicle_dir, filename), roi)

        # DeepSORT

        # from deep_sort_realtime.deepsort_tracker import DeepSort
        # tracker = DeepSort(max_age=30)
        # detections = []
        # for cls_id, det, conf in zip(results[0].boxes.cls, results[0].boxes.xyxy, results[0].boxes.conf):
        #     class_name = model.names[int(cls_id)]
        #     if class_name not in ALLOWED_CLASSES:
        #         continue
        #     x1, y1, x2, y2 = map(int, det)
        #     detections.append([x1, y1, x2, y2, float(conf)])
        # tracks = tracker.update_tracks(detections, frame=frame)
        # for track in tracks:
        #     if not track.is_confirmed():
        #         continue
        #     bbox = track.to_ltrb()
        #     track_id = track.track_id
        #     # draw track ID and color label as above

    # Display frame
    cv2.imshow("YOLO Vehicle Detection", frame)
    key = cv2.waitKey(0 if paused else 33) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('p'):
        paused = not paused

cap.release()
cv2.destroyAllWindows()
