"""
VoiceShield AI — Blockchain Report Ledger

Each forensic PDF is anchored to an immutable local hash chain:

    Genesis ──▶ block #n ──▶ block #n+1 ──▶ ... ──▶ block #N

A block commits:
  - the SHA-256 of the final report PDF (tamper-evidence on the file itself),
  - a Merkle root over the session's per-window evidence,
  - the block's identity (index, IST timestamp, report/call/incident ids),
  - the hash of the previous block (chain-linking -> immutability).

Blocks are "mined" with proof-of-work (SHA-256 nonce search at a configurable
difficulty) so retroactive rewriting is economically infeasible even locally.
The genesis block (index 0) is the trusted root and is mined with difficulty 0.

Verification:
  - file integrity:  recompute SHA-256 of the PDF on disk vs. the block
  - block identity:  recompute block hash from fields, recheck PoW difficulty
  - chain integrity: every block's prev_hash must equal its predecessor's hash
                    (PoW is enforced only on non-genesis blocks)
"""

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app import store

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

CHAIN_ID = "VoiceShieldAIV1"
GENESIS_HASH = "0" * 64

# Serializes the read-latest-block → index-assign → mine → insert sequence so
# two concurrent report generations can never pick the same block_index and
# collide on the PRIMARY KEY (fast, single-process; all anchor_report callers
# run in this process).
_LEDGER_LOCK = threading.Lock()


# ── Hashing helpers ────────────────────────────────────────────────────────

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def merkle_root(leaves: List[Any]) -> str:
    """Standard binary Merkle root over string/serializable leaves."""
    if not leaves:
        return sha256_hex(b"empty")
    level = [sha256_hex(json.dumps(l, sort_keys=True, separators=(",", ":")).encode("utf-8")) for l in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256_hex(a.encode() + b.encode()) for a, b in zip(level[0::2], level[1::2])]
    return level[0]


# ── Proof-of-work ──────────────────────────────────────────────────────────

def _target(difficulty: int) -> str:
    return "0" * difficulty


def _block_header(
    index: int,
    timestamp: str,
    report_id: str,
    call_id: str,
    incident_id: Optional[str],
    file_sha256: str,
    merkle: str,
    prev_hash: str,
    nonce: int,
) -> str:
    payload = {
        "chain": CHAIN_ID,
        "index": index,
        "timestamp": timestamp,
        "report_id": report_id,
        "call_id": call_id,
        "incident_id": incident_id,
        "file_sha256": file_sha256,
        "merkle_root": merkle,
        "prev_hash": prev_hash,
        "nonce": nonce,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def mine_block(
    *,
    index: int,
    report_id: str,
    call_id: str,
    incident_id: Optional[str],
    file_sha256: str,
    merkle: str,
    prev_hash: str,
    difficulty: Optional[int] = None,
) -> Dict[str, Any]:
    """Mine a block committing the given evidence with SHA-256 proof-of-work."""
    diff = difficulty if difficulty is not None else settings.blockchain_difficulty
    tgt = _target(int(diff))
    timestamp = datetime.now(IST).isoformat()
    nonce = 0
    t0 = time.perf_counter()
    while True:
        header = _block_header(index, timestamp, report_id, call_id, incident_id, file_sha256, merkle, prev_hash, nonce)
        h = sha256_hex(header.encode("utf-8"))
        if h.startswith(tgt):
            mined_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"Block #{index} mined (call={call_id}, difficulty={diff}, {mined_ms:.0f}ms) {h}")
            return {
                "block_index": index,
                "timestamp": timestamp,
                "report_id": report_id,
                "call_id": call_id,
                "incident_id": incident_id,
                "file_sha256": file_sha256,
                "merkle_root": merkle,
                "prev_hash": prev_hash,
                "nonce": nonce,
                "block_hash": h,
                "difficulty": int(diff),
            }
        nonce += 1


