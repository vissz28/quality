import asyncio
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


TIMEOUT = 300  # 5 minutes

_PLAYWRIGHT_CONFIG = """\
import { defineConfig } from '@playwright/test';
export default defineConfig({
  timeout: 30_000,
  retries: 0,
  reporter: 'json',
});
"""

_PACKAGE_JSON = """\
{
  "name": "generated-tests",
  "version": "1.0.0",
  "dependencies": {
    "@playwright/test": "latest"
  }
}
"""


@dataclass
class TestResult:
    title: str
    status: str          # "passed" | "failed" | "skipped"
    error: str = ""
    classification: str = ""   # "BUG" | "SETUP" | "TIMEOUT" | ""
    duration_ms: int = 0


@dataclass
class ExecutionSummary:
    results: list[TestResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_s: float = 0.0
    execution_error: str = ""


class TestExecutor:
    async def run(self, playwright_code: str) -> ExecutionSummary:
        summary = ExecutionSummary()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "generated.spec.ts").write_text(playwright_code, encoding="utf-8")
            (tmp / "playwright.config.ts").write_text(_PLAYWRIGHT_CONFIG, encoding="utf-8")
            (tmp / "package.json").write_text(_PACKAGE_JSON, encoding="utf-8")

            # Install @playwright/test if needed (fast if already cached)
            try:
                install = await asyncio.create_subprocess_exec(
                    "npm", "install", "--prefer-offline", "--no-audit",
                    cwd=tmp_dir,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, install_err = await asyncio.wait_for(install.communicate(), timeout=120)
            except FileNotFoundError:
                summary.execution_error = "Node.js is not available in this environment."
                return summary
            except asyncio.TimeoutError:
                summary.execution_error = "npm install timed out."
                return summary

            if install.returncode not in (0, 1):
                summary.execution_error = f"npm install failed: {install_err.decode()[:200]}"
                return summary

            # Run playwright
            try:
                proc = await asyncio.create_subprocess_exec(
                    "npx", "playwright", "test", "generated.spec.ts",
                    "--reporter=json",
                    cwd=tmp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT
                )
            except FileNotFoundError:
                summary.execution_error = "Playwright not found — run `npx playwright install` first."
                return summary
            except asyncio.TimeoutError:
                summary.execution_error = "Test execution timed out after 5 minutes."
                return summary

            summary = _parse_results(stdout.decode("utf-8", errors="replace"))

        return summary


def _classify(error: str) -> str:
    if re.search(r"timeout|Timeout|timed out", error):
        return "TIMEOUT"
    if re.search(
        r"locator\.|getBy|selector|net::|ERR_|Navigation|page\.|baseURL|fixture|not found", error
    ):
        return "SETUP"
    return "BUG"


def _parse_results(raw: str) -> ExecutionSummary:
    summary = ExecutionSummary()

    # Playwright JSON output may have non-JSON lines before/after — find the JSON blob
    try:
        start = raw.index("{")
        data = json.loads(raw[start:])
    except (ValueError, KeyError):
        summary.execution_error = f"Could not parse Playwright output: {raw[:200]}"
        return summary

    stats = data.get("stats", {})
    summary.passed = stats.get("expected", 0)
    summary.failed = stats.get("unexpected", 0)
    summary.skipped = stats.get("skipped", 0)
    summary.duration_s = round(stats.get("duration", 0) / 1000, 1)

    for suite in _flatten_suites(data.get("suites", [])):
        for spec in suite.get("specs", []):
            title = spec.get("title", "unknown")
            for test in spec.get("tests", []):
                status = test.get("status", "unknown")
                error_msg = ""
                classification = ""
                if status == "unexpected":
                    results_list = test.get("results", [])
                    if results_list:
                        err = results_list[0].get("error", {})
                        error_msg = err.get("message", "").split("\n")[0][:120]
                    classification = _classify(error_msg)
                    status = "failed"
                elif status == "expected":
                    status = "passed"

                duration = 0
                if test.get("results"):
                    duration = test["results"][0].get("duration", 0)

                summary.results.append(TestResult(
                    title=title,
                    status=status,
                    error=error_msg,
                    classification=classification,
                    duration_ms=duration,
                ))

    return summary


def _flatten_suites(suites: list) -> list:
    flat = []
    for s in suites:
        flat.append(s)
        flat.extend(_flatten_suites(s.get("suites", [])))
    return flat
