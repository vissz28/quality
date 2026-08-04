"""Documentation & Breaking Changes agent — checks docs/changelog follow-through
and breaking-change posture. Advisory only; never blocks.

Deterministic signals (was a README/API doc touched? was a CHANGELOG touched?)
are computed from the changed-file list. The breaking-change and backward-compat
judgement, and a drafted changelog line, come from the model.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "documentation-changelog" / "SKILLS.md"

# Filename signals (matched case-insensitively against the path basename/parts).
_CHANGELOG_RE = re.compile(r"(^|/)changelog", re.IGNORECASE)
_DOC_RE = re.compile(r"(^|/)readme|(^|/)docs?/|\.(md|mdx|rst|adoc)$|openapi|swagger", re.IGNORECASE)


def _extract_skill(name: str) -> str:
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in documentation-changelog/SKILLS.md")
    return match.group(1).strip()


DOC_REVIEW_SYSTEM = _extract_skill("DOC_REVIEW_SYSTEM")


def changelog_touched(paths: list[str]) -> bool:
    return any(_CHANGELOG_RE.search(p or "") for p in paths)


def docs_touched(paths: list[str]) -> bool:
    return any(_DOC_RE.search(p or "") for p in paths)


@dataclass
class DocResult:
    available: bool = False
    docs_updated: bool = False
    changelog_updated: bool = False
    breaking_changes: bool = False
    backward_compatible: bool = True
    breaking_documented: bool = True
    notes: str = ""
    suggested_changelog: str = ""
    doc_files: list[str] = field(default_factory=list)


class DocReviewer:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def review(
        self,
        mr_title: str,
        mr_description: str,
        diff_text: str,
        changed_paths: list[str],
    ) -> DocResult:
        docs_updated = docs_touched(changed_paths)
        changelog_updated = changelog_touched(changed_paths)
        doc_files = [p for p in changed_paths if _DOC_RE.search(p or "") or _CHANGELOG_RE.search(p or "")]

        # Deterministic result is always available even if the model call fails.
        result = DocResult(
            available=True,
            docs_updated=docs_updated,
            changelog_updated=changelog_updated,
            doc_files=doc_files,
        )
        try:
            context = _build_context(mr_title, mr_description, diff_text, changed_paths)
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=DOC_REVIEW_SYSTEM,
                messages=[{"role": "user", "content": context}],
            )
            data = _parse_json(message.content[0].text.strip())
            result.breaking_changes = bool(data.get("breaking_changes", False))
            result.backward_compatible = bool(data.get("backward_compatible", True))
            result.breaking_documented = bool(data.get("breaking_documented", True))
            result.notes = str(data.get("notes", "") or "")
            # Only surface a changelog suggestion when the diff didn't already add one.
            if not changelog_updated:
                result.suggested_changelog = str(data.get("suggested_changelog", "") or "")
        except Exception:
            # Keep the deterministic file signals; leave the model fields at safe defaults.
            pass
        return result


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(cleaned)


def _build_context(mr_title: str, mr_description: str, diff_text: str, changed_paths: list[str]) -> str:
    parts = [f"## MR Title\n{mr_title}"]
    if mr_description:
        parts.append(f"## MR Description\n{mr_description[:2000]}")
    if changed_paths:
        files = "\n".join(f"- `{p}`" for p in changed_paths[:30])
        parts.append(f"## Changed Files\n{files}")
    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")
    parts.append("Produce the documentation-review JSON:")
    return "\n\n".join(parts)
