"""
VoiceShield AI — Risk Banding, Verdicts, and Recommendations

Band edges derive from the configured role threshold (settings.adult_threshold
= 0.85 and settings.child_threshold = 0.70 by default). "critical" is the role
threshold itself; "high" sits 0.17 below it; "medium" starts at 0.35.

    critical   >= role_threshold              (child 0.70 / adult 0.85)
    high       >= role_threshold - 0.17
    medium     >= 0.35
    low        <  0.35
"""

from app.config import settings

HIGH_EDGE_OFSET = 0.17
MEDIUM_EDGE = 0.35


def threshold_for(role: str = "adult") -> float:
    return settings.child_threshold if role == "child" else settings.adult_threshold


def risk_band(score: float, role: str = "adult") -> str:
    critical = threshold_for(role)
    if score >= critical:
        return "critical"
    if score >= critical - HIGH_EDGE_OFSET:
        return "high"
    if score >= MEDIUM_EDGE:
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


def recommended_actions(band: str, role: str = "adult") -> list[str]:
    """
    Pre-transaction verification prompts surfaced to frontline staff before a
    sensitive action (fund transfer / privileged access) is taken. Child path
    stays protective (mute-first), adult path recommends secondary verification
    per SIH26104 ("call-back, multifactor authentication, supervisor escalation").
    """
    if role == "child":
        if band == "critical":
            return ["auto-mute speaker", "notify guardian", "notify authorities", "escalate to supervisor"]
        if band == "high":
            return ["auto-mute speaker", "verify caller identity"]
        return ["flag for manual review"]
    if band == "critical":
        return [
            "warn user",
            "require call-back verification on originating line",
            "require MFA / OTP challenge",
            "escalate to supervisor",
        ]
    if band == "high":
        return ["warn user", "require secondary verification (call-back or MFA)"]
    if band == "medium":
        return ["flag for manual review"]
    return ["continue real-time monitoring"]