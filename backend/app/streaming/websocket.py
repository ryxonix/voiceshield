"""
VoiceShield AI — WebSocket Streaming Endpoint
Real-time PCM audio ingestion, detection pipeline, and score emission.
DPDP Compliant: only scalar scores and metadata transmitted, never raw audio.
"""

import json
import logging
import uuid

import numpy as np
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings
from app.engine.ring_buffer import RingBuffer
from app.engine.pipeline import analyze_window
from app.engine.speaker import (
    extract_embedding,
    bytes_to_embedding,
    cosine_similarity,
    is_speaker_mismatch,
)
from app.engine.session import session_manager
from app.engine.risk import threshold_for
from app.mitigation.router import evaluate_mitigation
from app import store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["streaming"])

IST = timezone(timedelta(hours=5, minutes=30))


@router.websocket("/ws/stream/{call_id}")
async def stream_endpoint(
    websocket: WebSocket,
    call_id: str,
    role: str = Query("adult"),
    language: str = Query("auto"),
    speaker: str = Query(""),
):
    """
    WebSocket endpoint for real-time audio deepfake detection.

    Accepts:
        - binary frames: PCM 16 kHz mono int16 audio chunks
        - text frames:   JSON control messages, e.g. {"type":"end"}

    Emits JSON analysis events (scores only, never raw audio) plus
    mitigation events when a session threshold is crossed.

    Args:
        call_id: Unique identifier for this call session.
        role: Session role — 'adult' (threshold 0.85) or 'child' (threshold 0.70).
        language: Hint used for logging/telemetry (auto / en / hi / kn ...).
        speaker: Registered speaker label for cross-session voice-print checks.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: call_id={call_id}, role={role}, language={language}, speaker={speaker or '-'}")

    session_id = call_id

    # Dhwani (trained deepfake detector) requires full 3-second windows for a
    # meaningful score, so stream on 3s windows / 1s hop when it is available.
    # Fall back to the legacy 300ms windows when only AASIST-L is present.
    try:
        from app.engine.dhwani import get_detector, MAX_SAMPLES
        dhwani_ready = get_detector().is_ready
    except Exception:  # noqa: BLE001
        dhwani_ready = False

    if dhwani_ready:
        buffer_window = MAX_SAMPLES
        buffer_hop = int(settings.sample_rate)  # 1 s hop
    else:
        buffer_window = settings.window_samples
        buffer_hop = settings.hop_samples

    ring = RingBuffer(window_size=buffer_window, hop_size=buffer_hop)
    window_index = 0
    max_score = 0.0
    score_sum = 0.0
    last_score = 0.0
    n_windows = 0
    enterprise_verified = False
    incident_created = False
    last_speaker_check_t = -1_000_000
    step_ms = int(round(buffer_hop * 1000.0 / settings.sample_rate))
    threshold = threshold_for(role)

    store.create_session(call_id, role, language)

    try:
        while True:
            msg = await websocket.receive()

            # ── Connection closing ─────────────────────────────────
            if msg["type"] == "websocket.disconnect":
                break

            text = msg.get("text")
            if text is not None:
                try:
                    data = json.loads(text)
                    if data.get("type") == "end":
                        break
                except Exception:  # noqa: BLE001
                    continue
                continue

            raw_bytes = msg.get("bytes")
            if not raw_bytes:
                continue

            # ── Parse incoming PCM ──────────────────────────────────
            pcm = np.frombuffer(raw_bytes, dtype=np.int16)

            # ── Push to ring buffer and process complete windows ────
            for window in ring.push(pcm):
                t_ms = window_index * step_ms

                # ── Cross-session speaker check (throttled ~2.5s) ──
                mismatched: bool | None = None
                if speaker and (t_ms - last_speaker_check_t) >= 2500:
                    last_speaker_check_t = t_ms
                    ref_bytes = store.get_speaker_embedding(speaker)
                    if ref_bytes is not None:
                        try:
                            ref = bytes_to_embedding(ref_bytes)
                            window_float = window.astype(np.float32) / 32768.0
                            emb = extract_embedding(
                                window_float, sr=settings.sample_rate
                            )
                            sim = cosine_similarity(emb, ref)
                            mismatched = is_speaker_mismatch(sim)
                        except Exception as e:  # noqa: BLE001
                            logger.debug(f"Speaker check failed: {e}")

                # ── Full detection pipeline ─────────────────────────
                event = analyze_window(window, role=role, speaker_mismatch=mismatched)

                score = event["synthetic_score"]
                watermark_hit = event["watermark_hit"]
                if watermark_hit:
                    enterprise_verified = True

                # ── Persist window + running aggregates ─────────────
                window_index += 1
                n_windows += 1
                score_sum += score
                max_score = max(max_score, score)
                last_score = score

                store.add_window(
                    session_id=session_id,
                    t_ms=t_ms,
                    model_prob=event["model_prob"],
                    xai_risk=event["xai_risk"],
                    synthetic_score=score,
                    jitter_pct=event["prosody"]["jitter_pct"],
                    shimmer_pct=event["prosody"]["shimmer_pct"],
                    phase_continuity=event["prosody"]["phase_continuity"],
                    pitch_stability=event["prosody"]["pitch_stability"],
                    noise_floor_dropouts=event["prosody"]["noise_floor_dropouts"],
                    watermark_hit=watermark_hit,
                    verdict=event["verdict"],
                )
                store.update_session_live(session_id, n_windows, max_score, last_score)

                # ── Mitigation: trigger only on first threshold breach ──
                if (
                    not incident_created
                    and not watermark_hit
                    and score >= threshold
                    and score > 0.0
                ):
                    incident_created = True
                    severity = "critical" if role == "child" else "high"
                    if role == "child":
                        action = "child_shield"
                        message = (
                            "Child Shield engaged — possible deepfake detected. "
                            "Audio muted and guardian notified."
                        )
                    else:
                        action = "risk_banner"
                        message = (
                            "Potential deepfake detected — verify caller identity "
                            "before proceeding."
                        )

                    await websocket.send_json(
                        {
                            "type": "mitigation",
                            "action": action,
                            "severity": severity,
                            "overlay": action == "child_shield",
                            "mute": action == "child_shield",
                            "score": score,
                            "threshold": threshold,
                            "role": role,
                            "message": message,
                            "call_id": call_id,
                            "timestamp_ist": datetime.now(IST).isoformat(),
                        }
                    )

                    triggers = list(
                        dict.fromkeys(
                            [
                                f"score>={role}_threshold",
                                *(
                                    ["speaker_mismatch"]
                                    if event["speaker_mismatch"]
                                    else []
                                ),
                            ]
                        )
                    )
                    store.add_incident(
                        iid=str(uuid.uuid4())[:8].upper(),
                        session_id=session_id,
                        role=role,
                        language=language,
                        severity=severity,
                        score=score,
                        triggers=triggers,
                        speaker_mismatch=bool(event["speaker_mismatch"]),
                    )
                    # Fire-and-forget external alert dispatch (Telegram/ntfy/Resend...)
                    try:
                        await evaluate_mitigation(score, role, call_id)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"Mitigation routing failed: {e}")

                event["call_id"] = call_id
                event["session_id"] = session_id
                event["t_ms"] = t_ms
                event["window_index"] = window_index
                event["threshold"] = threshold
                event["timestamp_ist"] = datetime.now(IST).isoformat()

                # Legacy-compatible annotation fields (repo spec + tests)
                event["label"] = {
                    "verified_enterprise": "verified_enterprise",
                    "benign": "genuine",
                    "suspicious": "suspicious",
                    "synthetic": "synthetic",
                    "synthetic+speaker_mismatch": "synthetic",
                }.get(event["verdict"], "suspicious")
                event["prosodics"] = {
                    "jitter_pct": event["prosody"]["jitter_pct"],
                    "shimmer_pct": event["prosody"]["shimmer_pct"],
                    "phase_continuity": event["prosody"]["phase_continuity"],
                    "pitch_stability_pct": event["prosody"]["pitch_stability"],
                }
                event["watermark"] = {"detected": watermark_hit}
                event["mitigation"] = (
                    {"action": "none", "triggered": False, "threshold": threshold}
                    if not incident_created
                    else {"action": action, "triggered": True, "score": score, "threshold": threshold}
                )
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {call_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {call_id}: {e}", exc_info=True)
    finally:
        ring.reset()
        store.close_session(
            session_id,
            n_windows,
            max_score,
            (score_sum / n_windows) if n_windows else 0.0,
            last_score,
            enterprise_verified,
        )
        await session_manager.destroy(call_id)
        logger.info(f"Session cleaned up: {call_id}")