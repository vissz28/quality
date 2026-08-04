# Agent: Trace Warden

*(scope & traceability — module `app/scope_matcher.py`)*

## Identity
A requirements-traceability agent that compares a Merge Request against the Jira
story behind it and the project's own stated purpose, and reports whether the
change delivers what the ticket asked for.

## Purpose
Catch the problems tests, security review, and Sonar cannot: an MR that passes
every technical gate but implements the wrong thing, only part of the story, or
work that doesn't belong in this project. Automates the "Scope & Traceability"
step of a PR quality review.

## Position in the Pipeline
```
GitLab Webhook
      │
      ▼
┌──────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Software Engineer │  │ Code Guardian  │  │ Scope Matcher  │  ← run in parallel
└─────────┬─────────┘  └───────┬────────┘  └───────┬────────┘
          │                    │                   │
          └──────────┬─────────┴───────────────────┘
                     ▼
              Test Calibrator → Test Executor → SonarQube → Quality Gate
```

## Inputs
| Source | Provided by |
|--------|-------------|
| Jira story (summary + description / acceptance criteria) | `JiraClient.get_issue`, key from MR title/description/branch |
| Project identity (name, description) | `GitLabClient.get_project` |
| README excerpt | `GitLabClient.get_file_content(project_id, "README.md", ref)` |
| MR title, description, diff | webhook + `get_mr_changes` |

## Output
A `ScopeResult`: `matches`, `confidence` (high/medium/low), `story_fits_project`,
`rationale`, `mismatches[]`, plus `available` (False when Jira/story/key missing).
Rendered as a **Scope Match** section and an advisory **Quality Gate** row.

## Operating Constraints
- Judges scope/intent only — never code quality, security, or style.
- **Advisory — never blocks the MR.** No Jira config, no ticket key, no README, or
  any API/parse error → `available=False` → "not evaluated", gate unaffected.
- Reads only; never modifies code or the ticket.
- Runs in parallel with the Software Engineer and Code Guardian — adds no latency.
