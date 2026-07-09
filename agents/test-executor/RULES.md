# Rules: Test Executor

## R1 — Always edit the existing comment, never post a new one
Append results to the comment already created by the Test Calibrator using its `note_id`.
The developer sees one continuous comment that evolves: analysis → Gherkin → Playwright → results.
Never post a second comment — it creates noise and breaks the progressive UX.

## R2 — Never block the MR on test failures
Test failures do not change the commit status set by the Test Calibrator.
Results are informational. Generated tests may fail due to selector issues, missing env vars, or environment differences — that is expected for a first draft.

## R3 — Show a table, not raw logs
Format results as a Markdown table with one row per test:
- ✅ for passed
- ❌ for failed (include the first error line)
- ⚠️ for skipped

Never dump raw Playwright stdout into the comment.

**Why:** Raw logs are unreadable in a GitLab comment. A table gives the developer the signal they need in 10 seconds.

## R4 — Classify failures
For each failing test, add a one-word label in the table:
- `BUG` — assertion failure on actual application behaviour
- `SETUP` — selector not found, fixture missing, env var not set
- `TIMEOUT` — test exceeded time limit

**Why:** The developer needs to know whether to fix the code or fix the test.

## R5 — Handle execution errors gracefully
If `npx playwright test` cannot start (Node not found, Playwright not installed, subprocess timeout), post a single error row in the table:
```
| ⚠️ Execution failed | — | <error message> |
```
Never silently skip — the developer must always see that execution was attempted.
