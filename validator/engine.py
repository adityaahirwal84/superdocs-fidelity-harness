"""
Validation engine: runs every registered structural assertion module against
an (original, edited) docx pair and produces a ValidationReport.

Nothing here is document-specific. It works for any two .docx files handed
to it -- there is no hardcoded filename, template assumption, or document
structure baked in, per the assignment's "a stranger should be able to run
the validator against their own document without modification."
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from assertions import ALL_MODULES, AssertionResult, Status
from .docx_package import DocxPackage, DocxStructuralError


@dataclass
class ValidationRun:
    original_path: str
    edited_path: str
    results: list[AssertionResult]
    execution_time_seconds: float
    package_error: str | None = None  # set if a file couldn't even be opened as a docx

    @property
    def passed(self) -> list[AssertionResult]:
        return [r for r in self.results if r.status == Status.PASS]

    @property
    def failed(self) -> list[AssertionResult]:
        return [r for r in self.results if r.status == Status.FAIL]

    @property
    def overall_status(self) -> Status:
        if self.package_error:
            return Status.FAIL
        return Status.FAIL if self.failed else Status.PASS


class ValidationEngine:
    """Runs the full structural assertion suite against a document pair."""

    def __init__(self, modules=None):
        self.modules = modules if modules is not None else ALL_MODULES

    def run(self, original_path: str, edited_path: str) -> ValidationRun:
        start = time.monotonic()
        try:
            with DocxPackage.open(original_path) as original, DocxPackage.open(edited_path) as edited:
                results: list[AssertionResult] = []
                for module in self.modules:
                    results.extend(module.run(original, edited))
                elapsed = time.monotonic() - start
                return ValidationRun(
                    original_path=str(original_path),
                    edited_path=str(edited_path),
                    results=results,
                    execution_time_seconds=elapsed,
                )
        except DocxStructuralError as exc:
            elapsed = time.monotonic() - start
            return ValidationRun(
                original_path=str(original_path),
                edited_path=str(edited_path),
                results=[],
                execution_time_seconds=elapsed,
                package_error=str(exc),
            )
