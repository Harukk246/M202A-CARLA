import numpy as np
from pathlib import Path
from typing import Dict


PCAP_FEATURES_PATH = "/home/ubuntu/M202A-CARLA/scripts/mininet/test_pcap_features/TEST_camera_25_features.npy"
OUTPUT_PATH = "/home/ubuntu/M202A-CARLA/scripts/mininet/test_pcap_features/TEST_camera_25_features_processed.npy"

def preprocess_feature() -> None:

    pcap = np.load(PCAP_FEATURES_PATH)

    X = pcap[:, (0,1,3)] # pkt count, total pkt size, pkt std dev
    print(f"X shape {X.shape}")

    # get rid of networking noise at the beginning
    X = X[500:]

    # Standardize X: zero mean and unit variance
    X = (X - X.mean(axis=0)) / X.std(axis=0)

    np.save(OUTPUT_PATH, X)
    print(f"Processed X -> {OUTPUT_PATH}")

if __name__ == "__main__":
    preprocess_feature()
