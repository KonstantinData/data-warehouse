"""
load_2_silver_layer.py

DESCRIPTION
Builds the Silver layer from the latest (or a specified) Bronze run, using the same
folder structure convention:

  artifacts/bronze/<bronze_run_id>/data/*.csv   -> input  (Raw Data / Bronze)
  artifacts/silver/<silver_run_id>/data/*.csv   -> output (Cleaned, Standardized Data / Silver)
  artifacts/silver/<silver_run_id>/reports/*    -> human report

Each Silver run produces:
  artifacts/silver/<timestamp>_#<bronze_suffix>/
    data/
      *.csv           (cleaned, standardized copies)
      metadata.yaml   (run + table metadata, lineage)
      run_log.txt     (technical log)
    reports/
      elt_report.html (HTML run report)

TRANSFORMATION SCOPE (Bronze -> Silver)
- Data Cleansing:
  - Trim whitespace in string columns
  - Convert empty strings to NA/NULL
- Data Standardization:
  - Normalize date columns to ISO-like "YYYY-MM-DD"
  - Normalize numeric columns (parse to numeric, safe coercion)
- Data Normalization (lightweight, no Gold/star schema):
  - Type harmonisation across related tables (e.g. IDs, dates)
- Derived Columns (optional, light):
  - Only simple, table-local attributes (no aggregations)
- Data Enrichment (within same grain):
  - Standardization of domain codes (e.g. gender codes)

IMPORTANT
- No Gold-layer semantics (no aggregations, no star schema, no business KPI tables).
- Output structure and grain per file remains 1:1 zur Bronze-Tabelle.
- Silver run_id = <UTC timestamp>_#<bronze_suffix>  (suffix copied from bronze run_id).
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from src.utils.atomic_io import atomic_to_csv, atomic_write_text

# ------------------------------------------------------------------
# Ensure "src" root is on sys.path so we can import agents package
# ------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
SRC_ROOT = CURRENT_FILE.parents[1]  # .../src

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Now we can import the report agent from src/agents/load_2_report_agent.py
try:
    from agents.load_2_silver_layer_draft_agent import run_report_agent
except Exception:
    # We will handle failures again in main(); this prevents import-time crash
    run_report_agent = None  # type: ignore



# -----------------------------
# Paths (relative to project root)
# -----------------------------
BRONZE_ROOT = os.path.join("artifacts", "bronze")
SILVER_ROOT = os.path.join("artifacts", "silver")

# Optional overrides (for tests / CI)
BRONZE_ROOT = os.environ.get("BRONZE_ROOT", BRONZE_ROOT)
SILVER_ROOT = os.environ.get("SILVER_ROOT", SILVER_ROOT)

# Run-id pattern: YYYYMMDD_HHMMSS_#<hex>
RUN_ID_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})_#(?P<suffix>[0-9a-fA-F]{6,32})$")


# -----------------------------
# Helpers: time, paths, hashing
# -----------------------------
def utc_now() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """ISO-8601 with 'Z' suffix."""
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


def find_latest_bronze_run_id() -> str:
    if not os.path.exists(BRONZE_ROOT):
        raise FileNotFoundError(f"Bronze root not found: {BRONZE_ROOT}")

    run_ids: List[str] = []
    for name in os.listdir(BRONZE_ROOT):
        if os.path.isdir(os.path.join(BRONZE_ROOT, name)) and RUN_ID_RE.match(name):
            run_ids.append(name)

    if not run_ids:
        raise FileNotFoundError(f"No bronze runs found in: {BRONZE_ROOT}")

    # Lexicographic sort works with YYYYMMDD_HHMMSS prefix
    return sorted(run_ids)[-1]


def make_silver_run_id_from_bronze(bronze_run_id: str, now: Optional[datetime] = None) -> str:
    m = RUN_ID_RE.match(bronze_run_id)
    if not m:
        raise ValueError(f"Invalid bronze run id format: {bronze_run_id}")

    suffix = m.group("suffix")
    now_dt = now or utc_now()
    return f"{now_dt.strftime('%Y%m%d_%H%M%S')}_#{suffix}"


# -----------------------------
# Silver Transformations
# -----------------------------
def base_silver_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal, safe Silver defaults applied to ALL tables:

    - Trim whitespace in string columns
    - Convert empty strings to NA
    """
    out = df.copy()

    for col in out.columns:
        if out[col].dtype == "object" or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].astype("string").str.strip()
            out[col] = out[col].replace({"": pd.NA})

    return out


