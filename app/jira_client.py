"""Jira signal — reads the story behind an MR so the Scope Matcher agent can
check whether the change implements what the ticket asked for.

Like the SonarQube client this is an optional, read-only integration. When Jira
is not configured (or no ticket key is found on the MR) it is a no-op: callers
receive ``None`` and the scope check degrades to advisory "not evaluated" —
never blocking an MR.

Configuration (Jira Cloud REST API v3, HTTP basic auth email:token):

    JIRA_URL          base URL, e.g. https://mycompany.atlassian.net (required to enable)
    JIRA_EMAIL        account email for basic auth                    (required to enable)
    JIRA_API_TOKEN    API token (id.atlassian.com -> Security)        (required to enable)
    JIRA_PROJECT_KEY  optional; when set, key extraction prefers this project's prefix
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx

# A Jira issue key looks like ABC-123 / PROJ2-4567 (uppercase project + number).
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def extract_issue_key(*texts: str | None, project_key: str | None = None) -> str | None:
    """Return the first Jira issue key found across the given texts.

    Searches in order (typically MR title, description, source branch). When a
    ``project_key`` is provided, a key from that project wins over any other.
    """
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        found.extend(_KEY_RE.findall(text))
    if not found:
        return None
    if project_key:
        prefix = f"{project_key.upper()}-"
        for key in found:
            if key.upper().startswith(prefix):
                return key
    return found[0]


def _flatten_adf(node) -> str:
    """Flatten an Atlassian Document Format description into plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_flatten_adf(n) for n in node)
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "text":
            return node.get("text", "")
        if node_type == "hardBreak":
            return "\n"
        inner = _flatten_adf(node.get("content"))
        # Block-level nodes get a trailing newline so paragraphs/list items separate.
        if node_type in ("paragraph", "heading", "listItem", "blockquote", "codeBlock"):
            return inner + "\n"
        return inner
    return ""


@dataclass
class JiraIssue:
    key: str
    summary: str = ""
    description: str = ""
    url: str = ""


class JiraClient:
    def __init__(self):
        self.base = os.environ.get("JIRA_URL", "").rstrip("/")
        email = os.environ.get("JIRA_EMAIL", "")
        token = os.environ.get("JIRA_API_TOKEN", "")
        self.project_key = os.environ.get("JIRA_PROJECT_KEY") or None
        self._auth = (email, token) if (email and token) else None

    @property
    def configured(self) -> bool:
        return bool(self.base and self._auth)

    async def get_issue(self, key: str | None) -> JiraIssue | None:
        """Fetch a story's summary + description. Returns None when Jira is not
        configured, no key is given, or the issue can't be read — so the caller
        degrades gracefully and never blocks the MR."""
        if not self.configured or not key:
            return None
        try:
            async with httpx.AsyncClient(timeout=15, auth=self._auth) as client:
                r = await client.get(
                    f"{self.base}/rest/api/3/issue/{key}",
                    params={"fields": "summary,description"},
                    headers={"Accept": "application/json"},
                )
                if r.status_code != 200:
                    return None
                fields = r.json().get("fields", {})
                return JiraIssue(
                    key=key,
                    summary=fields.get("summary") or "",
                    description=_flatten_adf(fields.get("description")).strip(),
                    url=f"{self.base}/browse/{key}",
                )
        except Exception:
            return None
