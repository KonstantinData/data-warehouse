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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


# -----------------------------
# Helpers
# -----------------------------

def utc_now() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)

def iso_utc(dt: datetime) -> str:
    """ISO-8601 with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def safe_stat_utc(path: str) -> Dict[str, Any]:
    st = os.stat(path)
    mtime_utc = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    return {
        "file_size_bytes": st.st_size,
        "file_mtime_utc": iso_utc(mtime_utc),
    }

def write_yaml(data: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def write_html_report(context: Dict[str, Any], path: str) -> None:
    from jinja2 import Template
    template = Template(HTML_REPORT_TEMPLATE)
    html = template.render(**context)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

def read_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"files": {}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"files": {}}

def parse_args() -> argparse.Namespace:
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


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    args = parse_args()
    raw_crm = args.raw_crm
    raw_erp = args.raw_erp
    bronze_root = args.bronze_root
    crm_files = list_source_files(raw_crm, args.crm_file_glob, args.crm_file_exclude)
    erp_files = list_source_files(raw_erp, args.erp_file_glob, args.erp_file_exclude)
    state_dir = os.path.join(bronze_root, "_state")
    state_path = os.path.join(state_dir, "last_ingested.yaml")

    start_dt = utc_now()
    run_id = args.run_id or f"{start_dt.strftime('%Y%m%d_%H%M%S')}_#{str(uuid.uuid4())[:8]}"

    elt_dir = os.path.join(bronze_root, run_id)
    data_dir = os.path.join(elt_dir, "data")
    report_dir = os.path.join(elt_dir, "reports")

    ensure_dir(data_dir)
    ensure_dir(report_dir)
    ensure_dir(state_dir)

    log_path = os.path.join(data_dir, "run_log.txt")

    def log(msg: str) -> None:
        line = f"{iso_utc(utc_now())} | {msg}"
        print(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log(f"RUN_START run_id={run_id}")
    log(
        "CONFIG "
        f"RAW_CRM={raw_crm} RAW_ERP={raw_erp} BRONZE_ROOT={bronze_root} "
        f"CRM_FILE_GLOB={args.crm_file_glob} CRM_FILE_EXCLUDE={args.crm_file_exclude} "
        f"ERP_FILE_GLOB={args.erp_file_glob} ERP_FILE_EXCLUDE={args.erp_file_exclude}"
    )
    log(f"DISCOVERED CRM_FILES={crm_files}")
    log(f"DISCOVERED ERP_FILES={erp_files}")

    metadata: Dict[str, Any] = {
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
            "crm_root": raw_crm,
            "erp_root": raw_erp,
            "crm_file_glob": args.crm_file_glob,
            "crm_file_exclude": args.crm_file_exclude,
            "erp_file_glob": args.erp_file_glob,
            "erp_file_exclude": args.erp_file_exclude,
            "crm_files": crm_files,
            "erp_files": erp_files,
        },
        "tables": {},  # filename -> metadata
        "summary": {},
    }

    results: List[Dict[str, Any]] = []
    state = read_state(state_path)
    state_files = state.get("files", {})
    next_state_files: Dict[str, Any] = {}

    def process_file(src_root: str, filename: str, source_system: str) -> None:
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

            # File stats + checksum (audit/repro)
            st = safe_stat_utc(src_path)
            rec.update(st)
            rec["sha256"] = sha256_file(src_path)

            prev_state = state_files.get(src_path)
            is_changed = not prev_state or (
                prev_state.get("file_mtime_utc") != rec["file_mtime_utc"]
                or prev_state.get("sha256") != rec["sha256"]
            )
            rec["is_changed"] = is_changed
            if not is_changed:
                rec["status"] = "SKIPPED"
                rec["skip_reason"] = "unchanged"
                log(f"SKIPPED file={filename} source={source_system} reason=unchanged")
            else:
                # Read to profile (rows/schema/dtypes)
                t0 = time.perf_counter()
                df = pd.read_csv(src_path)
                rec["read_duration_s"] = time.perf_counter() - t0

                rec["rows"] = int(len(df))
                rec["schema"] = list(df.columns)
                rec["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}

                # Copy raw file byte-for-byte into bronze artifacts
                t1 = time.perf_counter()
                shutil.copy2(src_path, dest_path)
                rec["copy_duration_s"] = time.perf_counter() - t1

                rec["status"] = "SUCCESS"
                log(
                    f"SUCCESS file={filename} source={source_system} "
                    f"rows={rec['rows']} read={rec['read_duration_s']:.3f}s copy={rec['copy_duration_s']:.3f}s"
                )

        except Exception as e:
            rec["error_type"] = type(e).__name__
            rec["error_message"] = str(e)
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

        # Persist per-table metadata
        metadata["tables"][filename] = {
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

    # Process CRM
    log("BEGIN CRM SOURCE LOAD")
    for f in crm_files:
        process_file(raw_crm, f, "CRM")

    # Process ERP
    log("BEGIN ERP SOURCE LOAD")
    for f in erp_files:
        process_file(raw_erp, f, "ERP")

    # Summary
    ok = sum(1 for r in results if r["status"] == "SUCCESS")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    failed = len(results) - ok - skipped

    end_dt = utc_now()
    metadata["run"]["ended_utc"] = iso_utc(end_dt)
    metadata["run"]["duration_s"] = (end_dt - start_dt).total_seconds()

    has_new_data = any(
        r.get("is_changed") and r["status"] == "SUCCESS"
        for r in results
    )

    metadata["summary"] = {
        "files_total": len(results),
        "files_success": ok,
        "files_skipped": skipped,
        "files_failed": failed,
        "has_new_data": has_new_data,
    }

    # Write metadata.yaml
    write_yaml(metadata, os.path.join(data_dir, "metadata.yaml"))

    # Write HTML report
    report_ctx = {
        "run_id": run_id,
        "start_dt": iso_utc(start_dt),
        "end_dt": iso_utc(end_dt),
        "results": results,
    }
    write_html_report(report_ctx, os.path.join(report_dir, "elt_report.html"))

    if failed == 0:
        state_payload = {
            "updated_utc": iso_utc(end_dt),
            "files": next_state_files,
        }
        write_yaml(state_payload, state_path)

    log(f"RUN_END run_id={run_id} duration_s={metadata['run']['duration_s']:.3f} success={ok} failed={failed}")
    output_payload = {
        "run_id": run_id,
        "artifacts_dir": elt_dir,
        "has_new_data": has_new_data,
        "files_total": len(results),
        "files_success": ok,
        "files_skipped": skipped,
        "files_failed": failed,
    }
    print(json.dumps(output_payload))


if __name__ == "__main__":
    main()
