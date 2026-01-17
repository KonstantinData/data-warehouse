"""
load_summary_report.py

Aggregate pipeline summary across Bronze/Silver/Gold steps.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml

from src.utils.atomic_io import atomic_write_text
LOGGER = logging.getLogger(__name__)

ARTIFACTS_DIR = "artifacts"
REPORTS_DIR = "reports"
DATA_DIR = "data"
METADATA_FILE = "metadata.yaml"
SUMMARY_JSON = "summary_report.json"
SUMMARY_MD = "summary_report.md"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

DQ_KEYS = ("dq_summary", "dq", "data_quality")
SUMMARY_KEY = "summary"
RUN_KEY = "run"
TABLES_KEY = "tables"
OUTPUTS_KEY = "outputs"

def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """Return a UTC ISO-8601 string with a trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def find_repo_root(start: Path) -> Path:
    """Locate the repository root based on expected directories."""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "src").exists() and (cur / ARTIFACTS_DIR).exists():
            return cur
        cur = cur.parent
    return start.resolve()


def read_yaml(path: Path) -> Dict[str, Any]:
    """Read a YAML file safely, returning an empty dict on failure."""
    if not path.exists():
        LOGGER.warning("Metadata file missing", extra={"path": str(path)})
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        LOGGER.error("Failed to read metadata file", extra={"path": str(path), "error": str(exc)})
        return {}
    if not isinstance(payload, dict):
        LOGGER.error("Metadata payload is not a mapping", extra={"path": str(path), "type": type(payload).__name__})
        return {}
    return payload


def write_json(payload: Dict[str, Any], path: Path) -> None:
    """Write JSON to disk with exception handling."""
    try:
        serialized = json.dumps(payload, indent=2)
        atomic_write_text(serialized, path)
    except OSError as exc:
        LOGGER.error("Failed to write JSON report", extra={"path": str(path), "error": str(exc)})
        raise


def validate_run_id(run_id: str) -> None:
    """Validate run_id to prevent path traversal or unexpected input."""
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(f"Invalid run_id format: {run_id!r}")


def validate_metadata_schema(metadata: Dict[str, Any], path: Path) -> List[str]:
    """Validate that metadata contains expected top-level structures."""
    errors: List[str] = []
    if SUMMARY_KEY in metadata and not isinstance(metadata.get(SUMMARY_KEY), dict):
        errors.append(f"{SUMMARY_KEY} must be a mapping")
    if RUN_KEY in metadata and not isinstance(metadata.get(RUN_KEY), dict):
        errors.append(f"{RUN_KEY} must be a mapping")
    if TABLES_KEY in metadata and not isinstance(metadata.get(TABLES_KEY), dict):
        errors.append(f"{TABLES_KEY} must be a mapping")
    if OUTPUTS_KEY in metadata and not isinstance(metadata.get(OUTPUTS_KEY), list):
        errors.append(f"{OUTPUTS_KEY} must be a list")
    if errors:
        LOGGER.warning(
            "Metadata schema validation warnings",
            extra={"path": str(path), "errors": errors},
        )
    return errors


