"""Utilities for handling sensitive values safely."""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping

SENSITIVE_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPEN_AI_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GCP_SECRET",
    "AZURE_CLIENT_SECRET",
)


def get_required_secret(*keys: str, env: Mapping[str, str] | None = None) -> str:
    """Return the first populated secret from keys or raise a RuntimeError."""
    if not keys:
        raise ValueError("At least one secret key must be provided.")
    source = env if env is not None else os.environ
    for key in keys:
        value = source.get(key)
        if value:
            return value
    joined = ", ".join(keys)
    raise RuntimeError(f"Missing required secret(s): {joined}")


def redact_text(text: str, env: Mapping[str, str] | None = None) -> str:
    """Redact sensitive values from the provided text."""
    source = env if env is not None else os.environ
    redacted = text
    for key in SENSITIVE_ENV_KEYS:
        value = source.get(key)
        if value:
            redacted = redacted.replace(value, "***REDACTED***")
    return redacted


def redact_dict(payload: Mapping[str, Any], env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a redacted copy of a mapping, masking sensitive values."""
    source = env if env is not None else os.environ

    def redact_value(value: Any) -> Any:
        if isinstance(value, str):
            return redact_text(value, source)
        if isinstance(value, Mapping):
            return {k: redact_value(v) for k, v in value.items()}
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            return [redact_value(item) for item in value]
        return value

    return {
        key: "***REDACTED***" if key in SENSITIVE_ENV_KEYS else redact_value(value)
        for key, value in payload.items()
    }
