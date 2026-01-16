"""
load_1_bronze_layer.py

DESCRIPTION
Performs a Python-paced ELT of CRM and ERP raw CSV sources into a versioned bronze layer.

Each run produces:
  artifacts/bronze/<YYYYMMDD_HHMMSS>_#<random>/
    data/
      *.csv  (raw, byte-for-byte copies)
      metadata.yaml
      run_log.txt
    reports/
      elt_report.html

Key properties:
- Uses UTC timestamps (timezone-aware) for documentation
- File name per run: YYYYMMDD_HHMMSS_#+random (8 chars)
- Persists richer metadata (audit + reproducibility + status/errors)
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml

# -----------------------------
# Config
# -----------------------------

# Paths (relative to project root)
DEFAULT_RAW_CRM = os.path.join("raw", "source_crm")
DEFAULT_RAW_ERP = os.path.join("raw", "source_erp")

# Match your folder structure from the screenshot
DEFAULT_BRONZE_ROOT = os.path.join("artifacts", "bronze")

# Optional: allow overriding roots via env vars
DEFAULT_RAW_CRM = os.environ.get("RAW_CRM", DEFAULT_RAW_CRM)
DEFAULT_RAW_ERP = os.environ.get("RAW_ERP", DEFAULT_RAW_ERP)
DEFAULT_BRONZE_ROOT = os.environ.get("BRONZE_ROOT", DEFAULT_BRONZE_ROOT)


HTML_REPORT_TEMPLATE = """\
<html>
<head><title>Bronze ELT Report - {{ run_id }}</title></head>
<body>
<h1>Bronze ELT Report</h1>
<p>Run ID: {{ run_id }}</p>
<p>Run start (UTC): {{ start_dt }}</p>
<p>Run end (UTC): {{ end_dt }}</p>

<table border="1" cellpadding="6" cellspacing="0">
<tr>
  <th>file</th>
  <th>source</th>
  <th>status</th>
  <th>rows</th>
  <th>read(s)</th>
  <th>copy(s)</th>
  <th>size(bytes)</th>
  <th>mtime(UTC)</th>
  <th>sha256</th>
  <th>skip reason</th>
  <th>error</th>
</tr>
{% for r in results %}
<tr>
  <td>{{ r.file }}</td>
  <td>{{ r.source_system }}</td>
  <td>{{ r.status }}</td>
  <td>{{ r.rows }}</td>
  <td>{{ "%.3f"|format(r.read_duration_s or 0) }}</td>
  <td>{{ "%.3f"|format(r.copy_duration_s or 0) }}</td>
  <td>{{ r.file_size_bytes or "" }}</td>
  <td>{{ r.file_mtime_utc or "" }}</td>
  <td style="font-family: monospace;">{{ r.sha256 or "" }}</td>
  <td>{{ r.skip_reason or "" }}</td>
  <td>{{ r.error_message or "" }}</td>
</tr>
{% endfor %}
</table>

