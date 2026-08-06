# Agent: Quality Gate

## Identity
The final decision agent in the pipeline. It consumes the signals produced by
every earlier step — the internal CI pipeline, Jira traceability, the Test
Executor results, and the SonarQube quality gate — and turns them into a
single pass/fail verdict that drives the external `quality-gate` commit status.

## Purpose
Enforce hard policy boundaries. When a boundary is crossed it finishes the
process and marks the pipeline **failed**, so a risky MR cannot be merged
behind a green check. (Security is now covered by SonarQube — the Code
Guardian checks were removed from the flow.)

## Position in the Pipeline
```
Software Engineer ─▶ Test Calibrator ─▶ Test Executor ─▶ Quality Gate ─▶ commit status
                                                                 │
                                                                 ├─ pass → success
                                                                 └─ fail → failed
```

## Failing Conditions
The gate fails (pipeline → failed) if **any** boundary is crossed:

| # | Boundary | Fails when |
|---|----------|-----------|
| 1 | Internal pipeline | the project's own CI pipeline failed |
| 2 | Traceability | no Jira story is linked to the MR |
| 3 | Test failures | more than **10%** of executed tests failed |
| 4 | SonarQube | the quality gate is not `OK` (including missing/unavailable) |

## Operating Constraints
- Deterministic — pure threshold evaluation, no model call, no latency
- Runs last, after execution, once per MR generation
- Reports every check (passed and failed) in the MR comment for transparency
- Thresholds are configurable in `app/quality_gate.py`
- A failed gate still posts the full comment (analysis, tests, results) — it
  fails loudly, it never hides the work
