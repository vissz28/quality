# Agent: Change Herald

*(documentation & breaking changes — module `app/doc_reviewer.py`)*

## Identity
Reviews whether a change keeps its documentation, changelog, and compatibility
promises — the "Documentation & Breaking Changes" step of a PR quality review.

## Purpose
Catch the change that ships correct code but silently breaks callers or leaves the
docs/changelog stale. Flags undocumented breaking changes and dropped backward
compatibility, and drafts a changelog line when one is missing.

## Inputs
| Source | Provided by |
|--------|-------------|
| Changed-file list | `get_mr_changes` (README/API-doc + CHANGELOG detection) |
| MR title, description, diff | webhook + `get_mr_changes` |

## Output
A `DocResult`: `docs_updated`, `changelog_updated` (deterministic from files),
`breaking_changes`, `backward_compatible`, `breaking_documented`, `notes`,
`suggested_changelog`, plus `available`. Rendered as a **Documentation** section
and advisory **Quality Gate** rows.

## Operating Constraints
- Advisory — never blocks the MR.
- Judges docs/compat only — not code quality, security, style, or tests.
- Read-only by default. The optional changelog assist is a *suggestion* in the
  comment; auto-committing a changelog entry is opt-in via `CHANGELOG_AUTOUPDATE`.
- Runs in parallel with the other reviewers — no added latency.
