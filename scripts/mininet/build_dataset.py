import numpy as np
from pathlib import Path
from typing import Dict


VIDEO_FEATURES_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet/video_features")
PCAP_FEATURES_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet/pcap_features")
DATASET_OUTPUT_DIR = Path("/home/ubuntu/M202A-CARLA/scripts/mininet/dataset")


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
    for camera in common_cameras:
        pcap = np.load(pcap_files[camera])
        video = np.load(video_files[camera])

        X = pcap[:, (0,1,3)] # pkt count, total pkt size, pkt std dev
        target_rows = X.shape[0]

        if video.ndim == 1:
            video = video.reshape(-1, 1)
        if video.shape[0] < target_rows:
            print(
                f"Warning: video features for {camera} shorter than pcap features "
                f"({video.shape[0]} vs {target_rows})."
            )

        # assume Y is always larger than X, so we can slice Y to the same length as X
        y = video[:target_rows]

        # Remove first 500 elements from both X and y
        # get rid of networking noise at the beginning
        X = X[500:]
        y = y[500:]

        # Standardize X: zero mean and unit variance
        X = (X - X.mean(axis=0)) / X.std(axis=0)

        print(f"{camera}: X shape {X.shape}, y shape {y.shape}")

        DATASET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        X_path = DATASET_OUTPUT_DIR / f"{camera}_X.npy"
        y_path = DATASET_OUTPUT_DIR / f"{camera}_y.npy"
        np.save(X_path, X)
        np.save(y_path, y)
        print(f"Saved {camera} arrays: X -> {X_path}, y -> {y_path}")


if __name__ == "__main__":
    preprocess_feature_pairs()
