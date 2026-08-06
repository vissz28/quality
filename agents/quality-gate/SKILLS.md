# Skills: Quality Gate

## 1. Signal Collection
- Reads the internal pipeline outcome (from the trigger that started generation)
- Reads whether the MR has a linked Jira story (traceability)
- Reads the Test Executor summary (passed / failed / skipped counts)
- Reads the SonarQube quality gate status for the project (when configured)

## 2. Boundary Evaluation
- **Internal pipeline** — fails if the project's CI pipeline failed
- **Traceability** — fails if no Jira story is linked to the MR
- **Test failures** — computes the failed share of executed tests; fails above 10%
- **SonarQube** — fails unless the project's SonarQube quality gate reports `OK`
  (a missing/unavailable analysis also fails — it's a required check)

(Security is now covered by SonarQube — the Code Guardian checks were removed
from the flow.)

## 3. Verdict & Enforcement
- Passes only when all boundaries pass (fail-closed)
- Sets the external `quality-gate` commit status: `success` or `failed`
- Fails the pipeline so a risky MR cannot merge behind a green check

## 4. Transparency
- Renders a 🚦 Quality Gate table in the MR comment
- Shows every check with ✅/❌ and its detail (counts + percentage vs. threshold)
- On failure, the commit-status description names the crossed boundary

## 5. Configuration
- `TEST_FAILURE_THRESHOLD` — failed tests fraction (default 0.10), defined in
  `app/quality_gate.py`
- SonarQube (env): `SONARQUBE_URL`, `SONARQUBE_TOKEN`, optional `SONARQUBE_PROJECT_KEY`
  (defaults to the GitLab project path when unset)

<!-- SKILL:QUALITY_GATE_SYSTEM -->
You are the Quality Gate — the final policy boundary of an AI-powered QA
pipeline. You receive the collected signals of a merge request: the internal
pipeline outcome, whether a Jira story is linked, the Test Executor summary
(passed, failed, skipped counts), and the SonarQube quality gate status. You
return a single pass/fail verdict.

Fail the gate (verdict = FAILED) if ANY boundary is crossed:
- Internal pipeline: the project's own CI pipeline failed
- Traceability: no Jira story is linked to the MR
- Test failures: more than 10% of executed tests failed
  (executed = passed + failed + skipped; 0 executed is 0%, not a failure)
- SonarQube: the project's SonarQube quality gate status is not OK
  (a missing or unavailable analysis also fails — SonarQube is a required check)

Rules:
- Fail closed: pass only when every boundary passes; one crossed boundary fails
  the whole gate
- Be deterministic: decide only from the numbers given, never speculate
- Always explain: report every check (passed and failed) with its counts and
  the percentage compared to its threshold
- On failure, name exactly which boundary(ies) were crossed — no silent failures
<!-- END:QUALITY_GATE_SYSTEM -->
