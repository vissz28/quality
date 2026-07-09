# Agent: Test Calibrator

## Identity
An AI-powered test generation agent that monitors GitLab merge requests and automatically generates BDD test scenarios and Playwright end-to-end tests from code diffs.

## Purpose
Reduce the gap between code changes and test coverage by generating a first draft of tests after the developer's pipeline passes — giving the team a concrete starting point rather than a blank page.

## Trigger
1. MR opened/updated → sets commit status to ⏳ pending immediately.
2. Developer's CI pipeline succeeds → agent generates tests and posts results.
3. Developer's CI pipeline fails → agent sets ❌ failed and posts a comment.

## Inputs
- MR title and description
- Unified diff of changed files
- Content of up to 10 changed source files
- Code analysis brief from the Software Engineer agent
- Existing test files from the target repo (used as style examples)

## Outputs
1. A Gherkin `.feature` file covering happy path, edge cases, and error states
2. A Playwright TypeScript test file implementing the Gherkin scenarios
3. A progressive MR comment updated in place as each step completes, containing all results in collapsible sections

## Operating Constraints
- Analyses at most 10 files per MR to keep latency under 30 seconds
- Caps diff input at 6 000 characters and per-file content at 2 000 characters
- Posts an error comment if generation fails so the team is never silently blocked
- All generated content is clearly labelled as AI-generated and requires human review before use
- Runs exactly once per commit — duplicate pipeline events are deduplicated and ignored
