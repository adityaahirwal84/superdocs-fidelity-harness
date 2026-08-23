"""
Builds minimal, hand-authored .docx fixtures directly at the OpenXML level --
real word/document.xml, word/footnotes.xml, word/comments.xml,
word/header1.xml, word/footer1.xml, and a real word/_rels/document.xml.rels
wiring them together. No Microsoft Word and no python-docx abstraction is
needed or used: this is exactly the kind of "real file structure" the
harness itself is meant to validate, so the test fixtures are held to the
same standard.

Every fixture below is a genuinely openable, genuinely valid (if minimal)
.docx file: a real ZIP/OPC package with [Content_Types].xml, _rels/.rels,
and every part it declares actually present.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  <Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>
"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults/>
</w:styles>
"""

SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>
"""

HEADER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>Fidelity Harness Sample Document</w:t></w:r></w:p>
</w:hdr>
"""

FOOTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:r><w:t xml:space="preserve">Page </w:t></w:r>
    <w:fldSimple w:instr="PAGE \\* MERGEFORMAT"><w:r><w:t>1</w:t></w:r></w:fldSimple>
    <w:r><w:t xml:space="preserve"> of </w:t></w:r>
    <w:fldSimple w:instr="NUMPAGES \\* MERGEFORMAT"><w:r><w:t>1</w:t></w:r></w:fldSimple>
  </w:p>
</w:ftr>
"""

FOOTNOTES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>
  <w:footnote w:id="1">
    <w:p><w:r><w:t>This is the body of footnote 1, citing an external source.</w:t></w:r></w:p>
  </w:footnote>
</w:footnotes>
"""

COMMENTS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="1" w:author="Quality Engineer" w:date="2026-08-01T10:00:00Z" w:initials="QE">
    <w:p><w:r><w:t>Please double check this figure before publishing.</w:t></w:r></w:p>
  </w:comment>
