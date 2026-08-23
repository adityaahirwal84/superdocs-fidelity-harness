"""Unit tests for report generation and formatting."""

from __future__ import annotations

import json
from pathlib import Path

from validator import ValidationEngine
from reporting import build_report
from tests.fixtures import build_fixtures as fx


def test_report_text_and_markdown_contain_failures(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    broken = fx.build_regression_missing_bookmark(tmp_path / "broken.docx")

    engine = ValidationEngine()
    run = engine.run(str(original), str(broken))
    report = build_report(run)

    assert report.overall_status == "FAIL"
    text = report.to_text()
    assert "STRUCTURAL DIFFERENCES" in text
    assert "intro_ref" in text

    md = report.to_markdown()
    assert "## Structural Differences" in md
    assert "intro_ref" in md


def test_report_json_is_valid_and_complete(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    edited = fx.build_faithful_copy(tmp_path / "e.docx")

    engine = ValidationEngine()
    run = engine.run(str(original), str(edited))
    report = build_report(run)

    parsed = json.loads(report.to_json())
    assert parsed["summary"]["validation_status"] == "PASS"
    assert parsed["summary"]["assertions_executed"] == report.total_assertions
    assert parsed["structural_differences"] == []
