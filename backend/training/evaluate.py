"""
VoiceShield AI — Evaluation Metrics
Computes EER, min t-DCF, and generates evaluation reports.
"""

import os
import sys
import json
import argparse
import logging

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def compute_eer(scores: np.ndarray, labels: np.ndarray) -> float:
    """
    Compute Equal Error Rate (EER).
    Finds the operating threshold where False Positive Rate (FPR) equals False Negative Rate (FNR).
    """
    from sklearn.metrics import roc_curve

    if len(scores) == 0 or len(labels) == 0:
        return 0.5

    fpr, tpr, thresholds = roc_curve(labels, scores, pos_label=1)
    fnr = 1.0 - tpr

    # Find point where FPR and FNR are closest
    idx = np.nanargmin(np.abs(fpr - fnr))
    eer = float((fpr[idx] + fnr[idx]) / 2.0)
    return max(0.0, min(1.0, eer))


def compute_min_tdcf(
    scores: np.ndarray,
    labels: np.ndarray,
    Pspoof: float = 0.05,
    Cmiss: float = 1.0,
    Cfa: float = 10.0,
) -> float:
    """
    Compute minimum tandem Detection Cost Function (t-DCF).

    Args:
        scores: Model output scores.
        labels: Ground truth labels.
        Pspoof: Prior probability of spoof attack.
        Cmiss: Cost of miss (false negative).
        Cfa: Cost of false alarm (false positive).

    Returns:
        Minimum t-DCF value.
    """
    from sklearn.metrics import roc_curve

    if len(scores) == 0 or len(labels) == 0:
        return 1.0

    Ptar = 1.0 - Pspoof
    fpr, tpr, thresholds = roc_curve(labels, scores, pos_label=1)
    fnr = 1 - tpr

    # Normalized t-DCF
    tdcf = Cmiss * fnr * Ptar + Cfa * fpr * Pspoof
    min_tdcf = float(np.min(tdcf))

    return min_tdcf


def evaluate_model(model_path: str, test_loader=None) -> dict:
    """
    Full model evaluation.

    Args:
        model_path: Path to ONNX or PyTorch model.
        test_loader: Optional test dataloader. If None, generates mock data.

    Returns:
        Dict with EER, min t-DCF, and sample count.
    """
    import torch

    all_scores = []
    all_labels = []

    if test_loader is not None:
        # Load model
        if model_path.endswith(".onnx"):
            import onnxruntime as ort
            session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            input_name = session.get_inputs()[0].name

            for data, target in test_loader:
                output = session.run(None, {input_name: data.numpy()})[0]
                all_scores.extend(output.flatten())
                all_labels.extend(target.numpy())
        else:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.models.aasist import create_aasist_l

            model = create_aasist_l()
            model.load_state_dict(torch.load(model_path, map_location="cpu"))
            model.eval()

            with torch.no_grad():
                for data, target in test_loader:
                    output = model(data).squeeze(-1)
                    all_scores.extend(torch.sigmoid(output).numpy())
                    all_labels.extend(target.numpy())
    else:
        logger.warning("No test loader provided — using mock evaluation data")
        np.random.seed(42)
        all_scores = np.random.rand(200).tolist()
        all_labels = np.random.randint(0, 2, 200).tolist()

    scores = np.array(all_scores)
    labels = np.array(all_labels)

    eer = compute_eer(scores, labels)
    min_tdcf = compute_min_tdcf(scores, labels)

    report = {
        "EER": round(eer, 6),
        "min_tDCF": round(min_tdcf, 6),
        "num_samples": len(scores),
        "num_bonafide": int(np.sum(labels == 0)),
        "num_spoof": int(np.sum(labels == 1)),
    }

    logger.info(f"Evaluation Results:")
    for key, val in report.items():
        logger.info(f"  {key}: {val}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate AASIST-L")
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--test_dir", type=str, default=None)
    parser.add_argument("--test_protocol", type=str, default=None)
    args = parser.parse_args()

    test_loader = None
    if args.test_dir and args.test_protocol:
        from training.dataset import ASVspoofDataset
        from torch.utils.data import DataLoader

        test_ds = ASVspoofDataset(args.test_dir, args.test_protocol)
        test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)

    report = evaluate_model(args.model_path, test_loader)
    print(json.dumps(report, indent=2))
