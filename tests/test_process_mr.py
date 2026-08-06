"""End-to-end test of the MR processing flow with every external call mocked.

Mocks GitLab, the Claude-backed generators/analysers, and the test executor,
then drives `process_mr` and asserts that each stage lands in the live comment
and that the commit status transitions running -> success.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.main as main
from app.test_executor import ExecutionSummary, TestResult
from app.scope_matcher import ScopeResult
from app.doc_reviewer import DocResult
from app.risk_assessor import RiskResult
from app.sonarqube_client import SonarQubeResult


def _sonar_ok():
    """A SonarQubeClient mock whose gate is OK (SonarQube is a required check)."""
    client = AsyncMock()
    client.project_key = MagicMock(return_value="org_proj")
    client.analyse.return_value = SonarQubeResult(configured=True, status="OK")
    client.ensure_project.return_value = True
    client.delete_project.return_value = True
    return client


def _advisory_agents():
    """Mocks for the advisory agents (Scope Analyzer / Docs Reviewer / Risk Analyzer)
    and Jira, so the flow tests never construct real Anthropic clients."""
    scope = AsyncMock()
    scope.match.return_value = ScopeResult(available=False)
    docrev = AsyncMock()
    docrev.review.return_value = DocResult(available=True)
    risk = AsyncMock()
    risk.assess.return_value = RiskResult(available=False)
    jira = AsyncMock()
    jira.get_issue.return_value = None
    jira.project_key = None
    return scope, docrev, risk, jira


GHERKIN = """Feature: Number formatting
  Scenario: Zero value returns "0"
    Given a value of 0
    When it is formatted
    Then the result is "0"
  Scenario: Billion-scale value is divided and formatted
    Given a value of 2_000_000_000
    When it is formatted with unit B
    Then the result is "2.00B"
"""

PLAYWRIGHT = """import { test, expect } from '@playwright/test';

