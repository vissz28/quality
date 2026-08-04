"""Scope Matcher agent — checks whether an MR implements its Jira story and
whether that story fits this project. Advisory only; never blocks.

Mirrors the Code Guardian pattern: one module, its own Anthropic client, a system
prompt extracted from ``agents/scope-traceability/SKILLS.md``, and a dataclass
result. On any missing input or error it returns an unavailable result so the
quality gate treats it as "not evaluated".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import anthropic

if TYPE_CHECKING:
    from .jira_client import JiraIssue

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "scope-traceability" / "SKILLS.md"


def _extract_skill(name: str) -> str:
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in scope-traceability/SKILLS.md")
    return match.group(1).strip()


SCOPE_MATCH_SYSTEM = _extract_skill("SCOPE_MATCH_SYSTEM")


@dataclass
class ScopeResult:
    """Story↔MR alignment verdict. `available` is False when there was nothing to
    evaluate (no Jira story), in which case the gate row reads 'not evaluated'."""
    available: bool = False
    matches: bool = True
    confidence: str = ""            # "high" | "medium" | "low"
    story_fits_project: bool = True
    rationale: str = ""
    mismatches: list[str] = field(default_factory=list)
    issue_key: str = ""
    issue_url: str = ""


class ScopeMatcher:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def match(
        self,
        story: "JiraIssue | None",
        project_ctx: dict[str, str],
        mr_title: str,
        mr_description: str,
        diff_text: str,
    ) -> ScopeResult:
        """Compare the MR against the story + project. Returns an unavailable
        result (advisory) when there is no story or on any failure."""
        if story is None:
            return ScopeResult(available=False)
        try:
            context = _build_context(story, project_ctx, mr_title, mr_description, diff_text)
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SCOPE_MATCH_SYSTEM,
                messages=[{"role": "user", "content": context}],
            )
            data = _parse_json(message.content[0].text.strip())
            return ScopeResult(
                available=True,
                matches=bool(data.get("matches", True)),
                confidence=str(data.get("confidence", "") or ""),
                story_fits_project=bool(data.get("story_fits_project", True)),
                rationale=str(data.get("rationale", "") or ""),
                mismatches=[str(m) for m in (data.get("mismatches") or [])][:5],
                issue_key=story.key,
                issue_url=story.url,
            )
        except Exception:
            return ScopeResult(available=False, issue_key=getattr(story, "key", ""))


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(cleaned)


def _build_context(
    story: "JiraIssue",
    project_ctx: dict[str, str],
    mr_title: str,
    mr_description: str,
    diff_text: str,
) -> str:
    parts = [
        f"## Jira Story ({story.key})\n**Summary:** {story.summary}\n\n{story.description[:3000]}"
    ]
    identity = []
    if project_ctx.get("name"):
        identity.append(f"**Name:** {project_ctx['name']}")
    if project_ctx.get("description"):
        identity.append(f"**Description:** {project_ctx['description']}")
    if project_ctx.get("readme"):
        identity.append(f"**README excerpt:**\n{project_ctx['readme'][:2000]}")
    if identity:
        parts.append("## Project\n" + "\n\n".join(identity))
    parts.append(f"## MR Title\n{mr_title}")
    if mr_description:
        parts.append(f"## MR Description\n{mr_description[:2000]}")
    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")
    parts.append("Produce the scope-match JSON:")
    return "\n\n".join(parts)
