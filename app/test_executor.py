import asyncio
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx


TIMEOUT = 300  # 5 minutes

# When set, generated Playwright tests are executed by the Node.js runner
# service (see runner/) instead of shelling out to npm/npx locally. This is the
# path used in Docker/CI, where the Python image has no Node.js.
RUNNER_URL = os.environ.get("RUNNER_URL", "").rstrip("/")

# A prebuilt Playwright workspace baked into the image (see Dockerfile). When
# present we run specs there directly, skipping the slow/flaky per-run
# `npm install` that otherwise causes execution to time out on small hosts.
PLAYWRIGHT_WORKDIR = os.environ.get("PLAYWRIGHT_WORKDIR", "")

_PLAYWRIGHT_CONFIG = """\
import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  timeout: 30_000,
  retries: 0,
  reporter: 'json',
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
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
        if RUNNER_URL:
            return await self._run_remote(playwright_code)
        if PLAYWRIGHT_WORKDIR and Path(PLAYWRIGHT_WORKDIR).is_dir():
            return await self._run_in_workspace(playwright_code, PLAYWRIGHT_WORKDIR)
        return await self._run_local(playwright_code)

    async def _run_in_workspace(self, playwright_code: str, workdir: str) -> ExecutionSummary:
        """Run a spec in a prebuilt workspace — no per-run npm install.

        @playwright/test and the browser are already installed in `workdir`
        (baked into the image), so this only drops a spec file and runs it. This
        avoids the install timeout that left the execution section unrendered.
        """
        summary = ExecutionSummary()
        tmp = Path(workdir)
        spec_name = f"generated-{uuid.uuid4().hex}.spec.ts"
        spec_path = tmp / spec_name
        spec_path.write_text(playwright_code, encoding="utf-8")
        (tmp / "playwright.config.ts").write_text(_PLAYWRIGHT_CONFIG, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "playwright", "test", spec_name, "--reporter=json",
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        except FileNotFoundError:
            summary.execution_error = "Node.js/Playwright not available in the workspace."
            return summary
        except asyncio.TimeoutError:
            summary.execution_error = "Test execution timed out after 5 minutes."
            return summary
        finally:
            spec_path.unlink(missing_ok=True)

        return _parse_results(stdout.decode("utf-8", errors="replace"))

    async def _run_remote(self, playwright_code: str) -> ExecutionSummary:
        """Delegate execution to the Node.js runner service over HTTP."""
        summary = ExecutionSummary()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT + 30) as client:
                resp = await client.post(
                    f"{RUNNER_URL}/run", json={"code": playwright_code}
                )
        except httpx.HTTPError as e:
            summary.execution_error = f"Could not reach test runner: {e}"
            return summary

        raw = resp.text
        # The runner returns either the raw Playwright JSON report, or a JSON
        # object {"execution_error": "..."} when it couldn't run the tests.
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "execution_error" in data:
                summary.execution_error = data["execution_error"]
                return summary
        except ValueError:
            pass

        return _parse_results(raw)

    async def _run_local(self, playwright_code: str) -> ExecutionSummary:
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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_error(msg: str) -> str:
    """Strip ANSI color codes and table-breaking pipes from a Playwright error."""
    msg = _ANSI_RE.sub("", msg)
    return msg.replace("|", "¦").strip()


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
                        error_msg = _clean_error(err.get("message", "").split("\n")[0])[:120]
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