def extract_dq_summary(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract data-quality summary from multiple possible keys."""
    for key in DQ_KEYS:
        if key in metadata and metadata[key]:
            return metadata[key]
    summary = metadata.get(SUMMARY_KEY, {})
    for key in DQ_KEYS:
        if key in summary and summary[key]:
            return summary[key]
    return None


def iter_token_usage(payload: Any) -> Iterable[Dict[str, Any]]:
    """Recursively yield token_usage dictionaries from nested metadata."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "token_usage" and isinstance(value, dict):
                yield value
            # Recursively inspect nested structures for token usage metadata.
            yield from iter_token_usage(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_token_usage(item)


def aggregate_token_usage(metadatas: Iterable[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    """Aggregate numeric token usage across metadata payloads."""
    totals: Dict[str, int] = {}
    for metadata in metadatas:
        for usage in iter_token_usage(metadata):
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    totals[key] = totals.get(key, 0) + int(value)
    return totals or None


def safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def summarize_bronze(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    """Summarize bronze layer metadata for a run."""
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / ARTIFACTS_DIR / "bronze" / run_id
    metadata_path = root / DATA_DIR / METADATA_FILE
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / REPORTS_DIR / "elt_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    schema_errors = validate_metadata_schema(metadata, metadata_path)
    summary = metadata.get(SUMMARY_KEY, {})
    tables = metadata.get(TABLES_KEY, {})
    row_total = sum(safe_int(table.get("rows")) for table in tables.values())
    row_success = sum(
        safe_int(table.get("rows"))
        for table in tables.values()
        if table.get("status") == "SUCCESS"
    )
    status = "success" if summary.get("files_failed", 0) == 0 else "failed"
    run_meta = metadata.get(RUN_KEY, {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / REPORTS_DIR / "elt_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "files_total": summary.get("files_total"),
            "files_success": summary.get("files_success"),
            "files_skipped": summary.get("files_skipped"),
            "files_failed": summary.get("files_failed"),
            "rows_total": row_total,
            "rows_success": row_success,
        },
        "schema_errors": schema_errors,
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_silver(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    """Summarize silver layer metadata for a run."""
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / ARTIFACTS_DIR / "silver" / run_id
    metadata_path = root / METADATA_FILE
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / REPORTS_DIR / "elt_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    schema_errors = validate_metadata_schema(metadata, metadata_path)
    summary = metadata.get(SUMMARY_KEY, {})
    tables = metadata.get(TABLES_KEY, {})
    rows_in = sum(safe_int(table.get("rows_in")) for table in tables.values())
    rows_out = sum(safe_int(table.get("rows_out")) for table in tables.values())
    status = "success" if summary.get("files_failed", 0) == 0 else "failed"
    run_meta = metadata.get(RUN_KEY, {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / REPORTS_DIR / "elt_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "files_total": summary.get("files_total"),
            "files_success": summary.get("files_success"),
            "files_failed": summary.get("files_failed"),
            "rows_in": rows_in,
            "rows_out": rows_out,
        },
        "schema_errors": schema_errors,
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_gold(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    """Summarize gold layer metadata for a run."""
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / ARTIFACTS_DIR / "gold" / "marts" / run_id
    metadata_path = root / METADATA_FILE
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / REPORTS_DIR / "gold_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    schema_errors = validate_metadata_schema(metadata, metadata_path)
    outputs = metadata.get(OUTPUTS_KEY, [])
    rows_total = sum(safe_int(output.get("rows")) for output in outputs)
    status = metadata.get(RUN_KEY, {}).get("status") or ("success" if not metadata.get("errors") else "partial")
    run_meta = metadata.get(RUN_KEY, {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / DATA_DIR).relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / REPORTS_DIR / "gold_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "outputs_total": len(outputs),
            "rows_total": rows_total,
        },
        "schema_errors": schema_errors,
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_steps(step_results: Sequence[Any]) -> Dict[str, Any]:
    """Summarize orchestrator steps into status/timing structures."""
    def to_dict(result: Any) -> Dict[str, Any]:
        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, dict):
            return result
        return {
            "name": getattr(result, "name", None),
            "status": getattr(result, "status", None),
            "started_utc": getattr(result, "started_utc", None),
            "ended_utc": getattr(result, "ended_utc", None),
            "duration_s": getattr(result, "duration_s", None),
            "return_code": getattr(result, "return_code", None),
            "details": getattr(result, "details", None),
            "log_path": getattr(result, "log_path", None),
        }

    return {
        "statuses": {getattr(result, "name", None): getattr(result, "status", None) for result in step_results},
        "timings_s": {getattr(result, "name", None): getattr(result, "duration_s", None) for result in step_results},
        "details": [to_dict(result) for result in step_results],
    }


def build_summary_payload(
    repo_root: Path,
    run_id: str,
    started_utc: str,
    ended_utc: str,
    step_results: Sequence[Any],
    bronze_run_id: Optional[str],
    silver_run_id: Optional[str],
    gold_run_id: Optional[str],
    no_new_data: bool,
) -> Dict[str, Any]:
    """Build the summary payload for JSON and Markdown reports."""
    bronze_summary = summarize_bronze(repo_root, bronze_run_id)
    silver_summary = summarize_silver(repo_root, silver_run_id)
    gold_summary = summarize_gold(repo_root, gold_run_id)

    duration_s = None
    try:
        duration_s = (
            datetime.fromisoformat(ended_utc.replace("Z", "+00:00"))
            - datetime.fromisoformat(started_utc.replace("Z", "+00:00"))
        ).total_seconds()
    except ValueError as exc:
        LOGGER.warning("Failed to parse timestamps", extra={"error": str(exc)})

    payload = {
        "run_id": run_id,
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "duration_s": duration_s,
        "no_new_data": no_new_data,
        "steps": summarize_steps(step_results),
        "layers": {
            "bronze": bronze_summary,
            "silver": silver_summary,
            "gold": gold_summary,
        },
        "token_usage": aggregate_token_usage(
            [
                bronze_summary.get("metadata", {}),
                silver_summary.get("metadata", {}),
                gold_summary.get("metadata", {}),
            ]
        ),
    }
    return payload


def write_summary_report(
    output_dir: Path,
    run_id: str,
    started_utc: str,
    ended_utc: str,
    step_results: Sequence[Any],
    bronze_run_id: Optional[str],
    silver_run_id: Optional[str],
    gold_run_id: Optional[str],
    no_new_data: bool,
) -> Dict[str, Any]:
    """Write summary JSON and Markdown reports to output_dir."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.error("Failed to create output directory", extra={"path": str(output_dir), "error": str(exc)})
        raise
    repo_root = find_repo_root(Path(__file__).resolve())
    payload = build_summary_payload(
        repo_root=repo_root,
        run_id=run_id,
        started_utc=started_utc,
        ended_utc=ended_utc,
        step_results=step_results,
        bronze_run_id=bronze_run_id,
        silver_run_id=silver_run_id,
        gold_run_id=gold_run_id,
        no_new_data=no_new_data,
    )

    json_path = output_dir / SUMMARY_JSON
    write_json(payload, json_path)

    md_lines = [
        f"# Orchestration Summary: {run_id}",
        "",
        f"- Started (UTC): {started_utc}",
        f"- Ended (UTC): {ended_utc}",
        f"- No new data: {no_new_data}",
        "",
        "## Step Statuses",
    ]
    for name, status in payload["steps"]["statuses"].items():
        duration = payload["steps"]["timings_s"].get(name)
        md_lines.append(f"- {name}: {status} ({duration:.3f}s)" if duration is not None else f"- {name}: {status}")

    md_lines.extend(["", "## Layer Rollups"])
    for layer_name, layer in payload["layers"].items():
        md_lines.extend(
            [
                f"### {layer_name.capitalize()}",
                f"- Run ID: {layer.get('run_id') or 'N/A'}",
                f"- Status: {layer.get('status')}",
                f"- Duration (s): {layer.get('timings', {}).get('duration_s')}",
                f"- Data dir: {layer.get('paths', {}).get('data_dir')}",
            ]
        )

    md_lines.extend(["", "## Token Usage", f"- {payload.get('token_usage') or 'N/A'}"])

    md_path = output_dir / SUMMARY_MD
    try:
        markdown = "\n".join(md_lines)
        atomic_write_text(markdown, md_path)
    except OSError as exc:
        LOGGER.error("Failed to write Markdown report", extra={"path": str(md_path), "error": str(exc)})
        raise

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a summary report for a run.")
    parser.add_argument("run_id", help="Orchestrator run ID")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    run_id = args.run_id
    try:
        validate_run_id(run_id)
    except ValueError as exc:
        LOGGER.error("Invalid run_id provided", extra={"run_id": run_id, "error": str(exc)})
        return 2
    output_dir = repo_root / ARTIFACTS_DIR / REPORTS_DIR / run_id

    now = utc_now()
    write_summary_report(
        output_dir=output_dir,
        run_id=run_id,
        started_utc=iso_utc(now),
        ended_utc=iso_utc(now),
        step_results=[],
        bronze_run_id=None,
        silver_run_id=None,
        gold_run_id=None,
        no_new_data=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
