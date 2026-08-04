from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .test_executor import ExecutionSummary
    from .quality_gate import GateResult
    from .sonarqube_client import SonarQubeResult
    from .scope_matcher import ScopeResult
    from .doc_reviewer import DocResult
    from .risk_assessor import RiskResult

_HEADER = "## 🤖 Quality Code"

# Ordered pipeline of work shown as a live checklist in the MR comment. Index 0
# is always complete by the time we post — we only start after the project's
# internal pipeline has passed.
STEPS = [
    "Internal pipeline passed",
    "Fetching MR changes",
    "Analysing code & security review",
    "Scope & traceability match",
    "Documentation & breaking changes",
    "Rollback & risk",
    "Generating Gherkin scenarios",
    "Generating Playwright tests",
    "Executing tests",
    "SonarQube analysis",
    "Quality gate",
]
# Named indices for readability from main.py.
STEP_FETCH = 1
STEP_ANALYSE = 2
STEP_SCOPE = 3
STEP_DOC = 4
STEP_RISK = 5
STEP_GHERKIN = 6
STEP_PLAYWRIGHT = 7
STEP_EXECUTE = 8
STEP_SONAR = 9
STEP_GATE = 10
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

    _SONAR_RATING = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}
    _SONAR_METRIC_LABELS = {
        "bugs": "🐞 Bugs",
        "vulnerabilities": "🔓 Vulnerabilities",
        "code_smells": "👃 Code smells",
        "coverage": "🧪 Coverage",
        "duplicated_lines_density": "📑 Duplication",
        "sqale_rating": "🛠️ Maintainability",
        "security_rating": "🔒 Security",
        "reliability_rating": "♻️ Reliability",
    }
    _SONAR_PERCENT = {"coverage", "duplicated_lines_density"}
    _SONAR_RATING_METRICS = {"sqale_rating", "security_rating", "reliability_rating"}

    @staticmethod
    def sonarqube(result: SonarQubeResult) -> str:
        """Render the SonarQube analysis section for the MR comment.

        Handles three states: not configured, configured-but-unavailable, and a
        concrete OK/ERROR gate with headline measures.
        """
        heading = "---\n\n### 📊 SonarQube"

        if not result.configured:
            return f"{heading}\n\n> ⚪ Not configured — set `SONARQUBE_URL` and `SONARQUBE_TOKEN` to enable.\n"

        if not result.analysed:
            reason = result.error or "no analysis found for this branch"
            return f"{heading}\n\n> ⚠️ Unavailable — {reason}.\n"

        verdict = "✅ **PASSED**" if result.status == "OK" else "❌ **FAILED**"
        link = f" · [Open dashboard]({result.dashboard_url})" if result.dashboard_url else ""

        rows = []
        for metric, label in CommentBuilder._SONAR_METRIC_LABELS.items():
            value = result.measures.get(metric)
            if value is None:
                continue
            if metric in CommentBuilder._SONAR_RATING_METRICS:
                value = CommentBuilder._SONAR_RATING.get(value, value)
            elif metric in CommentBuilder._SONAR_PERCENT:
                value = f"{value}%"
            rows.append(f"| {label} | {value} |")

        table = (
            "| Metric | Value |\n|--------|-------|\n" + "\n".join(rows)
        ) if rows else "_No measures available._"

        return f"{heading}\n\n> {verdict}{link}\n\n{table}\n"

    @staticmethod
    def quality_gate(result: GateResult) -> str:
        heading = "---\n\n### 🚦 Quality Gate"
        verdict = "✅ **PASSED**" if result.passed else "❌ **FAILED**"
        rows = [
            f"| {'✅' if c.passed else '❌'} | {c.name} | {c.detail} |"
            for c in result.checks
        ]
        table = (
            "| | Check | Detail |\n"
            "|---|-------|--------|\n"
            + "\n".join(rows)
        )
        return f"{heading}\n\n> {verdict}\n\n{table}\n"

    # ── Scope, documentation, risk (advisory agents) ─────────────────────────

    @staticmethod
    def scope_match(result: "ScopeResult") -> str:
        heading = "---\n\n### 🎯 Trace Warden — Scope & Traceability"
        if not result.available:
            return (
                f"{heading}\n\n> ⚪ Not evaluated — no linked Jira story found "
                f"(set `JIRA_*` and reference a ticket key in the MR title/branch).\n"
            )
        verdict = "✅ **MATCHES STORY**" if result.matches else "⚠️ **POSSIBLE MISMATCH**"
        conf = f" · confidence: {result.confidence}" if result.confidence else ""
        if result.issue_url:
            link = f" · [{result.issue_key}]({result.issue_url})"
        elif result.issue_key:
            link = f" · {result.issue_key}"
        else:
            link = ""
        rows = [
            f"| {'✅' if result.matches else '⚠️'} | Implements the story | "
            f"{'yes' if result.matches else 'gaps found'} |",
            f"| {'✅' if result.story_fits_project else '⚠️'} | Story fits this project | "
            f"{'yes' if result.story_fits_project else 'out of scope?'} |",
        ]
        table = "| | Check | Result |\n|---|-------|--------|\n" + "\n".join(rows)
        body = f"{heading}\n\n> {verdict}{conf}{link}\n\n{table}\n"
        if result.rationale:
            body += f"\n> {result.rationale}\n"
        if result.mismatches:
            items = "\n".join(f"- {m}" for m in result.mismatches)
            body += f"\n**Gaps / possible scope creep:**\n{items}\n"
        return body

    @staticmethod
    def documentation(result: "DocResult") -> str:
        heading = "---\n\n### 📝 Change Herald — Documentation & Breaking Changes"
        if not result.available:
            return f"{heading}\n\n> ⚪ Not evaluated.\n"
        breaking_doc = "—" if not result.breaking_changes else (
            "documented" if result.breaking_documented else "NOT documented"
        )
        rows = [
            f"| {'✅' if result.docs_updated else '⚪'} | README / API docs updated | "
            f"{'updated' if result.docs_updated else 'not touched'} |",
            f"| {'✅' if result.changelog_updated else '⚪'} | Changelog updated | "
            f"{'updated' if result.changelog_updated else 'not touched'} |",
            f"| {'⚠️' if result.breaking_changes else '✅'} | Breaking changes | "
            f"{'yes' if result.breaking_changes else 'none detected'} |",
            f"| {'✅' if (not result.breaking_changes or result.breaking_documented) else '⚠️'} | "
            f"Breaking changes documented | {breaking_doc} |",
            f"| {'✅' if result.backward_compatible else '⚠️'} | Backward compatible | "
            f"{'yes' if result.backward_compatible else 'no'} |",
        ]
        table = "| | Check | Result |\n|---|-------|--------|\n" + "\n".join(rows)
        body = f"{heading}\n\n{table}\n"
        if result.notes:
            body += f"\n> {result.notes}\n"
        if result.suggested_changelog:
            body += f"\n**Suggested changelog entry** (no changelog change detected):\n```\n{result.suggested_changelog}\n```\n"
        return body

    _RISK_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}

    @staticmethod
    def rollback_risk(result: "RiskResult") -> str:
        heading = "---\n\n### 🛟 Risk Marshal — Rollback & Risk"
        if not result.available:
            return f"{heading}\n\n> ⚪ Not evaluated.\n"
        icon = CommentBuilder._RISK_ICON.get(result.risk_level, "🟢")
        if result.rollback_tag:
            anchor = f"🏷️ `{result.rollback_tag}`"
        else:
            anchor = result.rollback_notes or "—"
        flag_detail = (
            ("off by default" if result.feature_flag_safe else "defaults ON ⚠️")
            if result.feature_flag else "no new flag"
        )
        rows = [
            f"| {icon} | Overall risk | **{result.risk_level.upper()}** |",
            f"| {'✅' if result.feature_flag_safe else '⚠️'} | Feature flag default safe | {flag_detail} |",
            f"| {'🏷️' if result.rollback_tag else '•'} | Rollback anchor | {anchor} |",
        ]
        table = "| | Check | Result |\n|---|-------|--------|\n" + "\n".join(rows)
        body = f"{heading}\n\n> {icon} Risk: **{result.risk_level.upper()}**\n\n{table}\n"
        if result.rationale:
            body += f"\n> {result.rationale}\n"
        return body

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
