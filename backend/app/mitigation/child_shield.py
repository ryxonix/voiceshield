"""
VoiceShield AI — Child Shield Protocol
Generates the protective payload for child sessions when deepfake is detected.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any


IST = timezone(timedelta(hours=5, minutes=30))


def create_child_shield_payload(score: float, call_id: str) -> Dict[str, Any]:
    """
    Create the Child Shield protective payload.

    When triggered, instructs the client to:
    1. Immediately mute the speaker
    2. Display full-screen red protective overlay
    3. Show emergency contact information

    Args:
        score: Fused synthetic score that triggered the shield.
        call_id: Call session identifier.

    Returns:
        Dict payload for WebSocket transmission to the client.
    """
    return {
        "action": "child_shield",
        "triggered": True,
        "mute": True,
        "overlay": True,
        "message": "🛡️ DEEPFAKE ALERT — CALL PROTECTION ACTIVE",
        "sub_message": "Speaker has been muted for your safety",
        "score": round(score, 4),
        "emergency_contacts": {
            "i4c_helpline": {
                "name": "I4C Cybercrime Helpline",
                "number": "1930",
                "description": "National Cybercrime Reporting (24/7)",
            },
            "cyber_police": {
                "name": "Cyber Police Portal",
                "url": "https://cybercrime.gov.in",
                "description": "File an online complaint",
            },
            "child_helpline": {
                "name": "Childline India",
                "number": "1098",
                "description": "Child emergency helpline (24/7)",
            },
        },
        "timestamp_ist": datetime.now(IST).isoformat(),
        "call_id": call_id,
    }
