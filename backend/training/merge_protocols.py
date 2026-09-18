"""
VoiceShield AI — Multi-Language Protocol Merger
Merges per-language ASVspoof protocol files into a single weighted training set.

Weighting:
    hindi   -> 3x  (dominant Indian telecom language)
    english -> 3x  (critical for cross-lingual robustness)
    kannada -> 2x  (South Indian telecom region)
"""

import os
import argparse
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def merge_protocols(
    data_dir: str,
    languages: list,
    weights: dict,
    output_file: str,
    val_split: float = 0.15,
    seed: int = 42,
):
    """
    Merge multiple per-language protocol files into a single train/val split.

    Args:
        data_dir:    Root directory containing per-language wav files + protocols.
        languages:   List of language names (e.g. ['hindi', 'english', 'kannada']).
        weights:     Dict mapping language -> repeat multiplier.
        output_file: Base path for output (will produce _train.txt and _val.txt).
        val_split:   Fraction reserved for validation.
        seed:        RNG seed for reproducibility.
    """
    random.seed(seed)
    all_lines = []

    for lang in languages:
        proto_path = os.path.join(data_dir, f"{lang}_protocol.txt")
        if not os.path.exists(proto_path):
            logger.warning(f"Protocol file not found: {proto_path} — skipping")
            continue

        with open(proto_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        multiplier = weights.get(lang, 1)
        weighted = lines * multiplier
        random.shuffle(weighted)
        all_lines.extend(weighted)
        logger.info(f"  {lang:10s}: {len(lines)} samples × {multiplier}x = {len(weighted)} entries")

    random.shuffle(all_lines)

    split_idx = int(len(all_lines) * (1 - val_split))
    train_lines = all_lines[:split_idx]
    val_lines   = all_lines[split_idx:]

    train_out = output_file + "_train.txt"
    val_out   = output_file + "_val.txt"

    with open(train_out, "w") as f:
        f.write("\n".join(train_lines))
    with open(val_out, "w") as f:
        f.write("\n".join(val_lines))

    bonafide_train = sum(1 for l in train_lines if "bonafide" in l)
    bonafide_val   = sum(1 for l in val_lines   if "bonafide" in l)

    logger.info(f"\nMerged protocol written:")
    logger.info(f"  Train : {len(train_lines)} samples ({bonafide_train} bonafide, {len(train_lines)-bonafide_train} spoof)")
    logger.info(f"  Val   : {len(val_lines)}   samples ({bonafide_val} bonafide, {len(val_lines)-bonafide_val} spoof)")
    logger.info(f"  Files : {train_out}")
    logger.info(f"          {val_out}")

    return train_out, val_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge per-language protocols")
    parser.add_argument("--data_dir",  type=str, default="data/indic")
    parser.add_argument("--output",    type=str, default="data/indic/merged")
    parser.add_argument("--val_split", type=float, default=0.15)
    parser.add_argument("--seed",      type=int,   default=42)
    args = parser.parse_args()

    languages = ["hindi", "english", "kannada"]
    weights   = {"hindi": 3, "english": 3, "kannada": 2}

    logger.info("Language weighting:")
    for lang in languages:
        logger.info(f"  {lang:10s}: {weights[lang]}x")

    merge_protocols(
        data_dir=args.data_dir,
        languages=languages,
        weights=weights,
        output_file=args.output,
        val_split=args.val_split,
        seed=args.seed,
    )
