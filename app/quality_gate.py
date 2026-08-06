"""Quality Gate — the final policy boundary before a green commit status.

Turns the advisory signals from earlier steps into a pass/fail decision and,
when a boundary is crossed, fails the pipeline. Failing conditions:

  1. Internal pipeline failed          (enforced at trigger; surfaced here too)
  2. No linked Jira story               (traceability is required)
  3. > 10% of executed tests failed
  4. SonarQube quality gate failed / not analysed (required)

Thresholds live in one place so the policy is easy to see and tune.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        test_failure_threshold: float = TEST_FAILURE_THRESHOLD,
    ):
        self.test_failure_threshold = test_failure_threshold

    def evaluate(
        self,
        execution: "ExecutionSummary",
        internal_pipeline_failed: bool = False,
        sonar_status: str | None = None,
        jira_story_linked: bool = True,
    ) -> GateResult:
        checks: list[GateCheck] = []

        # 1. Internal pipeline — generation only runs after it succeeds, so this
        # is normally already satisfied; kept explicit for completeness.
        checks.append(GateCheck(
            "Internal pipeline",
            not internal_pipeline_failed,
            "failed" if internal_pipeline_failed else "passed",
        ))

        # 2. Traceability — a Jira story must be linked (required). "linked" when
        # a story is found; "N/A" and FAILED when the MR has no linked story.
        checks.append(GateCheck(
            "Jira story linked",
            bool(jira_story_linked),
            "linked" if jira_story_linked else "N/A",
        ))

        # (Security is now covered by SonarQube — the Code Guardian checks were
        # removed from the flow.)

        # 3. Test failures — > threshold share of executed tests failed.
        executed = execution.passed + execution.failed + execution.skipped
        fail_ratio = (execution.failed / executed) if executed else 0.0
        checks.append(GateCheck(
            "Test failures",
            fail_ratio <= self.test_failure_threshold,
            f"{execution.failed}/{executed} failed ({fail_ratio:.0%} > {self.test_failure_threshold:.0%})"
            if fail_ratio > self.test_failure_threshold
            else f"{execution.failed}/{executed} failed ({fail_ratio:.0%})",
        ))

        # 5. SonarQube quality gate — required. "OK" passes; a definitive ERROR
        # fails; anything else (not analysed / unavailable) is N/A and also FAILS
        # (SonarQube is a required check — no analysis means the gate isn't met).
        if sonar_status == "OK":
            checks.append(GateCheck("SonarQube quality gate", True, "passed"))
        elif sonar_status == "ERROR":
            checks.append(GateCheck("SonarQube quality gate", False, "failed on SonarQube"))
        else:
            checks.append(GateCheck("SonarQube quality gate", False, "N/A"))

        passed = all(c.passed for c in checks)
        return GateResult(passed=passed, checks=checks)
