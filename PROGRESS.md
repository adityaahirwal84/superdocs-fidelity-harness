# Progress & assumptions

A running log of decisions made while building this, per the "log the
assumptions you make as you go" working method.

## API contract

- Confirmed the four-call contract against the live docs at
  docs.superdocs.app rather than guessing: `POST /v1/documents/upload`
  (multipart), `POST /v1/chat/async` + `GET /v1/jobs/{id}`, `POST
  /v1/chat/{session_id}/approve`, `POST /v1/documents/export`. These match
  the assignment's "upload, chat, approve, export" naming exactly.
- Chose `chat_async` with `approval_mode="ask_every_time"` over the
  synchronous `chat` endpoint by default, since the assignment explicitly
  calls for an "approve proposed changes" stage and the sync endpoint has no
  HITL path.
- `response_mode="compact"` is used on the edit request to keep the harness
  cheap on large documents (per SuperDocs' own guidance for agents), since
  the harness never needs the full HTML mid-flight -- only the final
  exported .docx bytes, which come from a separate export call.
- Applied the "proposed-change content can arrive JSON-encoded and need a
  second parse" note from the docs via `_maybe_parse_json`, even though the
  fixtures and my own smoke testing never exercised a case where it actually
  fires (I don't have a live key in this sandbox -- see below). Left it in
  defensively since the docs call it out as the single most common
  integration bug.

## What I could not verify live

- This sandbox's network egress is locked to an allowlist that does not
  include api.superdocs.app, so I could not run `superdocs-fidelity run`
  against a live account inside this environment. I DID fetch the current
  API docs and OpenAPI schema live and built the client strictly against
  that contract, and I exercised every failure path (`SuperDocsAPIError`,
  `BudgetExceededError`, missing API key) that doesn't require an actual
  successful call. Before submitting, run `run` once against a real account
  with `--cost-cap 1` on a tiny document to confirm the live wiring, per the
  assignment's own advice to send one small instruction first while things
  warm up.

## Live verification attempt (later session)

A real SuperDocs API key was provided later, with an explicit request to
run the full live round trip and report results. Before spending anything
against a real account, I re-checked whether the sandbox's network
restriction (noted above) still applied — it did, and I confirmed this
directly rather than assuming it:

```
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" https://api.superdocs.app/health --max-time 10
HTTP 403
$ curl -s https://api.superdocs.app/health --max-time 10
Host not in allowlist: api.superdocs.app. Add this host to your network egress settings to allow access.

$ curl -s -o /dev/null -w "HTTP %{http_code}\n" https://api.superdocs.app/v1/sessions \
    -H "Authorization: Bearer <redacted>" --max-time 10
HTTP 403   # identical error, with a real key attached -- confirms this is not an auth problem

$ curl -s -o /dev/null -w "HTTP %{http_code}\n" https://example.com --max-time 8
HTTP 403   # arbitrary internet hosts are blocked the same way

$ curl -s -o /dev/null -w "HTTP %{http_code}\n" https://api.anthropic.com --max-time 8
HTTP 404   # a control request to an ALLOWLISTED host reaches the server fine
           # (wrong path, but it connected) -- proving this is a specific
           # allowlist, not a general network outage
```

Conclusion: the block is enforced by the sandbox's own egress proxy before
any request reaches SuperDocs, and it is identical whether or not a valid
API key is attached. No key can get past a host-level allowlist rejection.
I did not fabricate a "live run passed" result, and I did not spend any of
the provided key's operation budget, since no call ever left the sandbox.

**What I did instead, so the live run itself is a two-command formality
once network access exists:**

1. Re-audited the client code (`superdocs_client/client.py`) line by line
   against the currently-live OpenAPI schema and Python/curl examples at
   docs.superdocs.app (re-fetched fresh, not from memory or from the first
   build session) to confirm no drift.
2. Ran the full local test suite plus a manual verification harness (this
   environment has no `pytest` package and no way to install one, so the
   same assertions were run through a small stdlib-only runner) -- all pass,
   see "Local verification (this session)" below.
3. Exercised the CLI's `run` subcommand's error paths against the real host
   with the real key, up to the point network access is required, and found
   and fixed two real bugs in the process (see below) -- so what's left for
   a live run is exclusively the parts that need a reachable network, not
   general logic bugs.
4. Added `examples/sample_original.docx`,
   `examples/sample_edited_faithful.docx`, and
   `examples/sample_edited_with_regression.docx` -- committed, real
   documents -- so `run` (or `validate`) can be tried immediately by anyone
   with network access, without needing to run Python to generate a
   fixture first.
5. Documented the exact reproduction steps in the README's "Live
   verification status" section, including the precise command to run and
   what a passing/failing exit code and report look like.

### Bugs found and fixed while probing the real (blocked) request path

Both were found by actually running `cli/main.py run` against the live host
with the real key -- not by inspection -- which is exactly why this step
was worth doing even without full network access:

1. **`BudgetGuard(declared_cap=0)` raised an uncaught `ValueError` with a
   raw traceback** instead of a clean CLI error. `--cost-cap 0` is a
   plausible typo/misunderstanding for a first-time user ("I don't want to
   spend anything") and deserved a real "error: ..." message, not a stack
   trace. Fixed in `cli/main.py::cmd_run` by catching `ValueError` around
   `BudgetGuard` construction.
2. **`client.upload_document()` and `client.export_document()` calls in
   `cmd_run` were not wrapped in `SuperDocsAPIError` handling**, so a real
   API error (confirmed live: `403 Host not in allowlist` from the sandbox
   proxy) surfaced as an unhandled traceback instead of the same clean
   `error: ...` + exit code 4 pattern every other stage already used. Fixed
   by wrapping both calls.

Both fixes are covered by the existing error-path tests conceptually (same
`SuperDocsAPIError` / `BudgetExceededError` -> exit-code contract asserted
elsewhere); the fastest way to add a literal regression test for #2 would be
to inject a fake `requests.Session` that raises `SuperDocsAPIError` on
`upload`/`export` -- left as a documented follow-up rather than added here,
since it would be the first test in the suite to mock the network layer,
and every other test's value comes specifically from *not* mocking anything
below the CLI boundary.

### Local verification (this session)

Re-ran, after the fixes above:
- The full manual verification harness (10/10 checks pass): faithful edit
  passes every assertion; each of the seven regression scenarios is
  detected by name; the budget guard blocks over-cap spend; report
  generation is well-formed text/Markdown/JSON.
- `./superdocs-fidelity validate` against both the pre-existing test
  fixtures and the newly committed `examples/` documents: correct
  PASS/FAIL, correct exit codes (0/1), correct report contents.
- `./superdocs-fidelity run` against the real host with the real key, up to
  the network boundary: correct, named error output and exit code 4 (not a
  traceback) for the confirmed-live `403` response.
- `./superdocs-fidelity run --cost-cap 0`: correct, named error and exit
  code 2 (not a traceback).
- Every `.py` file in the repository byte-compiles cleanly
  (`python3 -m py_compile`).

### For whoever runs the actual live verification

Grant network access to `api.superdocs.app` (in Claude's network settings,
or by running this from a machine/CI job with normal internet access), then:

```bash
export SUPERDOCS_API_KEY=sk_your_real_key
./superdocs-fidelity run examples/sample_original.docx \
  --instruction "Add a one-sentence executive summary at the top" \
  --cost-cap 1 --small-sample \
  --output /tmp/live_edited.docx \
  --json-report live_verification_report.json
```

If it fails, paste the printed `error: ...` line and
`live_verification_report.json` back for a fix -- with network access
restored, this becomes a fast, ordinary bug-fix loop rather than a repeat of
the blocked-network investigation above.

## Live verification: completed (2026-08-10)

Network access to `api.superdocs.app` was restored (outside this project's
control -- a sandbox/environment setting, not a code change) and a real API
key was provided. The live round trip was run exactly as specified above:

```
$ superdocs-fidelity run examples/sample_original.docx \
    --instruction "Add a one-sentence executive summary at the top" \
    --cost-cap 1 --small-sample --output live_edited.docx
```

Upload, edit instruction, HITL approval, and export all completed
successfully against the real account. `validate` was then run against the
real exported document:

```
VALIDATION STATUS : FAIL
Assertions executed: 24
Passed             : 22
Failed             : 2
  - Bookmarks: Bookmark 'intro_ref' -- expected exists, actual missing
  - Internal Cross-References: Cross-reference field count -- expected >= 1, actual 0
```

### Was this a validator bug or a genuine regression?

Investigated at the raw OpenXML level before trusting the validator's own
report -- opened the actual `live_edited.docx` as a zip, grepped every part
(not just `word/document.xml`) for `intro_ref`, `bookmarkStart`/
`bookmarkEnd`, and any field-code machinery, and diffed the affected
paragraphs against the original byte for byte.

**Verdict: genuine regression in SuperDocs' export.** The bookmark and its
dependent `REF intro_ref` field are absent from every part of the exported
package, not relocated or renamed -- confirmed by exhaustive search, not
inferred from the validator's summary alone. The affected paragraph's four
original runs were also collapsed into one run with concatenated text
(`"See the "` + `""` + `" section for context."` + `"This claim needs a
citation."` -> `"See the  section for context.This claim needs a
citation."`, note the literal double space where the field used to render),
indicating SuperDocs fully re-serialized that paragraph during the edit
even though the instruction ("add a summary at the top") never asked to
touch it. Every other structural category on the same live export --
footnotes, comments, tracked changes, native equations (the oMath equation
was even upgraded to structured `<m:sSup>` markup rather than flattened),
header/footer relationship wiring, and section geometry -- came through the
same round trip intact, which is what makes this read as a specific gap in
SuperDocs' paragraph-normalization step rather than a general fidelity
problem.

Full evidence, XML excerpts, and the exhaustive-search commands are
preserved permanently in
[`live_verification/FINDINGS.md`](live_verification/FINDINGS.md), alongside
the real exported document and generated reports in that same folder.

### Why the validator was left unchanged

Per the verification instructions: a genuine regression means document the
finding and leave the validator alone, since "fixing" the validator to stop
reporting a real, confirmed loss of document structure would just be
hiding the bug it exists to catch. Both failing modules'
(`assertions/bookmarks.py`, `assertions/cross_references.py`) detection
logic was re-read line by line against this specific live failure as an
independent sanity check (not just re-run): both compare bookmark *names*/
field *instructions* actually present in the package, not ids or counts
alone, and both correctly reported absence because the elements are, in
fact, absent. No code in `assertions/`, `validator/`, or `reporting/` was
changed as part of this investigation.

## Validator design

- Deliberately did NOT use python-docx for the validator itself (only for
  building convenience in test fixtures, and even there I hand-authored the
  actual XML parts for full control). python-docx abstracts away exactly the
  structures this harness needs to inspect directly -- footnotes, comments,
  bookmarks, tracked-change metadata, header/footer relationship wiring --
  so raw `zipfile` + `lxml` on the OPC package is the only approach that
  satisfies "inspect the real Microsoft Word DOCX structure."
- Bookmark/cross-reference/footnote/comment "count" assertions treat
  `edited >= original` as PASS rather than requiring exact equality, since a
  legitimate edit can add new footnotes, bookmarks, etc. What must never
  decrease is the survival of every ORIGINAL element (checked by name/id/
  content, not just aggregate count) -- that's the actual fidelity claim.
- Equation-to-image conversion can't be proven with certainty from the
  package alone (an image is sometimes just an image). The assertion flags
  the pattern -- native oMath count dropped while inline image count rose by
  a comparable amount -- as a FAIL with a note that it's a likely conversion,
  since silence here is worse than an occasional false positive a human can
  dismiss in two seconds.
- Section geometry is compared positionally (section 1 to section 1, section
  2 to section 2, ...). If sections are inserted/removed the counts assertion
  catches that; the per-section geometry comparison only runs up to
  `min(len(original), len(edited))` to avoid index errors while still
  surfacing the count mismatch as its own explicit FAIL.

## Budget guard

- SuperDocs doesn't expose a "cost before you commit" endpoint, so the guard
  estimates using the documented billing rule (1 operation per 25 sections
  edited, minimum 1) BEFORE the call, and reconciles against the real
  `usage.ops_charged` field returned on every chat response AFTER the call.
  A cap violation raises before any further billable call is attempted;
  export and download are excluded from the cap entirely, since SuperDocs'
  own docs state exports are never billed.

## Scope cuts

- Did not build MCP-based access alongside REST; the assignment says either
  surface is acceptable for an assigned card and REST is simpler to test
  without a running MCP client. Documented here as a defended cut, not a
  gap I didn't notice.
- Did not attempt PDF/HTML export fidelity checks -- the assignment card is
  specifically about DOCX-in, DOCX-out round-trip fidelity, and adding other
  export formats would be scope creep beyond "build ONLY what the assignment
  requires."
