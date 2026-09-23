"""
VoiceShield AI — Forensic PDF Report Tests
Tests the I4C-ready PDF report generation.
"""

import os
import re
import tempfile
from datetime import datetime, timezone, timedelta

import pytest
from pypdf import PdfReader
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

    def test_pdf_mentions_risk_score(self):
        """PDF surfaces a composed Risk Score section (score, band, threshold, verdict)."""
        session_data = self._make_session_data()  # child, peak 0.92
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "risk_report.pdf")
            generate_forensic_pdf(session_data, pdf_path)
            reader = PdfReader(pdf_path)
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        assert "Risk Score" in text
        assert "0.9200" in text and "92.0%" in text
        assert "Critical" in text          # risk band from peak 0.92
        assert "child" in text and "0.70" in text  # role / child threshold
        assert "Synthetic" in text        # verdict_for(critical, child)


class TestWindowTimestamps:
    """_session_data_from_store must map store windows.t_ms onto the session start."""

    def test_pdf_timeline_shows_real_timestamps(self):
        """Regression: Score Timeline used N/A because timestamps were stubbed to None."""
        from app import store
        from app.main import _session_data_from_store
        from app.store import _DB_PATH
        import sqlite3

        call_id = "pdf-timeline-test"
        # Make the test idempotent across runs (persisted DB).
        with sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False) as conn:
            conn.execute("DELETE FROM windows WHERE session_id=?", (call_id,))
        store.create_session(call_id, role="adult", language="en")
        for i, score in enumerate([0.12, 0.53, 0.89]):
            store.add_window(
                session_id=call_id, t_ms=i * 2000, model_prob=score, xai_risk=score,
                synthetic_score=score, jitter_pct=1.0, shimmer_pct=2.0,
                phase_continuity=0.91, pitch_stability=80.0,
                noise_floor_dropouts=0, watermark_hit=False, verdict="bonafide",
            )
        store.close_session(call_id, window_count=3, max_score=0.89, avg_score=0.5133, last_score=0.89)

        sess = store.get_session(call_id)
        data = _session_data_from_store(call_id)
        assert data is not None
        hist = data["history"]
        assert len(hist) == 3

        start_dt = datetime.fromisoformat(sess["started_at"]).replace(tzinfo=timezone.utc)
        for i, h in enumerate(hist):
            assert h["timestamp"] is not None, f"window {i} timestamp must not be None"
            expected = start_dt + timedelta(milliseconds=i * 2000)
            assert abs(h["timestamp"] - expected.timestamp()) < 1.0

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "timeline.pdf")
            generate_forensic_pdf(data, pdf_path)
            reader = PdfReader(pdf_path)
            text = "\n".join((page.extract_text() or "") for page in reader.pages)

        assert "Score Timeline" in text
        assert "N/A" not in text
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text)
