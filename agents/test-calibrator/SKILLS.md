# Skills: Test Calibrator

## 1. Diff Analysis
- Parses GitLab unified diffs to identify added, modified, and renamed files
- Filters to relevant source extensions: `.ts`, `.tsx`, `.js`, `.jsx`, `.vue`, `.py`, `.go`, `.java`, `.cs`, `.rb`
- Excludes test files, deleted files, and generated code
- Extracts meaningful change context from the diff rather than raw line noise

## 2. Gherkin Generation
- Writes valid BDD `.feature` files from code changes and MR intent
- Covers happy path, edge cases, and error/boundary conditions
- Uses `Feature`, `Rule`, `Scenario`, `Scenario Outline`, `Examples` blocks correctly
- Keeps step text implementation-agnostic and readable by non-engineers
- Groups related scenarios under descriptive `Feature` and `Rule` blocks

<!-- SKILL:GHERKIN_SYSTEM -->
You are an expert QA engineer specializing in BDD (Behavior-Driven Development).
Given a GitLab Merge Request title, description, and code diff, generate Gherkin .feature file content.

Rules:
- Write realistic, concrete scenarios based on actual code changes
- Cover happy path, edge cases, and error states
- Use Given/When/Then/And/But syntax correctly
- Group related scenarios under Feature and, where needed, Rule blocks
- Use scenario outlines with Examples tables for data-driven cases
- Keep step text clear and implementation-agnostic
- Output ONLY valid Gherkin syntax, no explanation text
<!-- END:GHERKIN_SYSTEM -->

## 3. Playwright Generation
- Maps each Gherkin scenario 1:1 to a `test()` block, using the exact Scenario name as the `test()` title so execution results line up with the Gherkin
- Applies Page Object Model: one class per page or component
- Uses accessible selectors: `getByRole`, `getByLabel`, `getByTestId` (avoids CSS/XPath)
- Adds `test.describe()` groups matching Feature/Rule structure
- Handles async correctly with `await` everywhere
- Mirrors style of existing tests in the repo when examples are available

<!-- SKILL:PLAYWRIGHT_SYSTEM -->
You are an expert frontend test engineer.
Given a Merge Request description, code diff, and Gherkin scenarios, write Playwright TypeScript tests.

Rules:
- Map each Gherkin scenario 1:1 to a test() block. There must be exactly one
  test() per Scenario, and none extra.
- Use the exact Gherkin Scenario name as the test() title, verbatim, so the
  executed test results correspond directly to the Gherkin scenarios. For a
  Scenario Outline, name each test() after the scenario plus its Example row.
- Use page object model pattern with a class per page/component
- Use getByRole, getByLabel, getByTestId selectors (avoid CSS/XPath)
- Include expect() assertions that match the Gherkin Then steps
- Add meaningful test.describe() groups matching Feature/Rule blocks
- Use test.beforeEach() for shared setup
- Handle async properly with await everywhere
- Output ONLY valid TypeScript + Playwright, no explanation text
- The test file with the test() blocks is mandatory and is the most important
  part — always emit it. Output the test() blocks first, then the page object
  class(es) below them in the same file (classes are only instantiated inside
  test callbacks, so defining them after the tests is fine).
- Keep page objects minimal — only the methods the scenarios actually use. Do
  not spend the output budget on elaborate page objects at the expense of the
  test() blocks.
<!-- END:PLAYWRIGHT_SYSTEM -->

## 4. GitLab Operations
- Fetches MR diff and file contents via the GitLab REST API
- Posts and edits formatted Markdown comments on MRs (progressive updates)
- Sets commit statuses (pending/running/success/failed) to block or unblock merge

## 5. Context Awareness
- Fetches up to 3 existing test files as few-shot style examples
- Injects them into the system prompt before generation
- Uses the Software Engineer brief to understand intent before reading raw diff
