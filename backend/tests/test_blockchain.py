"""
VoiceShield AI — Blockchain Report Ledger Tests

Covers mining, anchoring, file integrity and API verification.
"""

import hashlib
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


# ── Mining / ledger helpers ────────────────────────────────────────────────

def _fake_pdf(path: str, content: bytes = b"Voiceshield forensic report mock\n"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)


from app.blockchain.ledger import settings

DIFFICULTY_TEST = 1


@pytest.fixture(autouse=True)
def _fast_mining(monkeypatch):
    monkeypatch.setattr(settings, "blockchain_difficulty", DIFFICULTY_TEST)
    from app import store
    store._execute("DELETE FROM blocks")


class TestMerkleRoot:
    def test_empty(self):
        from app.blockchain.ledger import merkle_root
        assert merkle_root([]) == hashlib.sha256(b"empty").hexdigest()

    def test_deterministic(self):
        from app.blockchain.ledger import merkle_root
        leaves = [10, 20, 30]
        a = merkle_root(leaves)
        b = merkle_root(leaves)
        assert a == b
        assert len(a) == 64

    def test_single_leaf(self):
        from app.blockchain.ledger import merkle_root
        h = merkle_root(["a"])
        assert len(h) == 64


class TestMining:
    def test_mine_success(self):
        from app.blockchain.ledger import mine_block, _recompute_block_hash
        block = mine_block(
            index=0, report_id="r", call_id="c", incident_id=None,
            file_sha256="a" * 64, merkle="b" * 64,
            prev_hash="0" * 64, difficulty=1,
        )
        assert block["block_hash"].startswith("0")
        assert block["block_hash"] == _recompute_block_hash(block)

    def test_mine_higher_index(self):
        from app.blockchain.ledger import mine_block
        block = mine_block(
            index=3, report_id="r3", call_id="c3", incident_id=None,
            file_sha256="1" * 64, merkle="2" * 64,
            prev_hash="3" * 64, difficulty=2,
        )
        assert block["block_hash"].startswith("00")
        assert block["block_index"] == 3


class TestAnchorAndVerify:
    def test_anchor_then_verify_valid(self):
        from app.blockchain import ledger
        from app import store
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            _fake_pdf(pdf, b"legitimate content")
            block = ledger.anchor_report(
                call_id="verify-001",
                report_id="F-verify-001",
                incident_id=None,
                file_path=pdf,
                window_leaves=[{"t": 0, "s": 0.5}, {"t": 100, "s": 0.8}],
            )
            assert block["block_index"] >= 0
            result = ledger.verify_report("verify-001")
            assert result["valid"] is True
            assert result["current_file_sha256"] == result["anchored_file_sha256"]
            assert len(result["problems"]) == 0

    def test_tamper_detected(self):
        from app.blockchain import ledger
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "tamper.pdf")
            _fake_pdf(pdf, b"original content")
            ledger.anchor_report(
                call_id="tamper-001", report_id="F-tamper",
                incident_id=None, file_path=pdf, window_leaves=[],
            )
            # Tamper with file
            _fake_pdf(pdf, b"MODIFIED content")
            result = ledger.verify_report("tamper-001")
            assert result["valid"] is False
            assert any("tamper" in p.lower() for p in result["problems"])

    def test_missing_file_detected(self):
        from app.blockchain import ledger
        pdf = "/tmp/nonexistent_voiceshield_test.pdf"
        ledger.anchor_report(
            call_id="missing-001", report_id="F-missing",
            incident_id=None, file_path=pdf, window_leaves=[],
        )
        result = ledger.verify_report("missing-001")
        assert result["valid"] is False
        assert any("missing" in p.lower() for p in result["problems"])

    def test_no_anchor_returns_error(self):
        from app.blockchain import ledger
        result = ledger.verify_report("never-existed")
        assert result["valid"] is False
        assert "no blockchain anchor" in result["error"].lower()


class TestChainIntegrity:
    def test_two_blocks_chain(self):
        from app.blockchain import ledger
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.pdf")
            p2 = os.path.join(tmp, "b.pdf")
            _fake_pdf(p1, b"first")
            _fake_pdf(p2, b"second")
            ledger.anchor_report(call_id="c1", report_id="r1", incident_id=None,
                                 file_path=p1, window_leaves=[1])
            ledger.anchor_report(call_id="c2", report_id="r2", incident_id=None,
                                 file_path=p2, window_leaves=[2])
        chain = ledger.verify_chain()
        assert chain["height"] >= 2
        assert chain["valid"] is True
        assert chain["blocks"][0]["valid"] is True
        assert chain["blocks"][1]["valid"] is True


# ── API tests ──────────────────────────────────────────────────────────────

class TestBlockchainAPI:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.main import app
        self.client = TestClient(app)

    def test_chain_status(self):
        r = self.client.get("/api/blockchain")
        assert r.status_code == 200
        body = r.json()
        assert body["chain_id"] == "VoiceShieldAIV1"
        assert "height" in body

    def test_verify_nonexistent_returns_404(self):
        r = self.client.get("/api/blockchain/verify/call/ghost-never-existed")
        assert r.status_code == 200  # graceful response with valid=false
        body = r.json()
        assert body["valid"] is False

    def test_verify_existing_block(self):
        from app.blockchain import ledger
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "api_test.pdf")
            _fake_pdf(pdf, b"api anchor content")
            ledger.anchor_report(
                call_id="api-001", report_id="F-api-001",
                incident_id=None, file_path=pdf, window_leaves=[],
            )
            # Full verification
            r = self.client.get("/api/blockchain/verify/call/api-001")
            assert r.status_code == 200
            assert r.json()["valid"] is True

            # Block-level verification
            r2 = self.client.get("/api/blockchain/verify/block/0")
            assert r2.status_code == 200
            assert r2.json()["valid"] is True
