"""
VoiceShield AI — Dhwani ONNX Inference Engine
Wraps the ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model
(Wav2Vec2 XLS-R + AASIST backend, trained on Indian languages).

Supported languages: Hindi, English, Tamil, Telugu, Malayalam
Also generalizes well to Kannada (detects synthesis artifacts, not language-specific).

Usage:
    detector = DhwaniDetector()
    result = detector.predict_file("audio.wav")
    result = detector.predict_array(audio_np, sr=16000)
"""

import os
import logging
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "dhwani", "best_model.onnx"
)
MODEL_PATH = os.path.normpath(MODEL_PATH)

TARGET_SR   = 16000
MAX_SAMPLES = 48000   # 3-second window as required by Dhwani


def _resample(audio: np.ndarray, src_sr: int) -> np.ndarray:
    if src_sr == TARGET_SR:
        return audio.astype(np.float32)
    g = gcd(src_sr, TARGET_SR)
    return resample_poly(audio, TARGET_SR // g, src_sr // g).astype(np.float32)


def _pad_or_trim(audio: np.ndarray) -> np.ndarray:
    """Pad short clips or trim long clips to exactly MAX_SAMPLES."""
    if len(audio) > MAX_SAMPLES:
        # Centre-crop
        start = (len(audio) - MAX_SAMPLES) // 2
        return audio[start : start + MAX_SAMPLES]
    elif len(audio) < MAX_SAMPLES:
        return np.pad(audio, (0, MAX_SAMPLES - len(audio)))
    return audio


class DhwaniDetector:
    """
    Ready-to-use Indian voice deepfake detector backed by the Dhwani ONNX model.
    Thread-safe: onnxruntime sessions are safe for concurrent inference.
    """

    def __init__(self, model_path: str = MODEL_PATH):
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 4
            self.session = ort.InferenceSession(
                model_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.input_name  = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            logger.info(f"Dhwani ONNX model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load Dhwani model: {e}")
            self.session = None

    @property
    def is_ready(self) -> bool:
        return self.session is not None

    def _preprocess(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Resample → mono → normalise → pad/trim to 3 s window."""
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = _resample(audio, sr)
        # Normalise to [-1, 1]
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak
        audio = _pad_or_trim(audio)
        return audio.reshape(1, -1).astype(np.float32)   # [1, T]

    def predict_array(self, audio: np.ndarray, sr: int = 16000) -> dict:
        """
        Run inference on a numpy audio array.

        Returns:
            {
                "label":           "bonafide" | "spoof",
                "synthetic_score": float [0, 1],   # higher = more likely spoof
                "confidence":      float [0, 1],
                "model":           "dhwani-onnx",
            }
        """
        if not self.is_ready:
            return {"error": "Model not loaded", "label": "unknown", "synthetic_score": 0.5}

        try:
            x = self._preprocess(audio, sr)
            outputs = self.session.run([self.output_name], {self.input_name: x})
            logit = float(outputs[0].flatten()[0])

            # Dhwani outputs a single logit: positive = spoof, negative = bonafide
            import math
            prob_spoof = 1.0 / (1.0 + math.exp(-logit))   # sigmoid

            label = "spoof" if prob_spoof > 0.5 else "bonafide"
            confidence = prob_spoof if label == "spoof" else 1.0 - prob_spoof

            return {
                "label":           label,
                "synthetic_score": round(prob_spoof, 4),
                "confidence":      round(confidence, 4),
                "model":           "dhwani-onnx",
            }
        except Exception as e:
            logger.error(f"Dhwani inference error: {e}")
            return {"error": str(e), "label": "unknown", "synthetic_score": 0.5}

    def predict_file(self, path: str) -> dict:
        """Run inference on a WAV/FLAC/MP3 file."""
        try:
            audio, sr = sf.read(path, dtype="float32")
            return self.predict_array(audio, sr)
        except Exception as e:
            logger.error(f"Failed to read audio file {path}: {e}")
            return {"error": str(e), "label": "unknown", "synthetic_score": 0.5}

    def predict_batch(self, audio_list: list, sr: int = 16000) -> list:
        """Run inference on a list of audio arrays."""
        return [self.predict_array(a, sr) for a in audio_list]


# ── Singleton ─────────────────────────────────────────────────────────────

_detector: DhwaniDetector | None = None


def get_detector() -> DhwaniDetector:
    """Return the singleton DhwaniDetector, loading on first call."""
    global _detector
    if _detector is None:
        _detector = DhwaniDetector()
    return _detector
