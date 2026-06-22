import re
import anthropic
from pathlib import Path

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "mr-test-generator" / "skills.md"


def _extract_skill(name: str) -> str:
    """Extract content between <!-- SKILL:name --> and <!-- END:name --> in skills.md."""
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in skills.md")
    return match.group(1).strip()


GHERKIN_SYSTEM = _extract_skill("GHERKIN_SYSTEM")
PLAYWRIGHT_SYSTEM = _extract_skill("PLAYWRIGHT_SYSTEM")


class TestGenerator:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def generate_gherkin(
        self,
        mr_title: str,
        mr_description: str,
        diff_text: str,
        file_contents: dict[str, str],
        quality_context: str | None = None,
        example_tests: list[tuple[str, str]] | None = None,
        code_analysis: str | None = None,
    ) -> str:
        system = _build_system(GHERKIN_SYSTEM, quality_context, example_tests, code_analysis)
        context = _build_context(mr_title, mr_description, diff_text, file_contents)
        prompt = f"{context}\n\nGenerate the Gherkin .feature file for this MR:"

        message = await self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    async def generate_playwright(
        self,
        mr_title: str,
        diff_text: str,
        gherkin: str,
        file_contents: dict[str, str],
        quality_context: str | None = None,
        example_tests: list[tuple[str, str]] | None = None,
        code_analysis: str | None = None,
    ) -> str:
        system = _build_system(PLAYWRIGHT_SYSTEM, quality_context, example_tests, code_analysis)
        context = _build_context(mr_title, "", diff_text, file_contents)
        prompt = (
            f"{context}\n\n"
            f"Gherkin scenarios:\n```gherkin\n{gherkin}\n```\n\n"
            "Generate Playwright TypeScript tests implementing these scenarios:"
        )

        message = await self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


def _build_system(
    base: str,
    quality_context: str | None,
    example_tests: list[tuple[str, str]] | None,
    code_analysis: str | None = None,
) -> str:
    parts = [base]
    if quality_context:
        parts.append(f"## Project Conventions\n{quality_context}")
    if example_tests:
        examples = "\n\n".join(
            f"### {path}\n```\n{content}\n```" for path, content in example_tests
        )
        parts.append(f"## Existing test style — match this\n{examples}")
    if code_analysis:
        parts.append(f"## Code Analysis\n{code_analysis}")
    return "\n\n".join(parts)


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
        parts.append(f"## Key Changed Files\n{files_section}")

    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")

    return "\n\n".join(parts)
