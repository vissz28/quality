# Agent: Quality Gate

## Identity
The final decision agent in the pipeline. It consumes the signals produced by
every earlier step — the internal CI pipeline, the Code Guardian review, and the
Test Executor results — and turns them into a single pass/fail verdict that
drives the external `quality-code` commit status.

## Purpose
Enforce hard security and policy boundaries. The Code Guardian is advisory and
never blocks on its own; the Quality Gate is where advice becomes enforcement.
When a boundary is crossed it finishes the process and marks the pipeline
**failed**, so a risky MR cannot be merged behind a green check.

## Position in the Pipeline
```
Software Engineer ─┐
                   ├─▶ Test Calibrator ─▶ Test Executor ─▶ Quality Gate ─▶ commit status
Code Guardian ─────┘                                              │
                                                                  ├─ pass → success
                                                                  └─ fail → failed
```

## Failing Conditions
The gate fails (pipeline → failed) if **any** boundary is crossed:

| # | Boundary | Fails when |
|---|----------|-----------|
| 1 | Internal pipeline | the project's own CI pipeline failed |
| 2 | Security checks | there is any high-severity security finding |
| 3 | Code Guardian red line | more than **10%** of Guardian findings are high severity |
| 4 | Test failures | more than **10%** of executed tests failed |

## Operating Constraints
- Deterministic — pure threshold evaluation, no model call, no latency
- Runs last, after execution, once per MR generation
- Reports every check (passed and failed) in the MR comment for transparency
- Thresholds are configurable in `app/quality_gate.py`
- A failed gate still posts the full comment (analysis, tests, results) — it
  fails loudly, it never hides the work
