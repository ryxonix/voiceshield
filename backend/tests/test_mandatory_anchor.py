"""
VoiceShield AI — MANDATORY NBF/Fabric Anchor (fail-closed) tests

Locks the mandated posture (about project.txt §7 / README "NBF anchor"):
BLOCKCHAIN_EXTERNAL_ANCHOR=true + BLOCKCHAIN_ANCHOR_REQUIRED=true means a
forensic report is committed to the local PoW ledger ONLY after a real
on-chain anchor succeeded — no demo provider, no 'pending' downgrade, no
unanchored block, and the REST/gRPC surfaces refuse (503 / UNAVAILABLE)
instead of handing off unanchored evidence.

The default offline suite pins fail-open posture via the autouse
`_default_offline_blockchain` fixture in tests/conftest.py (it runs FIRST);
every test below opts back into mandatory mode explicitly in its own body.

Covers, per the todo plan:
  1. demo provider + required  -> BlockAnchorError, nothing persisted,
     verify_report says no blockchain anchor / valid=False.
  2. external + required + gateway DOWN -> same fail-closed refusal.
  3. external + required + gateway UP   -> block committed, anchored,
     verify_report valid=True with external_anchor.anchor_status='anchored'.
  4. REST POST /api/blockchain/retry -> 503 while mandated+gateway down,
     200 once the gateway recovers.
  5. REST GET  /api/report/{call_id} -> 503 "Report NOT blockchain-anchored"
     when the anchor is mandated and the gateway is down.
  6. gRPC RetryAnchor -> StatusCode.UNAVAILABLE (never a successful retry).
"""

import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings

# Fixtures live in the shared helper module; importing them registers them
# for THIS module (fast mining difficulty + clean blocks/block_anchors).
from tests.blockchaintest_helpers import _clean_ledger, _fake_pdf, patch_httpx  # noqa: F401

GW = "http://nbf-gateway.test:4000"
CID = "Qm" + "0" * 44  # structurally plausible fake CID (46 chars)


# ── Helpers ────────────────────────────────────────────────────────────────

def _mandate(tmp_path, monkeypatch, *, external=True, required=True, gateway=GW):
    """Pin the fail-closed posture + offline-safe key dir for a test."""
    monkeypatch.setattr(settings, "blockchain_external_anchor", external)
    monkeypatch.setattr(settings, "blockchain_anchor_required", required)
    monkeypatch.setattr(settings, "nbf_gateway_url", gateway)
    monkeypatch.setattr(settings, "report_keys_dir", str(tmp_path))


def _gateway_down(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, json={"error": "NBF gateway down"})


