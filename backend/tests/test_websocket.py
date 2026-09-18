"""
VoiceShield AI — WebSocket Integration Tests
Tests the real-time WebSocket streaming endpoint.
"""

import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app

TEST_PCM_SAMPLES = 48000  # 3 s @ 16 kHz — fills a Dhwani analysis window


def _noise_pcm(n=TEST_PCM_SAMPLES):
    return np.random.randint(-32768, 32767, n, dtype=np.int16)


def _receive_analysis(ws, max_wait: int = 5):
    """Receive JSON messages until an analysis event arrives (skip mitigation)."""
    for _ in range(max_wait):
        msg = ws.receive_json()
        if msg.get("type") == "analysis":
            return msg
    raise AssertionError("No analysis event received")


class TestWebSocket:
    """Tests for the WebSocket streaming endpoint."""

    def test_websocket_connect(self):
        """WebSocket accepts connection at /ws/stream/{call_id}."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-001?role=adult") as ws:
            pass  # Connection accepted — disconnect

    def test_websocket_receives_response(self):
        """Sending PCM data produces a JSON analysis response."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-002?role=adult") as ws:
            pcm = _noise_pcm()
            ws.send_bytes(pcm.tobytes())
            response = _receive_analysis(ws)
            assert "synthetic_score" in response
            assert "call_id" in response
            assert response["call_id"] == "test-ws-002"

    def test_websocket_response_format(self):
        """Response contains all required fields per spec."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-003?role=adult") as ws:
            pcm = _noise_pcm()
            ws.send_bytes(pcm.tobytes())
            response = _receive_analysis(ws)
            required_fields = [
                "call_id", "window_index", "synthetic_score",
                "xai_risk", "model_prob", "label", "prosodics",
                "watermark", "mitigation", "latency_ms", "timestamp_ist",
            ]
            for field in required_fields:
                assert field in response, f"Missing field: {field}"

    def test_websocket_score_range(self):
        """Synthetic score is within [0.0, 1.0]."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-004?role=adult") as ws:
            pcm = _noise_pcm()
            ws.send_bytes(pcm.tobytes())
            response = _receive_analysis(ws)
            assert 0.0 <= response["synthetic_score"] <= 1.0

    def test_websocket_child_role(self):
        """Child role is preserved in the session."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-005?role=child") as ws:
            pcm = _noise_pcm()
            ws.send_bytes(pcm.tobytes())
            response = _receive_analysis(ws)
            assert "mitigation" in response

    def test_websocket_no_audio_in_response(self):
        """DPDP compliance: Response never contains raw audio data."""
        client = TestClient(app)
        with client.websocket_connect("/ws/stream/test-ws-006?role=adult") as ws:
            pcm = _noise_pcm()
            ws.send_bytes(pcm.tobytes())
            response = _receive_analysis(ws)
            response_str = json.dumps(response)
            assert len(response_str) < 2000  # Scalar scores only — compact
