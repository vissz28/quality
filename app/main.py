import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from .code_analyzer import CodeAnalyzer
from .code_guardian import CodeGuardian
from .comment_builder import (
    CommentBuilder,
    STEP_ANALYSE,
    STEP_GHERKIN,
    STEP_PLAYWRIGHT,
    STEP_EXECUTE,
    STEP_SONAR,
    STEP_GATE,
    STEP_DONE,
)
from .quality_gate import QualityGate
from .gitlab_client import GitLabClient
from .middleware import GitlabTokenMiddleware
from .sonarqube_client import SonarQubeClient
from .test_executor import ExecutionSummary, TestExecutor
from .test_generator import TestGenerator
from .scope_matcher import ScopeMatcher
from .doc_reviewer import DocReviewer
from .risk_assessor import RiskAssessor
from .jira_client import JiraClient, extract_issue_key

_VERSION = (Path(__file__).parent.parent / "VERSION").read_text().strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# _processing: keys currently being worked on (cleared after each run)
# _done: keys that finished successfully (never cleared — survives retries)
_processing: set[tuple[int, str]] = set()
_done: set[tuple[int, str]] = set()

# Commits registered for pipeline watching: (project_id, sha) -> {branch, mr_iid}
_pending_watches: dict[tuple[int, str], dict] = {}

# One lock per MR so generations are serialized: when a new commit's pipeline
# succeeds while an earlier one is still generating, the new run waits for the
# first to finish instead of overlapping (racing on the live comment / status).
_mr_locks: dict[tuple[int, int], asyncio.Lock] = {}

WATCH_INTERVAL = 2   # seconds between polls


def _get_mr_lock(project_id: int, mr_iid: int) -> asyncio.Lock:
    key = (project_id, mr_iid)
    lock = _mr_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _mr_locks[key] = lock
    return lock


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_watcher_loop(), name="pipeline-watcher")
    logger.info("[Watcher] Background loop started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Test Calibrator", version="1.0.0", lifespan=lifespan)
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

    if action not in ("open", "update", "reopen"):
        return JSONResponse({"status": "ignored", "reason": f"action '{action}' not handled"})

    project_id = payload["project"]["id"]
    mr_iid = mr["iid"]
    commit_sha = mr.get("last_commit", {}).get("id", "")

    # MR webhook fires on every push before the pipeline runs.
    # Mark the commit as pending so the check appears immediately in the MR,
    # then wait for the pipeline success event to start actual generation.
    source_branch = mr.get("source_branch", "")
    logger.info(f"[MR !{mr_iid}] Webhook received — setting status to pending.")
    background_tasks.add_task(_mark_pending, project_id, commit_sha, source_branch, mr_iid)
    return JSONResponse({"status": "pending", "mr_iid": mr_iid})


async def _handle_pipeline_event(
    payload: dict, background_tasks: BackgroundTasks
) -> JSONResponse:
    attrs = payload.get("object_attributes", {})
    status = attrs.get("status")
    source = attrs.get("source", "")
    project_id = payload["project"]["id"]
    project_web_url = payload["project"]["web_url"]
    branch = attrs.get("ref", "")
    pipeline_id = attrs.get("id")
    commit_sha = payload.get("commit", {}).get("id", "")
    mr_iid = (payload.get("merge_request") or {}).get("iid")

    # Only react to pipelines triggered by a push or an MR — ignore scheduled, tag, api, etc.
    if source not in ("push", "merge_request_event", "web", ""):
        logger.info(f"[Pipeline {pipeline_id}] Source '{source}' — ignoring.")
        return JSONResponse({"status": "ignored", "reason": f"pipeline source '{source}' not handled"})

    if status == "success":
        logger.info(f"[Pipeline {pipeline_id}] Succeeded on '{branch}' — triggering test generation.")
        background_tasks.add_task(
            _generate_from_pipeline,
            project_id=project_id,
            project_web_url=project_web_url,
            branch=branch,
            commit_sha=commit_sha,
            mr_iid=mr_iid,
        )
        return JSONResponse({"status": "accepted", "pipeline_id": pipeline_id})

    if status == "failed":
        pipeline_url = project_web_url + f"/-/pipelines/{pipeline_id}"
        background_tasks.add_task(
            notify_pipeline_failure,
            project_id=project_id,
            branch=branch,
            pipeline_id=pipeline_id,
            pipeline_url=pipeline_url,
            mr_iid=mr_iid,
            commit_sha=commit_sha,
        )
        return JSONResponse({"status": "accepted", "pipeline_id": pipeline_id})

    return JSONResponse({"status": "ignored", "reason": f"pipeline status '{status}' not handled"})