def anchor_report(
    *,
    call_id: str,
    report_id: str,
    incident_id: Optional[str],
    file_path: str,
    window_leaves: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Hash the final PDF, build evidence Merkle root, mine and commit a block.
    Returns the committed block dict.

    Order matters for the mandate: the block is mined, then the external
    NBF/Fabric anchor runs, and ONLY a successful (or, in default fail-open
    mode, a best-effort demo/pending) anchor leads to the block being inserted
    into the local ledger. In mandatory mode (`BLOCKCHAIN_ANCHOR_REQUIRED=true`)
    any anchor failure raises `BlockAnchorError` before the block is inserted,
    so the ledger never contains an unanchored report.
    """
    with _LEDGER_LOCK:
        try:
            with open(file_path, "rb") as fh:
                file_sha256 = sha256_hex(fh.read())
        except (FileNotFoundError, OSError) as e:
            # Never anchor sha256(b"") for an unreadable file: that would commit a
            # fake evidence hash into a tamper-evident chain. Fail loudly instead.
            raise FileNotFoundError(
                f"Cannot anchor report — file unreadable: {file_path} ({e})"
            ) from e

        from app.blockchain import external_anchor

        merkle = merkle_root(window_leaves or [])
        prev = store.get_latest_block()
        prev_hash = prev["block_hash"] if prev else GENESIS_HASH
        index = (prev["block_index"] + 1) if prev else 0

        block = mine_block(
            index=index,
            report_id=report_id,
            call_id=call_id,
            incident_id=incident_id,
            file_sha256=file_sha256,
            merkle=merkle,
            prev_hash=prev_hash,
            difficulty=0 if index == 0 else None,
        )
        block["file_path"] = file_path

        # Anchor rows must be written against a clean block dict — without the
        # locally-computed `difficulty` key, which is not a stored column for
        # the anchor row, and without `file_path`/`external_anchor` (those live
        # in the blocks row only). Hand the anchor a shallow copy minus those.
        anchor_input = {
            "block_index": block["block_index"],
            "timestamp": block["timestamp"],
            "report_id": block["report_id"],
            "call_id": block["call_id"],
            "incident_id": block["incident_id"],
            "file_path": block["file_path"],
            "file_sha256": block["file_sha256"],
            "merkle_root": block["merkle_root"],
            "prev_hash": block["prev_hash"],
            "nonce": block["nonce"],
            "block_hash": block["block_hash"],
        }

        # External I4C / NBF-Lite anchor — run BEFORE the local commit so the
        # mandated (fail-closed) posture never persists an unanchored block.
        if settings.blockchain_anchor_required:
            external = external_anchor.anchor_block(block, strict=True)
        # Default fail-open: local chain stays authoritative; the anchor row is
        # best-effort — 'demo' (offline) or 'pending' (gateway down), exactly as
        # today, and an unanchored row never blocks the local commit.
        else:
            try:
                external = external_anchor.anchor_block(block)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"External anchor hook failed: {e}")
                external = {"anchor_status": "pending", "error": f"{type(e).__name__}: {e}"}

        # Commit the local block only after the anchor attempt: the dict handed
        # to the store must stay clean (no `external_anchor` column), while the
        # anchor itself is persisted to the block_anchors table and surfaces on
        # the returned dict.
        store.insert_block(**block)
        block["external_anchor"] = external
        return block


# ── Verification ───────────────────────────────────────────────────────────

def _recompute_block_hash(block: Dict[str, Any]) -> str:
    header = _block_header(
        block["block_index"],
        block["timestamp"],
        block["report_id"],
        block["call_id"],
        block.get("incident_id"),
        block["file_sha256"],
        block["merkle_root"],
        block["prev_hash"],
        block["nonce"],
    )
    return sha256_hex(header.encode("utf-8"))


def file_sha256_on_disk(block: Dict[str, Any]) -> str:
    """Recompute the current SHA-256 of the anchored PDF on disk (if present)."""
    try:
        with open(block["file_path"], "rb") as fh:
            return sha256_hex(fh.read()), True
    except FileNotFoundError:
        return "", False
    except OSError:
        return "", False


def _check_pow(block: Dict[str, Any]) -> bool:
    # Use the difficulty locked into the block itself; rows migrated from a
    # pre-difficulty schema have no value yet, so fall back to the current
    # setting for those (genuine anchors update the column going forward).
    stored = block.get("difficulty")
    diff = stored if stored is not None else settings.blockchain_difficulty
    tgt = _target(int(diff))
    return block["block_hash"].startswith(tgt)


def verify_chain() -> Dict[str, Any]:
    """Walk the full ledger; report chain integrity (prev-hash linkage + PoW)."""
    blocks = store.list_blocks(limit=100000)
    checks: List[Dict[str, Any]] = []
    ok = True
    expected_prev = GENESIS_HASH
    for b in blocks:
        problems = []
        if b["prev_hash"] != expected_prev:
            problems.append("prev_hash mismatch (chain break)")
        if _recompute_block_hash(b) != b["block_hash"]:
            problems.append("block hash does not match fields")
        # Genesis (index 0) is the trusted root and is mined with difficulty 0,
        # so proof-of-work is only enforced on blocks 1+ using the difficulty
        # that block N was actually mined with (stored per block).
        if b["block_index"] != 0 and not _check_pow(b):
            problems.append("proof-of-work difficulty not met")
        if problems:
            ok = False
            checks.append({"block_index": b["block_index"], "valid": False, "problems": problems})
        else:
            checks.append({"block_index": b["block_index"], "valid": True, "problems": []})
        expected_prev = b["block_hash"]
    return {
        "chain_id": CHAIN_ID,
        "height": len(blocks),
        "valid": ok,
        "difficulty": int(settings.blockchain_difficulty),
        "genesis": blocks[0]["block_hash"] if blocks else GENESIS_HASH,
        "latest": blocks[-1]["block_hash"] if blocks else GENESIS_HASH,
        "blocks": checks,
    }


def verify_report(call_id: str) -> Dict[str, Any]:
    """Verify the anchor + file integrity + full chain for a report's call."""
    block = store.get_block_by_call(call_id)
    if block is None:
        return {"valid": False, "error": f"No blockchain anchor for call '{call_id}'. Generate the report first."}

    file_hash, file_present = file_sha256_on_disk(block)
    problems = []
    if not file_present:
        problems.append("anchored PDF missing on disk")
    elif file_hash != block["file_sha256"]:
        problems.append("PDF content does not match the anchored hash (file tampered?)")
    chain = verify_chain()
    if not chain["valid"]:
        problems.append("ledger integrity check failed")

    try:
        from app.blockchain import external_anchor

        ext = external_anchor.anchor_status_for_call(call_id)
        if ext.get("anchor_status") in ("anchored", "demo"):
            ext["onchain_verification"] = external_anchor.verify_anchor(call_id, block)
        # Mandated (fail-closed) posture: a report that is not really
        # on-chain cannot verify clean.
        if (
            settings.blockchain_anchor_required
            and ext.get("anchor_status") != "anchored"
        ):
            problems.append(
                "external NBF/Fabric anchor is REQUIRED but status is "
                f"{ext.get('anchor_status')!r} — report is not blockchain-anchored"
            )
    except Exception as e:  # pragma: no cover - defensive
        ext = {"anchor_status": "unavailable", "error": f"{type(e).__name__}: {e}"}
        if settings.blockchain_anchor_required:
            problems.append(f"external anchor unavailable under mandatory mode: {e}")

    return {
        "valid": not problems,
        "chain_id": chain["chain_id"],
        "chain_height": chain["height"],
        "block": block,
        "problems": problems,
        "current_file_sha256": file_hash or None,
        "anchored_file_sha256": block["file_sha256"],
        "external_anchor": ext,
    }