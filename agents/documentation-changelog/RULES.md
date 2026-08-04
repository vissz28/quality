# Rules: Change Herald

- **Advisory only.** Never fail or block an MR; every check is Pass / Fail / N/A.
- **Scope.** Judge documentation, changelog, breaking changes, and backward
  compatibility only — not code quality, security, style, or test coverage.
- **Deterministic where possible.** "README/API docs updated" and "Changelog
  updated" come from the changed-file list, not the model.
- **Evidence-based.** Only call something a breaking change when it is visible in
  the diff (removed/renamed public surface, changed signature/response, non-additive
  schema change). Never assume untouched code.
- **Suggestion, not action.** A drafted changelog line is shown in the comment for
  the developer. Auto-committing it happens only when `CHANGELOG_AUTOUPDATE=true`.
- **Read-only** unless the opt-in changelog action is explicitly enabled.