async def _mark_pending(project_id: int, commit_sha: str, branch: str = "", mr_iid: int | None = None) -> None:
    if not commit_sha:
        return
    gitlab = GitLabClient()
    try:
        await gitlab.set_commit_status(
            project_id, commit_sha, "pending", "Waiting for pipeline to pass…"
        )
    except Exception:
        logger.warning(f"Failed to set pending status for commit {commit_sha[:8]}")

    watch_key = (project_id, commit_sha)
    if watch_key in _done:
        return

    # Fast-path: pipeline may have already passed before this webhook arrived.
    try:
        pipeline = None
        if mr_iid:
            pipeline = await gitlab.get_mr_pipeline(project_id, mr_iid)
        if not pipeline:
            pipeline = await gitlab.get_pipeline_for_commit(project_id, commit_sha)
        if pipeline:
            status = pipeline.get("status")
            logger.info(f"[MR !{mr_iid}] Immediate pipeline check: {pipeline.get('id')} status={status}")
            if status == "success":
                await _generate_from_pipeline(
                    project_id=project_id,
                    project_web_url=pipeline.get("web_url", "").rsplit("/-/", 1)[0],
                    branch=branch,
                    commit_sha=commit_sha,
                    mr_iid=mr_iid,
                )
                return
            if status in ("failed", "canceled"):
                await notify_pipeline_failure(
                    project_id=project_id,
                    branch=branch,
                    pipeline_id=pipeline.get("id"),
                    pipeline_url=pipeline.get("web_url", ""),
                    mr_iid=mr_iid,
                    commit_sha=commit_sha,
                )
                return
    except Exception:
        logger.exception(f"[MR !{mr_iid}] Immediate pipeline check failed — falling back to watcher.")

    if watch_key not in _pending_watches:
        _pending_watches[watch_key] = {"branch": branch, "mr_iid": mr_iid}
        logger.info(f"[Watcher] Registered commit {commit_sha[:8]} on branch '{branch}'.")


async def _watcher_loop() -> None:
    """Single long-lived loop (started at app startup) that polls all registered commits."""
    gitlab = GitLabClient()
    while True:
        await asyncio.sleep(WATCH_INTERVAL)
        if not _pending_watches:
            continue
        logger.info(f"[Watcher] Checking {len(_pending_watches)} pending commit(s)…")
        for (project_id, commit_sha), info in list(_pending_watches.items()):
            done_key = (project_id, commit_sha)
            if done_key in _done:
                _pending_watches.pop(done_key, None)
                continue

            branch = info.get("branch", "")
            mr_iid = info.get("mr_iid")
            try:
                pipeline = None
                if mr_iid:
                    pipeline = await gitlab.get_mr_pipeline(project_id, mr_iid)
                if not pipeline:
                    pipeline = await gitlab.get_pipeline_for_commit(project_id, commit_sha)
                if not pipeline:
                    logger.info(f"[Watcher] No pipeline yet for {commit_sha[:8]} — waiting.")
                    continue

                status = pipeline.get("status")
                pipeline_id = pipeline.get("id")
                logger.info(
                    f"[Watcher] {commit_sha[:8]} — pipeline {pipeline_id}"
                    f" ({pipeline.get('source', '?')}) status: {status}"
                )

                if status == "success":
                    _pending_watches.pop(done_key, None)
                    await _generate_from_pipeline(
                        project_id=project_id,
                        project_web_url=pipeline.get("web_url", "").rsplit("/-/", 1)[0],
                        branch=branch,
                        commit_sha=commit_sha,
                        mr_iid=mr_iid,
                    )
                elif status in ("failed", "canceled"):
                    _pending_watches.pop(done_key, None)
                    await notify_pipeline_failure(
                        project_id=project_id,
                        branch=branch,
                        pipeline_id=pipeline_id,
                        pipeline_url=pipeline.get("web_url", ""),
                        mr_iid=mr_iid,
                        commit_sha=commit_sha,
                    )
                # else: pending/running — keep watching next cycle

            except Exception:
                logger.exception(f"[Watcher] Error checking pipeline for {commit_sha[:8]}")


