from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .test_executor import ExecutionSummary

_HEADER = "## 🤖 Quality Code"

# Ordered pipeline of work shown as a live checklist in the MR comment. Index 0
# is always complete by the time we post — we only start after the project's
# internal pipeline has passed.
STEPS = [
    "Internal pipeline passed",
    "Fetching MR changes",
    "Analysing code & security review",
    "Generating Gherkin scenarios",
    "Generating Playwright tests",
    "Executing tests",
]
# Named indices for readability from main.py.
STEP_FETCH = 1
STEP_ANALYSE = 2
STEP_GHERKIN = 3
STEP_PLAYWRIGHT = 4
STEP_EXECUTE = 5
STEP_DONE = len(STEPS)


def _cell(text: str) -> str:
    """Make text safe for a single Markdown table cell.

    A raw '|' is read as a column separator, and a newline ends the row — both
    shift every following value into the wrong column. Escape pipes and flatten
    newlines so multi-part titles (e.g. Scenario Outline example rows) stay put.
    """
    return text.replace("\\", "").replace("|", "\\|").replace("\n", " ").strip()


def _details(summary_line: str, body: str) -> str:
    """Render a GitLab-safe collapsible block. Never place --- directly before <details>."""
    return (
        f"<details>\n"
        f"<summary>{summary_line}</summary>\n\n"
        f"{body}\n\n"
        f"</details>"
    )


class CommentBuilder:

    # ── Live checklist ──────────────────────────────────────────────────────

    @staticmethod
    def progress(
        current: int,
        sections: list[str] | None = None,
        *,
        done: bool = False,
        failed: bool = False,
        meta: str = "",
    ) -> str:
        """Render the header, a step checklist, then any ready detail sections.

        `current` is the index of the step in progress; earlier steps show ✅,
        the current one ⏳ (or ❌ when `failed`), later ones ⬜. When `done`, all
        steps show ✅.
        """
        checklist = []
        for i, name in enumerate(STEPS):
            if done or i < current:
                icon = "✅"
            elif i == current:
                icon = "❌" if failed else "⏳"
            else:
                icon = "⬜"
            checklist.append(f"- {icon} {name}")

        parts = [_HEADER]
        if meta:
            parts.append(meta)
        parts.append("\n".join(checklist))
        if sections:
            parts.append("\n\n".join(s for s in sections if s))
        return "\n\n".join(parts) + "\n"

    @staticmethod
    def done_meta(changed_files: int, scenario_count: int, test_count: int) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"> ✅ Done · {now} · 📄 {changed_files} file(s) · "
            f"🥒 {scenario_count} scenario(s) · 🎭 {test_count} test(s)"
        )

    # ── Reusable detail sections ────────────────────────────────────────────

    @staticmethod
    def changed_files(changed_files: list[str]) -> str:
        file_list = "\n".join(f"- `{f}`" for f in changed_files[:20])
        return _details("📂 <strong>Changed files</strong>", file_list)

    @staticmethod
    def code_analysis(code_analysis: str) -> str:
        return _details("🔍 <strong>Code analysis</strong>", code_analysis)

    @staticmethod
    def gherkin(gherkin: str) -> str:
        scenario_count = gherkin.count("Scenario")
        return _details(
            f"🥒 <strong>Gherkin scenarios</strong> ({scenario_count})",
            f"```gherkin\n{gherkin}\n```",
        )

    @staticmethod
    def playwright(playwright: str) -> str:
        test_count = playwright.count("test(")
        return _details(
            f"🎭 <strong>Playwright tests</strong> ({test_count})",
            f"```typescript\n{playwright}\n```",
        )

    @staticmethod
    def review_footer() -> str:
        return "> ⚠️ *Always review AI-generated tests before merging.*"

    # ── Execution results ───────────────────────────────────────────────────

    @staticmethod
    def execution_results(summary: ExecutionSummary) -> str:
        heading = "---\n\n### 🧪 Test Execution Results"

        if summary.execution_error:
            return f"{heading}\n\n> ⚠️ Execution error: {summary.execution_error}\n"

        labels = {
            "passed": "✅ Passed",
            "failed": "❌ Failed",
            "skipped": "⚠️ Skipped",
        }
        summary_line = (
            f"> ✅ {summary.passed} passed · ❌ {summary.failed} failed · "
            f"⚠️ {summary.skipped} skipped · {summary.duration_s}s"
        )

        rows = []
        for r in summary.results:
            status = labels.get(r.status, "❓ Unknown")
            detail = f"`{r.classification}` — {r.error}" if r.status == "failed" and r.error else "—"
            duration = f"{r.duration_ms / 1000:.1f}s" if r.duration_ms else "—"
            title = _cell(r.title)
            rows.append(f"| {title} | {status} | {duration} | {detail} |")

        table = (
            "| Scenario | Status | Time | Details |\n"
            "|----------|--------|------|---------|\n"
            + "\n".join(rows)
        ) if rows else "_No individual test data available._"

        return f"{heading}\n\n{summary_line}\n\n{table}\n"