</body>
</html>
"""


@dataclass(frozen=True)
class BronzeRunConfig:
    """Configuration for a single bronze-layer load run.

    Attributes:
        raw_crm: Directory path containing CRM source CSVs.
        raw_erp: Directory path containing ERP source CSVs.
        bronze_root: Root directory for bronze artifacts.
        crm_file_glob: Glob pattern for CRM files to include.
        crm_file_exclude: Optional glob pattern for CRM files to exclude.
        erp_file_glob: Glob pattern for ERP files to include.
        erp_file_exclude: Optional glob pattern for ERP files to exclude.
        run_id: Optional run identifier. When omitted, a timestamp-based ID is generated.
    """

    raw_crm: str
    raw_erp: str
    bronze_root: str
    crm_file_glob: str
    crm_file_exclude: Optional[str]
    erp_file_glob: str
    erp_file_exclude: Optional[str]
    run_id: Optional[str] = None


@dataclass(frozen=True)
class BronzeRunPaths:
    """Materialized artifact paths for a bronze-layer run."""

    elt_dir: str
    data_dir: str
    report_dir: str
    state_dir: str
    state_path: str
    log_path: str


# -----------------------------
# Helpers
# -----------------------------

def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """Return ISO-8601 format with a Z suffix for UTC timestamps."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def ensure_dir(path: str) -> None:
    """Create a directory if it does not exist."""

    os.makedirs(path, exist_ok=True)


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 checksum of a file by streaming in chunks."""

    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def safe_stat_utc(path: str, stat_fn: Callable[[str], os.stat_result] = os.stat) -> Dict[str, Any]:
    """Return file size and mtime converted to UTC using a pluggable stat function."""

    st = stat_fn(path)
    mtime_utc = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    return {
        "file_size_bytes": st.st_size,
        "file_mtime_utc": iso_utc(mtime_utc),
    }


def write_yaml(data: Dict[str, Any], path: str) -> None:
    """Serialize a dictionary to a YAML file."""

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def write_html_report(context: Dict[str, Any], path: str) -> None:
    """Render and write the HTML report for the run."""

    from jinja2 import Template

    template = Template(HTML_REPORT_TEMPLATE)
    html = template.render(**context)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def read_state(path: str) -> Dict[str, Any]:
    """Load the persisted ingestion state from disk.

    Returns a dictionary containing a "files" mapping. Missing or empty files
    return a default structure to simplify downstream logic.
    """

    if not os.path.exists(path):
        return {"files": {}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"files": {}}


def write_state(path: str, payload: Dict[str, Any]) -> None:
    """Persist ingestion state to disk."""

    write_yaml(payload, path)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the bronze-layer load script."""

    parser = argparse.ArgumentParser(description="Load CRM/ERP raw CSVs into bronze layer.")
    parser.add_argument(
        "--run-id",
        default=os.environ.get("BRONZE_RUN_ID") or os.environ.get("RUN_ID"),
        help="Optional run identifier (defaults to BRONZE_RUN_ID or RUN_ID env vars).",
    )
    parser.add_argument("--raw-crm", default=DEFAULT_RAW_CRM, help="Path to CRM raw source directory.")
    parser.add_argument("--raw-erp", default=DEFAULT_RAW_ERP, help="Path to ERP raw source directory.")
    parser.add_argument("--bronze-root", default=DEFAULT_BRONZE_ROOT, help="Root path for bronze artifacts.")
    parser.add_argument(
        "--crm-file-glob",
        default=os.environ.get("CRM_FILE_GLOB", "*.csv"),
        help="Glob pattern for CRM files (default: *.csv).",
    )
    parser.add_argument(
        "--crm-file-exclude",
        default=os.environ.get("CRM_FILE_EXCLUDE"),
        help="Optional glob pattern to exclude CRM files.",
    )
    parser.add_argument(
        "--erp-file-glob",
        default=os.environ.get("ERP_FILE_GLOB", "*.csv"),
        help="Glob pattern for ERP files (default: *.csv).",
    )
    parser.add_argument(
        "--erp-file-exclude",
        default=os.environ.get("ERP_FILE_EXCLUDE"),
        help="Optional glob pattern to exclude ERP files.",
    )
    return parser.parse_args()


def list_source_files(root: str, include_glob: str, exclude_glob: Optional[str]) -> List[str]:
    """List files in the source directory filtered by include/exclude globs."""

    entries = []
    if not os.path.isdir(root):
        return entries
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        if include_glob and not fnmatch.fnmatch(name, include_glob):
            continue
        if exclude_glob and fnmatch.fnmatch(name, exclude_glob):
            continue
        entries.append(name)
    return sorted(entries)


def build_run_id(run_id: Optional[str], start_dt: datetime) -> str:
    """Return a deterministic run ID, generating one if none is supplied."""

    return run_id or f"{start_dt.strftime('%Y%m%d_%H%M%S')}_#{str(uuid.uuid4())[:8]}"


def build_run_paths(bronze_root: str, run_id: str) -> BronzeRunPaths:
    """Construct paths for a bronze-layer run."""

    elt_dir = os.path.join(bronze_root, run_id)
    data_dir = os.path.join(elt_dir, "data")
    report_dir = os.path.join(elt_dir, "reports")
    state_dir = os.path.join(bronze_root, "_state")
    state_path = os.path.join(state_dir, "last_ingested.yaml")
    log_path = os.path.join(data_dir, "run_log.txt")
    return BronzeRunPaths(
        elt_dir=elt_dir,
        data_dir=data_dir,
        report_dir=report_dir,
        state_dir=state_dir,
        state_path=state_path,
        log_path=log_path,
    )


