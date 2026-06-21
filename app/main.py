from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import logging

from .config import settings
from .gitlab_client import GitLabClient
from .test_generator import TestGenerator
from .comment_builder import CommentBuilder
from .report_builder import ReportBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MR Test Generator", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/gitlab")
async def gitlab_webhook(request: Request, background_tasks: BackgroundTasks):
    # Validate secret token
    token = request.headers.get("X-Gitlab-Token", "")
    if token != settings.GITLAB_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()

    # Only handle merge_request events
    if payload.get("object_kind") != "merge_request":
        return JSONResponse({"status": "ignored", "reason": "not a merge_request event"})

    mr = payload["object_attributes"]
    action = mr.get("action", "")

    # Only trigger on meaningful MR actions
    if action not in ("open", "update", "reopen"):
        return JSONResponse({"status": "ignored", "reason": f"action '{action}' not handled"})

    project_id = payload["project"]["id"]
    mr_iid = mr["iid"]

    logger.info(f"Processing MR !{mr_iid} (action: {action}) in project {project_id}")

    background_tasks.add_task(
        process_mr,
        project_id=project_id,
        mr_iid=mr_iid,
        mr_title=mr["title"],
        mr_description=mr.get("description", ""),
        source_branch=mr["source_branch"],
        target_branch=mr["target_branch"],
        author=payload.get("user", {}).get("name", "Unknown"),
        mr_url=mr["url"],
    )

    return JSONResponse({"status": "accepted", "mr_iid": mr_iid})


async def process_mr(
    project_id: int,
    mr_iid: int,
    mr_title: str,
    mr_description: str,
    source_branch: str,
    target_branch: str,
    author: str,
    mr_url: str,
):
    gitlab = GitLabClient()
    generator = TestGenerator()

    try:
        # ── 1. Fetch MR diff ───────────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Fetching diff...")
        changes = await gitlab.get_mr_changes(project_id, mr_iid)
        relevant = _filter_relevant_files(changes)

        if not relevant:
            logger.info(f"[MR !{mr_iid}] No relevant files found, skipping.")
            return

        # ── 2. Fetch file contents (up to 10 files) ────────────────────────
        logger.info(f"[MR !{mr_iid}] Fetching {len(relevant[:10])} file(s)...")
        file_contents: dict[str, str] = {}
        for file in relevant[:10]:
            content = await gitlab.get_file_content(
                project_id, file["new_path"], source_branch
            )
            if content:
                file_contents[file["new_path"]] = content

        # ── 3. Generate Gherkin with AI ────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Gherkin...")
        diff_text = _format_diff(relevant)
        gherkin = await generator.generate_gherkin(
            mr_title, mr_description, diff_text, file_contents
        )

        # ── 4. Generate Playwright with AI ─────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Playwright...")
        playwright = await generator.generate_playwright(
            mr_title, diff_text, gherkin, file_contents
        )

        # ── 5. Post bot comment ────────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Posting comment...")
        comment_md = CommentBuilder.build(
            mr_iid=mr_iid,
            mr_title=mr_title,
            changed_files=[f["new_path"] for f in relevant],
            gherkin=gherkin,
            playwright=playwright,
        )
        await gitlab.post_mr_comment(project_id, mr_iid, comment_md)

        # ── 6. Commit HTML report to branch ───────────────────────────────
        logger.info(f"[MR !{mr_iid}] Committing HTML report...")
        html_report = ReportBuilder.build(
            mr_iid=mr_iid,
            mr_title=mr_title,
            mr_url=mr_url,
            author=author,
            source_branch=source_branch,
            target_branch=target_branch,
            changed_files=relevant,
            gherkin=gherkin,
            playwright=playwright,
        )
        await gitlab.commit_file(
            project_id=project_id,
            branch=source_branch,
            file_path=f"test-reports/mr-{mr_iid}-tests.html",
            content=html_report,
            commit_message=f"chore(tests): AI-generated report for MR !{mr_iid} [skip ci]",
        )

        logger.info(f"[MR !{mr_iid}] ✅ Done.")

    except Exception as e:
        logger.exception(f"[MR !{mr_iid}] ❌ Failed: {e}")
        # Post error comment so the team knows something went wrong
        error_comment = (
            f"⚠️ **AI Test Generator** failed to process this MR.\n\n"
            f"```\n{str(e)}\n```"
        )
        try:
            await gitlab.post_mr_comment(project_id, mr_iid, error_comment)
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────

RELEVANT_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".vue",
    ".py", ".go", ".java", ".cs", ".rb",
}

def _filter_relevant_files(changes: list[dict]) -> list[dict]:
    """Keep only modified source files, skip deletes and test files."""
    result = []
    for change in changes:
        path: str = change.get("new_path", "")
        if change.get("deleted_file"):
            continue
        if any(x in path for x in ("/test", "/tests", "/spec", "__tests__")):
            continue
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext in RELEVANT_EXTENSIONS:
            result.append(change)
    return result


def _format_diff(changes: list[dict]) -> str:
    """Produce a compact unified diff summary for the AI prompt."""
    parts = []
    for change in changes:
        path = change.get("new_path", "")
        diff = change.get("diff", "")
        if diff:
            parts.append(f"--- {path} ---\n{diff[:3000]}")  # cap per file
    return "\n\n".join(parts)
