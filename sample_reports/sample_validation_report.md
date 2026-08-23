# SuperDocs Round-trip Fidelity Report

## Summary

- **Original document**: `/tmp/verify/original.docx`
- **Edited document**: `/tmp/verify/broken.docx`
- **Generated at**: 2026-08-07T09:56:32+00:00
- **Execution time**: 0.002s
- **Validation status**: **FAIL**
- **Assertions executed**: 24
- **Passed**: 22
- **Failed**: 2

## Structural Differences

| Assertion | Section | Element | Expected | Actual |
|---|---|---|---|---|
| Bookmarks | Document | Bookmark 'intro_ref' | bookmark exists | bookmark missing |
| Internal Cross-References | Document | Reference target 'intro_ref' | target bookmark exists in the document | no bookmark with this name found |

## All Assertions

| Assertion | Section | Element | Status |
|---|---|---|---|
| Footnotes | Document | word/footnotes.xml part | PASS |
| Footnotes | Document | Footnote count | PASS |
| Headers & Footers | Document | Header part(s) present | PASS |
| Headers & Footers | Document | Header count | PASS |
| Headers & Footers | Document | Header reference wiring | PASS |
| Headers & Footers | Document | Footer part(s) present | PASS |
| Headers & Footers | Document | Footer count | PASS |
| Headers & Footers | Document | Footer reference wiring | PASS |
| Page Number Fields | Document | Page number field code present | PASS |
| Page Number Fields | Document | Page number field count | PASS |
| Tracked Changes | Document (Original) | <w:ins> id=10 | PASS |
| Tracked Changes | Document (Edited) | <w:ins> id=10 | PASS |
| Tracked Changes | Document | Revision authors present in edited export | PASS |
| Comments | Document | word/comments.xml part | PASS |
| Comments | Document | Comment count | PASS |
| Comments | Document | Comment id=1 | PASS |
| Comments | Document | Comment id=1 anchor | PASS |
| Equations | Document | Native equation (oMath) count | PASS |
| Bookmarks | Document | Bookmark 'intro_ref' | FAIL |
| Internal Cross-References | Document | Cross-reference field count | PASS |
| Internal Cross-References | Document | Reference target 'intro_ref' | FAIL |
| Section Geometry | Document | Section count | PASS |
| Section Geometry | Section 1 | Page size & orientation | PASS |
| Section Geometry | Section 1 | Margins | PASS |