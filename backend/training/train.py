"""
VoiceShield AI — Training Loop
Trains AASIST-L with telecom augmentations, weighted BCE loss, and EER-based checkpointing.
"""

import os
import sys
import argparse
import logging
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def train_aasist(config: dict) -> None:
    """
    Full training loop for AASIST-L.

    Args:
        config: Dict with keys:
            train_dir, train_protocol, val_dir, val_protocol,
            save_dir, epochs, pos_weight
    """
    from app.models.aasist import create_aasist_l, get_param_count
    from training.dataset import create_dataloaders
    from training.augmentations import StochasticAugmentor
    from training.evaluate import compute_eer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    # Create model
    model = create_aasist_l().to(device)
    
    if config.get("pretrained_weights"):
        pretrained_path = config["pretrained_weights"]
        logger.info(f"Loading pretrained weights from {pretrained_path} for fine-tuning")
        model.load_state_dict(torch.load(pretrained_path, map_location=device))
        
    param_count = get_param_count(model)
    logger.info(f"AASIST-L parameters: {param_count:,}")

    # Optimizer & scheduler
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-5)
    scheduler = CosineAnnealingLR(optimizer, T_max=config.get("epochs", 100))

    # ── Weighted BCE for class imbalance ────────────────────────────────
    # pos_weight is auto-computed from the actual train-set ratio when the
    # caller does not force one. (Old default 9.0 assumed ASVspoof's 9:1
    # spoof:bonafide skew, which no longer matches the leak-free dataset.)
    if config.get("pos_weight") is not None:
        pos_weight_val = float(config["pos_weight"])
    else:
        from training.dataset import ASVspoofDataset
        probe = ASVspoofDataset(config["train_dir"], config["train_protocol"])
        n_s = max(1, sum(1 for _, l, _sr in probe.cache if l == 1))
        n_b = max(1, sum(1 for _, l, _sr in probe.cache if l == 0))
        pos_weight_val = n_b / n_s
        logger.info(f"Auto pos_weight from train split: {n_b} bonafide / {n_s} spoof = {pos_weight_val:.3f}")
    pos_weight = torch.tensor([pos_weight_val]).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # Data loaders
    config["augmentor"] = StochasticAugmentor()
    train_loader, val_loader = create_dataloaders(config)
    logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

    # Training state
    best_eer = float("inf")
    patience_counter = 0
    patience = config.get("patience", 10)
    save_dir = config.get("save_dir", "checkpoints")
    os.makedirs(save_dir, exist_ok=True)

    for epoch in range(config.get("epochs", 100)):
        # ── Train ──────────────────────────────────────────────────
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(device), target.to(device)

            optimizer.zero_grad()
            output = model(data).squeeze(-1)  # [B]
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            preds = (torch.sigmoid(output) > 0.5).float()
            correct += (preds == target).sum().item()
            total += target.size(0)

            if (batch_idx + 1) % 25 == 0 or (batch_idx + 1) == len(train_loader):
                logger.info(f"Epoch {epoch + 1:02d} | Batch {batch_idx + 1:03d}/{len(train_loader):03d} | Loss: {loss.item():.4f}")

        train_loss = total_loss / max(len(train_loader), 1)
        train_acc = correct / max(total, 1) * 100

        # ── Validate ───────────────────────────────────────────────
        model.eval()
        val_scores = []
        val_labels = []

        with torch.no_grad():
            for data, target in val_loader:
                data = data.to(device)
                output = model(data).squeeze(-1)
                val_scores.extend(torch.sigmoid(output).cpu().numpy())
                val_labels.extend(target.numpy())

        scores_arr = np.array(val_scores)
        labels_arr = np.array(val_labels)
        eer = compute_eer(scores_arr, labels_arr)

        log_str = (
            f"Epoch {epoch + 1:03d}/{config.get('epochs', 30):03d} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Train Acc: {train_acc:.1f}% | "
            f"Val EER: {eer:.4f}"
        )
        logger.info(log_str)
        log_file = os.path.join(save_dir, "training_log.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_str + "\n")
            f.flush()
            os.fsync(f.fileno())

        # ── Checkpointing ─────────────────────────────────────────
        if eer < best_eer:
            best_eer = eer
            patience_counter = 0
            ckpt_path = os.path.join(save_dir, "best_model.pth")
            torch.save(model.state_dict(), ckpt_path)
            best_msg = f"  ✓ Best model saved (EER={eer:.4f}) → {ckpt_path}"
            logger.info(best_msg)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(best_msg + "\n")
                f.flush()
                os.fsync(f.fileno())
        else:
            patience_counter += 1
            if patience_counter >= patience:
                stop_msg = f"Early stopping at epoch {epoch + 1} (patience={patience})"
                logger.info(stop_msg)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(stop_msg + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                break

        scheduler.step()

    logger.info(f"Training complete. Best EER: {best_eer:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AASIST-L")
    parser.add_argument("--train_dir", type=str, required=True)
    parser.add_argument("--train_protocol", type=str, required=True)
    parser.add_argument("--val_dir", type=str, required=True)
    parser.add_argument("--val_protocol", type=str, required=True)
    parser.add_argument("--save_dir", type=str, default="checkpoints")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--pos_weight", type=float, default=None,
                        help="Optional custom BCE positive-class weight (default: auto from data)")
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--pretrained_weights", type=str, default=None, help="Path to pretrained PyTorch model (.pth) to fine-tune")
    args = parser.parse_args()

    train_aasist(vars(args))
