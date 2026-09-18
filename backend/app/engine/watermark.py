"""
VoiceShield AI — Enterprise Watermark Verifier
Detects enterprise-embedded pilot tones in the VoLTE-optimized 7.0–7.5 kHz band.
"""

import numpy as np
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class WatermarkResult:
    """Result of enterprise watermark verification."""
    detected: bool       # True if a valid pilot tone was found
    tone_freq: float     # Detected tone frequency in Hz (0.0 if not detected)
    snr_ratio: float     # Signal-to-noise ratio of the tone vs. noise floor

    def to_dict(self) -> dict:
        return asdict(self)


def check_watermark(
    window: np.ndarray,
    sr: int = 16000,
    fft_size: int = 4096,
    band_low: float = 7000.0,
    band_high: float = 7500.0,
    snr_threshold: float = 12.0,
) -> WatermarkResult:
    """
    Check for an enterprise watermark pilot tone in the audio window.

    Runs a 4096-point FFT and scans for a stable tone in the 7.0–7.5 kHz
    band that exceeds 12× the noise floor.

    Args:
        window: 1D numpy array of int16 PCM samples.
        sr: Sample rate in Hz.
        fft_size: FFT size (default 4096 for high frequency resolution).
        band_low: Lower bound of watermark band in Hz.
        band_high: Upper bound of watermark band in Hz.
        snr_threshold: Required SNR ratio for detection (default 12.0×).

    Returns:
        WatermarkResult with detection status, tone frequency, and SNR.
    """
    # Nyquist check: if sample rate is too low, we can't see 7.5 kHz
    nyquist = sr / 2.0
    if nyquist < band_high:
        return WatermarkResult(detected=False, tone_freq=0.0, snr_ratio=0.0)

    # Prepare window for FFT (zero-pad if needed)
    window_float = window.astype(np.float32) / 32768.0
    if len(window_float) < fft_size:
        padded = np.zeros(fft_size, dtype=np.float32)
        padded[:len(window_float)] = window_float
    else:
        padded = window_float[:fft_size]

    # Apply Hann window to reduce spectral leakage
    padded = padded * np.hanning(len(padded))

    # Compute FFT
    spectrum = np.fft.rfft(padded, n=fft_size)
    magnitudes = np.abs(spectrum)
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sr)

    # Identify bins in the watermark band
    band_mask = (freqs >= band_low) & (freqs <= band_high)

    if not np.any(band_mask):
        return WatermarkResult(detected=False, tone_freq=0.0, snr_ratio=0.0)

    # Noise floor: median magnitude across the full spectrum
    noise_floor = float(np.median(magnitudes))
    if noise_floor < 1e-10:
        noise_floor = 1e-10  # Prevent division by zero

    # Peak in the watermark band
    band_magnitudes = magnitudes[band_mask]
    max_band_mag = float(np.max(band_magnitudes))
    max_band_idx = np.argmax(band_magnitudes)
    tone_freq = float(freqs[band_mask][max_band_idx])

    # SNR ratio
    snr_ratio = max_band_mag / noise_floor
    detected = snr_ratio > snr_threshold

    if detected:
        logger.info(
            f"Enterprise watermark detected: {tone_freq:.1f} Hz, "
            f"SNR={snr_ratio:.1f}× (threshold={snr_threshold}×)"
        )

    return WatermarkResult(
        detected=detected,
        tone_freq=tone_freq if detected else 0.0,
        snr_ratio=float(snr_ratio),
    )
