"""
Run inference with the trained BiLSTM regressor on a single feature file.

Loads the checkpoint produced by `model.py`, slides a WINDOW_SIZE context over
the provided PCAP feature sequence, and averages overlapping predictions so the
output aligns 1:1 with the original sequence length.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from model import BiLSTMRegressor, DEVICE, WINDOW_SIZE, DATASET_DIR

DEFAULT_MODEL_PATH = DATASET_DIR / "bilstm_regressor.pt"


def build_windows(sequence: np.ndarray, window_size: int) -> torch.Tensor:
    """Slice numpy array into overlapping windows (stride 1)."""
    seq_len = len(sequence)
    if seq_len < window_size:
        raise ValueError(
            f"Sequence length {seq_len} shorter than window size {window_size}."
        )

    windows = []
    for start in range(seq_len - window_size + 1):
        windows.append(sequence[start : start + window_size])

    stacked = np.stack(windows).astype(np.float32)
    return torch.from_numpy(stacked)


def overlap_average(preds: torch.Tensor, seq_len: int, window_size: int) -> np.ndarray:
    """Average overlapping window predictions back to the original sequence length."""
    output_dim = preds.shape[-1]
    sums = torch.zeros(seq_len, output_dim, device=preds.device)
    counts = torch.zeros(seq_len, 1, device=preds.device)

    for idx in range(preds.shape[0]):
        start = idx
        end = idx + window_size
        sums[start:end] += preds[idx]
        counts[start:end] += 1

    averaged = sums / counts
    return averaged.cpu().numpy()


def load_model(model_path: Path) -> tuple[BiLSTMRegressor, dict]:
    checkpoint = torch.load(model_path, map_location=DEVICE)
    input_dim = checkpoint["input_dim"]
    output_dim = checkpoint["output_dim"]
    window_size = checkpoint["window_size"]

    model = BiLSTMRegressor(
        input_dim=input_dim,
        hidden_dim=128,
        output_dim=output_dim,
    ).to(DEVICE)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, {
        "window_size": window_size,
        "input_dim": input_dim,
        "output_dim": output_dim,
    }


def run_inference(feature_path: Path, output_path: Path, model_path: Path) -> None:
    if not feature_path.exists():
        raise FileNotFoundError(f"Feature file not found: {feature_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    model, meta = load_model(model_path)
    window_size = meta["window_size"]

    features = np.load(feature_path)
    if features.ndim == 1:
        features = features[:, None]
    expected_in = meta["input_dim"]
    current_in = features.shape[1]
    if current_in > expected_in:
        print(
            f"Feature dimension {current_in} larger than model input {expected_in}. "
            "Truncating to fit the model."
        )
        features = features[:, :expected_in]
    elif current_in < expected_in:
        print(
            f"Feature dimension {current_in} smaller than model input {expected_in}. "
            "Zero padding the missing channels."
        )
        pad_width = expected_in - current_in
        features = np.pad(features, ((0, 0), (0, pad_width)), mode="constant")

    windows = build_windows(features, window_size).to(DEVICE)
    with torch.no_grad():
        preds = model(windows)

    averaged = overlap_average(preds, seq_len=len(features), window_size=window_size)
    averaged = np.clip(averaged, 0.0, 1.0)
    binary = np.rint(averaged)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(output_path, binary)
    print(f"Saved predictions to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BiLSTM inference on PCAP features.")
    parser.add_argument(
        "--feature-path",
        type=Path,
        required=True,
        help="Path to the .npy file containing PCAP features.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="Optional output path for the predicted y features (.txt). "
        "Defaults to <feature_path>_y_pred.txt",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to the trained model checkpoint (default: {DEFAULT_MODEL_PATH}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output_path
    if output_path is None:
        output_path = args.feature_path.with_name(
            args.feature_path.stem + "_y_pred.txt"
        )

    run_inference(args.feature_path, output_path, args.model_path)


if __name__ == "__main__":
    main()

