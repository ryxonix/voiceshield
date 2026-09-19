"""
VoiceShield AI — HTTP clients (sync + async).

Both clients are thin wrappers over httpx. Optional `transport` lets callers
inject an ASGI transport for in-process testing.
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, Optional

import httpx


class _BaseClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 20.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport

    @staticmethod
    def _context_form(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Map a context dict to the /api/analyze form fields."""
        if not context:
            return {}
        data: Dict[str, Any] = {}
        for key in ("caller", "origin", "txn_value", "txn_category"):
            if context.get(key) not in (None, ""):
                data[key] = context[key]
        if context.get("known_contact") is not None:
            data["known_contact"] = "true" if context["known_contact"] else "false"
        if context.get("prior_flags"):
            data["prior_flags"] = int(context["prior_flags"])
        return data

    @staticmethod
    def _files_for(
        path: Optional[str],
        data: Optional[bytes],
        filename: Optional[str],
        mime: str = "audio/wav",
    ) -> Dict[str, Any]:
        if path is not None:
            return {"file": (filename or os.path.basename(path), open(path, "rb"), mime)}
        if data is not None:
            return {"file": (filename or "audio.wav", io.BytesIO(data), mime)}
        return {}


class VoiceShieldClient(_BaseClient):
    """
    Synchronous VoiceShield AI client.

    Example:
        client = VoiceShieldClient("http://127.0.0.1:8000")
        result = client.analyze("call.wav", role="adult")
    """

    def _request(self, method: str, path: str, **kwargs) -> dict:
        with httpx.Client(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()

    # ── System ─────────────────────────────────────────────────
    def health(self) -> dict:
        return self._request("GET", "/health")

    def workflows(self) -> dict:
        return self._request("GET", "/api/workflows")

    # ── Detection ──────────────────────────────────────────────
    def detect(self, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return self._request(
            "POST", "/api/detect", params={"language": language}, files=files or None
        )

    def analyze(
        self,
        audio_path=None,
        audio_bytes=None,
        role: str = "adult",
        context: Optional[Dict[str, Any]] = None,
        filename=None,
    ) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return self._request(
            "POST",
            "/api/analyze",
            params={"role": role},
            files=files or None,
            data=self._context_form(context) or None,
        )

    # ── Sessions ───────────────────────────────────────────────
    def sessions(self, limit: int = 50) -> list:
        return self._request("GET", "/api/sessions", params={"limit": limit})

    def session(self, sid: str) -> dict:
        return self._request("GET", f"/api/sessions/{sid}")

    def session_windows(self, sid: str) -> list:
        return self._request("GET", f"/api/sessions/{sid}/windows")

    # ── Incidents + workflows ──────────────────────────────────
    def incidents(self, limit: int = 50) -> list:
        return self._request("GET", "/api/incidents", params={"limit": limit})

    def incident(self, iid: str) -> dict:
        return self._request("GET", f"/api/incidents/{iid}")

    def acknowledge(self, iid: str) -> dict:
        return self._request("POST", f"/api/incidents/{iid}/ack")

    def escalate(self, iid: str, note: str = "") -> dict:
        return self._request("POST", f"/api/incidents/{iid}/escalate", data={"note": note})

    def incident_report(self, iid: str) -> bytes:
        with httpx.Client(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = client.get(f"/api/incidents/{iid}/report")
            resp.raise_for_status()
            return resp.content

    # ── Tamper-evident ledger (NBF anchor) ─────────────────────
    def blockchain_status(self) -> dict:
        return self._request("GET", "/api/blockchain")

    def onchain(self, call_id: Optional[str] = None) -> dict:
        path = "/api/blockchain/onchain" if call_id is None else f"/api/blockchain/onchain/{call_id}"
        return self._request("GET", path)

    def verify_call(self, call_id: str) -> dict:
        return self._request("GET", f"/api/blockchain/verify/call/{call_id}")

    def retry_anchor(self, call_id: str) -> dict:
        return self._request("POST", f"/api/blockchain/retry/{call_id}")

    def report(self, call_id: str) -> bytes:
        with httpx.Client(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = client.get(f"/api/report/{call_id}")
            resp.raise_for_status()
            return resp.content

    # ── Speaker enrollment ─────────────────────────────────────
    def register_speaker(self, label: str, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return self._request(
            "POST",
            "/api/speakers/register",
            params={"label": label, "language": language},
            files=files or None,
        )


class AsyncVoiceShieldClient(_BaseClient):
    """Asynchronous VoiceShield AI client (same surface as the sync one)."""

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict:
        return await self._request("GET", "/health")

    async def workflows(self) -> dict:
        return await self._request("GET", "/api/workflows")

    async def detect(self, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return await self._request(
            "POST", "/api/detect", params={"language": language}, files=files or None
        )

    async def analyze(
        self,
        audio_path=None,
        audio_bytes=None,
        role: str = "adult",
        context: Optional[Dict[str, Any]] = None,
        filename=None,
    ) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return await self._request(
            "POST",
            "/api/analyze",
            params={"role": role},
            files=files or None,
            data=self._context_form(context) or None,
        )

    async def sessions(self, limit: int = 50) -> list:
        return await self._request("GET", "/api/sessions", params={"limit": limit})

    async def session(self, sid: str) -> dict:
        return await self._request("GET", f"/api/sessions/{sid}")

    async def session_windows(self, sid: str) -> list:
        return await self._request("GET", f"/api/sessions/{sid}/windows")

    async def incidents(self, limit: int = 50) -> list:
        return await self._request("GET", "/api/incidents", params={"limit": limit})

    async def incident(self, iid: str) -> dict:
        return await self._request("GET", f"/api/incidents/{iid}")

    async def acknowledge(self, iid: str) -> dict:
        return await self._request("POST", f"/api/incidents/{iid}/ack")

    async def escalate(self, iid: str, note: str = "") -> dict:
        return await self._request("POST", f"/api/incidents/{iid}/escalate", data={"note": note})

    async def incident_report(self, iid: str) -> bytes:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = await client.get(f"/api/incidents/{iid}/report")
            resp.raise_for_status()
            return resp.content

    async def blockchain_status(self) -> dict:
        return await self._request("GET", "/api/blockchain")

    async def onchain(self, call_id: Optional[str] = None) -> dict:
        path = "/api/blockchain/onchain" if call_id is None else f"/api/blockchain/onchain/{call_id}"
        return await self._request("GET", path)

    async def verify_call(self, call_id: str) -> dict:
        return await self._request("GET", f"/api/blockchain/verify/call/{call_id}")

    async def retry_anchor(self, call_id: str) -> dict:
        return await self._request("POST", f"/api/blockchain/retry/{call_id}")

    async def report(self, call_id: str) -> bytes:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            resp = await client.get(f"/api/report/{call_id}")
            resp.raise_for_status()
            return resp.content

    async def register_speaker(self, label: str, audio_path=None, audio_bytes=None, language="auto", filename=None) -> dict:
        files = self._files_for(audio_path, audio_bytes, filename)
        return await self._request(
            "POST",
            "/api/speakers/register",
            params={"label": label, "language": language},
            files=files or None,
        )