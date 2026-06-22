import anthropic

MODEL = "claude-sonnet-4-6"

GHERKIN_SYSTEM = """You are an expert QA engineer specializing in BDD (Behavior-Driven Development).
Given a GitLab Merge Request title, description, and code diff, generate Gherkin .feature file content.

Rules:
- Write realistic, concrete scenarios based on actual code changes
- Cover happy path, edge cases, and error states
- Use Given/When/Then/And/But syntax correctly
- Group related scenarios under Feature and, where needed, Rule blocks
- Use scenario outlines with Examples tables for data-driven cases
- Keep step text clear and implementation-agnostic
- Output ONLY valid Gherkin syntax, no explanation text
"""

PLAYWRIGHT_SYSTEM = """You are an expert frontend test engineer.
Given a Merge Request description, code diff, and Gherkin scenarios, write Playwright TypeScript tests.

Rules:
- Map each Gherkin scenario to a test() block
- Use page object model pattern with a class per page/component
- Use getByRole, getByLabel, getByTestId selectors (avoid CSS/XPath)
- Include expect() assertions that match the Gherkin Then steps
- Add meaningful test.describe() groups matching Feature/Rule blocks
- Use test.beforeEach() for shared setup
- Handle async properly with await everywhere
- Output ONLY valid TypeScript + Playwright, no explanation text
- Start output with the page object class, then the test file
"""


class TestGenerator:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def generate_gherkin(
        self,
        mr_title: str,
        mr_description: str,
        diff_text: str,
        file_contents: dict[str, str],
    ) -> str:
        context = _build_context(mr_title, mr_description, diff_text, file_contents)
        prompt = f"{context}\n\nGenerate the Gherkin .feature file for this MR:"

        message = await self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=GHERKIN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    async def generate_playwright(
        self,
        mr_title: str,
        diff_text: str,
        gherkin: str,
        file_contents: dict[str, str],
    ) -> str:
        context = _build_context(mr_title, "", diff_text, file_contents)
        prompt = (
            f"{context}\n\n"
            f"Gherkin scenarios:\n```gherkin\n{gherkin}\n```\n\n"
            "Generate Playwright TypeScript tests implementing these scenarios:"
        )

        message = await self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=PLAYWRIGHT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


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
