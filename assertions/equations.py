"""
Equation structural assertions.

Validates that native Word equations (OMML: <m:oMath> / <m:oMathPara>)
remain native mathematics after export, rather than being silently rasterized
into an inline image (<w:drawing> containing a <pic:pic>). A native equation
stays editable in Word's equation editor; a converted image does not.

We can't always PROVE a specific image *is* a converted equation (images can
legitimately be photos, screenshots, diagrams), but we can reliably detect
the harmful pattern: the count of native oMath objects dropped between
original and edited while the count of inline images rose by roughly the
same amount. That is flagged as a likely conversion for a human to confirm.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
M = NAMESPACES["m"]
NAME = "Equations"


def _oMath_count(pkg: DocxPackage) -> int:
    doc = pkg.document_xml
    # Count top-level oMath / oMathPara only (oMath nested inside oMathPara
    # would double count otherwise).
    para_count = len(list(doc.iter(f"{{{M}}}oMathPara")))
    standalone = 0
    for el in doc.iter(f"{{{M}}}oMath"):
        parent = el.getparent()
        if parent is None or parent.tag != f"{{{M}}}oMathPara":
            standalone += 1
    return para_count + standalone


def _inline_image_count(pkg: DocxPackage) -> int:
    doc = pkg.document_xml
    return len(list(doc.iter(f"{{{W}}}drawing")))


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_math = _oMath_count(original)
    if orig_math == 0:
        results.append(pass_(NAME, "Document", "Native equation (oMath) count", expected="0 (none in original)", detail="0"))
        return results

    edited_math = _oMath_count(edited)
    orig_images = _inline_image_count(original)
    edited_images = _inline_image_count(edited)

    if edited_math >= orig_math:
        results.append(
            pass_(NAME, "Document", "Native equation (oMath) count",
                  expected=f">= {orig_math}", detail=str(edited_math))
        )
    else:
        lost = orig_math - edited_math
        image_delta = edited_images - orig_images
        likely_converted = image_delta >= lost > 0
        detail = (
            f"{lost} native equation(s) missing after export. "
            f"Inline image count changed by {image_delta:+d} in the same document, "
            + ("which matches the pattern of equations being rasterized into pictures."
               if likely_converted else
               "which does not obviously match an equation-to-image conversion -- "
               "investigate directly.")
        )
        results.append(
            fail(NAME, "Document", "Native equation (oMath) count",
                 expected=f">= {orig_math}", actual=str(edited_math), detail=detail)
        )

    return results
