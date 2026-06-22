from datetime import datetime, timezone


class CommentBuilder:
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
            analysis_section = f"""---

<details>
<summary>🔍 <strong>Code analysis</strong> (developer-agent)</summary>

{code_analysis}

</details>

"""

        return f"""## 🤖 AI Test Generator

> Auto-generated for MR **!{mr_iid}** — {mr_title}
> 🕐 {now} · 📄 {len(changed_files)} file(s) analysed · \
🥒 {scenario_count} scenario(s) · 🎭 {test_count} test(s)

---

<details>
<summary>📂 <strong>Changed files analysed</strong></summary>

{file_list}
</details>

{analysis_section}---

<details>
<summary>🥒 <strong>Gherkin scenarios</strong> ({scenario_count} scenario(s))</summary>

```gherkin
{gherkin}
```

</details>

---

<details>
<summary>🎭 <strong>Playwright tests</strong> ({test_count} test(s))</summary>

```typescript
{playwright}
```

</details>

---

> ⚠️ *Always review AI-generated tests before merging.*
"""
