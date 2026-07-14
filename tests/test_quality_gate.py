"""Unit tests for the QualityGate boundary policy."""
from app.code_guardian import GuardianResult
from app.quality_gate import QualityGate
from app.test_executor import ExecutionSummary


def _exec(passed=0, failed=0, skipped=0) -> ExecutionSummary:
    return ExecutionSummary(passed=passed, failed=failed, skipped=skipped)


def test_gate_passes_when_all_clean():
    gate = QualityGate()
    result = gate.evaluate(GuardianResult(), _exec(passed=10))
    assert result.passed
    assert result.reasons == []


def test_gate_fails_on_high_severity_security_finding():
    guardian = GuardianResult(findings={"security": [{"severity": "high"}]})
    result = QualityGate().evaluate(guardian, _exec(passed=10))
    assert not result.passed
    assert any("Security" in r for r in result.reasons)


def test_security_rules_high_also_trips_boundary():
    guardian = GuardianResult(findings={"security_rules": [{"severity": "high"}]})
    result = QualityGate().evaluate(guardian, _exec(passed=5))
    assert not result.passed


def test_gate_fails_when_red_line_exceeds_10pct():
    # 2 high out of 10 findings = 20% > 10%.
    findings = {
        "frontend": [{"severity": "high"}, {"severity": "high"}]
        + [{"severity": "low"}] * 8,
    }
    result = QualityGate().evaluate(GuardianResult(findings=findings), _exec(passed=10))
    assert not result.passed
    assert any("red line" in r.lower() for r in result.reasons)


def test_red_line_exactly_10pct_passes():
    # 1 high out of 10 = 10%, not > 10%.
    findings = {"frontend": [{"severity": "high"}] + [{"severity": "low"}] * 9}
    result = QualityGate().evaluate(GuardianResult(findings=findings), _exec(passed=10))
    assert result.passed


def test_gate_fails_when_test_failures_exceed_10pct():
    # 2 failed out of 10 = 20% > 10%.
    result = QualityGate().evaluate(GuardianResult(), _exec(passed=8, failed=2))
    assert not result.passed
    assert any("Test failures" in r for r in result.reasons)


def test_test_failures_exactly_10pct_passes():
    # 1 failed out of 10 = 10%, not > 10%.
    result = QualityGate().evaluate(GuardianResult(), _exec(passed=9, failed=1))
    assert result.passed


def test_internal_pipeline_failure_fails_gate():
    result = QualityGate().evaluate(
        GuardianResult(), _exec(passed=10), internal_pipeline_failed=True
    )
    assert not result.passed
    assert any("Internal pipeline" in r for r in result.reasons)


def test_no_tests_executed_does_not_fail_on_test_ratio():
    # 0 executed -> 0% failure; gate not failed by the test-ratio check alone.
    result = QualityGate().evaluate(GuardianResult(), _exec())
    assert result.passed
