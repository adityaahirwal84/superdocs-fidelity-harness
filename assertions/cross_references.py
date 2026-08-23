"""
Internal cross-reference structural assertions.

Validates that internal cross-reference fields (REF and PAGEREF field codes,
the mechanism behind Word's "Insert Cross-reference" for headings, figures,
tables, and bookmarked text) still resolve: the bookmark name each reference
field points at must exist in the same document. A reference whose target
bookmark is gone becomes the literal, silent "Error! Reference source not
found." string the next time the field updates in Word.
"""

from __future__ import annotations

import re

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail
from .bookmarks import _bookmarks

W = NAMESPACES["w"]
NAME = "Internal Cross-References"

REF_FIELD_RE = re.compile(r"\b(?:REF|PAGEREF)\s+(\S+)", re.IGNORECASE)


def _field_instructions(pkg: DocxPackage) -> list[str]:
    doc = pkg.document_xml
    instructions = []
    for el in doc.iter(f"{{{W}}}fldSimple"):
        instr = el.get(f"{{{W}}}instr")
        if instr:
            instructions.append(instr.strip())
    for el in doc.iter(f"{{{W}}}instrText"):
        if el.text:
            instructions.append(el.text.strip())
    return instructions


def _cross_reference_targets(pkg: DocxPackage) -> list[str]:
    targets = []
    for instr in _field_instructions(pkg):
        match = REF_FIELD_RE.search(instr)
        if match:
            targets.append(match.group(1))
    return targets


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_targets = _cross_reference_targets(original)
    if not orig_targets:
        results.append(pass_(NAME, "Document", "Cross-reference field count", expected="0 (none in original)", detail="0"))
        return results

    edited_targets = _cross_reference_targets(edited)
    edited_bookmark_names, _, _ = _bookmarks(edited)
    edited_bookmark_name_set = set(edited_bookmark_names.values())

    if len(edited_targets) >= len(orig_targets):
        results.append(
            pass_(NAME, "Document", "Cross-reference field count",
                  expected=f">= {len(orig_targets)}", detail=str(len(edited_targets)))
        )
    else:
        results.append(
            fail(NAME, "Document", "Cross-reference field count",
                 expected=f">= {len(orig_targets)}", actual=str(len(edited_targets)),
                 detail="Fewer REF/PAGEREF fields after export than before edit.")
        )

    broken = [t for t in edited_targets if t not in edited_bookmark_name_set]
    if broken:
        for target in sorted(set(broken)):
            results.append(
                fail(NAME, "Document", f"Reference target '{target}'",
                     expected="target bookmark exists in the document",
                     actual="no bookmark with this name found",
                     detail="This field will render as 'Error! Reference source not found.' "
                            "the next time fields update in Word.")
            )
    else:
        results.append(
            pass_(NAME, "Document", "Cross-reference target resolution",
                  expected="every REF/PAGEREF target resolves to an existing bookmark")
        )

    return results
