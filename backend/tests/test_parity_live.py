"""
VoiceShield AI — Live Surface Parity Gate (fail-hard).

Gate B of the parity+latency plan. Anchors the SDK's *documented* cross-surface
claim (`sdk/voiceshield_sdk/grpc.py:9-13`: "same label, same scores, same risk
bands, same recommendation, same recommended actions ... over gRPC as over
REST") to a measurable, fail-hard gate: identical 16 kHz PCM window in ->
identical scores / bands / recommendations / actions out, on every transport
the SDK exposes.

**Corrected on the 2026-09-23 full-review pass.** The prior version compared
the engine's *verdict-core* dict (label/synthetic_score/risk_band/
recommendation) against the REST-analyze envelope (peak_score/risk_band/
windows_analyzed/recommendation/recommended_actions — carries no label or
synthetic_score) and the gRPC-detect envelope (label/synthetic_score/
confidence — carries no risk_band or recommendation). Those shapes cannot be
equal by construction, so two legs were permanently RED whatever the latency —
a category error, not a performance one. Transport envelopes legitimately
differ; the promised parity is on scores/bands/recommendations/actions across
surfaces that actually carry them.

What this gate asserts:

  1. test_engine_core_round_trips_cleanly      — the shared hot loop
     (`app.engine.pipeline.analyze_window`) still self-reports a verdict core
     on a real window.
  2. test_analyze_surfaces_agree_byte_for_byte — REST sync, REST async and
     gRPC Analyze return byte-identical {peak_score, risk_band,
     windows_analyzed, recommendation, recommended_actions, context} on
     identical PCM + context (silent window; the pipeline short-circuits the
     model deterministically, so this leg is fast).
  3. test_detect_surfaces_agree_byte_for_byte  — REST detect and gRPC detect
     return byte-identical {label, synthetic_score, confidence} from the
     Dhwani single-shot path (real ONNX run, ~16 s/window on this CPU box).
  4. test_engine_band_matches_surfaces         — the risk band + recommendation
     the engine assigns a window equals what REST Analyze reports for it.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict

import numpy as np

_BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_SDK = os.path.normpath(os.path.join(_BACKEND, "sdk"))
for _p in (_BACKEND, _SDK):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from app.engine.pipeline import analyze_window
from app.engine.risk import risk_band, recommendation

SR = 16000
WINDOW = SR * 3
ROLE = "adult"
_LIVE_RPC_TIMEOUT = 600.0

# Enrichment context used by the analyze parity leg. Caller supplied (so
# ctx.provided=True), origin empty (-> +0.05 unknown_origin modifier): the
# whole modifier pipeline is exercised, deterministically, on both surfaces.
_CONTEXT = {
    "caller": "9000000001",
    "origin": "",
    "txn_value": 0.0,
    "txn_category": "",
    "known_contact": None,
    "prior_flags": 0,
}

DETECT_CORE = ("label", "synthetic_score", "confidence")


def _silent_pcm() -> np.ndarray:
    """Deterministic silent 3 s int16 window (model short-circuit)."""
    return np.zeros(WINDOW, dtype=np.int16)


def _noise_pcm() -> np.ndarray:
    """Deterministic 3 s white-noise int16 window (real model run)."""
    rng = np.random.default_rng(seed=7)
    return rng.integers(-12000, 12000, WINDOW, dtype=np.int16).astype(np.int16)


def _analyze_core(d: Dict[str, Any]) -> Dict[str, Any]:
    """The byte-parity score core of an Analyze response (all surfaces)."""
    return {
        "peak_score": round(float(d.get("peak_score", 0.0)), 4),
        "risk_band": str(d.get("risk_band", "")),
        "windows_analyzed": int(d.get("windows_analyzed", 0)),
        "recommendation": str(d.get("recommendation", "")),
        "recommended_actions": tuple(str(a) for a in d.get("recommended_actions", [])),
    }


def _ctx_norm(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a context detail to the gRPC ContextDetail shape.

    REST's detail dict additionally exposes `provided` (gRPC proto has no such
    field) and returns None when nothing was supplied; those envelope
    differences are stripped so the *common* contract is compared.
    """
    if d is None:
        return {
            "enabled": False,
            "applied": False,
            "signals": {},
            "modifiers": {},
            "base_score": 0.0,
            "adjusted_score": 0.0,
        }
    return {
        "enabled": bool(d.get("enabled", False)),
        "applied": bool(d.get("applied", False)),
        "signals": {str(k): str(v) for k, v in (d.get("signals") or {}).items()},
        "modifiers": {str(k): round(float(v), 6) for k, v in (d.get("modifiers") or {}).items()},
        "base_score": round(float(d.get("base_score", 0.0)), 4),
        "adjusted_score": round(float(d.get("adjusted_score", 0.0)), 4),
    }


