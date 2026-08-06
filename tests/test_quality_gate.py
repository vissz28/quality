"""Unit tests for the QualityGate boundary policy.

Code Guardian was removed from the flow — security is now covered by SonarQube —
so the gate's checks are: internal pipeline · Jira story linked · test failures ·
SonarQube (required).
"""
from app.quality_gate import QualityGate
from app.test_executor import ExecutionSummary


def _exec(passed=0, failed=0, skipped=0) -> ExecutionSummary:
    return ExecutionSummary(passed=passed, failed=failed, skipped=skipped)


def test_gate_passes_when_all_clean():
    result = QualityGate().evaluate(_exec(passed=10), sonar_status="OK")
    assert result.passed
    assert result.reasons == []


def test_gate_fails_when_test_failures_exceed_10pct():
    # 2 failed out of 10 = 20% > 10%.
    result = QualityGate().evaluate(_exec(passed=8, failed=2), sonar_status="OK")
    assert not result.passed
    assert any("Test failures" in r for r in result.reasons)


def test_test_failures_exactly_10pct_passes():
    # 1 failed out of 10 = 10%, not > 10%.
    result = QualityGate().evaluate(_exec(passed=9, failed=1), sonar_status="OK")
    assert result.passed


def test_no_tests_executed_does_not_fail_on_test_ratio():
    # 0 executed -> 0% failure; gate not failed by the test-ratio check alone.
    result = QualityGate().evaluate(_exec(), sonar_status="OK")
    assert result.passed


def test_internal_pipeline_failure_fails_gate():
    result = QualityGate().evaluate(
        _exec(passed=10), internal_pipeline_failed=True, sonar_status="OK"
    )
    assert not result.passed
    assert any("Internal pipeline" in r for r in result.reasons)


def test_jira_story_not_linked_fails_gate():
    result = QualityGate().evaluate(_exec(passed=10), sonar_status="OK", jira_story_linked=False)
    assert not result.passed
    assert any("Jira" in r for r in result.reasons)


def test_sonarqube_error_fails_gate():
    result = QualityGate().evaluate(_exec(passed=10), sonar_status="ERROR")
    assert not result.passed
    assert any("SonarQube" in r for r in result.reasons)


def test_sonarqube_ok_passes():
    result = QualityGate().evaluate(_exec(passed=10), sonar_status="OK")
    assert result.passed


def test_sonarqube_not_analysed_fails():
    # SonarQube is a REQUIRED check — no analysis (N/A) fails the gate.
    result = QualityGate().evaluate(_exec(passed=10), sonar_status=None)
    assert not result.passed
    assert any("SonarQube" in r for r in result.reasons)
