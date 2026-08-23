# Architecture

```
                     ┌─────────────────────────────────────────────┐
                     │              cli/main.py                    │
                     │   validate <o> <e>      run <o> --instr ...  │
                     └──────────┬───────────────────┬──────────────┘
                                │                    │
                    (local, free, no key)     (live SuperDocs round trip)
                                │                    │
                                │         ┌──────────▼───────────┐
                                │         │  superdocs_client/    │
                                │         │  ─────────────────    │
                                │         │  upload_document()    │  1. upload
                                │         │  start_edit()         │  2. chat/async
                                │         │  poll_job()           │
                                │         │  approve_all_changes()│  3. approve
                                │         │  export_document()    │  4. export
                                │         │                       │
                                │         │  BudgetGuard          │  cost cap,
                                │         │  (estimate + actual)  │  estimate, actual
                                │         └──────────┬───────────┘
                                │                    │ writes edited.docx
                                ▼                    ▼
                     ┌─────────────────────────────────────────────┐
                     │              validator/engine.py             │
                     │   opens BOTH docx files as raw OpenXML        │
                     │   (zipfile + lxml, never text/OCR/PDF)        │
                     └──────────┬────────────────────────────────────┘
                                │ runs every module in assertions/
                                ▼
     ┌───────────────────────────────────────────────────────────────────┐
     │ footnotes · headers_footers · page_fields · tracked_changes ·      │
     │ comments · equations · bookmarks · cross_references ·              │
     │ section_geometry                                                    │
     │   each: run(original, edited) -> list[AssertionResult]              │
     └──────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────────────────────┐
                     │            reporting/report.py                │
                     │   summary, structural differences,             │
                     │   PASS/FAIL, execution time, cost               │
                     │   -> to_text() / to_markdown() / to_json()      │
                     └─────────────────────────────────────────────┘
```

## Data flow for `run`

1. **Upload** (`POST /v1/documents/upload`, multipart) — loads the original
   `.docx` as the session's active document. Response includes a chunk count
   used both for the small-sample check and the budget pre-flight estimate.
2. **Chat / edit instruction** (`POST /v1/chat/async` with
   `approval_mode=ask_every_time`) — starts an async, human-in-the-loop
   edit job and returns a `job_id`.
3. **Poll** (`GET /v1/jobs/{job_id}`) — until `awaiting_approval` or a
   terminal state. Large documents can legitimately take from ~30 seconds to
   several minutes; the poll loop only gives up after
   `SUPERDOCS_MAX_POLL_SECONDS`, and that's reported as "still processing,"
   not a failure.
4. **Approve** (`POST /v1/chat/{session_id}/approve`) — batch-approves every
   pending change. The confirmed `usage.ops_charged` from the resulting job
   is fed into the `BudgetGuard`.
5. **Export** (`POST /v1/documents/export`, `format=docx`) — writes the
   edited `.docx` to disk. Never billed as an operation per SuperDocs' docs.
6. **Validate** — the same code path as the standalone `validate`
   subcommand runs against `(original, exported)`, entirely offline.

## Why the validator and the client are separate packages

`validator/` and `assertions/` have zero dependency on `superdocs_client/`.
That's deliberate: it's what lets `validate` — and the entire regression
suite — run with no network access and no API key, which is also why it's
the piece graded as "real tests that run without a live key."
