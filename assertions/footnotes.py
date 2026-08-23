"""
Footnote structural assertions.

Validates existence, count, ids, and references -- i.e. that footnotes
in the edited document are still real <w:footnote> parts wired up through
<w:footnoteReference> elements in the body, not flattened into inline text
or bracketed superscript numbers.

SuperDocs' own marketing claims footnotes "survive editing and export as
real Word document parts: numbered, anchored, and visible in Word's review
pane, never flattened into body text" -- this module is exactly the check
that claim should have to survive.
"""

from __future__ import annotations

from lxml import etree

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Footnotes"

# Word reserves footnote ids -1 (separator) and 0 (continuation separator).
RESERVED_IDS = {"-1", "0"}


def _real_footnote_ids(pkg: DocxPackage) -> set[str]:
    tree = pkg.read_part_xml("word/footnotes.xml")
    if tree is None:
        return set()
    ids = set()
    for fn in tree.iter(f"{{{W}}}footnote"):
        fid = fn.get(f"{{{W}}}id")
        if fid and fid not in RESERVED_IDS:
            ids.add(fid)
    return ids


def _referenced_footnote_ids(pkg: DocxPackage) -> set[str]:
    doc = pkg.document_xml
    ids = set()
    for ref in doc.iter(f"{{{W}}}footnoteReference"):
        fid = ref.get(f"{{{W}}}id")
        if fid:
            ids.add(fid)
    return ids


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_ids = _real_footnote_ids(original)
    edited_ids = _real_footnote_ids(edited)
    orig_refs = _referenced_footnote_ids(original)
    edited_refs = _referenced_footnote_ids(edited)

    # 1. Existence: if the original had footnotes, the part must still exist.
    if orig_ids:
        if edited.has_part("word/footnotes.xml") and edited_ids:
            results.append(pass_(NAME, "Document", "word/footnotes.xml part", "present"))
        else:
            results.append(
                fail(
                    NAME, "Document", "word/footnotes.xml part",
                    expected=f"present with {len(orig_ids)} footnote(s)",
                    actual="missing or empty",
                    detail="Original document had native footnotes; edited export has none.",
                )
            )
            return results  # nothing further to check meaningfully

    # 2. Count.
    if orig_ids:
        expected_count = str(len(orig_ids))
        actual_count = str(len(edited_ids))
        if len(edited_ids) >= len(orig_ids):
            results.append(pass_(NAME, "Document", "Footnote count", expected_count, detail=actual_count))
        else:
            results.append(
                fail(NAME, "Document", "Footnote count", expected_count, actual_count,
                     detail="Fewer real footnotes after export than before edit.")
            )

    # 3. IDs preserved (original ids still present as real footnotes, not necessarily
    #    unchanged numbering -- Word renumbers ids on edit -- but every ORIGINAL
    #    footnote body's presence should survive as *some* footnote entry, and every
    #    footnote in the edited doc must have a matching reference).
    missing_ids = orig_ids - edited_ids
    for fid in sorted(missing_ids, key=lambda x: int(x) if x.lstrip("-").isdigit() else 0):
        results.append(
            fail(NAME, "Document", f"Footnote id={fid}",
                 expected="present in word/footnotes.xml", actual="missing",
                 detail="This footnote body existed in the original and cannot be found after export.")
        )

    # 4. References: every real footnote id in the edited doc must have a
    #    corresponding <w:footnoteReference> in the body (an orphaned body with
    #    no anchor is not a working footnote), and vice versa.
    orphan_bodies = edited_ids - edited_refs
    for fid in sorted(orphan_bodies, key=lambda x: int(x) if x.lstrip("-").isdigit() else 0):
        results.append(
            fail(NAME, "Document", f"Footnote id={fid} reference",
                 expected="anchored by a <w:footnoteReference> in the body",
                 actual="footnote body exists but no in-text reference points to it",
                 detail="An orphaned footnote body is not visible/clickable in Word.")
        )

    dangling_refs = edited_refs - edited_ids
    for fid in sorted(dangling_refs, key=lambda x: int(x) if x.lstrip("-").isdigit() else 0):
        results.append(
            fail(NAME, "Document", f"Footnote id={fid} reference",
                 expected="matching <w:footnote> body in word/footnotes.xml",
                 actual="in-text reference exists but no footnote body found",
                 detail="A dangling reference shows as a broken footnote mark in Word.")
        )

    if not orig_ids:
        # Original had no footnotes -- nothing to regress, but still report that
        # we checked, so "0 footnotes" reads as an intentional PASS, not silence.
        results.append(pass_(NAME, "Document", "Footnote count", expected="0 (none in original)", detail="0"))

    return results
