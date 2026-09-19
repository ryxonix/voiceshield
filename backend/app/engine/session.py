"""
VoiceShield AI — Session State Manager
Manages per-call session state with DPDP-compliant memory lifecycle.
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from app.engine.features import ProsodicsResult
from app.engine.fusion import FusionResult

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class SessionState:
    """State for a single active call session."""
    call_id: str
    role: str                            # 'adult' or 'child'
    start_time: datetime
    peak_score: float = 0.0
    peak_prosodics: Optional[Dict] = None
    window_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_action: str = "none"
    _max_history: int = 50


class SessionManager:
    """
    Thread-safe session manager for active call sessions.
    All operations are async-safe via asyncio.Lock.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(self, call_id: str, role: str) -> SessionState:
        """Create a new session for a call."""
        async with self._lock:
            state = SessionState(
                call_id=call_id,
                role=role,
                start_time=datetime.now(IST),
            )
            self._sessions[call_id] = state
            logger.info(f"Session created: {call_id} (role={role})")
            return state

    def get(self, call_id: str) -> Optional[SessionState]:
        """Get a session by call ID (synchronous for read)."""
        return self._sessions.get(call_id)

    async def update(
        self,
        call_id: str,
        result: FusionResult,
        prosodics: ProsodicsResult,
        window_index: int = 0,
    ) -> None:
        """Update session with a new detection result."""
        async with self._lock:
            state = self._sessions.get(call_id)
            if state is None:
                return

            state.window_count += 1

            # Record in history (capped at _max_history)
            entry = {
                "window_index": window_index,
                "synthetic_score": result.synthetic_score,
                "xai_risk": result.xai_risk,
                "model_prob": result.model_prob,
                "label": result.label,
                "timestamp": datetime.now(IST).isoformat(),
            }
            state.history.append(entry)
            if len(state.history) > state._max_history:
                state.history.pop(0)

            # Track peak score
            if result.synthetic_score > state.peak_score:
                state.peak_score = result.synthetic_score
                state.peak_prosodics = prosodics.to_dict()

    async def set_action(self, call_id: str, action: str) -> None:
        """Record the last mitigation action taken."""
        async with self._lock:
            state = self._sessions.get(call_id)
            if state:
                state.last_action = action

    async def destroy(self, call_id: str) -> None:
        """
        Destroy a session and wipe all data from memory.
        DPDP compliance: ensures no audio metadata persists after call ends.
        """
        async with self._lock:
            if call_id in self._sessions:
                state = self._sessions.pop(call_id)
                # Explicitly clear history list
                state.history.clear()
                state.peak_prosodics = None
                logger.info(f"Session destroyed: {call_id} (DPDP wiped)")

    async def destroy_all(self) -> None:
        """Destroy all sessions (called during shutdown)."""
        async with self._lock:
            for call_id in list(self._sessions.keys()):
                state = self._sessions.pop(call_id)
                state.history.clear()
            logger.info("All sessions destroyed (shutdown)")


# Singleton instance
session_manager = SessionManager()
