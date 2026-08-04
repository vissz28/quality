"""Unit tests for the Trace Warden / Change Herald / Risk Marshal agents —
the deterministic, non-model parts and their advisory-by-default behaviour."""
import os

# The agent constructors build an Anthropic client which needs a key present.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import asyncio

from app.jira_client import extract_issue_key
from app.doc_reviewer import docs_touched, changelog_touched, DocResult
from app.scope_matcher import ScopeMatcher, ScopeResult
from app.risk_assessor import RiskResult


# ── Jira key extraction ──────────────────────────────────────────────────────

def test_extract_issue_key_from_title():
    assert extract_issue_key("PROJ-123 add wallet", "", "feature/x") == "PROJ-123"


def test_extract_issue_key_falls_back_to_branch():
    assert extract_issue_key("add wallet", None, "feature/ABC-9-fix") == "ABC-9"


def test_extract_issue_key_prefers_configured_project():
    key = extract_issue_key("touches OPS-1 and CORE-2", project_key="core")
    assert key == "CORE-2"


def test_extract_issue_key_none_when_absent():
    assert extract_issue_key("no ticket here", "", "main") is None


# ── Documentation / changelog file detection (deterministic) ─────────────────

def test_docs_and_changelog_detection():
    paths = ["src/app.py", "README.md", "CHANGELOG.md", "docs/api.md"]
    assert docs_touched(paths) is True
    assert changelog_touched(paths) is True


def test_no_docs_or_changelog_touched():
    paths = ["src/app.py", "src/util.py"]
    assert docs_touched(paths) is False
    assert changelog_touched(paths) is False


# ── Advisory-by-default behaviour ────────────────────────────────────────────

def test_scope_match_without_story_is_advisory():
    # No linked story -> unavailable, and never a blocking mismatch.
    res = asyncio.run(ScopeMatcher().match(None, {}, "title", "desc", "diff"))
    assert res.available is False
    assert res.matches is True


def test_result_defaults_never_block():
    assert ScopeResult().available is False and ScopeResult().matches is True
    assert DocResult().backward_compatible is True and DocResult().breaking_changes is False
    assert RiskResult().available is False and RiskResult().risk_level == "low"
