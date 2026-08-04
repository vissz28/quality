"""SonarQube signal — reads an integrated project's quality gate from a
self-hosted SonarQube server so it can be surfaced as a pipeline step and folded
into the Quality Gate verdict.

This never runs a scan itself; the integrated project's own CI does that. We only
read the already-computed result via the SonarQube Web API. Configuration comes
from the environment:

    SONARQUBE_URL          base URL of the self-hosted server (required to enable)
    SONARQUBE_TOKEN        user/project analysis token (required to enable)
    SONARQUBE_PROJECT_KEY  optional override; when unset the GitLab project path
                           is used as the project key (multi-project webhooks)

When the server is not configured the client is a no-op: `analyse` returns an
unconfigured result and the gate treats it as "not analysed" (never blocks).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

# Metrics we pull for the MR comment. Kept small and human-meaningful.
_METRIC_KEYS = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,sqale_rating,security_rating,reliability_rating"


@dataclass
class SonarQubeResult:
    """Quality gate status plus a few headline measures for one project/branch."""
    configured: bool = False
    status: str | None = None          # "OK" | "ERROR" | "NONE" | None (unavailable)
    measures: dict[str, str] = field(default_factory=dict)
    conditions: list[dict] = field(default_factory=list)
    dashboard_url: str = ""
    error: str | None = None

    @property
    def analysed(self) -> bool:
        """True when the server returned a concrete gate status."""
        return self.status in ("OK", "ERROR")

    @property
    def failed(self) -> bool:
        """True only on a definitive gate failure — infra errors do not count."""
        return self.status == "ERROR"


class SonarQubeClient:
    def __init__(self):
        base = os.environ.get("SONARQUBE_URL", "").rstrip("/")
        token = os.environ.get("SONARQUBE_TOKEN", "")
        self.base = base
        self.token = token
        # SonarQube tokens authenticate as the HTTP basic username with an empty
        # password — the widely compatible method across server versions.
        self._auth = (token, "") if token else None

    @property
    def configured(self) -> bool:
        return bool(self.base and self.token)

    def project_key(self, project_path: str | None) -> str:
        """Resolve the SonarQube project key.

        Prefers an explicit env override (single-project setups); otherwise uses
        the GitLab project path so a single deployment can serve many projects.
        """
        return os.environ.get("SONARQUBE_PROJECT_KEY") or (project_path or "")

    def _dashboard_url(self, project_key: str, branch: str) -> str:
        url = f"{self.base}/dashboard?id={project_key}"
        if branch:
            url += f"&branch={branch}"
        return url

    async def analyse(self, project_path: str | None, branch: str = "") -> SonarQubeResult:
        """Fetch the quality gate status and headline measures for a project.

        Returns an unconfigured result when the server is not set up, and a
        result with `error` set (status None) when a configured server can't be
        reached — neither blocks the gate; only a definitive ERROR does.
        """
        if not self.configured:
            return SonarQubeResult(configured=False)

        project_key = self.project_key(project_path)
        if not project_key:
            return SonarQubeResult(configured=True, error="No SonarQube project key resolved")

        result = SonarQubeResult(
            configured=True,
            dashboard_url=self._dashboard_url(project_key, branch),
        )
        try:
            async with httpx.AsyncClient(timeout=15, auth=self._auth) as client:
                status_params = {"projectKey": project_key}
                if branch:
                    status_params["branch"] = branch
                r = await client.get(
                    f"{self.base}/api/qualitygates/project_status",
                    params=status_params,
                )
                r.raise_for_status()
                project_status = r.json().get("projectStatus", {})
                result.status = project_status.get("status")
                result.conditions = project_status.get("conditions", [])

                measure_params = {"component": project_key, "metricKeys": _METRIC_KEYS}
                if branch:
                    measure_params["branch"] = branch
                mr = await client.get(
                    f"{self.base}/api/measures/component",
                    params=measure_params,
                )
                if mr.status_code == 200:
                    measures = mr.json().get("component", {}).get("measures", [])
                    result.measures = {m["metric"]: m.get("value", "") for m in measures}
        except Exception as e:
            # A configured-but-unreachable server must not break every MR — record
            # the error and leave status None so the gate treats it as unavailable.
            result.error = str(e)[:200]
        return result
