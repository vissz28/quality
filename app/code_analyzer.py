import re
import anthropic
from pathlib import Path

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "software-engineer" / "SKILLS.md"


def _extract_skill(name: str) -> str:
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in software-engineer/SKILLS.md")
    return match.group(1).strip()


DEVELOPER_SYSTEM = _extract_skill("DEVELOPER_SYSTEM")


class CodeAnalyzer:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def analyze(
        self,
        mr_title: str,
        mr_description: str,
        diff_text: str,
        file_contents: dict[str, str],
    ) -> str | None:
        """Return a structured code analysis brief, or None on failure (R1 — never block)."""
        try:
            context = _build_context(mr_title, mr_description, diff_text, file_contents)
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=DEVELOPER_SYSTEM,
                messages=[{"role": "user", "content": context}],
            )
            return message.content[0].text.strip()
        except Exception:
            return None


def _build_context(
    mr_title: str,
    mr_description: str,
    diff_text: str,
    file_contents: dict[str, str],
) -> str:
    parts = [f"## MR Title\n{mr_title}"]
    if mr_description:
        parts.append(f"## Description\n{mr_description[:1000]}")
    if file_contents:
        files_section = "\n\n".join(
            f"### {path}\n```\n{content[:2000]}\n```"
            for path, content in list(file_contents.items())[:5]
        )
        parts.append(f"## Changed Files\n{files_section}")
    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")
    parts.append("Produce the structured analysis brief:")
    return "\n\n".join(parts)
