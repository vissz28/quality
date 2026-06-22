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
        """Create or update a file via the GitLab Commits API."""
        encoded_path = file_path.replace("/", "%2F")
        url = f"{self.base}/projects/{project_id}/repository/files/{encoded_path}"

        payload = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": "text",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            # Try update first, fallback to create
            r = await client.put(url, headers=self.headers, json=payload)
            if r.status_code == 400:
                r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
