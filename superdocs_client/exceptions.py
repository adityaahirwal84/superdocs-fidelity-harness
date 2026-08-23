"""Exceptions raised by the SuperDocs client.

Every exception carries enough context (status code, response body, job id)
for a caller to name the cause, not just the fact that something failed.
"""

from __future__ import annotations


class SuperDocsAPIError(RuntimeError):
    """Raised when the SuperDocs REST API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str, endpoint: str):
        self.status_code = status_code
        self.detail = detail
        self.endpoint = endpoint
        super().__init__(
            f"SuperDocs API error {status_code} calling {endpoint}: {detail}"
        )


class JobFailedError(RuntimeError):
    """Raised when an async job (chat_async) reaches status='failed'."""

    def __init__(self, job_id: str, error: str | None):
        self.job_id = job_id
        self.error = error
        super().__init__(f"SuperDocs job {job_id} failed: {error or 'no error detail returned'}")


class JobTimeoutError(RuntimeError):
    """
    Raised when a job does not reach a terminal state within max_poll_seconds.

    This is deliberately NOT treated as a failure by callers: per the SuperDocs
    docs, large-document operations can legitimately take from thirty seconds
    to several minutes with no visible progress. The correct read is "still
    processing," so this exception exists only to stop an unbounded poll loop
    and hand control back to a human/CI system, not to declare the edit dead.
    """

    def __init__(self, job_id: str, waited_seconds: float):
        self.job_id = job_id
        self.waited_seconds = waited_seconds
        super().__init__(
            f"SuperDocs job {job_id} did not complete within {waited_seconds:.0f}s. "
            "This does not necessarily mean it failed -- large documents can take "
            "several minutes. Re-poll with get_job(job_id) before assuming failure."
        )
