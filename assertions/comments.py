"""
Comment structural assertions.

Validates existence, author, timestamp, and content association: that
comments are still real word/comments.xml entries anchored in the body via
matching <w:commentRangeStart>/<w:commentRangeEnd>/<w:commentReference>
elements, each with a real author and date, rather than being dropped or
flattened into inline bracketed text.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Comments"


def _comment_entries(pkg: DocxPackage) -> dict[str, dict]:
    tree = pkg.read_part_xml("word/comments.xml")
    if tree is None:
        return {}
    out = {}
    for c in tree.iter(f"{{{W}}}comment"):
        cid = c.get(f"{{{W}}}id")
        if cid is None:
            continue
        text = "".join(t.text or "" for t in c.iter(f"{{{W}}}t"))
        out[cid] = {
            "author": c.get(f"{{{W}}}author"),
            "date": c.get(f"{{{W}}}date"),
            "text": text,
        }
    return out


def _referenced_comment_ids(pkg: DocxPackage) -> set[str]:
    doc = pkg.document_xml
    ids = set()
    for el in doc.iter(f"{{{W}}}commentReference"):
        cid = el.get(f"{{{W}}}id")
        if cid:
            ids.add(cid)
    return ids


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_comments = _comment_entries(original)
    if not orig_comments:
        results.append(pass_(NAME, "Document", "Comment count", expected="0 (none in original)", detail="0"))
        return results

    edited_comments = _comment_entries(edited)
    edited_refs = _referenced_comment_ids(edited)

    # Existence + count
    if edited_comments:
        results.append(pass_(NAME, "Document", "word/comments.xml part", expected="present"))
    else:
        results.append(
            fail(NAME, "Document", "word/comments.xml part",
                 expected=f"present with {len(orig_comments)} comment(s)", actual="missing or empty")
        )
        return results

    if len(edited_comments) >= len(orig_comments):
        results.append(pass_(NAME, "Document", "Comment count", expected=f">= {len(orig_comments)}", detail=str(len(edited_comments))))
    else:
        results.append(
            fail(NAME, "Document", "Comment count",
                 expected=f">= {len(orig_comments)}", actual=str(len(edited_comments)),
                 detail="Fewer comments after export than before edit.")
        )

    # Per-comment metadata + anchoring
    for cid, c in edited_comments.items():
        element = f"Comment id={cid}"
        missing = [f for f in ("author", "date") if not c.get(f)]
        if missing:
            results.append(
                fail(NAME, "Document", element,
                     expected="author and date present",
                     actual=f"missing: {', '.join(missing)}")
            )
        else:
            results.append(pass_(NAME, "Document", element, expected="author and date present",
                                  detail=f"author={c['author']!r} date={c['date']!r}"))

        if cid in edited_refs:
            results.append(pass_(NAME, "Document", f"{element} anchor", expected="anchored via <w:commentReference>"))
        else:
            results.append(
                fail(NAME, "Document", f"{element} anchor",
                     expected="anchored via <w:commentReference> in the body",
                     actual="comment body exists but no in-text reference points to it",
                     detail="An orphaned comment won't show a highlight/balloon in Word.")
            )

    # Comments that existed originally must still exist (by content association --
    # a comment surviving under a different internal id is fine; losing the text
    # entirely is not).
    orig_texts = {c["text"].strip() for c in orig_comments.values() if c["text"].strip()}
    edited_texts = {c["text"].strip() for c in edited_comments.values() if c["text"].strip()}
    missing_texts = orig_texts - edited_texts
    for text in sorted(missing_texts):
        snippet = (text[:60] + "...") if len(text) > 60 else text
        results.append(
            fail(NAME, "Document", f"Original comment text {snippet!r}",
                 expected="comment content preserved somewhere in edited export",
                 actual="no matching comment text found")
        )

    return results
