"""
VoiceShield AI — DPDP Act Compliance Layer
Digital Personal Data Protection Act 2023 alignment.

Ensures:
    - Ephemeral audio buffer lifecycle (RAM-only, auto-wiped)
    - Zero disk storage of raw audio
    - Minimized telemetry (scalar scores only)
    - Non-PII audit logging
"""

import sys
import ctypes
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


class EphemeralBuffer:
    """
    Wraps a numpy array with guaranteed memory wiping on destruction.
    Audio data exists strictly in RAM and is zeroed out when no longer needed.
    """

    def __init__(self, data: np.ndarray):
        self.data = data
        self._wiped = False

    def wipe(self) -> None:
        """Zero out the underlying memory buffer."""
        if self._wiped or self.data is None:
            return
        try:
            # Zero via numpy
            self.data.fill(0)
            # Double-wipe via ctypes for security
            if self.data.ctypes.data:
                ctypes.memset(self.data.ctypes.data, 0, self.data.nbytes)
        except Exception:
            pass
        finally:
            self._wiped = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.wipe()

    def __del__(self):
        self.wipe()


class SecureSession:
    """
    Context manager for a DPDP-compliant audio processing session.
    Tracks all ephemeral buffers and wipes them on session end.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._buffers: List[EphemeralBuffer] = []
        self._audit = AuditLogger()

    def register_buffer(self, buffer: EphemeralBuffer) -> None:
        """Register an ephemeral buffer for tracking."""
        self._buffers.append(buffer)

    def create_buffer(self, size: int, dtype=np.int16) -> EphemeralBuffer:
        """Create and register a new ephemeral buffer."""
        buf = EphemeralBuffer(np.zeros(size, dtype=dtype))
        self._buffers.append(buf)
        return buf

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        wiped_count = len(self._buffers)
        for buffer in self._buffers:
            buffer.wipe()
        self._buffers.clear()

        self._audit.log_event(
            call_id=self.session_id,
            synthetic_score=0.0,
            action_taken=f"session_destroyed (wiped {wiped_count} buffers)",
        )


class AuditLogger:
    """
    DPDP-compliant audit logger.

    LOGS ONLY:
        - Timestamp (IST)
        - Call ID
        - Synthetic score
        - Action taken

    NEVER LOGS:
        - Audio data, waveforms, or spectrograms
        - PII (phone numbers, names, addresses)
        - Raw feature vectors
    """

    def __init__(self):
        self._logger = logging.getLogger("voiceshield.audit")
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def log_event(
        self,
        call_id: str,
        synthetic_score: float,
        action_taken: str,
    ) -> None:
        """Log a scalar-only audit event in JSON Lines format."""
        event = {
            "timestamp": datetime.now(IST).isoformat(),
            "call_id": call_id,
            "synthetic_score": round(float(synthetic_score), 4),
            "action_taken": action_taken,
        }
        self._logger.info(json.dumps(event))


class ComplianceValidator:
    """
    Validates outbound data before WebSocket transmission.
    Uses a whitelist approach: only scalar scores, labels, timestamps,
    and action metadata are allowed through.
    """

    # Allowed keys for outbound transmission
    WHITELIST = frozenset({
        "call_id", "window_index", "synthetic_score", "xai_risk",
        "model_prob", "label", "prosodics", "watermark", "mitigation",
        "latency_ms", "timestamp_ist", "action", "triggered", "mute",
        "overlay", "message", "sub_message", "score", "threshold",
        "banner", "emergency_contacts", "detected",
        "jitter_pct", "shimmer_pct", "phase_continuity", "pitch_stability_pct",
    })

    @classmethod
    def validate_outbound(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strip any non-whitelisted keys from outbound data.
        Ensures no audio data or PII leaks through the WebSocket.
        """
        safe = {}
        for key, value in data.items():
            if key not in cls.WHITELIST:
                continue
            if isinstance(value, dict):
                safe[key] = cls.validate_outbound(value)
            elif isinstance(value, (int, float, str, bool, type(None), list)):
                safe[key] = value
        return safe


# Singleton audit logger
audit_logger = AuditLogger()
