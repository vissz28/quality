from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .test_executor import ExecutionSummary

_HEADER = "## 🤖 AI Test Generator"


class CommentBuilder:

    @staticmethod
    def starting() -> str:
        return f"{_HEADER}\n\n⏳ Analysing code changes…\n"

    @staticmethod
    def analysed(code_analysis: str) -> str:
        return (
            f"{_HEADER}\n\n"
            f"✅ Code analysed &nbsp;·&nbsp; ⏳ Generating Gherkin scenarios…\n\n"
            f"---\n\n"
            f"<details>\n"
            f"<summary>🔍 <strong>Code analysis</strong></summary>\n\n"
            f"{code_analysis}\n\n"
            f"</details>\n"
        )

    @staticmethod
    def gherkin_ready(code_analysis: str | None, gherkin: str) -> str:
        scenario_count = gherkin.count("Scenario")
        analysis_block = ""
        if code_analysis:
            analysis_block = (
                f"<details>\n"
                f"<summary>🔍 <strong>Code analysis</strong></summary>\n\n"
                f"{code_analysis}\n\n"
                f"</details>\n\n---\n\n"
            )
        return (
            f"{_HEADER}\n\n"
            f"✅ Code analysed &nbsp;·&nbsp; ✅ Gherkin ready &nbsp;·&nbsp; ⏳ Generating Playwright tests…\n\n"
            f"---\n\n"
            f"{analysis_block}"
            f"<details>\n"
            f"<summary>🥒 <strong>Gherkin scenarios</strong> ({scenario_count})</summary>\n\n"
            f"```gherkin\n{gherkin}\n```\n\n"
            f"</details>\n"
        )

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

        analysis_section = ""
        if code_analysis:
            analysis_section = (
                f"---\n\n"
                f"<details>\n"
                f"<summary>🔍 <strong>Code analysis</strong></summary>\n\n"
                f"{code_analysis}\n\n"
                f"</details>\n\n"
            )

        return (
            f"{_HEADER}\n\n"
            f"> ✅ Done · {now} · 📄 {len(changed_files)} file(s) · "
            f"🥒 {scenario_count} scenario(s) · 🎭 {test_count} test(s)\n\n"
            f"---\n\n"
            f"<details>\n"
            f"<summary>📂 <strong>Changed files</strong></summary>\n\n"
            f"{file_list}\n"
            f"</details>\n\n"
            f"{analysis_section}"
            f"---\n\n"
            f"<details>\n"
            f"<summary>🥒 <strong>Gherkin scenarios</strong> ({scenario_count})</summary>\n\n"
            f"```gherkin\n{gherkin}\n```\n\n"
            f"</details>\n\n"
            f"---\n\n"
            f"<details>\n"
            f"<summary>🎭 <strong>Playwright tests</strong> ({test_count})</summary>\n\n"
            f"```typescript\n{playwright}\n```\n\n"
            f"</details>\n\n"
            f"---\n\n"
            f"{guardian_report if guardian_report else ''}"
            f"---\n\n"
            f"> ⚠️ *Always review AI-generated tests before merging.*\n"
        )

    @staticmethod
    def execution_results(summary: ExecutionSummary) -> str:
        if summary.execution_error:
            return (
                f"---\n\n"
                f"### 🧪 Test Execution Results\n\n"
                f"> ⚠️ Execution error: {summary.execution_error}\n"
            )

        icons = {"passed": "✅", "failed": "❌", "skipped": "⚠️"}
        total = summary.passed + summary.failed + summary.skipped
        summary_line = (
            f"> ✅ {summary.passed} passed · ❌ {summary.failed} failed · "
            f"⚠️ {summary.skipped} skipped · {summary.duration_s}s"
        )

        rows = []
        for r in summary.results:
            icon = icons.get(r.status, "❓")
            if r.status == "failed":
                detail = f"`{r.classification}` — {r.error}" if r.error else f"`{r.classification}`"
            else:
                detail = "—"
            rows.append(f"| {icon} {r.title} | {detail} |")

        table = (
            "| Test | Details |\n"
            "|------|---------|\n"
            + "\n".join(rows)
        ) if rows else "_No individual test data available._"

        return (
            f"---\n\n"
            f"### 🧪 Test Execution Results\n\n"
            f"{summary_line}\n\n"
            f"{table}\n"
        )
