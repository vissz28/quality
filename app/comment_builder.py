from datetime import datetime, timezone


class CommentBuilder:
    @staticmethod
    def build(
        mr_iid: int,
        mr_title: str,
        changed_files: list[str],
        gherkin: str,
        playwright: str,
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        file_list = "\n".join(f"- `{f}`" for f in changed_files[:20])
        scenario_count = gherkin.count("Scenario")
        test_count = playwright.count("test(")

        return f"""## 🤖 AI Test Generator

> Auto-generated for MR **!{mr_iid}** — {mr_title}
> 🕐 {now} · 📄 {len(changed_files)} file(s) analysed · \
🥒 {scenario_count} scenario(s) · 🎭 {test_count} test(s)

---

<details>
<summary>📂 <strong>Changed files analysed</strong></summary>

{file_list}
</details>

---

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

> 📊 Full interactive report available as a pipeline artifact: \
`test-reports/mr-{mr_iid}-tests.html`
> ⚠️ *Always review AI-generated tests before merging.*
"""
