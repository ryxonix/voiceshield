"""
VoiceShield AI — Risk Banding, Verdicts, and Recommendations

Bands mirror the dashboard cards:
    critical   >= 0.85
    high       >= 0.68
    medium     >= 0.35
    low        <  0.35
"""

ADULT_THRESHOLD = 0.85
CHILD_THRESHOLD = 0.70


def threshold_for(role: str = "adult") -> float:
    return CHILD_THRESHOLD if role == "child" else ADULT_THRESHOLD


def risk_band(score: float, role: str = "adult") -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.68:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def verdict_for(band: str, role: str = "adult") -> str:
    del role
    if band in ("critical", "high"):
        return "suspicious" if band == "high" else "synthetic"
    if band == "medium":
        return "suspicious"
    return "benign"


def recommendation(band: str, role: str = "adult") -> str:
    if band == "critical":
        if role == "child":
            return "EMERGENCY — Child Shield engaged: mute audio, notify guardian & authorities."
        return "CRITICAL — Verified deepfake: block call, log incident, alert law enforcement."
    if band == "high":
        if role == "child":
            return "HIGH — Strong voice integrity risk: mute speaker and verify caller identity."
        return "HIGH — Likely synthetic voice: warn user and require identity verification."
    if band == "medium":
        return "MEDIUM — Voice integrity questionable: escalate for manual review."
    return "LOW — Voice integrity nominal, continuing real-time monitoring."