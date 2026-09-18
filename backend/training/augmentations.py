"""
VoiceShield AI — Telecom Codec & Noise Augmentation Pipeline
Stochastic augmentations simulating Indian telecom network conditions.

Augmentations (30-60% probability per batch):
    1. G.711 A-law/μ-law round-trip (PSTN 64 kbps)  [ITU-T G.711 corrected]
    2. AMR-NB (2G/3G) round-trip via ffmpeg
    3. AMR-WB (VoLTE HD voice) round-trip via ffmpeg
    4. Background noise injection (synthetic pink/brown noise)
    5. Random packet loss with linear interpolation (not zero-fill)
    6. Bandwidth truncation via Butterworth filter (300 Hz – 3.4 kHz)
"""

import os
import logging
import shutil
import tempfile
import subprocess
import numpy as np
from scipy.signal import butter, sosfilt

logger = logging.getLogger(__name__)

# ── ITU-T G.711 Constants ─────────────────────────────────────────────────
_ALAW_A = 87.6
_ALAW_LN_TERM = 1.0 + np.log(_ALAW_A)          # 1 + ln(87.6)  ≈ 5.473
_ALAW_THRESHOLD = 1.0 / _ALAW_LN_TERM           # segment boundary ≈ 0.1827


# ── G.711 A-law (ITU-T G.711 §3.2) ───────────────────────────────────────

def g711_alaw_roundtrip(audio: np.ndarray) -> np.ndarray:
    """
    Correct ITU-T G.711 A-law 8-bit companding round-trip.
    Fixes the expansion formula discontinuity that caused beeping artefacts.
    """
    A = _ALAW_A
    ln_term = _ALAW_LN_TERM          # 1 + ln(A)

    x = audio.astype(np.float32) / 32768.0
    abs_x = np.abs(x)
    sign_x = np.sign(x)

    # ── Compression ──────────────────────────────────────────────
    seg1 = abs_x < (1.0 / A)
    compressed = np.where(
        seg1,
        sign_x * (A * abs_x) / ln_term,
        sign_x * (1.0 + np.log(np.where(seg1, 1.0, A * abs_x))) / ln_term,
    )

    # 8-bit uniform quantisation in [-1, 1]
    quantized = np.round(compressed * 127.0) / 127.0
    abs_q = np.abs(quantized)
    sign_q = np.sign(quantized)

    # ── Expansion (corrected per ITU-T G.711 §3.2) ───────────────
    # Segment boundary in compressed domain
    boundary = 1.0 / ln_term
    seg1_q = abs_q < boundary
    decompressed = np.where(
        seg1_q,
        # Linear segment: y = x * ln_term / A
        sign_q * (abs_q * ln_term) / A,
        # Logarithmic segment: y = exp(x * ln_term - 1) / A
        # NOTE: "-1" not "-(1+ln(A))" — ITU-T specifies -1 here.
        sign_q * (np.exp(np.where(seg1_q, 0.0, abs_q * ln_term - 1.0)) + 1e-9) / A,
    )

    return np.clip(decompressed * 32768.0, -32768, 32767).astype(np.int16)


# ── G.711 μ-law (ITU-T G.711 §3.1) ──────────────────────────────────────

def g711_ulaw_roundtrip(audio: np.ndarray) -> np.ndarray:
    """Vectorized PSTN μ-law 8-bit companding (64 kbps)."""
    mu = 255.0
    x = audio.astype(np.float32) / 32768.0

    # Compression
    companded = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    # 8-bit quantisation
    quantized = np.round(companded * 127.0) / 127.0
    # Expansion
    decompanded = np.sign(quantized) * (1.0 / mu) * (np.expm1(np.abs(quantized) * np.log1p(mu)))
    return np.clip(decompanded * 32768.0, -32768, 32767).astype(np.int16)


# ── ffmpeg Codec Round-trip ───────────────────────────────────────────────

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _ffmpeg_codec_roundtrip(
    audio: np.ndarray, sr: int, codec: str, ext: str, codec_sr: int
) -> np.ndarray:
    """Generic ffmpeg codec round-trip. Falls back to passthrough if unavailable."""
    if not HAS_FFMPEG:
        return audio
    try:
        import scipy.io.wavfile as wav
        with tempfile.TemporaryDirectory() as tmpdir:
            in_wav  = os.path.join(tmpdir, "input.wav")
            out_cod = os.path.join(tmpdir, f"output.{ext}")
            out_wav = os.path.join(tmpdir, "output.wav")

            wav.write(in_wav, sr, audio)
            subprocess.run(
                ["ffmpeg", "-y", "-i", in_wav, "-ar", str(codec_sr),
                 "-ac", "1", "-c:a", codec, out_cod],
                check=True, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-i", out_cod, "-ar", str(sr), "-ac", "1", out_wav],
                check=True, capture_output=True, timeout=10,
            )
            _, decoded = wav.read(out_wav)
            return decoded.astype(np.int16)
    except Exception as e:
        logger.debug(f"Codec roundtrip ({codec}) failed: {e}")
        return audio


