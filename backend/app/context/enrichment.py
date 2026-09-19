"""
VoiceShield AI — Contextual Risk Enrichment

Adds conservative, transparent risk modifiers on top of the acoustic synthetic
score using call metadata (caller, origin, transaction value, known-contact
status, and a caller's historical fraud flags). Mirrors the SIH26104 problem
statement's "contextual enrichment" component.

DPDP posture: only scalar metadata is read (caller pattern, origin, amount,
flag count) — never audio. Raw acoustic scores stay untouched in the window
store; enrichment is applied to the *actionable* score surfaced on incidents,
alerts, and the pre-transaction verification prompts.

Fail-open: if enrichment is disabled or no context is provided, the acoustic
score is returned unchanged.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple

from app.config import settings
from app import store


@dataclass
class CallContext:
    """Call metadata used for contextual risk enrichment."""

    caller: str = ""
    origin: str = ""               # telecom / voip / enterprise / unknown
    txn_value: float = 0.0         # transaction value (INR); 0 = no transaction
    txn_category: str = ""         # e.g. fund_transfer / privileged_access
    known_contact: Optional[bool] = None   # explicit override; None = auto-check
    prior_flags: Optional[int] = None      # explicit override; None = auto-check
    provided: bool = False                 # True when any field was supplied

    @classmethod
    def from_mapping(cls, raw: Optional[Dict[str, Any]]) -> "CallContext":
        if not raw:
            return cls()
        data = raw if isinstance(raw, dict) else {}
        provided = any(
            (
                bool(data.get("caller")),
                bool(data.get("origin")),
                float(data.get("txn_value") or 0.0) > 0.0,
                bool(data.get("txn_category")),
                data.get("known_contact") is not None,
                data.get("prior_flags") is not None,
            )
        )
        return cls(
            caller=str(data.get("caller") or ""),
            origin=str(data.get("origin") or ""),
            txn_value=float(data.get("txn_value") or 0.0),
            txn_category=str(data.get("txn_category") or ""),
            known_contact=data.get("known_contact"),
            prior_flags=data.get("prior_flags"),
            provided=provided,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_signals(ctx: CallContext) -> Dict[str, Any]:
    """Resolve the discrete signals that drive modifier selection."""
    signals: Dict[str, Any] = {}

    signals["unknown_origin"] = ctx.origin.strip() in ("", "unknown")

    if ctx.known_contact is not None:
        signals["known_contact"] = bool(ctx.known_contact)
    else:
        auto = store.contact_match(ctx.caller)  # None when contacts unconfigured
        if auto is not None:
            signals["known_contact"] = auto

    signals["high_value_txn"] = ctx.txn_value >= settings.context_high_value_threshold

    flags = ctx.prior_flags if ctx.prior_flags is not None else store.get_caller_flags(ctx.caller)
    signals["prior_fraud_flags"] = int(flags) if flags else 0

    return signals


def enrich_score(
    score: float,
    ctx_or_raw: Any,
    role: str = "adult",
) -> Tuple[float, Dict[str, Any]]:
    """
    Return (adjusted_score, detail). The detail dict exposes every signal and
    modifier so the arithmetic is auditable end-to-end (a judged-friendly
    "actionable risk score", per SIH26104).
    """
    ctx = (
        ctx_or_raw
        if isinstance(ctx_or_raw, CallContext)
        else CallContext.from_mapping(ctx_or_raw)
    )
    base = float(score)
    detail: Dict[str, Any] = {
        "enabled": bool(settings.contextual_enrichment),
        "provided": ctx.provided,
        "applied": False,
        "signals": {},
        "modifiers": {},
        "base_score": round(base, 4),
        "adjusted_score": round(base, 4),
    }

    if not settings.contextual_enrichment or not ctx.provided:
        return detail["adjusted_score"], detail

    signals = resolve_signals(ctx)
    detail["signals"] = signals

    mods: Dict[str, float] = {}

    if signals.get("unknown_origin"):
        mods["unknown_origin"] = round(settings.context_unknown_origin_penalty, 4)

    known = signals.get("known_contact")
    if known is True:
        mods["known_contact"] = -round(settings.context_known_contact_boost, 4)
    elif known is False:
        mods["unknown_contact"] = round(settings.context_unknown_contact_penalty, 4)

    if signals.get("high_value_txn"):
        mods["high_value_txn"] = round(settings.context_high_value_penalty, 4)

    flags = int(signals.get("prior_fraud_flags") or 0)
    if flags > 0:
        mods["prior_fraud_flags"] = round(
            min(flags, 3) * settings.context_prior_flag_penalty, 4
        )

    if mods:
        adjusted = max(0.0, min(1.0, base + sum(mods.values())))
        detail["applied"] = True
        detail["modifiers"] = mods
        detail["adjusted_score"] = round(adjusted, 4)
        return detail["adjusted_score"], detail

    return detail["adjusted_score"], detail