# Working with this repository

This is the SuperDocs "Round-trip fidelity harness with structural
assertions" build (assignment 2.1, difficulty band S3). It's a validation
suite, not a document editor and not a clone of SuperDocs.

## Ground rules for anyone (human or agent) picking this up

- The `validate` subcommand and everything under `tests/` must always work
  with **zero network access and no API key**. If a change breaks that,
  it's a regression, not a tradeoff.
- Every structural assertion module lives in `assertions/` and exposes one
  function: `run(original: DocxPackage, edited: DocxPackage) ->
  list[AssertionResult]`. Don't special-case a filename or a specific
  document's structure anywhere in this package -- the whole point is that
  a stranger can point it at their own .docx unmodified.
- The validator inspects raw OpenXML (`zipfile` + `lxml`) on purpose. Don't
  reach for python-docx, text extraction, or a PDF/image comparison inside
  `validator/` or `assertions/` even if it looks like a shortcut -- that's
  exactly what the assignment forbids.
- Never hardcode a SuperDocs API key, endpoint, or response shape without
  checking it against `docs.superdocs.app` first. If a docs page moved,
  fetch the current one rather than guessing from memory.
- Budget guard changes need a test in `tests/test_budget_guard.py` before
  they're considered done -- this is the one part of the harness that can
  cost real money if it's wrong.

## Adding a new structural assertion

1. Write `assertions/your_check.py` with a `run(original, edited)` function
   returning `list[AssertionResult]` (see `assertions/base.py`).
2. Register it in `assertions/__init__.py`'s `ALL_MODULES` list.
3. Add a fixture-breaking function in `tests/fixtures/build_fixtures.py`
   (`build_regression_your_check(...)`) and a regression test in
   `tests/test_regression.py` that proves the validator catches it.
4. Run `pytest` -- everything, including your new test, should pass.

## Running things

```bash
pip install -r requirements.txt

# Structural comparison only, no API key needed:
./superdocs-fidelity validate original.docx edited.docx

# Full live round trip (needs SUPERDOCS_API_KEY, see .env.example):
./superdocs-fidelity run original.docx --instruction "Add an executive summary" --cost-cap 2

pytest
```
