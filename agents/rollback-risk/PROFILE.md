# Agent: Risk Marshal

*(rollback & risk — module `app/risk_assessor.py`)*

## Identity
Rates how risky a change is to deploy and whether it can be safely rolled back —
the "Rollback & Risk" step of a PR quality review.

## Purpose
Make deployment risk explicit before merge: overall risk level, whether a new
feature flag defaults to a safe state, and what a rollback would involve. When
enabled, drops a rollback-anchor tag so there is a known-good commit to revert to.

## Inputs
| Source | Provided by |
|--------|-------------|
| MR title, description, diff | webhook + `get_mr_changes` |
| Target branch (for the rollback tag) | webhook |

## Output
A `RiskResult`: `risk_level` (low/medium/high), `feature_flag`,
`feature_flag_safe`, `rollback_notes`, `rationale`, plus `available` and
`rollback_tag` (set when a tag was created). Rendered as a **Rollback & Risk**
section and advisory **Quality Gate** rows.

## Operating Constraints
- Advisory — never blocks the MR (risk level is informational).
- Judges risk/reversibility only — not code quality, security, or style.
- **Read-only by default.** The rollback-anchor tag is created only when
  `ROLLBACK_AUTOTAG=true` and the gate passes; tags are non-destructive and easy
  to delete.
- Runs in parallel with the other reviewers — no added latency.
