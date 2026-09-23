"""
VoiceShield AI — FastAPI Application Entry Point

Zero-trust, real-time audio deepfake detection and mitigation platform
optimized for the Indian telecom context.

All external services are 100% free or free-tier for .edu.in students.
"""

import io
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, UploadFile, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from app.config import settings

# Ensure the local telemetry store exists even before the lifespan runs.
from app import store as _store
_store.init_db()

# ── Logging Setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("voiceshield")


# ── Lifespan: startup / shutdown ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — initializes and cleans up resources."""
    logger.info("═" * 60)
    logger.info("  VoiceShield AI — Starting Up")
    logger.info("═" * 60)

    # Initialize local persistence (SQLite telemetry)
    from app import store
    store.init_db()

    # Load Dhwani ONNX model (Indian multilingual deepfake detector)
    try:
        from app.engine.dhwani import get_detector
        detector = get_detector()
        if detector.is_ready:
            logger.info("Dhwani ONNX model loaded — Indian voice deepfake detection READY")
        else:
            logger.warning("Dhwani model not ready — check models/dhwani/best_model.onnx")
    except Exception as e:
        logger.warning(f"Dhwani model not loaded: {e}")

    # Also attempt to load legacy AASIST ONNX session
    try:
        from app.models.inference import AASISTInference
        AASISTInference.get_instance()
        logger.info(f"AASIST ONNX model loaded: {settings.onnx_model_path}")
    except Exception as e:
        logger.warning(f"AASIST ONNX model not loaded (using Dhwani only): {e}")

    # Initialize Sentry error monitoring
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=1.0,
            )
            logger.info("Sentry error tracking initialized successfully.")
        except Exception as e:
            logger.warning(f"Sentry initialization skipped: {e}")

    # Initialize Resend Email API
    if settings.resend_api_key:
        try:
            import resend
            resend.api_key = settings.resend_api_key
            logger.info("Resend Email API initialized successfully.")
        except Exception as e:
            logger.warning(f"Resend initialization skipped: {e}")

    # Log configured alert channels
    channels = []
    if settings.telegram_bot_token:
        channels.append("Telegram")
    if settings.smtp_user:
        channels.append("Email/SMTP")
    if settings.resend_api_key:
        channels.append("Resend Email")
    if settings.ntfy_topic:
        channels.append(f"ntfy.sh/{settings.ntfy_topic}")
    if settings.fast2sms_api_key:
        channels.append("Fast2SMS")
    if settings.webhook_url:
        channels.append("Webhook")
    if settings.database_url:
        channels.append("Neon PostgreSQL")
    logger.info(f"  Alert channels & Services: {channels or ['None configured']}")
    logger.info(f"  Thresholds: adult={settings.adult_threshold}, child={settings.child_threshold}")

    # Start the external gRPC service alongside the REST app so bank /
    # contact-center / telecom integrations get the same VoiceShield surface
    # on settings.grpc_port (default 50051) without running a second process.
    # Graceful: if the port is already in use (a standalone `python -m
    # app.grpc.server` is running), the app logs the fact and continues.
    grpc_server = None
    try:
        from app.grpc import server as grpc_server_module

        grpc_server = grpc_server_module.create_server()
        if getattr(grpc_server, "_vs_bound", 0):
            await grpc_server.start()
            logger.info(f"gRPC VoiceShield service started on :{settings.grpc_port}")
        else:
            grpc_server = None
    except Exception as e:  # noqa: BLE001 - never crash REST because of gRPC
        logger.warning(f"gRPC service not started: {e}")
        grpc_server = None

    logger.info("═" * 60)

    yield  # ── Application runs here ──

    # Cleanup
    logger.info("VoiceShield AI — Shutting down. Wiping all session buffers.")
    try:
        from app.engine.session import session_manager
        await session_manager.destroy_all()
    except Exception:
        pass
    if grpc_server is not None:
        try:
            from app.grpc import server as grpc_server_module
            await grpc_server_module.stop(grpc_server)
        except Exception:  # noqa: BLE001
            pass
    logger.info("Shutdown complete.")


