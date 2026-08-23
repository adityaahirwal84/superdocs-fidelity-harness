"""
Configuration loading for the Round-trip Fidelity Harness.

Every value that could plausibly change between environments (API base URL,
API key, default cost cap, poll interval, etc.) is read from the environment
rather than hardcoded. Secrets are never hardcoded, never logged, and never
written to a report.

Values can be supplied via a `.env` file (see `.env.example`) or real
environment variables. Real environment variables always win over `.env`
so CI systems can override without editing files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_env_file(path: Path) -> dict:
    """Very small .env parser: KEY=VALUE per line, '#' comments, no quoting magic."""
    values: dict = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for a harness run."""

    api_key: str | None
    base_url: str
    request_timeout_seconds: int
    poll_interval_seconds: float
    max_poll_seconds: int
    default_cost_cap: int
    model_tier: str
    thinking_depth: str
    small_sample_chunk_limit: int

    def require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(
                "SUPERDOCS_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or export SUPERDOCS_API_KEY in your shell. The `validate` subcommand "
                "does not need a key; only `run` (the live round trip) does."
            )
        return self.api_key


def load_settings(env_file: str | os.PathLike = ".env") -> Settings:
    """
    Load settings from (in increasing precedence order):
      1. Built-in defaults
      2. A .env file, if present
      3. Real process environment variables
    """
    file_values = _parse_env_file(Path(env_file))

    def get(name: str, default: str) -> str:
        if name in os.environ:
            return os.environ[name]
        if name in file_values:
            return file_values[name]
        return default

    return Settings(
        api_key=get("SUPERDOCS_API_KEY", "") or None,
        base_url=get("SUPERDOCS_BASE_URL", "https://api.superdocs.app").rstrip("/"),
        request_timeout_seconds=int(get("SUPERDOCS_REQUEST_TIMEOUT_SECONDS", "60")),
        poll_interval_seconds=float(get("SUPERDOCS_POLL_INTERVAL_SECONDS", "2")),
        max_poll_seconds=int(get("SUPERDOCS_MAX_POLL_SECONDS", "1800")),  # 30 min cap, matches API
        default_cost_cap=int(get("SUPERDOCS_DEFAULT_COST_CAP", "5")),
        model_tier=get("SUPERDOCS_MODEL_TIER", "core"),
        thinking_depth=get("SUPERDOCS_THINKING_DEPTH", "balanced"),
        small_sample_chunk_limit=int(get("SUPERDOCS_SMALL_SAMPLE_CHUNK_LIMIT", "40")),
    )
