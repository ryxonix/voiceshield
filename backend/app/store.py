"""
VoiceShield AI — Local Persistence Layer (SQLite)

Stores detection telemetry only — DPDP compliant:
- per-window scores and XAI sub-scores
- incident records
- deterministic speaker reference embeddings (one-way, non-reconstructable)

Raw audio is NEVER written to disk.
"""

import json
import logging
import os
import sqlite3
import threading
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "voiceshield.db"))
_WRITE_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    call_id             TEXT PRIMARY KEY,
    role                TEXT NOT NULL DEFAULT 'adult',
    language            TEXT NOT NULL DEFAULT 'auto',
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    status              TEXT NOT NULL DEFAULT 'active',
    window_count        INTEGER NOT NULL DEFAULT 0,
    max_score           REAL NOT NULL DEFAULT 0.0,
    avg_score           REAL NOT NULL DEFAULT 0.0,
    last_score          REAL NOT NULL DEFAULT 0.0,
    enterprise_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS windows (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT NOT NULL,
    t_ms                 INTEGER NOT NULL,
    model_prob           REAL NOT NULL DEFAULT 0.0,
    xai_risk             REAL NOT NULL DEFAULT 0.0,
    synthetic_score      REAL NOT NULL DEFAULT 0.0,
    jitter_pct           REAL NOT NULL DEFAULT 0.0,
    shimmer_pct          REAL NOT NULL DEFAULT 0.0,
    phase_continuity     REAL NOT NULL DEFAULT 0.0,
    pitch_stability      REAL NOT NULL DEFAULT 0.0,
    noise_floor_dropouts INTEGER NOT NULL DEFAULT 0,
    watermark_hit        INTEGER NOT NULL DEFAULT 0,
    verdict              TEXT NOT NULL DEFAULT 'benign'
);
CREATE INDEX IF NOT EXISTS idx_windows_session ON windows(session_id, t_ms);

CREATE TABLE IF NOT EXISTS incidents (
    id               TEXT PRIMARY KEY,
    session_id       TEXT,
    role             TEXT NOT NULL DEFAULT 'adult',
    language         TEXT NOT NULL DEFAULT 'auto',
    severity         TEXT NOT NULL DEFAULT 'high',
    score            REAL NOT NULL DEFAULT 0.0,
    triggers         TEXT NOT NULL DEFAULT '[]',
    speaker_mismatch INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    acknowledged     INTEGER NOT NULL DEFAULT 0,
    report_path      TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);

CREATE TABLE IF NOT EXISTS speakers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL UNIQUE,
    language    TEXT NOT NULL DEFAULT 'auto',
    embedding   BLOB,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    block_index  INTEGER PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    report_id    TEXT NOT NULL,
    call_id      TEXT NOT NULL,
    incident_id  TEXT,
    file_path    TEXT NOT NULL,
    file_sha256  TEXT NOT NULL,
    merkle_root  TEXT NOT NULL,
    prev_hash    TEXT NOT NULL,
    nonce        INTEGER NOT NULL DEFAULT 0,
    block_hash   TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blocks_call ON blocks(call_id);