def create_logger(log_path: str, now_fn: Callable[[], datetime] = utc_now) -> Callable[[str], None]:
    """Create a log function that writes to stdout and a run-local log file."""

    def log(msg: str) -> None:
        line = f"{iso_utc(now_fn())} | {msg}"
        print(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    return log


def build_metadata(
    config: BronzeRunConfig,
    run_id: str,
    start_dt: datetime,
    crm_files: Iterable[str],
    erp_files: Iterable[str],
) -> Dict[str, Any]:
    """Initialize metadata payload for the run."""

    return {
        "run": {
            "run_id": run_id,
            "layer": "bronze",
            "pipeline": "elt_bronze",
            "started_utc": iso_utc(start_dt),
        },
        "env": {
            "python": sys.version.replace("\n", " "),
            "pandas": getattr(pd, "__version__", "unknown"),
            "platform": platform.platform(),
        },
        "sources": {
            "crm_root": config.raw_crm,
            "erp_root": config.raw_erp,
            "crm_file_glob": config.crm_file_glob,
            "crm_file_exclude": config.crm_file_exclude,
            "erp_file_glob": config.erp_file_glob,
            "erp_file_exclude": config.erp_file_exclude,
            "crm_files": list(crm_files),
            "erp_files": list(erp_files),
        },
        "tables": {},
        "summary": {},
    }


def detect_changed(prev_state: Optional[Dict[str, Any]], current: Dict[str, Any]) -> bool:
    """Return True when the file differs from the last ingested state.

    We combine mtime and checksum to avoid false negatives:
    - `mtime` is cheap but can miss updates if timestamps are preserved.
    - `sha256` is slower but guarantees content detection.
    The two together provide a balance of performance and correctness.
    """

    if not prev_state:
        return True
    return (
        prev_state.get("file_mtime_utc") != current.get("file_mtime_utc")
        or prev_state.get("sha256") != current.get("sha256")
    )


def read_csv_with_retry(
    path: str,
    read_csv_fn: Callable[[str], pd.DataFrame],
    retries: int = 1,
    sleep_s: float = 0.2,
) -> pd.DataFrame:
    """Read a CSV with limited retries for transient I/O or parse errors."""

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return read_csv_fn(path)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(sleep_s)
    raise last_exc or RuntimeError("Failed to read CSV")


def copy_with_retry(
    src_path: str,
    dest_path: str,
    copy_fn: Callable[[str, str], str],
    retries: int = 1,
    sleep_s: float = 0.2,
) -> None:
    """Copy a file with limited retries for transient I/O errors."""

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            copy_fn(src_path, dest_path)
            return
        except OSError as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(sleep_s)
    raise last_exc or RuntimeError("Failed to copy file")


def process_file(
    src_root: str,
    filename: str,
    source_system: str,
    data_dir: str,
    state_files: Dict[str, Any],
    next_state_files: Dict[str, Any],
    metadata_tables: Dict[str, Any],
    results: List[Dict[str, Any]],
    log: Callable[[str], None],
    read_csv_fn: Callable[[str], pd.DataFrame] = pd.read_csv,
    copy_fn: Callable[[str, str], str] = shutil.copy2,
    stat_fn: Callable[[str], os.stat_result] = os.stat,
    sha_fn: Callable[[str], str] = sha256_file,
) -> None:
    """Process a single file, recording audit metadata and load status.

    Args:
        src_root: Source directory for the file.
        filename: File name within the source directory.
        source_system: Logical source name (e.g., CRM or ERP).
        data_dir: Destination directory inside the run's artifact tree.
        state_files: Previously stored state mapping keyed by source path.
        next_state_files: Mutable mapping to populate with new state.
        metadata_tables: Mutable metadata mapping keyed by filename.
        results: Mutable list of per-file result dictionaries.
        log: Logging callable for run-level messages.
        read_csv_fn: Dependency-injected CSV reader for testability.
        copy_fn: Dependency-injected copy function for testability.
        stat_fn: Dependency-injected os.stat function for testability.
        sha_fn: Dependency-injected SHA-256 calculator for testability.

    Raises:
        FileNotFoundError: If the source file is missing.
        OSError: If file operations fail after retries.
        pd.errors.ParserError: If CSV parsing fails after retries.
    """

    src_path = os.path.join(src_root, filename)
    dest_path = os.path.join(data_dir, filename)

    rec: Dict[str, Any] = {
        "file": filename,
        "source_system": source_system,
        "source_path": src_path,
        "status": "FAILED",
        "skip_reason": None,
        "rows": 0,
        "schema": [],
        "dtypes": {},
        "read_duration_s": None,
        "copy_duration_s": None,
        "file_size_bytes": None,
        "file_mtime_utc": None,
        "sha256": None,
        "error_type": None,
        "error_message": None,
    }

    try:
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source file not found: {src_path}")

        st = safe_stat_utc(src_path, stat_fn=stat_fn)
        rec.update(st)
        rec["sha256"] = sha_fn(src_path)

        prev_state = state_files.get(src_path)
        is_changed = detect_changed(prev_state, rec)
        rec["is_changed"] = is_changed

        if not is_changed:
            rec["status"] = "SKIPPED"
            rec["skip_reason"] = "unchanged"
            log(f"SKIPPED file={filename} source={source_system} reason=unchanged")
        else:
            t0 = time.perf_counter()
            df = read_csv_with_retry(src_path, read_csv_fn=read_csv_fn)
            rec["read_duration_s"] = time.perf_counter() - t0

            rec["rows"] = int(len(df))
            rec["schema"] = list(df.columns)
            rec["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}

            t1 = time.perf_counter()
            copy_with_retry(src_path, dest_path, copy_fn=copy_fn)
            rec["copy_duration_s"] = time.perf_counter() - t1

            rec["status"] = "SUCCESS"
            log(
                f"SUCCESS file={filename} source={source_system} "
                f"rows={rec['rows']} read={rec['read_duration_s']:.3f}s "
                f"copy={rec['copy_duration_s']:.3f}s"
            )

    except Exception as exc:
        rec["error_type"] = type(exc).__name__
        rec["error_message"] = str(exc)
        rec["is_changed"] = True
        log(f"ERROR file={filename} source={source_system} {rec['error_type']}: {rec['error_message']}")
        log(traceback.format_exc())
    else:
        if rec["status"] in {"SUCCESS", "SKIPPED"}:
            next_state_files[src_path] = {
                "source_system": source_system,
                "file_mtime_utc": rec["file_mtime_utc"],
                "sha256": rec["sha256"],
                "file_size_bytes": rec["file_size_bytes"],
            }

    metadata_tables[filename] = {
        "source_system": rec["source_system"],
        "source_path": rec["source_path"],
        "status": rec["status"],
        "skip_reason": rec["skip_reason"],
        "rows": rec["rows"],
        "schema": rec["schema"],
        "dtypes": rec["dtypes"],
        "read_duration_s": rec["read_duration_s"],
        "copy_duration_s": rec["copy_duration_s"],
        "file_size_bytes": rec["file_size_bytes"],
        "file_mtime_utc": rec["file_mtime_utc"],
        "sha256": rec["sha256"],
        "error_type": rec["error_type"],
        "error_message": rec["error_message"],
        "is_changed": rec.get("is_changed"),
    }

    results.append(rec)


def summarize_results(results: Iterable[Dict[str, Any]]) -> Tuple[int, int, int, bool]:
    """Summarize the results list into success/skip/failure counts."""

    results_list = list(results)
    ok = sum(1 for r in results_list if r["status"] == "SUCCESS")
    skipped = sum(1 for r in results_list if r["status"] == "SKIPPED")
    failed = len(results_list) - ok - skipped
    has_new_data = any(r.get("is_changed") and r["status"] == "SUCCESS" for r in results_list)
    return ok, skipped, failed, has_new_data


# -----------------------------
# Main
# -----------------------------

def run_bronze_load(
    config: BronzeRunConfig,
    now_fn: Callable[[], datetime] = utc_now,
    read_csv_fn: Callable[[str], pd.DataFrame] = pd.read_csv,
    copy_fn: Callable[[str, str], str] = shutil.copy2,
    stat_fn: Callable[[str], os.stat_result] = os.stat,
    sha_fn: Callable[[str], str] = sha256_file,
) -> Dict[str, Any]:
    """Execute a bronze-layer load using the provided configuration.

    Returns:
        A JSON-serializable payload summarizing the run.
    """

    crm_files = list_source_files(config.raw_crm, config.crm_file_glob, config.crm_file_exclude)
    erp_files = list_source_files(config.raw_erp, config.erp_file_glob, config.erp_file_exclude)

    start_dt = now_fn()
    run_id = build_run_id(config.run_id, start_dt)
    paths = build_run_paths(config.bronze_root, run_id)

    ensure_dir(paths.data_dir)
    ensure_dir(paths.report_dir)
    ensure_dir(paths.state_dir)

    log = create_logger(paths.log_path, now_fn=now_fn)
    log(f"RUN_START run_id={run_id}")
    log(
        "CONFIG "
        f"RAW_CRM={config.raw_crm} RAW_ERP={config.raw_erp} BRONZE_ROOT={config.bronze_root} "
        f"CRM_FILE_GLOB={config.crm_file_glob} CRM_FILE_EXCLUDE={config.crm_file_exclude} "
        f"ERP_FILE_GLOB={config.erp_file_glob} ERP_FILE_EXCLUDE={config.erp_file_exclude}"
    )
    log(f"DISCOVERED CRM_FILES={crm_files}")
    log(f"DISCOVERED ERP_FILES={erp_files}")

    metadata = build_metadata(config, run_id, start_dt, crm_files, erp_files)
    results: List[Dict[str, Any]] = []
    state = read_state(paths.state_path)
    state_files = state.get("files", {})
    next_state_files: Dict[str, Any] = {}

    log("BEGIN CRM SOURCE LOAD")
    for filename in crm_files:
        process_file(
            config.raw_crm,
            filename,
            "CRM",
            paths.data_dir,
            state_files,
            next_state_files,
            metadata["tables"],
            results,
            log,
            read_csv_fn=read_csv_fn,
            copy_fn=copy_fn,
            stat_fn=stat_fn,
            sha_fn=sha_fn,
        )

    log("BEGIN ERP SOURCE LOAD")
    for filename in erp_files:
        process_file(
            config.raw_erp,
            filename,
            "ERP",
            paths.data_dir,
            state_files,
            next_state_files,
            metadata["tables"],
            results,
            log,
            read_csv_fn=read_csv_fn,
            copy_fn=copy_fn,
            stat_fn=stat_fn,
            sha_fn=sha_fn,
        )

    ok, skipped, failed, has_new_data = summarize_results(results)

    end_dt = now_fn()
    metadata["run"]["ended_utc"] = iso_utc(end_dt)
    metadata["run"]["duration_s"] = (end_dt - start_dt).total_seconds()
    metadata["summary"] = {
        "files_total": len(results),
        "files_success": ok,
        "files_skipped": skipped,
        "files_failed": failed,
        "has_new_data": has_new_data,
    }

    write_yaml(metadata, os.path.join(paths.data_dir, "metadata.yaml"))

    report_ctx = {
        "run_id": run_id,
        "start_dt": iso_utc(start_dt),
        "end_dt": iso_utc(end_dt),
        "results": results,
    }
    write_html_report(report_ctx, os.path.join(paths.report_dir, "elt_report.html"))

    if failed == 0:
        state_payload = {
            "updated_utc": iso_utc(end_dt),
            "files": next_state_files,
        }
        write_state(paths.state_path, state_payload)

    log(
        f"RUN_END run_id={run_id} duration_s={metadata['run']['duration_s']:.3f} "
        f"success={ok} failed={failed}"
    )

    return {
        "run_id": run_id,
        "artifacts_dir": paths.elt_dir,
        "has_new_data": has_new_data,
        "files_total": len(results),
        "files_success": ok,
        "files_skipped": skipped,
        "files_failed": failed,
    }


def main() -> None:
    """CLI entrypoint for the bronze-layer loader."""

    args = parse_args()
    config = BronzeRunConfig(
        raw_crm=args.raw_crm,
        raw_erp=args.raw_erp,
        bronze_root=args.bronze_root,
        crm_file_glob=args.crm_file_glob,
        crm_file_exclude=args.crm_file_exclude,
        erp_file_glob=args.erp_file_glob,
        erp_file_exclude=args.erp_file_exclude,
        run_id=args.run_id,
    )
    output_payload = run_bronze_load(config)
    print(json.dumps(output_payload))


if __name__ == "__main__":
    main()
