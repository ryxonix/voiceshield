"""
VoiceShield AI — Shared Per-Window Analysis Pipeline

Used by both the streaming WebSocket endpoint and the file-analysis
(/api/analyze) endpoint so their scoring is identical.

Emits an event dict shaped for the dashboard's AnalysisEvent type.
"""

import time

import numpy as np

from app.config import settings
from app.engine.features import extract_prosodics, noise_floor_dropouts_count
from app.engine.watermark import check_watermark
from app.engine.fusion import compute_risk
from app.engine.risk import risk_band, verdict_for, recommendation
from app.models.inference import AASISTInference


def _window_rms(window: np.ndarray) -> float:
    """RMS of an int16 window, normalized to [0, 1]."""
    f = window.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(f ** 2) + 1e-12))


def _speech_fraction(window: np.ndarray) -> float:
    """Share of 100 ms frames whose RMS exceeds the speech floor.

    A window may pass the whole-window RMS check yet be almost entirely
    silence with only a short utterance (e.g. a quick "hello"). Both trained
    models are out-of-distribution on such mostly-silent clips and score them
    as SYNTHETIC. Requiring a minimum amount of actual speech keeps those
    false positives away while demodulating real speech windows normally.
    """
    frame_samples = int(settings.sample_rate * 0.1)  # 100 ms
    f = window.astype(np.float32) / 32768.0
    n_frames = max(len(f) // frame_samples, 1)
    frames = f[: n_frames * frame_samples].reshape(n_frames, frame_samples)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    return float(np.mean(rms > settings.silence_rms_threshold))


def _is_silent(window: np.ndarray) -> bool:
    """True when a window has no meaningful speech energy.

    Two gates: overall window RMS, and the fraction of 100 ms frames that
    contain actual speech. Dhwani is trained on 3-second clips of continuous
    speech; silence and mic-idle noise are out-of-distribution inputs that the
    model scores as SYNTHETIC. Gate those windows here so silence or a brief
    utterance never reads as a deepfake.
    """
    if _window_rms(window) < settings.silence_rms_threshold:
        return True
    if _speech_fraction(window) < settings.min_speech_fraction:
        return True
    return False


def _model_probability(window: np.ndarray, *, include_xlsr: bool = False) -> float:
    """Run the best available trained models and ensemble their outputs.

    - If Dhwani AND the official pretrained AASIST-L are both loaded,
      returns the average of the two spoof probabilities (ensemble).
    - If only one is available, uses it alone.
    - Legacy local AASIST-L is a last resort (untrained).

    `include_xlsr` gates the heavy cloud-trained XLS-R-300m detector, which
    takes seconds per window on CPU — reserved for the file-analysis path so
    real-time streaming stays within the ~78 ms per-window latency budget.
    """
    if _is_silent(window):
        return 0.0

    log = __import__("logging").getLogger(__name__)
    win_f32 = (window.astype(np.float32) / 32768.0).copy()
    dhwani_prob: float | None = None
    aasist_official_prob: float | None = None
    cloud_xlsr_prob: float | None = None

    # ── Dhwani ─────────────────────────────────────────────────────────
    try:
        from app.engine.dhwani import get_detector
        det = get_detector()
        if det.is_ready:
            result = det.predict_array(win_f32)
            prob = result.get("synthetic_score")
            if prob is not None:
                dhwani_prob = float(np.clip(prob, 0.0, 1.0))
    except Exception as exc:
        log.warning("Dhwani unavailable: %s", exc)

    # ── AASIST-L official (pretrained, MIT license) ────────────────────
    try:
        from app.engine.aasist_official import get_aasist_official
        ao = get_aasist_official()
        if ao.is_ready:
            aasist_official_prob = float(ao.predict_spoof(win_f32))
    except Exception as exc:
        log.warning("AASIST-L official unavailable: %s", exc)

    # ── Cloud XLS-R (trained Wav2Vec2 sequence classification) ─────────
    # Optional: only for /api/analyze. load() is idempotent and lazily
    # pulls in the 1.2 GB checkpoint on first file analysis.
    if include_xlsr:
        try:
            from app.engine.wfp import CloudXLSR
            detector = CloudXLSR.get_instance()
            if detector.is_ready or detector.load():
                cloud_xlsr_prob = float(detector.predict_spoof(
                    win_f32, sr=settings.sample_rate))
        except Exception as exc:
            log.warning("Cloud XLS-R unavailable: %s", exc)

    # ── Ensemble ───────────────────────────────────────────────────────
    # Average of every *trained* model that actually loaded. The cloud
    # XLS-R (sih_cloud_xlsr) is the trained 300m box; Dhwani and AASIST-L
    # official are the two MIT-licensed pretrained boxes. Any subset that
    # is ready participates (we never degrade to untrained legacy).
    boxes = [p for p in (dhwani_prob, aasist_official_prob, cloud_xlsr_prob) if p is not None]
    if boxes:
        return float(np.clip(sum(boxes) / len(boxes), 0.0, 1.0))
    log.warning("No trained models available — falling back to legacy untrained AASIST-L")
    return float(AASISTInference.get_instance().predict(window))


def analyze_window(
    window: np.ndarray,
    *,
    role: str = "adult",
    speaker_mismatch: bool | None = None,
    include_xlsr: bool = False,
) -> dict:
    """
    Run the full per-window detection pipeline on an int16 PCM window.

    Returns an analysis event dict (without stream/timestamp fields):
        synthetic_score, model_prob, xai_risk, verdict, risk_band,
        recommendation, speaker_mismatch, watermark_hit,
        prosody{jitter_pct, shimmer_pct, phase_continuity,
                pitch_stability, noise_floor_dropouts, watermark_snr},
        latency_ms

    `include_xlsr` enables the heavy cloud-trained XLS-R-300m detector
    (seconds/window) — use it only for the file-analysis path, never for
    real-time streaming.
    """
    prosodics = extract_prosodics(window, sr=settings.sample_rate)

    t0 = time.perf_counter()
    model_prob = _model_probability(window, include_xlsr=include_xlsr)
    latency_ms = (time.perf_counter() - t0) * 1000

    watermark = check_watermark(
        window,
        sr=settings.sample_rate,
        fft_size=settings.watermark_fft_size,
        band_low=settings.watermark_band_low,
        band_high=settings.watermark_band_high,
        snr_threshold=settings.watermark_snr_threshold,
    )

    fusion = compute_risk(
        model_prob=model_prob,
        prosodics=prosodics,
        watermark=watermark,
        model_weight=settings.fusion_model_weight,
        xai_weight=settings.fusion_xai_weight,
    )

    score = fusion.synthetic_score
    mismatched = speaker_mismatch is True
    if mismatched:
        score = float(np.clip(score + 0.15, 0.0, 1.0))

    band = risk_band(score, role)
    if fusion.label == "verified_enterprise":
        verdict = "verified_enterprise"
    else:
        verdict = verdict_for(band, role)
        if mismatched:
            verdict = "synthetic+speaker_mismatch" if band in ("critical", "high") else "suspicious"

    nfd = noise_floor_dropouts_count(window, sr=settings.sample_rate)

    return {
        "type": "analysis",
        "synthetic_score": round(score, 4),
        "model_prob": round(model_prob, 4),
        "xai_risk": round(fusion.xai_risk, 4),
        "verdict": verdict,
        "risk_band": band,
        "recommendation": recommendation(band, role),
        "speaker_mismatch": mismatched,
        "watermark_hit": watermark.detected,
        "prosody": {
            "jitter_pct": round(prosodics.jitter_pct, 3),
            "shimmer_pct": round(prosodics.shimmer_pct, 3),
            "phase_continuity": round(prosodics.phase_continuity, 4),
            "pitch_stability": round(prosodics.pitch_stability_pct, 2),
            "noise_floor_dropouts": nfd,
            "watermark_snr": round(watermark.snr_ratio, 2),
        },
        "latency_ms": round(latency_ms, 2),
    }


def hop_step_ms() -> int:
    """Time advance per emitted window (ms)."""
    return int(round(settings.hop_samples * 1000.0 / settings.sample_rate))