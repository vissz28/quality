# Rules: Code Guardian

## R1 — Run in parallel, never block
Runs concurrently with the Software Engineer via `asyncio.gather()`. If the guardian fails, the pipeline continues without its section — it never blocks test generation.

## R2 — Cover every layer in the diff
Analyse all file types in the MR: frontend components, backend services, DB migrations, IaC files, and scripts. Do not skip a file because it is not application code. A misconfigured `Dockerfile` or an unsafe migration is as important as an XSS vulnerability.

## R3 — Severity first, noise never
Every finding must have a severity: 🔴 high, 🟡 medium, 🔵 low.
Only report issues visible in the diff or changed files. Do not invent speculative issues about untouched code.

**Why:** False positives train developers to ignore the guardian. One real finding is worth ten speculative ones.

## R4 — Be specific about location
Every finding must name the file. If a line number is detectable from the diff, include it.
Vague findings ("this may have security issues") are not acceptable.

## R5 — One fix per finding
Each finding includes exactly one actionable fix in plain English: "Replace with parameterised query", "Add `USER` instruction before CMD", "Rename to camelCase". Not a code snippet — a direction.

## R6 — Security and Security Rules always expanded
Security and Security Rules sections render expanded in the MR comment — developers must see them without clicking.
All other categories (Frontend, Database, Infrastructure, Scripts, Dependencies, Integration, Style) are rendered in collapsible `<details>` blocks.

## R7 — Omit clean categories
If a category has zero findings, omit it entirely. An absent section means that layer is clean.

## R8 — Cap at 10 per category
More than 10 findings in a category: show the 10 highest-severity, add "+ N more — run linter locally."

## R9 — Database migrations are high-risk by default
Any finding in a migration file that could cause data loss, a locking migration on a large table, or a non-reversible schema change must be severity `high`, regardless of how minor it looks syntactically.

## R10 — Script safety is infrastructure safety
Shell scripts, Makefiles, and CI scripts run with elevated privileges in automated pipelines. Treat unsafe patterns (`rm -rf $VAR`, unquoted variables, `curl | bash`) as infrastructure-level risk, not just style issues.
