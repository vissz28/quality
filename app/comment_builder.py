from datetime import datetime, timezone

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
            f"> ⚠️ *Always review AI-generated tests before merging.*\n"
        )
