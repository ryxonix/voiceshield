"""
VoiceShield AI — NBF-Lite / I4C External Blockchain Anchor

Every locally-mined report block (see ledger.py) is ALSO committed to a
permissioned Hyperledger Fabric ledger through an NBF-Lite-compatible REST
gateway, and the report PDF is stored on IPFS as *ciphertext* so raw forensic
content never leaves operator custody (DPDP-first).

Flow (per report):

    1. AES-256-GCM encrypt the PDF. The per-report key is derived from an
       org-custody master key (HMAC-SHA256(master, "voiceshield-report-anchor:"+call_id)).
       Only {ipfs_cid, enc_alg, key_fp, file_sha256} are ever committed to
       the ledger; the raw key never leaves the operator's machine.
    2. Push ciphertext (base64) to the IPFS store endpoint  ->  CID.
    3. Invoke chaincode `voiceshield-report AnchorReport(...)` on Fabric,
       recording call/report/incident ids, block hash, merkle root,
       timestamp, ipfs_cid, enc_alg, key_fp.

Fail-open: if the gateway is unreachable, the local PoW chain remains
authoritative and the anchor row is marked 'pending' (retryable). A
`DemoAnchor` provider records the exact same payload to a local shadow file
so verification is truthful even with no Fabric node running (e.g. a laptop
demo); its status is reported as 'demo', never 'anchored'.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

import httpx

from app.config import settings
from app import store

logger = logging.getLogger(__name__)

# An empty CID marker used when IPFS is unavailable. Genuine CIDs are 46 chars.
CID_PENDING = "CidPending-" + "0" * 36


# ── Org key custody ────────────────────────────────────────────────────────

def _master_key_path() -> str:
    base = settings.report_keys_dir or os.path.join(
        os.path.dirname(__file__), "..", "..", "reports", "keys"
    )
    return os.path.join(base, "org_master.key")


def _load_or_create_master_key() -> bytes:
    """Load the org master key, generating a 32-byte key on first use."""
    path = _master_key_path()
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return fh.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = secrets.token_bytes(32)
    with open(path, "wb") as fh:
        fh.write(key)
    logger.info(f"Generated org master key at {path}")
    return key


def _derive_report_key(master: bytes, call_id: str) -> bytes:
    return hmac.new(master, ("voiceshield-report-anchor:" + call_id).encode("utf-8"), hashlib.sha256).digest()


def key_fingerprint(master: bytes, call_id: str) -> str:
    """Short, non-sensitive fingerprint so custody can be attested on-chain."""
    return hmac.new(master, ("voicefingerprint:" + call_id).encode("utf-8"), hashlib.sha256).hexdigest()[:16]


# ── Crypto (AES-256-GCM) ───────────────────────────────────────────────────

def _aes_import():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: F401
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        return True, None
    except Exception as e:  # pragma: no cover - env dependent
        return False, e


def encrypt_pdf(path: str, key: bytes) -> Dict[str, str]:
    """Encrypt a PDF with AES-256-GCM. Returns base64 ctxt + nonce + tag hex."""
    ok, err = _aes_import()
    if not ok:
        raise RuntimeError(f"'cryptography' not installed: {err}. pip install cryptography")

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(path, "rb") as fh:
        plain = fh.read()
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, plain, b"voiceshield-report-v1")
    # wire format: nonce(12) || tag(16) || ciphertext
    encoded = base64.b64encode(nonce + ct).decode("ascii")
    return {
        "cipher_b64": encoded,
        "nonce_hex": nonce.hex(),
        "file_sha256": hashlib.sha256(plain).hexdigest(),
        "enc_alg": "AES-256-GCM",
    }


def decrypt_pdf(cipher_b64: str, key: bytes) -> bytes:
    """Decrypt an AES-256-GCM payload produced by encrypt_pdf."""
    raw = base64.b64decode(cipher_b64)
    nonce, ct = raw[:12], raw[12:]
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(key).decrypt(nonce, ct, b"voiceshield-report-v1")


# ── Anchor providers ───────────────────────────────────────────────────────

class AnchorProvider:
    name = "abstract"

    def anchor(
        self,
        *,
        block_index: int,
        call_id: str,
        report_id: str,
        incident_id: Optional[str],
        file_sha256: str,
        merkle_root: str,
        block_hash: str,
        timestamp: str,
        pdf_path: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class DemoAnchor(AnchorProvider):
    """Records the full anchor payload to a local shadow file (no network)."""

    name = "demo"

    def _shadow_path(self, call_id: str) -> str:
        base = settings.report_keys_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "reports", "keys"
        )
        return os.path.join(base, f"shadow_{call_id}.json")

    def anchor(self, *, block_index, call_id, report_id, incident_id, file_sha256,
               merkle_root, block_hash, timestamp, pdf_path):
        # Still push the file to the local shadow ledger for verifiability.
        payload = {
            "provider": self.name,
            "block_index": block_index,
            "call_id": call_id,
            "report_id": report_id,
            "incident_id": incident_id,
            "file_sha256": file_sha256,
            "merkle_root": merkle_root,
            "block_hash": block_hash,
            "timestamp": timestamp,
            "enc_alg": "AES-256-GCM",
            "ipfs_cid": CID_PENDING,
            "key_fp": "",
            "anchored_at": None,
        }
        try:
            path = self._shadow_path(call_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except OSError as e:
            logger.warning(f"Demo anchor shadow write failed: {e}")
        return payload


class I4CAnchor(AnchorProvider):
    """Real NBF-Lite path: IPFS ciphertext + Fabric chaincode invocation."""

    name = "i4c"

    def __init__(self) -> None:
        gw = (settings.nbf_gateway_url or "").strip().rstrip("/")
        self.gateway = gw
        self.ipfs_store = (settings.ipfs_store_url or gw + "/store").strip().rstrip("/")
        self.channel = settings.nbf_channel
        self.cc = settings.nbf_cc
        self.user = settings.nbf_user
        self.msp = settings.nbf_msp
        self.cfgpath = settings.nbf_cfgpath

    def _ipfs_store(self, call_id: str, cipher_b64: str) -> str:
        r = httpx.post(
            self.ipfs_store,
            json={"fileName": f"VoiceShield_{call_id}.pdf.enc", "fileContents": cipher_b64},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        cid = data.get("hash") or data.get("ipfs_hash") or data.get("cid")
        if not cid or cid == "null" or cid == "":
            raise RuntimeError(f"IPFS store returned no CID: {data}")
        return str(cid)

    def _fabric_invoke(self, fcn: str, args: list, tx_id: str) -> str:
        body = {
            "fcn": fcn,
            "args": args,
            "user": self.user,
            "ccname": self.cc,
            "channel": self.channel,
            "cfgpath": self.cfgpath,
            "local": False,
            "mspId": self.msp,
            "txId": tx_id,
        }
        r = httpx.post(self.gateway + "/fabric/v1/invokecc", json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data["error"]))
        if isinstance(data, dict):
            # Tolerate envelope variants across gateways (NBFLite samplerest
            # included): tx_id / payload / txID / transactionId.
            for key in ("tx_id", "payload", "txID", "transactionId", "txid"):
                if data.get(key):
                    return str(data[key])
        return str(data.get("tx_id") or data.get("payload") or data)

    def anchor(self, *, block_index, call_id, report_id, incident_id, file_sha256,
               merkle_root, block_hash, timestamp, pdf_path):
        if not self.gateway:
            raise RuntimeError("NBF_GATEWAY_URL not configured")
        ok, err = _aes_import()
        if not ok:
            raise RuntimeError(f"'cryptography' not installed: {err}")

        master = _load_or_create_master_key()
        report_key = _derive_report_key(master, call_id)
        enc = encrypt_pdf(pdf_path, report_key)
        cid = self._ipfs_store(call_id, enc["cipher_b64"])
        key_fp = key_fingerprint(master, call_id)
        tx_id = "tx-" + secrets.token_hex(12)

        txid = self._fabric_invoke(
            "AnchorReport",
            [
                str(call_id),
                str(report_id),
                str(incident_id or ""),
                file_sha256,
                merkle_root,
                block_hash,
                timestamp,
                cid,
                enc["enc_alg"],
                key_fp,
            ],
            tx_id,
        )
        return {
            "provider": self.name,
            "block_index": block_index,
            "call_id": call_id,
            "report_id": report_id,
            "incident_id": incident_id,
            "file_sha256": file_sha256,
            "merkle_root": merkle_root,
            "block_hash": block_hash,
            "timestamp": timestamp,
            "enc_alg": enc["enc_alg"],
            "ipfs_cid": cid,
            "key_fp": key_fp,
            "tx_id": txid,
            "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


# ── Public orchestration ───────────────────────────────────────────────────

def get_provider() -> AnchorProvider:
    if settings.blockchain_external_anchor:
        return I4CAnchor()
    return DemoAnchor()


def anchor_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Commit an already-mined local block to the external ledger. Fail-open:
    any provider/gateway error downgrades to 'pending' and is persisted.
    """
    provider = get_provider()
    status = "pending"
    error = None
    try:
        result = provider.anchor(
            block_index=block["block_index"],
            call_id=block["call_id"],
            report_id=block["report_id"],
            incident_id=block.get("incident_id"),
            file_sha256=block["file_sha256"],
            merkle_root=block["merkle_root"],
            block_hash=block["block_hash"],
            timestamp=block["timestamp"],
            pdf_path=block.get("file_path", ""),
        )
        status = "demo" if provider.name == "demo" else "anchored"
        logger.info(f"External anchor #{block['block_index']} [{provider.name}] {status} cid={result.get('ipfs_cid')}")
        store.upsert_block_anchor(
            block_index=block["block_index"],
            call_id=block["call_id"],
            anchor_status=status,
            provider=provider.name,
            ipfs_cid=result.get("ipfs_cid"),
            enc_alg=result.get("enc_alg"),
            key_fp=result.get("key_fp"),
            payload_sha256=block["file_sha256"],
            tx_id=result.get("tx_id"),
            error=None,
        )
        return {**result, "anchor_status": status, "error": None}
    except Exception as e:  # fail-open; local chain is authoritative
        error = f"{type(e).__name__}: {e}"
        logger.warning(f"External anchor #{block['block_index']} failed (fail-open): {error}")
        store.upsert_block_anchor(
            block_index=block["block_index"],
            call_id=block["call_id"],
            anchor_status="pending",
            provider=provider.name,
            tx_id=None,
            error=error,
        )
        return {
            "provider": provider.name,
            "anchor_status": "pending",
            "ipfs_cid": None,
            "tx_id": None,
            "error": error,
            "message": "Local PoW chain is authoritative; external anchor pending (retryable).",
        }


