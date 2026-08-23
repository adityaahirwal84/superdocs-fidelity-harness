"""
Bookmark structural assertions.

Validates bookmark existence and ids: every <w:bookmarkStart> must have a
matching <w:bookmarkEnd> with the same w:id, and every bookmark name present
in the original document must still resolve to a real bookmark in the
edited export (bookmarks are how cross-references, TOC entries, and hyperlink
targets resolve, so a dropped bookmark quietly breaks all of those).
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Bookmarks"

# Word writes an internal "_GoBack" bookmark automatically; it's not
# user-authored content and is noise for this assertion.
IGNORED_BOOKMARK_NAMES = {"_GoBack"}


def _bookmarks(pkg: DocxPackage) -> tuple[dict[str, str], set[str], set[str]]:
    """Returns (id -> name for starts, set of start ids, set of end ids)."""
    doc = pkg.document_xml
    starts: dict[str, str] = {}
    start_ids: set[str] = set()
    end_ids: set[str] = set()
    for el in doc.iter(f"{{{W}}}bookmarkStart"):
        bid = el.get(f"{{{W}}}id")
        name = el.get(f"{{{W}}}name")
        if bid is not None:
            start_ids.add(bid)
            if name not in IGNORED_BOOKMARK_NAMES:
                starts[bid] = name
    for el in doc.iter(f"{{{W}}}bookmarkEnd"):
        bid = el.get(f"{{{W}}}id")
        if bid is not None:
            end_ids.add(bid)
    return starts, start_ids, end_ids


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_starts, _, _ = _bookmarks(original)
    if not orig_starts:
        results.append(pass_(NAME, "Document", "Bookmark count", expected="0 (none in original)", detail="0"))
        return results

    edited_starts, edited_start_ids, edited_end_ids = _bookmarks(edited)
    orig_names = set(orig_starts.values())
    edited_names = set(edited_starts.values())

    # Existence / count by name (ids can legitimately be renumbered on edit).
    missing_names = orig_names - edited_names
    if not missing_names:
        results.append(
            pass_(NAME, "Document", "Bookmark names preserved",
                  expected=f"all {len(orig_names)} original bookmark name(s) present", detail=str(len(edited_names)))
        )
    else:
        for name in sorted(missing_names):
            results.append(
                fail(NAME, "Document", f"Bookmark '{name}'",
                     expected="bookmark exists", actual="bookmark missing",
                     detail="Any cross-reference or hyperlink targeting this bookmark will now be broken.")
            )

    # Start/end pairing integrity in the edited document.
    unmatched_starts = edited_start_ids - edited_end_ids
    unmatched_ends = edited_end_ids - edited_start_ids
    for bid in sorted(unmatched_starts):
        name = edited_starts.get(bid, "?")
        results.append(
            fail(NAME, "Document", f"Bookmark id={bid} ('{name}')",
                 expected="matching <w:bookmarkEnd> with same id",
                 actual="no matching bookmarkEnd found",
                 detail="An unterminated bookmark is malformed and Word may repair or drop it silently.")
        )
    for bid in sorted(unmatched_ends):
        results.append(
            fail(NAME, "Document", f"Bookmark id={bid}",
                 expected="matching <w:bookmarkStart> with same id",
                 actual="no matching bookmarkStart found",
                 detail="A bookmarkEnd with no start is malformed OOXML.")
        )
    if not unmatched_starts and not unmatched_ends and edited_start_ids:
        results.append(pass_(NAME, "Document", "Bookmark start/end pairing", expected="every start has a matching end"))

    return results
