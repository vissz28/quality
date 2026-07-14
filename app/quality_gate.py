"""Quality Gate — the final policy boundary before a green commit status.

Turns the advisory signals from earlier steps into a pass/fail decision and,
when a boundary is crossed, fails the pipeline. Failing conditions:

  1. Internal pipeline failed          (enforced at trigger; surfaced here too)
  2. Any high-severity security finding (hard security boundary)
  3. > 10% of Guardian findings are high severity  ("red line")
  4. > 10% of executed tests failed

Thresholds live in one place so the policy is easy to see and tune.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .code_guardian import GuardianResult
    from .test_executor import ExecutionSummary

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "quality-gate" / "SKILLS.md"


def _extract_skill(name: str) -> str:
    """Load a <!-- SKILL:name --> block from the agent's SKILLS.md."""
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in quality-gate/SKILLS.md")
    return match.group(1).strip()


# Bound to the agent's skill definition (the policy of record), like the other
# agents. Enforcement below is deterministic — the thresholds here must stay in
# sync with the boundaries described in the skill.
QUALITY_GATE_SYSTEM = _extract_skill("QUALITY_GATE_SYSTEM")

RED_LINE_THRESHOLD = 0.10       # fraction of high-severity Guardian findings
TEST_FAILURE_THRESHOLD = 0.10   # fraction of failed tests


@dataclass
class GateCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    passed: bool
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def reasons(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.passed]

    @property
    def summary(self) -> str:
        if self.passed:
            return "All quality boundaries passed."
        return "; ".join(self.reasons)


class QualityGate:
    def __init__(
        self,
        red_line_threshold: float = RED_LINE_THRESHOLD,
        test_failure_threshold: float = TEST_FAILURE_THRESHOLD,
    ):
        self.red_line_threshold = red_line_threshold
        self.test_failure_threshold = test_failure_threshold

    def evaluate(
        self,
        guardian: "GuardianResult",
        execution: "ExecutionSummary",
        internal_pipeline_failed: bool = False,
    ) -> GateResult:
        checks: list[GateCheck] = []

        # 1. Internal pipeline — generation only runs after it succeeds, so this
        # is normally already satisfied; kept explicit for completeness.
        checks.append(GateCheck(
            "Internal pipeline",
            not internal_pipeline_failed,
            "failed" if internal_pipeline_failed else "passed",
        ))

        # 2. Security boundary — any high-severity security finding fails.
        sec_high = guardian.high_security
        checks.append(GateCheck(
            "Security checks",
            sec_high == 0,
            f"{sec_high} high-severity security finding(s)" if sec_high else "no high-severity security findings",
        ))

        # 3. Guardian red line — > threshold share of findings are high severity.
        total = guardian.total
        high = guardian.high
        ratio = (high / total) if total else 0.0
        checks.append(GateCheck(
            "Code Guardian red line",
            ratio <= self.red_line_threshold,
            f"{high}/{total} findings high severity ({ratio:.0%} > {self.red_line_threshold:.0%})"
            if ratio > self.red_line_threshold
            else f"{high}/{total} findings high severity ({ratio:.0%})",
        ))

        # 4. Test failures — > threshold share of executed tests failed.
        executed = execution.passed + execution.failed + execution.skipped
        fail_ratio = (execution.failed / executed) if executed else 0.0
        checks.append(GateCheck(
            "Test failures",
            fail_ratio <= self.test_failure_threshold,
            f"{execution.failed}/{executed} failed ({fail_ratio:.0%} > {self.test_failure_threshold:.0%})"
            if fail_ratio > self.test_failure_threshold
            else f"{execution.failed}/{executed} failed ({fail_ratio:.0%})",
        ))

        passed = all(c.passed for c in checks)
        return GateResult(passed=passed, checks=checks)