async def _generate_from_pipeline(
    project_id: int,
    project_web_url: str,
    branch: str,
    commit_sha: str,
    mr_iid: int | None,
) -> None:
    """Triggered by a pipeline success event — looks up the MR and runs generation."""
    gitlab = GitLabClient()
    try:
        if not mr_iid:
            mr_iid = await gitlab.get_open_mr_for_branch(project_id, branch)
        if not mr_iid:
            logger.info(f"[Pipeline] No open MR for branch '{branch}' — skipping.")
            if commit_sha:
                await gitlab.set_commit_status(project_id, commit_sha, "success", "No MR — skipped.")
            return

        # We only reach here on a pipeline *success* (watcher / pipeline-success
        # webhook / immediate check all gate on success), so the internal
        # pipeline has already finished — start generation directly. Re-checking
        # the pipeline here is unsafe: our own pending "quality-code" status can
        # make the MR-pipelines query read in-progress and defer forever.
        logger.info(f"[MR !{mr_iid}] Internal pipeline finished — starting generation.")
        mr = await gitlab.get_mr_details(project_id, mr_iid)
        await process_mr(
            project_id=project_id,
            project_web_url=project_web_url,
            mr_iid=mr_iid,
            mr_title=mr.get("title", ""),
            mr_description=mr.get("description", "") or "",
            source_branch=mr.get("source_branch", branch),
            target_branch=mr.get("target_branch", "main"),
            author=mr.get("author", {}).get("name", "Unknown"),
            mr_url=mr.get("web_url", ""),
            commit_sha=commit_sha,
        )
    except Exception as e:
        logger.exception(f"[Pipeline] Failed to generate tests for branch '{branch}': {e}")
        if commit_sha:
            try:
                await gitlab.set_commit_status(
                    project_id, commit_sha, "failed", f"Test generation error: {str(e)[:100]}"
                )
            except Exception:
                pass


async def notify_pipeline_failure(
    project_id: int,
    branch: str,
    pipeline_id: int,
    pipeline_url: str,
    mr_iid: int | None,
    commit_sha: str = "",
) -> None:
    gitlab = GitLabClient()
    try:
        if not mr_iid:
            mr_iid = await gitlab.get_open_mr_for_branch(project_id, branch)

        if not mr_iid:
            logger.info(f"[Pipeline {pipeline_id}] No open MR found for branch '{branch}', skipping.")
            return

        if commit_sha:
            await gitlab.set_commit_status(
                project_id, commit_sha, "failed",
                "Pipeline failed — fix it before tests can be generated.",
            )

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
    """Serialize generation per MR — a new run waits for the in-flight one.

    Without this, two pipelines for the same MR (e.g. two quick pushes) generate
    concurrently and race on the live comment and commit status.
    """
    lock = _get_mr_lock(project_id, mr_iid)
    if lock.locked():
        logger.info(f"[MR !{mr_iid}] Generation already running — waiting for it to finish first.")
    async with lock:
        await _process_mr(
            project_id=project_id,
            project_web_url=project_web_url,
            mr_iid=mr_iid,
            mr_title=mr_title,
            mr_description=mr_description,
            source_branch=source_branch,
            target_branch=target_branch,
            author=author,
            mr_url=mr_url,
            commit_sha=commit_sha,
        )


