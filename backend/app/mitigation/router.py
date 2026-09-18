"""
VoiceShield AI — Role-Aware Mitigation Router
Routes detection results to appropriate mitigation actions based on role and score.
"""

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MitigationAction:
    """Base mitigation action."""
    action: str
    triggered: bool
    details: Dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


async def evaluate_mitigation(
    score: float,
    role: str,
    call_id: str,
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

    # ── Child Shield Protocol ──────────────────────────────────────
    if role == "child":
        logger.warning(
            f"CHILD SHIELD TRIGGERED: call={call_id}, "
            f"score={score:.4f} ≥ {threshold}"
        )

        # Dispatch alerts asynchronously (non-blocking)
        asyncio.create_task(
            _dispatch_alerts_safe(call_id, score, role, "child_shield")
        )

        from app.mitigation.child_shield import create_child_shield_payload
        return create_child_shield_payload(score, call_id)

    # ── Adult Risk Banner ──────────────────────────────────────────
    logger.warning(
        f"ADULT ALERT: call={call_id}, "
        f"score={score:.4f} ≥ {threshold}"
    )

    # Dispatch alerts asynchronously (non-blocking)
    asyncio.create_task(
        _dispatch_alerts_safe(call_id, score, role, "adult_alert")
    )

    return {
        "action": "adult_alert",
        "triggered": True,
        "banner": True,
        "message": "⚠️ POTENTIAL DEEPFAKE DETECTED — Exercise caution",
        "score": round(score, 4),
        "threshold": threshold,
    }


async def _dispatch_alerts_safe(
    call_id: str, score: float, role: str, action_type: str
) -> None:
    """Safely dispatch alerts — never raises exceptions."""
    try:
        from app.mitigation.alerts import dispatch_alerts
        await dispatch_alerts(call_id, score, role, action_type)
    except Exception as e:
        logger.error(f"Alert dispatch failed for {call_id}: {e}")
