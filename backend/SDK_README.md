# VoiceShield AI — Python SDK

Integration SDK for the VoiceShield AI REST API (mirrors SIH26104's
"REST/gRPC APIs and SDKs for banking / contact-center / enterprise / telecom"
requirement). The gRPC-style contract is in [`sdk/voiceshield.proto`](sdk/voiceshield.proto);
the SDK below is the shipped HTTP implementation of that contract.

Dependencies: `httpx`, `websockets` (both already in `backend/requirements.txt`).

```bash
pip install -e backend            # or:  pip install httpx websockets
```

```python
from voiceshield_sdk import VoiceShieldClient

vs = VoiceShieldClient("http://127.0.0.1:8000")
r = vs.analyze(
    "call.wav",
    role="adult",
    context={"caller": "+919000000001", "origin": "telecom",
             "txn_value": 200000, "txn_category": "fund_transfer"},
)
print(r["risk_band"], r["recommended_actions"])
```

## 1. Bank — guard fund transfers (async)

```python
import asyncio
from voiceshield_sdk import AsyncVoiceShieldClient

async def main():
    vs = AsyncVoiceShieldClient("http://127.0.0.1:8000")
    r = await vs.analyze(
        "caller_intent.wav",
        role="adult",
        context={"caller": "+919000000001", "origin": "voip",
                 "txn_value": 500000, "txn_category": "fund_transfer"},
    )
    if r["risk_band"] in ("critical", "high"):
        print("HOLD transfer —", ", ".join(r["recommended_actions"]))
        incident = (await vs.incidents())[0]
        await vs.escalate(incident["id"], note="Fund transfer on hold")
    else:
        print("Proceed", r["peak_score"])

asyncio.run(main())
```

## 2. Contact center — escalate suspicious calls

```python
vs = VoiceShieldClient("http://127.0.0.1:8000")
for inc in vs.incidents():
    if not inc["acknowledged"] and inc["severity"] == "critical":
        ws_cfg = vs.workflows()          # operator-editable rules
        vs.acknowledge(inc["id"])
        pdf = vs.incident_report(inc["id"])   # I4C-ready forensic PDF
```

## 3. Telecom operator — live line monitoring (WebSocket)

```python
import asyncio
from voiceshield_sdk import AsyncLiveSession

async def monitor():
    async with AsyncLiveSession(
        "ws://127.0.0.1:8000", call_id="mbox-042", role="adult",
        caller="+919000000001", origin="telecom",
    ) as session:
        pcm = b"\x00" * 3200            # 100ms of silence (16k mono int16)
        async for event in session.events():
            if event.get("type") == "mitigation":
                print("ALERT", event["recommended_actions"])
                await session.finish()
                break

asyncio.run(monitor())
```

## Enrichment & workflows

- Contextual enrichment is **opt-in** (`CONTEXTUAL_ENRICHMENT=true` in
  `backend/.env`) and fail-open: no context supplied → acoustic score untouched.
- The webhook payload for every `dispatch_alerts` call now carries
  `recommended_actions` and `context` (when applied) so a banking middleware
  can trigger its own hold/MFA flow. Escalation of a confirmed incident posts to
  `WEBHOOK_URL` / `CHAKSHU_DIP_WEBHOOK_URL` with `escalation: true`.
- Workflows (`backend/workflows.json`) define band → actions/channels and are
  editable without a deploy; serve them via `GET /api/workflows`.