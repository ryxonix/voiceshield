"""
VoiceShield AI — Risk Fusion Engine
Combines AASIST model probability with XAI prosodic risk for final scoring.
"""

import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, Any

from app.engine.features import ProsodicsResult
from app.engine.watermark import WatermarkResult


@dataclass
class FusionResult:
    """Result of risk score fusion."""
    synthetic_score: float    # Final fused risk score ∈ [0, 1]
    xai_risk: float           # XAI-derived risk component ∈ [0, 1]
    model_prob: float         # Raw AASIST model probability
    label: str                # Classification label
    details: Dict[str, Any]   # Detailed breakdown for telemetry

    def to_dict(self) -> dict:
        return asdict(self)


def compute_risk(
    model_prob: float,
    prosodics: ProsodicsResult,
    watermark: WatermarkResult,
    model_weight: float = 0.7,
    xai_weight: float = 0.3,
) -> FusionResult:
    """
    Compute the final fused risk score.

    Formula:
        xai_risk = (1.0 - phase_continuity)*0.5
                 + max(0.0, 1.0 - jitter_pct/1.0)*0.3
                 + max(0.0, 1.0 - shimmer_pct/3.0)*0.2

        synthetic_score = clip(0.7 × model_prob + 0.3 × clip(xai_risk, 0, 1), 0, 1)

    If enterprise watermark is detected, short-circuits to score=0.0.

    Args:
        model_prob: AASIST model output probability ∈ [0, 1].
        prosodics: Prosodic feature extraction result.
        watermark: Watermark verification result.
        model_weight: Weight for model probability (default 0.7).
        xai_weight: Weight for XAI risk (default 0.3).

    Returns:
        FusionResult with fused score, sub-scores, and label.
    """
    # ── Enterprise Watermark Short-Circuit ──────────────────────────
    if watermark.detected:
        return FusionResult(
            synthetic_score=0.0,
            xai_risk=0.0,
            model_prob=model_prob,
            label="verified_enterprise",
            details={
                "watermark_detected": True,
                "watermark_snr": watermark.snr_ratio,
                "watermark_freq": watermark.tone_freq,
                "short_circuited": True,
            },
        )

    # ── XAI Risk Computation ────────────────────────────────────────
    # Phase continuity: lower continuity → higher risk
    phase_penalty = (1.0 - prosodics.phase_continuity) * 0.5

    # Jitter: synthetic speech often has unnaturally LOW jitter (too perfect)
    jitter_penalty = max(0.0, 1.0 - prosodics.jitter_pct / 1.0) * 0.3

    # Shimmer: synthetic speech often has unnaturally LOW shimmer
    shimmer_penalty = max(0.0, 1.0 - prosodics.shimmer_pct / 3.0) * 0.2

    xai_risk = float(np.clip(
        phase_penalty + jitter_penalty + shimmer_penalty,
        0.0, 1.0,
    ))

    # ── Fused Score ─────────────────────────────────────────────────
    synthetic_score = float(np.clip(
        model_weight * model_prob + xai_weight * xai_risk,
        0.0, 1.0,
    ))

    # ── Label Assignment ────────────────────────────────────────────
    if synthetic_score < 0.5:
        label = "genuine"
    elif synthetic_score < 0.85:
        label = "suspicious"
    else:
        label = "synthetic"

    return FusionResult(
        synthetic_score=synthetic_score,
        xai_risk=xai_risk,
        model_prob=model_prob,
        label=label,
        details={
            "phase_penalty": phase_penalty,
            "jitter_penalty": jitter_penalty,
            "shimmer_penalty": shimmer_penalty,
            "prosodics": prosodics.to_dict(),
            "watermark_detected": False,
        },
    )
