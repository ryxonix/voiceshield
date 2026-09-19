"""
VoiceShield AI — Contextual Enrichment Tests

Covers the opt-in, fail-open enrichment pipeline: signals (unknown origin,
known-contact, high-value transaction, historical fraud flags), transparent
modifiers, clamping, and disable/no-context identities.
"""

import pytest


@pytest.fixture(autouse=True)
def _clean_tables():
    from app import store
    store._execute("DELETE FROM context_contacts")
    store._execute("DELETE FROM caller_reputation")
    yield


@pytest.fixture(autouse=True)
def _toggle(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "contextual_enrichment", True)
    yield


def _enrich(score, raw=None):
    from app.context.enrichment import enrich_score, CallContext
    ctx = raw if isinstance(raw, dict) else {}
    return enrich_score(score, ctx)


class TestDisabledAndFailOpen:
    def test_disabled_returns_unchanged(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "contextual_enrichment", False)
        adjusted, detail = _enrich(0.5, {"caller": "x", "origin": "unknown"})
        assert adjusted == 0.5
        assert detail["applied"] is False

    def test_no_context_returns_unchanged(self):
        adjusted, detail = _enrich(0.5)
        assert adjusted == 0.5
        assert detail["applied"] is False
        assert detail["provided"] is False


class TestSignals:
    def test_unknown_origin_penalty(self):
        adjusted, detail = _enrich(0.5, {"origin": "unknown"})
        assert adjusted == pytest.approx(0.55, abs=1e-6)
        assert detail["applied"] is True
        assert "unknown_origin" in detail["modifiers"]

    def test_known_telecom_origin_no_penalty(self):
        adjusted, detail = _enrich(0.5, {"origin": "telecom", "caller": "+91x"})
        assert adjusted == 0.5
        assert detail["applied"] is False

    def test_known_contact_boost(self):
        adjusted, detail = _enrich(0.8, {"caller": "+91x", "origin": "telecom", "known_contact": True})
        assert adjusted == pytest.approx(0.75, abs=1e-6)

    def test_unknown_contact_penalty(self):
        adjusted, detail = _enrich(0.5, {"caller": "+91x", "origin": "telecom", "known_contact": False})
        assert adjusted == pytest.approx(0.55, abs=1e-6)

    def test_high_value_transaction_penalty(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "context_high_value_threshold", 100000.0)
        adjusted, detail = _enrich(0.5, {"caller": "+91x", "origin": "telecom", "txn_value": 200000})
        assert adjusted == pytest.approx(0.55, abs=1e-6)
        assert "high_value_txn" in detail["modifiers"]

    def test_low_value_transaction_no_penalty(self):
        adjusted, _ = _enrich(0.5, {"caller": "+91x", "origin": "telecom", "txn_value": 500})
        assert adjusted == 0.5

    def test_prior_flags_capped_at_three(self):
        adjusted, detail = _enrich(0.3, {"caller": "+91x", "origin": "telecom", "prior_flags": 5})
        assert adjusted == pytest.approx(0.39, abs=1e-6)

    def test_clamped_at_one(self):
        adjusted, _ = _enrich(0.99, {"caller": "+91x", "prior_flags": 3})
        assert adjusted == 1.0


class TestAutoSources:
    def test_contact_match_when_table_empty_is_none(self):
        from app.context.enrichment import resolve_signals, CallContext
        ctx = CallContext.from_mapping({"caller": "+91x"})
        signals = resolve_signals(ctx)
        assert "known_contact" not in signals  # None -> signal disabled

    def test_contact_match_true_via_table(self):
        from app import store
        store.upsert_context_contact("Mom", "+919000000001")
        from app.context.enrichment import resolve_signals, CallContext
        ctx = CallContext.from_mapping({"caller": "+919000000001"})
        signals = resolve_signals(ctx)
        assert signals["known_contact"] is True

    def test_reputation_flags_auto(self):
        from app import store
        store.bump_caller_flags("+91bad")
        store.bump_caller_flags("+91bad")
        from app.context.enrichment import resolve_signals, CallContext
        ctx = CallContext.from_mapping({"caller": "+91bad"})
        signals = resolve_signals(ctx)
        assert signals["prior_fraud_flags"] == 2


class TestCallContextParsing:
    def test_from_mapping_provided_heuristics(self):
        from app.context.enrichment import CallContext
        assert CallContext.from_mapping(None).provided is False
        assert CallContext.from_mapping({}).provided is False
        assert CallContext.from_mapping({"caller": "x"}).provided is True
        assert CallContext.from_mapping({"known_contact": False}).provided is True
        assert CallContext.from_mapping({"txn_value": 0}).provided is False
        assert CallContext.from_mapping({"txn_value": 1}).provided is True