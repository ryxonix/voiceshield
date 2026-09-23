"""
VoiceShield AI - gRPC SDK client module.

Mirrors `voiceshield_sdk/client.py` (httpx REST SDK) 1:1 in public surface, but
speaks the `voiceshield.v1.VoiceShield` gRPC Service from
`backend/sdk/voiceshield.proto` over an insecure / TLS channel.

Because the gRPC servicer reuses the *same* engine pipeline, context
enrichment, risk bands, incident store, and tamper-evident ledger as the REST
app (see `app.grpc.servicer`), a gRPC `detect()` / `analyze()` returns the same
scores, bands, recommendation, recommended actions, and context detail as the
REST SDK on the same 16 kHz PCM audio + same context - parity is by
construction and asserted byte-for-byte in `tests/test_parity_live.py`.

Threading model:
  * `VoiceShieldGrpcClient`    - synchronous facade on a plain `grpc.Channel`.
    Use from sync bank / contact-center / telecom integrations.
  * `VoiceShieldGrpcAioClient` - asyncio facade on a `grpc.aio.Channel`, a
    drop-in for callers who already use the async (httpx) REST SDK.

Both accept an injected `channel=...` so test-suites can pass an in-process
`grpc.aio` server channel, or a TLS channel for production.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional, Union

import grpc

from app.grpc.voiceshield_pb2 import (
    AcknowledgeRequest,
    AcknowledgeResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    DetectRequest,
    DetectResponse,
    EscalateRequest,
    EscalateResponse,
    GetIncidentRequest,
    GetWorkflowsRequest,
    GetWorkflowsResponse,
    ListIncidentsRequest,
    ListIncidentsResponse,
    RegisterSpeakerRequest,
    RegisterSpeakerResponse,
    RetryAnchorRequest,
    RetryAnchorResponse,
    VerifyCallRequest,
    VerifyCallResponse,
)
from app.grpc.voiceshield_pb2_grpc import VoiceShieldStub

logger = logging.getLogger("voiceshield_sdk.grpc")


# ---- Wire shapes (gRPC response -> REST-shaped dict) ----------------
class _GrpcShapes:
    """Serialize gRPC responses into the exact dict shapes REST returns."""

    @staticmethod
    def detect(r: DetectResponse) -> Dict[str, Any]:
        return {
            "label": r.label,
            "synthetic_score": round(float(r.synthetic_score), 4),
            "confidence": round(float(r.confidence), 4),
        }

    @staticmethod
    def analyze(r: AnalyzeResponse) -> Dict[str, Any]:
        ctx = r.context
        return {
            "peak_score": round(float(r.peak_score), 4),
            "risk_band": r.risk_band,
            "windows_analyzed": int(r.windows_analyzed),
            "recommendation": r.recommendation,
            "recommended_actions": [str(a) for a in r.recommended_actions],
            "context": {
                "enabled": bool(ctx.enabled),
                "applied": bool(ctx.applied),
                "signals": {str(k): str(v) for k, v in ctx.signals.items()},
                "modifiers": {str(k): round(float(v), 6) for k, v in ctx.modifiers.items()},
                "base_score": round(float(ctx.base_score), 4),
                "adjusted_score": round(float(ctx.adjusted_score), 4),
            },
        }

    @staticmethod
    def workflows(r: GetWorkflowsResponse) -> Dict[str, Any]:
        return {
            "version": int(r.version),
            "active_path": r.active_path,
            "rules": [
                {
                    "role": rule.role,
                    "band_min": rule.band_min,
                    "actions": [str(a) for a in rule.actions],
                    "channels": [str(c) for c in rule.channels],
                }
                for rule in r.rules
            ],
        }

    @staticmethod
    def incidents(r: ListIncidentsResponse) -> List[Dict[str, Any]]:
        return [_GrpcShapes.incident(i) for i in r.incidents]

    @staticmethod
    def incident(i) -> Dict[str, Any]:
        ctx = i.context
        return {
            "id": i.id,
            "session_id": i.session_id,
            "role": i.role,
            "severity": i.severity,
            "score": round(float(i.score), 4),
            "base_score": round(float(i.base_score), 4),
            "context": {
                "enabled": bool(ctx.enabled),
                "applied": bool(ctx.applied),
                "signals": {str(k): str(v) for k, v in ctx.signals.items()},
                "modifiers": {str(k): round(float(v), 6) for k, v in ctx.modifiers.items()},
                "base_score": round(float(ctx.base_score), 4),
                "adjusted_score": round(float(ctx.adjusted_score), 4),
            },
            "triggers": [str(t) for t in i.triggers],
            "speaker_mismatch": bool(i.speaker_mismatch),
            "acknowledged": bool(i.acknowledged),
            "created_at": i.created_at,
        }

    @staticmethod
    def acknowledge(r: AcknowledgeResponse) -> Dict[str, Any]:
        return {"ok": bool(r.ok), "id": r.id}

    @staticmethod
    def escalate(r: EscalateResponse) -> Dict[str, Any]:
        return {
            "ok": bool(r.ok),
            "id": r.id,
            "escalated": bool(r.escalated),
            "caller_flag_count": int(r.caller_flag_count),
        }

    @staticmethod
    def verify(r: VerifyCallResponse) -> Dict[str, Any]:
        return {
            "valid": bool(r.valid),
            "anchor_status": r.anchor_status,
            "ipfs_cid": r.ipfs_cid,
            "tx_id": r.tx_id,
            "problems": [str(p) for p in r.problems],
        }

    @staticmethod
    def retry(r: RetryAnchorResponse) -> Dict[str, Any]:
        return {str(k): str(v) for k, v in r.result.items()}

    @staticmethod
    def register(r: RegisterSpeakerResponse) -> Dict[str, Any]:
        return {"ok": bool(r.ok), "label": r.label, "dim": int(r.dim)}


# ---- Audio helpers --------------------------------------------------
def _pcm16_to_float(pcm: bytes) -> "numpy.ndarray":
    import numpy as np

    raw = np.frombuffer(pcm, dtype="<i2")
    return raw.astype(np.float32) / 32768.0


def _audio_bytes(audio_path=None, audio_bytes=None, filename=None) -> Optional[bytes]:
    """Resolve audio source to 16 kHz mono int16 PCM bytes."""
    if audio_path is not None:
        with open(audio_path, "rb") as f:
            return f.read()
    return audio_bytes


def _wav_bytes_to_pcm16(wav_bytes: bytes) -> bytes:
    """Best-effort: pass WAV bytes straight through (servicer understands WAV)."""
    return wav_bytes


class _BaseGrpcClient:
    def __init__(
        self,
        channel: Optional[grpc.Channel] = None,
        target: str = "127.0.0.1:50051",
        timeout: float = 15.0,
    ) -> None:
        if channel is not None:
            self._channel = channel
            self._own_channel = False
        else:
            self._channel = grpc.insecure_channel(target)
            self._own_channel = True
        self._timeout = timeout

    def close(self) -> None:
        if self._own_channel:
            self._channel.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class VoiceShieldGrpcClient(_BaseGrpcClient):
    """Synchronous gRPC client mirroring `voiceshield_sdk.VoiceShieldClient`."""

    def __init__(
        self,
        channel: Optional[grpc.Channel] = None,
        target: str = "127.0.0.1:50051",
        timeout: float = 15.0,
    ) -> None:
        super().__init__(channel=channel, target=target, timeout=timeout)
        self._stub = VoiceShieldStub(self._channel)

    # -- Detect / Analyze --------------------------------------------
    def detect(
        self,
        audio_path=None,
        audio_bytes=None,
        language: str = "auto",
        role: str = "adult",
        filename=None,
    ) -> dict:
        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("detect(): provide audio_path or audio_bytes")
        resp = self._stub.Detect(
            DetectRequest(audio=pcm, language=language), timeout=self._timeout
        )
        return _GrpcShapes.detect(resp)

    def analyze(
        self,
        audio_path=None,
        audio_bytes=None,
        role: str = "adult",
        context: Optional[Dict[str, Any]] = None,
        filename=None,
    ) -> dict:
        from app.grpc.voiceshield_pb2 import ContextDetail  # local, tiny

        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("analyze(): provide audio_path or audio_bytes")
        ctx = context or {}
        resp = self._stub.Analyze(
            AnalyzeRequest(
                audio=pcm,
                role=role,
                caller=str(ctx.get("caller") or ""),
                origin=str(ctx.get("origin") or ""),
                txn_value=float(ctx.get("txn_value") or 0.0),
                txn_category=str(ctx.get("txn_category") or ""),
                known_contact=bool(ctx.get("known_contact")),
                prior_flags=int(ctx.get("prior_flags") or 0),
            ),
            timeout=self._timeout,
        )
        return _GrpcShapes.analyze(resp)

    # -- Incidents ---------------------------------------------------
    def incidents(self, limit: int = 50) -> list:
        resp = self._stub.ListIncidents(
            ListIncidentsRequest(limit=limit), timeout=self._timeout
        )
        return _GrpcShapes.incidents(resp)

    def incident(self, iid: str) -> dict:
        resp = self._stub.GetIncident(GetIncidentRequest(id=iid), timeout=self._timeout)
        return _GrpcShapes.incident(resp)

    def acknowledge(self, iid: str) -> dict:
        resp = self._stub.Acknowledge(
            AcknowledgeRequest(id=iid), timeout=self._timeout
        )
        return _GrpcShapes.acknowledge(resp)

    def escalate(self, iid: str, note: str = "") -> dict:
        resp = self._stub.Escalate(
            EscalateRequest(id=iid, note=note), timeout=self._timeout
        )
        return _GrpcShapes.escalate(resp)

    # -- Workflows ---------------------------------------------------
    def workflows(self) -> dict:
        resp = self._stub.GetWorkflows(GetWorkflowsRequest(), timeout=self._timeout)
        return _GrpcShapes.workflows(resp)

    # -- Blockchain / ledger -----------------------------------------
    def verify_call(self, call_id: str) -> dict:
        resp = self._stub.VerifyCall(
            VerifyCallRequest(call_id=call_id), timeout=self._timeout
        )
        return _GrpcShapes.verify(resp)

    def retry_anchor(self, call_id: str) -> dict:
        resp = self._stub.RetryAnchor(
            RetryAnchorRequest(call_id=call_id), timeout=self._timeout
        )
        return _GrpcShapes.retry(resp)

    # -- Speaker enrollment ------------------------------------------
    def register_speaker(self, label: str, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("register_speaker(): provide audio_path or audio_bytes")
        resp = self._stub.RegisterSpeaker(
            RegisterSpeakerRequest(audio=pcm, label=label, language=language),
            timeout=self._timeout,
        )
        return _GrpcShapes.register(resp)


class VoiceShieldGrpcAioClient(_BaseGrpcClient):
    """Async gRPC client mirroring `voiceshield_sdk.AsyncVoiceShieldClient`."""

    def __init__(
        self,
        channel: Optional[grpc.aio.Channel] = None,
        target: str = "127.0.0.1:50051",
        timeout: float = 15.0,
    ) -> None:
        if channel is None:
            channel = grpc.aio.insecure_channel(target)
            _built_channel = True
        else:
            _built_channel = False
        super().__init__(channel=channel, target=target, timeout=timeout)
        if _built_channel:
            self._own_channel = True
        self._stub = VoiceShieldStub(self._channel)

    async def aclose(self) -> None:
        if self._own_channel:
            await self._channel.close()
            self._own_channel = False
            return
        self.close()

    def close(self) -> None:
        if not self._own_channel:
            return
        close_fn = self._channel.close
        # A `grpc.aio.Channel.close()` is a *coroutine*; there is no way to await it from
        # a sync method. Refuse rather than drop an un-awaited coroutine on the floor.
        if inspect.iscoroutinefunction(close_fn):
            raise RuntimeError(
                "VoiceShieldGrpcAioClient owns an aio channel; use `await client.aclose()`"
                " instead of the sync `close()`"
            )
        self._channel.close()
        self._own_channel = False


    async def detect(self, audio_path=None, audio_bytes=None, language: str = "auto", filename=None) -> dict:
        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("detect(): provide audio_path or audio_bytes")
        resp = await self._stub.Detect(DetectRequest(audio=pcm, language=language), timeout=self._timeout)
        return _GrpcShapes.detect(resp)

    async def analyze(self, audio_path=None, audio_bytes=None, role: str = "adult", context=None, filename=None) -> dict:
        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("analyze(): provide audio_path or audio_bytes")
        ctx = context or {}
        resp = await self._stub.Analyze(
            AnalyzeRequest(
                audio=pcm,
                role=role,
                caller=str(ctx.get("caller") or ""),
                origin=str(ctx.get("origin") or ""),
                txn_value=float(ctx.get("txn_value") or 0.0),
                txn_category=str(ctx.get("txn_category") or ""),
                known_contact=bool(ctx.get("known_contact")),
                prior_flags=int(ctx.get("prior_flags") or 0),
            ),
            timeout=self._timeout,
        )
        return _GrpcShapes.analyze(resp)

    async def workflows(self) -> dict:
        resp = await self._stub.GetWorkflows(GetWorkflowsRequest(), timeout=self._timeout)
        return _GrpcShapes.workflows(resp)

    async def incidents(self, limit: int = 50) -> list:
        resp = await self._stub.ListIncidents(
            ListIncidentsRequest(limit=limit), timeout=self._timeout
        )
        return _GrpcShapes.incidents(resp)

    async def incident(self, iid: str) -> dict:
        resp = await self._stub.GetIncident(GetIncidentRequest(id=iid), timeout=self._timeout)
        return _GrpcShapes.incident(resp)

    async def acknowledge(self, iid: str) -> dict:
        resp = await self._stub.Acknowledge(AcknowledgeRequest(id=iid), timeout=self._timeout)
        return _GrpcShapes.acknowledge(resp)

    async def escalate(self, iid: str, note: str = "") -> dict:
        resp = await self._stub.Escalate(EscalateRequest(id=iid, note=note), timeout=self._timeout)
        return _GrpcShapes.escalate(resp)

    async def verify_call(self, call_id: str) -> dict:
        resp = await self._stub.VerifyCall(
            VerifyCallRequest(call_id=call_id), timeout=self._timeout
        )
        return _GrpcShapes.verify(resp)

    async def retry_anchor(self, call_id: str) -> dict:
        resp = await self._stub.RetryAnchor(
            RetryAnchorRequest(call_id=call_id), timeout=self._timeout
        )
        return _GrpcShapes.retry(resp)

    async def register_speaker(self, label: str, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        pcm = _audio_bytes(audio_path, audio_bytes, filename)
        if not pcm:
            raise ValueError("register_speaker(): provide audio_path or audio_bytes")
        resp = await self._stub.RegisterSpeaker(
            RegisterSpeakerRequest(audio=pcm, label=label, language=language),
            timeout=self._timeout,
        )
        return _GrpcShapes.register(resp)


__all__ = ["VoiceShieldGrpcClient", "VoiceShieldGrpcAioClient"]
