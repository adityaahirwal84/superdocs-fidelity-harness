"""
Tracked-changes (revision) structural assertions.

Validates that revision entries in the edited document -- <w:ins>, <w:del>,
<w:pPrChange>, <w:rPrChange>, and their table equivalents -- are well-formed:
every revision must carry w:id, w:author, and w:date, and those values must
be non-empty. This does not assert revision *counts* stay identical between
original and edited (the whole point of a review workflow is that the edit
introduces new revisions) -- it asserts that whatever revisions exist in
the edited document carry real, usable metadata, and that revisions present
in the ORIGINAL document (prior editorial history) are not silently dropped.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Tracked Changes"

REVISION_TAGS = ("ins", "del", "pPrChange", "rPrChange", "tblPrChange", "trPrChange", "tcPrChange")


def _collect_revisions(pkg: DocxPackage) -> list[dict]:
    doc = pkg.document_xml
    revisions = []
    for tag in REVISION_TAGS:
        for el in doc.iter(f"{{{W}}}{tag}"):
            revisions.append(
                {
                    "tag": tag,
                    "id": el.get(f"{{{W}}}id"),
                    "author": el.get(f"{{{W}}}author"),
                    "date": el.get(f"{{{W}}}date"),
                }
            )
    return revisions


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_revisions = _collect_revisions(original)
    edited_revisions = _collect_revisions(edited)

    if not orig_revisions and not edited_revisions:
        results.append(pass_(NAME, "Document", "Revision entries", expected="0 (none in original)", detail="0"))
        return results

    # Prior editorial history must not be silently dropped.
    if orig_revisions and not edited_revisions:
        results.append(
            fail(NAME, "Document", "Revision entries",
                 expected=f"{len(orig_revisions)} revision(s) preserved or superseded by new ones",
                 actual="0 revisions found in edited export",
                 detail="Tracked changes present in the original document are gone after export -- "
                        "either silently accepted/rejected or stripped.")
        )
        return results

    # Every revision (from either document) with metadata gaps is a FAIL.
    checked_any = False
    for source_label, revisions in (("Original", orig_revisions), ("Edited", edited_revisions)):
        for rev in revisions:
            checked_any = True
            element_label = f"<w:{rev['tag']}> id={rev['id']}"
            missing = [f for f in ("id", "author", "date") if not rev.get(f)]
            if missing:
                results.append(
                    fail(NAME, f"Document ({source_label})", element_label,
                         expected="w:id, w:author, and w:date all present",
                         actual=f"missing: {', '.join(missing)}",
                         detail="A revision without complete metadata can't be attributed or audited.")
                )
            else:
                results.append(
                    pass_(NAME, f"Document ({source_label})", element_label,
                          expected="w:id, w:author, w:date present",
                          detail=f"author={rev['author']!r} date={rev['date']!r}")
                )

    # Summary by author, useful for the report even when everything passes.
    if edited_revisions:
        authors = sorted({r["author"] for r in edited_revisions if r.get("author")})
        results.append(
            pass_(NAME, "Document", "Revision authors present in edited export",
                  expected=">= 1 named author", detail=", ".join(authors) if authors else "none")
        )

    return results
