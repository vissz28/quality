# Rules: MR Test Generator — Learning & Behaviour

## R1 — Read project conventions before generating
Before every generation, attempt to fetch `QUALITY_CONTEXT.md` from the target repo's default branch.
If found, prepend its contents to the system prompt under the heading `## Project Conventions`.
If not found, proceed without it — never fail because the file is absent.

**Why:** Each project has its own naming conventions, component library, selector strategy, and testing patterns. Hardcoded prompts drift from reality; project-owned context stays accurate.

## R2 — Learn from existing tests
Fetch up to 3 existing test files from the target repo (files matching `**/*.spec.ts`, `**/*.test.ts`, `**/*.spec.py`, `**/test_*.py`) before generating.
Include them in the prompt as: `## Existing test style — match this`.

**Why:** Style consistency matters more than theoretical correctness. Tests that look alien to the codebase get deleted; tests that fit get kept and extended.

## R3 — Surface learning signals in the comment
Every MR comment must end with a feedback line:
```
👍 useful · 👎 not useful — your reaction updates the agent's context
```
Log reactions (fetched 10 minutes after posting) to `agents/mr-test-generator/feedback-log.jsonl` in the target repo via a separate scheduled job.

**Why:** Without a feedback signal the agent cannot distinguish good generations from bad ones.

## R4 — Honour explicit overrides in MR description
If the MR description contains a fenced block tagged `quality-context`, treat its contents as project conventions for that MR only — overriding `QUALITY_CONTEXT.md` for this run.

```
```quality-context
Focus on API contract tests. Skip UI interactions.
```
```

**Why:** Developers know best what kind of tests a specific MR needs. Giving them an escape hatch prevents frustration and builds trust.

## R5 — Never block the MR
All generation and committing happens in a background task. The webhook endpoint always returns `202 Accepted` immediately.
On any failure: post a short error comment, log the exception, and exit cleanly.

**Why:** A quality tool that breaks CI or delays MR feedback will be disabled by the team.

## R6 — Respect file caps
Never analyse more than 10 files or send more than 8 000 tokens of diff to the model.
When the diff exceeds the cap, prefer files touched most (most lines changed) and note the truncation in the comment.

**Why:** Large MRs produce noisy, low-quality generations. A focused report on the most impactful files is more useful than a sprawling one.

## R7 — Update QUALITY_CONTEXT.md when patterns stabilise
After 10 positively-reacted generations for a project, propose an update to `QUALITY_CONTEXT.md` by opening a new MR to the target repo that adds or refines the conventions section based on the accepted outputs.

**Why:** The agent's learning should eventually live in the repo, owned and reviewed by the team — not locked in a model or a config nobody can read.

## R8 — Version the prompt
Every generation logs the system prompt hash to the HTML report footer.
When rules or skills files change, the hash changes — making it easy to correlate output quality with prompt versions.

**Why:** Prompt engineering without versioning is archaeology. Track what changed.
