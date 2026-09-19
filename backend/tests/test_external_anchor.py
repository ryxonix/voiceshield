"""
VoiceShield AI — External (NBF-Fabric / IPFS) Anchor Tests

Covers AES-256-GCM encryption roundtrip, key derivation/fingerprints, the
fail-open DemoAnchor fallback and API exposure of anchor state.
"""

import json
import os
import tempfile

import httpx
import pytest


@pytest.fixture(autouse=True)
def _clean_db():
    from app import store
    store._execute("DELETE FROM block_anchors")
    yield


class TestCrypto:
    def test_derive_key_is_64_hex(self):
        from app.blockchain.external_anchor import _derive_report_key
        key = _derive_report_key(b"0" * 32, "call-test-1")
        assert len(key) == 32

    def test_derive_key_differs_by_call(self):
        from app.blockchain.external_anchor import _derive_report_key
        a = _derive_report_key(b"0" * 32, "call-a")
        b = _derive_report_key(b"0" * 32, "call-b")
        assert a != b

    def test_fingerprint_stable_and_short(self):
        from app.blockchain.external_anchor import key_fingerprint
        master = b"m" * 32
        fp1 = key_fingerprint(master, "call-x")
        fp2 = key_fingerprint(master, "call-x")
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_encrypt_decrypt_roundtrip(self):
        from app.blockchain.external_anchor import encrypt_pdf, decrypt_pdf
        from app.blockchain.external_anchor import _derive_report_key
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.pdf")
            with open(path, "wb") as fh:
                fh.write(b"%PDF-1.4 VoiceShield forensic report")
            key = _derive_report_key(b"0" * 32, "call-r")
            enc = encrypt_pdf(path, key)
            assert enc["enc_alg"] == "AES-256-GCM"
            assert enc["file_sha256"]
            plain = decrypt_pdf(enc["cipher_b64"], key)
            assert plain == b"%PDF-1.4 VoiceShield forensic report"

    def test_wrong_key_fails(self):
        from app.blockchain.external_anchor import encrypt_pdf, decrypt_pdf
        from app.blockchain.external_anchor import _derive_report_key
        from cryptography.exceptions import InvalidTag
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.pdf")
            with open(path, "wb") as fh:
                fh.write(b"%PDF-1.4 secret")
            key = _derive_report_key(b"0" * 32, "call-w")
            enc = encrypt_pdf(path, key)
            with pytest.raises(InvalidTag):
                decrypt_pdf(enc["cipher_b64"], b"1" * 32)


class TestAnchorBlock:
    def test_demo_anchor_status_and_persist(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.config.settings.blockchain_external_anchor", False,
        )
        monkeypatch.setattr(
            "app.config.settings.report_keys_dir", str(tmp_path),
        )
        from app.blockchain import external_anchor as ea
        block = {
            "block_index": 0, "call_id": "call-a", "report_id": "REP-a",
            "incident_id": None, "file_sha256": "a" * 64,
            "merkle_root": "b" * 64, "block_hash": "c" * 64,
            "timestamp": "2026-09-19T00:00:00+05:30", "file_path": "no.pdf",
        }
        res = ea.anchor_block(block)
        assert res["provider"] == "demo"
        assert res["anchor_status"] == "demo"

        persisted = ea.anchor_status_for_call("call-a")
        assert persisted["provider"] == "demo"
        assert persisted["anchor_status"] == "demo"

    def test_verify_report_surfaces_anchor_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.config.settings.blockchain_external_anchor", False,
        )
        monkeypatch.setattr(
            "app.config.settings.report_keys_dir", str(tmp_path),
        )
        from app.blockchain import ledger
        pdf = os.path.join(tmp_path, "v.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 anchored")
        ledger.anchor_report(
            call_id="call-v", report_id="REP-v", incident_id=None,
            file_path=pdf, window_leaves=[1],
        )
        verified = ledger.verify_report("call-v")
        assert verified["external_anchor"]["provider"] == "demo"
        assert verified["external_anchor"]["anchor_status"] == "demo"