def anchor_status_for_call(call_id: str) -> Dict[str, Any]:
    """Read the persisted external-anchor state for a call (for verify)."""
    row = store.get_block_anchor_by_call(call_id)
    if row is None:
        return {
            "provider": None,
            "anchor_status": "not_anchored",
            "ipfs_cid": None,
            "key_fp": None,
            "tx_id": None,
            "error": None,
        }
    return {
        "provider": row.get("provider"),
        "anchor_status": row.get("anchor_status"),
        "ipfs_cid": row.get("ipfs_cid"),
        "enc_alg": row.get("enc_alg"),
        "key_fp": row.get("key_fp"),
        "tx_id": row.get("tx_id"),
        "error": row.get("error"),
        "anchored_at": row.get("anchored_at"),
    }


def retry_anchor(block: Dict[str, Any]) -> Dict[str, Any]:
    """Re-attempt an external anchor for a previously 'pending' block."""
    return anchor_block(block)


# ── On-chain verification (NBF-Fabric query + IPFS round-trip) ─────────────

def _gateway_base() -> str:
    """Normalized gateway URL (no trailing slash) or '' when unconfigured."""
    return (settings.nbf_gateway_url or "").strip().rstrip("/")


# NBFLite's samplerest returns the ReportAnchor as a JSON string. Both our
# chaincode and theirs may use camelCase field names, so normalize to the
# snake_case keys the backend compares against.
_CAMEL_TO_SNAKE = {
    "callId": "call_id",
    "reportId": "report_id",
    "incidentId": "incident_id",
    "fileSha256": "file_sha256",
    "merkleRoot": "merkle_root",
    "blockHash": "block_hash",
    "ipfsCid": "ipfs_cid",
    "encAlg": "enc_alg",
    "keyFp": "key_fp",
}


