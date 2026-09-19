"""
VoiceShield AI — Role-Aware Mitigation Router
Routes detection results to appropriate mitigation actions based on role and score.
"""

import asyncio
import logging
from typing import Any, Dict

from app.config import settings
from app.engine.risk import risk_band, recommended_actions
from app.mitigation.workflows import workflow_detail

logger = logging.getLogger(__name__)


async def evaluate_mitigation(
    score: float,
    role: str,
    call_id: str,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Evaluate whether the current score triggers mitigation.

    Thresholds:
        - Adult: ≥ 0.85 → risk banner + async alerts
        - Child: ≥ 0.70 → immediate mute + shield overlay + async alerts

    Args:
        score: Fused synthetic score ∈ [0, 1].
        role: Session role ('adult' or 'child').
        call_id: Call session identifier.
        context: Optional contextual-enrichment detail (app.context.enrichment).

    Returns:
        Dict with action type and details for WebSocket transmission.
    """
    # Determine threshold
    threshold = (
        settings.child_threshold if role == "child"
        else settings.adult_threshold
    )

    if score < threshold:
        return {
            "action": "none",
            "triggered": False,
            "threshold": threshold,
        }

    band = risk_band(score, role)
    actions = recommended_actions(band, role)
    wf = workflow_detail(band, role)

    # ── Child Shield Protocol ──────────────────────────────────────
    if role == "child":
        logger.warning(
            f"CHILD SHIELD TRIGGERED: call={call_id}, "
            f"score={score:.4f} ≥ {threshold}"
        )

        # Dispatch alerts asynchronously (non-blocking)
        asyncio.create_task(
            _dispatch_alerts_safe(call_id, score, role, "child_shield", context=context)
        )

        from app.mitigation.child_shield import create_child_shield_payload
        payload = create_child_shield_payload(score, call_id)
        payload.update(
            {
                "risk_band": band,
                "recommended_actions": actions,
                "workflow": wf.get("matched_rule", {}),
            }
        )
        return payload

    # ── Adult Risk Banner ──────────────────────────────────────────
    logger.warning(
        f"ADULT ALERT: call={call_id}, "
        f"score={score:.4f} ≥ {threshold}"
    )

    # Dispatch alerts asynchronously (non-blocking)
    asyncio.create_task(
        _dispatch_alerts_safe(call_id, score, role, "adult_alert", context=context)
    )

    return {
        "action": "adult_alert",
        "triggered": True,
        "banner": True,
        "message": "⚠️ POTENTIAL DEEPFAKE DETECTED — Exercise caution",
        "score": round(score, 4),
        "threshold": threshold,
        "risk_band": band,
        "recommended_actions": actions,
        "workflow": wf.get("matched_rule", {}),
    }


async def _dispatch_alerts_safe(
    call_id: str,
    score: float,
    role: str,
    action_type: str,
    context: Dict[str, Any] | None = None,
) -> None:
    """Safely dispatch alerts — never raises exceptions."""
    try:
        from app.mitigation.alerts import dispatch_alerts
        band = risk_band(score, role)
        await dispatch_alerts(
            call_id,
            score,
            role,
            action_type,
            context=context,
            recommended_actions=recommended_actions(band, role),
        )
    except Exception as e:
        logger.error(f"Alert dispatch failed for {call_id}: {e}")
