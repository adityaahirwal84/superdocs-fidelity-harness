# Live verification: findings

**Date of live run:** 2026-08-10
**Command:** `superdocs-fidelity run examples/sample_original.docx --instruction "Add a one-sentence executive summary at the top" --cost-cap 1 --small-sample --output live_edited.docx`
**Result:** Live round trip completed successfully (upload → edit → approve →
export all succeeded against the real API). Structural validation: **FAIL**
(22/24 assertions passed; 2 failed).
**Evidence files in this folder:** `live_edited.docx` (the real SuperDocs
export), `live_validation_report.json`, `live_validation_report.md`.

## Verdict

**Genuine regression in SuperDocs' export, not a validator bug.** Per the
verification instructions, the validator was left unchanged — this file is
the documentation of that finding.

The two failing assertions:

| Assertion | Element | Expected | Actual |
|---|---|---|---|
| Bookmarks | Bookmark `'intro_ref'` | bookmark exists | bookmark missing |
| Internal Cross-References | Cross-reference field count | >= 1 | 0 |

## How this was confirmed (not just trusted from the report)

Before accepting the validator's own verdict, both failures were checked
independently, at the raw OpenXML level, against the actual bytes of
`live_edited.docx`:

1. **Exhaustive string search across every part of the exported package**
   (not just `word/document.xml`) for any trace of the bookmark name or
   field-code machinery that might indicate the validator missed a
   relocated element:

   ```
   $ grep -rl "intro_ref" .                    -> NOT FOUND anywhere
   $ grep -rl "bookmarkStart\|bookmarkEnd" .    -> NOT FOUND anywhere
   $ grep -rl "fldSimple\|instrText\|fldChar" . -> only word/footer1.xml
   ```

   The one field-code hit is the page-number field (`PAGE` / `NUMPAGES` in
   `word/footer1.xml`), unrelated to the missing cross-reference — confirmed
   by reading that part directly, and consistent with the Page Number
   Fields assertion passing.

2. **Direct paragraph-level diff of the affected content.**

   Original (`word/document.xml`):
   ```xml
   <w:p>
     <w:bookmarkStart w:id="0" w:name="intro_ref"/>
     <w:r><w:t>Introduction</w:t></w:r>
     <w:bookmarkEnd w:id="0"/>
   </w:p>
   <w:p>
     <w:r><w:t xml:space="preserve">See the </w:t></w:r>
     <w:fldSimple w:instr="REF intro_ref \h"><w:r><w:t>Introduction</w:t></w:r></w:fldSimple>
     <w:r><w:t xml:space="preserve"> section for context.</w:t></w:r>
     <w:r><w:t>This claim needs a citation.</w:t></w:r>
     <w:r><w:footnoteReference w:id="1"/></w:r>
   </w:p>
   ```

   Live export (`word/document.xml`, namespace noise trimmed):
   ```xml
   <w:p>
     <w:r><w:rPr/><w:t>Introduction</w:t></w:r>
   </w:p>
   <w:p>
     <w:r><w:rPr/><w:t>See the  section for context.This claim needs a citation.</w:t></w:r>
     <w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="1"/></w:r>
   </w:p>
   ```

   The bookmark wrapper around "Introduction" is gone. The `REF intro_ref`
   field is gone -- not converted to a hyperlink, not converted to static
   text carrying the resolved value, just deleted -- leaving a literal
   double space (`"See the  section"`) where the field used to render as
   "Introduction". The four separate runs in the original paragraph were
   also collapsed into one run with concatenated text, meaning this
   paragraph was fully re-serialized rather than surgically edited.

3. **Cross-checked that this isn't part of a broader serialization failure**
   that the validator would also be expected to catch elsewhere (i.e. ruling
   out "the validator got lucky and everything is actually broken"): the
   other 22 assertions all passed, and were spot-verified against the raw
   XML too -- footnote body and reference both intact, comment body/author/
   date/anchor all intact, the tracked-change insertion survived (with a
   renumbered `w:id`, `10` -> `1`, which is expected and not flagged, since
   Word legitimately renumbers revision ids), the native `<m:oMath>`
   equation survived and was even upgraded to structured OMML (`<m:sSup>`
   for the exponent) rather than flattened, and header/footer relationship
   wiring and section geometry (page size, margins) all matched exactly.

## What this implies

The scope of what broke -- a bookmark and its dependent field, in a
paragraph the edit instruction never asked to touch ("Add a one-sentence
executive summary at the top" only concerns the top of the document) --
suggests SuperDocs' edit pipeline re-serializes and lightly normalizes
paragraphs outside the literal diff region of an instructed edit, and that
normalization pass does not currently preserve bookmark start/end markers
or simple field codes (`w:fldSimple`) that live inside a paragraph it
touches during that pass. Everything else the harness checks -- footnotes,
comments, tracked changes, equations, headers/footers, page geometry --
survived the same round trip intact, so this reads as a specific gap in
that normalization step rather than a general fidelity problem with
SuperDocs' export.

## Why the validator was not changed

Every one of its ten assertion categories requires deliberately breaking
that exact structural element in a hand-authored fixture and confirming
detection (see `tests/test_regression.py`); the Bookmarks and Internal
Cross-References modules are exercised by
`build_regression_missing_bookmark()` specifically and pass that regression
test. Both modules' detection logic was re-read line by line against this
live failure as an independent check, not merely re-run: `bookmarks.py`
compares bookmark *names* (not ids, which Word may legitimately renumber)
between original and edited, and correctly reported `intro_ref` as absent
because it is, in fact, absent from every part of the package.
`cross_references.py` scans both `w:fldSimple` and complex-field
`w:instrText` runs across the body and every header/footer part for `REF`/
`PAGEREF` instructions, and correctly reported zero because there are zero
anywhere in the package. Changing either module to stop reporting this
would mean hiding a real, confirmed loss of document structure -- exactly
what this harness exists to catch.