def _flag(name: str) -> bool:
    """Read a boolean opt-in feature flag from the environment (default off)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


async def _gather_project_ctx(gitlab: GitLabClient, project_id: int, ref: str) -> dict:
    """Best-effort project identity for the Trace Warden: name/description + README.
    Any failure is swallowed — the scope check degrades gracefully."""
    ctx: dict[str, str] = {}
    try:
        proj = await gitlab.get_project(project_id)
        ctx["name"] = proj.get("name", "") or ""
        ctx["description"] = proj.get("description", "") or ""
    except Exception:
        pass
    try:
        readme = await gitlab.get_file_content(project_id, "README.md", ref)
        if readme:
            ctx["readme"] = readme
    except Exception:
        pass
    return ctx


async def _append_changelog(
    gitlab: GitLabClient, project_id: int, branch: str, entry: str, mr_iid: int
) -> str | None:
    """Opt-in: append a suggested changelog line to CHANGELOG.md on the source
    branch. Uses [skip ci] so the extra commit doesn't retrigger the pipeline.
    Returns a status note, or None if nothing was written."""
    try:
        line = entry.strip()
        if not line.startswith("-"):
            line = f"- {line}"
        existing = await gitlab.get_file_content(project_id, "CHANGELOG.md", branch)
        if existing is None:
            content = f"# Changelog\n\n## Unreleased\n\n{line}\n"
        elif line in existing:
            return None  # already present
        elif "## Unreleased" in existing:
            content = existing.replace("## Unreleased", f"## Unreleased\n\n{line}", 1)
        else:
            head, _, rest = existing.partition("\n")
            content = f"{head}\n\n## Unreleased\n\n{line}\n{rest}"
        await gitlab.commit_file(
            project_id, branch, "CHANGELOG.md", content,
            f"docs(changelog): add entry for MR !{mr_iid} [skip ci]",
        )
        return f"> 📝 **Change Herald** added a changelog entry on `{branch}`: `{line}`"
    except Exception:
        return None


async def _process_mr(
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
    key = (project_id, commit_sha if commit_sha else f"mr-{mr_iid}")
    if key in _done or key in _processing:
        logger.info(f"[MR !{mr_iid}] Already {'done' if key in _done else 'in progress'} — skipping.")
        return
    _processing.add(key)

    gitlab = GitLabClient()
    generator = TestGenerator()
    analyzer = CodeAnalyzer()
    guardian = CodeGuardian()
    executor = TestExecutor()
    sonarqube = SonarQubeClient()
    scope_matcher = ScopeMatcher()
    doc_reviewer = DocReviewer()
    risk_assessor = RiskAssessor()
    jira = JiraClient()

    async def _set_status(state: str, description: str, url: str = "") -> None:
        if commit_sha:
            try:
                await gitlab.set_commit_status(project_id, commit_sha, state, description, url)
            except Exception:
                logger.warning(f"[MR !{mr_iid}] Failed to set commit status '{state}'")

    # note_id tracks the live comment so we can edit it in place at each step.
    note_id: int | None = None

    async def _update(body: str) -> None:
        if note_id is None:
            return
        try:
            await gitlab.edit_mr_comment(project_id, mr_iid, note_id, body)
        except Exception:
            logger.warning(f"[MR !{mr_iid}] Failed to update comment")

    try:
        # Guard: skip if another process already started or finished this commit.
        if commit_sha:
            existing = await gitlab.get_commit_status(project_id, commit_sha)
            if existing in ("running", "success"):
                logger.info(f"[MR !{mr_iid}] Commit {commit_sha[:8]} already {existing} — skipping.")
                return

        await _set_status("running", "Generating tests…")

        # ── 1. Fetch diff — bail early before posting any comment ─────────
        logger.info(f"[MR !{mr_iid}] Fetching diff...")
        changes = await gitlab.get_mr_changes(project_id, mr_iid)
        relevant = _filter_relevant_files(changes)
        if not relevant:
            logger.info(f"[MR !{mr_iid}] No relevant files — skipping.")
            await _set_status("success", "No source files changed — skipped.")
            _done.add(key)
            return

        # ── 2. Open live comment (internal pipeline already passed) ────────
        # `sections` accumulates the detail blocks; each step re-renders the
        # checklist + everything gathered so far, so every process is visible.
        sections: list[str] = [
            CommentBuilder.changed_files([f["new_path"] for f in relevant])
        ]
        try:
            note_id = await gitlab.post_mr_comment(
                project_id, mr_iid, CommentBuilder.progress(STEP_ANALYSE, sections)
            )
        except Exception:
            logger.warning(f"[MR !{mr_iid}] Could not post initial comment")

        # ── 3. Build diff-focused file contents ───────────────────────────
        file_contents: dict[str, str] = {}
        for file in relevant[:10]:
            diff = file.get("diff", "")
            if diff:
                file_contents[file["new_path"]] = _extract_changed_lines(diff)

        # ── 4. Fetch example tests ─────────────────────────────────────────
        example_tests = await gitlab.get_example_tests(project_id, target_branch)

        # ── 5. Review agents (parallel): engineer, guardian, scope, docs, risk ─
        logger.info(f"[MR !{mr_iid}] Running review agents in parallel...")
        diff_text = _format_diff(relevant)
        changed_paths = [f["new_path"] for f in relevant]

        # Extra context for the Scope Matcher: project identity + linked Jira story.
        project_ctx = await _gather_project_ctx(gitlab, project_id, target_branch)
        issue_key = extract_issue_key(
            mr_title, mr_description, source_branch, project_key=jira.project_key
        )
        story = await jira.get_issue(issue_key)

        code_analysis, guardian_report, scope_report, doc_report, risk_report = await asyncio.gather(
            analyzer.analyze(mr_title, mr_description, diff_text, file_contents),
            guardian.review(mr_title, diff_text, file_contents),
            scope_matcher.match(story, project_ctx, mr_title, mr_description, diff_text),
            doc_reviewer.review(mr_title, mr_description, diff_text, changed_paths),
            risk_assessor.assess(mr_title, mr_description, diff_text),
        )
        if code_analysis:
            sections.append(CommentBuilder.code_analysis(code_analysis))
        else:
            logger.warning(f"[MR !{mr_iid}] Code analysis failed — proceeding without it.")
        if guardian_report.markdown:
            sections.append(guardian_report.markdown)
        else:
            logger.warning(f"[MR !{mr_iid}] Code Guardian returned no findings.")
        sections.append(CommentBuilder.scope_match(scope_report))
        sections.append(CommentBuilder.documentation(doc_report))
        sections.append(CommentBuilder.rollback_risk(risk_report))
        await _update(CommentBuilder.progress(STEP_GHERKIN, sections))

        # ── 6. Generate Gherkin ────────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Gherkin...")
        gherkin = await generator.generate_gherkin(
            mr_title, mr_description, diff_text, file_contents,
            example_tests=example_tests, code_analysis=code_analysis,
        )
        sections.append(CommentBuilder.gherkin(gherkin))
        await _update(CommentBuilder.progress(STEP_PLAYWRIGHT, sections))

        # ── 7. Generate Playwright ─────────────────────────────────────────
        logger.info(f"[MR !{mr_iid}] Generating Playwright...")
        playwright = await generator.generate_playwright(
            mr_title, diff_text, gherkin, file_contents,
            example_tests=example_tests, code_analysis=code_analysis,
        )
        sections.append(CommentBuilder.playwright(playwright))
        await _update(CommentBuilder.progress(STEP_EXECUTE, sections))

        # ── 8. Execute tests and append results ───────────────────────────
        # Always render the execution section, even if the executor itself
        # crashes — otherwise the comment silently ends at the Playwright tests.
        logger.info(f"[MR !{mr_iid}] Running generated tests (test-executor)...")
        try:
            execution = await executor.run(playwright)
        except Exception as e:
            logger.exception(f"[MR !{mr_iid}] Executor crashed: {e}")
            execution = ExecutionSummary(execution_error=f"Executor crashed: {str(e)[:200]}")
        sections.append(CommentBuilder.execution_results(execution))
        if execution.execution_error:
            logger.warning(f"[MR !{mr_iid}] Test execution error: {execution.execution_error}")
        else:
            logger.info(
                f"[MR !{mr_iid}] Execution: {execution.passed} passed, "
                f"{execution.failed} failed, {execution.skipped} skipped."
            )

        # ── 9. SonarQube — read the project's quality gate from the server ─
        await _update(CommentBuilder.progress(STEP_SONAR, sections))
        logger.info(f"[MR !{mr_iid}] Fetching SonarQube analysis...")
        sonar = await sonarqube.analyse(_project_path_from_url(project_web_url), source_branch)
        sections.append(CommentBuilder.sonarqube(sonar))
        if sonar.error:
            logger.warning(f"[MR !{mr_iid}] SonarQube unavailable: {sonar.error}")
        elif sonar.configured:
            logger.info(f"[MR !{mr_iid}] SonarQube status: {sonar.status}")

        # ── 10. Quality gate — the final security/policy boundary ─────────
        await _update(CommentBuilder.progress(STEP_GATE, sections))
        gate = QualityGate().evaluate(guardian_report, execution, sonar_status=sonar.status)
        sections.append(CommentBuilder.quality_gate(gate))
        if gate.passed:
            logger.info(f"[MR !{mr_iid}] Quality gate PASSED.")
        else:
            logger.warning(f"[MR !{mr_iid}] Quality gate FAILED: {gate.summary}")

        # ── Opt-in actions (off by default) ───────────────────────────────
        # Risk Marshal: drop a rollback-anchor tag on the target branch (a
        # known-good pre-merge commit) when the gate passes.
        if gate.passed and _flag("ROLLBACK_AUTOTAG"):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            tag_name = f"rollback/pre-mr{mr_iid}-{stamp}"
            try:
                created = await gitlab.create_tag(
                    project_id, tag_name, target_branch,
                    message=f"Rollback anchor before MR !{mr_iid}",
                )
                risk_report.rollback_tag = tag_name
                sections.append(
                    f"> 🏷️ **Risk Marshal** set rollback anchor `{tag_name}` on `{target_branch}`"
                    + ("" if created else " (already existed)") + "."
                )
                logger.info(f"[MR !{mr_iid}] Rollback tag {tag_name} ensured on {target_branch}.")
            except Exception as e:
                logger.warning(f"[MR !{mr_iid}] Rollback tag failed: {e}")

        # Change Herald: append the suggested changelog entry on the source branch.
        if (
            _flag("CHANGELOG_AUTOUPDATE")
            and doc_report.available
            and not doc_report.changelog_updated
            and doc_report.suggested_changelog
        ):
            note = await _append_changelog(
                gitlab, project_id, source_branch, doc_report.suggested_changelog, mr_iid
            )
            if note:
                sections.append(note)

        # ── 11. Final comment update + commit status ──────────────────────
        sections.append(CommentBuilder.review_footer())
        meta = CommentBuilder.done_meta(
            len(relevant), gherkin.count("Scenario"), playwright.count("test(")
        )
        if gate.passed:
            final = CommentBuilder.progress(STEP_DONE, sections, done=True, meta=meta)
        else:
            final = CommentBuilder.progress(STEP_GATE, sections, failed=True, meta=meta)
        if note_id:
            await _update(final)
        else:
            try:
                note_id = await gitlab.post_mr_comment(project_id, mr_iid, final)
            except Exception:
                pass

        if gate.passed:
            await _set_status("success", "Quality gate passed — review before merging.", mr_url)
            logger.info(f"[MR !{mr_iid}] ✅ Done.")
        else:
            await _set_status("failed", f"Quality gate failed: {gate.summary[:120]}", mr_url)
            logger.info(f"[MR !{mr_iid}] ❌ Done (quality gate failed).")
        _done.add(key)

    except Exception as e:
        logger.exception(f"[MR !{mr_iid}] ❌ Failed: {e}")
        await _set_status("failed", f"Test generation failed: {str(e)[:100]}")
        error_body = f"❌ **Quality Code** failed.\n\n```\n{str(e)}\n```"
        try:
            if note_id:
                await gitlab.edit_mr_comment(project_id, mr_iid, note_id, error_body)
            else:
                await gitlab.post_mr_comment(project_id, mr_iid, error_body)
        except Exception:
            pass
    finally:
        _processing.discard(key)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _project_path_from_url(web_url: str) -> str:
    """Derive the GitLab project path (`group/repo`) from its web URL.

    Used as the default SonarQube project key when SONARQUBE_PROJECT_KEY is unset,
    so one deployment can serve many integrated projects.
    """
    if not web_url:
        return ""
    without_scheme = web_url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[1] if "/" in without_scheme else ""


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