def _gateway_up(state: dict):
    """Success routes for /store, /fabric/v1/invokecc, /health, querycc,
    retrieve — `state['block']` / `state['cipher']` feed the verify leg."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        if "querycc" in path:
            b = state["block"]
            payload = {
                "call_id": b["call_id"],
                "report_id": b["report_id"],
                "block_hash": b["block_hash"],
                "file_sha256": b["file_sha256"],
                "merkle_root": b["merkle_root"],
                "timestamp": b["timestamp"],
                "ipfs_cid": CID,
                "enc_alg": "AES-256-GCM",
            }
            return httpx.Response(200, json={"result": json.dumps(payload)})
        if "retrieve" in path:
            return httpx.Response(200, json={"data": state["cipher"]})
        if path.endswith("/store"):
            return httpx.Response(200, json={"hash": CID})
        if "invokecc" in path:
            return httpx.Response(200, json={"tx_id": "tx-mand-ok-1"})
        return httpx.Response(500, json={"error": f"unexpected {path}"})

    return handler


def _pdf(tmp_path, name="report.pdf") -> str:
    path = os.path.join(str(tmp_path), name)
    _fake_pdf(path, b"%PDF-1.4 VoiceShield mandatory-anchor test report\n")
    return path


def _cipher_for(pdf_path: str, call_id: str) -> str:
    from app.blockchain import external_anchor as ea

    key = ea._derive_report_key(ea._load_or_create_master_key(), call_id)
    return ea.encrypt_pdf(pdf_path, key)["cipher_b64"]


# ── 1. Demo provider is rejected under the mandate ────────────────────────

class TestDemoRejectedWhenRequired:
    def test_anchor_raises_and_nothing_persists(self, tmp_path, monkeypatch):
        from app import store
        from app.blockchain import ledger
        from app.blockchain.external_anchor import BlockAnchorError

        # Demo provider (external OFF) but anchor MANDATED -> refuse.
        _mandate(tmp_path, monkeypatch, external=False, required=True)
        pdf = _pdf(tmp_path)

        with pytest.raises(BlockAnchorError) as exc:
            ledger.anchor_report(
                call_id="mand-demo-1", report_id="F-mand-demo",
                incident_id=None, file_path=pdf, window_leaves=[{"s": 0.5}],
            )
        assert exc.value.provider == "demo"

        # Fail-closed: no block row, no anchor row.
        assert store.get_block_by_call("mand-demo-1") is None
        assert store.get_block_anchor_by_call("mand-demo-1") is None

        rep = ledger.verify_report("mand-demo-1")
        assert rep["valid"] is False
        assert "no blockchain anchor" in rep["error"].lower()

    def test_subsequent_successful_anchor_still_works(self, tmp_path, monkeypatch):
        """The refusal is per-call, not a permanently wedged ledger."""
        from app import store
        from app.blockchain import ledger
        from app.blockchain.external_anchor import BlockAnchorError

        _mandate(tmp_path, monkeypatch, external=False, required=True)
        with pytest.raises(BlockAnchorError):
            ledger.anchor_report(
                call_id="mand-demo-2a", report_id="F-a",
                incident_id=None, file_path=_pdf(tmp_path, "a.pdf"),
                window_leaves=None,
            )
        assert store.get_block_by_call("mand-demo-2a") is None

        # Mandate released (e.g. operator switches to the real gateway later):
        monkeypatch.setattr(settings, "blockchain_anchor_required", False)
        block = ledger.anchor_report(
            call_id="mand-demo-2b", report_id="F-b",
            incident_id=None, file_path=_pdf(tmp_path, "b.pdf"),
            window_leaves=None,
        )
        assert store.get_block_by_call("mand-demo-2b") is not None
        assert block["external_anchor"]["anchor_status"] == "demo"


# ── 2. Gateway DOWN under the mandate ─────────────────────────────────────

class TestGatewayDownWhenRequired:
    def test_anchor_raises_and_verify_reports_not_anchored(self, tmp_path, monkeypatch):
        from app import store
        from app.blockchain import ledger
        from app.blockchain.external_anchor import BlockAnchorError

        _mandate(tmp_path, monkeypatch, external=True, required=True)
        patch_httpx(monkeypatch, _gateway_down)
        pdf = _pdf(tmp_path)

        with pytest.raises(BlockAnchorError) as exc:
            ledger.anchor_report(
                call_id="mand-down-1", report_id="F-mand-down",
                incident_id=None, file_path=pdf, window_leaves=None,
            )
        assert "mandatory" in str(exc.value).lower() or "FAILED" in str(exc.value)

        assert store.get_block_by_call("mand-down-1") is None
        assert store.get_block_anchor_by_call("mand-down-1") is None

        rep = ledger.verify_report("mand-down-1")
        assert rep["valid"] is False
        assert "no blockchain anchor" in rep["error"].lower()


# ── 3. Gateway UP under the mandate ───────────────────────────────────────

class TestGatewayUpWhenRequired:
    def test_full_anchor_and_verify_roundtrip(self, tmp_path, monkeypatch):
        from app import store
        from app.blockchain import ledger

        _mandate(tmp_path, monkeypatch, external=True, required=True)
        pdf = _pdf(tmp_path)
        call_id = "mand-up-1"
        state: dict = {"block": None, "cipher": _cipher_for(pdf, call_id)}
        patch_httpx(monkeypatch, _gateway_up(state))

        block = ledger.anchor_report(
            call_id=call_id, report_id="F-mand-up", incident_id=None,
            file_path=pdf, window_leaves=[{"t": 0, "s": 0.42}],
        )

        assert block["external_anchor"]["anchor_status"] == "anchored"
        assert block["external_anchor"]["ipfs_cid"] == CID
        assert block["external_anchor"]["tx_id"] == "tx-mand-ok-1"

        stored = store.get_block_by_call(call_id)
        assert stored is not None, "mandated+successful anchor must commit the block"
        anchor_row = store.get_block_anchor_by_call(call_id)
        assert anchor_row["anchor_status"] == "anchored"
        assert anchor_row["ipfs_cid"] == CID

        state["block"] = stored
        rep = ledger.verify_report(call_id)
        assert rep["valid"] is True, rep.get("problems")
        assert rep["problems"] == []
        assert rep["external_anchor"]["anchor_status"] == "anchored"


# ── 4. REST retry: 503 while down, 200 when recovered ─────────────────────

class TestRestRetryAnchor:
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def _seed_pending(self, tmp_path, monkeypatch, call_id: str) -> str:
        """Fail-open seed (mandate OFF, gateway down) -> 'pending' anchor row."""
        from app.blockchain import ledger

        _mandate(tmp_path, monkeypatch, external=True, required=False)
        patch_httpx(monkeypatch, _gateway_down)
        pdf = _pdf(tmp_path, f"{call_id}.pdf")
        block = ledger.anchor_report(
            call_id=call_id, report_id=f"F-{call_id}",
            incident_id=None, file_path=pdf, window_leaves=None,
        )
        assert block["external_anchor"]["anchor_status"] == "pending"
        return pdf

    def test_retry_503_then_200_on_recovery(self, tmp_path, monkeypatch, client):
        call_id = "mand-retry-rest"
        self._seed_pending(tmp_path, monkeypatch, call_id)

        # Flip to mandatory while the gateway is still down -> 503.
        monkeypatch.setattr(settings, "blockchain_anchor_required", True)
        r = client.post(f"/api/blockchain/retry/{call_id}")
        assert r.status_code == 503, r.text
        body = r.json()
        assert "not blockchain-anchored" in body["error"]
        assert "BLOCKCHAIN_ANCHOR_REQUIRED" in body["detail"]

        # Gateway recovers -> retry anchors on-chain -> 200.
        from app import store
        state: dict = {"block": store.get_block_by_call(call_id), "cipher": None}
        state["cipher"] = _cipher_for(state["block"]["file_path"], call_id)
        patch_httpx(monkeypatch, _gateway_up(state))

        r2 = client.post(f"/api/blockchain/retry/{call_id}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["anchor_status"] == "anchored"

        from app import store as st
        assert st.get_block_anchor_by_call(call_id)["anchor_status"] == "anchored"

    def test_retry_demo_400_only_when_not_required(self, tmp_path, monkeypatch, client):
        """Demo + NOT required -> 400 (disabled); the demo check must not fire
        when the anchor is mandated (it would mask the real 503 path)."""
        from app.blockchain import ledger

        _mandate(tmp_path, monkeypatch, external=False, required=False)
        # Seed a demo block so the 400 is not just the 404 no-block path.
        ledger.anchor_report(
            call_id="mand-demo-retry", report_id="F-demo-retry",
            incident_id=None, file_path=_pdf(tmp_path, "dr.pdf"),
            window_leaves=None,
        )
        r = client.post("/api/blockchain/retry/mand-demo-retry")
        assert r.status_code == 400
        assert "disabled" in r.json()["error"].lower()


# ── 5. REST forensic report: 503 when the anchor cannot be made ───────────

class TestRestReportRefusesUnanchored:
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _telemetry(self, tmp_path):
        """Persist session telemetry so /api/report gets past the 404 guard."""
        from app import store
        call_id = "mand-report-1"
        store.create_session(call_id, role="adult", language="en")
        store.add_window(
            session_id=call_id, t_ms=0, model_prob=0.61, xai_risk=0.58,
            synthetic_score=0.64, jitter_pct=2.1, shimmer_pct=3.4,
            phase_continuity=0.91, pitch_stability=87.5,
            noise_floor_dropouts=0, watermark_hit=False, verdict="bonafide",
        )
        yield
        # The endpoint writes the PDF before anchoring; never leave it behind.
        pdf = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports", f"VoiceShield_Forensic_Report_{call_id}.pdf",
        )
        if os.path.exists(pdf):
            os.remove(pdf)

    def test_report_503_when_mandatory_anchor_unavailable(self, tmp_path, monkeypatch, client):
        from app import store

        _mandate(tmp_path, monkeypatch, external=True, required=True)
        patch_httpx(monkeypatch, _gateway_down)

        r = client.get("/api/report/mand-report-1")
        assert r.status_code == 503, r.text
        body = r.json()
        assert "Report NOT blockchain-anchored" in body["error"]
        assert "BLOCKCHAIN_ANCHOR_REQUIRED" in body["detail"]

        # Fail-closed: still no block for this call.
        assert store.get_block_by_call("mand-report-1") is None

    def test_report_200_when_anchor_succeeds(self, tmp_path, monkeypatch, client):
        from app import store

        _mandate(tmp_path, monkeypatch, external=True, required=True)
        call_id = "mand-report-1"
        state: dict = {"block": None, "cipher": None}
        patch_httpx(monkeypatch, _gateway_up(state))

        r = client.get(f"/api/report/{call_id}")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"

        stored = store.get_block_by_call(call_id)
        assert stored is not None
        assert store.get_block_anchor_by_call(call_id)["anchor_status"] == "anchored"


# ── 6. gRPC RetryAnchor maps BlockAnchorError -> UNAVAILABLE ──────────────

class _FakeServicerContext:
    """Minimal gRPC servicer context capturing code/details."""

    def __init__(self):
        self.code = None
        self.details = None

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details = details

    def abort(self, code, details):
        self.set_code(code)
        self.set_details(details)
        raise RuntimeError(f"aborted: {code} {details}")


class TestGrpcRetryAnchorUnavailable:
    def test_unavailable_when_mandated_anchor_fails(self, tmp_path, monkeypatch):
        import grpc

        from app import store
        from app.blockchain import ledger
        from app.grpc.servicer import VoiceShield
        from app.grpc.voiceshield_pb2 import RetryAnchorRequest

        # Fail-open seed -> pending block (retryable).
        _mandate(tmp_path, monkeypatch, external=True, required=False)
        patch_httpx(monkeypatch, _gateway_down)
        ledger.anchor_report(
            call_id="mand-retry-grpc", report_id="F-grpc-retry",
            incident_id=None, file_path=_pdf(tmp_path, "gr.pdf"),
            window_leaves=None,
        )
        assert store.get_block_anchor_by_call("mand-retry-grpc")["anchor_status"] == "pending"

        # Mandate ON, gateway still down -> UNAVAILABLE, empty result.
        monkeypatch.setattr(settings, "blockchain_anchor_required", True)
        servicer = VoiceShield()
        ctx = _FakeServicerContext()
        resp = servicer.RetryAnchor(
            RetryAnchorRequest(call_id="mand-retry-grpc"), ctx
        )

        assert ctx.code == grpc.StatusCode.UNAVAILABLE
        assert "not blockchain-anchored" in (ctx.details or "")
        assert dict(resp.result) == {}
        # Still pending — a failed mandated retry never claims success.
        assert store.get_block_anchor_by_call("mand-retry-grpc")["anchor_status"] == "pending"

    def test_not_found_for_unknown_call(self):
        import grpc

        from app.grpc.servicer import VoiceShield
        from app.grpc.voiceshield_pb2 import RetryAnchorRequest

        servicer = VoiceShield()
        ctx = _FakeServicerContext()
        servicer.RetryAnchor(RetryAnchorRequest(call_id="never-existed-xyz"), ctx)
        assert ctx.code == grpc.StatusCode.NOT_FOUND
