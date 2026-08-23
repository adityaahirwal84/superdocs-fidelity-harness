"""
Command-line interface for the Round-trip Fidelity Harness.

Two subcommands:

  superdocs-fidelity validate original.docx edited.docx
      Pure local structural comparison. No network calls, no API key needed.
      This is what "validate original.docx edited.docx or an equivalent CLI"
      in the assignment refers to, and it's also what the regression test
      and CI use, since it runs without a live key.

  superdocs-fidelity run original.docx --instruction "..." --cost-cap 3
      The full round trip: upload -> edit instruction -> approve -> export
      -> structural validation, against the live SuperDocs API. Requires
      SUPERDOCS_API_KEY. Enforces the budget guard's declared cost cap
      before spending a single operation.

Changing which document to validate never requires changing source code --
every path is a CLI argument.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from config import load_settings
from superdocs_client import (
    SuperDocsClient,
    BudgetGuard,
    BudgetExceededError,
    JobFailedError,
    JobTimeoutError,
    SuperDocsAPIError,
)
from validator import ValidationEngine
from reporting import build_report


def _write_report(report, text_out, json_out, markdown_out) -> None:
    print(report.to_text())
    if text_out:
        Path(text_out).write_text(report.to_text(), encoding="utf-8")
    if json_out:
        Path(json_out).write_text(report.to_json(), encoding="utf-8")
    if markdown_out:
        Path(markdown_out).write_text(report.to_markdown(), encoding="utf-8")


def _add_report_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--text-report", metavar="PATH", help="Write the plain-text report to this path.")
    parser.add_argument("--json-report", metavar="PATH", help="Write the machine-readable JSON report to this path.")
    parser.add_argument("--markdown-report", metavar="PATH", help="Write the Markdown report to this path (good for a PR).")


def cmd_validate(args: argparse.Namespace) -> int:
    engine = ValidationEngine()
    run = engine.run(args.original, args.edited)
    report = build_report(run)
    _write_report(report, args.text_report, args.json_report, args.markdown_report)
    return 0 if report.overall_status == "PASS" else 1


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        guard = BudgetGuard(declared_cap=args.cost_cap)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        client = SuperDocsClient(settings)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    session_id = args.session_id or f"fidelity-harness-{uuid.uuid4().hex[:12]}"
    print(f"Session: {session_id}")
    print(f"Budget guard: declared cost cap = {guard.declared_cap} operation(s)")

    # Stage 1: upload
    print(f"\n[1/5] Uploading {args.original} ...")
    try:
        upload = client.upload_document(args.original, session_id)
    except SuperDocsAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    print(f"  Loaded {upload.filename} ({upload.chunks_count} chunk(s))")

    if args.small_sample and upload.chunks_count > settings.small_sample_chunk_limit:
        print(
            f"error: --small-sample is set but this document has {upload.chunks_count} chunks "
            f"(limit {settings.small_sample_chunk_limit}). Validate a smaller document first, "
            "or drop --small-sample once you trust the harness on this document size.",
            file=sys.stderr,
        )
        return 2

    # Budget pre-flight: refuse to even start the edit if the estimate alone busts the cap.
    estimate = BudgetGuard.estimate_chat_ops(upload.chunks_count)
    try:
        guard.check_estimate(estimate, label=f"edit instruction over {upload.chunks_count} chunks")
    except BudgetExceededError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(f"  Estimated cost of the edit instruction: {estimate} operation(s)")

    # Stage 2: chat / edit instruction (HITL by default)
    print(f"\n[2/5] Sending edit instruction: {args.instruction!r}")
    try:
        job_id = client.start_edit(session_id, args.instruction, approval_mode="ask_every_time")
        job = client.poll_job(job_id)
    except (JobFailedError, JobTimeoutError, SuperDocsAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    # Stage 3: approve proposed changes
    if job.is_awaiting_approval:
        changes = job.pending_changes
        print(f"\n[3/5] {len(changes)} change(s) proposed -- approving all (batch HITL approval).")
        for c in changes:
            print(f"  - {c.get('operation', '?')}: {c.get('ai_explanation', 'no explanation given')}")
        try:
            client.approve_all_changes(session_id, job_id, changes)
            job = client.poll_job(job_id, stop_statuses=("completed", "failed", "cancelled"))
        except (JobFailedError, JobTimeoutError, SuperDocsAPIError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 4
    else:
        print("\n[3/5] No changes required approval (job resolved directly).")

    usage = job.usage
    ops_charged = int(usage.get("ops_charged", 1) or 1)
    try:
        guard.record_actual(ops_charged, label="edit instruction", raw_usage=usage)
    except BudgetExceededError as exc:
        # Spend already happened server-side; the run is marked over-budget in
        # the final report rather than pretending it can be undone here.
        print(f"warning: {exc}", file=sys.stderr)

    # Stage 4: export
    print(f"\n[4/5] Exporting edited document to {args.output} ...")
    try:
        client.export_document(session_id, args.output, fmt="docx")
    except SuperDocsAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    # Stage 5: structural validation (free, local, no API key needed for this part)
    print(f"\n[5/5] Running structural fidelity validation ...")
    engine = ValidationEngine()
    validation_run = engine.run(args.original, args.output)
    report = build_report(validation_run, cost=guard.finalize())
    _write_report(report, args.text_report, args.json_report, args.markdown_report)

    return 0 if report.overall_status == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="superdocs-fidelity",
        description="Round-trip fidelity harness with structural assertions for SuperDocs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Compare two .docx files structurally. No API key required.",
    )
    validate_parser.add_argument("original", help="Path to the original .docx")
    validate_parser.add_argument("edited", help="Path to the edited/exported .docx")
    _add_report_output_args(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser(
        "run",
        help="Full round trip against the live SuperDocs API: upload, edit, approve, export, validate.",
    )
    run_parser.add_argument("original", help="Path to the original .docx to upload")
    run_parser.add_argument("--instruction", required=True, help="Edit instruction to send to SuperDocs")
    run_parser.add_argument("--output", default="edited.docx", help="Where to save the exported .docx")
    run_parser.add_argument("--session-id", default=None, help="Reuse a specific session id")
    run_parser.add_argument(
        "--cost-cap", type=int, required=True,
        help="Maximum operations this run may spend. Required -- there is no silent default for a live run.",
    )
    run_parser.add_argument(
        "--small-sample", action="store_true",
        help="Refuse to run if the document exceeds the small-sample chunk limit. "
             "Use this while proving the harness out before pointing it at large documents.",
    )
    _add_report_output_args(run_parser)
    run_parser.set_defaults(func=cmd_run)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
