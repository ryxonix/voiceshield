"""
VoiceShield AI — On-device / edge inference worker.

Runs the SAME backend ONNX + DSP pipeline as a standalone CLI for on-prem /
edge boxes (PoE-powered NUC/RPi-class, operator network), satisfying the
"on-device or edge inference" requirement of SIH26104. Emits scalar scores only
(feature-only logging) — raw audio is never written back and buffers are wiped.

Reuses the backend modules over sys.path (no server, no DB, no network).

Usage:
    python vs_edge.py --input bonafide.wav --role adult
    python vs_edge.py --input cloned.wav --role child --json
    python vs_edge.py --input a.wav b.wav --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow importing the shared backend pipeline without booting FastAPI.
_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import numpy as np  # noqa: E402


def _decide_window() -> tuple[int, int]:
    """Mirror the server's model-aware window strategy."""
    from app.config import settings

    try:
        from app.engine.dhwani import get_detector, MAX_SAMPLES
        dhwani_ready = get_detector().is_ready
    except Exception:  # noqa: BLE001
        dhwani_ready = False
    return (
        (MAX_SAMPLES, int(settings.sample_rate))
        if dhwani_ready
        else (settings.window_samples, settings.hop_samples)
    )


def analyze_file(path: str, role: str = "adult", max_windows: int = 300) -> dict:
    import soundfile as sf
    from app.engine.ring_buffer import RingBuffer
    from app.engine.pipeline import analyze_window
    from app.engine.risk import risk_band, recommendation

    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    audio = audio[:, 0]
    if sr != 16000:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    audio = np.clip(audio, -1.0, 1.0)
    int16 = (audio * 32767.0).astype(np.int16)

    window_size, hop_size = _decide_window()
    if len(int16) < window_size:
        int16 = np.pad(int16, (0, window_size - len(int16)), mode="constant")

    ring = RingBuffer(window_size=window_size, hop_size=hop_size)
    frames = ring.push(int16)[:max_windows]
    step_ms = int(round(hop_size * 1000.0 / 16000))

    windows = []
    peak = 0.0
    for idx, frame in enumerate(frames):
        ev = analyze_window(frame, role=role, include_xlsr=True)
        peak = max(peak, ev["synthetic_score"])
        windows.append(
            {
                "t_ms": idx * step_ms,
                "synthetic_score": round(float(ev["synthetic_score"]), 4),
                "model_prob": round(float(ev["model_prob"]), 4),
                "xai_risk": round(float(ev["xai_risk"]), 4),
                "verdict": ev["verdict"],
            }
        )

    return {
        "file": os.path.basename(path),
        "role": role,
        "peak_score": round(float(peak), 4),
        "risk_band": risk_band(peak, role),
        "recommendation": recommendation(risk_band(peak, role), role),
        "windows_analyzed": len(windows),
        "windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceShield AI edge worker")
    parser.add_argument("--input", nargs="+", required=True, help="WAV/FLAC file(s)")
    parser.add_argument("--role", default="adult", choices=["adult", "child"])
    parser.add_argument("--json", action="store_true", help="emit JSON (one object per file)")
    args = parser.parse_args()

    results = [analyze_file(p, role=args.role) for p in args.input]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for r in results:
        print(
            f"{r['file']:<24} peak={r['peak_score']:.3f} "
            f"band={r['risk_band']:<8} windows={r['windows_analyzed']}"
        )
        print(f"    {r['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())