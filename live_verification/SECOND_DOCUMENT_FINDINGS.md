# Live verification #2: findings (Section Geometry)

**Original:** `examples/second_document.docx`
**Live export:** `second_live_edited.docx` (uploaded, saved here as
`second_live_edited.docx`)
**Reported failure:**

| Assertion | Element | Expected | Actual |
|---|---|---|---|
| Section Geometry | Section 1: Page size & orientation | `11906x16838 portrait` | `11909x16834 portrait` |

**Evidence files in this folder:** `second_live_edited.docx`,
`second_live_validation_report.json`, `second_live_validation_report.md`.

## Verdict

**Genuine, byte-level change made by SuperDocs' export -- not a validator
false positive.** Per the instructions, the validator was not touched. This
file documents the evidence.

## How this was confirmed

### 1. Reproduced the failure with the unmodified CLI

```
$ superdocs-fidelity validate examples/second_document.docx second_live_edited.docx
VALIDATION STATUS : FAIL
Assertions executed: 17
Passed             : 16
Failed             : 1

[Section Geometry] Section 1
  Element  : Page size & orientation
  Expected : 11906x16838 portrait
  Actual   : 11909x16834 portrait
```

### 2. Re-read the assertion logic before trusting its output

`assertions/section_geometry.py::_pg_sz()` does a direct, verbatim string
read of the `w:w` / `w:h` attributes on `<w:pgSz>` via `element.get(...)`,
and `run()` compares the two resulting dicts with plain Python `==`. There
is no unit conversion, rounding, or tolerance logic anywhere in this path --
so whatever it reports is a literal transcription of what the XML attribute
strings say, not an interpretation that could introduce drift on its own.

### 3. Independently confirmed the actual attribute values with zero XML

**parsing involved at all** -- plain `grep` on the raw, unzipped bytes of
`word/document.xml` from both files, bypassing `lxml` (and therefore the
validator's own reader) entirely:

```
$ unzip -p examples/second_document.docx word/document.xml | grep -o '<w:pgSz[^/]*/>'
<w:pgSz w:w="11906" w:h="16838" w:orient="portrait"/>

$ unzip -p second_live_edited.docx word/document.xml | grep -o '<w:pgSz[^/]*/>'
<w:pgSz w:w="11909" w:h="16834"/>
```

The numbers the validator reported are exactly what's in the file. The
`w:orient` attribute is simply absent in the live export rather than
changed -- that resolves to the OOXML-spec default of `portrait`
(`_pg_sz()` handles this explicitly: `el.get(...) or "portrait"`), which is
why orientation itself was not flagged as a separate difference; only the
numeric dimensions were.

### 4. Confirmed margins -- the other half of this section's geometry --

**are byte-identical**, ruling out a wholesale re-derivation of the section
properties:

```
$ unzip -p examples/second_document.docx word/document.xml | grep -o '<w:pgMar[^/]*/>'
<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>

$ unzip -p second_live_edited.docx word/document.xml | grep -o '<w:pgMar[^/]*/>'
<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>
```

Identical. Whatever changed the page size did not touch the margins.

### 5. Ruled out a standard-preset substitution

Checked `(11909, 16834)` against every common OOXML page-size preset
(Letter `12240x15840`, Legal `12240x20160`, A4 `11906x16838`, A5
`8391x11907`, B5 `9978x14170`, Tabloid `15840x24480`) -- no match. This
isn't SuperDocs swapping in a different named page size; the original
`11906x16838` is itself the exact standard OOXML value for A4, and the
live export's value is not any recognized preset.

### 6. Quantified the actual physical drift

```
width : 11909 - 11906 = +3 twips  = +0.0529 mm
height: 16834 - 16838 = -4 twips  = -0.0706 mm
```

A twip is 1/1440 inch (1/20 of a point). The live export's page is about
**0.05 mm wider and 0.07 mm shorter** than the original -- roughly a tenth
of the width of a human hair, invisible at any print or screen resolution,
but a real, non-zero, non-rounding-neutral difference in the literal
attribute values stored in the file.

## What this implies

This does not look like an intentional resize, a page-size preset swap, or
a rendering/display artifact -- the delta is too small to be visible and
doesn't correspond to any standard target size. The more likely explanation
is that SuperDocs' internal document model stores or round-trips page
geometry through a different unit (e.g. millimeters, points, or pixels at
some DPI) with floating-point rounding, and the conversion back to OOXML
twips on export doesn't land exactly on the input value. This investigation
did not attempt to reverse-engineer SuperDocs' internal unit pipeline --
several plausible conversion paths (96 dpi pixels, 72 dpi points, whole-mm
rounding) were checked by hand and none reproduced `11909x16834` exactly,
so the precise mechanism is not established here, only that the change is
real and sub-millimeter in magnitude.

Practically: this is very unlikely to be visible in Word or on a printed
page, but it is a genuine loss of exactness in the round trip, and
`Section Geometry` is exactly the assertion category built to catch this
class of change -- the assignment's own framing ("looks fine in a text diff
and wrong on a printed page") is really about geometry drift like this,
even when, as here, the magnitude turns out to be negligible.

## Why the validator was not changed

The comparison is an exact match by design (see `assertions/
section_geometry.py`'s module docstring: silently normalizing page
size/orientation is exactly the kind of change this category exists to
catch), and a 3-4 twip drift is a real difference in the file, confirmed
independently of the validator via raw `grep` on the unzipped bytes. Adding
a tolerance window here would be a genuine design change to what "passes,"
not a bug fix -- and was explicitly out of scope for this investigation.
No code in `assertions/`, `validator/`, or `reporting/` was modified.
