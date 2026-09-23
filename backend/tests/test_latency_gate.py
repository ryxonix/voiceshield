"""
VoiceShield AI — Latency Budget Gate (fail-hard).

Gate A from the parity+latency plan. Anchors the *documented* per-window
real-time latency budget (about project.txt §8 / README "Latency budget",
2026-09-23) to a measurable, fail-hard gate on the real hot loop.

Reality: on the reference CPU the trained AASIST-L official detector
(~0.78 s/window) + XAI prosody (~0.77 s) total ~1.5-1.6 s median per 3 s
window — the historical ≤78 ms budget was unreachable on CPU and was honestly
retired. The real-time profile therefore budgets `latency_budget_ms=2000.0`
by default (measured pass margin ~25%) and this gate enforces it.

The hot loop is `app.engine.pipeline.analyze_window(window, role=...)` — the
exact callable the WebSocket live driver (app/streaming/websocket.py:173), the
gRPC servicer (_windowed, app/grpc/servicer.py), and the latency gate all run
per window. `analyze_window` reports its own `latency_ms` measured in-pipeline
with `time.perf_counter`, so we assert the pipeline's own honest number, not a
test-harness proxy.

The gate measures the REALTIME profile deterministically (`realtime=True`),
so it stays valid regardless of `settings.latency_profile` in the local .env.
The ensemble /api/analyze surface is seconds-per-window by design and is NOT
a streaming-latency contract — it is bounded as a batch by the SDK RPC timeout.

Budget resolution:
  * default  budget: settings.latency_budget_ms (2000.0 ms) — from config,
    not duplicated here (single source of truth).
  * env override: VOICESHIELD_LATENCY_BUDGET_MS — set ONLY on slower CI
    runners to raise the assert; the test prints the effective budget so a
    silent relaxation is impossible. Default is fail-hard.

Sad path is deliberate: if the hot loop exceeds the budget (worst-window
median after warm-up), the suite fails — that is the point.
"""

import os
from statistics import median

import numpy as np

from app.config import settings
from app.engine.pipeline import analyze_window


SR = 16000
WINDOW = SR * 3          # 3 s PCM window = 48 000 samples @16 kHz
ROLE = "adult"

# Warm-up runs (model load / first-touch cost is excluded from the median).
WARMUP = 3
# Measured runs used for the median; profiling noise (GC, scheduler blip) is
# smoothed by the median, not the mean — the budget is a "typical window" gate.
MEASURED = 25

# Fail-hard budget: single source of truth = the app's own config. CI may raise
# it explicitly via VOICESHIELD_LATENCY_BUDGET_MS. A silent raise is impossible
# because the test prints the effective budget and the effective budget.
BUDGET_MS = float(os.environ.get("VOICESHIELD_LATENCY_BUDGET_MS", settings.latency_budget_ms))


def _noise_window(seed: int) -> np.ndarray:
    """Deterministic pseudo noise window (int16 PCM) for stable timing."""
    rng = np.random.default_rng(seed=seed)
    return rng.integers(-12_000, 12_000, size=WINDOW, dtype=np.int16).astype(np.int16)


def _selection_latencies() -> list[float]:
    """Return per-window latency_ms from the real-time hot loop (post warm-up).

    Each window travels the exact callable the streaming/gRPC paths use
    (`analyze_window`), forced to the real-time profile. Independent fresh
    windows avoid cross-run cache effects.
    """
    for w in range(WARMUP):
        analyze_window(_noise_window(seed=1000 + w), role=ROLE, realtime=True)

    lat = []
    for w in range(MEASURED):
        ev = analyze_window(_noise_window(seed=2000 + w), role=ROLE, realtime=True)
        lat.append(ev["latency_ms"])
    return lat


def test_per_window_latency_within_documented_budget():
    """
    The real-time hot loop (analyze_window, realtime=True) must keep median
    per-window latency within the documented real-time budget
    (settings.latency_budget_ms default 2000 ms; fails hard).

    Uses the pipeline's own latency_ms (via perf_counter inside the real hot
    path the WebSocket + gate both invoke), median of ≥20 measured windows
    AFTER warm-up so model-load/first-touch cost is excluded.
    """
    lat = _selection_latencies()
    assert len(lat) >= 20, f"expected ≥20 measured windows, got {len(lat)}"
    med = median(lat)

    # Envelope for the printed gate — the documented number becomes a tested,
    # visible, reproducible claim (min / p50 / p95 / max over the same run).
    o = sorted(lat)
    p95 = o[min(len(o) - 1, int(0.95 * len(o)))]
    print(
        "\n[latency-gate] realtime per-window latency envelope "
        f"(median={med:.1f}ms, min={o[0]:.1f}ms, p95={p95:.1f}ms, max={o[-1]:.1f}ms "
        f"| budget={BUDGET_MS}ms, profile=realtime, {len(lat)} windows)"
    )

    assert med <= BUDGET_MS, (
        f"per-window median latency {med:.2f}ms exceeds documented real-time "
        f"budget {BUDGET_MS}ms — latency regression or slow model path"
    )