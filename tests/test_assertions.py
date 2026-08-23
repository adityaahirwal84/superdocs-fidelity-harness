"""
Unit tests exercising each assertion module directly (not just through the
end-to-end regression scenarios in test_regression.py), including a couple
of edge cases: a document with none of a given element (should PASS with an
explicit "0 in original" result, never silently skip), and well-formed
start/end pairing checks.
"""

from __future__ import annotations

from pathlib import Path

from validator.docx_package import DocxPackage
from assertions import footnotes, bookmarks, comments, section_geometry, Status
from tests.fixtures import build_fixtures as fx


def test_footnotes_pass_on_identical_structure(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    edited = fx.build_faithful_copy(tmp_path / "e.docx")
    with DocxPackage.open(original) as o, DocxPackage.open(edited) as e:
        results = footnotes.run(o, e)
    assert all(r.status == Status.PASS for r in results)
    assert len(results) >= 2  # existence + count at minimum


def test_bookmarks_none_in_original_reports_explicit_zero(tmp_path: Path):
    # Build a document with no bookmarkStart at all by stripping them from the
    # base fixture directly (cheap way to get a "zero elements" case without a
    # whole new fixture function).
    original_path = fx.build_original(tmp_path / "o.docx")
    import zipfile
    data = original_path.read_bytes()
    Path(tmp_path / "stripped.docx").write_bytes(data)

    from tests.fixtures.build_fixtures import DOCUMENT_XML, base_parts
    stripped_doc = (
        DOCUMENT_XML.replace('<w:bookmarkStart w:id="0" w:name="intro_ref"/>', "")
        .replace('<w:bookmarkEnd w:id="0"/>', "")
        .replace('<w:fldSimple w:instr="REF intro_ref \\h"><w:r><w:t>Introduction</w:t></w:r></w:fldSimple>', "")
    )
    with zipfile.ZipFile(tmp_path / "no_bookmarks.docx", "w") as zf:
        for name, content in base_parts(stripped_doc).items():
            zf.writestr(name, content)

    with DocxPackage.open(tmp_path / "no_bookmarks.docx") as o, DocxPackage.open(tmp_path / "no_bookmarks.docx") as e:
        results = bookmarks.run(o, e)

    assert len(results) == 1
    assert results[0].status == Status.PASS
    assert "0" in results[0].expected


def test_comments_detects_missing_author_metadata(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")

    import zipfile
    from tests.fixtures.build_fixtures import base_parts

    parts = base_parts()
    parts["word/comments.xml"] = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="1" w:date="2026-08-01T10:00:00Z">
    <w:p><w:r><w:t>Missing author attribute.</w:t></w:r></w:p>
  </w:comment>
</w:comments>
"""
    bad_path = tmp_path / "bad_comment.docx"
    with zipfile.ZipFile(bad_path, "w") as zf:
        for name, content in parts.items():
            zf.writestr(name, content)

    with DocxPackage.open(original) as o, DocxPackage.open(bad_path) as e:
        results = comments.run(o, e)

    failing = [r for r in results if r.status == Status.FAIL and "author" in r.actual.lower()]
    assert failing, [r.to_dict() for r in results]


def test_section_geometry_pass_when_unchanged(tmp_path: Path):
    original = fx.build_original(tmp_path / "o.docx")
    edited = fx.build_faithful_copy(tmp_path / "e.docx")
    with DocxPackage.open(original) as o, DocxPackage.open(edited) as e:
        results = section_geometry.run(o, e)
    assert all(r.status == Status.PASS for r in results)
    assert any("Margins" in r.element for r in results)
    assert any("Page size" in r.element for r in results)
