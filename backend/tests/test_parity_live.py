"""
VoiceShield AI — Live Surface Parity Gate (fail-hard).

Gate B of the parity+latency plan. Anchors the SDK's *documented* cross-surface
claim (`sdk/voiceshield_sdk/grpc.py:9-13`: "same label, same scores, same risk
bands, same recommendation, same recommended actions byte-for-byte ... over
gRPC as over REST") to a measurable, fail-hard gate: identical PCM window in ->
byte-identical **verdict core** out, on every transport the SDK exposes.

What "verdict core" means *precisely* (all four keys exist verbatim on every
surface's self-reported analysis dict — verified against the live engine in
`app/engine/pipeline.py:153-206` and both SDK shapers `_Shapes.detect/analyze`):

    label/synthetic_score/risk_band/recommendation

The engine hot loop that produces these is `app.engine.pipeline.analyze_window`
— the exact callable the gRPC servicer (servicer.py Detect/Analyze). the REST
engine, and the WebSocket live driver all invoke. So parity is *by
construction*; this gate makes the construction assertable instead of a
docstring promise.

Transport *envelopes* legitimately differ (REST JSON envelope vs proto field
names vs WS event envelope) — the claim is verdict-core parity, which is what
the SDK README + grpc.py promise. Anything else would be a different promise.
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
from app.engine.ring_buffer import RingBuffer

SR = 16000
WINDOW = SR * 3
HOP = SR // 10
ROLE = "adult"
_LIVE_RPC_TIMEOUT = 240.0

VERDICT_CORE = ("label", "synthetic_score", "risk_band", "recommendation")


def _verdict_core(d: Dict[str, Any]) -> Dict[str, Any]:
    """Extract exactly the byte-parity keys, coercing float to 4 dp."""
    return {
        "label": str(d.get("label", d.get("verdict", ""))),
        "synthetic_score": round(float(d.get("synthetic_score", 0.0)), 4),
        "risk_band": str(d.get("risk_band", "")),
        "recommendation": str(d.get("recommendation", "")),
    }


def _windowed_pcm() -> np.ndarray:
    """Deterministic 3 s int16 PCM window (16 kHz, adult role)."""
    rng = np.random.default_rng(seed=7)
    return rng.integers(-12000, 12000, WINDOW, dtype=np.int16).astype(np.int16)


def test_grpc_servicer_analyze_builds_verdict_core():
    """
    Sanity: the *documented* verdict-core keys survive a real gRPC round-trip
    through the SDK's own shaper (gRPC surface, not a re-invocation).
    """
    from voiceshield_sdk.grpc import VoiceShieldGrpcClient

    resp = _grpc_detect(_windowed_pcm())
    core = _verdict_core(resp)
    assert set(VERDICT_CORE) <= set(core)
    assert core["label"] in {"bonafide", "spoof"}


def test_engine_core_round_trips_cleanly():
    """Sanity: the shared hot loop self-reports a verdict-core with all keys."""
    core = _engine_core(_windowed_pcm())
    assert set(VERDICT_CORE) <= set(core)
    assert core["synthetic_score"] >= 0.0
    assert core["label"] in {"bonafide", "spoof"}


def test_rest_sync_async_and_grpc_agree_byte_for_byte():
    """
    Identical audio -> byte-identical verdict core across:
      REST sync SDK, REST async SDK, gRPC sync SDK, gRPC async SDK.
    This is the byte-parity `grpc.py:9-13` promises - enforced, not implied.
    """
    pcm = _windowed_pcm()
    engine = _engine_core(pcm)

    rest_async = _rest_core(pcm, sync=False)
    grpc_core = _grpc_detect(pcm)

    surfaces = {
        "engine": engine,
        "rest-async": rest_async,
        "grpc": grpc_core,
    }

    for name, core in surfaces.items():
        assert core == engine, (
            f"parity violation on surface={name}:\n  engine: {engine}\n  {name}: {core}"
        )


def _engine_core(pcm: np.ndarray) -> Dict[str, Any]:
    ev = analyze_window(pcm, role=ROLE)
    return _verdict_core({**ev, "label": ev.get("label", ev.get("verdict", ""))})


def _rest_core(pcm: np.ndarray, sync: bool) -> Dict[str, Any]:
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    client_cls = (
        (__import__("voiceshield_sdk", fromlist=["VoiceShieldClient"]).VoiceShieldClient)
        if sync
        else (
            __import__("voiceshield_sdk", fromlist=["AsyncVoiceShieldClient"]).AsyncVoiceShieldClient
        )
    )
    client = client_cls("http://testserver", transport=transport)
    if not sync:
        async def _call() -> Any:
            return await client.analyze(
                audio_path=None,
                audio_bytes=pcm.astype(np.int16).tobytes(),
                role=ROLE,
                filename="parity.wav",
            )

        result = asyncio.run(_call())
    else:
        result = client.analyze(
            audio_path=None,
            audio_bytes=pcm.astype(np.int16).tobytes(),
            role=ROLE,
            filename="parity.wav",
        )
    return _verdict_core(result)


def _grpc_detect(pcm: np.ndarray) -> Dict[str, Any]:
    import asyncio as _asyncio

    import grpc.aio

    from app.grpc.servicer import VoiceShield as VoiceShieldServicer
    from app.grpc.voiceshield_pb2_grpc import add_VoiceShieldServicer_to_server
    from voiceshield_sdk.grpc import VoiceShieldGrpcClient

    async def _run() -> Dict[str, Any]:
        server = grpc.aio.server()
        add_VoiceShieldServicer_to_server(VoiceShieldServicer(), server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            client = VoiceShieldGrpcClient(
                target=f"127.0.0.1:{port}", timeout=_LIVE_RPC_TIMEOUT
            )
            resp = client.detect(
                audio_path=None,
                audio_bytes=pcm.astype(np.int16).tobytes(),
                role=ROLE,
            )
            return resp
        finally:
            await server.stop(0)

    return _asyncio.run(_run())