</w:comments>
"""

# Main document body. Contains, deliberately, one of every structural
# element the assignment asks the harness to validate:
#   - a bookmark ("intro_ref") wrapping a run
#   - a footnote reference to footnote id=1
#   - a comment range + reference to comment id=1
#   - a tracked-change insertion (w:ins) with id/author/date
#   - a native equation (m:oMath)
#   - a REF field targeting the "intro_ref" bookmark (cross-reference)
#   - a sectPr with explicit pgSz + pgMar (section geometry) and
#     headerReference/footerReference wired to rId5/rId6
DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    <w:p>
      <w:bookmarkStart w:id="0" w:name="intro_ref"/>
      <w:r><w:t>Introduction</w:t></w:r>
      <w:bookmarkEnd w:id="0"/>
    </w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">See the </w:t></w:r>
      <w:fldSimple w:instr="REF intro_ref \\h"><w:r><w:t>Introduction</w:t></w:r></w:fldSimple>
      <w:r><w:t xml:space="preserve"> section for context.</w:t></w:r>
      <w:r><w:t>This claim needs a citation.</w:t></w:r>
      <w:r><w:footnoteReference w:id="1"/></w:r>
    </w:p>
    <w:p>
      <w:commentRangeStart w:id="1"/>
      <w:r><w:t>Revenue grew twelve percent year over year.</w:t></w:r>
      <w:commentRangeEnd w:id="1"/>
      <w:r><w:commentReference w:id="1"/></w:r>
    </w:p>
    <w:p>
      <w:ins w:id="10" w:author="AI Editor" w:date="2026-08-01T11:00:00Z">
        <w:r><w:t>This sentence was added during review.</w:t></w:r>
      </w:ins>
    </w:p>
    <w:p>
      <m:oMathPara>
        <m:oMath>
          <m:r><w:rPr/><m:t>x=(-b\u00b1sqrt(b^2-4ac))/(2a)</m:t></m:r>
        </m:oMath>
      </m:oMathPara>
    </w:p>
    <w:sectPr>
      <w:headerReference w:type="default" r:id="rId5"/>
      <w:footerReference w:type="default" r:id="rId6"/>
      <w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def _write_docx(path: Path, parts: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content)


def base_parts(document_xml: str = DOCUMENT_XML) -> dict[str, str]:
    return {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": ROOT_RELS,
        "word/_rels/document.xml.rels": DOCUMENT_RELS,
        "word/document.xml": document_xml,
        "word/styles.xml": STYLES_XML,
        "word/settings.xml": SETTINGS_XML,
        "word/footnotes.xml": FOOTNOTES_XML,
        "word/comments.xml": COMMENTS_XML,
        "word/header1.xml": HEADER_XML,
        "word/footer1.xml": FOOTER_XML,
    }


def build_original(path: str | Path) -> Path:
    """A well-formed docx containing one of every structural element the
    harness checks. Used as the 'original' side of every test."""
    path = Path(path)
    _write_docx(path, base_parts())
    return path


def build_faithful_copy(path: str | Path) -> Path:
    """An 'edited' document that changed body text but preserved every
    structural element -- the harness should report PASS across the board."""
    edited_document_xml = DOCUMENT_XML.replace(
        "Revenue grew twelve percent year over year.",
        "Revenue grew twelve percent year over year, driven by the EMEA region.",
    )
    path = Path(path)
    _write_docx(path, base_parts(edited_document_xml))
    return path


# -- deliberately broken fixtures, one per regression scenario ---------------

def build_regression_missing_bookmark(path: str | Path) -> Path:
    """Removes the 'intro_ref' bookmark but leaves the REF field pointing at
    it -- this should FAIL both the Bookmarks and Cross-References assertions."""
    broken = DOCUMENT_XML.replace(
        '<w:bookmarkStart w:id="0" w:name="intro_ref"/>', ""
    ).replace(
        '<w:bookmarkEnd w:id="0"/>', ""
    )
    path = Path(path)
    parts = base_parts(broken)
    _write_docx(path, parts)
    return path


def build_regression_missing_footer(path: str | Path) -> Path:
    """Drops the footer part entirely (and its sectPr reference) -- this
    should FAIL the Headers & Footers assertion and the Page Number Fields
    assertion (the PAGE field lived only in the footer)."""
    broken_document = DOCUMENT_XML.replace(
        '<w:footerReference w:type="default" r:id="rId6"/>', ""
    )
    path = Path(path)
    parts = base_parts(broken_document)
    del parts["word/footer1.xml"]
    parts["[Content_Types].xml"] = CONTENT_TYPES.replace(
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>',
        "",
    )
    parts["word/_rels/document.xml.rels"] = DOCUMENT_RELS.replace(
        '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>',
        "",
    )
    _write_docx(path, parts)
    return path


def build_regression_equation_to_image(path: str | Path) -> Path:
    """Replaces the native <m:oMath> equation with a <w:drawing> image
    placeholder -- this should FAIL the Equations assertion."""
    image_stub = (
        '<w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<wp:extent cx="100000" cy="50000"/></wp:inline></w:drawing></w:r>'
    )
    start = DOCUMENT_XML.index("<m:oMathPara>")
    end = DOCUMENT_XML.index("</m:oMathPara>") + len("</m:oMathPara>")
    broken = DOCUMENT_XML[:start] + image_stub + DOCUMENT_XML[end:]
    path = Path(path)
    _write_docx(path, base_parts(broken))
    return path


def build_regression_dropped_comment(path: str | Path) -> Path:
    """Removes the comment body from comments.xml but leaves the in-text
    commentReference dangling -- should FAIL the Comments assertion."""
    path = Path(path)
    parts = base_parts()
    parts["word/comments.xml"] = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>
"""
    _write_docx(path, parts)
    return path


def build_regression_orphaned_footnote_reference(path: str | Path) -> Path:
    """Removes footnote id=1's body but leaves the <w:footnoteReference>
    in the text -- should FAIL the Footnotes assertion (dangling reference)."""
    path = Path(path)
    parts = base_parts()
    parts["word/footnotes.xml"] = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>
</w:footnotes>
"""
    _write_docx(path, parts)
    return path


def build_regression_section_geometry_changed(path: str | Path) -> Path:
    """Flips the page from portrait Letter to landscape A4-ish dimensions --
    should FAIL the Section Geometry assertion."""
    broken = DOCUMENT_XML.replace(
        '<w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/>',
        '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>',
    ).replace(
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>',
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>',
    )
    path = Path(path)
    _write_docx(path, base_parts(broken))
    return path


def build_not_a_docx(path: str | Path) -> Path:
    """A file with a .docx extension that isn't a valid OPC package at all --
    exercises the harness's package-open error path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("this is not a zip file")
    return path
