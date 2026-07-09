# Rules: Test Calibrator

## R1 — Learn from existing tests
Fetch up to 3 existing test files from the target repo (files matching `**/*.spec.ts`, `**/*.test.ts`, `**/*.spec.py`, `**/test_*.py`) before generating.
Include them in the prompt as: `## Existing test style — match this`.

**Why:** Style consistency matters more than theoretical correctness. Tests that look alien to the codebase get deleted; tests that fit get kept and extended.

## R2 — Never block the MR
All generation happens in a background task. The webhook endpoint returns immediately.
On any failure: post a short error comment, log the exception, and exit cleanly.

**Why:** A quality tool that blocks MR feedback will be disabled by the team.

## R3 — Respect file caps
Never analyse more than 10 files or send more than 8 000 tokens of diff to the model.
When the diff exceeds the cap, prefer files touched most (most lines changed) and note the truncation in the comment.

**Why:** Large MRs produce noisy, low-quality generations. A focused report on the most impactful files is more useful than a sprawling one.

## R4 — Run exactly once per commit
Track completed runs with a persistent in-memory set keyed by `(project_id, commit_sha)`.
If a duplicate pipeline success event arrives after completion, discard it immediately without any API calls.
Failed runs are not marked done — they can be retried on the next push.

**Why:** GitLab fires multiple pipeline success events (branch pipeline + MR detached pipeline). Without deduplication the agent runs twice, posting a duplicate comment and wasting API quota.

## R5 — Use the Software Engineer brief
The code analysis brief from the Software Engineer agent is injected into the prompt under `## Code Analysis` before the diff.
If the brief is unavailable, proceed with diff only — never skip generation because analysis failed.

**Why:** The brief provides intent and risk context that the raw diff cannot express. Tests written with it are more accurate and targeted.
