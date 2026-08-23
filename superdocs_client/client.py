"""
Minimal SuperDocs REST client covering the four-call contract named in the
assignment: upload, chat (edit instruction), approve, export.

Built strictly against the documented API at https://docs.superdocs.app
(fetched live while building this harness; endpoint shapes below match the
published OpenAPI schema and the official Python examples). No endpoint here
is invented. Everything else on the SuperDocs surface (templates, cross-session
memory, attachments, multi-document sessions, ...) is out of scope on purpose --
the assignment says build against the four first, everything else is optional
depth, and this harness is a validation suite, not a SuperDocs client library.

Two important, easy-to-miss behaviors called out by SuperDocs' own docs, and
handled here:

  1. Proposed-change content in a job's `metadata.pending_changes` can arrive
     with fields that are JSON-encoded strings needing a second parse in some
     SuperDocs response shapes. `_maybe_parse_json` centralizes that so it
     isn't reimplemented (or missed) in three different call sites.
  2. Long-running operations legitimately take from ~30 seconds to several
     minutes with no visible progress. `poll_job` treats "still in_progress"
     as normal, not as failure, and only raises after `max_poll_seconds`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from config.settings import Settings
from .exceptions import SuperDocsAPIError, JobFailedError, JobTimeoutError


def _maybe_parse_json(value: Any) -> Any:
    """Some SuperDocs fields (notably proposed-change content) arrive as a
    JSON-encoded string and need a second parse. Final response objects are
    already parsed. This helper is idempotent and safe to call on anything."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "{[":
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                return value
    return value


@dataclass
class UploadResult:
    session_id: str
    filename: str
    chunks_count: int
    raw: dict


@dataclass
class JobResult:
    job_id: str
    status: str
    progress: int
    raw: dict

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")

    @property
    def is_awaiting_approval(self) -> bool:
        return self.status == "awaiting_approval"

    @property
    def pending_changes(self) -> list[dict]:
        metadata = self.raw.get("metadata") or {}
        changes = metadata.get("pending_changes") or []
        return [
            {**c, "new_html": _maybe_parse_json(c.get("new_html")),
             "old_html": _maybe_parse_json(c.get("old_html"))}
            for c in changes
        ]

    @property
    def usage(self) -> dict:
        result = self.raw.get("result") or {}
        return result.get("usage") or {}


class SuperDocsClient:
    """Thin, explicit wrapper around the documented SuperDocs REST endpoints."""

    def __init__(self, settings: Settings, session: Optional[requests.Session] = None):
        self._settings = settings
        self._api_key = settings.require_api_key()
        self._base_url = settings.base_url
        self._timeout = settings.request_timeout_seconds
        self._session = session or requests.Session()

    # -- internal ----------------------------------------------------------

    def _headers(self, json_body: bool = True) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self._base_url}{path}"
        response = self._session.request(method, url, timeout=self._timeout, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise SuperDocsAPIError(response.status_code, str(detail), path)
        return response

    # -- call 1: upload ------------------------------------------------------

    def upload_document(self, file_path: str, session_id: str) -> UploadResult:
        """
        POST /v1/documents/upload (multipart) -- loads a .docx/.pdf/.html/.md/.rtf
        file as the session's active editable document. Returns chunk metadata
        used both for the small-sample check and for budget estimation.
        """
        with open(file_path, "rb") as fh:
            response = self._request(
                "POST",
                "/v1/documents/upload",
                headers=self._headers(json_body=False),
                files={"file": (file_path.split("/")[-1], fh)},
                data={"session_id": session_id},
            )
        data = response.json()
        return UploadResult(
            session_id=session_id,
            filename=data.get("filename", file_path),
            chunks_count=int(data.get("chunks_count", 0) or 0),
            raw=data,
        )

    # -- call 2: chat / edit instruction -------------------------------------

    def start_edit(
        self,
        session_id: str,
        message: str,
        approval_mode: str = "ask_every_time",
        response_mode: str = "compact",
    ) -> str:
        """
        POST /v1/chat/async -- sends the edit instruction. Async + HITL by
        default (approval_mode='ask_every_time') so every proposed change goes
        through an explicit human/CI approval step before touching the
        document, matching the assignment's "approve proposed changes" stage.

        Returns the job_id to poll.
        """
        body = {
            "message": message,
            "session_id": session_id,
            "approval_mode": approval_mode,
            "response_mode": response_mode,
            "model_tier": self._settings.model_tier,
            "thinking_depth": self._settings.thinking_depth,
        }
        response = self._request("POST", "/v1/chat/async", headers=self._headers(), json=body)
        return response.json()["job_id"]

    def get_job(self, job_id: str) -> JobResult:
        """GET /v1/jobs/{job_id} -- current status, pending changes, usage."""
        response = self._request("GET", f"/v1/jobs/{job_id}", headers=self._headers())
        data = response.json()
        return JobResult(
            job_id=data["job_id"],
            status=data["status"],
            progress=int(data.get("progress", 0) or 0),
            raw=data,
        )

    def poll_job(
        self,
        job_id: str,
        stop_statuses: tuple[str, ...] = ("completed", "failed", "cancelled", "awaiting_approval"),
    ) -> JobResult:
        """
        Poll until the job reaches one of `stop_statuses`.

        Large documents or deep model settings can legitimately take from
        thirty seconds to several minutes with no visible progress -- that is
        "still processing," not a crash. This loop only raises JobTimeoutError
        after settings.max_poll_seconds, and never raises merely for slowness.
        """
        deadline = time.monotonic() + self._settings.max_poll_seconds
        while True:
            job = self.get_job(job_id)
            if job.status in stop_statuses:
                if job.status == "failed":
                    raise JobFailedError(job_id, job.raw.get("error"))
                return job
            if time.monotonic() >= deadline:
                raise JobTimeoutError(job_id, self._settings.max_poll_seconds)
            time.sleep(self._settings.poll_interval_seconds)

    # -- call 3: approve ------------------------------------------------------

    def approve_all_changes(self, session_id: str, job_id: str, changes: list[dict]) -> dict:
        """
        POST /v1/chat/{session_id}/approve -- approves every pending change in
        one batch call. For a validation harness the interesting behavior is
        structural fidelity, not editorial judgment, so batch-approve is the
        default path; deny-with-feedback is exposed for callers who want it.
        """
        body = {
            "job_id": job_id,
            "approved": True,
            "changes": [{"change_id": c["change_id"], "approved": True} for c in changes],
        }
        response = self._request(
            "POST", f"/v1/chat/{session_id}/approve", headers=self._headers(), json=body
        )
        return response.json()

    def deny_change(self, session_id: str, job_id: str, change_id: str, feedback: str) -> dict:
        body = {"job_id": job_id, "change_id": change_id, "approved": False, "feedback": feedback}
        response = self._request(
            "POST", f"/v1/chat/{session_id}/approve", headers=self._headers(), json=body
        )
        return response.json()

    # -- call 4: export ------------------------------------------------------

    def export_document(self, session_id: str, output_path: str, fmt: str = "docx") -> str:
        """
        POST /v1/documents/export -- exports the session's current document
        state. Per SuperDocs docs this round-trips through their native docx
        renderer and never counts as a billable operation.
        """
        body = {"session_id": session_id, "format": fmt}
        response = self._request("POST", "/v1/documents/export", headers=self._headers(), json=body)
        with open(output_path, "wb") as fh:
            fh.write(response.content)
        return output_path

    # -- account status (used by the budget guard for a sanity check) -------

    def verify_key(self) -> bool:
        """Cheapest documented way to confirm a key works: GET /v1/sessions."""
        response = self._session.get(
            f"{self._base_url}/v1/sessions", headers=self._headers(json_body=False), timeout=self._timeout
        )
        return response.status_code == 200
