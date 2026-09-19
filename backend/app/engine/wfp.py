"""
VoiceShield AI — Cloud XLS-R Spoof Detector (Wav2Vec2 For Sequence Classification)

Loads the XLS-R-300m impersonation detector trained in the cloud training
kit (`cloud/training` → notebook 03) and saved under
`backend/models/sih_cloud_xlsr/`. The checkpoint is a sequence-classification
head on top of the XLS-R-300m feature extractor with
id2label {0: bonafide, 1: spoof}; score = probability of class 1.

Thread-safety: inference is CPU-bound and stateless, guarded by a simple lock
so concurrent API calls never feed two streams into torch at the same time.
"""

import os
import time
import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "sih_cloud_xlsr")
)

TARGET_SR = 16000


class CloudXLSR:
    """Wraps the cloud-trained XLS-R-300m impersonation detector.

    Lazy, singleton, CPU-only. `from_pretrained` can take several seconds
    on first load (1.2 GB safetensors), so a singleton + an `is_ready` gate
    keeps streaming real-time while letting the file-analysis endpoint
    double-check each window with the trained model.
    """

    _instance: "CloudXLSR | None" = None
    _instance_lock = threading.Lock()

    def __init__(self, ckpt_dir: str = CHECKPOINT_DIR):
        self.ckpt_dir = ckpt_dir
        self.model = None
        self.processor = None
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CloudXLSR":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        """Load the model from the checkpoint dir. Idempotent."""
        if self.model is not None:
            return True
        if not os.path.isfile(os.path.join(self.ckpt_dir, "config.json")):
            logger.warning("Cloud XLS-R checkpoint not found: %s", self.ckpt_dir)
            return False
        try:
            import torch
            from transformers import (
                Wav2Vec2ForSequenceClassification,
                Wav2Vec2Processor,
            )
            t0 = time.time()
            model = Wav2Vec2ForSequenceClassification.from_pretrained(self.ckpt_dir)
            self.model = model
            self.model.eval()
            processor = Wav2Vec2Processor.from_pretrained(self.ckpt_dir)
            self.processor = processor
            logger.info(
                "Cloud XLS-R loaded in %.1fs",
                time.time() - t0,
            )
            return True
        except Exception as exc:
            logger.warning("Cloud XLS-R load failed: %s", exc)
            self.model = None
            return False

    def predict_spoof(self, audio: np.ndarray, sr: int | None = None) -> float:
        """Return P(class=spoof) ∈ [0, 1] for an audio array.

        `sr` is the audio's sample rate (defaults to 16 kHz — the model's
        target). Audio is resampled to 16 kHz, centre-trimmed/padded to ≤30 s
        (XLS-R supports up to 30 s), then run through the processor + model.
        """
        if self.model is None:
            return 0.5
        try:
            import torch
            import numpy as np

            win = np.asarray(audio, dtype=np.float32)
            if win.ndim > 1:
                win = win.mean(axis=1)
            src_rate = sr if sr is not None else TARGET_SR
            if src_rate != TARGET_SR:
                win = _resample(win, src_rate)
            win = win.astype(np.float32)
            # Centre-trim to ≤ TARGET_SR * 30
            max_samples = TARGET_SR * 30
            if len(win) > max_samples:
                start = (len(win) - max_samples) // 2
                win = win[start : start + max_samples]

            with self._lock, torch.no_grad():
                inputs = self.processor(
                    win, sampling_rate=TARGET_SR, return_tensors="pt"
                )
                logits = self.model(**inputs).logits
                prob_spoof = float(torch.softmax(logits, dim=-1)[0, 1].item())
            return float(np.clip(prob_spoof, 0.0, 1.0))
        except Exception as exc:
            logger.warning("Cloud XLS-R inference error: %s", exc)
            return 0.5


def _resample(audio: np.ndarray, src_sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    """Linear-interp resample (cheap, good enough for XLS-R input)."""
    if src_sr == target_sr:
        return audio
    n_out = int(round(len(audio) * target_sr / src_sr))
    x = np.linspace(0, len(audio) - 1, n_out)
    return np.interp(x, np.arange(len(audio)), audio).astype(np.float32)
