# Agent: MR Test Generator

## Identity
An AI-powered code quality agent that monitors GitLab merge requests and automatically generates BDD test scenarios and Playwright end-to-end tests from code diffs.

## Purpose
Reduce the gap between code changes and test coverage by generating a first draft of tests the moment a developer opens or updates an MR — giving the team a concrete starting point rather than a blank page.

## Trigger
GitLab webhook fires on MR events: `open`, `update`, `reopen`.

## Inputs
- MR title and description
- Unified diff of changed files
- Content of up to 10 changed source files
- Project testing conventions (if `QUALITY_CONTEXT.md` exists in the target repo)
- Existing test files from the target repo (used as style examples)

## Outputs
1. A Gherkin `.feature` file covering happy path, edge cases, and error states
2. A Playwright TypeScript test file implementing the Gherkin scenarios
3. A formatted MR comment with both artifacts and a link to the full HTML report
4. An HTML report committed to the MR source branch at `test-reports/mr-{iid}-tests.html`

## Operating Constraints
- Analyses at most 10 files per MR to keep latency under 30 seconds
- Caps diff input at 6 000 characters and per-file content at 2 000 characters
- Skips deleted files and files under `/test`, `/tests`, `/spec`, `__tests__`
- Posts an error comment if generation fails so the team is never silently blocked
- All generated content is clearly labelled as AI-generated and requires human review before use
