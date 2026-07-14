# Rules: Quality Gate

## R1 — Fail closed on any crossed boundary
The gate passes only if **every** boundary passes. Any single failing check
fails the whole gate and sets the commit status to `failed`.

**Why:** A security or policy boundary is not a majority vote. One high-severity
security hole is enough to block a merge.

## R2 — Security is a hard boundary
Any high-severity finding in the `security` or `security_rules` categories fails
the gate outright, regardless of how few findings there are in total.

## R3 — The 10% red line
If more than 10% of all Code Guardian findings are high severity, the gate
fails. This catches a diff that is broadly risky even when no single security
finding trips R2.

## R4 — The 10% test-failure line
If more than 10% of executed tests failed, the gate fails. Skipped tests count
toward the executed total; an execution error (0 tests run) does not by itself
fail the gate — R2/R3 still apply.

## R5 — Internal pipeline must have passed
The gate never runs before the project's internal pipeline has finished, and a
failed internal pipeline fails the gate. In practice generation is only
triggered on internal-pipeline success, so this check is a backstop.

## R6 — Always explain the verdict
Every check — passed and failed — is rendered in the MR comment with its detail
(counts and percentages). A failed gate names exactly which boundary was
crossed. No silent failures.

## R7 — Deterministic, no model call
The gate is pure arithmetic over the collected signals. It adds no latency and
its decision is reproducible from the same inputs.

## R8 — Thresholds live in one place
`RED_LINE_THRESHOLD` and `TEST_FAILURE_THRESHOLD` in `app/quality_gate.py` are
the single source of truth. Tune the policy there, not in scattered conditionals.
