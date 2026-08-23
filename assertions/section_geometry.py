"""
Section geometry structural assertions.

Validates margins, orientation, paper size, and other <w:sectPr> page-setup
properties per section, comparing each section's geometry between the
original and edited document by position. A document with three sections
(e.g. cover page portrait, body portrait, appendix landscape) must still
have three sections with matching geometry after a round trip -- silently
collapsing sections or normalizing page size/orientation is exactly the
kind of change that looks fine in a text diff and wrong on a printed page.
"""

from __future__ import annotations

from validator.docx_package import DocxPackage, NAMESPACES
from .base import AssertionResult, pass_, fail

W = NAMESPACES["w"]
NAME = "Section Geometry"


def _pg_sz(sect_pr) -> dict:
    el = sect_pr.find(f"{{{W}}}pgSz")
    if el is None:
        return {}
    return {
        "w": el.get(f"{{{W}}}w"),
        "h": el.get(f"{{{W}}}h"),
        "orient": el.get(f"{{{W}}}orient") or "portrait",  # portrait is the implicit default
    }


def _pg_mar(sect_pr) -> dict:
    el = sect_pr.find(f"{{{W}}}pgMar")
    if el is None:
        return {}
    keys = ("top", "right", "bottom", "left", "header", "footer", "gutter")
    return {k: el.get(f"{{{W}}}{k}") for k in keys}


def _section_geometries(pkg: DocxPackage) -> list[dict]:
    return [
        {"page_size": _pg_sz(sect_pr), "margins": _pg_mar(sect_pr)}
        for sect_pr in pkg.section_properties()
    ]


def run(original: DocxPackage, edited: DocxPackage) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    orig_sections = _section_geometries(original)
    edited_sections = _section_geometries(edited)

    if not orig_sections:
        results.append(fail(NAME, "Document", "Section count",
                             expected=">= 1 (every valid docx has at least one sectPr)",
                             actual="0", detail="Original document has no <w:sectPr> at all -- unusual and worth investigating."))
        return results

    # Section count
    if len(edited_sections) == len(orig_sections):
        results.append(pass_(NAME, "Document", "Section count", expected=str(len(orig_sections)), detail=str(len(edited_sections))))
    else:
        results.append(
            fail(NAME, "Document", "Section count",
                 expected=str(len(orig_sections)), actual=str(len(edited_sections)),
                 detail="Sections were merged or split during editing -- page geometry may no longer "
                        "apply to the content the author intended.")
        )

    # Per-section geometry, compared positionally up to the shorter length.
    for idx in range(min(len(orig_sections), len(edited_sections))):
        section_label = f"Section {idx + 1}"
        orig_geo = orig_sections[idx]
        edited_geo = edited_sections[idx]

        orig_sz, edited_sz = orig_geo["page_size"], edited_geo["page_size"]
        if orig_sz:
            if edited_sz == orig_sz:
                results.append(pass_(NAME, section_label, "Page size & orientation",
                                      expected=f"{orig_sz['w']}x{orig_sz['h']} {orig_sz['orient']}"))
            else:
                results.append(
                    fail(NAME, section_label, "Page size & orientation",
                         expected=f"{orig_sz['w']}x{orig_sz['h']} {orig_sz['orient']}",
                         actual=(f"{edited_sz['w']}x{edited_sz['h']} {edited_sz['orient']}" if edited_sz else "missing <w:pgSz>"))
                )

        orig_mar, edited_mar = orig_geo["margins"], edited_geo["margins"]
        if orig_mar:
            if edited_mar == orig_mar:
                results.append(pass_(NAME, section_label, "Margins",
                                      expected=", ".join(f"{k}={v}" for k, v in orig_mar.items())))
            else:
                diffs = {
                    k: (orig_mar.get(k), (edited_mar or {}).get(k))
                    for k in orig_mar
                    if orig_mar.get(k) != (edited_mar or {}).get(k)
                }
                results.append(
                    fail(NAME, section_label, "Margins",
                         expected=", ".join(f"{k}={v}" for k, v in orig_mar.items()),
                         actual=", ".join(f"{k}={v[1]}" for k, v in diffs.items()) if diffs else "missing <w:pgMar>",
                         detail=f"Changed fields: {', '.join(diffs.keys())}" if diffs else "")
                )

    return results
