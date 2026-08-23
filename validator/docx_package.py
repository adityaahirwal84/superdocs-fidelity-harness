"""
Raw OpenXML (.docx) package access.

This module deliberately does NOT use python-docx or any other abstraction
that flattens the package into a text/paragraph model. The assignment is
explicit: inspect the real Microsoft Word DOCX structure, the native OpenXML
package, its XML parts and relationships -- never plain text, never OCR,
never a PDF/screenshot comparison.

A .docx file is a ZIP archive (the OPC -- Open Packaging Conventions). The
parts that matter for this harness:

  word/document.xml          main body: paragraphs, runs, tables, bookmarks,
                              tracked changes, field codes, oMath, images
  word/footnotes.xml         footnote bodies
  word/endnotes.xml          endnote bodies
  word/comments.xml          comment bodies
  word/header{N}.xml         header parts (N = 1, 2, 3, ...)
  word/footer{N}.xml         footer parts
  word/settings.xml          document-wide settings
  word/styles.xml            style definitions
  word/numbering.xml         list numbering definitions
  word/_rels/document.xml.rels   relationships from document.xml to headers/
                              footers/images/etc (this is how a sectPr's
                              r:id for a headerReference resolves to an
                              actual header{N}.xml part)
  [Content_Types].xml        declares the content type of every part

Nothing here hardcodes a filename, a specific document's structure, or a
specific template. Every assertion module works from what it actually finds
in the package, which is what lets the same validator run unmodified against
a stranger's document.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}

RELATIONSHIP_TYPE_HEADER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
)
RELATIONSHIP_TYPE_FOOTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
)


class DocxStructuralError(RuntimeError):
    """Raised when a file is not a well-formed OPC/.docx package at all.

    This is distinct from a validation FAIL: a FAIL means a structural
    element changed in a document that is still a valid docx. This error
    means the file itself can't be opened as one -- e.g. it isn't a zip, or
    it's missing word/document.xml -- and no assertion can even run.
    """


@dataclass
class DocxPackage:
    """Read-only handle on a single .docx file's OpenXML parts."""

    path: Path
    _zip: zipfile.ZipFile = field(repr=False)
    _xml_cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def open(cls, path: str | Path) -> "DocxPackage":
        path = Path(path)
        if not path.exists():
            raise DocxStructuralError(f"File not found: {path}")
        try:
            zf = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as exc:
            raise DocxStructuralError(
                f"{path} is not a valid .docx (not a readable ZIP/OPC package): {exc}"
            ) from exc
        if "word/document.xml" not in zf.namelist():
            raise DocxStructuralError(
                f"{path} is a zip file but has no word/document.xml -- not a .docx package"
            )
        return cls(path=path, _zip=zf)

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "DocxPackage":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- part access ---------------------------------------------------------

    def part_names(self) -> list[str]:
        return self._zip.namelist()

    def has_part(self, part_name: str) -> bool:
        return part_name in self._zip.namelist()

    def read_part_bytes(self, part_name: str) -> Optional[bytes]:
        if not self.has_part(part_name):
            return None
        return self._zip.read(part_name)

    def read_part_xml(self, part_name: str) -> Optional[etree._Element]:
        """Parse a part as XML. Returns None if the part doesn't exist.
        Raises DocxStructuralError if the part exists but is not well-formed
        XML -- that is itself a structural fidelity failure worth surfacing."""
        if part_name in self._xml_cache:
            return self._xml_cache[part_name]
        raw = self.read_part_bytes(part_name)
        if raw is None:
            return None
        try:
            tree = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise DocxStructuralError(
                f"{self.path}: part '{part_name}' exists but is not well-formed XML: {exc}"
            ) from exc
        self._xml_cache[part_name] = tree
        return tree

    @property
    def document_xml(self) -> etree._Element:
        tree = self.read_part_xml("word/document.xml")
        if tree is None:
            raise DocxStructuralError(f"{self.path}: missing word/document.xml")
        return tree

    def find_header_footer_parts(self) -> dict[str, list[str]]:
        """Return {'header': [...part names...], 'footer': [...part names...]}
        discovered by walking [Content_Types].xml overrides AND the raw
        namelist, so this works even if a document uses non-standard
        numbering for its header/footer parts."""
        headers, footers = [], []
        for name in self.part_names():
            base = name.rsplit("/", 1)[-1]
            if base.startswith("header") and base.endswith(".xml"):
                headers.append(name)
            elif base.startswith("footer") and base.endswith(".xml"):
                footers.append(name)
        return {"header": sorted(headers), "footer": sorted(footers)}

    def document_relationships(self) -> dict[str, dict]:
        """Parse word/_rels/document.xml.rels into {r:id -> {type, target}}."""
        tree = self.read_part_xml("word/_rels/document.xml.rels")
        if tree is None:
            return {}
        rels = {}
        for rel in tree.findall("pr:Relationship", NAMESPACES):
            rels[rel.get("Id")] = {
                "type": rel.get("Type"),
                "target": rel.get("Target"),
            }
        return rels

    def header_footer_reference_ids(self) -> dict[str, list[str]]:
        """
        Collect the r:id values referenced by <w:headerReference> and
        <w:footerReference> elements inside every <w:sectPr> in the document,
        keyed by 'header' / 'footer'. Cross-referencing these against
        document_relationships() is how we confirm a sectPr's header/footer
        pointer actually resolves to a real part, not a dangling reference.
        """
        doc = self.document_xml
        out = {"header": [], "footer": []}
        for tag, key in (("headerReference", "header"), ("footerReference", "footer")):
            for el in doc.iter(f"{{{NAMESPACES['w']}}}{tag}"):
                rid = el.get(f"{{{NAMESPACES['r']}}}id")
                if rid:
                    out[key].append(rid)
        return out

    def section_properties(self) -> list[etree._Element]:
        """All <w:sectPr> elements: the last child of the body (final section)
        plus one inside the last paragraph of every earlier section break."""
        doc = self.document_xml
        return list(doc.iter(f"{{{NAMESPACES['w']}}}sectPr"))
