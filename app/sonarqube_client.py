"""SonarQube signal — reads an integrated project's quality gate from a
self-hosted SonarQube server so it can be surfaced as a pipeline step and folded
into the Quality Gate verdict.

This client never runs a scan itself; the bot's external scan pipeline does that
(see _run_external_sonar_scan in app/main.py). We only read the already-computed
result via the SonarQube Web API. Configuration comes from the environment:

    SONARQUBE_URL          base URL of the self-hosted server (required to enable)
    SONARQUBE_TOKEN        user/project analysis token (required to enable)
    SONARQUBE_PROJECT_KEY  optional override; when unset the GitLab project path
                           is used as the project key (multi-project webhooks)

When the server is not configured the client is a no-op: `analyse` returns an
unconfigured result and the gate treats it as "not analysed" (never blocks).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Metrics we pull for the MR comment. Kept human-meaningful.
_METRIC_KEYS = (
    "bugs,vulnerabilities,code_smells,security_hotspots,"
    "coverage,duplicated_lines_density,ncloc,sqale_index,"
    "sqale_rating,security_rating,reliability_rating"
)


@dataclass
class SonarQubeResult:
    """Quality gate status plus a few headline measures for one project/branch."""
    configured: bool = False
    status: str | None = None          # "OK" | "ERROR" | "NONE" | None (unavailable)
    measures: dict[str, str] = field(default_factory=dict)
    conditions: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)   # actual bugs/vulns/smells
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
        """Resolve the SonarCloud/SonarQube project key for the repo being scanned.

        The key must follow whichever repo the pipeline is running on, resolved in
        order:
          1. SONARQUBE_PROJECT_KEY — explicit override for a single-repo deployment.
          2. SONAR_ORG set — SonarCloud keys are org-prefixed, so derive
             `<org>_<repo>` from the reviewed project path (e.g. vissz28 + quality
             -> vissz28_quality). This lets one deployment scan many repos, each
             into its own SonarCloud project.
          3. Fallback — the raw GitLab path (group/repo), for self-hosted SonarQube
             where keys aren't org-prefixed.
        """
        explicit = os.environ.get("SONARQUBE_PROJECT_KEY")
        if explicit:
            return explicit
        path = project_path or ""
        org = os.environ.get("SONAR_ORG")
        if org and path:
            repo = path.rstrip("/").split("/")[-1]
            return f"{org}_{repo}"
        return path

    async def ensure_project(self, project_key: str) -> bool:
        """Create the SonarCloud/SonarQube project if missing (idempotent).

        Prevents "component ... not found" on a repo's first scan. No-op when the
        client is unconfigured or no key is given. Treats an "already exists" 400
        as success. Never raises — provisioning is best-effort.
        """
        if not self.configured or not project_key:
            return False
        data = {"project": project_key, "name": project_key.split("_")[-1] or project_key}
        org = os.environ.get("SONAR_ORG")
        if org:
            data["organization"] = org
        try:
            async with httpx.AsyncClient(timeout=15, auth=self._auth) as client:
                r = await client.post(f"{self.base}/api/projects/create", data=data)
                if r.status_code in (200, 201):
                    logger.info("SonarCloud project created: %s", project_key)
                    return True
                # Already provisioned (manually or by a prior scan) → fine.
                if r.status_code == 400 and "exist" in r.text.lower():
                    logger.info("SonarCloud project already exists: %s", project_key)
                    return True
                logger.warning(
                    "ensure_project(%s) failed HTTP %s: %s",
                    project_key, r.status_code, r.text[:300],
                )
                return False
        except Exception as e:
            logger.warning("ensure_project(%s) error: %s", project_key, str(e)[:200])
            return False

    async def delete_project(self, project_key: str) -> bool:
        """Delete the project — used for ephemeral scan cleanup (create→scan→read→
        delete). Requires an admin-scoped token. No-op when unconfigured/no key;
        never raises.
        """
        if not self.configured or not project_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=15, auth=self._auth) as client:
                r = await client.post(f"{self.base}/api/projects/delete", data={"project": project_key})
                return r.status_code in (200, 204)
        except Exception:
            return False

    def _dashboard_url(self, project_key: str, branch: str) -> str:
        url = f"{self.base}/dashboard?id={project_key}"
        if branch:
            url += f"&branch={branch}"
        return url

    async def analyse(
        self, project_path: str | None, branch: str = "", pull_request: str | int | None = None
    ) -> SonarQubeResult:
        """Fetch the quality gate status and headline measures for a project.

        SonarCloud/SonarQube store an MR analysis under `pullRequest=<iid>` and a
        branch analysis under `branch=<name>`. We try, in order of specificity,
        pullRequest → branch → default (main), and use the first scope that has an
        analysis — so we find the result however the pipeline produced it.

        Returns an unconfigured result when the server is not set up, and a result
        with `error` set (status None) when nothing is found or the server can't be
        reached — neither blocks the gate; only a definitive ERROR does.
        """
        if not self.configured:
            return SonarQubeResult(configured=False)

        project_key = self.project_key(project_path)
        if not project_key:
            return SonarQubeResult(configured=True, error="No SonarQube project key resolved")

        # Scopes to try, most specific first. `{}` = the project's default branch.
        scopes: list[dict[str, str]] = []
        if pull_request:
            scopes.append({"pullRequest": str(pull_request)})
        if branch:
            scopes.append({"branch": branch})
        scopes.append({})

        result = SonarQubeResult(
            configured=True,
            dashboard_url=self._dashboard_url(project_key, branch),
        )
        try:
            async with httpx.AsyncClient(timeout=15, auth=self._auth) as client:
                for scope in scopes:
                    r = await client.get(
                        f"{self.base}/api/qualitygates/project_status",
                        params={"projectKey": project_key, **scope},
                    )
                    if r.status_code != 200:
                        continue  # scope not analysed — try the next
                    project_status = r.json().get("projectStatus", {})
                    status = project_status.get("status")
                    if not status or status == "NONE":
                        continue
                    result.status = status
                    result.conditions = project_status.get("conditions", [])
                    mr = await client.get(
                        f"{self.base}/api/measures/component",
                        params={"component": project_key, "metricKeys": _METRIC_KEYS, **scope},
                    )
                    if mr.status_code == 200:
                        measures = mr.json().get("component", {}).get("measures", [])
                        result.measures = {m["metric"]: m.get("value", "") for m in measures}
                    # The actual open issues (bugs/vulns/smells) — worst first.
                    iss = await client.get(
                        f"{self.base}/api/issues/search",
                        params={
                            "componentKeys": project_key,
                            "types": "BUG,VULNERABILITY,CODE_SMELL",
                            "resolved": "false",
                            "s": "SEVERITY",
                            "asc": "false",
                            "ps": 20,
                            **scope,
                        },
                    )
                    if iss.status_code == 200:
                        result.issues = iss.json().get("issues", [])
                    return result
                # No scope had an analysis.
                result.error = "no analysis found (pull request / branch / default)"
        except Exception as e:
            # A configured-but-unreachable server must not break every MR — record
            # the error and leave status None so the gate treats it as unavailable.
            result.error = str(e)[:200]
        return result