# ── Surface clients ──────────────────────────────────────────────────────

_REST_URL = ""


def _ensure_rest() -> str:
    """Start the FastAPI app on a real loopback socket (once) and return its URL."""
    global _REST_URL
    if _REST_URL:
        return _REST_URL
    import threading
    import time

    pytest.importorskip("uvicorn")

    from app.main import app
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 60.0
    while time.time() < deadline:
        if server.should_exit:
            raise RuntimeError("uvicorn exited during startup")
        if server.started and server.servers:
            sockets = server.servers[0].sockets
            if sockets:
                port = sockets[0].getsockname()[1]
                _REST_URL = f"http://127.0.0.1:{port}"
                return _REST_URL
        time.sleep(0.05)
    raise RuntimeError("timed out waiting for uvicorn to start")


def _rest_analyze_sync(pcm: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
    from voiceshield_sdk import VoiceShieldClient

    client = VoiceShieldClient(_ensure_rest(), timeout=_LIVE_RPC_TIMEOUT)
    kwargs: Dict[str, Any] = dict(
        audio_path=None,
        audio_bytes=pcm.astype(np.int16).tobytes(),
        role=ROLE,
        filename="parity.wav",
    )
    if context:
        kwargs["context"] = context
    return client.analyze(**kwargs)


def _rest_analyze(pcm: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
    from voiceshield_sdk import AsyncVoiceShieldClient

    kwargs: Dict[str, Any] = dict(
        audio_path=None,
        audio_bytes=pcm.astype(np.int16).tobytes(),
        role=ROLE,
        filename="parity.wav",
    )
    if context:
        kwargs["context"] = context

    async def _call() -> Any:
        return await AsyncVoiceShieldClient(
            _ensure_rest(), timeout=_LIVE_RPC_TIMEOUT
        ).analyze(**kwargs)

    return asyncio.run(_call())


def _rest_detect(pcm: np.ndarray) -> Dict[str, Any]:
    from voiceshield_sdk import VoiceShieldClient

    client = VoiceShieldClient(_ensure_rest(), timeout=_LIVE_RPC_TIMEOUT)
    return client.detect(
        audio_path=None,
        audio_bytes=pcm.astype(np.int16).tobytes(),
        filename="parity.wav",
    )


def _grpc_call(surface: str, pcm: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
    import threading
    import time

    import grpc.aio

    from app.grpc.servicer import VoiceShield as VoiceShieldServicer
    from app.grpc.voiceshield_pb2_grpc import add_VoiceShieldServicer_to_server
    from voiceshield_sdk.grpc import VoiceShieldGrpcClient

    # The sync SDK client would deadlock if the gRPC aio server loop ran in
    # this same thread, so the aio server runs in its own daemon thread and the
    # sync client calls it over a real loopback channel - exactly like a
    # bank/telecom caller would talk to a deployed gRPC listener.
    holder: Dict[str, Any] = {"port": None}
    stop_flag = threading.Event()

    async def _serve() -> None:
        server = grpc.aio.server()
        add_VoiceShieldServicer_to_server(VoiceShieldServicer(), server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        holder["port"] = port
        try:
            while not stop_flag.is_set():
                await asyncio.sleep(0.1)
        finally:
            await server.stop(0)

    thread = threading.Thread(target=lambda: asyncio.run(_serve()), daemon=True)
    thread.start()
    deadline = time.time() + 30.0
    while holder["port"] is None and time.time() < deadline:
        time.sleep(0.02)
    if holder["port"] is None:
        raise RuntimeError("gRPC server did not start in time")
    port = holder["port"]

    try:
        client = VoiceShieldGrpcClient(
            target=f"127.0.0.1:{port}", timeout=_LIVE_RPC_TIMEOUT
        )
        if surface == "analyze":
            return client.analyze(
                audio_path=None,
                audio_bytes=pcm.astype(np.int16).tobytes(),
                role=ROLE,
                context=context or None,
                filename="parity.wav",
            )
        return client.detect(
            audio_path=None,
            audio_bytes=pcm.astype(np.int16).tobytes(),
            language="auto",
            role=ROLE,
            filename="parity.wav",
        )
    finally:
        stop_flag.set()


# ── Tests ────────────────────────────────────────────────────────────────


def test_engine_core_round_trips_cleanly():
    """Sanity: the shared hot loop self-reports a verdict core on a real window."""
    core = analyze_window(_noise_pcm(), role=ROLE)
    for key in ("synthetic_score", "risk_band", "recommendation", "verdict"):
        assert key in core, f"engine event lost key={key}"
    assert core["synthetic_score"] >= 0.0
    assert core["verdict"] in {"bonafide", "spoof", "suspicious", "verified_enterprise"}


def test_analyze_surfaces_agree_byte_for_byte():
    """
    Identical PCM + context -> byte-identical score core across REST sync,
    REST async, and gRPC Analyze; context detail also agrees on the common keys.
    """
    from app.config import settings

    pytest.importorskip("voiceshield_sdk")

    silent = _silent_pcm()
    enrichment = settings.contextual_enrichment
    settings.contextual_enrichment = True  # exercise the enrichment pipeline
    try:
        rest_sync = _rest_analyze_sync(silent, context=_CONTEXT)
        rest_async = _rest_analyze(silent, context=_CONTEXT)
        grpc = _grpc_call("analyze", silent, _CONTEXT)
    finally:
        settings.contextual_enrichment = enrichment

    surfaces = {
        "rest-sync": rest_sync,
        "rest-async": rest_async,
        "grpc": grpc,
    }
    cores = {name: _analyze_core(d) for name, d in surfaces.items()}
    ctxs = {name: _ctx_norm(d.get("context")) for name, d in surfaces.items()}

    baseline = cores["rest-sync"]
    for name, core in cores.items():
        assert core == baseline, (
            f"parity violation on analyze surface={name}:\n"
            f"  rest-sync: {baseline}\n  {name}: {core}"
        )
    ctx_baseline = ctxs["rest-sync"]
    for name, ctx in ctxs.items():
        assert ctx == ctx_baseline, (
            f"context parity violation on analyze surface={name}:\n"
            f"  rest-sync: {ctx_baseline}\n  {name}: {ctx}"
        )

    # Sanity on the core values themselves.
    assert baseline["windows_analyzed"] == 1
    assert baseline["risk_band"] in {"low", "medium", "high", "critical"}
    assert baseline["peak_score"] == ctx_baseline["adjusted_score"]
    for act in baseline["recommended_actions"]:
        assert isinstance(act, str)


def test_detect_surfaces_agree_byte_for_byte():
    """
    Identical PCM -> byte-identical {label, synthetic_score, confidence} from
    REST detect and gRPC detect (Dhwani single-shot path — a real model run).
    """
    pytest.importorskip("voiceshield_sdk")

    pcm = _noise_pcm()
    rest = _rest_detect(pcm)
    grpc = _grpc_call("detect", pcm, {})

    assert {k: rest.get(k) for k in DETECT_CORE} == {k: grpc.get(k) for k in DETECT_CORE}, (
        f"detect parity violation:\n  rest: {rest}\n  grpc: {grpc}"
    )
    assert rest.get("label") in {"bonafide", "spoof"}
    assert 0.0 <= float(rest.get("synthetic_score", 0.0)) <= 1.0


def test_engine_band_matches_surfaces():
    """
    The band + recommendation the engine assigns a window equals what REST
    Analyze reports for that window (enrichment off, no context supplied).
    """
    pytest.importorskip("voiceshield_sdk")

    silent = _silent_pcm()
    ev = analyze_window(silent, role=ROLE)
    engine_band = risk_band(ev["synthetic_score"], ROLE)
    engine_rec = recommendation(engine_band, ROLE)

    rest = _rest_analyze_sync(silent, context={})
    assert rest["risk_band"] == engine_band, (
        f"REST band != engine band: rest={rest['risk_band']} engine={engine_band}"
    )
    assert rest["recommendation"] == engine_rec, (
        f"REST recommendation != engine recommendation: "
        f"rest={rest['recommendation']} engine={engine_rec}"
    )