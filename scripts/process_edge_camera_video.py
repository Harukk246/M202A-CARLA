import util

import cv2
import numpy as np
from ultralytics import YOLO

import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
import json

import torchreid

PATH_4 = "/home/ubuntu/M202A-CARLA/scripts/global_id_test_videos/black_blue/camera_4.mp4"
PATH_5 = "/home/ubuntu/M202A-CARLA/scripts/global_id_test_videos/black_blue/camera_5.mp4"

OUTPUT_4_PATH = "/home/ubuntu/M202A-CARLA/scripts/global_id_test_videos/black_blue/camera_4_input.json"
OUTPUT_5_PATH = "/home/ubuntu/M202A-CARLA/scripts/global_id_test_videos/black_blue/camera_5_input.json"

COLOR = (0, 255, 0) # green for active tracking

class ReIDModelOSNet(nn.Module):
    def __init__(self, embedding_dim: int = 512):
        super().__init__()
        # OSNet backbone from Torchreid
        self.backbone = torchreid.models.build_model(
            name='osnet_x1_0',          # or osnet_x1_25 if you want bigger
            num_classes=1000,           # unused for embeddings
            pretrained=True
        )
        # Torchreid models usually expose a 'classifier' / 'head' – drop it for pure embeddings
        if hasattr(self.backbone, 'classifier'):
            self.backbone.classifier = nn.Identity()

    def forward(self, x):
        feat = self.backbone(x)         # [B, C]
        feat = nn.functional.normalize(feat, p=2, dim=1)
        return feat

# ---------------------------
# 1. Simple ReID / embedding model
# ---------------------------
class ReIDModel(nn.Module):
    """
    Very simple ReID backbone:
    - ResNet18 pretrained on ImageNet
    - Replace the FC head with a 128-D embedding
    -   the final FC head takes the embedding and computes class logits, we 
    -   skip this entirely and just steal the embedding, which doesn't
    -   neccesarily have to be constrained to the 1000 classes.
    - L2-normalize the output so we can use cosine similarity
    """
    def __init__(self, embedding_dim: int = 128):
        super().__init__()
        backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        # remove the original fc
        self.feature_extractor = nn.Sequential(*list(backbone.children())[:-1])  # [B, 512, 1, 1]
        self.fc = nn.Linear(512, embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.feature_extractor(x)        # [B, 512, 1, 1]
        feat = feat.view(feat.size(0), -1)      # [B, 512]
        emb = self.fc(feat)                     # [B, D]
        emb = nn.functional.normalize(emb, p=2, dim=1)
        return emb

# Standard image transforms for the ReID model
reid_transform = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(
        mean=[0.485, 0.456, 0.406],  # ImageNet stats
        std=[0.229, 0.224, 0.225],
    ),
])

def extract_embedding(model: nn.Module, device, img_bgr: np.ndarray) -> np.ndarray:
    """
    Take a BGR crop (OpenCV format), convert to RGB, transform, run through ReID model.
    Returns a 1D numpy array embedding (L2-normalized).
    """
    # defensive: if crop is empty, return None
    if img_bgr.size == 0:
        return None

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    tensor = reid_transform(img_rgb).unsqueeze(0).to(device)  # [1, 3, H, W]

    with torch.no_grad():
        emb = model(tensor)  # [1, D]
    emb_np = emb[0].cpu().numpy()  # [D]
    return emb_np

# -------------------------------------------------------------------
# 2. Global appearance-based tracker across BOTH cameras
# -------------------------------------------------------------------
class GlobalAppearanceTracker:
    """
    Maintains a gallery of "global tracks" across *all* cameras.

    For each new detection embedding:
        - compute cosine similarity to existing global tracks
        - if best similarity >= threshold -> assign that global ID
        - else create a new global ID

    This is *appearance-only* (no timing, no geometry, no motion).
    """

    def __init__(self, sim_threshold: float = 0.7):
        self.sim_threshold = sim_threshold
        self.next_global_id = 1
        # global_id -> dict with keys: 'embedding', 'history'
        self.tracks = {}

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
        return float(np.dot(a, b) / denom)

    # constantly update stored global embeddings so we keep embedding state
    # as current as possible. 80% prev and 20% new, acts like a low pass filter.
    def update_gallery_embedding(self, global_id: int, new_emb: np.ndarray):
        """Running average of embeddings to keep track representation stable."""
        old_emb = self.tracks[global_id]["embedding"]
        updated = 0.8 * old_emb + 0.2 * new_emb
        updated /= np.linalg.norm(updated) + 1e-8
        self.tracks[global_id]["embedding"] = updated

    def assign_global_ids(self, embeddings, camera_id: int, frame_idx: int, bboxes, local_ids):
        """
        embeddings: list of np.ndarray (each [D])
        camera_id:  4 or 5 (or 0/1, any int)
        frame_idx:  current frame number
        bboxes:     list of [x1, y1, x2, y2]
        local_ids:  list of per-camera ByteTrack track_ids

        Returns: list of global IDs, same length/order as embeddings.
        """
        assigned_ids = []

        for emb, bbox, local_id in zip(embeddings, bboxes, local_ids):
            if emb is None:
                assigned_ids.append(-1)
                continue

            best_id = None
            best_sim = -1.0

            # Compare with existing global tracks
            for gid, info in self.tracks.items():
                sim = self.cosine_similarity(emb, info["embedding"])
                if sim > best_sim:
                    best_sim = sim
                    best_id = gid

            if best_id is not None and best_sim >= self.sim_threshold:
                # Match found -> update track
                assigned_ids.append(best_id)
                self.update_gallery_embedding(best_id, emb)

                self.tracks[best_id]["history"].append({
                    "camera_id": camera_id,
                    "local_id": local_id,
                    "frame_idx": frame_idx,
                    "bbox": bbox,
                })
            else:
                # No match -> new global ID
                gid = self.next_global_id
                self.next_global_id += 1

                self.tracks[gid] = {
                    "embedding": emb,
                    "history": [{
                        "camera_id": camera_id,
                        "local_id": local_id,
                        "frame_idx": frame_idx,
                        "bbox": bbox,
                    }]
                }
                assigned_ids.append(gid)

        return assigned_ids

