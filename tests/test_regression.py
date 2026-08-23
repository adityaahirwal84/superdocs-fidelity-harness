"""
Regression tests.

Per the assignment: "Include an example regression test. Deliberately break
one structural element. Verify that the validator detects it." This module
does that for every one of the ten assertion categories that has a clean,
mechanical way to break it, plus one for a file that isn't a valid docx at
all.

Each test builds a genuinely broken .docx (see tests/fixtures/build_fixtures.py),
runs the real ValidationEngine against it, and asserts both that the overall
status is FAIL and that the specific assertion category that should have
caught it did.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from validator import ValidationEngine
from assertions import Status
from tests.fixtures import build_fixtures as fx


@pytest.fixture()
def engine() -> ValidationEngine:
    return ValidationEngine()


def _assertion_names(run) -> set[str]:
    return {r.assertion_name for r in run.failed}


def test_faithful_edit_passes_every_assertion(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    edited = fx.build_faithful_copy(tmp_path / "edited.docx")

    run = engine.run(str(original), str(edited))

    assert run.overall_status == Status.PASS, [r.to_dict() for r in run.failed]
    assert run.failed == []
    assert len(run.passed) > 0


def test_regression_missing_bookmark_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_missing_bookmark(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    names = _assertion_names(run)
    assert "Bookmarks" in names
    assert "Internal Cross-References" in names  # the REF field now dangles too
    bookmark_failures = [r for r in run.failed if r.assertion_name == "Bookmarks"]
    assert any("intro_ref" in r.element for r in bookmark_failures)


def test_regression_missing_footer_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_missing_footer(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    names = _assertion_names(run)
    assert "Headers & Footers" in names
    assert "Page Number Fields" in names  # PAGE field lived in the dropped footer


def test_regression_equation_converted_to_image_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_equation_to_image(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    assert "Equations" in _assertion_names(run)


def test_regression_dropped_comment_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_dropped_comment(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    assert "Comments" in _assertion_names(run)


def test_regression_orphaned_footnote_reference_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_orphaned_footnote_reference(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    assert "Footnotes" in _assertion_names(run)


def test_regression_section_geometry_changed_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    broken = fx.build_regression_section_geometry_changed(tmp_path / "broken.docx")

    run = engine.run(str(original), str(broken))

    assert run.overall_status == Status.FAIL
    assert "Section Geometry" in _assertion_names(run)


def test_regression_not_a_docx_is_detected(tmp_path: Path, engine: ValidationEngine):
    original = fx.build_original(tmp_path / "original.docx")
    not_docx = fx.build_not_a_docx(tmp_path / "broken.docx")

    run = engine.run(str(original), str(not_docx))

    assert run.overall_status == Status.FAIL
    assert run.package_error is not None
    assert "not a valid .docx" in run.package_error or "not a readable ZIP" in run.package_error
