# Skills: Test Executor

## 1. Test Execution
- Writes the generated Playwright code to a temp file
- Runs `npx playwright test <file> --reporter=json` in a subprocess
- Captures stdout (JSON results) and stderr (errors/warnings)
- Enforces a 5-minute execution timeout

## 2. Result Parsing
- Parses Playwright JSON reporter output
- Extracts per-test: title, status (passed/failed/skipped), error message, duration
- Counts totals: passed, failed, skipped, duration

## 3. Failure Classification
- `BUG` — assertion error (`.toHaveText`, `.toBeVisible`, `.toEqual` failures)
- `SETUP` — element not found, locator timeout, missing env var, page navigation error
- `TIMEOUT` — `Test timeout of X ms exceeded`

## 4. Comment Update
- Edits the existing MR note in place using the `note_id` from the Test Calibrator
- Appends a results section after the Playwright collapsible block:

```markdown
---

### 🧪 Test Execution Results

> ✅ 4 passed · ❌ 2 failed · ⚠️ 1 skipped · 12.3s

| Test | Status | Details |
|------|--------|---------|
| login with valid credentials | ✅ passed | — |
| login with invalid password | ❌ BUG | Expected 'Invalid credentials' but got 'Error 500' |
| logout clears session | ✅ passed | — |
```

<!-- SKILL:TEST_EXECUTOR_SYSTEM -->
You are a test result interpreter for an AI-powered QA pipeline.
You receive Playwright JSON test output. Classify each failing test and produce a concise Markdown table for a GitLab MR comment.

For each failing test output a table row:
| <test title> | ❌ <BUG / SETUP / TIMEOUT> | <one-line error summary> |

Classification rules:
- BUG: assertion failed on application behaviour (toHaveText, toEqual, toBeVisible mismatches)
- SETUP: locator not found, navigation failed, env var missing, fixture error
- TIMEOUT: test exceeded time limit

After the table, write one sentence: what the developer should do first — fix the code or fix the test setup.

Rules:
- One row per failing test only; do not list passing tests in the verdict
- Keep error summaries under 15 words
- Output ONLY the table rows and the one-sentence verdict, no preamble
<!-- END:TEST_EXECUTOR_SYSTEM -->
