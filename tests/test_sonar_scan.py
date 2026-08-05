"""Tests for the bot-owned external SonarCloud scan pipeline orchestration
(_run_external_sonar_scan): a no-op unless configured, else trigger + wait."""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import asyncio
from unittest.mock import AsyncMock

import app.main as main
from app.main import _run_external_sonar_scan, _clone_url
from app.sonarqube_client import SonarQubeClient
from app import sonar_scanner


# ── In-bot scanner (clone URL + availability + no-op safety) ──────────────────

def test_clone_url_injects_token(monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-xyz")
    assert _clone_url("https://gitlab.com/g/app") == "https://oauth2:glpat-xyz@gitlab.com/g/app.git"


def test_scanner_unavailable_without_cli(monkeypatch):
    # No sonar-scanner on PATH in CI → available() is False, run_scan is a no-op.
    monkeypatch.setattr(sonar_scanner.shutil, "which", lambda _c: None)
    assert sonar_scanner.available() is False
    ok = asyncio.run(sonar_scanner.run_scan("url", "feat", "k", 3, "main"))
    assert ok is False


# ── SonarCloud project-key resolution (follows the repo being scanned) ────────

def test_key_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("SONARQUBE_PROJECT_KEY", "fixed_key")
    monkeypatch.setenv("SONAR_ORG", "vissz28")
    assert SonarQubeClient().project_key("group/other") == "fixed_key"


def test_key_derived_from_org_and_repo(monkeypatch):
    monkeypatch.delenv("SONARQUBE_PROJECT_KEY", raising=False)
    monkeypatch.setenv("SONAR_ORG", "vissz28")
    assert SonarQubeClient().project_key("vissz28/quality") == "vissz28_quality"


def test_key_falls_back_to_path(monkeypatch):
    monkeypatch.delenv("SONARQUBE_PROJECT_KEY", raising=False)
    monkeypatch.delenv("SONAR_ORG", raising=False)
    assert SonarQubeClient().project_key("group/repo") == "group/repo"


# ── Ephemeral project lifecycle (create / delete are no-ops when unconfigured) ─

def test_ensure_and_delete_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SONARQUBE_URL", raising=False)
    monkeypatch.delenv("SONARQUBE_TOKEN", raising=False)
    client = SonarQubeClient()
    assert asyncio.run(client.ensure_project("k")) is False
    assert asyncio.run(client.delete_project("k")) is False


def test_env_flag_parsing(monkeypatch):
    monkeypatch.setenv("SONAR_SCAN_EPHEMERAL", "TRUE")
    assert main._env_flag("SONAR_SCAN_EPHEMERAL") is True
    monkeypatch.setenv("SONAR_SCAN_EPHEMERAL", "false")
    assert main._env_flag("SONAR_SCAN_EPHEMERAL") is False
    monkeypatch.delenv("SONAR_SCAN_EPHEMERAL", raising=False)
    assert main._env_flag("SONAR_SCAN_EPHEMERAL") is False


def _fake_gitlab():
    g = AsyncMock()
    return g


def test_noop_when_not_configured(monkeypatch):
    monkeypatch.delenv("SONAR_SCAN_PROJECT_ID", raising=False)
    monkeypatch.delenv("SONAR_SCAN_TRIGGER_TOKEN", raising=False)
    g = _fake_gitlab()
    result = asyncio.run(
        _run_external_sonar_scan(g, "vissz28_quality", "https://gitlab.com/g/app", "feat", 5)
    )
    assert result is None
    g.trigger_pipeline.assert_not_called()


def test_triggers_and_waits_for_success(monkeypatch):
    monkeypatch.setenv("SONAR_SCAN_PROJECT_ID", "42")
    monkeypatch.setenv("SONAR_SCAN_TRIGGER_TOKEN", "tok")
    monkeypatch.setattr(main, "WATCH_INTERVAL", 0)  # no real sleeping in tests

    g = _fake_gitlab()
    g.trigger_pipeline.return_value = {"id": 99, "status": "created"}
    g.get_pipeline.return_value = {"id": 99, "status": "success"}

    result = asyncio.run(
        _run_external_sonar_scan(g, "vissz28_quality", "https://gitlab.com/g/app", "feat", 7)
    )
    assert result == "success"
    # The reviewed repo is passed as host/group/repo.git (no scheme) + PR context.
    _, kwargs = g.trigger_pipeline.call_args
    variables = kwargs.get("variables") or g.trigger_pipeline.call_args.args[3]
    assert variables["TARGET_REPO"] == "gitlab.com/g/app.git"
    assert variables["TARGET_REF"] == "feat"
    assert variables["SONAR_PROJECT_KEY"] == "vissz28_quality"
    assert variables["MR_IID"] == "7"


def test_trigger_failure_returns_none(monkeypatch):
    monkeypatch.setenv("SONAR_SCAN_PROJECT_ID", "42")
    monkeypatch.setenv("SONAR_SCAN_TRIGGER_TOKEN", "tok")
    g = _fake_gitlab()
    g.trigger_pipeline.return_value = None
    result = asyncio.run(
        _run_external_sonar_scan(g, "k", "https://gitlab.com/g/app", "feat", 1)
    )
    assert result is None
