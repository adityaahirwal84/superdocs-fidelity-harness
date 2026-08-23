"""
Registry of structural assertion modules.

Every module here exposes a single `run(original: DocxPackage, edited:
DocxPackage) -> list[AssertionResult]` function. The engine discovers and
runs each one; adding a new structural check means adding a new module and
one line to ALL_MODULES, never touching the engine itself.
"""

from . import (
    footnotes,
    headers_footers,
    page_fields,
    tracked_changes,
    comments,
    equations,
    bookmarks,
    cross_references,
    section_geometry,
)
from .base import AssertionResult, AssertionModule, Status

ALL_MODULES = [
    footnotes,
    headers_footers,
    page_fields,
    tracked_changes,
    comments,
    equations,
    bookmarks,
    cross_references,
    section_geometry,
]

__all__ = ["ALL_MODULES", "AssertionResult", "AssertionModule", "Status"]
