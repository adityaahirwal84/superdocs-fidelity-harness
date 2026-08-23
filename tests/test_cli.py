"""
CLI-level smoke tests, run the same way a stranger would: as a subprocess
against the `superdocs-fidelity` executable, not by importing internals.
This is the test that proves "clone to working in minutes" for the
`validate` subcommand, which needs no API key.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.fixtures import build_fixtures as fx

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "superdocs-fidelity"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_validate_pass_exit_code(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    edited = fx.build_faithful_copy(tmp_path / "e.docx")

    result = _run_cli("validate", str(original), str(edited))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATION STATUS : PASS" in result.stdout


def test_cli_validate_fail_exit_code(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    broken = fx.build_regression_missing_bookmark(tmp_path / "b.docx")

    result = _run_cli("validate", str(original), str(broken))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "VALIDATION STATUS : FAIL" in result.stdout
    assert "intro_ref" in result.stdout


def test_cli_validate_writes_json_report(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    edited = fx.build_faithful_copy(tmp_path / "e.docx")
    json_path = tmp_path / "report.json"

    result = _run_cli("validate", str(original), str(edited), "--json-report", str(json_path))

    assert result.returncode == 0
    assert json_path.exists()
    assert '"validation_status": "PASS"' in json_path.read_text()


def test_cli_run_without_api_key_fails_cleanly(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    env_clean_result = subprocess.run(
        [sys.executable, str(CLI), "run", str(original), "--instruction", "test", "--cost-cap", "1"],
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin"},  # deliberately no SUPERDOCS_API_KEY
    )
    assert env_clean_result.returncode == 2
    assert "SUPERDOCS_API_KEY" in env_clean_result.stderr
