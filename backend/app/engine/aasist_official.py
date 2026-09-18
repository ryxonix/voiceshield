"""AASIST-L official pretrained model wrapper.

Loads the pretrained AASIST-L checkpoint from `clovaai/aasist` (MIT license)
cloned into `models/weights/aasist/AASIST-L.pth`. Accepts raw 16 kHz float32
waveforms of any length (center-pads / trims to 64600 samples internally).

Spoof probability ∈ [0, 1]:  0 = bona-fide,  1 = spoof.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch

logger = logging.getLogger(__name__)

_AASIST_WINDOW_SAMPLES = 64600          # official AASIST/L forward pass
_REPO_ROOT = Path(__file__).resolve().parents[2]   # backend/
_AASIST_REPO = _REPO_ROOT / "models" / "weights" / "aasist"
_AASIST_WEIGHTS = _REPO_ROOT / "models" / "aasist_l_official.pth" # fallback
_AASIST_WEIGHTS_ALT = _REPO_ROOT / "models" / "weights" / "aasist" / "AASIST-L.pth"
_AASIST_WEIGHTS_ALT2 = Path(r"F:\voiceshield\backend\hf_models\aasist\models\weights\AASIST-L.pth")

_instance: Optional["AASISTOfficial"] = None


class AASISTOfficial:
    """Singleton wrapper around the official AASIST-L pretrained checkpoint."""

    def __init__(self, weights_path: Path):
        self._weights_path = weights_path
        self._model = None
        self._ready = False
        self._load()

    # ── internal ───────────────────────────────────────────────────────
    def _load(self):
        if not self._weights_path.exists():
            logger.warning("AASIST-L weights not found at %s", self._weights_path)
            return
        try:
            # Add the cloned repo to sys.path so `models.AASIST` imports
            repo_dir = str(_REPO_ROOT / "hf_models" / "aasist")
            if repo_dir not in sys.path:
                sys.path.insert(0, repo_dir)

            from models.AASIST import Model as AASISTModel

            config = {
                "architecture": "AASIST",
                "nb_samp": _AASIST_WINDOW_SAMPLES,
                "first_conv": 128,
                "filts": [70, [1, 32], [32, 32], [32, 24], [24, 24]],
                "gat_dims": [24, 32],
                "pool_ratios": [0.4, 0.5, 0.7, 0.5],
                "temperatures": [2.0, 2.0, 100.0, 100.0],
            }

            self._model = AASISTModel(config)
            state_dict = torch.load(
                str(self._weights_path), map_location="cpu"
            )
            self._model.load_state_dict(state_dict)
            self._model.eval()

            self._ready = True
            logger.info(
                "AASIST-L official loaded (%s, %d params)",
                self._weights_path.name,
                sum(p.numel() for p in self._model.parameters()),
            )
        except Exception as exc:
            logger.warning("AASIST-L official load failed: %s", exc)

    # ── public API ─────────────────────────────────────────────────────
    @property
    def is_ready(self) -> bool:
        return self._ready

    def predict_spoof(self, audio: np.ndarray) -> float:
        """Return spoof probability for a raw 16 kHz float32 waveform.

        The waveform is resampled (if needed), center-padded / trimmed
        to exactly 64600 samples, then run through AASIST-L.
        """
        if not self._ready or self._model is None:
            return float("nan")

        samples = audio.astype(np.float32)

        # Pad / trim to official window length
        if len(samples) < _AASIST_WINDOW_SAMPLES:
            pad_total = _AASIST_WINDOW_SAMPLES - len(samples)
            pad_left = pad_total // 2
            pad_right = pad_total - pad_left
            samples = np.pad(samples, (pad_left, pad_right), mode="constant")
        elif len(samples) > _AASIST_WINDOW_SAMPLES:
            start = (len(samples) - _AASIST_WINDOW_SAMPLES) // 2
            samples = samples[start : start + _AASIST_WINDOW_SAMPLES]

        with torch.no_grad():
            t = torch.from_numpy(samples).unsqueeze(0)  # (1, 64600)
            _, logits = self._model(t)                    # logits (1, 2)
            probs = torch.softmax(logits, dim=1)          # [spoof, bona_fide]
            spoof_prob = probs[0, 0].item()

        return float(np.clip(spoof_prob, 0.0, 1.0))


def get_aasist_official() -> AASISTOfficial:
    """Return the singleton AASIST-L instance (lazy-init on first call)."""
    global _instance
    if _instance is None:
        # Search multiple candidate paths
        for candidate in [_AASIST_WEIGHTS_ALT2, _AASIST_WEIGHTS_ALT, _AASIST_WEIGHTS]:
            if candidate.exists():
                _instance = AASISTOfficial(candidate)
                return _instance
        logger.warning("AASIST-L official weights not found in any candidate path")
        _instance = AASISTOfficial(Path("models/aasist_l_official.pth"))  # will warn
    return _instance
