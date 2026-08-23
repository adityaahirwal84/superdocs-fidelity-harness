"""
Page number field assertions.

Validates that page-number field codes (PAGE, NUMPAGES, SECTIONPAGES) survive
editing as real Word fields -- either the simple <w:fldSimple w:instr="PAGE ...">
form or the complex begin/instrText/end run sequence -- rather than being
replaced with a static, edit-frozen number typed as plain text.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Page Number Fields"

PAGE_FIELD_KEYWORDS = ("PAGE", "NUMPAGES", "SECTIONPAGES")


def _field_instructions(pkg: DocxPackage) -> list[str]:
    """Collect every field instruction string found in the document, across
    document.xml AND every header/footer part (page fields almost always
    live in headers/footers, but can legally appear in the body too)."""
    instructions: list[str] = []

    def collect_from(tree) -> None:
        if tree is None:
            return
        # Simple fields
        for el in tree.iter(f"{{{W}}}fldSimple"):
            instr = el.get(f"{{{W}}}instr")
            if instr:
                instructions.append(instr.strip())
        # Complex fields: instruction text lives in <w:instrText> runs
        for el in tree.iter(f"{{{W}}}instrText"):
            if el.text:
                instructions.append(el.text.strip())

    collect_from(pkg.document_xml)
    parts = pkg.find_header_footer_parts()
    for part_name in parts["header"] + parts["footer"]:
        collect_from(pkg.read_part_xml(part_name))

    return instructions


def _is_page_field(instr: str) -> bool:
    upper = instr.upper()
    return any(kw in upper for kw in PAGE_FIELD_KEYWORDS)


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_instructions = _field_instructions(original)
    orig_page_fields = [i for i in orig_instructions if _is_page_field(i)]

    if not orig_page_fields:
        results.append(pass_(NAME, "Document", "Page number field(s)", expected="0 (none in original)", detail="0"))
        return results

    edited_instructions = _field_instructions(edited)
    edited_page_fields = [i for i in edited_instructions if _is_page_field(i)]

    if edited_page_fields:
        results.append(
            pass_(NAME, "Document", "Page number field code present",
                  expected=f">= 1 field containing {PAGE_FIELD_KEYWORDS}",
                  detail=f"{len(edited_page_fields)} found")
        )
    else:
        results.append(
            fail(NAME, "Document", "Page number field code present",
                 expected=f"field code present, e.g. {orig_page_fields[0]!r}",
                 actual="no PAGE/NUMPAGES/SECTIONPAGES field instruction found anywhere in the document",
                 detail="Page numbering was likely flattened into static text, which will no longer "
                        "update as pages are added or removed in Word.")
        )
        return results

    if len(edited_page_fields) >= len(orig_page_fields):
        results.append(
            pass_(NAME, "Document", "Page number field count",
                  expected=f">= {len(orig_page_fields)}", detail=str(len(edited_page_fields)))
        )
    else:
        results.append(
            fail(NAME, "Document", "Page number field count",
                 expected=f">= {len(orig_page_fields)}", actual=str(len(edited_page_fields)),
                 detail="Fewer page-numbering fields survived than were present originally.")
        )

    return results
