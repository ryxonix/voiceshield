"""
VoiceShield AI — Prosodic Feature Extraction Tests
Tests the XAI prosodic feature extraction pipeline.
"""

import numpy as np
import pytest
from app.engine.features import extract_prosodics, ProsodicsResult


class TestProsodicsExtraction:
    """Tests for the prosodic feature extraction pipeline."""

    def _generate_sine(self, freq=200, sr=16000, duration_s=0.3, amplitude=0.5):
        """Generate a pure sine wave for testing."""
        t = np.arange(int(sr * duration_s)) / sr
        signal = (amplitude * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        return signal

    def _generate_noise(self, sr=16000, duration_s=0.3):
        """Generate random noise."""
        n_samples = int(sr * duration_s)
        return np.random.randint(-32768, 32767, n_samples, dtype=np.int16)

    def test_returns_prosodics_result(self):
        """Extraction returns a ProsodicsResult dataclass."""
        signal = self._generate_sine()
        result = extract_prosodics(signal, sr=16000)
        assert isinstance(result, ProsodicsResult)

    def test_has_all_fields(self):
        """Result contains all required prosodic fields."""
        signal = self._generate_sine()
        result = extract_prosodics(signal, sr=16000)
        assert hasattr(result, 'jitter_pct')
        assert hasattr(result, 'shimmer_pct')
        assert hasattr(result, 'phase_continuity')
        assert hasattr(result, 'pitch_stability_pct')

    def test_pure_tone_low_jitter(self):
        """A pure sine wave should have low jitter (stable pitch)."""
        signal = self._generate_sine(freq=200)
        result = extract_prosodics(signal, sr=16000)
        # Pure tone should have very low jitter
        assert result.jitter_pct < 5.0

    def test_pure_tone_high_phase_continuity(self):
        """A pure sine wave should have high phase continuity."""
        signal = self._generate_sine(freq=200)
        result = extract_prosodics(signal, sr=16000)
        assert result.phase_continuity > 0.5

    def test_pitch_stability_formula(self):
        """Pitch stability follows: max(0, 100 - min(jitter*40, 100))."""
        signal = self._generate_sine()
        result = extract_prosodics(signal, sr=16000)
        expected = max(0.0, 100.0 - min(result.jitter_pct * 40, 100.0))
        assert abs(result.pitch_stability_pct - expected) < 0.01

    def test_values_in_valid_range(self):
        """All prosodic values fall within expected ranges."""
        signal = self._generate_sine()
        result = extract_prosodics(signal, sr=16000)
        assert 0.0 <= result.jitter_pct
        assert 0.0 <= result.shimmer_pct
        assert 0.0 <= result.phase_continuity <= 1.0
        assert 0.0 <= result.pitch_stability_pct <= 100.0

    def test_noise_input_handled(self):
        """Random noise doesn't crash the extractor."""
        noise = self._generate_noise()
        result = extract_prosodics(noise, sr=16000)
        assert isinstance(result, ProsodicsResult)

    def test_silence_input_handled(self):
        """Silence (zeros) doesn't crash the extractor."""
        silence = np.zeros(4800, dtype=np.int16)
        result = extract_prosodics(silence, sr=16000)
        assert isinstance(result, ProsodicsResult)

    def test_correct_window_size(self):
        """Extraction works with exactly 4800 samples (300ms @ 16kHz)."""
        signal = self._generate_sine(duration_s=0.3)
        assert len(signal) == 4800
        result = extract_prosodics(signal, sr=16000)
        assert isinstance(result, ProsodicsResult)
