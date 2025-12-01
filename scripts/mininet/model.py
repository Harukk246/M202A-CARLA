"""
Sequence modeling entry point for the Mininet dataset.

Loads paired feature tensors from `dataset/`, slices them into fixed-size
windows, performs a train/test split, and trains a bidirectional LSTM that
predicts the per-frame target for every timestep in a window.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, TensorDataset, random_split


WINDOW_SIZE = 16  # frames per sequence window
TEST_SPLIT = 0.2
BATCH_SIZE = 64
EPOCHS = 75
LEARNING_RATE = 3e-4
DATASET_DIR = Path(__file__).resolve().parent / "dataset"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RNG_SEED = 1337


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_feature_pairs(dataset_dir: Path) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Collect X/y numpy arrays for every camera that has a matching pair."""
    pairs: List[Tuple[np.ndarray, np.ndarray]] = []
    for x_path in sorted(dataset_dir.glob("camera_*_features_X.npy")):
        cam_prefix = x_path.name.replace("_features_X.npy", "")
        y_path = dataset_dir / f"{cam_prefix}_features_y.npy"
        if not y_path.exists():
            continue

        x = np.load(x_path)
        y = np.load(y_path)
        if y.ndim == 1:
            y = y[:, None]

        seq_len = min(len(x), len(y))
        if seq_len < WINDOW_SIZE:
            continue

        pairs.append((x[:seq_len], y[:seq_len]))

    if not pairs:
        raise FileNotFoundError(f"No usable feature pairs under {dataset_dir}")

    return pairs


def build_windows(
    series_pairs: Sequence[Tuple[np.ndarray, np.ndarray]],
    window_size: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Slice every sequence into overlapping windows with stride 1."""
    windows_x: List[np.ndarray] = []
    windows_y: List[np.ndarray] = []

    for x_np, y_np in series_pairs:
        seq_len = len(x_np)
        if seq_len < window_size:
            continue

        n_windows = seq_len - window_size + 1
        for start in range(n_windows):
            end = start + window_size
            windows_x.append(x_np[start:end])
            windows_y.append(y_np[start:end])

    X = torch.from_numpy(np.stack(windows_x)).float()
    y = torch.from_numpy(np.stack(windows_y)).float()
    return X, y


class BiLSTMRegressor(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            batch_first=True,
            bidirectional=True,
            num_layers=2,
            dropout=0.1,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_out, _ = self.lstm(x)
        return self.head(seq_out)


def split_dataset(dataset: Dataset, test_split: float) -> Tuple[Dataset, Dataset]:
    test_len = math.ceil(len(dataset) * test_split)
    train_len = len(dataset) - test_len
    return random_split(dataset, [train_len, test_len])


@dataclass
class Metrics:
    loss: float


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
) -> Metrics:
    train_mode = optimizer is not None
    model.train(mode=train_mode)

    total_loss = 0.0
    total_batches = 0

    for batch_x, batch_y in loader:
        batch_x = batch_x.to(DEVICE)
        batch_y = batch_y.to(DEVICE)

        preds = model(batch_x)
        loss = criterion(preds, batch_y)

        if train_mode:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        total_loss += loss.item()
        total_batches += 1

    mean_loss = total_loss / max(total_batches, 1)
    return Metrics(loss=mean_loss)


def main() -> None:
    set_seed(RNG_SEED)

    pairs = load_feature_pairs(DATASET_DIR)
    X, y = build_windows(pairs, WINDOW_SIZE)

    dataset = TensorDataset(X, y)
    train_ds, test_ds = split_dataset(dataset, TEST_SPLIT)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE)

    input_dim = X.shape[-1]
    output_dim = y.shape[-1]

    model = BiLSTMRegressor(input_dim=input_dim, hidden_dim=128, output_dim=output_dim).to(DEVICE)
    print("Model architecture:\n", model)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    for epoch in range(1, EPOCHS + 1):
        train_metrics = run_epoch(model, train_loader, criterion, optimizer)
        test_metrics = run_epoch(model, test_loader, criterion)
        print(
            f"Epoch {epoch:02d} "
            f"| train_loss={train_metrics.loss:.5f} "
            f"| test_loss={test_metrics.loss:.5f}"
        )

    print("Training complete.")

    model_path = DATASET_DIR / "bilstm_regressor.pt"
    torch.save(
        {
            "model_state": model.state_dict(),
            "input_dim": input_dim,
            "output_dim": output_dim,
            "window_size": WINDOW_SIZE,
        },
        model_path,
    )
    print(f"Saved model checkpoint to {model_path}")


if __name__ == "__main__":
    main()