def main() -> None:
    
    # ---------------------------
    # Video setup
    # ---------------------------
    cap4 = cv2.VideoCapture(PATH_4)
    cap5 = cv2.VideoCapture(PATH_5)

    if not cap4.isOpened():
        print(f"Error: could not open video {PATH_4}")
        return
    if not cap5.isOpened():
        print(f"Error: could not open video {PATH_5}")
        return

    # ---------------------------
    # YOLO model (detector)
    # ---------------------------
    print("Loading YOLOv8m...")
    yolo_model4 = YOLO("yolov8x.pt") # two seperate models because it maintains internal state
    yolo_model5 = YOLO("yolov8x.pt")
    ALLOWED_CLASSES = {"car", "truck", "bus", "motorbike"}

    # ---------------------------
    # ReID / embedding model
    # ---------------------------
    print("Loading ReID...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    # fallback to ReIDModel if needed.
    reid_model = ReIDModelOSNet(embedding_dim=512).to(device)
    reid_model.eval()

    # ---------------------------------------------------------------
    # Global appearance-based tracker (shared across both cameras)
    # ---------------------------------------------------------------
    # WARNING: THIS VALUE IS EXTREMELY SENSITIVE
    # use 0.86 for regular resnet
    global_tracker = GlobalAppearanceTracker(sim_threshold=0.65)

    # ---------------------------------------------------------------
    # MAIN LOOP BEGIN ===============================================
    # ---------------------------------------------------------------

    frame_idx = 0
    camera_4_output = []
    camera_5_output = []

    # DEBUG: can comment these lines out for faster processing
    cv2.namedWindow("camera_4", cv2.WINDOW_NORMAL)
    cv2.namedWindow("camera_5", cv2.WINDOW_NORMAL)

    while True:
        ret4, frame4 = cap4.read()
        ret5, frame5 = cap5.read()

        # Stop when either video ends
        if not ret4 or not ret5:
            break

        # All processing happens here after loading frames.

        # ----------------------------------------
        # 1) YOLO detection
        # ----------------------------------------
        results4 = yolo_model4.track(
            frame4,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.35,
            iou=0.5,
            verbose=False,
        )[0]
        results5 = yolo_model5.track(
            frame5,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.35,
            iou=0.5,
            verbose=False,
        )[0]

        dets_cam4 = []  # (embedding, bbox, local_id)
        dets_cam5 = []

        # Process camera 4 frame.
        for result in results4:
            if result.boxes is None or result.boxes.id is None: continue

            boxes = result.boxes.cpu().numpy()
            for box_data, cls_id, track_id in zip(boxes.xyxy, boxes.cls, boxes.id):

                    cls_id = int(cls_id)
                    track_id = int(track_id)

                    # don't track anything but vehicles
                    if yolo_model4.names[int(cls_id)] not in ALLOWED_CLASSES: continue

                    # fetch bounding box corners
                    x1, y1, x2, y2 = box_data.astype(int)

                    # get frame height and width
                    h5, w5 = frame4.shape[:2]

                    # generate parameters for image crop
                    x1 = int(max(0, min(w5 - 1, x1)))
                    x2 = int(max(0, min(w5 - 1, x2)))
                    y1 = int(max(0, min(h5 - 1, y1)))
                    y2 = int(max(0, min(h5 - 1, y2)))
                    if x2 <= x1 or y2 <= y1:
                        continue

                    crop = frame4[y1:y2, x1:x2]
                    # DEBUG: cv2.imshow("cropped_vehicle", crop)  # visualize the most recent crop
                    emb = extract_embedding(reid_model, device, crop)

                    # get resnet embedding, bounding box, and local bytetrack id
                    dets_cam4.append((emb, [x1, y1, x2, y2], track_id))

                    # DEBUG: show green identification rectangle
                    cv2.rectangle(frame4, (x1, y1), (x2, y2), COLOR, 2)
                    
        # Process camera 5 frame.
        for result in results5:
            if result.boxes is None or result.boxes.id is None: continue

            boxes = result.boxes.cpu().numpy()
            for box_data, cls_id, track_id in zip(boxes.xyxy, boxes.cls, boxes.id):

                    cls_id = int(cls_id)
                    track_id = int(track_id)

                    # don't track anything but vehicles
                    if yolo_model5.names[int(cls_id)] not in ALLOWED_CLASSES: continue

                    # fetch bounding box corners
                    x1, y1, x2, y2 = box_data.astype(int)

                    # get frame height and width
                    h5, w5 = frame5.shape[:2]

                    # generate parameters for image crop
                    x1 = int(max(0, min(w5 - 1, x1)))
                    x2 = int(max(0, min(w5 - 1, x2)))
                    y1 = int(max(0, min(h5 - 1, y1)))
                    y2 = int(max(0, min(h5 - 1, y2)))
                    if x2 <= x1 or y2 <= y1:
                        continue

                    crop = frame5[y1:y2, x1:x2]
                    # DEBUG: cv2.imshow("cropped_vehicle", crop)  # visualize the most recent crop
                    emb = extract_embedding(reid_model, device, crop)

                    # get resnet embedding, bounding box, and local bytetrack id
                    dets_cam5.append((emb, [x1, y1, x2, y2], track_id))

                    # DEBUG: show green identification rectangle
                    cv2.rectangle(frame5, (x1, y1), (x2, y2), COLOR, 2)

        # ----------------------------------------
        # 3) Global ID assignment (appearance-only)
        # ----------------------------------------
        
        if dets_cam4:
            emb4   = [e for (e, b, tid) in dets_cam4]
            box4   = [b for (e, b, tid) in dets_cam4]
            lid4   = [tid for (e, b, tid) in dets_cam4]
            global_ids4 = global_tracker.assign_global_ids(
                emb4, camera_id=4, frame_idx=frame_idx, bboxes=box4, local_ids=lid4
            )
        else:
            lid4 = []
            global_ids4 = []
        
        if dets_cam5:
            emb5   = [e for (e, b, tid) in dets_cam5]
            box5   = [b for (e, b, tid) in dets_cam5]
            lid5   = [tid for (e, b, tid) in dets_cam5]
            global_ids5 = global_tracker.assign_global_ids(
                emb5, camera_id=5, frame_idx=frame_idx, bboxes=box5, local_ids=lid5
            )
        else:
            lid5 = []
            global_ids5 = []

        # ----------------------------------------
        # 4) Preprare for output generation
        # ----------------------------------------

        '''
        Output of this script can look like:
        per camera:

        the vector index implicitly serves as the frame index
        [0|1 for if car detected, [pos/vel of cars], [id of cars]]
        '''

        camera_4_output_frame = {
            'frame': frame_idx,
            'car_detected': True if any(global_ids4) else False,
            'camera_pos': util.CAMERA_CONFIGS[0]["pos"],
            'cars': []
        }

        # If this frame has any global detections, append entries to `cars`
        # with global_id, local_id, and placeholder xyz position [0, 0, 0].
        if any(global_ids4):
            for local_id, global_id in zip(lid4, global_ids4):
                if global_id is None:
                    continue
                camera_4_output_frame['cars'].append({
                    'global_id': int(global_id),
                    'local_id': int(local_id),
                    'position': [0.0, 0.0, 0.0], # TODO: fill this code in from camera.py
                })

        camera_4_output.append(camera_4_output_frame)

        camera_5_output_frame = {
            'frame': frame_idx,
            'car_detected': True if any(global_ids5) else False,
            'camera_pos': util.CAMERA_CONFIGS[1]["pos"],
            'cars': []
        }

        # If this frame has any global detections, append entries to `cars`
        # with global_id, local_id, and placeholder xyz position [0, 0, 0].
        if any(global_ids5):
            for local_id, global_id in zip(lid5, global_ids5):
                if global_id is None:
                    continue
                camera_5_output_frame['cars'].append({
                    'global_id': int(global_id),
                    'local_id': int(local_id),
                    'position': [0.0, 0.0, 0.0], # TODO: fill this code in from camera.py
                })

        camera_5_output.append(camera_5_output_frame)

        # DEBUG: can comment these lines out for faster processing
        print("frame:", frame_idx, "global_ids4:", global_ids4, "global_ids5", global_ids5)
        cv2.imshow("camera_4", frame4)
        cv2.imshow("camera_5", frame5)

        frame_idx += 1

        # DEBUG: can comment these lines out for faster processing
        key = cv2.waitKey(33) & 0xFF
        if key == ord("q"):
            break

    # ----------------------------------------
    # 45) Cleanup operations and save data
    # ----------------------------------------

    with open(OUTPUT_4_PATH, "w") as f:
        json.dump(camera_4_output, f, indent=2)

    with open(OUTPUT_5_PATH, "w") as f:
        json.dump(camera_5_output, f, indent=2)

    # DEBUG: can comment these lines out for faster processing
    cap4.release()
    cap5.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

