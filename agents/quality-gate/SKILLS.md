# Skills: Quality Gate

## 1. Signal Collection
- Reads the internal pipeline outcome (from the trigger that started generation)
- Reads structured Code Guardian findings (category + severity per finding)
- Reads the Test Executor summary (passed / failed / skipped counts)

## 2. Boundary Evaluation
- **Internal pipeline** — fails if the project's CI pipeline failed
- **Security checks** — fails on any high-severity `security` / `security_rules` finding
- **Red line** — computes the high-severity share of all findings; fails above 10%
- **Test failures** — computes the failed share of executed tests; fails above 10%

## 3. Verdict & Enforcement
- Passes only when all boundaries pass (fail-closed)
- Sets the external `quality-code` commit status: `success` or `failed`
- Fails the pipeline so a risky MR cannot merge behind a green check

## 4. Transparency
- Renders a 🚦 Quality Gate table in the MR comment
- Shows every check with ✅/❌ and its detail (counts + percentage vs. threshold)
- On failure, the commit-status description names the crossed boundary

## 5. Configuration
- `RED_LINE_THRESHOLD` — high-severity findings fraction (default 0.10)
- `TEST_FAILURE_THRESHOLD` — failed tests fraction (default 0.10)
- Both defined in `app/quality_gate.py`
