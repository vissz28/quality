"""In-bot SonarCloud scanner.

Instead of triggering a separate GitLab pipeline, the bot scans the reviewed MR
itself: it clones the repo (read-only), runs the `sonar-scanner` CLI as a
subprocess, and uploads the analysis to SonarCloud. The SonarQubeClient then
reads the result back for the comment + gate.

Requirements (provided by the Docker image / environment):
  - `sonar-scanner` on PATH (the image installs the CLI with a bundled JRE).
  - `git` on PATH (to clone the target).
  - SONARQUBE_TOKEN (upload), SONAR_ORG, SONARQUBE_URL (default sonarcloud.io).

Everything is best-effort: any missing tool / clone failure returns False and the
gate treats Sonar as "not analysed" (never blocks).
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """In-bot scanning is OPT-IN: the scanner is memory-heavy and can OOM-kill
    the whole service on a small instance. Only run it when explicitly enabled."""
    return os.environ.get("SONAR_INBOT_SCAN", "").strip().lower() in ("1", "true", "yes", "on")


def available() -> bool:
    """True when in-bot scanning is enabled AND the CLI/git/token/org are present."""
    return bool(
        _enabled()
        and shutil.which("sonar-scanner")
        and shutil.which("git")
        and os.environ.get("SONARQUBE_TOKEN")
        and os.environ.get("SONAR_ORG")
    )


async def run_scan(
    clone_url: str,
    source_branch: str,
    project_key: str,
    mr_iid: int | None = None,
    target_branch: str = "",
) -> bool:
    """Clone the target branch and scan it into SonarCloud.

    Uses PR scope when `mr_iid` is given (new code = the MR diff vs the base
    branch), else a plain branch scan. `sonar.qualitygate.wait` blocks until
    SonarCloud finishes computing the gate, so the caller's read sees a ready
    result. Returns True if the scan ran to completion (regardless of gate
    pass/fail); False on a missing tool, clone failure, or error.
    """
    if not available():
        logger.warning("In-bot Sonar scan skipped: scanner/git/token/org not all present.")
        return False

    host = os.environ.get("SONARQUBE_URL", "https://sonarcloud.io").rstrip("/")
    org = os.environ["SONAR_ORG"]
    scan_env = {**os.environ, "SONAR_TOKEN": os.environ["SONARQUBE_TOKEN"]}
    # The scanner indexes the whole repo and is memory-hungry; the default heap
    # OOMs on non-trivial repos. Raise it (tunable), but note the Render instance
    # must actually have this much RAM free.
    scan_env["SONAR_SCANNER_JAVA_OPTS"] = os.environ.get(
        "SONAR_SCANNER_JAVA_OPTS", "-Xmx2048m"
    )
    # Skip vendored / build / generated dirs so we index far fewer files (less
    # memory, faster) without losing signal on the actual source.
    exclusions = os.environ.get(
        "SONAR_EXCLUSIONS",
        "**/node_modules/**,**/dist/**,**/build/**,**/.next/**,**/coverage/**,"
        "**/vendor/**,**/*.min.js,**/*.map,**/__snapshots__/**",
    )
    workdir = tempfile.mkdtemp(prefix="sonar-scan-")
    try:
        # Full clone so blame / new-code and the PR base branch are available.
        rc = await _run(["git", "clone", "--quiet", clone_url, workdir])
        if rc != 0:
            logger.warning("In-bot Sonar scan: git clone failed.")
            return False
        await _run(["git", "checkout", "--quiet", source_branch], cwd=workdir)

        args = [
            "sonar-scanner",
            f"-Dsonar.host.url={host}",
            f"-Dsonar.organization={org}",
            f"-Dsonar.projectKey={project_key}",
            "-Dsonar.sources=.",
            f"-Dsonar.exclusions={exclusions}",
        ]
        if mr_iid:
            args += [
                f"-Dsonar.pullrequest.key={mr_iid}",
                f"-Dsonar.pullrequest.branch={source_branch}",
                f"-Dsonar.pullrequest.base={target_branch or 'main'}",
            ]
        else:
            args += [f"-Dsonar.branch.name={source_branch}"]
        args += ["-Dsonar.qualitygate.wait=true"]

        rc = await _run(args, cwd=workdir, env=scan_env)
        # rc != 0 can mean a red gate (expected) or a real error; either way the
        # analysis is uploaded, so let the caller read the actual status.
        logger.info(f"In-bot Sonar scan finished (scanner exit {rc}).")
        return True
    except Exception as e:
        logger.warning(f"In-bot Sonar scan error: {str(e)[:200]}")
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
    """Run a subprocess, capturing output; return its exit code."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0 and out:
        text = out.decode("utf-8", "replace")
        # Surface the actual root cause — the wrapper "ERROR" line hides it in a
        # "Caused by:" / exception line, so match those too.
        _KEYS = (
            "error", "caused by", "exception", "authoriz", "authentic",
            "not permitted", "forbidden", "403", "401", "does not exist",
            "license", "quality gate", "not found", "base branch", "insufficient",
        )
        diag = [ln for ln in text.splitlines() if any(k in ln.lower() for k in _KEYS)][:25]
        if diag:
            logger.warning("scan diagnostic lines:\n%s", "\n".join(diag))
        logger.info("scan cmd output tail:\n%s", text[-1500:])
    return proc.returncode if proc.returncode is not None else 1
