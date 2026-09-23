"""
VoiceShield AI — gRPC `known_contact` proto3 3-state presence tests

`optional bool known_contact` (proto3 explicit presence, oneof `_known_contact`)
keeps all three REST form states on the gRPC wire:

    (i)   not set      -> HasField False -> servicer passes None -> auto-check
    (ii)  set True     -> known-contact boost signal
    (iii) set False    -> explicit unknown-contact penalty

Locks down:
  * pb2 presence semantics (HasField round-trip through serialization),
  * SDK client leave-unset-when-None behaviour,
  * a full round-trip through a REAL gRPC server + VoiceShieldGrpcClient,
  * byte-parity of the enrichment context between gRPC Analyze and REST
    /api/analyze for all three states (silent PCM -> model short-circuit,
    so the leg stays fast).
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time

import numpy as np
import pytest

_BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_SDK = os.path.normpath(os.path.join(_BACKEND, "sdk"))
for _p in (_BACKEND, _SDK):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SR = 16000
WINDOW = SR * 3
ROLE = "adult"
CALLER = "+919000000042"   # contacts table cleaned below -> auto-check = None
_RPC_TIMEOUT = 120.0

# The three wire states: (label, value passed by the SDK/REST caller).
STATE_UNSET = ("unset", None)
STATE_TRUE = ("true", True)
STATE_FALSE = ("false", False)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_and_enrichment_on():
    """Empty contact/reputation tables (deterministic auto-check) + force the
    enrichment pipeline on (config default is off for the offline suite)."""
    from app import store
    from app.config import settings

    store._execute("DELETE FROM context_contacts")
    store._execute("DELETE FROM caller_reputation")
    saved = settings.contextual_enrichment
    settings.contextual_enrichment = True
    try:
        yield
    finally:
        settings.contextual_enrichment = saved


def _silent_pcm() -> np.ndarray:
    """Deterministic silent 3 s int16 window (pipeline short-circuits)."""
    return np.zeros(WINDOW, dtype=np.int16)


# ── 1. pb2 presence semantics ─────────────────────────────────────────────

class TestPb2Presence:
    def _req(self, known_contact=...):
        from app.grpc.voiceshield_pb2 import AnalyzeRequest

        req = AnalyzeRequest(audio=b"\x00\x00", role=ROLE, caller=CALLER)
        if known_contact is not ...:
            req.known_contact = known_contact
        return req

    def test_not_set_hasfield_false(self):
        req = self._req()
        assert req.HasField("known_contact") is False

    def test_set_true_hasfield_true(self):
        req = self._req(True)
        assert req.HasField("known_contact") is True
        assert req.known_contact is True

    def test_set_false_hasfield_true_and_value_false(self):
        """Explicit False must survive as a PRESENT field, not collapse to
        the proto3 default (which would be indistinguishable from unset)."""
        req = self._req(False)
        assert req.HasField("known_contact") is True
        assert req.known_contact is False

    def test_presence_survives_serialization_roundtrip(self):
        from app.grpc.voiceshield_pb2 import AnalyzeRequest

        for value, expect_present in ((None, False), (True, True), (False, True)):
            req = AnalyzeRequest(audio=b"\x00\x00", role=ROLE, caller=CALLER)
            if value is not None:
                req.known_contact = value
            parsed = AnalyzeRequest()
            parsed.ParseFromString(req.SerializeToString())
            assert parsed.HasField("known_contact") is expect_present, value
            if expect_present:
                assert parsed.known_contact is value


# ── 2. SDK leaves the field unset iff None ────────────────────────────────

class TestSdkWireBehaviour:
    def _build_request(self, ctx: dict):
        from app.grpc.voiceshield_pb2 import AnalyzeRequest

        _req = AnalyzeRequest(audio=b"", role=ROLE)
        if ctx.get("known_contact") is not None:
            _req.known_contact = bool(ctx["known_contact"])
        return _req

    @pytest.mark.parametrize("value,expected", [(None, False), (True, True), (False, True)])
    def test_sdk_sets_field_iff_value_provided(self, value, expected):
        req = self._build_request({"known_contact": value})
        assert req.HasField("known_contact") is expected
        if expected:
            assert req.known_contact is value

    def test_missing_key_equals_none(self):
        assert self._build_request({}).HasField("known_contact") is False
        assert self._build_request({"known_contact": None}).HasField("known_contact") is False


# ── 3. Real gRPC round-trip (server + VoiceShieldGrpcClient) ─────────────

@pytest.fixture(scope="module")
def grpc_target():
    """Start the real aio gRPC server once; yield '127.0.0.1:{port}'."""
    from app.grpc.servicer import VoiceShield
    from app.grpc.voiceshield_pb2_grpc import add_VoiceShieldServicer_to_server

    holder: dict = {"port": None}
    stop_flag = threading.Event()

    async def _serve() -> None:
        import grpc.aio

        server = grpc.aio.server()
        add_VoiceShieldServicer_to_server(VoiceShield(), server)
        holder["port"] = server.add_insecure_port("127.0.0.1:0")
        await server.start()
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
    try:
        yield f"127.0.0.1:{holder['port']}"
    finally:
        stop_flag.set()
        thread.join(timeout=10.0)


def _grpc_analyze(grpc_target: str, known_contact) -> dict:
    from voiceshield_sdk.grpc import VoiceShieldGrpcClient

    ctx: dict = {"caller": CALLER, "origin": "telecom"}
    if known_contact is not None:
        ctx["known_contact"] = known_contact
    client = VoiceShieldGrpcClient(target=grpc_target, timeout=_RPC_TIMEOUT)
    return client.analyze(
        audio_path=None,
        audio_bytes=_silent_pcm().tobytes(),
        role=ROLE,
        context=ctx,
        filename="kc.wav",
    )


def _rest_analyze(known_contact) -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    data = {"caller": CALLER, "origin": "telecom"}
    if known_contact is not None:
        data["known_contact"] = "true" if known_contact else "false"
    client = TestClient(app)
    r = client.post(
        f"/api/analyze?role={ROLE}",
        files={"file": ("kc.wav", _silent_pcm().tobytes(), "audio/wav")},
        data=data,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _ctx_norm(d) -> dict:
    """Normalize a context detail to the gRPC ContextDetail shape
    (REST exposes bools + a `provided` key; the proto map is stringly)."""
    if d is None:
        return {
            "enabled": False, "applied": False, "signals": {},
            "modifiers": {}, "base_score": 0.0, "adjusted_score": 0.0,
        }
    return {
        "enabled": bool(d.get("enabled", False)),
        "applied": bool(d.get("applied", False)),
        "signals": {str(k): str(v) for k, v in (d.get("signals") or {}).items()},
        "modifiers": {str(k): round(float(v), 6) for k, v in (d.get("modifiers") or {}).items()},
        "base_score": round(float(d.get("base_score", 0.0)), 4),
        "adjusted_score": round(float(d.get("adjusted_score", 0.0)), 4),
    }


class TestKnownContactThreeStates:
    """(i) unset -> auto-check (absent), (ii) True -> boost, (iii) False -> penalty."""

    def test_unset_means_auto_check_signal_absent(self, grpc_target):
        resp = _grpc_analyze(grpc_target, None)
        ctx = resp["context"]
        # Empty contacts table -> auto resolves to None -> signal disabled.
        assert "known_contact" not in ctx["signals"]
        assert "known_contact" not in ctx["modifiers"]
        assert "unknown_contact" not in ctx["modifiers"]
        # Caller/origin were supplied, so enrichment ran — but telecom origin
        # + empty tables means no modifier fired -> applied stays False.
        assert ctx["enabled"] is True
        assert ctx["applied"] is False

    def test_explicit_true_boosts(self, grpc_target):
        resp = _grpc_analyze(grpc_target, True)
        ctx = resp["context"]
        assert ctx["signals"].get("known_contact") == "True"
        assert "known_contact" in ctx["modifiers"]
        assert ctx["modifiers"]["known_contact"] < 0  # boost lowers risk
        assert ctx["adjusted_score"] <= ctx["base_score"]

    def test_explicit_false_penalizes(self, grpc_target):
        resp = _grpc_analyze(grpc_target, False)
        ctx = resp["context"]
        assert ctx["signals"].get("known_contact") == "False"
        assert "unknown_contact" in ctx["modifiers"]
        assert ctx["modifiers"]["unknown_contact"] > 0  # penalty raises risk
        assert ctx["adjusted_score"] >= ctx["base_score"]

    def test_true_and_false_produce_different_scores(self, grpc_target):
        r_true = _grpc_analyze(grpc_target, True)
        r_false = _grpc_analyze(grpc_target, False)
        r_unset = _grpc_analyze(grpc_target, None)
        assert r_true["context"]["adjusted_score"] < r_unset["context"]["adjusted_score"]
        assert r_unset["context"]["adjusted_score"] < r_false["context"]["adjusted_score"]
        # Same acoustic base (silent window) across all three.
        bases = {r["context"]["base_score"] for r in (r_true, r_false, r_unset)}
        assert len(bases) == 1


class TestGrpcRestEnrichmentParity:
    """gRPC Analyze and REST /api/analyze must agree on the enrichment context
    for each of the three known_contact wire states (silent PCM)."""

    @pytest.mark.parametrize(
        "state",
        [STATE_UNSET, STATE_TRUE, STATE_FALSE],
        ids=[s[0] for s in (STATE_UNSET, STATE_TRUE, STATE_FALSE)],
    )
    def test_context_parity_per_state(self, grpc_target, state):
        _, value = state
        grpc_resp = _grpc_analyze(grpc_target, value)
        rest_resp = _rest_analyze(value)

        grpc_ctx = _ctx_norm(grpc_resp["context"])
        rest_ctx = _ctx_norm(rest_resp.get("context"))

        assert grpc_ctx == rest_ctx, (
            f"enrichment context parity violation for known_contact={value!r}:\n"
            f"  grpc: {grpc_ctx}\n  rest: {rest_ctx}"
        )
        # Score core parity too (context feeds the surfaced peak score).
        assert round(float(grpc_resp["peak_score"]), 4) == round(float(rest_resp["peak_score"]), 4)
        assert grpc_resp["risk_band"] == rest_resp["risk_band"]
        assert grpc_resp["recommendation"] == rest_resp["recommendation"]
