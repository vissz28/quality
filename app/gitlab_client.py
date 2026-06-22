import base64
import os
import httpx


class GitLabClient:
    def __init__(self):
        self.base = os.environ["GITLAB_URL"].rstrip("/") + "/api/v4"
        self.headers = {
            "PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"],
            "Content-Type": "application/json",
        }

    # ── MR ───────────────────────────────────────────────────────────────────

    async def get_mr_changes(self, project_id: int, mr_iid: int) -> list[dict]:
        """Return list of changed files with diff text."""
        url = f"{self.base}/projects/{project_id}/merge_requests/{mr_iid}/changes"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json().get("changes", [])

    async def post_mr_comment(self, project_id: int, mr_iid: int, body: str) -> None:
        """Post a note (comment) on the MR."""
        url = f"{self.base}/projects/{project_id}/merge_requests/{mr_iid}/notes"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, headers=self.headers, json={"body": body})
            r.raise_for_status()

    async def get_latest_pipeline_status(
        self, project_id: int, ref: str
    ) -> str | None:
        """Return the status of the latest pipeline for a branch."""
        url = f"{self.base}/projects/{project_id}/pipelines"
        params = {"ref": ref, "order_by": "id", "sort": "desc", "per_page": 1}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=self.headers, params=params)
            if r.status_code != 200:
                return None
            pipelines = r.json()
            return pipelines[0]["status"] if pipelines else None

    async def get_open_mr_for_branch(
        self, project_id: int, branch: str
    ) -> int | None:
        """Return the IID of the open MR for a branch, or None if not found."""
        url = f"{self.base}/projects/{project_id}/merge_requests"
        params = {"source_branch": branch, "state": "opened"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=self.headers, params=params)
            if r.status_code != 200:
                return None
            mrs = r.json()
            return mrs[0]["iid"] if mrs else None

    # ── Commit status ─────────────────────────────────────────────────────────

    async def get_commit_status(
        self,
        project_id: int,
        sha: str,
        name: str = "AI Test Generator",
    ) -> str | None:
        """Return the latest status string for the named check on a commit, or None."""
        url = f"{self.base}/projects/{project_id}/repository/commits/{sha}/statuses"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=self.headers, params={"name": name})
            if r.status_code != 200:
                return None
            statuses = r.json()
            return statuses[0]["status"] if statuses else None

    async def set_commit_status(
        self,
        project_id: int,
        sha: str,
        state: str,
        description: str,
        target_url: str = "",
    ) -> None:
        """Post a commit status (pending/success/failed) to block or unblock merge."""
        url = f"{self.base}/projects/{project_id}/statuses/{sha}"
        payload = {
            "state": state,
            "name": "AI Test Generator",
            "description": description,
        }
        if target_url:
            payload["target_url"] = target_url
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()

    # ── Learning context (R1, R2) ─────────────────────────────────────────────

    async def get_example_tests(
        self, project_id: int, ref: str, limit: int = 3
    ) -> list[tuple[str, str]]:
        """Fetch up to `limit` existing test files as style examples (R2)."""
        url = f"{self.base}/projects/{project_id}/repository/tree"
        patterns = ["spec", "test", "tests", "__tests__"]
        found: list[tuple[str, str]] = []

        async with httpx.AsyncClient(timeout=15) as client:
            for folder in patterns:
                if len(found) >= limit:
                    break
                r = await client.get(
                    url,
                    headers=self.headers,
                    params={"ref": ref, "path": folder, "recursive": True},
                )
                if r.status_code != 200:
                    continue
                for item in r.json():
                    if len(found) >= limit:
                        break
                    path: str = item.get("path", "")
                    if item.get("type") == "blob" and any(
                        path.endswith(ext)
                        for ext in (".spec.ts", ".test.ts", ".spec.py", "test_.py")
                    ):
                        content = await self.get_file_content(project_id, path, ref)
                        if content:
                            found.append((path, content[:2000]))
        return found

    # ── Files ─────────────────────────────────────────────────────────────────

    async def get_file_content(
        self, project_id: int, file_path: str, ref: str
    ) -> str | None:
        """Return decoded file content or None if not found."""
        encoded_path = file_path.replace("/", "%2F")
        url = f"{self.base}/projects/{project_id}/repository/files/{encoded_path}"
        params = {"ref": ref}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self.headers, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    async def commit_file(
        self,
        project_id: int,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> None:
        """Create or update a file via the GitLab Commits API (actions endpoint)."""
        encoded_path = file_path.replace("/", "%2F")
        async with httpx.AsyncClient(timeout=30) as client:
            # Determine whether to create or update
            check = await client.get(
                f"{self.base}/projects/{project_id}/repository/files/{encoded_path}",
                headers=self.headers,
                params={"ref": branch},
            )
            action = "update" if check.status_code == 200 else "create"

            r = await client.post(
                f"{self.base}/projects/{project_id}/repository/commits",
                headers=self.headers,
                json={
                    "branch": branch,
                    "commit_message": commit_message,
                    "actions": [
                        {
                            "action": action,
                            "file_path": file_path,
                            "content": base64.b64encode(content.encode()).decode(),
                            "encoding": "base64",
                        }
                    ],
                },
            )
            r.raise_for_status()
