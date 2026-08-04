# Rules: Risk Marshal

- **Advisory only.** Never fail or block an MR. Risk level is informational; a
  "high" rating warns, it does not gate.
- **Scope.** Judge deployment risk and reversibility only — not code quality,
  security findings, style, or tests.
- **Evidence-based.** Base the risk rating and flag detection only on the diff and
  description. Never assume untouched code.
- **Rollback tag is opt-in and safe.** Create it only when `ROLLBACK_AUTOTAG=true`
  and the gate passes. It tags the target branch's current commit (a known-good
  pre-merge point). Tags are non-destructive; never delete or move refs.
- **No branch/code writes.** This agent never commits code or edits history — the
  only optional write is creating a lightweight tag.
