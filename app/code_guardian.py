import json
import re
import anthropic
from pathlib import Path

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "code-guardian" / "SKILLS.md"


def _extract_skill(name: str) -> str:
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in code-guardian/SKILLS.md")
    return match.group(1).strip()


CODE_GUARDIAN_SYSTEM = _extract_skill("CODE_GUARDIAN_SYSTEM")

_SEVERITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🔵"}

# Categories rendered expanded (no <details> wrapper)
_EXPANDED = {"security", "security_rules"}

_CATEGORY_LABELS = {
    "security":       "🔒 Security",
    "security_rules": "🛡️ Security Rules",
    "frontend":       "🖥️ Frontend",
    "database":       "🗄️ Database",
    "infrastructure": "🏗️ Infrastructure",
    "scripts":        "📜 Scripts",
    "dependencies":   "📦 Dependencies",
    "integration":    "🔗 Integration",
    "style":          "🎨 Style & Conventions",
}


class CodeGuardian:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def review(
        self,
        mr_title: str,
        diff_text: str,
        file_contents: dict[str, str],
    ) -> str | None:
        """Return a formatted Markdown findings section, or None on failure."""
        try:
            context = _build_context(mr_title, diff_text, file_contents)
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=CODE_GUARDIAN_SYSTEM,
                messages=[{"role": "user", "content": context}],
            )
            raw = message.content[0].text.strip()
            data = _parse_json(raw)
            return _format(data)
        except Exception:
            return None


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(cleaned)


def _format(data: dict) -> str:
    sections = []

    for key in ("security", "security_rules", "frontend", "database", "infrastructure", "scripts", "dependencies", "integration", "style"):
        findings = data.get(key, [])
        if not findings:
            continue

        label = _CATEGORY_LABELS[key]
        count = len(findings)

        if key == "dependencies":
            table = _dep_table(findings)
        else:
            table = _findings_table(findings)

        if key in _EXPANDED:
            sections.append(f"#### {label}\n\n{table}")
        else:
            sections.append(
                f"<details>\n"
                f"<summary><strong>{label}</strong> ({count})</summary>\n\n"
                f"{table}\n\n"
                f"</details>"
            )

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"---\n\n### 🛡️ Code Guardian\n\n{body}\n"


def _findings_table(findings: list[dict]) -> str:
    header = "| | Location | Issue | Fix |\n|---|----------|-------|-----|\n"
    rows = []
    for f in findings[:10]:
        icon = _SEVERITY_ICON.get(f.get("severity", "low"), "🔵")
        location = f.get("file", "")
        if f.get("line"):
            location += f":{f['line']}"
        issue = f.get("issue", "").replace("|", "\\|")
        fix = f.get("fix", "").replace("|", "\\|")
        rows.append(f"| {icon} | `{location}` | {issue} | {fix} |")
    return header + "\n".join(rows)


def _dep_table(findings: list[dict]) -> str:
    header = "| | Package | Issue | Fix |\n|---|---------|-------|-----|\n"
    rows = []
    for f in findings[:10]:
        icon = _SEVERITY_ICON.get(f.get("severity", "low"), "🔵")
        pkg = f.get("package", "")
        current = f.get("current", "")
        label = f"`{pkg}` `{current}`" if current else f"`{pkg}`"
        issue = f.get("issue", "").replace("|", "\\|")
        fix = f.get("fix", "").replace("|", "\\|")
        rows.append(f"| {icon} | {label} | {issue} | {fix} |")
    return header + "\n".join(rows)


def _build_context(mr_title: str, diff_text: str, file_contents: dict[str, str]) -> str:
    parts = [f"## MR Title\n{mr_title}"]
    if file_contents:
        files_section = "\n\n".join(
            f"### {path}\n```\n{content[:2000]}\n```"
            for path, content in list(file_contents.items())[:10]
        )
        parts.append(f"## Changed Files\n{files_section}")
    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")
    parts.append("Produce the findings JSON:")
    return "\n\n".join(parts)
