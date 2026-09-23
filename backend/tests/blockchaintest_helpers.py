"""Shared fixtures/helpers for the blockchain anchor test modules."""

import os
import types

import httpx
import pytest

from app.blockchain.ledger import settings

DIFFICULTY_TEST = 1


@pytest.fixture(autouse=True)
def _clean_ledger():
    """Fast mining (difficulty 1) + a clean ledgers between tests."""
    settings.blockchain_difficulty = DIFFICULTY_TEST
    from app import store
    store._execute("DELETE FROM blocks")
    store._execute("DELETE FROM block_anchors")
    yield
    settings.blockchain_difficulty = DIFFICULTY_TEST


def _fake_pdf(path: str, content: bytes = b"VoiceShield forensic report mock\n"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)


def patch_httpx(monkeypatch, handler):
    """Swap external_anchor.httpx for an httpx.MockTransport-backed client."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.blockchain.external_anchor.httpx",
        types.SimpleNamespace(get=client.get, post=client.post),
    )
    return client