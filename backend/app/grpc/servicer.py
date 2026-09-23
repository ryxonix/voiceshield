"""
VoiceShield AI â€” gRPC Service Layer (A1)

Implements the `VoiceShield` Service from `backend/sdk/voiceshield.proto`
(external integration contract for SIH26104: "REST/gRPC APIs and SDKs for
integration with core banking systems, contact center platforms, enterprise
communication tools, and telecom networks").

Every RPC deliberately mirrors a FastAPI endpoint 1:1 so a bank / operator
gets byte-identical detection, incident, workflow, blockchain, and speaker
data over gRPC as over REST:

    Detect           <=>  POST /api/detect
    Analyze          <=>  POST /api/analyze          (contextual enrichment)
    ListIncidents    <=>  GET  /api/incidents
    GetIncident      <=>  GET  /api/incidents/{iid}
    Acknowledge      <=>  POST /api/incidents/{iid}/ack
    Escalate         <=>  POST /api/incidents/{iid}/escalate
    GetWorkflows     <=>  GET  /api/workflows
    VerifyCall       <=>  GET  /api/blockchain/verify/call/{call_id}
    RetryAnchor      <=>  POST /api/blockchain/retry/{call_id}
    RegisterSpeaker  <=>  POST /api/speakers/register

The servicer reuses the exact engine pipeline / risk bands / enrichment /
ledger / store modules used by the REST app â€” no duplicated scoring logic â€”
so a gRPC `Analyze` yields the same score, band, recommendation, and
recommended actions as a REST `Analyze` on the same 16 kHz PCM audio.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import grpc
from grpc import StatusCode as GrpcStatus

from app.grpc.voiceshield_pb2 import (
    AnalyzeRequest,
    AnalyzeResponse,
    DetectRequest,
    DetectResponse,
    GetIncidentRequest,
    ListIncidentsRequest,
    ListIncidentsResponse,
    GetWorkflowsRequest,
    GetWorkflowsResponse,
    Incident,
    AcknowledgeRequest,
    AcknowledgeResponse,
    EscalateRequest,
    EscalateResponse,
    RegisterSpeakerRequest,
    RegisterSpeakerResponse,
    RetryAnchorRequest,
    RetryAnchorResponse,
    VerifyCallRequest,
    VerifyCallResponse,
    WorkflowRule,
    ContextDetail,
)
from app.grpc.voiceshield_pb2_grpc import VoiceShieldServicer

logger = logging.getLogger("voiceshield.grpc")


# â”€â”€ PCM helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _pcm16_to_float(pcm: bytes) -> np.ndarray:
    """Decode 16-bit little-endian mono PCM @16 kHz â†’ float32 in [-1, 1].

    Matches the REST websocket stream path (np.frombuffer(int16)/32768),
    so a gRPC `Detect`/`Analyze` scores identically to a WS call.
    """
    raw = np.frombuffer(pcm, dtype="<i2")
    return raw.astype(np.float32) / 32768.0


def _windowed(audio_f32: np.ndarray, role: str = "adult", max_windows: int = 300, include_xlsr: bool = False):
    """Slide windowed frames and run the pipeline â€” mirrors main._process_windowed."""
    from app.engine.pipeline import analyze_window
    from app.engine.ring_buffer import RingBuffer

    # 16-bit PCM window expected by the ring buffer / dhwani path.
    int16 = np.clip(audio_f32, -1.0, 1.0) * 32767.0
    int16 = int16.astype(np.int16)

    try:
        from app.engine.dhwani import get_detector, MAX_SAMPLES

        dhwani_ready = get_detector().is_ready
    except Exception:
        dhwani_ready = False

    from app.config import settings
    

    if dhwani_ready:
        window_size = MAX_SAMPLES
        hop_size = settings.sample_rate  # 1 s hop
    else:
        window_size = settings.window_samples
        hop_size = settings.hop_samples

    if len(int16) < window_size:
        int16 = np.pad(int16, (0, window_size - len(int16)), mode="constant")

    ring = RingBuffer(window_size=window_size, hop_size=hop_size)
    frames = ring.push(int16)[:max_windows]
    step_ms = int(round(hop_size * 1000.0 / settings.sample_rate))

    windows = []
    peak = 0.0
    for idx, frame in enumerate(frames):
        ev = analyze_window(frame, role=role, include_xlsr=include_xlsr)
        score = float(ev["synthetic_score"])
        peak = max(peak, score)
        windows.append(
            {
                "t_ms": idx * step_ms,
                "synthetic_score": score,
                "model_prob": float(ev.get("model_prob", score)),
                "verdict": ev.get("verdict", ""),
            }
        )
    return windows, peak, len(windows)


def _json_field(raw) -> dict:
    import json

    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _risk(v: dict) -> Dict[str, Any]:
    """Bundle the risk helpers into one import so RPCs stay thin."""
    from app.engine.risk import risk_band, recommendation, recommended_actions

    return {
        "risk_band": risk_band,
        "recommendation": recommendation,
        "recommended_actions": recommended_actions,
    }


class VoiceShield(VoiceShieldServicer):
    """Concrete gRPC servicer â€” mirror of the FastAPI REST surface."""

    # â”€â”€ Detection (single shot, PCM16 bytes) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    def Detect(self, request: DetectRequest, context) -> DetectResponse:
        from app.engine.dhwani import get_detector

        detector = get_detector()
        if not detector.is_ready:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Detection model not loaded yet.")
            return DetectResponse(label="unknown", synthetic_score=0.5, confidence=0.5)

        try:
            # Exactly mirrors POST /api/detect: Dhwani single-shot over the
            # decoded float audio, so gRPC and REST agree byte-for-byte on
            # identical 16 kHz PCM (label, synthetic_score, confidence).
            audio = _pcm16_to_float(request.audio)
            result = detector.predict_array(audio, sr=16000)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Dhwani gRPC detection failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Dhwani inference failed: {e}")
            return DetectResponse(label="unknown", synthetic_score=0.5, confidence=0.5)

        return DetectResponse(
            label=str(result.get("label", "unknown")),
            synthetic_score=round(float(result.get("synthetic_score", 0.5)), 4),
            confidence=round(float(result.get("confidence", 0.5)), 4),
        )

    # â”€â”€ Analyze (sliding windows + contextual enrichment) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def Analyze(self, request: AnalyzeRequest, context) -> AnalyzeResponse:
        from app.context.enrichment import CallContext, enrich_score
        from app.engine.risk import risk_band, recommendation, recommended_actions

        role = request.role or "adult"
        audio = _pcm16_to_float(request.audio)
        # include_xlsr=True mirrors POST /api/analyze (main._process_windowed),
        # so REST and gRPC Analyze yield identical windows on identical PCM.
        windows, peak, count = _windowed(audio, role=role, include_xlsr=True)

        ctx = CallContext.from_mapping(
            {
                "caller": request.caller or "",
                "origin": request.origin or "",
                "txn_value": request.txn_value or 0.0,
                "txn_category": request.txn_category or "",
                # proto3 bool has no presence: True => explicit override,
                # False/default => unset => auto-check (matches REST "" form).
                "known_contact": True if request.known_contact else None,
                "prior_flags": request.prior_flags if request.prior_flags > 0 else None,
            }
        )
        adjusted, detail = enrich_score(peak, ctx, role=role)

        band = risk_band(adjusted, role)
        detail_enabled = bool(detail.get("enabled", False))
        detail_applied = bool(detail.get("applied", False))

        return AnalyzeResponse(
            peak_score=round(float(adjusted), 4),
            risk_band=str(band),
            windows_analyzed=int(count),
            recommendation=str(recommendation(band, role)),
            recommended_actions=recommended_actions(band, role),
            context=ContextDetail(
                enabled=detail_enabled,
                applied=detail_applied,
                signals={str(k): str(v) for k, v in (detail.get("signals") or {}).items()},
                modifiers={str(k): round(float(v), 6) for k, v in (detail.get("modifiers") or {}).items()},
                base_score=round(float(detail.get("base_score") or peak), 4),
                adjusted_score=round(float(detail.get("adjusted_score") or adjusted), 4),
            ),
        )

    # â”€â”€ Incidents â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€  â•â•â•â•
    def _incident(self, i: Dict[str, Any]) -> Incident:
        trg = i.get("triggers") or "[]"
        if isinstance(trg, str):
            import json
            try:
                trg = json.loads(trg)
            except Exception:
                trg = []
        ctx = _json_field(i.get("context_json"))
        return Incident(
            id=str(i["id"]),
            session_id=str(i.get("session_id") or ""),
            role=str(i.get("role") or "adult"),
            severity=str(i["severity"]),
            score=round(float(i["score"]), 4),
            base_score=round(float(i.get("base_score") or i["score"]), 4),
            context=ContextDetail(
                enabled=bool(ctx.get("enabled", False)),
                applied=bool(ctx.get("applied", False)),
                signals={str(k): str(v) for k, v in (ctx.get("signals") or {}).items()},
                modifiers={str(k): round(float(v), 6) for k, v in (ctx.get("modifiers") or {}).items()},
                base_score=round(float(ctx.get("base_score") or i["score"]), 4),
                adjusted_score=round(float(ctx.get("adjusted_score") or i["score"]), 4),
            ),
            triggers=[str(t) for t in trg],
            speaker_mismatch=bool(i.get("speaker_mismatch", False)),
            acknowledged=bool(i.get("acknowledged", False)),
            created_at=str(i.get("created_at") or ""),
        )

    def ListIncidents(self, request: ListIncidentsRequest, context) -> ListIncidentsResponse:
        from app import store
        limit = request.limit if request.limit > 0 else 50
        return ListIncidentsResponse(incidents=[self._incident(i) for i in store.list_incidents(limit)])

    def GetIncident(self, request: GetIncidentRequest, context) -> Incident:
        from app import store
        i = store.get_incident(request.id)
        if i is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"No incident with id '{request.id}'")
            return Incident(id=request.id)
        return self._incident(i)

    def Acknowledge(self, request: AcknowledgeRequest, context) -> AcknowledgeResponse:
        from app import store
        i = store.get_incident(request.id)
        if i is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"No incident with id '{request.id}'")
            return AcknowledgeResponse(ok=False, id=request.id)
        store.ack_incident(request.id)
        return AcknowledgeResponse(ok=True, id=request.id)

    def Escalate(self, request: EscalateRequest, context) -> EscalateResponse:
        from app import store
        i = store.get_incident(request.id)
        if i is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"No incident with id '{request.id}'")
            return EscalateResponse(ok=False, id=request.id, escalated=False, caller_flag_count=0)
        ctx = _json_field(i.get("context_json"))
        caller = (ctx.get("caller") if isinstance(ctx, dict) else None) or ""
        flag_count = store.bump_caller_flags(caller) if caller else 0
        store.escalate_incident(request.id, request.note or "")
        return EscalateResponse(
            ok=True,
            id=request.id,
            escalated=True,
            caller_flag_count=int(flag_count),
        )

    # â”€â”€ Workflows (opt-in config) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def GetWorkflows(self, request: GetWorkflowsRequest, context) -> GetWorkflowsResponse:
        from app.mitigation.workflows import get_workflow_config, _default_path
        cfg = get_workflow_config()
        rules = cfg.get("rules") or []
        return GetWorkflowsResponse(
            version=int(cfg.get("version") or 1),
            rules=[
                WorkflowRule(
                    role=str(r.get("role") or "adult"),
                    band_min=str(r.get("band_min") or "low"),
                    actions=[str(a) for a in (r.get("actions") or [])],
                    channels=[str(c) for c in (r.get("channels") or [])],
                )
                for r in rules
            ],
            active_path=str(cfg.get("active_path") or _default_path()),
        )

    # â”€â”€ Blockchain verification â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€  â•â•â•â•
    def VerifyCall(self, request: VerifyCallRequest, context) -> VerifyCallResponse:
        from app.blockchain.ledger import verify_report
        from app import store

        block = store.get_block_by_call(request.call_id)
        if block is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"No blockchain anchor for call '{request.call_id}'.")
            return VerifyCallResponse(valid=False)

        rep = verify_report(request.call_id)
        problems = [str(p) for p in (rep.get("problems") or [])]
        ext = rep.get("external_anchor") or {}
        return VerifyCallResponse(
            valid=bool(rep.get("valid") and not problems),
            anchor_status=str(ext.get("anchor_status") or rep.get("anchor_status") or ""),
            ipfs_cid=str(ext.get("ipfs_cid") or ext.get("ipfs_cid") or ""),
            tx_id=str(ext.get("tx_id") or ""),
            problems=problems,
        )

    def RetryAnchor(self, request: RetryAnchorRequest, context) -> RetryAnchorResponse:
        from app import store
        from app.blockchain.external_anchor import retry_anchor

        block = store.get_block_by_call(request.call_id)
        if block is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"No block for call '{request.call_id}'. Generate a report first.")
            return RetryAnchorResponse(result={})

        result = retry_anchor(block) or {}
        return RetryAnchorResponse(result={str(k): str(v) for k, v in result.items()})

    # â”€â”€ Speaker enrollment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ï¿½â”€
    def RegisterSpeaker(self, request: RegisterSpeakerRequest, context) -> RegisterSpeakerResponse:
        from app.engine.speaker import extract_embedding, embedding_to_bytes
        from app import store

        audio = _pcm16_to_float(request.audio)
        if audio.size < 8000:  # < 0.5 s @16 kHz
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Speaker sample too short â€” record at least 0.5s of speech.")
            return RegisterSpeakerResponse(ok=False, label=request.label, dim=0)

        emb = extract_embedding(audio, sr=16000)
        store.register_speaker(request.label.strip(), request.language or "auto", embedding_to_bytes(emb))
        logger.info(f"Speaker enrolled via gRPC: {request.label} ({request.language or 'auto'})")
        return RegisterSpeakerResponse(
            ok=True,
            label=request.label.strip(),
            dim=int(emb.size if hasattr(emb, "size") else len(emb)),
        )


# â”€â”€ Servicer registration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def register(server) -> None:
    """Attach the VoiceShield servicer to a grpc.aio.Server (adds handlers)."""
    from app.grpc.voiceshield_pb2_grpc import add_VoiceShieldServicer_to_server

    add_VoiceShieldServicer_to_server(VoiceShield(), server)
    logger.info("VoiceShield gRPC servicer registered on this server.")

