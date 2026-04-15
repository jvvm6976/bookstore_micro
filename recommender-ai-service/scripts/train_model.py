"""
Demo model training script.
Generates synthetic behavior data and trains the BehaviorMLP.

Usage:
  python scripts/train_model.py

Output:
  artifacts/behavior_model.pt
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path

ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)
MODEL_PATH = ARTIFACTS_DIR / "behavior_model.pt"

FEATURE_DIM = 10
HIDDEN      = 32
N_SEGMENTS  = 5
N_SAMPLES   = 2000
EPOCHS      = 50
LR          = 1e-3

SEGMENTS = ["new", "casual", "engaged", "loyal", "champion"]


def generate_demo_data(n: int = N_SAMPLES):
    """
    Synthetic feature vectors with labels.
    Features: [views, searches, cart, purchases, ratings, avg_rating,
               unique_cats, avg_price, days_since, purchase_freq]
    All normalized to [0, 1].
    """
    np.random.seed(42)
    X = np.random.rand(n, FEATURE_DIM).astype(np.float32)

    # Engagement = weighted sum of activity features
    engagement = (
        X[:, 0] * 0.1 + X[:, 1] * 0.2 + X[:, 2] * 0.3 +
        X[:, 3] * 0.4 + X[:, 4] * 0.2 + X[:, 5] * 0.1
    )
    engagement = np.clip(engagement, 0, 1)

    # Propensity = purchase-heavy signal
    propensity = (X[:, 3] * 0.5 + X[:, 2] * 0.3 + X[:, 9] * 0.2)
    propensity = np.clip(propensity, 0, 1)

    # Segment based on purchases + engagement
    purchases = X[:, 3]
    segments = np.zeros(n, dtype=np.int64)
    segments[purchases > 0.8] = 4   # champion
    segments[(purchases > 0.5) & (purchases <= 0.8)] = 3   # loyal
    segments[(purchases > 0.2) & (purchases <= 0.5)] = 2   # engaged
    segments[(purchases > 0.05) & (purchases <= 0.2)] = 1  # casual
    # rest = 0 (new)

    return X, engagement.astype(np.float32), propensity.astype(np.float32), segments


class BehaviorMLP(nn.Module):
    def __init__(self, feature_dim=FEATURE_DIM, hidden=HIDDEN, n_segments=N_SEGMENTS):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(feature_dim, hidden), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
        )
        self.engagement_head = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.propensity_head = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.segment_head    = nn.Linear(hidden // 2, n_segments)

    def forward(self, x):
        h = self.shared(x)
        return self.engagement_head(h).squeeze(-1), self.propensity_head(h).squeeze(-1), self.segment_head(h)


def train():
    print("Generating synthetic training data...")
    X, eng_labels, prop_labels, seg_labels = generate_demo_data()

    X_t    = torch.tensor(X)
    eng_t  = torch.tensor(eng_labels)
    prop_t = torch.tensor(prop_labels)
    seg_t  = torch.tensor(seg_labels)

    model     = BehaviorMLP()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    mse_loss  = nn.MSELoss()
    ce_loss   = nn.CrossEntropyLoss()

    print(f"Training BehaviorMLP for {EPOCHS} epochs...")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        eng_pred, prop_pred, seg_logits = model(X_t)
        loss = (
            mse_loss(eng_pred, eng_t) +
            mse_loss(prop_pred, prop_t) +
            ce_loss(seg_logits, seg_t) * 0.5
        )
        loss.backward()
        optimizer.step()
        if epoch % 10 == 0:
            print(f"  Epoch {epoch:3d}/{EPOCHS} | loss={loss.item():.4f}")

    torch.save(model.state_dict(), str(MODEL_PATH))
    print(f"\nModel saved to {MODEL_PATH}")

    # Quick eval
    model.eval()
    with torch.no_grad():
        eng_p, prop_p, seg_l = model(X_t[:10])
        seg_pred = seg_l.argmax(dim=-1)
        print("\nSample predictions (first 10):")
        for i in range(10):
            print(
                f"  eng={eng_p[i]:.3f} prop={prop_p[i]:.3f} "
                f"seg={SEGMENTS[seg_pred[i]]} (true={SEGMENTS[seg_labels[i]]})"
            )


if __name__ == "__main__":
    train()
