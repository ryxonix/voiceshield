"""
VoiceShield AI — Official Client SDK.

Thin, dependency-light (httpx + websockets only) REST + streaming client so
banks, contact centers, enterprise comms, and telecom operators can integrate
VoiceShield AI's voice-integrity checks into their own applications —
mirroring the SIH26104 "REST/gRPC APIs and SDKs" requirement.

Integrates with:
  - detection                 /api/detect, /api/analyze
  - real-time streaming       ws://host/ws/stream/{call_id}
  - incidents                 /api/incidents*
  - configurable workflows    /api/workflows
  - tamper-evident blockchain /api/blockchain*, /api/report/{call_id}
  - speaker enrollment        /api/speakers/register
"""

from .client import VoiceShieldClient, AsyncVoiceShieldClient
from .live import AsyncLiveSession

__version__ = "0.1.0"

__all__ = [
    "VoiceShieldClient",
    "AsyncVoiceShieldClient",
    "AsyncLiveSession",
]