class TestAnchorAPI:
    def test_blockchain_status_includes_anchor_summary(self, monkeypatch):
        monkeypatch_helper(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.get("/api/blockchain")
        assert r.status_code == 200
        body = r.json()
        assert "external_anchor" in body
        assert "count" in body["external_anchor"]

    def test_verify_includes_external_anchor(self, monkeypatch):
        monkeypatch_helper(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app
        from app.blockchain import ledger
        import tempfile
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "api_anchor.pdf")
            with open(pdf, "wb") as fh:
                fh.write(b"%PDF-1.4 api anchor")
            ledger.anchor_report(
                call_id="api-anchor-1", report_id="F-apia", incident_id=None,
                file_path=pdf, window_leaves=[],
            )
            r = client.get("/api/blockchain/verify/call/api-anchor-1")
            assert r.status_code == 200
            assert "external_anchor" in r.json()

    def test_retry_when_disabled_returns_400(self, monkeypatch):
        monkeypatch_helper(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.post("/api/blockchain/retry/call-none")
        assert r.status_code in (400, 404)


class TestOnchainVerification:
    """Live NBF-Fabric query + IPFS round-trip verification (httpx.MockTransport)."""

    CID = "Qm" + "0" * 44  # fake but structurally plausible CID

    def _patch_get(self, monkeypatch, handler):
        """Swap external_anchor.httpx.get for a MockTransport-backed client.get."""
        import types

        import httpx

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(
            "app.blockchain.external_anchor.httpx",
            types.SimpleNamespace(get=client.get),
        )
        return client

    def _seed(self, tmp_path, monkeypatch, call_id="call-oc"):
        """Mint a local block + upgrade its anchor row to a real 'anchored' row."""
        from app import store
        from app.blockchain import external_anchor as ea
        from app.blockchain import ledger

        monkeypatch.setattr("app.config.settings.report_keys_dir", str(tmp_path))
        monkeypatch.setattr("app.config.settings.blockchain_external_anchor", False)
        monkeypatch.setattr("app.config.settings.nbf_gateway_url", "http://gateway:4000")

        pdf = os.path.join(tmp_path, f"{call_id}.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 onchain verification")
        block = ledger.anchor_report(
            call_id=call_id, report_id=f"REP-{call_id}", incident_id=None,
            file_path=pdf, window_leaves=None,
        )
        store.upsert_block_anchor(
            block_index=block["block_index"],
            call_id=call_id,
            anchor_status="anchored",
            provider="i4c",
            ipfs_cid=self.CID,
            enc_alg="AES-256-GCM",
            key_fp=ea.key_fingerprint(ea._load_or_create_master_key(), call_id),
            payload_sha256=block["file_sha256"],
            tx_id="tx-mock",
        )
        return ea, block, pdf

    def _cipher(self, ea, call_id, pdf):
        key = ea._derive_report_key(ea._load_or_create_master_key(), call_id)
        return ea.encrypt_pdf(pdf, key)["cipher_b64"]

    def _onchain_payload(self, block):
        return json.dumps(
            {
                "call_id": block["call_id"],
                "block_hash": block["block_hash"],
                "file_sha256": block["file_sha256"],
                "merkle_root": block["merkle_root"],
            }
        )

    def test_full_roundtrip_verified(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        cipher = self._cipher(ea, block["call_id"], pdf)

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": self._onchain_payload(block)})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": cipher})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_get(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["anchor_status"] == "anchored"
        assert res["verified"] is True
        assert res["onchain"]["block_hash"] == block["block_hash"]
        assert res["sha256_match"] is True
        assert res["is_pdf"] is True
        assert res["problems"] == []

    def test_tampered_ciphertext_fails(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        tampered_pdf = os.path.join(tmp_path, "tampered.pdf")
        with open(tampered_pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 TAMPERED CONTENT")

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": self._onchain_payload(block)})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._cipher(ea, block["call_id"], tampered_pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_get(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is False
        assert res["sha256_match"] is False
        assert any("does not decrypt" in p for p in res["problems"])

    def test_onchain_mismatch_detected(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                forged = json.dumps(
                    {
                        "call_id": block["call_id"],
                        "block_hash": "f" * 64,  # differs from the local block
                        "file_sha256": block["file_sha256"],
                        "merkle_root": block["merkle_root"],
                    }
                )
                return httpx.Response(200, json={"result": forged})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._cipher(ea, block["call_id"], pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_get(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is False
        assert any("block_hash differs" in p for p in res["problems"])

    def test_demo_or_pending_makes_no_network_call(self, tmp_path, monkeypatch):
        from app import store
        from app.blockchain import external_anchor as ea
        from app.blockchain import ledger

        monkeypatch.setattr("app.config.settings.report_keys_dir", str(tmp_path))
        monkeypatch.setattr("app.config.settings.blockchain_external_anchor", False)
        monkeypatch.setattr("app.config.settings.nbf_gateway_url", "http://gateway:4000")

        pdf = os.path.join(tmp_path, "demo.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 demo")
        block = ledger.anchor_report(
            call_id="call-demo", report_id="REP-demo", incident_id=None,
            file_path=pdf, window_leaves=None,
        )
        # default demo provider leaves the anchor as 'demo' — verify must NOT hit the gateway
        def handler(_request):
            raise AssertionError("demo anchor must never touch the network")

        self._patch_get(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["anchor_status"] == "demo"
        assert res["verified"] is False
        assert any("NBF-Fabric offline" in p for p in res["problems"])
        # orphan 'pending' rows also short-circuit
        store.upsert_block_anchor(
            block_index=block["block_index"], call_id=block["call_id"],
            anchor_status="pending", provider="i4c",
        )
        res2 = ea.verify_anchor(block["call_id"])
        assert res2["anchor_status"] == "pending"
        assert res2["verified"] is False
        assert any("nothing on-chain" in p for p in res2["problems"])


    def test_stale_anchor_detected(self, tmp_path, monkeypatch):
        """An anchored row whose chaincode record vanished is reported stale,
        with a re-anchor hint, without a false 'verified'."""

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"error": "no record found"})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_get(monkeypatch, handler)
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        res = ea.verify_anchor(block["call_id"])
        assert res["stale"] is True
        assert res["verified"] is False
        assert any("stale" in p for p in res["problems"])

    def test_dead_gateway_surfaces_unreachable(self, tmp_path, monkeypatch):
        """A dead gateway fails fast and surfaces 'gateway_unreachable' with a
        hint instead of raw per-request errors."""

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(503)
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_get(monkeypatch, handler)
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        res = ea.verify_anchor(block["call_id"])
        assert res["anchor_status"] == "gateway_unreachable"
        assert res["verified"] is False
        assert any("gateway_unreachable" in p or "gateway unreachable" in p for p in res["problems"])


class TestNBFLiteParity:
    """Response-envelope parity with the official NBFLite samplerest gateway.

    NBFLite wraps chaincode results in JSON strings, may name ReportAnchor
    fields in camelCase, and (in the sample) pins the base64 *text* to IPFS
    rather than the decoded bytes. These tests lock the backend's tolerance
    of all three differences plus the onchain-verification round trip.
    """

    CID = "Qm" + "0" * 44

    def _patch_httpx(self, monkeypatch, handler, with_post=False):
        import types

        import httpx

        client = httpx.Client(transport=httpx.MockTransport(handler))
        ns = {"get": client.get}
        if with_post:
            ns["post"] = client.post
        monkeypatch.setattr("app.blockchain.external_anchor.httpx", types.SimpleNamespace(**ns))
        return client

    def _seed(self, tmp_path, monkeypatch, call_id="call-nl"):
        from app import store
        from app.blockchain import external_anchor as ea
        from app.blockchain import ledger

        monkeypatch.setattr("app.config.settings.report_keys_dir", str(tmp_path))
        monkeypatch.setattr("app.config.settings.blockchain_external_anchor", False)
        monkeypatch.setattr("app.config.settings.nbf_gateway_url", "http://gateway:4000")
        monkeypatch.setattr("app.config.settings.nbf_ipfs_mode", "auto")

        pdf = os.path.join(tmp_path, f"{call_id}.pdf")
        with open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 nbflite parity")
        block = ledger.anchor_report(
            call_id=call_id, report_id=f"REP-{call_id}", incident_id=None,
            file_path=pdf, window_leaves=None,
        )
        store.upsert_block_anchor(
            block_index=block["block_index"], call_id=call_id,
            anchor_status="anchored", provider="i4c",
            ipfs_cid=self.CID, enc_alg="AES-256-GCM",
            key_fp=ea.key_fingerprint(ea._load_or_create_master_key(), call_id),
            payload_sha256=block["file_sha256"], tx_id="tx-nl",
        )
        return ea, block, pdf

    def _cipher(self, ea, call_id, pdf):
        import base64 as b64
        key = ea._derive_report_key(ea._load_or_create_master_key(), call_id)
        return ea.encrypt_pdf(pdf, key)["cipher_b64"]

    def _base64text_payload(self, ea, call_id, pdf):
        """What the NBFLite sample gateway pins: base64 of the base64 text."""
        import base64 as b64
        return b64.b64encode(self._cipher(ea, call_id, pdf).encode("ascii")).decode("ascii")

    def test_camelcase_result_wrapped_in_string(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        camel = json.dumps(
            {
                "callId": block["call_id"],
                "reportId": block["report_id"],
                "incidentId": "",
                "fileSha256": block["file_sha256"],
                "merkleRoot": block["merkle_root"],
                "blockHash": block["block_hash"],
                "timestamp": block["timestamp"],
                "ipfsCid": self.CID,
                "encAlg": "AES-256-GCM",
                "keyFp": ea.key_fingerprint(ea._load_or_create_master_key(), block["call_id"]),
            }
        )

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": camel})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._base64text_payload(ea, block["call_id"], pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_httpx(monkeypatch, handler)
        onchain = ea.query_onchain(block["call_id"])
        assert onchain["block_hash"] == block["block_hash"]
        assert onchain["file_sha256"] == block["file_sha256"]
        assert onchain["merkle_root"] == block["merkle_root"]
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is True
        assert res["problems"] == []

    def test_snakecase_dict_result_not_wrapped(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": {
                    "call_id": block["call_id"], "block_hash": block["block_hash"],
                    "file_sha256": block["file_sha256"], "merkle_root": block["merkle_root"],
                }})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._base64text_payload(ea, block["call_id"], pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_httpx(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is True

    def test_invokecc_envelope_variants(self, monkeypatch):
        from app import config
        from app.blockchain import external_anchor as ea

        monkeypatch.setattr(config.settings, "nbf_gateway_url", "http://gateway:4000")
        provider = ea.I4CAnchor()
        for env in ({"tx_id": "abc1"}, {"payload": "abc2"}, {"txID": "abc3"},
                    {"transactionId": "abc4"}, {"txid": "abc5"}):

            def handler(request):
                return httpx.Response(200, json=env)

            self._patch_httpx(monkeypatch, handler, with_post=True)
            got = provider._fabric_invoke("anchorReport", ["call-x"], "tx-x")
            assert got == next(iter(env.values())), f"envelope {env}"

    def test_retrieve_explicit_base64text_mode(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        monkeypatch.setattr("app.config.settings.nbf_ipfs_mode", "base64text")

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": json.dumps({
                    "call_id": block["call_id"], "block_hash": block["block_hash"],
                    "file_sha256": block["file_sha256"], "merkle_root": block["merkle_root"],
                })})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._base64text_payload(ea, block["call_id"], pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_httpx(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is True
        assert res["ipfs"]["mode"] == "base64text"

    def test_forced_raw_mode_auto_fallback_reports(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)
        monkeypatch.setattr("app.config.settings.nbf_ipfs_mode", "raw")

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": json.dumps({
                    "call_id": block["call_id"], "block_hash": block["block_hash"],
                    "file_sha256": block["file_sha256"], "merkle_root": block["merkle_root"],
                })})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": self._base64text_payload(ea, block["call_id"], pdf)})
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_httpx(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is True
        assert res["ipfs"]["mode"] == "auto(forced-fallback)"

    def test_garbage_retrieve_fails_open(self, tmp_path, monkeypatch):
        ea, block, pdf = self._seed(tmp_path, monkeypatch)

        def handler(request):
            if "health" in str(request.url):
                return httpx.Response(200, json={"status": "ok"})
            if "querycc" in str(request.url):
                return httpx.Response(200, json={"result": json.dumps({
                    "call_id": block["call_id"], "block_hash": block["block_hash"],
                    "file_sha256": block["file_sha256"], "merkle_root": block["merkle_root"],
                })})
            if "retrieve" in str(request.url):
                return httpx.Response(200, json={"data": "bm90LWEtcGRm"})  # base64("not-a-pdf")
            raise AssertionError(f"unexpected request: {request.url}")

        self._patch_httpx(monkeypatch, handler)
        res = ea.verify_anchor(block["call_id"])
        assert res["verified"] is False
        assert res["decrypt"] is False
        assert any("fail-open" in p for p in res["problems"])


def monkeypatch_helper(monkeypatch):
    """Avoid real IPFS/gateway calls: force demo provider for API tests."""
    import app.config
    monkeypatch.setattr(app.config.settings, "blockchain_external_anchor", False)