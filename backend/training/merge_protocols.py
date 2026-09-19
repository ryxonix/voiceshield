"""
VoiceShield AI — Multi-Language Protocol Merger (leak-free)

Merges per-language ASVspoof protocol files into a single train/val split.

IMPORTANT FIX (v2):
  The older version multiplied each line by a language weight and then
  split the *duplicated* list — so the SAME audio file could land in
  BOTH train and val (data leakage, meaningless EER). This version:

    1. de-duplicates by FILE ID first,
    2. splits unique files into train/val (sorted, stratified split),
    3. ONLY THEN oversamples the TRAIN lines by language weight.

  Result: a file can never appear in both splits.

Weighting:
    hindi   -> 3x  (dominant Indian telecom language)
    english -> 3x  (critical for cross-lingual robustness)
    kannada -> 2x  (South Indian telecom region)
"""

import os
import argparse
import random
import logging
from collections import OrderedDict

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _split_deterministic(names, seed, val_fraction):
    """Deterministic 85/15 split over a sorted unique-name list."""
    rng = random.Random(seed)
    ordered = sorted(names)
    rng.shuffle(ordered)
    cut = int(len(ordered) * (1.0 - val_fraction))
    return set(ordered[:cut]), set(ordered[cut:])


def merge_protocols(
    data_dir: str,
    languages: list,
    weights: dict,
    output_file: str,
    val_split: float = 0.15,
    seed: int = 42,
):
    """
    Merge multiple per-language protocol files into a single leak-free
    train/val split.

    A file id is ONLY ever in train or ONLY ever in val.
    """
    # dict: file_id -> line (first occurrence wins; ids are unique per protocol)
    unique = OrderedDict()
    per_lang = {}

    for lang in languages:
        proto_path = os.path.join(data_dir, f"{lang}_protocol.txt")
        if not os.path.exists(proto_path):
            logger.warning(f"Protocol file not found: {proto_path} — skipping")
            continue

        with open(proto_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        by_id = OrderedDict()
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                by_id.setdefault(parts[1], line)
        per_lang[lang] = by_id
        logger.info(f"  {lang:10s}: {len(lines)} protocol lines -> {len(by_id)} unique files")

    # ── Global deduped file-id universe ────────────────────────────────
    all_ids = []
    for by_id in per_lang.values():
        for fid, line in by_id.items():
            if fid not in unique:
                unique[fid] = line
                all_ids.append(fid)
    logger.info(f"Unique files across languages: {len(all_ids)}")

    if not all_ids:
        logger.error("No protocol files found — aborting.")
        return None, None

    # ── File-level split: no file appears in both splits ───────────────
    train_ids, val_ids = _split_deterministic(all_ids, seed, val_split)
    logger.info(f"Split at FILE level: {len(train_ids)} train / {len(val_ids)} val")

    # ── Build split sets per language + label summary ──────────────────
    def label_of(fid):
        return unique[fid].split()[-1] if unique[fid].split() else "unknown"

    def count(_ids):
        bon = sum(1 for i in _ids if label_of(i) == "bonafide")
        return len(_ids), bon, len(_ids) - bon

    n_tr, b_tr, s_tr = count(train_ids)
    n_va, b_va, s_va = count(val_ids)
    logger.info(
        f"  Train : {n_tr} (bonafide {b_tr}, spoof {s_tr}) | "
        f"Val: {n_va} (bonafide {b_va}, spoof {s_va})"
    )

    # ── Oversample TRAIN only by language weight (val stays pure) ──────
    weighted_train = []
    for lang, by_id in per_lang.items():
        mult = weights.get(lang, 1)
        ids = [fid for fid in train_ids if fid in by_id]
        weighted_train.extend(by_id[fid] for fid in ids * mult)
        logger.info(f"  {lang:10s}: {len(ids)} train files x {mult} = {len(ids) * mult} train lines")

    random.Random(seed).shuffle(weighted_train)

    val_lines = [unique[fid] for fid in sorted(val_ids)]

    train_out = output_file + "_train.txt"
    val_out = output_file + "_val.txt"
    with open(train_out, "w", encoding="utf-8") as f:
        f.write("\n".join(weighted_train))
    with open(val_out, "w", encoding="utf-8") as f:
        f.write("\n".join(val_lines))

    logger.info(f"\nLeak-free merged protocols written:")
    logger.info(f"  Train : {train_out} ({len(weighted_train)} lines, {len(train_ids)} unique files)")
    logger.info(f"  Val   : {val_out} ({len(val_lines)} lines, {len(val_ids)} unique files)")
    return train_out, val_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge per-language protocols (leak-free)")
    parser.add_argument("--data_dir", type=str, default="data/indic")
    parser.add_argument("--output", type=str, default="data/indic/merged")
    parser.add_argument("--val_split", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    languages = ["hindi", "english", "kannada"]
    weights = {"hindi": 3, "english": 3, "kannada": 2}

    logger.info("Language weighting (train-only oversampling):")
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