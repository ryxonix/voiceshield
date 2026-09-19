"""
VoiceShield AI — Real-time streaming session (WebSocket).

Mirrors the repo's `ws://host/ws/stream/{call_id}` streaming contract: send raw
PCM 16k mono int16 chunks, receive JSON scalar analysis events. Raw audio never
leaves the caller's process as decoded data — only the PCM you send and the
scalar scores you receive (DPDP-safe by design).
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import urlencode

import websockets


class AsyncLiveSession:
    """
    Async WebSocket live call session.

    Example:
        async with AsyncLiveSession("ws://127.0.0.1:8000", call_id="c1",
                                     role="adult", caller="+919000000001",
                                     origin="telecom") as session:
            await session.send_frame(b"\\x00" * 3200)
            async for event in session.events():
                print(event["synthetic_score"])
    """

    def __init__(
        self,
        base_url: str = "ws://127.0.0.1:8000",
        call_id: str = "sdk-call",
        role: str = "adult",
        language: str = "auto",
        speaker: str = "",
        caller: str = "",
        origin: str = "",
        txn_value: float = 0.0,
        txn_category: str = "",
    ) -> None:
        base = base_url.replace("http://", "ws://").replace("https://", "wss://")
        query = urlencode(
            {
                "role": role,
                "language": language,
                "speaker": speaker,
                "caller": caller,
                "origin": origin,
                "txn_value": txn_value,
                "txn_category": txn_category,
            }
        )
        self.url = f"{base}/ws/stream/{call_id}?{query}"
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    async def __aenter__(self) -> "AsyncLiveSession":
        self._ws = await websockets.connect(self.url)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None

    async def send_frame(self, pcm_bytes: bytes) -> None:
        """Send one chunk of raw PCM 16-bit mono at 16 kHz."""
        if self._ws is None:
            raise RuntimeError("session not connected")
        await self._ws.send(pcm_bytes)

    async def finish(self) -> None:
        """Gracefully end the call (server wipes the session buffer)."""
        if self._ws is None:
            raise RuntimeError("session not connected")
        await self._ws.send(json.dumps({"type": "end"}))

    async def events(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Yield analysis + mitigation events until the server closes the stream.
        Each event carries only scalars (see /ws/stream contract).
        """
        if self._ws is None:
            raise RuntimeError("session not connected")
        async for raw in self._ws:
            if isinstance(raw, bytes):
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                continue