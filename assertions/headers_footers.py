"""
Header and footer structural assertions.

Validates existence and structure: that headers/footers are still real
word/header{N}.xml and word/footer{N}.xml parts wired to a <w:sectPr> via
<w:headerReference>/<w:footerReference> relationship ids that actually
resolve in word/_rels/document.xml.rels -- not flattened into the top/bottom
of the body text.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, RELATIONSHIP_TYPE_HEADER, RELATIONSHIP_TYPE_FOOTER
from .base import AssertionResult, pass_, fail

NAME = "Headers & Footers"


def _resolved_parts(pkg: DocxPackage, kind: str) -> set[str]:
    """r:ids referenced by sectPr headerReference/footerReference elements
    that actually resolve to a real part via the relationships file."""
    ref_ids = pkg.header_footer_reference_ids()[kind]
    rels = pkg.document_relationships()
    resolved = set()
    for rid in ref_ids:
        rel = rels.get(rid)
        if rel and rel["target"]:
            resolved.add(rel["target"])
    return resolved


def _check_kind(pkg_name: str, original: DocxPackage, edited: DocxPackage, kind: str, rel_type: str) -> list[AssertionResult]:
    results = []
    label = kind.capitalize()

    orig_parts = original.find_header_footer_parts()[kind]
    edited_parts = edited.find_header_footer_parts()[kind]

    if not orig_parts:
        results.append(pass_(NAME, "Document", f"{label} count", expected="0 (none in original)", detail="0"))
        return results

    # Existence
    if edited_parts:
        results.append(pass_(NAME, "Document", f"{label} part(s) present", expected="present"))
    else:
        results.append(
            fail(NAME, "Document", f"{label} part(s) present",
                 expected=f"{len(orig_parts)} {kind} part(s) present",
                 actual="none found",
                 detail=f"Original document had {kind}s; none found in edited export.")
        )
        return results

    # Count (edited may legitimately have >= original if sections were added)
    if len(edited_parts) >= len(orig_parts):
        results.append(pass_(NAME, "Document", f"{label} count", expected=f">= {len(orig_parts)}", detail=str(len(edited_parts))))
    else:
        results.append(
            fail(NAME, "Document", f"{label} count",
                 expected=f">= {len(orig_parts)}", actual=str(len(edited_parts)),
                 detail=f"Original had {len(orig_parts)} {kind} part(s); edited has fewer.")
        )

    # Structural wiring: every sectPr headerReference/footerReference must resolve
    orig_resolved = _resolved_parts(original, kind)
    edited_resolved = _resolved_parts(edited, kind)

    if orig_resolved and not edited_resolved:
        results.append(
            fail(NAME, "Document", f"{label} reference wiring",
                 expected=f"<w:sectPr> {kind}Reference resolves to a real part",
                 actual="no sectPr in the edited document resolves a valid " + kind + "Reference",
                 detail=f"{label} XML parts exist but are no longer referenced by any section -- "
                        "effectively orphaned and won't display in Word.")
        )
    elif orig_resolved:
        results.append(
            pass_(NAME, "Document", f"{label} reference wiring",
                  expected="sectPr reference resolves to a real part", detail=str(len(edited_resolved)))
        )

    return results


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results = []
    results += _check_kind(NAME, original, edited, "header", RELATIONSHIP_TYPE_HEADER)
    results += _check_kind(NAME, original, edited, "footer", RELATIONSHIP_TYPE_FOOTER)
    return results
