from ultralytics import YOLO
import cv2
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --------------------------
# Config
# --------------------------
video_path = r"C:\Users\fasts\Desktop\carla\traffic1.mp4"
save_vehicle_dir = r"C:\Users\fasts\Desktop\carla\detected_vehicles"
pdf_path = os.path.join(save_vehicle_dir, "vehicle_summary.pdf")
os.makedirs(save_vehicle_dir, exist_ok=True)

model = YOLO("yolov8n.pt")
ALLOWED_CLASSES = ["car", "truck", "bus", "motorbike"]

# --------------------------
# Video setup
# --------------------------
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
frame_idx = 0

# --------------------------
# Tracking + ID remap
# --------------------------
id_map = {}
next_ordered_id = 1
vehicle_times = {}  # ordered_id -> {class, enter, exit, snapshot}

# --------------------------
# Process video
# --------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    current_time = frame_idx / fps
    frame_idx += 1

    # YOLO + ByteTrack tracking
    results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)

    for result in results:
        boxes = result.boxes
        if boxes.id is None:
            continue

        for box in boxes:
            cls = int(box.cls.item())
            class_name = model.names[cls]
            if class_name not in ALLOWED_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            raw_id = int(box.id.item())

            # Remap ordered ID
            if raw_id not in id_map:
                id_map[raw_id] = next_ordered_id
                next_ordered_id += 1
            ordered_id = id_map[raw_id]

            # Treat the camera view as the zone
            if ordered_id not in vehicle_times:
                vehicle_times[ordered_id] = {
                    "class": class_name,
                    "enter": current_time,
                    "exit": current_time,
                    "snapshot": None
                }
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    # save snapshot
                    img_path = os.path.join(save_vehicle_dir, f"vehicle_{ordered_id}.jpg")
                    cv2.imwrite(img_path, crop)
                    vehicle_times[ordered_id]["snapshot"] = img_path
            else:
                vehicle_times[ordered_id]["exit"] = current_time

            # Draw bounding box and ID
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID {ordered_id}: {class_name}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Vehicle Tracking (Full Frame)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# --------------------------
# Generate PDF report
# --------------------------
sorted_entries = sorted(vehicle_times.items(), key=lambda x: x[1]["enter"])
doc = SimpleDocTemplate(pdf_path, pagesize=letter)
styles = getSampleStyleSheet()
story = []

for tid, info in sorted_entries:
    if info["snapshot"] and os.path.exists(info["snapshot"]):
        story.append(Image(info["snapshot"], width=300, height=200))
    dwell = info["exit"] - info["enter"]
    story.append(Paragraph(f"ID {tid} | Class: {info['class']}", styles["Normal"]))
    story.append(Paragraph(f"Enter: {info['enter']:.2f}s | Exit: {info['exit']:.2f}s | Dwell: {dwell:.2f}s", styles["Normal"]))
    story.append(Spacer(1, 20))

doc.build(story)
print(f"✅ PDF saved at {pdf_path}")
