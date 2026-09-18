"""
VoiceShield AI — Prosodic Feature Extraction (XAI Layer)
Extracts Jitter, Shimmer, Phase Continuity, and Pitch Stability from audio windows.
These features provide explainability for deepfake detection decisions.
"""

import numpy as np
import librosa
from dataclasses import dataclass, asdict
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProsodicsResult:
    """Prosodic feature extraction result for a single audio window."""
    jitter_pct: float         # Pitch jitter (cycle-to-cycle period instability) in %
    shimmer_pct: float        # Amplitude instability across glottal cycles in %
    phase_continuity: float   # Spectral phase continuity ∈ [0, 1]
    pitch_stability_pct: float  # Derived pitch stability ∈ [0, 100]

    def to_dict(self) -> dict:
        return asdict(self)


def extract_prosodics(window: np.ndarray, sr: int = 16000) -> ProsodicsResult:
    """
    Extract prosodic features from a 300ms audio window.

    Args:
        window: 1D numpy array of int16 PCM samples (typically 4800 samples).
        sr: Sample rate in Hz (default 16000).

    Returns:
        ProsodicsResult with jitter, shimmer, phase continuity, and pitch stability.
    """
    t_start = time.perf_counter()

    # Normalize int16 to float32 [-1, 1]
    window_float = window.astype(np.float32) / 32768.0

    # ── 1. Pitch Jitter (%) ────────────────────────────────────────────
    jitter_pct = _compute_jitter(window_float, sr)

    # ── 2. Shimmer (%) ─────────────────────────────────────────────────
    shimmer_pct = _compute_shimmer(window_float)

    # ── 3. Spectral Phase Continuity ───────────────────────────────────
    phase_continuity = _compute_phase_continuity(window_float, sr)

    # ── 4. Pitch Stability (%) ─────────────────────────────────────────
    pitch_stability_pct = max(0.0, 100.0 - min(jitter_pct * 40.0, 100.0))

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    logger.debug(f"Feature extraction: {elapsed_ms:.1f}ms")

    return ProsodicsResult(
        jitter_pct=float(jitter_pct),
        shimmer_pct=float(shimmer_pct),
        phase_continuity=float(phase_continuity),
        pitch_stability_pct=float(pitch_stability_pct),
    )


def _compute_jitter(window_float: np.ndarray, sr: int) -> float:
    """
    Compute pitch jitter using YIN-based f0 tracking.

    Jitter_local = [1/(N-1) × Σ|T_i - T_{i+1}|] / [1/N × ΣT_i] × 100%
    """
    try:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            window_float, fmin=50, fmax=500, sr=sr,
            frame_length=1024, hop_length=256
        )

        # Extract voiced frames with valid f0
        valid_mask = voiced_flag & ~np.isnan(f0)
        voiced_f0 = f0[valid_mask]

        if len(voiced_f0) < 2:
            return 0.5  # Default for insufficient voiced frames

        periods = 1.0 / voiced_f0  # T_i in seconds
        mean_period = np.mean(periods)

        if mean_period <= 0:
            return 0.5

        period_diffs = np.abs(np.diff(periods))
        jitter = (np.mean(period_diffs) / mean_period) * 100.0

        return float(np.clip(jitter, 0.0, 50.0))

    except Exception as e:
        logger.debug(f"Jitter computation failed: {e}")
        return 0.5


def _compute_shimmer(window_float: np.ndarray) -> float:
    """
    Compute amplitude shimmer across glottal cycles.

    Shimmer_local = [1/(N-1) × Σ|A_i - A_{i+1}|] / [1/N × ΣA_i] × 100%
    """
    try:
        # Segment into half-cycles using zero crossings
        zero_crossings = np.where(np.diff(np.signbit(window_float)))[0]

        if len(zero_crossings) < 3:
            return 1.5  # Default for insufficient cycles

        # Get peak amplitude of each half-cycle
        peaks = []
        for i in range(len(zero_crossings) - 1):
            start = zero_crossings[i]
            end = zero_crossings[i + 1]
            if end > start:
                segment_peak = np.max(np.abs(window_float[start:end]))
                if segment_peak > 1e-6:  # Skip near-silent segments
                    peaks.append(segment_peak)

        if len(peaks) < 2:
            return 1.5

        peaks = np.array(peaks)
        mean_peak = np.mean(peaks)

        if mean_peak <= 0:
            return 1.5

        amplitude_diffs = np.abs(np.diff(peaks))
        shimmer = (np.mean(amplitude_diffs) / mean_peak) * 100.0

        return float(np.clip(shimmer, 0.0, 50.0))

    except Exception as e:
        logger.debug(f"Shimmer computation failed: {e}")
        return 1.5


def _compute_phase_continuity(window_float: np.ndarray, sr: int) -> float:
    """
    Compute spectral phase continuity across adjacent STFT frames.

    φ_cont = 1 - (1/K) × Σ[|∠X_t[k] - ∠X_{t-1}[k] - Δφ_expected[k]| / π]
    """
    try:
        n_fft = 512
        hop_length = 128

        # Compute STFT
        D = librosa.stft(window_float, n_fft=n_fft, hop_length=hop_length)

        if D.shape[1] < 2:
            return 0.5  # Need at least 2 frames

        # Phase angles
        phase = np.angle(D)

        # Expected phase advance per frequency bin
        # Δφ_expected[k] = 2π × k × hop_length / n_fft
        k = np.arange(D.shape[0])
        expected_advance = (2 * np.pi * k * hop_length / n_fft).reshape(-1, 1)

        # Actual phase difference between consecutive frames
        phase_diff = np.diff(phase, axis=1)

        # Phase deviation (wrapped to [-π, π])
        deviation = phase_diff - expected_advance
        # Wrap to [-π, π]
        deviation = np.abs(np.mod(deviation + np.pi, 2 * np.pi) - np.pi)
        normalized_dev = deviation / np.pi

        # Phase continuity
        phase_continuity = 1.0 - float(np.mean(normalized_dev))

        return float(np.clip(phase_continuity, 0.0, 1.0))

    except Exception as e:
        logger.debug(f"Phase continuity computation failed: {e}")
        return 0.5


def noise_floor_dropouts_count(window: np.ndarray, sr: int = 16000, hop: int = 200) -> int:
    """
    Count short drop-out frames in a window: energy frames more than 35 dB
    below the window peak (typical of concatenated/garbled synthetic audio).

    Args:
        window: 1D numpy array of int16 PCM samples.
        sr: Sample rate in Hz (used only for frame sizing).
        hop: Frame length in samples (default 200 = 12.5 ms @ 16 kHz).

    Returns:
        Integer count of drop-out frames.
    """
    win = window.astype(np.float32) / 32768.0
    if win.size < 2 * hop or hop < 100:
        return 0
    frame_count = win.size // hop
    frames = win[: frame_count * hop].reshape(frame_count, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    peak = float(rms.max()) if rms.size else 1e-6
    if peak < 1e-7:
        return int(rms.size)
    db = 20.0 * np.log10((rms / peak) + 1e-9)
    return int(np.sum(db < -35.0))