test('Zero value returns "0"', async () => {
  expect(format(0, 'B')).toBe('0');
});
test('Billion-scale value is divided and formatted', async () => {
  expect(format(2_000_000_000, 'B')).toBe('2.00B');
});
"""


def _execution_summary() -> ExecutionSummary:
    """All-passing execution — the happy path that clears the quality gate."""
    s = ExecutionSummary(passed=2, failed=0, skipped=0, duration_s=1.4)
    s.results = [
        TestResult(title='Zero value returns "0"', status="passed", duration_ms=700),
        TestResult(
            title="Billion-scale value is divided and formatted",
            status="passed",
            duration_ms=800,
        ),
    ]
    return s


def _make_gitlab(comment_bodies: list[str], status_calls: list[tuple[str, str]]):
    """A fake GitLabClient recording every comment body and status transition."""
    gl = AsyncMock()

    gl.get_mr_changes.return_value = [
        {"new_path": "src/formatter.ts", "diff": "@@\n+function format() {}\n", "deleted_file": False},
    ]
    gl.get_example_tests.return_value = []
    gl.get_commit_status.return_value = None  # nothing ran yet -> don't skip

    async def _post(project_id, mr_iid, body):
        comment_bodies.append(body)
        return 111  # note_id

    async def _edit(project_id, mr_iid, note_id, body):
        comment_bodies.append(body)

    async def _status(project_id, sha, state, description, url=""):
        status_calls.append((state, description))

    gl.post_mr_comment.side_effect = _post
    gl.edit_mr_comment.side_effect = _edit
    gl.set_commit_status.side_effect = _status
    return gl


@pytest.fixture(autouse=True)
def _reset_state():
    main._processing.clear()
    main._done.clear()
    main._mr_locks.clear()
    main._mr_comments.clear()
    yield


@pytest.mark.asyncio
async def test_process_mr_full_flow_populates_comment():
    comment_bodies: list[str] = []
    status_calls: list[tuple[str, str]] = []

    gitlab = _make_gitlab(comment_bodies, status_calls)

    generator = AsyncMock()
    generator.generate_gherkin.return_value = GHERKIN
    generator.generate_playwright.return_value = PLAYWRIGHT

    analyzer = AsyncMock()
    analyzer.analyze.return_value = "Change formats numbers with unit suffixes."

    executor = AsyncMock()
    executor.run.return_value = _execution_summary()

    scope, docrev, risk, jira = _advisory_agents()
    jira.get_issue.return_value = {"summary": "Format numbers with unit suffixes"}
    with patch.object(main, "GitLabClient", return_value=gitlab), \
         patch.object(main, "TestGenerator", return_value=generator), \
         patch.object(main, "CodeAnalyzer", return_value=analyzer), \
         patch.object(main, "TestExecutor", return_value=executor), \
         patch.object(main, "SonarQubeClient", return_value=_sonar_ok()), \
         patch.object(main, "ScopeMatcher", return_value=scope), \
         patch.object(main, "DocReviewer", return_value=docrev), \
         patch.object(main, "RiskAssessor", return_value=risk), \
         patch.object(main, "JiraClient", return_value=jira):
        await main.process_mr(
            project_id=1,
            project_web_url="https://gitlab.example.com/group/proj",
            mr_iid=42,
            mr_title="Format numbers with unit suffixes",
            mr_description="Adds B/M/K formatting",
            source_branch="feature/formatter",
            target_branch="main",
            author="Elvis",
            mr_url="https://gitlab.example.com/group/proj/-/merge_requests/42",
            commit_sha="abc1234",
        )

    # Each generator/analyser/executor was invoked exactly once.
    analyzer.analyze.assert_awaited_once()
    generator.generate_gherkin.assert_awaited_once()
    generator.generate_playwright.assert_awaited_once()
    executor.run.assert_awaited_once()
    executor.run.assert_awaited_with(PLAYWRIGHT)

    # Every process step is shown as a checklist item across the updates.
    all_text = "\n".join(comment_bodies)
    assert "Internal pipeline" in all_text
    assert "Scope & traceability" in all_text
    assert "Analysing code" in all_text
    assert "Generating Gherkin scenarios" in all_text
    assert "Generating Playwright tests" in all_text
    assert "Executing tests" in all_text
    assert "Quality gate" in all_text

    # The checklist advances: the opening comment is still in progress (has ⬜),
    # and the final comment has everything checked (no ⬜, no ⏳).
    assert "⬜" in comment_bodies[0]
    assert "⬜" not in comment_bodies[-1] and "⏳" not in comment_bodies[-1]

    # The final comment is the last body written; it must contain every stage.
    final = comment_bodies[-1]
    assert "Code analysis" in final
    assert "Gherkin scenarios" in final
    assert "Playwright tests" in final
    assert "Test Execution Results" in final

    # The three advisory agents render their own sections (technical names).
    assert "Scope Analyzer" in final
    assert "Docs Reviewer" in final
    assert "Risk Analyzer" in final
    # New checklist steps are present and complete in the final comment.
    assert "Scope & traceability" in final
    assert "Rollback & risk" in final

    # The execution table is populated with per-scenario rows (not the empty msg).
    assert "No individual test data available" not in final
    assert "| Scenario | Status | Time | Details |" in final
    assert 'Zero value returns "0"' in final
    assert "✅ Passed" in final

    # Quality gate passed (all tests green) -> status success.
    assert "🚦 Gate Verdict" in final
    assert "PASSED" in final
    states = [state for state, _ in status_calls]
    assert states[0] == "running"
    assert states[-1] == "success"


@pytest.mark.asyncio
async def test_process_mr_renders_section_even_when_execution_fails():
    """If the runner can't execute, the section still renders with the error."""
    comment_bodies: list[str] = []
    status_calls: list[tuple[str, str]] = []

    gitlab = _make_gitlab(comment_bodies, status_calls)

    generator = AsyncMock()
    generator.generate_gherkin.return_value = GHERKIN
    generator.generate_playwright.return_value = PLAYWRIGHT

    analyzer = AsyncMock()
    analyzer.analyze.return_value = "analysis"

    executor = AsyncMock()
    failed = ExecutionSummary()
    failed.execution_error = "Node.js is not available in this environment."
    executor.run.return_value = failed

    scope, docrev, risk, jira = _advisory_agents()
    with patch.object(main, "GitLabClient", return_value=gitlab), \
         patch.object(main, "TestGenerator", return_value=generator), \
         patch.object(main, "CodeAnalyzer", return_value=analyzer), \
         patch.object(main, "TestExecutor", return_value=executor), \
         patch.object(main, "ScopeMatcher", return_value=scope), \
         patch.object(main, "DocReviewer", return_value=docrev), \
         patch.object(main, "RiskAssessor", return_value=risk), \
         patch.object(main, "JiraClient", return_value=jira):
        await main.process_mr(
            project_id=1,
            project_web_url="https://gitlab.example.com/group/proj",
            mr_iid=7,
            mr_title="t",
            mr_description="",
            source_branch="b",
            target_branch="main",
            author="a",
            mr_url="u",
            commit_sha="deadbee",
        )

    final = comment_bodies[-1]
    assert "Test Execution Results" in final
    assert "Execution error" in final
    assert "Node.js is not available" in final


@pytest.mark.asyncio
async def test_generate_from_pipeline_runs_generation():
    """On a pipeline-success trigger, generation starts (no deferral deadlock)."""
    gitlab = AsyncMock()
    gitlab.get_mr_details.return_value = {
        "title": "t", "description": "", "source_branch": "b",
        "target_branch": "main", "author": {"name": "a"}, "web_url": "u",
    }

    scope, docrev, risk, jira = _advisory_agents()
    with patch.object(main, "GitLabClient", return_value=gitlab), \
         patch.object(main, "process_mr", new=AsyncMock()) as proc:
        await main._generate_from_pipeline(
            project_id=1,
            project_web_url="https://gitlab.example.com/group/proj",
            branch="feature/x",
            commit_sha="abc1234",
            mr_iid=42,
        )

    proc.assert_awaited_once()
    # Must not get parked back on the watcher (that was the deadlock).
    assert (1, "abc1234") not in main._pending_watches
