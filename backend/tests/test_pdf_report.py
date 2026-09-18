"""
VoiceShield AI — Forensic PDF Report Tests
Tests the I4C-ready PDF report generation.
"""

import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest
from app.forensics.pdf_report import generate_forensic_pdf


IST = timezone(timedelta(hours=5, minutes=30))


class TestForensicPDF:
    """Tests for the I4C forensic incident PDF generator."""

    def _make_session_data(self):
        """Create sample session data for testing."""
        return {
            "call_id": "test-call-001",
            "role": "child",
            "start_time": datetime.now(IST).isoformat(),
            "end_time": datetime.now(IST).isoformat(),
            "peak_score": 0.92,
            "peak_prosodics": {
                "jitter_pct": 0.3,
                "shimmer_pct": 1.2,
                "phase_continuity": 0.45,
                "pitch_stability_pct": 88.0,
            },
            "action_taken": "child_shield",
            "history": [
                {"window_index": i, "synthetic_score": 0.5 + i * 0.05,
                 "timestamp": datetime.now(IST).isoformat()}
                for i in range(10)
            ],
        }

    def test_pdf_generated(self):
        """PDF file is created at the specified path."""
        session_data = self._make_session_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_report.pdf")
            result = generate_forensic_pdf(session_data, pdf_path)
            assert os.path.exists(pdf_path)

    def test_pdf_not_empty(self):
        """Generated PDF has non-zero file size."""
        session_data = self._make_session_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_report.pdf")
            generate_forensic_pdf(session_data, pdf_path)
            size = os.path.getsize(pdf_path)
            assert size > 1000  # Should be at least a few KB

    def test_pdf_is_valid(self):
        """Generated file starts with PDF magic bytes."""
        session_data = self._make_session_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_report.pdf")
            generate_forensic_pdf(session_data, pdf_path)
            with open(pdf_path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-"

    def test_missing_fields_handled(self):
        """PDF generation handles missing optional fields gracefully."""
        minimal_data = {
            "call_id": "minimal-001",
            "role": "adult",
            "start_time": datetime.now(IST).isoformat(),
            "peak_score": 0.5,
            "peak_prosodics": None,
            "action_taken": "none",
            "history": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "minimal_report.pdf")
            generate_forensic_pdf(minimal_data, pdf_path)
            assert os.path.exists(pdf_path)
