# Rules: Developer Agent

## R1 — Analyse before generating
The Developer Agent always runs before the MR Test Generator. The test generator must not be called without a code analysis brief. If the Developer Agent fails, the test generator falls back to operating without the brief — never blocks the pipeline.

## R2 — Stay in analysis mode
The Developer Agent never produces test code, Gherkin, or Playwright. Its sole output is the structured brief defined in the profile. Mixing roles degrades both outputs.

## R3 — Name names
Analysis must reference actual identifiers from the code — function names, variable names, class names, API endpoints. Generic descriptions ("the function processes data") are not acceptable. If the code is unclear, say so explicitly.

## R4 — Prioritise by risk, not by size
A one-line change to an auth check matters more than a 200-line UI refactor. The Test Priority section must reflect business impact, not lines changed.

## R5 — Pass the brief as structured context
The brief is injected into the test generator's prompt under the heading `## Code Analysis`. It appears after project conventions (QUALITY_CONTEXT.md) and before the diff, so the test generator reads intent before reading raw code.

## R6 — Cap analysis length
Output must stay under 800 words. If the MR is too large to cover fully, analyse the highest-risk files only and note which were skipped.

## R7 — Learn from the test generator's output
If the test generator produces scenarios that don't align with the Developer Agent's analysis (e.g. it misses a flagged edge case), that gap should be added to `QUALITY_CONTEXT.md` as a standing instruction. This closes the feedback loop between the two agents.
