"""Rollback & Risk agent — rates deployment risk and rollback posture. Advisory
and read-only: it reports the risk level, feature-flag safety, and whether the
change can be safely rolled back. It never writes to the repo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-6"

_SKILLS_FILE = Path(__file__).parent.parent / "agents" / "rollback-risk" / "SKILLS.md"

_RISK_LEVELS = ("low", "medium", "high")


def _extract_skill(name: str) -> str:
    text = _SKILLS_FILE.read_text()
    match = re.search(rf"<!-- SKILL:{name} -->\n(.*?)<!-- END:{name} -->", text, re.DOTALL)
    if not match:
        raise ValueError(f"Skill block '{name}' not found in rollback-risk/SKILLS.md")
    return match.group(1).strip()


RISK_ASSESS_SYSTEM = _extract_skill("RISK_ASSESS_SYSTEM")


@dataclass
class RiskResult:
    available: bool = False
    risk_level: str = "low"          # "low" | "medium" | "high"
    feature_flag: bool = False
    feature_flag_safe: bool = True
    rollback_notes: str = ""
    rationale: str = ""


class RiskAssessor:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def assess(self, mr_title: str, mr_description: str, diff_text: str) -> RiskResult:
        try:
            context = _build_context(mr_title, mr_description, diff_text)
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=RISK_ASSESS_SYSTEM,
                messages=[{"role": "user", "content": context}],
            )
            data = _parse_json(message.content[0].text.strip())
            level = str(data.get("risk_level", "low") or "low").lower()
            if level not in _RISK_LEVELS:
                level = "low"
            return RiskResult(
                available=True,
                risk_level=level,
                feature_flag=bool(data.get("feature_flag", False)),
                feature_flag_safe=bool(data.get("feature_flag_safe", True)),
                rollback_notes=str(data.get("rollback_notes", "") or ""),
                rationale=str(data.get("rationale", "") or ""),
            )
        except Exception:
            return RiskResult(available=False)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(cleaned)


def _build_context(mr_title: str, mr_description: str, diff_text: str) -> str:
    parts = [f"## MR Title\n{mr_title}"]
    if mr_description:
        parts.append(f"## MR Description\n{mr_description[:2000]}")
    if diff_text:
        parts.append(f"## Diff\n```diff\n{diff_text[:6000]}\n```")
    parts.append("Produce the risk-assessment JSON:")
    return "\n\n".join(parts)