def normalize_date_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Standardize a date-like column to ISO "YYYY-MM-DD" as string.
    """
    if col not in df.columns:
        return df

    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors="coerce")
    df[col] = df[col].dt.date.astype("string")
    df[col] = df[col].replace({"NaT": pd.NA})
    return df


def normalize_numeric_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Ensure a column is numeric (float) where possible.
    """
    if col not in df.columns:
        return df

    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def normalize_integer_id(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Ensure an ID column is stored as nullable integer (Int64) where possible.
    """
    if col not in df.columns:
        return df

    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def transform_cst_info(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for cst_info.csv:
    - Apply base cleaning
    - Normalize cst_id to Int64
    - Standardize cst_create_date to YYYY-MM-DD
    - Trim whitespace in cst_firstname, cst_lastname
    - Standardize missing values in all columns
    - Harmonize gender codes (M/F/NA)
    """
    df = base_silver_cleaning(df)
    if "cst_id" in df.columns:
        df = normalize_integer_id(df, "cst_id")
    if "cst_create_date" in df.columns:
        df = normalize_date_column(df, "cst_create_date")
    for col in ["cst_firstname", "cst_lastname", "cst_marital_status"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().replace({"": pd.NA})
    if "cst_gndr" in df.columns:
        tmp = df["cst_gndr"].astype("string").str.strip().str.upper()
        tmp = tmp.replace({
            "MALE": "M",
            "FEMALE": "F",
            "F": "F",
            "M": "M",
            "": pd.NA,
            "NAN": pd.NA,
            "NONE": pd.NA,
            "NULL": pd.NA,
        })
        df["cst_gndr"] = tmp.replace({"": pd.NA})
    # Standardize missing values in all columns (convert empty string or "nan"/"null" to pd.NA)
    for col in df.columns:
        df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    return df


def transform_CST_AZ12(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for CST_AZ12.csv:
    - Apply base cleaning
    - Parse BDATE as date
    - Standardize missing values in GEN
    - Trim whitespace in GEN
    """
    df = base_silver_cleaning(df)
    # Standardize column names for case-insensitive access
    cols = {c.lower(): c for c in df.columns}
    if "bdate" in cols:
        df = normalize_date_column(df, cols["bdate"])
    if "gen" in cols:
        tmp = df[cols["gen"]].astype("string").str.strip().str.upper()
        tmp = tmp.replace({
            "MALE": "M",
            "FEMALE": "F",
            "F": "F",
            "M": "M",
            "": pd.NA,
            "NAN": pd.NA,
            "NONE": pd.NA,
            "NULL": pd.NA,
        })
        df[cols["gen"]] = tmp.replace({"": pd.NA})
    # Standardize missing values in all columns
    for col in df.columns:
        df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    return df


def transform_LOC_A101(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for LOC_A101.csv:
    - Apply base cleaning
    - Standardize missing values in CNTRY
    - Trim whitespace in CNTRY
    """
    df = base_silver_cleaning(df)
    cols = {c.lower(): c for c in df.columns}
    if "cntry" in cols:
        df[cols["cntry"]] = df[cols["cntry"]].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    return df


def transform_PX_CAT_G1V2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for PX_CAT_G1V2.csv:
    - Apply base cleaning
    - Standardize MAINTENANCE values to 'Yes' / 'No' / NA
    """
    df = base_silver_cleaning(df)
    if "MAINTENANCE" in df.columns:
        tmp = df["MAINTENANCE"].astype("string").str.strip().str.lower()
        tmp = tmp.replace({
            "yes": "Yes",
            "no": "No",
            "true": "Yes",
            "false": "No",
            "1": "Yes",
            "0": "No",
            "": pd.NA,
            "nan": pd.NA,
            "null": pd.NA,
        })
        df["MAINTENANCE"] = tmp.replace({"": pd.NA})
    return df


def transform_prd_info(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for prd_info.csv:
    - Apply base cleaning
    - Normalize prd_id to Int64
    - Parse prd_start_dt and prd_end_dt as date
    - Standardize missing values in prd_cost, prd_end_dt, prd_line
    - Trim whitespace in prd_line
    """
    df = base_silver_cleaning(df)
    if "prd_id" in df.columns:
        df = normalize_integer_id(df, "prd_id")
    if "prd_cost" in df.columns:
        df = normalize_numeric_column(df, "prd_cost")
    if "prd_start_dt" in df.columns:
        df = normalize_date_column(df, "prd_start_dt")
    if "prd_end_dt" in df.columns:
        df = normalize_date_column(df, "prd_end_dt")
    if "prd_line" in df.columns:
        df["prd_line"] = df["prd_line"].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    # Standardize missing values in all columns
    for col in df.columns:
        df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    return df


def transform_sales_details(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver logic for sales_details.csv:
    - Apply base cleaning
    - Normalize sls_cust_id to Int64
    - Parse sls_order_dt, sls_ship_dt, sls_due_dt as date (if possible)
    - Standardize missing values in sls_sales, sls_price
    - Normalize sls_sales, sls_quantity, sls_price as numeric
    """
    df = base_silver_cleaning(df)
    # Normalize sls_cust_id to Int64
    if "sls_cust_id" in df.columns:
        df = normalize_integer_id(df, "sls_cust_id")
    # Parse date columns (if they are not already date)
    for col in ["sls_order_dt", "sls_ship_dt", "sls_due_dt"]:
        if col in df.columns:
            # Try to parse as date if not already
            # If integer (e.g. YYYYMMDD), parse accordingly
            if pd.api.types.is_integer_dtype(df[col]) or pd.api.types.is_float_dtype(df[col]):
                # Try to parse as YYYYMMDD
                df[col] = pd.to_datetime(df[col], format="%Y%m%d", errors="coerce")
            else:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.date.astype("string")
            df[col] = df[col].replace({"NaT": pd.NA})
    # Normalize numeric columns
    for col in ["sls_sales", "sls_quantity", "sls_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # Standardize missing values in sls_sales, sls_price
    for col in ["sls_sales", "sls_price"]:
        if col in df.columns:
            df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    # Standardize missing values in all columns
    for col in df.columns:
        df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "null": pd.NA, "NULL": pd.NA})
    return df


def transform_for_silver(filename: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Dispatch to table-specific Silver transformations based on the filename.

    This keeps Bronze grain & column layout, but ensures:
    - cleaned strings
    - harmonized IDs, dates, numerics
    - basic domain-standardization (e.g. gender, maintenance flag)
    """
    name = filename.lower()
    if name == "cst_info.csv":
        return transform_cst_info(df)
    if name == "cst_az12.csv":
        return transform_CST_AZ12(df)
    if name == "loc_a101.csv":
        return transform_LOC_A101(df)
    if name == "px_cat_g1v2.csv":
        return transform_PX_CAT_G1V2(df)
    if name == "prd_info.csv":
        return transform_prd_info(df)
    if name == "sales_details.csv":
        return transform_sales_details(df)
    # Default: only generic base cleaning
    return base_silver_cleaning(df)


# -----------------------------
# Minimal HTML report template
# -----------------------------
HTML_REPORT_TEMPLATE = """\
<html>
<head><title>Silver Run Report</title></head>
<body>
<h1>Silver Run Report: {{ run_id }}</h1>
<p>Run start (UTC): {{ start_dt }}</p>
<p>Run end (UTC): {{ end_dt }}</p>
<p>Source bronze_run_id: {{ bronze_run_id }}</p>

<table border="1" cellpadding="6" cellspacing="0">
<tr>
  <th>file</th>
  <th>status</th>
  <th>rows_in</th>
  <th>rows_out</th>
  <th>read(s)</th>
  <th>write(s)</th>
  <th>in_size(bytes)</th>
  <th>in_mtime(UTC)</th>
  <th>in_sha256</th>
  <th>out_sha256</th>
  <th>error</th>
</tr>
{% for r in results %}
<tr>
  <td>{{ r.file }}</td>
  <td>{{ r.status }}</td>
  <td>{{ r.rows_in }}</td>
  <td>{{ r.rows_out }}</td>
  <td>{{ "%.3f"|format(r.read_duration_s or 0) }}</td>
  <td>{{ "%.3f"|format(r.write_duration_s or 0) }}</td>
  <td>{{ r.in_file_size_bytes or "" }}</td>
  <td>{{ r.in_file_mtime_utc or "" }}</td>
  <td style="font-family: monospace;">{{ r.in_sha256 or "" }}</td>
  <td style="font-family: monospace;">{{ r.out_sha256 or "" }}</td>
  <td>{{ r.error_message or "" }}</td>
</tr>
{% endfor %}
</table>

</body>
</html>
"""


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    # bronze_run_id can be passed as CLI arg; otherwise latest bronze is used.
    bronze_run_id = sys.argv[1] if len(sys.argv) > 1 else find_latest_bronze_run_id()

    bronze_data_dir = os.path.join(BRONZE_ROOT, bronze_run_id, "data")
    if not os.path.exists(bronze_data_dir):
        raise FileNotFoundError(f"Bronze data dir not found: {bronze_data_dir}")

    # Build silver run_id (new timestamp + bronze suffix)
    start_dt = utc_now()
    silver_run_id = make_silver_run_id_from_bronze(bronze_run_id, now=start_dt)

    # Create silver folders
    elt_dir = os.path.join(SILVER_ROOT, silver_run_id)
    data_dir = os.path.join(elt_dir, "data")
    report_dir = os.path.join(elt_dir, "reports")
    ensure_dir(data_dir)
    ensure_dir(report_dir)

    # Logging (run_log.txt under data/)
    log_file = os.path.join(data_dir, "run_log.txt")

    def log(msg: str) -> None:
        ts = iso_utc(utc_now())
        line = f"{ts} | {msg}"
        existing = Path(log_file).read_text(encoding="utf-8") if os.path.exists(log_file) else ""
        atomic_write_text(f"{existing}{line}\n", log_file)
        print(line)

    log(f"RUN_START run_id={silver_run_id}")
    log(f"SOURCE bronze_run_id={bronze_run_id}")
    log(f"CONFIG BRONZE_ROOT={BRONZE_ROOT} SILVER_ROOT={SILVER_ROOT}")

    # Read bronze metadata for lineage (optional)
    bronze_metadata_path = os.path.join(bronze_data_dir, "metadata.yaml")
    bronze_metadata: Optional[Dict[str, Any]] = None
    if os.path.exists(bronze_metadata_path):
        with open(bronze_metadata_path, "r", encoding="utf-8") as f:
            bronze_metadata = yaml.safe_load(f)

    results: List[Dict[str, Any]] = []

    metadata: Dict[str, Any] = {
        "run": {
            "run_id": silver_run_id,
            "layer": "silver",
            "pipeline": "load_2_silver_layer",
            "started_utc": iso_utc(start_dt),
        },
        "env": {
            "python": sys.version.replace("\n", " "),
            "pandas": getattr(pd, "__version__", "unknown"),
            "platform": platform.platform(),
        },
        "source": {
            "bronze_run_id": bronze_run_id,
            "bronze_artifact_path": os.path.join(BRONZE_ROOT, bronze_run_id),
            "bronze_data_dir": bronze_data_dir,
            "bronze_metadata_present": bronze_metadata is not None,
        },
        "tables": {},  # filename -> metadata
        "summary": {},
    }

    if bronze_metadata is not None and isinstance(bronze_metadata, dict):
        # compact lineage pointer
        metadata["source"]["bronze_run_started_utc"] = bronze_metadata.get("run", {}).get("started_utc")

    # Process each CSV from bronze/data
    for filename in sorted(os.listdir(bronze_data_dir)):
        if not filename.lower().endswith(".csv"):
            continue

        src_path = os.path.join(bronze_data_dir, filename)
        out_path = os.path.join(data_dir, filename)

        rec: Dict[str, Any] = {
            "file": filename,
            "status": "FAILED",
            "rows_in": 0,
            "rows_out": 0,
            "schema_in": [],
            "schema_out": [],
            "dtypes_in": {},
            "dtypes_out": {},
            "read_duration_s": None,
            "write_duration_s": None,
            "in_file_size_bytes": None,
            "in_file_mtime_utc": None,
            "in_sha256": None,
            "out_sha256": None,
            "error_type": None,
            "error_message": None,
        }

        try:
            if not os.path.exists(src_path):
                raise FileNotFoundError(f"Bronze CSV not found: {src_path}")

            in_stat = safe_stat_utc(src_path)
            rec["in_file_size_bytes"] = in_stat["file_size_bytes"]
            rec["in_file_mtime_utc"] = in_stat["file_mtime_utc"]
            rec["in_sha256"] = sha256_file(src_path)

            # Read
            t0 = time.perf_counter()
            df = pd.read_csv(src_path)
            rec["read_duration_s"] = time.perf_counter() - t0

            rec["rows_in"] = int(len(df))
            rec["schema_in"] = list(df.columns)
            rec["dtypes_in"] = {c: str(t) for c, t in df.dtypes.items()}

            # Transform (Bronze -> Silver)
            cleaned = transform_for_silver(filename, df)

            rec["rows_out"] = int(len(cleaned))
            rec["schema_out"] = list(cleaned.columns)
            rec["dtypes_out"] = {c: str(t) for c, t in cleaned.dtypes.items()}

            # Write
            t1 = time.perf_counter()
            atomic_to_csv(cleaned, out_path, index=False)
            rec["write_duration_s"] = time.perf_counter() - t1

            rec["out_sha256"] = sha256_file(out_path)

            rec["status"] = "SUCCESS"
            log(
                f"SUCCESS file={filename} rows_in={rec['rows_in']} rows_out={rec['rows_out']} "
                f"read={rec['read_duration_s']:.3f}s write={rec['write_duration_s']:.3f}s"
            )

        except Exception as e:
            rec["error_type"] = type(e).__name__
            rec["error_message"] = str(e)
            log(f"ERROR file={filename} {rec['error_type']}: {rec['error_message']}")
            log(traceback.format_exc())

        results.append(rec)

        # Persist per-table metadata (even on failure)
        metadata["tables"][filename] = {
            "status": rec["status"],
            "rows_in": rec["rows_in"],
            "rows_out": rec["rows_out"],
            "schema_in": rec["schema_in"],
            "schema_out": rec["schema_out"],
            "dtypes_in": rec["dtypes_in"],
            "dtypes_out": rec["dtypes_out"],
            "read_duration_s": rec["read_duration_s"],
            "write_duration_s": rec["write_duration_s"],
            "input": {
                "path": src_path,
                "file_size_bytes": rec["in_file_size_bytes"],
                "file_mtime_utc": rec["in_file_mtime_utc"],
                "sha256": rec["in_sha256"],
            },
            "output": {
                "path": out_path,
                "sha256": rec["out_sha256"],
            },
            "error_type": rec["error_type"],
            "error_message": rec["error_message"],
        }

    end_dt = utc_now()
    ok = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = len(results) - ok

    metadata["run"]["ended_utc"] = iso_utc(end_dt)
    metadata["run"]["duration_s"] = (end_dt - start_dt).total_seconds()
    metadata["summary"] = {
        "files_total": len(results),
        "files_success": ok,
        "files_failed": failed,
    }

    # Persist metadata.yaml under data/
    atomic_write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True),
        os.path.join(data_dir, "metadata.yaml"),
    )

    # Write HTML report under reports/
    report_html_path = os.path.join(report_dir, "elt_report.html")
    report_ctx = {
        "run_id": silver_run_id,
        "bronze_run_id": bronze_run_id,
        "start_dt": iso_utc(start_dt),
        "end_dt": iso_utc(end_dt),
        "results": results,
    }
    from jinja2 import Template

    atomic_write_text(Template(HTML_REPORT_TEMPLATE).render(**report_ctx), report_html_path)

    # Call LLM-based report agent (if import was successful)
    if run_report_agent is not None:
        try:
            log("CALL agents.load_2_report_agent.run_report_agent ...")
            run_report_agent(
                run_id=bronze_run_id,
                silver_run_id=silver_run_id,
            )
            log("load_2_report_agent finished successfully.")
        except Exception as e:
            # LLM/report failures must NOT break the ETL run
            log(f"WARNING: load_2_report_agent failed: {type(e).__name__}: {e}")
    else:
        log("WARNING: run_report_agent could not be imported; skipping LLM report generation.")

    log(
        f"RUN_END run_id={silver_run_id} "
        f"duration_s={metadata['run']['duration_s']:.3f} "
        f"success={ok} failed={failed}"
    )
    log(f"OUTPUT={elt_dir}")

    # Return non-zero if anything failed
    return 0 if failed == 0 else 2



if __name__ == "__main__":
    raise SystemExit(main())