CREATE TABLE IF NOT EXISTS block_anchors (
    block_index   INTEGER PRIMARY KEY,
    call_id       TEXT NOT NULL,
    anchor_status TEXT NOT NULL DEFAULT 'pending',
    provider      TEXT NOT NULL DEFAULT 'demo',
    ipfs_cid      TEXT,
    enc_alg       TEXT,
    key_fp        TEXT,
    payload_sha256 TEXT,
    tx_id         TEXT,
    error         TEXT,
    anchored_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_block_anchors_call ON block_anchors(call_id);
"""


def init_db() -> None:
    """Create the SQLite schema if it does not exist yet."""
    conn = sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.info(f"Storage initialized: {_DB_PATH}")
    finally:
        conn.close()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _execute(sql: str, params: tuple = ()) -> None:
    with _WRITE_LOCK:
        conn = _connect()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()


def _fetchall(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _fetchone(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


# ── Sessions ────────────────────────────────────────────────────────────────

def create_session(call_id: str, role: str = "adult", language: str = "auto") -> None:
    _execute(
        "INSERT INTO sessions (call_id, role, language, started_at) VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(call_id) DO UPDATE SET "
        "role=excluded.role, language=excluded.language, started_at=datetime('now'), "
        "ended_at=NULL, status='active', window_count=0, max_score=0.0, avg_score=0.0, "
        "last_score=0.0, enterprise_verified=0",
        (call_id, role or "adult", language or "auto"),
    )


def close_session(
    call_id: str,
    window_count: int,
    max_score: float,
    avg_score: float,
    last_score: float,
    enterprise_verified: bool = False,
) -> None:
    _execute(
        "UPDATE sessions SET status='closed', ended_at=datetime('now'), "
        "window_count=?, max_score=?, avg_score=?, last_score=?, enterprise_verified=? "
        "WHERE call_id=?",
        (
            int(window_count),
            round(float(max_score), 4),
            round(float(avg_score), 4),
            round(float(last_score), 4),
            int(bool(enterprise_verified)),
            call_id,
        ),
    )


def update_session_live(
    call_id: str, window_count: int, max_score: float, last_score: float
) -> None:
    _execute(
        "UPDATE sessions SET window_count=?, max_score=?, last_score=? WHERE call_id=?",
        (int(window_count), round(float(max_score), 4), round(float(last_score), 4), call_id),
    )


def get_session(call_id: str) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM sessions WHERE call_id=?", (call_id,))
    return dict(row) if row else None


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _fetchall("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (int(limit),))
    return [dict(r) for r in rows]


# ── Windows ─────────────────────────────────────────────────────────────────

def add_window(
    *,
    session_id: str,
    t_ms: int,
    model_prob: float,
    xai_risk: float,
    synthetic_score: float,
    jitter_pct: float,
    shimmer_pct: float,
    phase_continuity: float,
    pitch_stability: float,
    noise_floor_dropouts: int,
    watermark_hit: bool,
    verdict: str,
) -> None:
    _execute(
        "INSERT INTO windows (session_id, t_ms, model_prob, xai_risk, synthetic_score, "
        "jitter_pct, shimmer_pct, phase_continuity, pitch_stability, "
        "noise_floor_dropouts, watermark_hit, verdict) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            session_id,
            int(t_ms),
            round(float(model_prob), 4),
            round(float(xai_risk), 4),
            round(float(synthetic_score), 4),
            round(float(jitter_pct), 4),
            round(float(shimmer_pct), 4),
            round(float(phase_continuity), 4),
            round(float(pitch_stability), 4),
            int(noise_floor_dropouts),
            int(bool(watermark_hit)),
            verdict,
        ),
    )


def get_windows(session_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    rows = _fetchall(
        "SELECT * FROM windows WHERE session_id=? ORDER BY t_ms ASC LIMIT ?",
        (session_id, int(limit)),
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "t_ms": r["t_ms"],
                "synthetic_score": r["synthetic_score"],
                "model_prob": r["model_prob"],
                "xai_risk": r["xai_risk"],
                "jitter_pct": r["jitter_pct"],
                "shimmer_pct": r["shimmer_pct"],
                "phase_continuity": r["phase_continuity"],
                "pitch_stability": r["pitch_stability"],
                "noise_floor_dropouts": r["noise_floor_dropouts"],
                "watermark_hit": bool(r["watermark_hit"]),
                "verdict": r["verdict"],
            }
        )
    return out


# ── Incidents ───────────────────────────────────────────────────────────────

def add_incident(
    *,
    iid: str,
    session_id: str,
    role: str,
    language: str,
    severity: str,
    score: float,
    triggers: List[str],
    speaker_mismatch: bool,
) -> None:
    _execute(
        "INSERT OR REPLACE INTO incidents (id, session_id, role, language, severity, "
        "score, triggers, speaker_mismatch, created_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        (
            iid,
            session_id,
            role or "adult",
            language or "auto",
            severity or "high",
            round(float(score), 4),
            json.dumps(triggers or []),
            int(bool(speaker_mismatch)),
        ),
    )


def get_incident(iid: str) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM incidents WHERE id=?", (iid,))
    return dict(row) if row else None


def list_incidents(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _fetchall("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (int(limit),))
    return [dict(r) for r in rows]


def ack_incident(iid: str) -> None:
    _execute("UPDATE incidents SET acknowledged=1 WHERE id=?", (iid,))


def set_incident_report_path(iid: str, path: str) -> None:
    _execute("UPDATE incidents SET report_path=? WHERE id=?", (path, iid))


# ── Speakers ────────────────────────────────────────────────────────────────

def register_speaker(label: str, language: str, embedding_bytes: bytes) -> None:
    _execute(
        "INSERT INTO speakers (label, language, embedding, created_at) VALUES (?,?,?,datetime('now')) "
        "ON CONFLICT(label) DO UPDATE SET language=excluded.language, embedding=excluded.embedding, "
        "created_at=datetime('now')",
        (label, language or "auto", embedding_bytes),
    )


def get_speaker_embedding(label: str) -> Optional[bytes]:
    row = _fetchone("SELECT embedding FROM speakers WHERE label=?", (label,))
    return row["embedding"] if row and row["embedding"] is not None else None


# ── Blockchain (report anchoring ledger) ───────────────────────────────────

def insert_block(
    *,
    block_index: int,
    timestamp: str,
    report_id: str,
    call_id: str,
    incident_id: Optional[str],
    file_path: str,
    file_sha256: str,
    merkle_root: str,
    prev_hash: str,
    nonce: int,
    block_hash: str,
) -> None:
    _execute(
        "INSERT INTO blocks (block_index, timestamp, report_id, call_id, incident_id, "
        "file_path, file_sha256, merkle_root, prev_hash, nonce, block_hash, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (
            int(block_index),
            timestamp,
            report_id,
            call_id,
            incident_id,
            file_path,
            file_sha256,
            merkle_root,
            prev_hash,
            int(nonce),
            block_hash,
        ),
    )


def get_latest_block() -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM blocks ORDER BY block_index DESC LIMIT 1")
    return dict(row) if row else None


def get_block(index: int) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM blocks WHERE block_index=?", (int(index),))
    return dict(row) if row else None


def get_block_by_call(call_id: str) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM blocks WHERE call_id=? ORDER BY block_index DESC LIMIT 1", (call_id,))
    return dict(row) if row else None


def list_blocks(limit: int = 100) -> List[Dict[str, Any]]:
    rows = _fetchall("SELECT * FROM blocks ORDER BY block_index ASC LIMIT ?", (int(limit),))
    return [dict(r) for r in rows]

# ---- External anchor (NBF-Lite / Fabric) side table --------------------

def upsert_block_anchor(
    *,
    block_index: int,
    call_id: str,
    anchor_status: str,
    provider: str,
    ipfs_cid: Optional[str] = None,
    enc_alg: Optional[str] = None,
    key_fp: Optional[str] = None,
    payload_sha256: Optional[str] = None,
    tx_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    _execute(
        "INSERT INTO block_anchors (block_index, call_id, anchor_status, provider, ipfs_cid, "
        "enc_alg, key_fp, payload_sha256, tx_id, error, anchored_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(block_index) DO UPDATE SET "
        "anchor_status=excluded.anchor_status, provider=excluded.provider, "
        "ipfs_cid=excluded.ipfs_cid, enc_alg=excluded.enc_alg, key_fp=excluded.key_fp, "
        "payload_sha256=excluded.payload_sha256, tx_id=excluded.tx_id, "
        "error=excluded.error, anchored_at=datetime('now')",
        (
            int(block_index),
            call_id,
            anchor_status,
            provider,
            ipfs_cid,
            enc_alg,
            key_fp,
            payload_sha256,
            tx_id,
            error,
        ),
    )


def get_block_anchor(block_index: int) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM block_anchors WHERE block_index=?", (int(block_index),))
    return dict(row) if row else None


def get_block_anchor_by_call(call_id: str) -> Optional[Dict[str, Any]]:
    row = _fetchone("SELECT * FROM block_anchors WHERE call_id=? ORDER BY block_index DESC LIMIT 1", (call_id,))
    return dict(row) if row else None

