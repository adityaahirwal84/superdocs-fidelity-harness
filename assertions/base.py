"""Shared types for every structural assertion module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class AssertionResult:
    """
    One structural assertion outcome.

    Every field here maps directly onto the failure-reporting shape the
    assignment specifies: assertion name, document section, structural
    element, expected value, actual value, PASS/FAIL.
    """

    assertion_name: str
    section: str          # e.g. "Section 1", "Document", "Header 2"
    element: str           # e.g. "Bookmark 'intro_ref'", "Footnote id=3"
    expected: str
    actual: str
    status: Status
    detail: str = ""       # optional extra context, never required to understand the row

    def to_dict(self) -> dict:
        return {
            "assertion_name": self.assertion_name,
            "section": self.section,
            "element": self.element,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status.value,
            "detail": self.detail,
        }

    def to_report_block(self) -> str:
        return (
            f"{self.section}\n"
            f"{self.element}\n\n"
            f"Expected:\n{self.expected}\n\n"
            f"Actual:\n{self.actual}\n\n"
            f"Status:\n{self.status.value}"
        )


def pass_(assertion_name: str, section: str, element: str, expected: str, detail: str = "") -> AssertionResult:
    return AssertionResult(assertion_name, section, element, expected, expected, Status.PASS, detail)


def fail(assertion_name: str, section: str, element: str, expected: str, actual: str, detail: str = "") -> AssertionResult:
    return AssertionResult(assertion_name, section, element, expected, actual, Status.FAIL, detail)


@dataclass
class AssertionModule:
    """A named group of assertion results produced by one assertions/*.py module."""

    name: str
    results: list = field(default_factory=list)
