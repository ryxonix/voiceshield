"""
VoiceShield AI — Configurable Workflow Tests

Verifies band/role rule resolution, bundled-default fallback when the
workflows file is missing/malformed, and the recommended-actions contract.
"""

import pytest


class TestDefaultsAndFallback:
    def test_bundled_defaults_when_path_empty(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "workflows_path", "")
        from app.mitigation.workflows import get_workflow_config
        cfg = get_workflow_config()
        assert cfg["version"] == 1
        assert len(cfg["rules"]) > 0

    def test_missing_file_falls_back(self, monkeypatch, tmp_path):
        from app.config import settings
        monkeypatch.setattr(settings, "workflows_path", str(tmp_path / "nope.json"))
        from app.mitigation.workflows import get_workflow_config
        assert get_workflow_config()["version"] == 1

    def test_malformed_json_falls_back(self, monkeypatch, tmp_path):
        from app.config import settings
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(settings, "workflows_path", str(bad))
        from app.mitigation.workflows import get_workflow_config
        assert get_workflow_config()["version"] == 1

    def test_loaded_custom_file(self, monkeypatch, tmp_path):
        from app.config import settings
        custom = tmp_path / "wf.json"
        custom.write_text(
            '{"version": 2, "rules": [{"role": "adult", "band_min": "critical", '
            '"actions": ["require_mfa"], "channels": ["email"]}]}',
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "workflows_path", str(custom))
        from app.mitigation.workflows import get_workflow_config
        cfg = get_workflow_config()
        assert cfg["version"] == 2
        assert cfg["rules"][0]["actions"] == ["require_mfa"]


class TestResolution:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "workflows_path", "")
        yield

    def test_adult_critical_requires_mfa_and_escalation(self):
        from app.mitigation.workflows import resolve_workflow
        rule = resolve_workflow("critical", "adult")
        assert "require_mfa" in rule["actions"]
        assert "escalate_supervisor" in rule["actions"]

    def test_adult_high_warns_and_requires_verification(self):
        from app.mitigation.workflows import resolve_workflow
        rule = resolve_workflow("high", "adult")
        assert rule["actions"] == ["warn_user", "require_secondary_verification"]

    def test_adult_medium_flags_manual_review(self):
        from app.mitigation.workflows import resolve_workflow
        assert resolve_workflow("medium", "adult")["actions"] == ["flag_manual_review"]

    def test_child_always_mutes(self):
        from app.mitigation.workflows import resolve_workflow
        for band in ("high", "critical"):
            assert "auto_mute" in resolve_workflow(band, "child")["actions"]

    def test_below_all_rules_falls_back_to_least_specific(self):
        from app.mitigation.workflows import resolve_workflow
        # "low" satisfies no adult rule; fall back to the least-specific one.
        rule = resolve_workflow("low", "adult")
        assert rule["band_min"] == "medium"
        assert rule["actions"] == ["flag_manual_review"]


class TestActionsContract:
    def test_risk_recommended_actions_cover_sih_kw(self):
        from app.engine.risk import recommended_actions
        adult_critical = recommended_actions("critical", "adult")
        joined = " ".join(adult_critical).lower()
        assert "call-back" in joined
        assert "mfa" in joined
        assert "supervisor" in joined

    def test_child_critical_keeps_protective_posture(self):
        from app.engine.risk import recommended_actions
        child_critical = recommended_actions("critical", "child")
        assert any("auto-mute" in a for a in child_critical)
        assert any("guardian" in a for a in child_critical)

    def test_low_band_continues_monitoring(self):
        from app.engine.risk import recommended_actions
        assert recommended_actions("low", "adult") == ["continue real-time monitoring"]