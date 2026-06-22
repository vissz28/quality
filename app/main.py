import logging
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from .code_analyzer import CodeAnalyzer
from .comment_builder import CommentBuilder
from .gitlab_client import GitLabClient
from .middleware import GitlabTokenMiddleware
from .report_builder import ReportBuilder
from .test_generator import TestGenerator

_VERSION = (Path(__file__).parent.parent / "VERSION").read_text().strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MR Test Generator", version="1.0.0")
app.add_middleware(GitlabTokenMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok", "version": _VERSION}


@app.post("/webhook/gitlab")
async def gitlab_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    kind = payload.get("object_kind")

    if kind == "pipeline":
        return await _handle_pipeline_event(payload, background_tasks)

    if kind != "merge_request":
        return JSONResponse({"status": "ignored", "reason": "not a merge_request event"})

    mr = payload["object_attributes"]
    action = mr.get("action", "")

    # Only trigger on meaningful MR actions
    if action not in ("open", "update", "reopen"):
        return JSONResponse({"status": "ignored", "reason": f"action '{action}' not handled"})

    project_id = payload["project"]["id"]
    mr_iid = mr["iid"]

    logger.info(f"Processing MR !{mr_iid} (action: {action}) in project {project_id}")

    commit_sha = mr.get("last_commit", {}).get("id", "")

    background_tasks.add_task(
        process_mr,
        project_id=project_id,
        project_web_url=payload["project"]["web_url"],
        mr_iid=mr_iid,
        mr_title=mr["title"],
        mr_description=mr.get("description", ""),
        source_branch=mr["source_branch"],
        target_branch=mr["target_branch"],
        author=payload.get("user", {}).get("name", "Unknown"),
        mr_url=mr["url"],
        commit_sha=commit_sha,
    )

    return JSONResponse({"status": "accepted", "mr_iid": mr_iid})


async def _handle_pipeline_event(
    payload: dict, background_tasks: BackgroundTasks
) -> JSONResponse:
    attrs = payload.get("object_attributes", {})
    status = attrs.get("status")

    if status != "failed":
        return JSONResponse({"status": "ignored", "reason": f"pipeline status '{status}' not handled"})

    project_id = payload["project"]["id"]
    branch = attrs.get("ref", "")
    pipeline_id = attrs.get("id")
    pipeline_url = payload["project"]["web_url"] + f"/-/pipelines/{pipeline_id}"

    # MR IID may be in the payload directly (GitLab >= 15.x)
    mr_iid = (payload.get("merge_request") or {}).get("iid")

    background_tasks.add_task(
        notify_pipeline_failure,
        project_id=project_id,
        branch=branch,
        pipeline_id=pipeline_id,
        pipeline_url=pipeline_url,
        mr_iid=mr_iid,
    )
    return JSONResponse({"status": "accepted", "pipeline_id": pipeline_id})


async def notify_pipeline_failure(
    project_id: int,
    branch: str,
    pipeline_id: int,
    pipeline_url: str,
    mr_iid: int | None,
) -> None:
    gitlab = GitLabClient()
    try:
        if not mr_iid:
            mr_iid = await gitlab.get_open_mr_for_branch(project_id, branch)

        if not mr_iid:
            logger.info(f"[Pipeline {pipeline_id}] No open MR found for branch '{branch}', skipping.")
            return

        comment = (
            f"## ❌ Pipeline Failed\n\n"
            f"Pipeline [#{pipeline_id}]({pipeline_url}) failed on branch `{branch}`.\n\n"
            f"Please check the [pipeline logs]({pipeline_url}) and fix before merging."
        )
        await gitlab.post_mr_comment(project_id, mr_iid, comment)
        logger.info(f"[Pipeline {pipeline_id}] Failure comment posted on MR !{mr_iid}.")
    except Exception as e:
        logger.exception(f"[Pipeline {pipeline_id}] Failed to post failure comment: {e}")


async def process_mr(
    project_id: int,
    project_web_url: str,
    mr_iid: int,
    mr_title: str,
    mr_description: str,
    source_branch: str,
    target_branch: str,
    author: str,
    mr_url: str,
    commit_sha: str = "",
):
    gitlab = GitLabClient()
    generator = TestGenerator()
    analyzer = CodeAnalyzer()

    async def _set_status(state: str, description: str, url: str = "") -> None:
        if commit_sha:
            try:
                await gitlab.set_commit_status(project_id, commit_sha, state, description, url)
            except Exception:
                logger.warning(f"[MR !{mr_iid}] Failed to set commit status '{state}'")

    try:
        await _set_status("pending", "Generating tests…")

        # ── 1. Check pipeline status — skip if failed ─────────────────────
        pipeline_status = await gitlab.get_latest_pipeline_status(project_id, source_branch)
        if pipeline_status == "failed":
            logger.info(f"[MR !{mr_iid}] Pipeline failed — skipping test generation.")
            await _set_status("failed", "Pipeline failed — fix it before generating tests.")
            await gitlab.post_mr_comment(
                project_id, mr_iid,
                "❌ **AI Test Generator** failed: the pipeline is failing on this branch.\n\n"
                "Fix the pipeline first, then push a new commit to trigger test generation."
            )
            return

        # ── 2. Fetch MR diff ───────────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Fetching diff...")
        changes = await gitlab.get_mr_changes(project_id, mr_iid)
        relevant = _filter_relevant_files(changes)

        if not relevant:
            logger.info(f"[MR !{mr_iid}] No relevant files found, skipping.")
            return

        # ── 3. Build diff-focused file contents ────────────────────────────
        # Use only the changed hunks per file — not the full file content.
        # For new files (no previous version), include full diff as context.
        file_contents: dict[str, str] = {}
        for file in relevant[:10]:
            diff = file.get("diff", "")
            if diff:
                file_contents[file["new_path"]] = _extract_changed_lines(diff)

        # ── 3. Fetch example tests for style reference (R2) ──────────────────
        example_tests = await gitlab.get_example_tests(project_id, target_branch)
        if example_tests:
            logger.info(f"[MR !{mr_iid}] {len(example_tests)} example test(s) found.")

        # ── 4. Developer Agent — code analysis brief ──────────────────────
        logger.info(f"[MR !{mr_iid}] Analysing code (developer-agent)...")
        diff_text = _format_diff(relevant)
        code_analysis = await analyzer.analyze(
            mr_title, mr_description, diff_text, file_contents
        )
        if code_analysis:
            logger.info(f"[MR !{mr_iid}] Code analysis ready.")
        else:
            logger.warning(f"[MR !{mr_iid}] Code analysis failed — proceeding without it.")

        # ── 5. Generate Gherkin with AI ────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Gherkin...")
        gherkin = await generator.generate_gherkin(
            mr_title, mr_description, diff_text, file_contents,
            example_tests=example_tests,
            code_analysis=code_analysis,
        )

        # ── 6. Generate Playwright with AI ─────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Playwright...")
        playwright = await generator.generate_playwright(
            mr_title, diff_text, gherkin, file_contents,
            example_tests=example_tests,
            code_analysis=code_analysis,
        )

        # ── 7. Post bot comment ────────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Posting comment...")
        report_url = f"{project_web_url}/-/blob/{source_branch}/test-reports/mr-{mr_iid}-tests.html"
        comment_md = CommentBuilder.build(
            mr_iid=mr_iid,
            mr_title=mr_title,
            changed_files=[f["new_path"] for f in relevant],
            gherkin=gherkin,
            playwright=playwright,
            report_url=report_url,
        )
        await gitlab.post_mr_comment(project_id, mr_iid, comment_md)

        # ── 7. Commit HTML report to branch ───────────────────────────────
        logger.info(f"[MR !{mr_iid}] Committing HTML report to '{source_branch}'...")
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
            code_analysis=code_analysis,
        )
        await gitlab.commit_file(
            project_id=project_id,
            branch=source_branch,
            file_path=f"test-reports/mr-{mr_iid}-tests.html",
            content=html_report,
            commit_message=f"chore(tests): AI-generated report for MR !{mr_iid} [skip ci]",
        )
        logger.info(f"[MR !{mr_iid}] HTML report committed successfully.")

        await _set_status("success", "Tests generated — review before merging.", report_url)
        logger.info(f"[MR !{mr_iid}] ✅ Done.")

    except Exception as e:
        logger.exception(f"[MR !{mr_iid}] ❌ Failed: {e}")
        await _set_status("failed", f"Test generation failed: {str(e)[:100]}")
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


def _extract_changed_lines(diff: str, context: int = 3) -> str:
    """Return only added/removed lines plus `context` surrounding lines from a unified diff.

    Strips hunk headers and unchanged lines beyond the context window so the AI
    sees exactly what changed — not the whole file.
    """
    lines = diff.splitlines()
    result: list[str] = []
    window: list[str] = []

    for line in lines:
        if line.startswith(("@@", "---", "+++")):
            if window:
                result.extend(window)
                window = []
            result.append(line)
        elif line.startswith(("+", "-")):
            result.extend(window)
            window = []
            result.append(line)
        else:
            window.append(line)
            if len(window) > context:
                window.pop(0)

    return "\n".join(result)[:3000]


def _format_diff(changes: list[dict]) -> str:
    """Produce a compact unified diff summary for the AI prompt."""
    parts = []
    for change in changes:
        path = change.get("new_path", "")
        diff = change.get("diff", "")
        if diff:
            parts.append(f"--- {path} ---\n{diff[:3000]}")  # cap per file
    return "\n\n".join(parts)