def amr_nb_roundtrip(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Simulate AMR-NB (2G/3G) codec round-trip."""
    return _ffmpeg_codec_roundtrip(audio, sr, "libopencore_amrnb", "amr", 8000)


def amr_wb_roundtrip(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Simulate AMR-WB (VoLTE HD voice, 50 Hz–7000 Hz) round-trip."""
    return _ffmpeg_codec_roundtrip(audio, sr, "libvo_amrwbenc", "awb", 16000)


# ── Butterworth PSTN Bandpass — rate-adaptive ─────────────────────────────

_PSTN_SOS_CACHE: dict[int, np.ndarray] = {}

def _get_pstn_sos(sr: int) -> np.ndarray:
    """
    Return a cached Butterworth bandpass SOS for the given sample rate.
    Pre-computing at fs=16000 only and applying to audio at a different rate
    was the primary cause of beeping in Hindi/Kannada samples.
    """
    if sr not in _PSTN_SOS_CACHE:
        # Clamp cutoffs to valid Nyquist range
        nyq = sr / 2.0
        low  = min(300.0,  nyq * 0.9)
        high = min(3400.0, nyq * 0.9)
        if low >= high:
            high = nyq * 0.9
            low  = min(300.0, high * 0.1)
        _PSTN_SOS_CACHE[sr] = butter(4, [low, high], btype="band", fs=sr, output="sos")
    return _PSTN_SOS_CACHE[sr]


def bandwidth_truncation(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Apply PSTN bandwidth Butterworth filter matched to actual sample rate."""
    try:
        sos = _get_pstn_sos(sr)
        filtered = sosfilt(sos, audio.astype(np.float32))
        return np.clip(filtered, -32768, 32767).astype(np.int16)
    except Exception:
        return audio


# ── Background Noise ──────────────────────────────────────────────────────

def add_background_noise(audio: np.ndarray, snr_db: float = 12.0) -> np.ndarray:
    """Add synthetic Gaussian noise at the specified SNR (dB)."""
    try:
        noise = np.random.randn(len(audio)).astype(np.float32)
        audio_f = audio.astype(np.float32)
        sig_p   = np.mean(audio_f ** 2) + 1e-10
        noise_p = np.mean(noise ** 2) + 1e-10
        scale   = np.sqrt(sig_p / (10 ** (snr_db / 10.0) * noise_p))
        return np.clip(audio_f + noise * scale, -32768, 32767).astype(np.int16)
    except Exception:
        return audio


# ── Packet Loss — linear interpolation (not zero-fill) ───────────────────

def packet_loss_simulation(
    audio: np.ndarray,
    loss_rate: float = 0.05,
    frame_ms: int = 20,
    sr: int = 16000,
) -> np.ndarray:
    """
    Simulate random packet loss with linear interpolation concealment.
    Previously used zero-fill which created hard on/off clicks (beeps).
    Now replaces lost frames with a linear ramp between the boundary samples.
    """
    try:
        frame_len = int(sr * frame_ms / 1000)
        num_frames = len(audio) // frame_len
        if num_frames == 0:
            return audio

        mask = np.random.rand(num_frames) < loss_rate
        if not np.any(mask):
            return audio

        res = audio.copy().astype(np.float32)
        for idx in np.where(mask)[0]:
            s = idx * frame_len
            e = (idx + 1) * frame_len
            # Use boundary samples for smooth linear interpolation
            v_start = res[s - 1] if s > 0 else 0.0
            v_end   = res[e]     if e < len(res) else 0.0
            res[s:e] = np.linspace(v_start, v_end, frame_len)

        return np.clip(res, -32768, 32767).astype(np.int16)
    except Exception:
        return audio


# ── Stochastic Augmentor ──────────────────────────────────────────────────

class StochasticAugmentor:
    """
    Stochastic batch augmentation pipeline.
    Each augmentation is applied independently with its own probability.

    Fixed in this version:
      - G.711 A-law expansion formula (ITU-T G.711 §3.2)
      - Butterworth filter is now sample-rate adaptive (no more beep on FLEURS audio)
      - Packet loss uses linear interpolation instead of zero-fill
    """

    def __init__(self, sr: int = 16000):
        self.sr = sr
        self.augmentations = [
            ("g711_alaw",    g711_alaw_roundtrip,    0.40),
            ("g711_ulaw",    g711_ulaw_roundtrip,    0.40),
            ("amr_nb",       self._amr_nb,            0.35),
            ("amr_wb",       self._amr_wb,            0.35),
            ("noise",        add_background_noise,    0.50),
            ("packet_loss",  self._packet_loss,       0.45),
            ("bandwidth",    self._bandwidth,         0.40),
        ]

    def _amr_nb(self, a):      return amr_nb_roundtrip(a, self.sr)
    def _amr_wb(self, a):      return amr_wb_roundtrip(a, self.sr)
    def _packet_loss(self, a): return packet_loss_simulation(a, sr=self.sr)
    def _bandwidth(self, a):   return bandwidth_truncation(a, sr=self.sr)

    def augment_sample(self, audio: np.ndarray) -> np.ndarray:
        """Apply random augmentation chain to a single audio sample."""
        for _name, fn, prob in self.augmentations:
            if np.random.rand() < prob:
                audio = fn(audio)
        return audio

    def augment_batch(self, batch: np.ndarray) -> np.ndarray:
        """Apply random augmentation chain to each sample in a batch."""
        return np.array([self.augment_sample(sample) for sample in batch])
