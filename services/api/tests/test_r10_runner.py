"""Evidence classification must fail closed even when a command exits successfully."""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "verify_r10", Path(__file__).resolve().parents[3] / "scripts/verify_r10.py"
)
R10 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R10)


def test_successful_command_without_test_evidence_fails(tmp_path):
    runner = R10.Runner(tmp_path, dict(os.environ))
    result = runner.run(
        "missing-evidence",
        "Missing evidence",
        [sys.executable, "-c", "print('done')"],
        validator=lambda: R10.pytest_validation(tmp_path / "missing.xml"),
    )
    assert result["exit_code"] == 0
    assert result["status"] == "FAIL"


@pytest.mark.parametrize(
    "body",
    [
        "",
        '<testcase name="ignored"><skipped/></testcase>',
        '<testcase name="bad"><failure/></testcase>',
    ],
)
def test_empty_skipped_or_failed_required_suite_cannot_pass(tmp_path, body):
    path = tmp_path / "tests.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    with pytest.raises(ValueError):
        R10.pytest_validation(path)


def test_only_named_optional_profiles_can_skip(tmp_path):
    path = tmp_path / "tests.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="real"/>'
        '<testcase classname="test_live_adapters" name="live"><skipped/></testcase>'
        "</testsuite></testsuites>"
    )
    counts = R10.pytest_validation(path, optional_skips=True)
    assert counts["tests"] == 2 and len(counts["skipped"]) == 1
    path.write_text(path.read_text().replace("test_live_adapters", "test_authority"))
    with pytest.raises(ValueError):
        R10.pytest_validation(path, optional_skips=True)


@pytest.mark.parametrize(
    "stats",
    [
        {"expected": 0},
        {"expected": 2, "unexpected": 1},
        {"expected": 2, "flaky": 1},
        {"expected": 2, "skipped": 1},
    ],
)
def test_browser_coverage_cannot_hide_missing_flaky_or_failed_tests(tmp_path, stats):
    path = tmp_path / "browser.json"
    path.write_text(json.dumps({"stats": stats}))
    with pytest.raises(ValueError):
        R10.playwright_counts(path)


def test_failed_command_and_credentials_are_recorded_safely(tmp_path):
    secret = "synthetic-credential-for-test"
    runner = R10.Runner(tmp_path, {**os.environ, "SOME_API_KEY": secret})
    result = runner.run(
        "failed",
        "Failed check",
        [sys.executable, "-c", "import os; print(os.environ['SOME_API_KEY']); raise SystemExit(7)"],
    )
    assert result["status"] == "FAIL" and result["exit_code"] == 7
    assert secret not in (tmp_path / result["log"]).read_text()
    data = R10.report(tmp_path, runner.results, {})
    assert data["r10_status"] == data["selected_checks_status"] == "FAIL"


def test_timeout_is_failure_and_terminates_owned_process(tmp_path):
    runner = R10.Runner(tmp_path, dict(os.environ))
    started = time.monotonic()
    result = runner.run(
        "timeout",
        "Timed-out check",
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout=1,
    )
    assert result["status"] == "FAIL" and "Exceeded" in result["reason"]
    assert time.monotonic() - started < 10


def test_local_success_never_approves_r10_or_human_requirements(tmp_path):
    runner = R10.Runner(tmp_path, dict(os.environ))
    runner.run("local", "Local check", [sys.executable, "-c", "print('passed')"])
    runner.missing(
        "human", "Human session", "Participant evidence required", selected=False, scope="human"
    )
    data = R10.report(tmp_path, runner.results, {"commit": "synthetic"})
    assert data["selected_checks_status"] == "PASS"
    assert data["r10_status"] == "NOT RUN"
    assert data["checks"][-1]["status"] == "NOT RUN"
    assert data["evidence_files"][0]["sha256"]
    runner.missing("required", "Missing required tool", "Install prerequisite")
    assert R10.report(tmp_path, runner.results, {})["selected_checks_status"] == "NOT RUN"
    assert R10.report(tmp_path, [], {})["selected_checks_status"] == "NOT RUN"


def test_release_gate_exit_code_stays_nonzero_after_local_success():
    data = {"selected_checks_status": "PASS", "r10_status": "NOT RUN"}
    assert R10.result_exit_code(data) == 0
    assert R10.result_exit_code(data, require_complete=True) == 2
    assert R10.result_exit_code({"selected_checks_status": "FAIL", "r10_status": "FAIL"}) == 1
