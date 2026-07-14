import json
import re
from dataclasses import dataclass, field
import anthropic
from pathlib import Path

MODEL = "claude-sonnet-4-6"

# Categories the guardian reports; used for both rendering and gating.
_CATEGORIES = (
    "security", "security_rules", "frontend", "database",
    "infrastructure", "scripts", "dependencies", "integration", "style",
)
_SECURITY_CATEGORIES = ("security", "security_rules")


@dataclass
class GuardianResult:
    """Rendered markdown plus the structured findings the quality gate needs."""
    markdown: str = ""
    findings: dict[str, list[dict]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.findings.values())

    @property
    def high(self) -> int:
        return sum(
            1 for v in self.findings.values() for f in v if f.get("severity") == "high"
        )

    @property
    def high_security(self) -> int:
        return sum(
            1
            for cat in _SECURITY_CATEGORIES
            for f in self.findings.get(cat, [])
            if f.get("severity") == "high"
        )

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
    ) -> GuardianResult:
        """Return the rendered findings section plus structured findings.

        On failure returns an empty result (empty markdown, no findings) so the
        pipeline continues — the guardian never blocks by itself.
        """
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
            findings = {k: data.get(k, []) for k in _CATEGORIES if data.get(k)}
            return GuardianResult(markdown=_format(data), findings=findings)
        except Exception:
            return GuardianResult()


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(cleaned)


def _format(data: dict) -> str:
    inner_sections = []

    for key in ("security", "security_rules", "frontend", "database", "infrastructure", "scripts", "dependencies", "integration", "style"):
        findings = data.get(key, [])
        if not findings:
            continue

        label = _CATEGORY_LABELS[key]
        count = len(findings)
        table = _dep_table(findings) if key == "dependencies" else _findings_table(findings)

        if key in _EXPANDED:
            # Expanded categories render inline (no collapsible)
            inner_sections.append(f"**{label}**\n\n{table}")
        else:
            inner_sections.append(
                f"<details>\n"
                f"<summary><strong>{label}</strong> ({count})</summary>\n\n"
                f"{table}\n\n"
                f"</details>"
            )

    if not inner_sections:
        return ""

    total = sum(len(data.get(k, [])) for k in _CATEGORY_LABELS)
    body = "\n\n".join(inner_sections)
    # Return a single <details> block — comment_builder places it between other sections
    return (
        f"<details>\n"
        f"<summary>🛡️ <strong>Code Guardian</strong> ({total} finding{'s' if total != 1 else ''})</summary>\n\n"
        f"{body}\n\n"
        f"</details>"
    )


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