def _normalize_anchor(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``record`` with any camelCase ReportAnchor keys folded to snake_case."""
    out: Dict[str, Any] = {}
    for k, v in record.items():
        out[_CAMEL_TO_SNAKE.get(k, k)] = v
    return out


def query_onchain(call_id: str, missing_ok: bool = False) -> Optional[Dict[str, Any]]:
    """Query the Fabric chaincode (`QueryReport`) for a call's anchor record.

    Returns the parsed, key-normalized ReportAnchor as a dict, or ``None`` when
    the chaincode reports no record and ``missing_ok`` is set (used for
    stale-anchor detection). Fail-fast otherwise: any gateway/chaincode error
    raises so callers can degrade gracefully (fail-open).
    """
    gw = _gateway_base()
    if not gw:
        raise RuntimeError("NBF_GATEWAY_URL not configured (cannot query chaincode)")
    params = {
        "fcn": "QueryReport",
        "args": str(call_id),
        "user": settings.nbf_user,
        "ccname": settings.nbf_cc,
        "channel": settings.nbf_channel,
        "cfgpath": settings.nbf_cfgpath,
        "mspId": settings.nbf_msp,
    }
    r = httpx.get(f"{gw}/fabric/v1/querycc", params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and body.get("error"):
        if missing_ok and str(body["error"]).lower() in ("no record found", "record not found", "empty"):
            return None
        raise RuntimeError(str(body["error"]))
    result = body.get("result")
    if result is None:
        if missing_ok:
            return None
        raise RuntimeError(f"Chaincode query returned no result: {body}")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            result = {"raw": result}
    if not isinstance(result, dict):
        return {"raw": result}
    return _normalize_anchor(result)


def _gateway_health(timeout: float = 10.0) -> bool:
    """Fast health probe for the NBF-Lite gateway (fails quickly when dead)."""
    gw = _gateway_base()
    if not gw:
        return False
    try:
        r = httpx.get(f"{gw}/health", timeout=timeout)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def _decode_cipher_payload(data: str, key: bytes, mode: str = "auto") -> bytes:
    """Decrypt the /retrieve payload to the plaintext PDF bytes.

    Gateways differ on what bytes are pinned under the CID:
      raw        — our trimmed gateway: decoded AES bytes, so body data is the
                   base64 cipher (decrypt_pdf(data) works directly).
      base64text — NBFLite sample gateway: the base64 *text* was pinned, so
                   body data is base64(base64-string); decode twice.
    ``auto`` tries raw first and falls back to base64text. Raises on failure.
    """
    if mode not in ("auto", "raw", "base64text"):
        raise ValueError(f"unknown nbf_ipfs_mode {mode!r}")

    def try_raw():
        return decrypt_pdf(data, key)

    def try_text():
        decoded = base64.b64decode(data)
        return decrypt_pdf(decoded.decode("ascii"), key)

    if mode == "raw":
        return try_raw()
    if mode == "base64text":
        return try_text()
    try:
        return try_raw()
    except Exception:
        return try_text()


def fetch_ipfs(cid: str) -> str:
    """Fetch raw bytes pinned under `cid`, returned as base64 (never decoded
    to UTF-8 — the stored payload is opaque AES-256-GCM ciphertext)."""
    gw = _gateway_base()
    if not gw:
        raise RuntimeError("NBF_GATEWAY_URL not configured (cannot fetch IPFS)")
    r = httpx.get(f"{gw}/retrieve/{cid}", timeout=60)
    r.raise_for_status()
    body = r.json()
    data = body.get("data")
    if isinstance(data, dict):  # tolerate legacy {data:{data:...}} double-wrap
        data = data.get("data")
    if data is None:
        raise RuntimeError(f"IPFS retrieve returned no payload for {cid}")
    return str(data)


def verify_anchor(
    call_id: str, local_block: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """End-to-end external-anchor verification (fail-open).

    When an anchor row exists it checks:
      1. on-chain record (Fabric `QueryReport`) fields vs the local block,
      2. IPFS round-trip: fetch the ciphertext, decrypt with the org-derived
         report key, recompute SHA-256 (must equal ``file_sha256``) and
         confirm the document starts with ``%PDF``.

    Pending / demo / not-anchored rows stay truthful — never a false
    'verified'. Every failure is a fail-open note; the local PoW chain remains
    authoritative either way.
    """
    status = anchor_status_for_call(call_id)
    anchor_status = status.get("anchor_status", "not_anchored")
    problems: List[str] = []
    result: Dict[str, Any] = {
        "anchor_status": anchor_status,
        "verified": False,
        "onchain": None,
        "ipfs": None,
        "decrypt": None,
        "sha256_match": None,
        "is_pdf": None,
        "problems": problems,
        "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if local_block is None:
        from app import store as _store
        local_block = _store.get_block_by_call(call_id)
    if local_block is None:
        problems.append(f"no local block for call '{call_id}'")
        return result

    if anchor_status != "anchored":
        # Demo/pending/not-anchored: nothing real on-chain to compare, so we
        # report truthfully and make NO network attempt (fail-open, offline-safe).
        if anchor_status == "demo":
            problems.append("demo anchor (NBF-Fabric offline) — no real on-chain record to compare")
        else:
            problems.append(f"external anchor {anchor_status} — nothing on-chain to verify")
        return result

    # Pre-flight: fast health probe on the gateway so a dead / unwired forward
    # fails quickly and cleanly with an actionable hint instead of raw 500s.
    if not _gateway_health(timeout=10.0):
        result["anchor_status"] = "gateway_unreachable"
        problems.append(
            "NBF-Lite gateway unreachable — set NBF_GATEWAY_URL to a live "
            "gateway (restart Codespace or deploy scripts/local-wsl2.sh) and "
            "call POST /api/blockchain/retry/{call_id} to re-anchor"
        )
        result["problems"] = problems
        return result

    # 1) On-chain record vs local block
    try:
        onchain = query_onchain(call_id, missing_ok=True)
        if onchain is None:
            result["stale"] = True
            problems.append(
                f"on-chain record missing for '{call_id}' — anchor is stale; "
                "re-anchor via POST /api/blockchain/retry/{call_id}"
            )
        else:
            result["onchain"] = onchain
            for field, expect in (
                ("call_id", call_id),
                ("block_hash", local_block["block_hash"]),
                ("file_sha256", local_block["file_sha256"]),
                ("merkle_root", local_block["merkle_root"]),
            ):
                if str(onchain.get(field, "")) != str(expect):
                    problems.append(f"on-chain {field} differs from local block")
    except Exception as e:  # fail-open
        problems.append(f"on-chain query failed (fail-open): {type(e).__name__}: {e}")

    # 2) IPFS round trip (only for real, pinned anchors)
    ipfs_cid = status.get("ipfs_cid")
    if ipfs_cid and not str(ipfs_cid).startswith(CID_PENDING[:12]):
        try:
            cipher_b64 = fetch_ipfs(str(ipfs_cid))
            key = _derive_report_key(_load_or_create_master_key(), call_id)
            try:
                plain = _decode_cipher_payload(
                    cipher_b64, key, settings.nbf_ipfs_mode or "auto"
                )
                fmt = settings.nbf_ipfs_mode
            except Exception:
                # auto-detect fallback when forced mode fails
                plain = _decode_cipher_payload(cipher_b64, key, "auto")
                fmt = "auto(forced-fallback)"
            result["ipfs"] = {
                "cid": str(ipfs_cid),
                "cipher_b64_len": len(cipher_b64),
                "mode": fmt,
            }
            result["decrypt"] = True
            result["sha256_match"] = (
                hashlib.sha256(plain).hexdigest() == local_block["file_sha256"]
            )
            result["is_pdf"] = plain[:4] == b"%PDF"
            if not result["sha256_match"]:
                problems.append("IPFS ciphertext does not decrypt to the anchored PDF hash")
            if not result["is_pdf"]:
                problems.append("decrypted IPFS payload is not a PDF")
        except Exception as e:  # fail-open
            result["decrypt"] = False
            problems.append(f"IPFS fetch/decrypt failed (fail-open): {type(e).__name__}: {e}")
    else:
        result["ipfs"] = None

    result["verified"] = anchor_status == "anchored" and not problems
    return result