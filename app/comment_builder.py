from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .test_executor import ExecutionSummary

_HEADER = "## 🤖 AI Test Generator"


def _details(summary_line: str, body: str) -> str:
    """Render a GitLab-safe collapsible block. Never place --- directly before <details>."""
    return (
        f"<details>\n"
        f"<summary>{summary_line}</summary>\n\n"
        f"{body}\n\n"
        f"</details>"
    )


class CommentBuilder:

    @staticmethod
    def starting() -> str:
        return f"{_HEADER}\n\n⏳ Analysing code changes…\n"

    @staticmethod
    def analysed(code_analysis: str) -> str:
        block = _details("🔍 <strong>Code analysis</strong>", code_analysis)
        return (
            f"{_HEADER}\n\n"
            f"✅ Code analysed &nbsp;·&nbsp; ⏳ Generating Gherkin scenarios…\n\n"
            f"{block}\n"
        )

    @staticmethod
    def gherkin_ready(code_analysis: str | None, gherkin: str) -> str:
        scenario_count = gherkin.count("Scenario")
        parts = [
            f"{_HEADER}\n\n"
            f"✅ Code analysed &nbsp;·&nbsp; ✅ Gherkin ready &nbsp;·&nbsp; ⏳ Generating Playwright tests…\n"
        ]
        if code_analysis:
            parts.append(_details("🔍 <strong>Code analysis</strong>", code_analysis))
        parts.append(_details(
            f"🥒 <strong>Gherkin scenarios</strong> ({scenario_count})",
            f"```gherkin\n{gherkin}\n```",
        ))
        return "\n\n".join(parts) + "\n"

    @staticmethod
    def build(
        mr_iid: int,
        mr_title: str,
        changed_files: list[str],
        gherkin: str,
        playwright: str,
        code_analysis: str | None = None,
        guardian_report: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        file_list = "\n".join(f"- `{f}`" for f in changed_files[:20])
        scenario_count = gherkin.count("Scenario")
        test_count = playwright.count("test(")

        sections = [
            f"{_HEADER}\n\n"
            f"> ✅ Done · {now} · 📄 {len(changed_files)} file(s) · "
            f"🥒 {scenario_count} scenario(s) · 🎭 {test_count} test(s)\n\n"
            f"---",

            _details("📂 <strong>Changed files</strong>", file_list),
        ]

        if code_analysis:
            sections.append(_details("🔍 <strong>Code analysis</strong>", code_analysis))

        if guardian_report:
            sections.append(guardian_report)

        sections.append(_details(
            f"🥒 <strong>Gherkin scenarios</strong> ({scenario_count})",
            f"```gherkin\n{gherkin}\n```",
        ))
        sections.append(_details(
            f"🎭 <strong>Playwright tests</strong> ({test_count})",
            f"```typescript\n{playwright}\n```",
        ))

        sections.append("> ⚠️ *Always review AI-generated tests before merging.*")

        return "\n\n".join(sections) + "\n"

    @staticmethod
    def execution_results(summary: ExecutionSummary) -> str:
        heading = "\n\n---\n\n### 🧪 Test Execution Results"

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
            rows.append(f"| {r.title} | {status} | {duration} | {detail} |")

        table = (
            "| Scenario | Status | Time | Details |\n"
            "|----------|--------|------|---------|\n"
            + "\n".join(rows)
        ) if rows else "_No individual test data available._"

        return f"{heading}\n\n{summary_line}\n\n{table}\n"
