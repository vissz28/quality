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

_HEADER = "## Quality Gate"

# Ordered pipeline of work shown as a live checklist in the MR comment. Step 0
# (the project's internal CI) is what we wait on — the rest starts once it finishes,
# so the comment first appears with step 0 pending (⏳).
STEPS = [
    "Internal pipeline",
    "Scope & traceability",
    "Analysing code & security review",
    "Generating Gherkin scenarios",
    "Generating Playwright tests",
    "Executing tests",
    "SonarQube analysis",
    "Documentation & breaking changes",
    "Rollback & risk",
    "Quality gate",
]
# Named indices for readability from main.py. Scope & traceability is the SECOND
# step (right after the internal pipeline). The Quality gate — the final verdict —
# is LAST, after the advisory docs/risk agents. (Fetching the MR changes happens
# as part of the scope step, not a separate line.)
STEP_FETCH = 1
STEP_SCOPE = 1
STEP_ANALYSE = 2
STEP_GHERKIN = 3
STEP_PLAYWRIGHT = 4
STEP_EXECUTE = 5
STEP_SONAR = 6
STEP_DOC = 7
STEP_RISK = 8
STEP_GATE = 9
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
    _SONAR_COMPARATOR = {"GT": ">", "GE": "≥", "GTE": "≥", "LT": "<", "LE": "≤", "LTE": "≤", "EQ": "=", "NE": "≠"}
    _SONAR_METRIC_LABELS = {
        "new_coverage": "🧪 Coverage (new code)",
        "coverage": "🧪 Coverage",
        "new_duplicated_lines_density": "📑 Duplication (new code)",
        "duplicated_lines_density": "📑 Duplication",
        "new_maintainability_rating": "🛠️ Maintainability",
        "sqale_rating": "🛠️ Maintainability",
        "new_reliability_rating": "♻️ Reliability",
        "reliability_rating": "♻️ Reliability",
        "new_security_rating": "🔒 Security",
        "security_rating": "🔒 Security",
        "new_security_hotspots_reviewed": "🛡️ Hotspots reviewed",
        "security_hotspots_reviewed": "🛡️ Hotspots reviewed",
        "new_violations": "⚠️ New issues",
        "new_bugs": "🐞 New bugs",
        "new_vulnerabilities": "🔓 New vulnerabilities",
        "new_code_smells": "👃 New code smells",
    }

    @staticmethod
    def _sonar_value(metric: str, value) -> str:
        """Format a Sonar value: ratings -> A–E, percents -> N%, otherwise a number."""
        if value in (None, ""):
            return "—"
        if metric.endswith("_rating"):
            try:
                return CommentBuilder._SONAR_RATING.get(f"{float(value):.1f}", str(value))
            except (TypeError, ValueError):
                return str(value)
        if metric.endswith("coverage") or "duplicated_lines_density" in metric or "hotspots_reviewed" in metric:
            try:
                return f"{float(value):g}%"
            except (TypeError, ValueError):
                return f"{value}%"
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _sonar_condition_rows(conditions: list[dict]) -> list[str]:
        """One row per gate condition: status · metric · required · actual."""
        rows = []
        for c in conditions or []:
            metric = c.get("metricKey", "")
            label = CommentBuilder._SONAR_METRIC_LABELS.get(metric, metric)
            icon = "✅" if c.get("status") == "OK" else "❌"
            actual = CommentBuilder._sonar_value(metric, c.get("actualValue"))
            if metric.endswith("_rating"):
                required = CommentBuilder._sonar_value(metric, c.get("errorThreshold"))
            else:
                comp = CommentBuilder._SONAR_COMPARATOR.get(c.get("comparator", ""), "")
                required = f"{comp} {CommentBuilder._sonar_value(metric, c.get('errorThreshold'))}".strip()
            rows.append(f"| {icon} | {label} | {required} | {actual} |")
        return rows

    @staticmethod
    def sonarqube(result: SonarQubeResult) -> str:
        """Render the SonarQube gate as a Metric · Required · Actual · Status table.

        Built from the server's own gate conditions (the values it actually
        enforces), so it matches the Sonar Way quality gate exactly. Only the gate
        metrics are shown — the important information, nothing else.
        """
        heading = "---\n\n### 📊 SonarQube"

        if not result.configured:
            return f"{heading}\n\n> ⚪ Not configured — set `SONARQUBE_URL` and `SONARQUBE_TOKEN` to enable.\n"

        if not result.analysed:
            reason = result.error or "no analysis found for this branch"
            return f"{heading}\n\n> ⚠️ Unavailable — {reason}.\n"

        verdict = "✅ **PASSED**" if result.status == "OK" else "❌ **FAILED**"
        link = f" · [Open dashboard]({result.dashboard_url})" if result.dashboard_url else ""

        rows = CommentBuilder._sonar_condition_rows(result.conditions)
        if rows:
            table = (
                "| | Metric | Required | Actual |\n"
                "|---|--------|----------|--------|\n" + "\n".join(rows)
            )
        else:
            table = (
                "_Gate passed — no conditions reported._"
                if result.status == "OK" else "_No gate conditions available._"
            )

        return f"{heading}\n\n> {verdict}{link}\n\n{table}\n"

    @staticmethod
    def quality_gate(result: GateResult) -> str:
        heading = "---\n\n### 🚦 Gate Verdict"
        if result.passed:
            verdict = "✅ **PASSED** — this merge request meets all Quality Gate rules. Cleared for review."
        else:
            verdict = (
                "❌ **FAILED** — this merge request doesn't satisfy the Quality Gate rules. "
                "Resolve the ❌ items below, then re-run before merging."
            )
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

    # ── Scope, documentation, risk (advisory agents — collapsible) ───────────

    @staticmethod
    def scope_match(result: "ScopeResult") -> str:
        if not result.available:
            return _details(
                "🎯 <strong>Scope Analyzer</strong> — not evaluated",
                "> ⚠️ No linked Jira story (set `JIRA_*` and reference a ticket key in the MR title/branch).",
            )
        verdict = "✅ Matches story" if result.matches else "⚠️ Possible mismatch"
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
        body = f"> **{verdict}**{conf}{link}\n\n{table}"
        if result.rationale:
            body += f"\n\n> {result.rationale}"
        if result.mismatches:
            body += "\n\n**Gaps / possible scope creep:**\n" + "\n".join(f"- {m}" for m in result.mismatches)
        return _details(f"🎯 <strong>Scope Analyzer</strong> — {verdict}", body)

    @staticmethod
    def documentation(result: "DocResult") -> str:
        if not result.available:
            return _details("📝 <strong>Docs Reviewer</strong> — not evaluated", "> ⚪ Not evaluated.")

        has_docs = result.readme_exists or result.docs_folder_exists
        # No documentation surface at all — a single alert, not per-file nags.
        if not has_docs and not result.changelog_exists:
            body = "> ⚠️ This project has no **README**, **CHANGELOG**, or **docs/** folder — consider adding documentation."
            return _details("📝 <strong>Docs Reviewer</strong> — no documentation", body)

        def _row(label: str, updated: bool, exists: bool) -> str:
            if updated:
                return f"| ✅ | {label} | updated |"
            if exists:
                return f"| ⚠️ | {label} | None |"
            return f"| ⚪ | {label} | N/A |"

        rows = [
            _row("Changelog changed", result.changelog_updated, result.changelog_exists),
            _row("README / docs correction", result.docs_updated, has_docs),
        ]
        table = "| | Check | Result |\n|---|-------|--------|\n" + "\n".join(rows)
        body = table
        if result.notes:
            body += f"\n\n> {result.notes}"
        if result.suggested_changelog and result.changelog_exists:
            body += f"\n\n**Suggested changelog entry** (no changelog change detected):\n```\n{result.suggested_changelog}\n```"
        return _details("📝 <strong>Docs Reviewer</strong> — Documentation", body)

    _RISK_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}

    @staticmethod
    def rollback_risk(result: "RiskResult") -> str:
        if not result.available:
            return _details("🛟 <strong>Risk Analyzer</strong> — not evaluated", "> ⚪ Not evaluated.")
        icon = CommentBuilder._RISK_ICON.get(result.risk_level, "🟢")
        flag_detail = (
            ("off by default" if result.feature_flag_safe else "defaults ON ⚠️")
            if result.feature_flag else "no new flag"
        )
        rows = [
            f"| {icon} | Overall risk | **{result.risk_level.upper()}** |",
            f"| {'✅' if result.feature_flag_safe else '⚠️'} | Feature flag default safe | {flag_detail} |",
            f"| • | Can you roll back? | {result.rollback_notes or '—'} |",
        ]
        table = "| | Check | Result |\n|---|-------|--------|\n" + "\n".join(rows)
        body = f"> {icon} Risk: **{result.risk_level.upper()}**\n\n{table}"
        if result.rationale:
            body += f"\n\n> {result.rationale}"
        return _details(f"🛟 <strong>Risk Analyzer</strong> — {icon} {result.risk_level.upper()} risk", body)

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
