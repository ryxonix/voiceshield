"""
VoiceShield AI — Risk Fusion Engine Tests
Tests the watermark verifier and risk score fusion.
"""

import numpy as np
import pytest
from app.engine.features import ProsodicsResult
from app.engine.watermark import check_watermark, WatermarkResult
from app.engine.fusion import compute_risk, FusionResult


class TestWatermark:
    """Tests for the enterprise watermark verifier."""

    def test_no_watermark_in_silence(self):
        """Silence should not trigger watermark detection."""
        silence = np.zeros(4800, dtype=np.int16)
        result = check_watermark(silence, sr=16000)
        assert isinstance(result, WatermarkResult)
        assert result.detected is False

    def test_no_watermark_in_noise(self):
        """Random noise should not trigger watermark detection."""
        noise = np.random.randint(-1000, 1000, 4800, dtype=np.int16)
        result = check_watermark(noise, sr=16000)
        assert result.detected is False

    def test_watermark_detected_with_pilot_tone(self):
        """A strong pilot tone at 7.25 kHz should be detected."""
        sr = 16000
        t = np.arange(4800) / sr
        # Strong pilot tone at 7.25 kHz (center of 7.0-7.5 kHz band)
        tone = (np.sin(2 * np.pi * 7250 * t) * 30000).astype(np.int16)
        # Add weak background
        bg = np.random.randint(-100, 100, 4800, dtype=np.int16)
        signal = np.clip(tone.astype(np.int32) + bg.astype(np.int32), -32768, 32767).astype(np.int16)
        result = check_watermark(signal, sr=sr)
        assert result.detected is True

    def test_low_sample_rate_skipped(self):
        """Sample rates too low for 7.5 kHz Nyquist should return not detected."""
        signal = np.zeros(4800, dtype=np.int16)
        result = check_watermark(signal, sr=8000)
        assert result.detected is False


class TestFusion:
    """Tests for the risk fusion engine."""

    def _make_prosodics(self, jitter=0.5, shimmer=1.5,
                         phase=0.9, stability=80.0):
        return ProsodicsResult(
            jitter_pct=jitter,
            shimmer_pct=shimmer,
            phase_continuity=phase,
            pitch_stability_pct=stability,
        )

    def _make_watermark(self, detected=False):
        return WatermarkResult(detected=detected, tone_freq=0.0, snr_ratio=0.0)

    def test_returns_fusion_result(self):
        """Fusion returns a FusionResult."""
        result = compute_risk(0.5, self._make_prosodics(), self._make_watermark())
        assert isinstance(result, FusionResult)

    def test_watermark_short_circuits(self):
        """Detected watermark → score=0.0, label='verified_enterprise'."""
        wm = self._make_watermark(detected=True)
        result = compute_risk(0.99, self._make_prosodics(), wm)
        assert result.synthetic_score == 0.0
        assert result.label == "verified_enterprise"

    def test_score_range(self):
        """Fused score is always in [0.0, 1.0]."""
        for model_prob in [0.0, 0.3, 0.5, 0.7, 1.0]:
            result = compute_risk(model_prob, self._make_prosodics(), self._make_watermark())
            assert 0.0 <= result.synthetic_score <= 1.0

    def test_high_model_prob_high_score(self):
        """High model probability leads to high fused score."""
        result = compute_risk(0.95, self._make_prosodics(jitter=0.1, shimmer=0.5, phase=0.3), self._make_watermark())
        assert result.synthetic_score >= 0.6

    def test_low_model_prob_low_score(self):
        """Low model probability leads to lower fused score."""
        result = compute_risk(0.05, self._make_prosodics(jitter=2.0, shimmer=5.0, phase=0.95), self._make_watermark())
        assert result.synthetic_score < 0.5

    def test_fusion_formula_exact(self):
        """Verify the exact fusion formula: 0.7*model + 0.3*xai_risk."""
        prosodics = self._make_prosodics(jitter=0.5, shimmer=1.5, phase=0.9)
        model_prob = 0.8
        result = compute_risk(model_prob, prosodics, self._make_watermark())

        # Manually compute expected
        xai_risk = (
            (1.0 - 0.9) * 0.5 +
            max(0.0, 1.0 - 0.5 / 1.0) * 0.3 +
            max(0.0, 1.0 - 1.5 / 3.0) * 0.2
        )
        expected = np.clip(0.7 * 0.8 + 0.3 * np.clip(xai_risk, 0.0, 1.0), 0.0, 1.0)
        assert abs(result.synthetic_score - expected) < 0.01

    def test_label_genuine(self):
        """Score < 0.5 → label 'genuine'."""
        result = compute_risk(0.1, self._make_prosodics(jitter=2.0, shimmer=5.0, phase=0.95), self._make_watermark())
        assert result.label == "genuine"

    def test_label_synthetic(self):
        """Score >= 0.85 → label 'synthetic'."""
        result = compute_risk(0.99, self._make_prosodics(jitter=0.05, shimmer=0.1, phase=0.1), self._make_watermark())
        assert result.label == "synthetic"