# ── FastAPI App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="VoiceShield AI",
    description=(
        "Zero-trust, real-time audio deepfake detection and mitigation "
        "platform optimized for the Indian telecom context. "
        "All services are free / free-tier for .edu.in students."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Serialization helpers ──────────────────────────────────────────────────
def _serialize_session(s: dict) -> dict:
    return {
        "id": s["call_id"],
        "call_id": s["call_id"],
        "role": s["role"],
        "language": s["language"],
        "window_count": int(s["window_count"]),
        "max_score": round(float(s["max_score"]), 4),
        "avg_score": round(float(s["avg_score"]), 4),
        "average_score": round(float(s["avg_score"]), 4),
        "last_score": round(float(s["last_score"]), 4),
        "enterprise_verified": bool(s["enterprise_verified"]),
        "status": s["status"],
        "started_at": s["started_at"],
        "ended_at": s["ended_at"],
        "caller": s.get("caller") or "",
        "origin": s.get("origin") or "",
        "txn_value": round(float(s.get("txn_value") or 0.0), 2),
        "context": _json_field(s.get("context_json")),
    }


def _serialize_incident(i: dict) -> dict:
    triggers = i.get("triggers") or "[]"
    if isinstance(triggers, str):
        try:
            triggers = json.loads(triggers)
        except Exception:
            triggers = []
    return {
        "id": i["id"],
        "session_id": i.get("session_id"),
        "role": i.get("role", "adult"),
        "language": i.get("language", "auto"),
        "severity": i["severity"],
        "score": round(float(i["score"]), 4),
        "base_score": round(float(i.get("base_score") or i["score"]), 4),
        "context": _json_field(i.get("context_json")),
        "triggers": triggers,
        "speaker_mismatch": bool(i["speaker_mismatch"]),
        "created_at": i["created_at"],
        "acknowledged": bool(i["acknowledged"]),
        "report_path": i.get("report_path"),
    }


def _json_field(raw) -> dict:
    """Best-effort decode of a stored JSON text column."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ── Audio decoding helpers ─────────────────────────────────────────────────
def _decode_audio_bytes(data: bytes) -> np.ndarray:
    """Decode uploaded audio bytes to mono float32 at the pipeline sample rate.

    Accepts both WAV containers (soundfile) and — for byte-parity with the
    engine hot loop and the gRPC detect surface, which the SDK promises are
    identical on identical PCM windows (`sdk/voiceshield_sdk/grpc.py:9-13`) —
    raw 16-bit mono PCM at the pipeline sample rate (no container, no header).
    """
    import soundfile as sf
    import librosa

    if not data.startswith(b"RIFF"):
        pcm16 = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        return np.clip(pcm16, -1.0, 1.0)

    audio, file_sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    audio = audio[:, 0]
    if file_sr != settings.sample_rate:
        audio = librosa.resample(
            audio, orig_sr=file_sr, target_sr=settings.sample_rate
        )
    return np.clip(audio, -1.0, 1.0)


def _process_windowed(audio_float: np.ndarray, role: str = "adult", max_windows: int = 300):
    """
    Slide overlapping windows over the audio and run the detection pipeline.

    Uses 3-second / 1-second-hop windows when Dhwani (trained) is available;
    otherwise falls back to 300 ms / 100 ms hop for the legacy AASIST-L path.

    Returns (windows, peak_score, count).
    """
    from app.engine.ring_buffer import RingBuffer
    from app.engine.pipeline import analyze_window

    int16 = (np.clip(audio_float, -1.0, 1.0) * 32767.0).astype(np.int16)

    # Choose window size matching the active model's expectation
    try:
        from app.engine.dhwani import get_detector, MAX_SAMPLES
        dhwani_ready = get_detector().is_ready
    except Exception:  # noqa: BLE001
        dhwani_ready = False

    if dhwani_ready:
        window_size = MAX_SAMPLES
        hop_size = int(settings.sample_rate)      # 1 s
    else:
        window_size = settings.window_samples      # 4800
        hop_size = settings.hop_samples            # 1600

    ring = RingBuffer(window_size=window_size, hop_size=hop_size)
    if len(int16) < window_size:
        # Pad short clips (e.g. < 3 s) so at least one full window is produced.
        int16 = np.pad(int16, (0, window_size - len(int16)), mode="constant")
    frames = ring.push(int16)[:max_windows]
    step_ms = int(round(hop_size * 1000.0 / settings.sample_rate))
    windows = []
    peak = 0.0

    for idx, frame in enumerate(frames):
        # Forensic file-analysis path ALWAYS uses the full ensemble, regardless
        # of latency_profile; the real-time profile is for live streaming only.
        ev = analyze_window(frame, role=role, include_xlsr=True, realtime=False)
        t_ms = idx * step_ms
        peak = max(peak, ev["synthetic_score"])
        windows.append(
            {
                "t_ms": t_ms,
                "synthetic_score": ev["synthetic_score"],
                "model_prob": ev["model_prob"],
                "xai_risk": ev["xai_risk"],
                "jitter_pct": ev["prosody"]["jitter_pct"],
                "shimmer_pct": ev["prosody"]["shimmer_pct"],
                "phase_continuity": ev["prosody"]["phase_continuity"],
                "pitch_stability": ev["prosody"]["pitch_stability"],
                "noise_floor_dropouts": ev["prosody"]["noise_floor_dropouts"],
                "watermark_hit": ev["watermark_hit"],
                "verdict": ev["verdict"],
            }
        )

    return windows, peak, len(windows)


def _session_data_from_store(call_id: str) -> dict | None:
    """Build forensic-PDF session_data from persisted telemetry."""
    from app import store

    sess = store.get_session(call_id)
    if sess is None:
        return None
    windows = store.get_windows(call_id)
    history = [
        {
            "window_index": i,
            "synthetic_score": w["synthetic_score"],
            "timestamp": None,
        }
        for i, w in enumerate(windows)
    ]
    return {
        "call_id": call_id,
        "role": sess.get("role", "adult"),
        "start_time": sess.get("started_at"),
        "end_time": sess.get("ended_at"),
        "peak_score": float(sess.get("max_score", 0.0)),
        "peak_prosodics": _peak_window_prosodics(windows),
        "action_taken": "ALERT_DISPATCHED" if sess.get("max_score", 0.0) >= 0.7 else "MONITORING",
        "history": history,
    }


def _peak_window_prosodics(windows: list) -> dict:
    if not windows:
        return {}
    peak = max(windows, key=lambda w: w["synthetic_score"])
    return {
        "jitter_pct": peak.get("jitter_pct", 0.0),
        "shimmer_pct": peak.get("shimmer_pct", 0.0),
        "phase_continuity": peak.get("phase_continuity", 1.0),
        "pitch_stability_pct": peak.get("pitch_stability", 100.0),
    }


# ── Health Check ───────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "VoiceShield AI",
        "version": "1.0.0",
    }


# ── System Info ────────────────────────────────────────────────────────────
@app.get("/info", tags=["system"])
async def system_info():
    """Returns system configuration (non-sensitive)."""
    return {
        "model": settings.onnx_model_path,
        "threads": settings.onnx_threads,
        "thresholds": {
            "adult": settings.adult_threshold,
            "child": settings.child_threshold,
        },
        "audio": {
            "sample_rate": settings.sample_rate,
            "window_ms": settings.window_samples / settings.sample_rate * 1000,
            "hop_ms": settings.hop_samples / settings.sample_rate * 1000,
        },
        "latency_budget_ms": settings.latency_budget_ms,
    }


# ── Detect Endpoint (Dhwani Indian Voice Deepfake Detection) ─────────────
@app.post("/api/detect", tags=["detection"])
async def detect_audio(
    file: UploadFile | None = File(None),
    language: str = "auto",
):
    """
    Detect if an uploaded audio file is bonafide (real) or spoof (AI-generated).

    - **file**: WAV/FLAC/MP3 audio file (max 3 seconds, 16 kHz recommended)
    - **language**: hint for logging only — model auto-detects (hindi/kannada/english)

    Returns: label, synthetic_score (0=bonafide, 1=spoof), confidence
    """
    from app.engine.dhwani import get_detector

    if file is None:
        return JSONResponse(status_code=422, content={"error": "No audio file provided."})

    detector = get_detector()
    if not detector.is_ready:
        return JSONResponse(status_code=503, content={"error": "Detection model not loaded yet."})

    try:
        contents = await file.read()
        try:
            # Container formats (wav/flac/mp3/ogg): same decode predict_file used.
            import soundfile as sf
            audio, file_sr = sf.read(io.BytesIO(contents), dtype="float32")
        except Exception:
            # Raw 16-bit mono PCM @16 kHz (no header) — the SDK's byte-parity
            # promise (sdk/voiceshield_sdk/grpc.py). No temp files (DPDP).
            audio = _decode_audio_bytes(contents)
            file_sr = settings.sample_rate
        result = detector.predict_array(audio, file_sr)

        result["language_hint"] = language
        result["filename"] = file.filename
        return result
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── File Analyzer (sliding-window deep analysis) ──────────────────────────
@app.post("/api/analyze", tags=["detection"])
async def analyze_file(
    file: UploadFile | None = File(None),
    role: str = Query("adult"),
    caller: str = Form(""),
    origin: str = Form(""),
    txn_value: float = Form(0.0),
    txn_category: str = Form(""),
    known_contact: str = Form(""),
    prior_flags: int = Form(0),
):
    """
    Run the full sliding-window pipeline on an uploaded file.

    Returns peak score, risk band, per-window table, and a recommendation.
    Optional form fields feed contextual enrichment (opt-in, see settings):
    caller, origin, txn_value, txn_category, known_contact ("", "true", "false"),
    prior_flags.
    """
    from app.engine.risk import risk_band, recommendation, recommended_actions
    from app.context.enrichment import CallContext, enrich_score

    if file is None:
        return JSONResponse(status_code=422, content={"error": "No audio file provided."})

    try:
        contents = await file.read()
        t0 = time.perf_counter()
        audio = _decode_audio_bytes(contents)
        windows, peak, count = _process_windowed(audio, role=role)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            f"Analyze: {file.filename} role={role} windows={count} "
            f"peak={peak:.4f} in {elapsed:.0f}ms"
        )
        band = risk_band(peak, role)

        # Contextual enrichment (opt-in; fails open to unchanged when disabled)
        kc = None if known_contact.strip() == "" else known_contact.strip().lower() == "true"
        ctx = CallContext.from_mapping(
            {
                "caller": caller,
                "origin": origin,
                "txn_value": txn_value,
                "txn_category": txn_category,
                "known_contact": kc,
                "prior_flags": prior_flags if prior_flags > 0 else None,
            }
        )
        ctx_score, ctx_detail = enrich_score(peak, ctx, role)
        ctx_band = risk_band(ctx_score, role)

        return {
            "peak_score": round(ctx_score, 4),
            "risk_band": ctx_band,
            "windows_analyzed": count,
            "recommendation": recommendation(ctx_band, role),
            "recommended_actions": recommended_actions(ctx_band, role),
            "context": ctx_detail if ctx.provided else None,
            "windows": windows,
        }
    except Exception as e:
        logger.error(f"Analyze failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Sessions (dashboard + forensics) ──────────────────────────────────────
@app.get("/api/sessions", tags=["dashboard"])
async def list_sessions(limit: int = Query(50)):
    """List persisted detection sessions (newest first)."""
    from app import store
    return [_serialize_session(s) for s in store.list_sessions(limit)]


@app.get("/api/sessions/{sid}", tags=["dashboard"])
async def get_session_detail(sid: str):
    """Get a single session detail."""
    from app import store
    sess = store.get_session(sid)
    if sess is None:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return _serialize_session(sess)


@app.get("/api/sessions/{sid}/windows", tags=["dashboard"])
async def get_session_windows(sid: str):
    """Get the per-window analysis table for a session (newest last)."""
    from app import store
    if store.get_session(sid) is None:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return store.get_windows(sid)


# ── Incidents ──────────────────────────────────────────────────────────────
@app.get("/api/incidents", tags=["incidents"])
async def list_incidents(limit: int = Query(50)):
    """List detection incidents (newest first)."""
    from app import store
    return [_serialize_incident(i) for i in store.list_incidents(limit)]


@app.get("/api/incidents/{iid}", tags=["incidents"])
async def get_incident_detail(iid: str):
    """Get a single incident detail."""
    from app import store
    inc = store.get_incident(iid)
    if inc is None:
        return JSONResponse(status_code=404, content={"error": "Incident not found"})
    return _serialize_incident(inc)


@app.post("/api/incidents/{iid}/ack", tags=["incidents"])
async def ack_incident(iid: str):
    """Acknowledge an incident (marks it handled)."""
    from app import store
    if store.get_incident(iid) is None:
        return JSONResponse(status_code=404, content={"error": "Incident not found"})
    store.ack_incident(iid)
    return {"ok": True, "id": iid, "acknowledged": True}


@app.post("/api/incidents/{iid}/escalate", tags=["incidents"])
async def escalate_incident(iid: str, note: str = Form("")):
    """
    Escalate a confirmed-fraud incident: record the caller in the reputation
    ledger and re-fire the escalation webhook (e.g. DoT DIP / operator receiver)
    with escalation=true. SOP prompts (call-back / MFA) are operator actions;
    this endpoint handles the supervisor-escalation leg concretely.
    """
    from app import store
    from app.mitigation.alerts import _send_with_retry

    inc = store.get_incident(iid)
    if inc is None:
        return JSONResponse(status_code=404, content={"error": "Incident not found"})

    ctx = _json_field(inc.get("context_json"))
    caller = (ctx.get("caller") if isinstance(ctx, dict) else None) or ""
    flag_count = store.bump_caller_flags(caller) if caller else 0

    targets = [u for u in (settings.webhook_url, settings.chakshu_dip_webhook_url) if u]
    payload = {
        "channel": "incident_escalation",
        "flow": "escalated_fraud",
        "incident_id": iid,
        "call_id": inc.get("session_id"),
        "note": note,
        "escalation": "Operator-level escalation — supervisor review required",
        "caller_flag_count": flag_count,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S IST"),
    }
    for url in targets:
        await _send_with_retry("EscalationWebhook", url, json_payload=payload)

    return {
        "ok": True,
        "id": iid,
        "escalated": True,
        "webhooks": len(targets),
        "caller_flag_count": flag_count,
    }


@app.get("/api/workflows", tags=["incidents"])
async def get_workflows():
    """Return the active mitigation workflow configuration (editable JSON)."""
    from app.mitigation.workflows import get_workflow_config, _default_path
    cfg = get_workflow_config()
    cfg["active_path"] = _default_path() if settings.workflows_path else "bundled_defaults"
    return cfg


@app.get("/api/incidents/{iid}/report", tags=["incidents", "forensics"])
async def generate_incident_report(iid: str):
    """Generate and download an I4C-ready forensic incident PDF report."""
    from app import store
    from app.forensics.pdf_report import generate_forensic_pdf

    inc = store.get_incident(iid)
    if inc is None:
        return JSONResponse(status_code=404, content={"error": "Incident not found"})

    call_id = inc.get("session_id") or inc["id"]
    session_data = _session_data_from_store(call_id)
    if session_data is None:
        session_data = {
            "call_id": call_id,
            "role": inc.get("role", "adult"),
            "start_time": inc.get("created_at"),
            "end_time": None,
            "peak_score": float(inc.get("score", 0.0)),
            "peak_prosodics": {},
            "action_taken": "ALERT_DISPATCHED",
            "history": [],
        }
    session_data["incident_id"] = iid
    session_data["severity"] = inc.get("severity", "high")
    session_data["triggers"] = _serialize_incident(inc).get("triggers", [])
    session_data["speaker_mismatch"] = _serialize_incident(inc).get("speaker_mismatch", False)

    reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    saved_pdf_path = os.path.join(reports_dir, f"VoiceShield_Incident_{iid}.pdf")

    try:
        from app.blockchain import ledger
        from app.blockchain.ledger import CHAIN_ID
        from app.blockchain.external_anchor import BlockAnchorError
        generate_forensic_pdf(
            session_data,
            saved_pdf_path,
            blockchain={"chain_id": CHAIN_ID, "call_id": call_id},
        )

        # Anchor the incident PDF to the tamper-evident ledger.
        windows = store.get_windows(call_id)
        leaves = sorted(f"{w['t_ms']}:{w['synthetic_score']}" for w in windows)
        block = ledger.anchor_report(
            call_id=call_id,
            report_id=f"INCIDENT-{iid}",
            incident_id=iid,
            file_path=saved_pdf_path,
            window_leaves=leaves,
        )
        store.set_incident_report_path(iid, saved_pdf_path)
        logger.info(f"Incident report saved + anchored to blockchain: #{block['block_index']} {saved_pdf_path}")
        return FileResponse(
            path=saved_pdf_path,
            filename=f"VoiceShield_Incident_{iid}.pdf",
            media_type="application/pdf",
        )
    except BlockAnchorError as e:
        # Mandatory mode (BLOCKCHAIN_ANCHOR_REQUIRED=true): no anchor, no hand-off.
        logger.error(f"Blockchain anchor refused for incident {iid}: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "error": f"Report NOT blockchain-anchored: {e}",
                "detail": "BLOCKCHAIN_ANCHOR_REQUIRED=true — unanchored evidence is refused for forensic hand-off. On-chain anchoring failed; the report was not committed to the ledger.",
            },
        )
    except Exception as e:
        logger.error(f"PDF generation failed for {iid}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate forensic report: {str(e)}"},
        )


# ── Blockchain Report Ledger ───────────────────────────────────────────────
@app.get("/api/blockchain", tags=["blockchain"])
async def blockchain_status():
    """Ledger summary — chain height, difficulty, genesis/latest hashes."""
    from app import store
    from app.blockchain import ledger
    chain = ledger.verify_chain()
    return {
        "chain_id": chain["chain_id"],
        "height": chain["height"],
        "difficulty": chain["difficulty"],
        "valid": chain["valid"],
        "genesis": chain["genesis"],
        "latest": chain["latest"],
        "blocks": [
            {
                "block_index": b["block_index"],
                "call_id": b["call_id"],
                "report_id": b["report_id"],
                "incident_id": b.get("incident_id"),
                "block_hash": b["block_hash"],
                "prev_hash": b["prev_hash"],
                "file_sha256": b["file_sha256"],
                "merkle_root": b["merkle_root"],
                "timestamp": b["timestamp"],
                "nonce": b["nonce"],
                "external_anchor": _anchor_summary(b["block_index"]),
            }
            for b in store.list_blocks()
        ],
        "external_anchor": _anchor_summary(None),
    }


# NOTE: the two /api/blockchain/onchain routes MUST be declared before
# /api/blockchain/{index}, otherwise the literal "onchain" path is captured by
# the int index route and FastAPI returns a 422 instead of reaching them.

@app.get("/api/blockchain/onchain/{call_id}", tags=["blockchain"])
async def blockchain_onchain_call(call_id: str):
    """Live NBF-Fabric + IPFS verification for a report's external anchor.

    Queries the chaincode record for the call, compares it to the local
    PoW block, retrieves the pinned ciphertext from IPFS, decrypts it with
    the org-derived report key, and confirms the decrypted document matches
    the anchored SHA-256 (and looks like a PDF). Fail-open: local chain is
    authoritative; any unreachable service is reported, not fatal.
    """
    from app.blockchain import external_anchor

    return external_anchor.verify_anchor(call_id)


@app.get("/api/blockchain/onchain", tags=["blockchain"])
async def blockchain_onchain():
    """External-anchor status for every locally-mined report block.

    `verifiable` lists calls whose anchors are 'anchored' (a Fabric node is
    reachable), `pending_demo` the offline demo/pending rows, so operators can
    see at a glance which reports have a public, cross-verifiable anchor.
    """
    from app import store
    from app.blockchain import external_anchor

    anchors = {r["block_index"]: r for r in _store_fetch_anchors()}

    verifiable = []
    pending_demo = []
    for b in store.list_blocks():
        summary = anchors.get(b["block_index"], {})
        status = summary.get("anchor_status", "not_anchored")
        row = {
            "call_id": b["call_id"],
            "block_index": b["block_index"],
            "block_hash": b["block_hash"],
            "file_sha256": b["file_sha256"],
            "anchor_status": status,
            "provider": summary.get("provider"),
            "ipfs_cid": summary.get("ipfs_cid"),
            "tx_id": summary.get("tx_id"),
        }
        if status == "anchored":
            verifiable.append(row)
        elif status in ("pending", "demo", "not_anchored"):
            pending_demo.append(row)
    return {
        "gateway_url": external_anchor._gateway_base() or None,
        "external_anchor": _anchor_summary(None),
        "verifiable": verifiable,
        "pending_demo": pending_demo,
    }


@app.get("/api/blockchain/{index}", tags=["blockchain"])
async def blockchain_block(index: int):
    """Fetch a single block by its chain index."""
    from app import store
    block = store.get_block(index)
    if block is None:
        return JSONResponse(status_code=404, content={"error": f"No block at index {index}"})
    return block


@app.get("/api/blockchain/verify/call/{call_id}", tags=["blockchain"])
async def blockchain_verify_call(call_id: str):
    """Full tamper-evidence check for a report: file hash + block identity + chain linkage."""
    from app.blockchain import ledger
    return ledger.verify_report(call_id)


@app.get("/api/blockchain/verify/block/{index}", tags=["blockchain"])
async def blockchain_verify_block(index: int):
    """Chain + PoW integrity check for a single block."""
    from app import store
    from app.blockchain import ledger
    block = store.get_block(index)
    if block is None:
        return JSONResponse(status_code=404, content={"error": f"No block at index {index}"})
    problems = []
    if ledger._recompute_block_hash(block) != block["block_hash"]:
        problems.append("block hash does not match fields")
    # Genesis (index 0) is the trusted root and is mined with difficulty 0,
    # so proof-of-work is only enforced on blocks 1+.
    if index != 0 and not ledger._check_pow(block):
        problems.append("proof-of-work difficulty not met")
    chain = ledger.verify_chain()
    if not chain["valid"]:
        problems.append("ledger integrity check failed")
    return {
        "valid": not problems,
        "block_index": index,
        "chain_height": chain["height"],
        "problems": problems,
        "block": block,
    }


# ---- External anchor helpers (NBF-Lite / Fabric) ------------------------

def _anchor_summary(block_index: Optional[int] = None) -> dict:
    """Collapse persisted external-anchor state for a block or the whole chain."""
    try:
        if block_index is None:
            rows = _store_fetch_anchors()
            statuses = [r.get("anchor_status", "pending") for r in rows]
            return {
                "enabled": _store_anchor_enabled(),
                "count": len(rows),
                "anchored": statuses.count("anchored"),
                "demo": statuses.count("demo"),
                "pending": statuses.count("pending"),
            }
        row = _store.get_block_anchor(block_index)
        if row is None:
            return {"anchor_status": "not_anchored", "provider": None, "ipfs_cid": None}
        return {
            "anchor_status": row.get("anchor_status"),
            "provider": row.get("provider"),
            "ipfs_cid": row.get("ipfs_cid"),
            "key_fp": row.get("key_fp"),
            "tx_id": row.get("tx_id"),
            "error": row.get("error"),
        }
    except Exception as e:  # pragma: no cover - defensive
        return {"anchor_status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def _store_fetch_anchors():
    import sqlite3

    conn = _store._connect()
    try:
        rows = conn.execute(
            "SELECT block_index, call_id, anchor_status, provider, ipfs_cid, tx_id, error "
            "FROM block_anchors"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _store_anchor_enabled() -> bool:
    from app.blockchain.external_anchor import get_provider

    try:
        return get_provider().name != "demo"
    except Exception:
        return False


@app.post("/api/blockchain/retry/{call_id}", tags=["blockchain"])
async def blockchain_retry_anchor(call_id: str):
    """Re-attempt the external Fabric/IPFS anchor for a pending report block."""
    from app.blockchain import external_anchor, ledger
    from app.blockchain.external_anchor import BlockAnchorError

    block = _store.get_block_by_call(call_id)
    if block is None:
        return JSONResponse(status_code=404, content={"error": f"No block found for call '{call_id}'. Generate a report first."})
    provider = external_anchor.get_provider()
    if not settings.blockchain_anchor_required and provider.name == "demo":
        return JSONResponse(status_code=400, content={"error": "External anchor disabled (BLOCKCHAIN_EXTERNAL_ANCHOR=false)."})
    try:
        result = external_anchor.retry_anchor(block)
    except BlockAnchorError as e:
        logger.error(f"Retry anchor failed for {call_id}: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "error": f"Anchor retry failed — still not blockchain-anchored: {e}",
                "detail": "BLOCKCHAIN_ANCHOR_REQUIRED=true — the anchor did not succeed on-chain. The block stays unanchored; re-run once the NBF gateway/provider is healthy.",
            },
        )
    return result


# ── Speaker Enrollment ─────────────────────────────────────────────────────
@app.post("/api/speakers/register", tags=["speakers"])
async def register_speaker(
    file: UploadFile | None = File(None),
    label: str = Query("unknown"),
    language: str = Query("auto"),
):
    """
    Enroll a speaker voice-print for cross-session identity checks.

    Stores only a deterministic, one-way embedding vector (DPDP compliant).
    """
    from app import store
    from app.engine.speaker import extract_embedding, embedding_to_bytes

    if file is None:
        return JSONResponse(status_code=422, content={"error": "No audio file provided.", "detail": "No audio file provided."})
    if not label or not label.strip():
        return JSONResponse(status_code=422, content={"error": "A non-empty speaker label is required.", "detail": "A non-empty speaker label is required."})

    try:
        contents = await file.read()
        audio = _decode_audio_bytes(contents)
        if audio.size < settings.sample_rate // 2:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Speaker sample too short — record at least 0.5s of speech.",
                    "detail": "Speaker sample too short — record at least 0.5s of speech.",
                },
            )
        emb = extract_embedding(audio, sr=settings.sample_rate)
        store.register_speaker(label.strip(), language or "auto", embedding_to_bytes(emb))
        logger.info(f"Speaker enrolled: {label} ({language}), dim={emb.size}")
        return {
            "ok": True,
            "label": label.strip(),
            "language": language or "auto",
            "dim": int(emb.size),
        }
    except Exception as e:
        logger.error(f"Speaker registration failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e), "detail": str(e)})


# ── Forensic PDF Report Endpoint (by call_id) ─────────────────────────────
@app.get("/api/report/{call_id}", tags=["forensics"])
async def generate_report(call_id: str):
    """Generate and download an I4C-ready forensic incident PDF report."""
    from app import store
    from app.forensics.pdf_report import generate_forensic_pdf

    session_data = _session_data_from_store(call_id)
    if session_data is None:
        # No stored telemetry for this call — refuse to fabricate forensic
        # evidence. A forensic PDF must never contain invented scores/dates.
        return JSONResponse(
            status_code=404,
            content={"error": f"No session telemetry for call '{call_id}'.", "detail": "Forensic reports are generated only from persisted session windows."},
        )

    # Generate PDF file in backend/reports directory as well as temp for download
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    saved_pdf_path = os.path.join(reports_dir, f"VoiceShield_Forensic_Report_{call_id}.pdf")

    try:
        from app.blockchain import ledger
        from app.blockchain.ledger import CHAIN_ID
        from app.blockchain.external_anchor import BlockAnchorError
        generate_forensic_pdf(
            session_data,
            saved_pdf_path,
            blockchain={"chain_id": CHAIN_ID, "call_id": call_id},
        )

        # Anchor the final PDF to the tamper-evident ledger (SHA-256 + PoW).
        windows = store.get_windows(call_id)
        leaves = sorted(f"{w['t_ms']}:{w['synthetic_score']}" for w in windows)
        block = ledger.anchor_report(
            call_id=call_id,
            report_id=f"FORENSIC-{call_id}",
            incident_id=None,
            file_path=saved_pdf_path,
            window_leaves=leaves,
        )
        logger.info(f"Report saved + anchored to blockchain: #{block['block_index']} {saved_pdf_path}")
        return FileResponse(
            path=saved_pdf_path,
            filename=f"VoiceShield_Forensic_Report_{call_id}.pdf",
            media_type="application/pdf",
        )
    except BlockAnchorError as e:
        # Mandatory mode (BLOCKCHAIN_ANCHOR_REQUIRED=true): no anchor, no hand-off.
        logger.error(f"Blockchain anchor refused for {call_id}: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "error": f"Report NOT blockchain-anchored: {e}",
                "detail": "BLOCKCHAIN_ANCHOR_REQUIRED=true — unanchored evidence is refused for forensic hand-off. On-chain anchoring failed; the report was not committed to the ledger.",
            },
        )
    except Exception as e:
        logger.error(f"PDF generation failed for {call_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate forensic report: {str(e)}"},
        )


# ── Include WebSocket Router ──────────────────────────────────────────────
try:
    from app.streaming.websocket import router as ws_router
    app.include_router(ws_router)
    logger.info("WebSocket streaming router mounted.")
except ImportError as e:
    logger.warning(f"WebSocket router not available: {e}")


# ── Serve built frontend (production single-server mode) ──────────────────
_frontend_dist = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if os.path.isdir(_frontend_dist):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
    logger.info(f"Serving frontend build from {_frontend_dist}")


# ── Run with Uvicorn ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )