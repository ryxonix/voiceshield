"""
VoiceShield AI — SDK Smoke Tests

Exercises the sync/async HTTP clients against an in-process ASGI transport and
the WebSocket session contract (without a real network). Also verifies the
incident-escalation → caller-reputation path wired through the client.
"""

import asyncio
import io
import os
import sys

import httpx
import pytest

sys.path.insert(
    0,
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sdk")),
)


@pytest.fixture(scope="module")
def app():
    import app.main as main
    return main.app


@pytest.fixture(autouse=True)
def _clean():
    from app import store
    store._execute("DELETE FROM incidents")
    store._execute("DELETE FROM caller_reputation")
    yield


def _wav_bytes(duration_s: float = 1.0, sr: int = 16000) -> bytes:
    import numpy as np
    import soundfile as sf
    # Silence, so the fallback AASIST-L path returns a benign low score.
    pcm = np.zeros(int(sr * duration_s), dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def test_async_health(app):
    from voiceshield_sdk import AsyncVoiceShieldClient
    transport = httpx.ASGITransport(app=app)

    async def _run():
        client = AsyncVoiceShieldClient("http://testserver", transport=transport)
        return await client.health()

    result = asyncio.run(_run())
    assert result["status"] == "healthy"


def test_async_workflows(app):
    from voiceshield_sdk import AsyncVoiceShieldClient
    transport = httpx.ASGITransport(app=app)

    async def _run():
        client = AsyncVoiceShieldClient("http://testserver", transport=transport)
        return await client.workflows()

    result = asyncio.run(_run())
    assert result.get("version") == 1
    assert len(result.get("rules", [])) > 0


def test_async_analyze_shapes(app):
    from voiceshield_sdk import AsyncVoiceShieldClient
    transport = httpx.ASGITransport(app=app)

    async def _run():
        client = AsyncVoiceShieldClient("http://testserver", transport=transport)
        return await client.analyze(
            audio_bytes=_wav_bytes(),
            role="adult",
            context={"caller": "+919000000001", "txn_value": 500},
            filename="silence.wav",
        )

    result = asyncio.run(_run())
    assert "peak_score" in result
    assert "risk_band" in result
    assert "recommended_actions" in result
    assert "windows" in result


def test_escalate_bumps_reputation(app):
    from app import store
    from voiceshield_sdk import AsyncVoiceShieldClient
    transport = httpx.ASGITransport(app=app)

    iid = "ESCALATE1"
    store.add_incident(
        iid=iid,
        session_id="call-esc",
        role="adult",
        language="en",
        severity="high",
        score=0.93,
        triggers=["score>=adult_threshold"],
        speaker_mismatch=False,
        context_json='{"caller": "+91bad"}',
    )

    async def _run():
        client = AsyncVoiceShieldClient("http://testserver", transport=transport)
        return await client.escalate(iid, note="confirmed fraud")

    result = asyncio.run(_run())
    assert result["escalated"] is True
    assert result["caller_flag_count"] >= 1
    assert store.get_caller_flags("+91bad") >= 1


def test_sync_incidents_roundtrip(app):
    from app import store
    from voiceshield_sdk import VoiceShieldClient
    transport = httpx.ASGITransport(app=app)

    store.add_incident(
        iid="SYNC1",
        session_id="call-sync",
        role="adult",
        language="en",
        severity="high",
        score=0.9,
        triggers=["score>=adult_threshold"],
        speaker_mismatch=False,
        base_score=0.9,
        context_json='{"caller": "+91x"}',
    )

    async def _run():
        from voiceshield_sdk import AsyncVoiceShieldClient
        client = AsyncVoiceShieldClient("http://testserver", transport=httpx.ASGITransport(app=app))
        incidents = await client.incidents()
        assert any(i["id"] == "SYNC1" for i in incidents)
        detail = await client.incident("SYNC1")
        assert detail["base_score"] == detail["score"]

    asyncio.run(_run())


def test_live_session_query_contains_context(app):
    from voiceshield_sdk import AsyncLiveSession
    session = AsyncLiveSession(
        "ws://testserver", call_id="c9", role="adult",
        caller="+919000000001", origin="telecom", txn_value=200000,
    )
    assert "caller=%2B919000000001" in session.url
    assert "origin=telecom" in session.url
    assert "txn_value=200000" in session.url
    assert "role=adult" in session.url