"""
VoiceShield AI — Configurable Mitigation Workflows

Implements the SIH26104 requirement for "configurable workflows for banks,
enterprises, and government agencies to define automated responses when
impersonation risk crosses thresholds".

Rules live in a JSON file (default `backend/workflows.json`, overridable via
WORKFLOWS_PATH env var) so operators can change actions/channels without a code
deploy. If the file is missing or malformed, bundled defaults are used —
fail-open, and never raises.
"""

import json
import os
from typing import Dict, List, Optional

from app.config import settings

_BAND_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_DEFAULT_RULES: List[Dict] = [
    {
        "role": "child",
        "band_min": "critical",
        "actions": ["auto_mute", "notify_guardian_and_authorities", "escalate_supervisor"],
        "channels": ["telegram", "sms", "email", "webhook"],
    },
    {
        "role": "child",
        "band_min": "high",
        "actions": ["auto_mute", "verify_caller_identity"],
        "channels": ["telegram", "webhook"],
    },
    {
        "role": "adult",
        "band_min": "critical",
        "actions": ["warn_user", "require_call_back", "require_mfa", "escalate_supervisor"],
        "channels": ["telegram", "email", "webhook"],
    },
    {
        "role": "adult",
        "band_min": "high",
        "actions": ["warn_user", "require_secondary_verification"],
        "channels": ["telegram", "webhook"],
    },
    {
        "role": "adult",
        "band_min": "medium",
        "actions": ["flag_manual_review"],
        "channels": ["webhook"],
    },
]

_DEFAULTS = {"version": 1, "rules": _DEFAULT_RULES}


def _resolve_path(path: str) -> str:
    """Resolve a possibly-relative path against the backend root."""
    if not path or os.path.isabs(path):
        return path
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )  # app/mitigation/workflows.py -> backend/
    return os.path.normpath(os.path.join(backend_root, path))


def _default_path() -> str:
    return _resolve_path("workflows.json")


def _load() -> tuple[Dict, str]:
    """Load the workflow config; returns (config, human-readable source)."""
    configured = settings.workflows_path
    if not configured:
        return _DEFAULTS, "bundled_defaults"
    path = _resolve_path(configured)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("rules"), list) and data["rules"]:
            return data, path
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULTS, "bundled_defaults (active file missing or malformed)"


def resolve_workflow(band: str, role: str = "adult", data: Optional[Dict] = None) -> Dict:
    """
    Pick the most specific rule whose band_min is satisfied by the current band.
    Returns a dict with keys: role, band_min, actions, channels.
    """
    if data is None:
        data, _ = _load()
    level = _BAND_ORDER.get(band, 1)
    best = None
    for rule in data["rules"]:
        if rule.get("role", "adult") != role:
            continue
        if _BAND_ORDER.get(rule.get("band_min", "low"), 0) <= level:
            if best is None or _BAND_ORDER.get(rule["band_min"], 0) > _BAND_ORDER.get(
                best["band_min"], 0
            ):
                best = rule
    if best is not None:
        return best
    # No rule satisfied: fall back to the least specific rule for the role.
    role_rules = [r for r in data["rules"] if r.get("role", "adult") == role]
    if role_rules:
        return min(role_rules, key=lambda r: _BAND_ORDER.get(r.get("band_min", "low"), 0))
    return data["rules"][0]


def get_workflow_config() -> Dict:
    """Return the full parsed workflow config (for the /api/workflows route)."""
    data, _ = _load()
    return data


def workflow_detail(band: str, role: str = "adult") -> Dict:
    data, source = _load()
    rule = resolve_workflow(band, role, data=data)
    return {
        "band": band,
        "role": role,
        "matched_rule": {
            "role": rule.get("role"),
            "band_min": rule.get("band_min"),
            "actions": rule.get("actions", []),
            "channels": rule.get("channels", []),
        },
        "config_source": source,
    }