"""Utilities for run_id validation and parsing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

RUN_ID_RE = re.compile(r"^([a-z0-9_]+)_#([0-9a-fA-F]{6,32})$")


def _guard_path_traversal(run_id: str) -> None:
    if Path(run_id).name != run_id:
        raise ValueError("Run id must not contain path separators.")
    if run_id in {".", ".."}:
        raise ValueError("Run id must not be '.' or '..'.")


def validate_run_id(run_id: str) -> None:
    """Validate a run_id against the strict pattern and path guard."""
    _guard_path_traversal(run_id)
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"Invalid run_id format: {run_id!r}")


def parse_run_id(run_id: str) -> Tuple[str, str]:
    """Return (prefix, suffix) for a validated run_id."""
    validate_run_id(run_id)
    match = RUN_ID_RE.match(run_id)
    if not match:
        raise ValueError(f"Invalid run_id format: {run_id!r}")
    return match.group(1), match.group(2)


def format_run_id(prefix: str, suffix: str) -> str:
    """Format a run_id from prefix and suffix with validation."""
    run_id = f"{prefix}_#{suffix}"
    validate_run_id(run_id)
    return run_id
