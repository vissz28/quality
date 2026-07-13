"""End-to-end test of the MR processing flow with every external call mocked.

Mocks GitLab, the Claude-backed generators/analysers, and the test executor,
then drives `process_mr` and asserts that each stage lands in the live comment
and that the commit status transitions running -> success.
"""
from unittest.mock import AsyncMock, patch

import pytest

import app.main as main
from app.test_executor import ExecutionSummary, TestResult


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
    s = ExecutionSummary(passed=1, failed=1, skipped=0, duration_s=1.4)
    s.results = [
        TestResult(title='Zero value returns "0"', status="passed", duration_ms=700),
        TestResult(
            title="Billion-scale value is divided and formatted",
            status="failed",
            error="expect(received).toBe(expected)",
            classification="BUG",
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

    guardian = AsyncMock()
    guardian.review.return_value = "🛡️ **Code Guardian** — no blocking issues."

    executor = AsyncMock()
    executor.run.return_value = _execution_summary()

    with patch.object(main, "GitLabClient", return_value=gitlab), \
         patch.object(main, "TestGenerator", return_value=generator), \
         patch.object(main, "CodeAnalyzer", return_value=analyzer), \
         patch.object(main, "CodeGuardian", return_value=guardian), \
         patch.object(main, "TestExecutor", return_value=executor):
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
    guardian.review.assert_awaited_once()
    generator.generate_gherkin.assert_awaited_once()
    generator.generate_playwright.assert_awaited_once()
    executor.run.assert_awaited_once()
    executor.run.assert_awaited_with(PLAYWRIGHT)

    # Every process step is shown as a checklist item across the updates.
    all_text = "\n".join(comment_bodies)
    assert "Internal pipeline passed" in all_text
    assert "Fetching MR changes" in all_text
    assert "Analysing code & security review" in all_text
    assert "Generating Gherkin scenarios" in all_text
    assert "Generating Playwright tests" in all_text
    assert "Executing tests" in all_text

    # The checklist advances: the opening comment is still in progress (has ⬜),
    # and the final comment has everything checked (no ⬜, no ⏳).
    assert "⬜" in comment_bodies[0]
    assert "⬜" not in comment_bodies[-1] and "⏳" not in comment_bodies[-1]

    # The final comment is the last body written; it must contain every stage.
    final = comment_bodies[-1]
    assert "Code analysis" in final
    assert "Code Guardian" in final
    assert "Gherkin scenarios" in final
    assert "Playwright tests" in final
    assert "Test Execution Results" in final

    # The execution table is populated with per-scenario rows (not the empty msg).
    assert "No individual test data available" not in final
    assert "| Scenario | Status | Time | Details |" in final
    assert 'Zero value returns "0"' in final
    assert "✅ Passed" in final
    assert "❌ Failed" in final
    assert "`BUG`" in final

    # Commit status went running -> success.
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
    guardian = AsyncMock()
    guardian.review.return_value = ""

    executor = AsyncMock()
    failed = ExecutionSummary()
    failed.execution_error = "Node.js is not available in this environment."
    executor.run.return_value = failed

    with patch.object(main, "GitLabClient", return_value=gitlab), \
         patch.object(main, "TestGenerator", return_value=generator), \
         patch.object(main, "CodeAnalyzer", return_value=analyzer), \
         patch.object(main, "CodeGuardian", return_value=guardian), \
         patch.object(main, "TestExecutor", return_value=executor):
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
