import numpy as np
from pathlib import Path
from typing import Dict


VIDEO_FEATURES_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet/video_features")
PCAP_FEATURES_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet/pcap_features")
DATASET_OUTPUT_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet")
X_OUTPUT_PATH = DATASET_OUTPUT_DIR / "combined_X.npy"
Y_OUTPUT_PATH = DATASET_OUTPUT_DIR / "combined_y.npy"


def _load_feature_map(directory: Path) -> Dict[str, Path]:
    """Return mapping of feature file stem -> path."""
    return {path.stem: path for path in directory.glob("*.npy")}


def preprocess_feature_pairs() -> None:
    video_files = _load_feature_map(VIDEO_FEATURES_DIR)
    pcap_files = _load_feature_map(PCAP_FEATURES_DIR)

    common_cameras = sorted(video_files.keys() & pcap_files.keys())
    if not common_cameras:
        raise RuntimeError("No overlapping camera feature files found.")

    print(f"Found {len(common_cameras)} matching feature pairs.")
    X_blocks = []
    y_blocks = []
    for camera in common_cameras:
        pcap = np.load(pcap_files[camera])
        video = np.load(video_files[camera])

        X = pcap
        target_rows = X.shape[0]

        if video.ndim == 1:
            video = video.reshape(-1, 1)
        if video.shape[0] < target_rows:
            print(
                f"Warning: video features for {camera} shorter than pcap features "
                f"({video.shape[0]} vs {target_rows})."
            )

        y = video[:target_rows]

        print(f"{camera}: X shape {X.shape}, y shape {y.shape}")

        X_blocks.append(X)
        y_blocks.append(y)

    if not X_blocks:
        raise RuntimeError("No feature blocks were collected.")

    DATASET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    X_all = np.concatenate(X_blocks, axis=0)
    y_all = np.concatenate(y_blocks, axis=0)
    np.save(X_OUTPUT_PATH, X_all)
    np.save(Y_OUTPUT_PATH, y_all)
    print(f"Saved concatenated arrays: X -> {X_OUTPUT_PATH}, y -> {Y_OUTPUT_PATH}")


if __name__ == "__main__":
    preprocess_feature_pairs()
