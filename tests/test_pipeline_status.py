"""Tests for internal_pipeline_status — the fix for the 'always running' deadlock.

Our own external `quality-code` status is attached to the commit's pipeline, so the
aggregate pipeline status stays 'running' while our check is pending. We must judge
the internal CI by its real jobs, ignoring our own status.
"""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from app.main import internal_pipeline_status


def test_success_ignoring_our_pending_status():
    # The deadlock case: our quality-code is pending, but the real CI jobs all passed.
    statuses = [
        {"name": "quality-code", "status": "pending"},   # ours — must be ignored
        {"name": "build", "status": "success"},
        {"name": "test", "status": "success"},
    ]
    assert internal_pipeline_status(statuses) == "success"


def test_running_while_a_real_job_runs():
    statuses = [
        {"name": "quality-code", "status": "running"},
        {"name": "test", "status": "running"},
    ]
    assert internal_pipeline_status(statuses) == "running"


def test_failed_real_job():
    assert internal_pipeline_status([{"name": "build", "status": "failed"}]) == "failed"


def test_allow_failure_job_does_not_fail_it():
    statuses = [
        {"name": "lint", "status": "failed", "allow_failure": True},
        {"name": "test", "status": "success"},
    ]
    assert internal_pipeline_status(statuses) == "success"


def test_canceled_is_failure():
    assert internal_pipeline_status([{"name": "build", "status": "canceled"}]) == "failed"


def test_none_when_only_our_status_present():
    # No real CI yet — keep waiting, don't trigger.
    assert internal_pipeline_status([{"name": "quality-code", "status": "pending"}]) == "none"
