"""
load_3_gold_layer_template.py

Template for the Gold runner (marts builder).

This file is treated as the immutable raw version.
The load_3_gold_layer_agent.py copies this template
verbatim to src/runs/load_3_gold_layer.py and injects
a GOLD_MART_PLAN variable after the 'from __future__' import.

The effective Gold runner (after copy) is load_3_gold_layer.py
and behaves as documented below.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import yaml

"""
load_3_gold_layer.py

Gold runner (marts builder)

CONVENTIONS
- Gold paths do NOT contain 'elt'.
- Reads from Silver runs.
- Uses UTC timestamps (timezone-aware) everywhere for documentation.

INPUT (preferred, from Silver layer):
  artifacts/silver/<silver_run_id>/data/*.csv

Expected Silver tables and key columns:
- sales_details.csv
    sls_ord_num    : order identifier
    sls_prd_key    : product key (to prd_info.prd_key)
    sls_cust_id    : customer id (to cst_info.cst_id)
    sls_sales      : revenue for line (preferred)
    sls_quantity   : quantity
    sls_price      : unit price
    sls_order_dt   : order date (int, YYYYMMDD)
    sls_ship_dt    : ship date (int, YYYYMMDD)
    sls_due_dt     : due date (int, YYYYMMDD)
- prd_info.csv
    prd_key        : product key (string)
    prd_nm         : product name
    prd_cost       : product cost
    prd_line       : product line
    prd_start_dt   : product start date (int, YYYYMMDD)
    prd_end_dt     : product end date (int, YYYYMMDD)
- PX_CAT_G1V2.csv
    ID             : product category id (string)
    CAT            : category
    SUBCAT         : subcategory
    MAINTENANCE    : maintenance flag
- cst_info.csv
    cst_id         : numeric customer id (joins to sales_details.sls_cust_id)
    cst_key        : business key (string)
    cst_firstname, cst_lastname
    cst_marital_status
    cst_gndr
    cst_create_date
- CST_AZ12.csv
    CID            : customer business id (string, e.g. 'AW-00011000')
    BDATE          : birthdate (int, YYYYMMDD)
    GEN            : gender
- LOC_A101.csv
    CID            : location/customer business id (e.g. 'AW-00011000')
    CNTRY          : country name

OUTPUT:
  artifacts/gold/marts/<gold_run_id>/
    data/
      gold_dim_customer.csv
      gold_dim_product.csv
      gold_dim_location.csv
      gold_fact_sales.csv
      gold_agg_exec_kpis.csv
      gold_agg_product_performance.csv
      gold_agg_geo_performance.csv
      gold_wide_sales_enriched.csv
    metadata.yaml
    reports/gold_report.html
    run_log.txt

RUN ID
- silver_run_id must match: YYYYMMDD_HHMMSS_#<suffix>
- gold_run_id = <UTC timestamp>_#<same suffix>
- Optional override: pass gold_run_id as argv[2] or set RUN_ID/ORCHESTRATOR_RUN_ID

GOLD_MART_PLAN (injected by agent):
- dict with at least: {"mart_list": ["gold_dim_customer", ...]}
- If absent or invalid, all marts are treated as enabled.
"""

RUN_ID_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})_#(?P<suffix>[0-9a-fA-F]{6,32})$")
PIPELINE_VERSION = "1.1.0"
MAX_IO_ATTEMPTS = 3
IO_BACKOFF_S = 0.5

REQUIRED_SCHEMAS: Dict[str, Tuple[str, ...]] = {
    "sales_details.csv": (
        "sls_ord_num",
        "sls_prd_key",
        "sls_cust_id",
        "sls_sales",
        "sls_quantity",
        "sls_price",
        "sls_order_dt",
        "sls_ship_dt",
        "sls_due_dt",
    ),
    "prd_info.csv": ("prd_key", "prd_nm", "prd_cost", "prd_line", "prd_start_dt", "prd_end_dt"),
    "PX_CAT_G1V2.csv": ("ID", "CAT", "SUBCAT", "MAINTENANCE"),
    "cst_info.csv": (
        "cst_id",
        "cst_key",
        "cst_firstname",
        "cst_lastname",
        "cst_marital_status",
        "cst_gndr",
        "cst_create_date",
    ),
    "CST_AZ12.csv": ("CID", "BDATE", "GEN"),
    "LOC_A101.csv": ("CID", "CNTRY"),
}


HTML_REPORT_TEMPLATE = """
<html>
<head><title>Gold Run Report</title></head>
<body>
<h1>Gold Run Report: {{ run_id }}</h1>
<p>Run start (UTC): {{ start_dt }}</p>
<p>Run end (UTC): {{ end_dt }}</p>
<p>Source silver_run_id: {{ silver_run_id }}</p>

<h2>Outputs</h2>
<ul>
{% for o in outputs %}
  <li>{{ o }}</li>
{% endfor %}
</ul>

<h2>Status</h2>
<p>{{ status }}</p>

{% if errors and errors|length > 0 %}
<h2>Errors</h2>
<ul>
{% for e in errors %}
  <li>{{ e }}</li>
{% endfor %}
</ul>
{% endif %}

{% if notes %}
<h2>Notes</h2>
<p>{{ notes }}</p>
{% endif %}

</body>
</html>
"""


# -----------------------------
# Time helpers (UTC)
# -----------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# -----------------------------
# Repo root + silver root resolution
# -----------------------------
def find_repo_root(start: Path) -> Path:
    cur = start
    while cur != cur.parent:
        if (cur / "artifacts").exists() and (cur / "src").exists():
            return cur
        cur = cur.parent
    # fallback
    return start.resolve().parents[2]


REPO_ROOT = find_repo_root(Path(__file__).resolve())


def resolve_silver_root(repo_root: Path) -> Path:
    """
    Preferred convention:
      artifacts/silver/<run_id>/
    But we support legacy/fallbacks.
    """
    override = os.environ.get("SILVER_ROOT_OVERRIDE")
    if override:
        candidate = Path(override).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        raise FileNotFoundError(f"SILVER_ROOT_OVERRIDE does not exist or is not a directory: {candidate}")

    candidates = [
        repo_root / "artifacts" / "silver",  # PREFERRED
        repo_root / "artifacts" / "silver" / "elt",  # legacy
        repo_root / "artifacts" / "silver" / "runs",
        repo_root / "artifacts" / "sylver" / "runs",  # legacy spelling
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    raise FileNotFoundError(
        "Could not find Silver root. Tried:\n" + "\n".join(str(c) for c in candidates)
    )


SILVER_ROOT = resolve_silver_root(REPO_ROOT)
GOLD_ROOT = Path(os.environ.get("GOLD_ROOT_OVERRIDE", str(REPO_ROOT / "artifacts" / "gold" / "marts"))).expanduser()


# -----------------------------
# IO helpers
# -----------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": iso_utc(utc_now()),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        context = getattr(record, "context", None)
        if event:
            payload["event"] = event
        if context:
            payload["context"] = context
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            payload["exception"] = {"type": exc_type, "message": str(record.exc_info[1])}
        return json.dumps(payload, ensure_ascii=False)


def build_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger(f"gold_runner_{log_path}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
    logger.info(message, extra={"event": event, "context": context or {}})
    print(f"{iso_utc(utc_now())} | {event} | {message}")


def with_retry(action: Callable[[], Any], *, attempts: int = MAX_IO_ATTEMPTS, backoff_s: float = IO_BACKOFF_S) -> Any:
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except (OSError, IOError) as exc:
            if attempt == attempts:
                raise
            time.sleep(backoff_s * attempt)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    def _read() -> None:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk_size)
                if not b:
                    break
                h.update(b)

    with_retry(_read)
    return h.hexdigest()


def write_yaml(obj: Dict[str, Any], path: Path) -> None:
    data = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
    with_retry(lambda: path.write_text(data, encoding="utf-8"))


def write_html(report_ctx: Dict[str, Any], path: Path) -> None:
    from jinja2 import Template

    rendered = Template(HTML_REPORT_TEMPLATE).render(**report_ctx)
    with_retry(lambda: path.write_text(rendered, encoding="utf-8"))


def find_latest_run_id(root: Path) -> str:
    if not root.exists():
        raise FileNotFoundError(f"Root does not exist: {root}")

    run_ids: List[str] = []
    for name in root.iterdir():
        if not name.is_dir():
            continue
        if RUN_ID_RE.match(name.name):
            run_ids.append(name.name)

    if not run_ids:
        raise FileNotFoundError(f"No runs found in: {root}")

    return sorted(run_ids)[-1]


def resolve_silver_data_dir(silver_run_id: str) -> Path:
    """
    Handles both:
      SILVER_ROOT = artifacts/silver
      SILVER_ROOT = artifacts/silver/elt (legacy)
    """
    d = SILVER_ROOT / silver_run_id / "data"
    if d.exists():
        return d

    for c in [
        REPO_ROOT / "artifacts" / "silver" / silver_run_id / "data",
        REPO_ROOT / "artifacts" / "silver" / "elt" / silver_run_id / "data",
        REPO_ROOT / "artifacts" / "silver" / "runs" / silver_run_id / "data",
        REPO_ROOT / "artifacts" / "sylver" / "runs" / silver_run_id / "data",
    ]:
        if c.exists():
            return c

    raise FileNotFoundError(f"Silver data dir not found for run_id={silver_run_id}")


def make_gold_run_id_from_silver(silver_run_id: str, now: Optional[datetime] = None) -> str:
    m = RUN_ID_RE.match(silver_run_id)
    if not m:
        raise ValueError(f"Invalid silver run_id format: {silver_run_id}")
    suffix = m.group("suffix")
    now_dt = now or utc_now()
    return f"{now_dt.strftime('%Y%m%d_%H%M%S')}_#{suffix}"


def load_csv(folder: Path, filename: str) -> Optional[pd.DataFrame]:
    p = folder / filename
    if not p.exists():
        return None
    return with_retry(lambda: pd.read_csv(p))


def write_csv(df: pd.DataFrame, path: Path) -> None:
    with_retry(lambda: df.to_csv(path, index=False))


def validate_required_columns(
    df: pd.DataFrame,
    required: Sequence[str],
    table_name: str,
) -> List[str]:
    missing = [col for col in required if col not in df.columns]
    return [f"{table_name} missing columns: {missing}"] if missing else []


# -----------------------------
# GOLD_MART_PLAN handling
# -----------------------------
def get_mart_plan() -> Optional[Dict[str, Any]]:
    try:
        plan = GOLD_MART_PLAN  # type: ignore[name-defined]
    except NameError:
        return None
    return plan if isinstance(plan, dict) else None


def mart_enabled(mart_name: str, plan: Optional[Dict[str, Any]]) -> bool:
    """
    Decide whether a mart should be built based on GOLD_MART_PLAN.

    If GOLD_MART_PLAN is missing or invalid, all marts are treated as enabled.
    """
    if not plan:
        return True

    mart_list = plan.get("mart_list")
    if not isinstance(mart_list, list) or not mart_list:
        return True

    return mart_name in mart_list


# -----------------------------
# Utility: Date conversion
# -----------------------------
def int_to_date(val: Any) -> Optional[str]:
    """
    Converts integer YYYYMMDD to ISO date string.
    """
    try:
        v = int(val)
        if v <= 0:
            return None
        return f"{v // 10000:04d}-{(v // 100) % 100:02d}-{v % 100:02d}"
    except Exception:
        return None


def add_period_month(df: pd.DataFrame, date_col: str, out_col: str = "period") -> pd.DataFrame:
    """
    Adds a 'period' column in YYYY-MM format based on integer date column.
    """
    df = df.copy()
    df[out_col] = df[date_col].apply(lambda x: int_to_date(x)[:7] if pd.notnull(x) and int_to_date(x) else None)
    return df


# -----------------------------
# GOLD MART BUILDERS
# -----------------------------

def build_gold_dim_customer(
    cst_info: pd.DataFrame,
    cst_az12: Optional[pd.DataFrame],
    loc: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Build gold_dim_customer:
    - One row per customer (cst_id)
    - Merge cst_info, CST_AZ12, LOC_A101
    - Dimensions: cst_key, cst_firstname, cst_lastname, cst_marital_status, cst_gndr, cst_create_date, CID, BDATE, GEN, CNTRY
    """
    # Standardize keys
    cst = cst_info.copy()
    cst["cst_id"] = pd.to_numeric(cst["cst_id"], errors="coerce")
    cst["cst_key"] = cst["cst_key"].astype(str)
    # Merge CST_AZ12
    if cst_az12 is not None:
        az = cst_az12.copy()
        az["CID"] = az["CID"].astype(str)
        az["BDATE"] = pd.to_numeric(az["BDATE"], errors="coerce")
        az["GEN"] = az["GEN"].astype(str)
        # Attempt to join on cst_key == CID (removing dashes)
        cst["CID"] = cst["cst_key"].str.replace("-", "", regex=False)
        az["CID_norm"] = az["CID"].str.replace("-", "", regex=False)
        cst = cst.merge(
            az[["CID_norm", "BDATE", "GEN"]],
            left_on="CID",
            right_on="CID_norm",
            how="left",
        )
        cst = cst.drop(columns=["CID_norm"])
    else:
        cst["BDATE"] = None
        cst["GEN"] = None
    # Merge LOC_A101
    if loc is not None:
        loc_df = loc.copy()
        loc_df["CID"] = loc_df["CID"].astype(str)
        loc_df["CID_norm"] = loc_df["CID"].str.replace("-", "", regex=False)
        cst = cst.merge(
            loc_df[["CID_norm", "CNTRY"]],
            left_on="CID",
            right_on="CID_norm",
            how="left",
        )
        cst = cst.drop(columns=["CID_norm"])
    else:
        cst["CNTRY"] = None
    # Select columns
    out_cols = [
        "cst_id",
        "cst_key",
        "cst_firstname",
        "cst_lastname",
        "cst_marital_status",
        "cst_gndr",
        "cst_create_date",
        "CID",
        "BDATE",
        "GEN",
        "CNTRY",
    ]
    # Ensure all columns exist
    for col in out_cols:
        if col not in cst.columns:
            cst[col] = None
    # Remove duplicates
    cst = cst.drop_duplicates(subset=["cst_id"])
    return cst[out_cols]


def build_gold_dim_product(
    prd_info: pd.DataFrame,
    px_cat: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Build gold_dim_product:
    - One row per product (prd_key)
    - Merge prd_info, PX_CAT_G1V2
    - Dimensions: prd_key, prd_nm, prd_line, prd_start_dt, prd_end_dt, ID, CAT, SUBCAT, MAINTENANCE
    - Measures: prd_cost
    """
    prd = prd_info.copy()
    prd["prd_key"] = prd["prd_key"].astype(str)
    prd["prd_id"] = prd["prd_key"]  # Alias for clarity
    # Merge PX_CAT_G1V2
    if px_cat is not None:
        px = px_cat.copy()
        px["ID"] = px["ID"].astype(str)
        # Try to join on prd_key == ID (if possible)
        prd = prd.merge(
            px[["ID", "CAT", "SUBCAT", "MAINTENANCE"]],
            left_on="prd_key",
            right_on="ID",
            how="left",
        )
    else:
        prd["ID"] = prd["prd_key"]
        prd["CAT"] = None
        prd["SUBCAT"] = None
        prd["MAINTENANCE"] = None
    # Select columns
    out_cols = [
        "prd_id",
        "prd_key",
        "prd_nm",
        "prd_cost",
        "prd_line",
        "prd_start_dt",
        "prd_end_dt",
        "ID",
        "CAT",
        "SUBCAT",
        "MAINTENANCE",
    ]
    for col in out_cols:
        if col not in prd.columns:
            prd[col] = None
    prd = prd.drop_duplicates(subset=["prd_id"])
    return prd[out_cols]


def build_gold_dim_location(
    loc: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_dim_location:
    - One row per customer location (CID)
    - Dimensions: CID, CNTRY
    """
    l = loc.copy()
    l["CID"] = l["CID"].astype(str)
    l = l.drop_duplicates(subset=["CID"])
    out_cols = ["CID", "CNTRY"]
    for col in out_cols:
        if col not in l.columns:
            l[col] = None
    return l[out_cols]


def build_gold_fact_sales(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_fact_sales:
    - One row per sales order line
    - Measures: sls_sales, sls_quantity, sls_price
    - Dimensions: sls_prd_key, sls_cust_id, sls_order_dt, sls_ship_dt, sls_due_dt
    """
    f = sales.copy()
    # Ensure columns exist
    for col in [
        "sls_ord_num",
        "sls_prd_key",
        "sls_cust_id",
        "sls_sales",
        "sls_quantity",
        "sls_price",
        "sls_order_dt",
        "sls_ship_dt",
        "sls_due_dt",
    ]:
        if col not in f.columns:
            f[col] = None
    # Remove duplicates
    f = f.drop_duplicates(subset=["sls_ord_num", "sls_prd_key"])
    out_cols = [
        "sls_ord_num",
        "sls_prd_key",
        "sls_cust_id",
        "sls_sales",
        "sls_quantity",
        "sls_price",
        "sls_order_dt",
        "sls_ship_dt",
        "sls_due_dt",
    ]
    return f[out_cols]


def build_gold_agg_exec_kpis(
    fact_sales: pd.DataFrame,
    dim_customer: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_agg_exec_kpis:
    - Aggregated at monthly and customer segment level
    - Measures: Conversion Rate, Customer Lifetime Value, Return Rate, Average Order Value, Customer Retention Rate
    - Dimensions: period, customer_segment
    - Customer segments: use cst_marital_status, cst_gndr, GEN, or create 'All'
    - Return Rate: not available, set as None
    """
    # Prepare sales with period
    sales = fact_sales.copy()
    sales = add_period_month(sales, "sls_order_dt", "period")
    # Join customer segment
    cust = dim_customer.copy()
    cust["cst_id"] = pd.to_numeric(cust["cst_id"], errors="coerce")
    # For demo, segment by cst_marital_status; fallback to 'All'
    if "cst_marital_status" in cust.columns:
        cust["customer_segment"] = cust["cst_marital_status"].fillna("Unknown")
    else:
        cust["customer_segment"] = "All"
    sales["sls_cust_id"] = pd.to_numeric(sales["sls_cust_id"], errors="coerce")
    sales = sales.merge(
        cust[["cst_id", "customer_segment"]],
        left_on="sls_cust_id",
        right_on="cst_id",
        how="left",
    )
    # Compute KPIs
    def safe_div(a, b):
        return float(a) / float(b) if b else None

    agg = (
        sales.groupby(["period", "customer_segment"], dropna=False)
        .agg(
            total_sales=("sls_sales", "sum"),
            order_count=("sls_ord_num", "nunique"),
            customer_count=("sls_cust_id", "nunique"),
        )
        .reset_index()
    )
    # Conversion Rate: not computable (no funnel data), set None
    agg["Conversion Rate"] = None
    # Customer Lifetime Value: total_sales / customer_count
    agg["Customer Lifetime Value"] = agg.apply(lambda r: safe_div(r["total_sales"], r["customer_count"]), axis=1)
    # Return Rate: not available, set None
    agg["Return Rate"] = None
    # Average Order Value: total_sales / order_count
    agg["Average Order Value"] = agg.apply(lambda r: safe_div(r["total_sales"], r["order_count"]), axis=1)
    # Customer Retention Rate: not computable (needs time window), set None
    agg["Customer Retention Rate"] = None
    # Select columns
    out_cols = [
        "period",
        "customer_segment",
        "Conversion Rate",
        "Customer Lifetime Value",
        "Return Rate",
        "Average Order Value",
        "Customer Retention Rate",
    ]
    return agg[out_cols]


def build_gold_agg_product_performance(
    fact_sales: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_agg_product_performance:
    - Aggregated at product and category level monthly
    - Measures: Total Sales, Total Quantity Sold, Return Rate (not available)
    - Dimensions: prd_id, period, prd_line, CAT, SUBCAT
    """
    sales = fact_sales.copy()
    sales = add_period_month(sales, "sls_order_dt", "period")
    prod = dim_product.copy()
    # Join product attributes
    sales = sales.merge(
        prod[["prd_id", "prd_key", "prd_line", "CAT", "SUBCAT"]],
        left_on="sls_prd_key",
        right_on="prd_key",
        how="left",
    )
    # Aggregate
    agg = (
        sales.groupby(["prd_id", "period", "prd_line", "CAT", "SUBCAT"], dropna=False)
        .agg(
            Total_Sales=("sls_sales", "sum"),
            Total_Quantity_Sold=("sls_quantity", "sum"),
        )
        .reset_index()
    )
    agg["Return Rate"] = None  # No returns data
    out_cols = [
        "prd_id",
        "period",
        "prd_line",
        "CAT",
        "SUBCAT",
        "Total_Sales",
        "Total_Quantity_Sold",
        "Return Rate",
    ]
    return agg[out_cols]


def build_gold_agg_geo_performance(
    fact_sales: pd.DataFrame,
    dim_location: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_agg_geo_performance:
    - Aggregated at country and product category level monthly
    - Measures: Total Sales, Total Quantity Sold
    - Dimensions: CNTRY, CAT, period
    """
    sales = fact_sales.copy()
    sales = add_period_month(sales, "sls_order_dt", "period")
    # Join location
    # Need to map sls_cust_id -> CID -> CNTRY
    # Assume sls_cust_id can be mapped via cst_info/cst_key/CID, but here, use sls_cust_id as string for join
    # For demo, assume sales has 'CID' (if not, skip location join)
    if "CID" not in sales.columns and "sls_cust_id" in sales.columns:
        sales["CID"] = sales["sls_cust_id"].astype(str)
    loc = dim_location.copy()
    loc["CID"] = loc["CID"].astype(str)
    sales = sales.merge(
        loc[["CID", "CNTRY"]],
        on="CID",
        how="left",
    )
    # Join product category
    prod = dim_product.copy()
    prod["prd_key"] = prod["prd_key"].astype(str)
    sales = sales.merge(
        prod[["prd_key", "CAT"]],
        left_on="sls_prd_key",
        right_on="prd_key",
        how="left",
    )
    # Aggregate
    agg = (
        sales.groupby(["CNTRY", "CAT", "period"], dropna=False)
        .agg(
            Total_Sales=("sls_sales", "sum"),
            Total_Quantity_Sold=("sls_quantity", "sum"),
        )
        .reset_index()
    )
    out_cols = [
        "CNTRY",
        "CAT",
        "period",
        "Total_Sales",
        "Total_Quantity_Sold",
    ]
    return agg[out_cols]


def build_gold_wide_sales_enriched(
    fact_sales: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_location: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build gold_wide_sales_enriched:
    - One row per sales order line enriched with customer, product, and location attributes
    - Measures: sls_sales, sls_quantity, sls_price
    - Dimensions: cst_id, cst_key, cst_marital_status, cst_gndr, BDATE, GEN, CNTRY, prd_id, prd_key, prd_nm, prd_line, CAT, SUBCAT
    """
    sales = fact_sales.copy()
    # Join customer
    cust = dim_customer.copy()
    cust["cst_id"] = pd.to_numeric(cust["cst_id"], errors="coerce")
    sales["sls_cust_id"] = pd.to_numeric(sales["sls_cust_id"], errors="coerce")
    sales = sales.merge(
        cust[
            [
                "cst_id",
                "cst_key",
                "cst_marital_status",
                "cst_gndr",
                "BDATE",
                "GEN",
                "CNTRY",
            ]
        ],
        left_on="sls_cust_id",
        right_on="cst_id",
        how="left",
    )
    # Join product
    prod = dim_product.copy()
    prod["prd_key"] = prod["prd_key"].astype(str)
    sales = sales.merge(
        prod[
            [
                "prd_id",
                "prd_key",
                "prd_nm",
                "prd_line",
                "CAT",
                "SUBCAT",
            ]
        ],
        left_on="sls_prd_key",
        right_on="prd_key",
        how="left",
    )
    # Join location (if not already present)
    if "CID" not in sales.columns and "cst_key" in sales.columns:
        sales["CID"] = sales["cst_key"].str.replace("-", "", regex=False)
    loc = dim_location.copy()
    loc["CID"] = loc["CID"].astype(str)
    sales = sales.merge(
        loc[["CID", "CNTRY"]],
        on="CID",
        how="left",
        suffixes=("", "_loc"),
    )
    # Select columns
    out_cols = [
        "sls_ord_num",
        "sls_prd_key",
        "sls_cust_id",
        "sls_sales",
        "sls_quantity",
        "sls_price",
        "cst_id",
        "cst_key",
        "cst_marital_status",
        "cst_gndr",
        "BDATE",
        "GEN",
        "CNTRY",
        "prd_id",
        "prd_key",
        "prd_nm",
        "prd_line",
        "CAT",
        "SUBCAT",
    ]
    for col in out_cols:
        if col not in sales.columns:
            sales[col] = None
    return sales[out_cols]


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    silver_run_id = sys.argv[1] if len(sys.argv) > 1 else find_latest_run_id(SILVER_ROOT)
    silver_data_dir = resolve_silver_data_dir(silver_run_id)

    start_dt = utc_now()
    perf_start = time.perf_counter()
    requested_run_id = None
    if len(sys.argv) > 2:
        requested_run_id = sys.argv[2]
    else:
        requested_run_id = os.environ.get("RUN_ID") or os.environ.get("ORCHESTRATOR_RUN_ID")

    if requested_run_id and RUN_ID_RE.match(requested_run_id):
        gold_run_id = requested_run_id
        run_id_source = "provided"
    else:
        gold_run_id = make_gold_run_id_from_silver(silver_run_id, now=start_dt)
        run_id_source = "generated"

    m = RUN_ID_RE.match(silver_run_id)
    suffix = m.group("suffix") if m else None

    gold_dir = GOLD_ROOT / gold_run_id
    data_dir = gold_dir / "data"
    reports_dir = gold_dir / "reports"

    ensure_dir(data_dir)
    ensure_dir(reports_dir)

    run_log_path = gold_dir / "run_log.txt"
    logger = build_logger(run_log_path)
    mart_plan = get_mart_plan()

    outputs: List[Dict[str, Any]] = []
    errors: List[str] = []
    notes: List[str] = []
    if requested_run_id and not RUN_ID_RE.match(requested_run_id):
        notes.append(f"Requested run_id '{requested_run_id}' did not match expected format; generated run_id used instead.")

    log_event(logger, "RUN_START", "Gold run started", {"silver_run_id": silver_run_id})
    log_event(logger, "RUN_METADATA", "Gold run identifiers resolved", {"gold_run_id": gold_run_id, "run_id_source": run_id_source})
    log_event(
        logger,
        "RUN_PATHS",
        "Resolved IO paths",
        {"repo_root": str(REPO_ROOT), "silver_data_dir": str(silver_data_dir), "gold_dir": str(gold_dir)},
    )
    if mart_plan:
        log_event(logger, "MART_PLAN", "Loaded mart plan configuration", {"marts": mart_plan.get("mart_list", [])})

    try:
        # Load all required silver tables
        sales = load_csv(silver_data_dir, "sales_details.csv")
        prd_info = load_csv(silver_data_dir, "prd_info.csv")
        px_cat = load_csv(silver_data_dir, "PX_CAT_G1V2.csv")
        cst_info = load_csv(silver_data_dir, "cst_info.csv")
        cst_az12 = load_csv(silver_data_dir, "CST_AZ12.csv")
        loc = load_csv(silver_data_dir, "LOC_A101.csv")

        for name, df in [
            ("sales_details.csv", sales),
            ("prd_info.csv", prd_info),
            ("PX_CAT_G1V2.csv", px_cat),
            ("cst_info.csv", cst_info),
            ("CST_AZ12.csv", cst_az12),
            ("LOC_A101.csv", loc),
        ]:
            if df is None:
                continue
            required = REQUIRED_SCHEMAS.get(name)
            if required:
                schema_errors = validate_required_columns(df, required, name)
                if schema_errors:
                    raise ValueError("; ".join(schema_errors))

        # 1) gold_dim_customer
        if mart_enabled("gold_dim_customer", mart_plan):
            try:
                if cst_info is None:
                    raise FileNotFoundError("cst_info.csv is required for gold_dim_customer")
                if REQUIRED_SCHEMAS.get("cst_info.csv"):
                    schema_errors = validate_required_columns(cst_info, REQUIRED_SCHEMAS["cst_info.csv"], "cst_info.csv")
                    if schema_errors:
                        raise ValueError("; ".join(schema_errors))
                dim_customer = build_gold_dim_customer(cst_info, cst_az12, loc)
                out = data_dir / "gold_dim_customer.csv"
                mart_start = time.perf_counter()
                write_csv(dim_customer, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_dim_customer",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(dim_customer)),
                        "schema": list(dim_customer.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(logger, "MART_BUILT", "Built gold_dim_customer", {"rows": len(dim_customer), "duration_s": duration})
            except Exception as e:
                msg = f"Failed gold_dim_customer: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_dim_customer"}})
        else:
            dim_customer = None

        # 2) gold_dim_product
        if mart_enabled("gold_dim_product", mart_plan):
            try:
                if prd_info is None:
                    raise FileNotFoundError("prd_info.csv is required for gold_dim_product")
                if REQUIRED_SCHEMAS.get("prd_info.csv"):
                    schema_errors = validate_required_columns(prd_info, REQUIRED_SCHEMAS["prd_info.csv"], "prd_info.csv")
                    if schema_errors:
                        raise ValueError("; ".join(schema_errors))
                dim_product = build_gold_dim_product(prd_info, px_cat)
                out = data_dir / "gold_dim_product.csv"
                mart_start = time.perf_counter()
                write_csv(dim_product, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_dim_product",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(dim_product)),
                        "schema": list(dim_product.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(logger, "MART_BUILT", "Built gold_dim_product", {"rows": len(dim_product), "duration_s": duration})
            except Exception as e:
                msg = f"Failed gold_dim_product: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_dim_product"}})
        else:
            dim_product = None

        # 3) gold_dim_location
        if mart_enabled("gold_dim_location", mart_plan):
            try:
                if loc is None:
                    raise FileNotFoundError("LOC_A101.csv is required for gold_dim_location")
                if REQUIRED_SCHEMAS.get("LOC_A101.csv"):
                    schema_errors = validate_required_columns(loc, REQUIRED_SCHEMAS["LOC_A101.csv"], "LOC_A101.csv")
                    if schema_errors:
                        raise ValueError("; ".join(schema_errors))
                dim_location = build_gold_dim_location(loc)
                out = data_dir / "gold_dim_location.csv"
                mart_start = time.perf_counter()
                write_csv(dim_location, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_dim_location",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(dim_location)),
                        "schema": list(dim_location.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(logger, "MART_BUILT", "Built gold_dim_location", {"rows": len(dim_location), "duration_s": duration})
            except Exception as e:
                msg = f"Failed gold_dim_location: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_dim_location"}})
        else:
            dim_location = None

        # 4) gold_fact_sales
        if mart_enabled("gold_fact_sales", mart_plan):
            try:
                if sales is None:
                    raise FileNotFoundError("sales_details.csv is required for gold_fact_sales")
                if REQUIRED_SCHEMAS.get("sales_details.csv"):
                    schema_errors = validate_required_columns(
                        sales,
                        REQUIRED_SCHEMAS["sales_details.csv"],
                        "sales_details.csv",
                    )
                    if schema_errors:
                        raise ValueError("; ".join(schema_errors))
                fact_sales = build_gold_fact_sales(sales)
                out = data_dir / "gold_fact_sales.csv"
                mart_start = time.perf_counter()
                write_csv(fact_sales, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_fact_sales",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(fact_sales)),
                        "schema": list(fact_sales.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(logger, "MART_BUILT", "Built gold_fact_sales", {"rows": len(fact_sales), "duration_s": duration})
            except Exception as e:
                msg = f"Failed gold_fact_sales: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_fact_sales"}})
        else:
            fact_sales = None

        # 5) gold_agg_exec_kpis
        if mart_enabled("gold_agg_exec_kpis", mart_plan):
            try:
                if fact_sales is None or dim_customer is None:
                    raise FileNotFoundError("gold_fact_sales and gold_dim_customer are required for gold_agg_exec_kpis")
                agg_exec_kpis = build_gold_agg_exec_kpis(fact_sales, dim_customer)
                out = data_dir / "gold_agg_exec_kpis.csv"
                mart_start = time.perf_counter()
                write_csv(agg_exec_kpis, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_agg_exec_kpis",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(agg_exec_kpis)),
                        "schema": list(agg_exec_kpis.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(logger, "MART_BUILT", "Built gold_agg_exec_kpis", {"rows": len(agg_exec_kpis), "duration_s": duration})
            except Exception as e:
                msg = f"Failed gold_agg_exec_kpis: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_agg_exec_kpis"}})

        # 6) gold_agg_product_performance
        if mart_enabled("gold_agg_product_performance", mart_plan):
            try:
                if fact_sales is None or dim_product is None:
                    raise FileNotFoundError("gold_fact_sales and gold_dim_product are required for gold_agg_product_performance")
                agg_prod_perf = build_gold_agg_product_performance(fact_sales, dim_product)
                out = data_dir / "gold_agg_product_performance.csv"
                mart_start = time.perf_counter()
                write_csv(agg_prod_perf, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_agg_product_performance",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(agg_prod_perf)),
                        "schema": list(agg_prod_perf.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(
                    logger,
                    "MART_BUILT",
                    "Built gold_agg_product_performance",
                    {"rows": len(agg_prod_perf), "duration_s": duration},
                )
            except Exception as e:
                msg = f"Failed gold_agg_product_performance: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_agg_product_performance"}})

        # 7) gold_agg_geo_performance
        if mart_enabled("gold_agg_geo_performance", mart_plan):
            try:
                if fact_sales is None or dim_location is None or dim_product is None:
                    raise FileNotFoundError("gold_fact_sales, gold_dim_location, and gold_dim_product are required for gold_agg_geo_performance")
                agg_geo_perf = build_gold_agg_geo_performance(fact_sales, dim_location, dim_product)
                out = data_dir / "gold_agg_geo_performance.csv"
                mart_start = time.perf_counter()
                write_csv(agg_geo_perf, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_agg_geo_performance",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(agg_geo_perf)),
                        "schema": list(agg_geo_perf.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(
                    logger,
                    "MART_BUILT",
                    "Built gold_agg_geo_performance",
                    {"rows": len(agg_geo_perf), "duration_s": duration},
                )
            except Exception as e:
                msg = f"Failed gold_agg_geo_performance: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_agg_geo_performance"}})

        # 8) gold_wide_sales_enriched
        if mart_enabled("gold_wide_sales_enriched", mart_plan):
            try:
                if fact_sales is None or dim_customer is None or dim_product is None or dim_location is None:
                    raise FileNotFoundError("gold_fact_sales, gold_dim_customer, gold_dim_product, and gold_dim_location are required for gold_wide_sales_enriched")
                wide_sales = build_gold_wide_sales_enriched(fact_sales, dim_customer, dim_product, dim_location)
                out = data_dir / "gold_wide_sales_enriched.csv"
                mart_start = time.perf_counter()
                write_csv(wide_sales, out)
                duration = time.perf_counter() - mart_start
                outputs.append(
                    {
                        "name": "gold_wide_sales_enriched",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(wide_sales)),
                        "schema": list(wide_sales.columns),
                        "sha256": sha256_file(out),
                        "duration_s": duration,
                    }
                )
                log_event(
                    logger,
                    "MART_BUILT",
                    "Built gold_wide_sales_enriched",
                    {"rows": len(wide_sales), "duration_s": duration},
                )
            except Exception as e:
                msg = f"Failed gold_wide_sales_enriched: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.exception(msg, extra={"event": "MART_FAILURE", "context": {"mart": "gold_wide_sales_enriched"}})

        notes.append("Gold marts built based on Silver sales, product, customer, demographic, and location data, where available. Date fields converted to ISO format where appropriate. Return Rate KPIs set to None due to lack of returns data.")

    except Exception as e:
        errors.append(f"UNHANDLED gold build failure: {type(e).__name__}: {e}")
        logger.exception(
            "UNHANDLED_EXCEPTION",
            extra={"event": "UNHANDLED_EXCEPTION", "context": {"error_type": type(e).__name__}},
        )

    end_dt = utc_now()
    total_duration = time.perf_counter() - perf_start
    status = "success" if not errors else "partial"

    meta: Dict[str, Any] = {
        "run": {
            "layer": "gold",
            "pipeline": "load_3_gold_layer",
            "pipeline_version": PIPELINE_VERSION,
            "run_id": gold_run_id,
            "started_utc": iso_utc(start_dt),
            "ended_utc": iso_utc(end_dt),
            "duration_s": (end_dt - start_dt).total_seconds(),
            "status": status,
        },
        "env": {
            "python": sys.version.replace("\n", " "),
            "pandas": getattr(pd, "__version__", "unknown"),
            "platform": platform.platform(),
        },
        "source": {
            "silver_run_id": silver_run_id,
            "silver_data_dir": str(silver_data_dir),
            "suffix": suffix,
        },
        "metrics": {
            "outputs_count": len(outputs),
            "errors_count": len(errors),
            "duration_s": total_duration,
        },
        "outputs": outputs,
        "errors": errors,
        "notes": notes,
    }

    write_yaml(meta, gold_dir / "metadata.yaml")

    write_html(
        {
            "run_id": gold_run_id,
            "start_dt": iso_utc(start_dt),
            "end_dt": iso_utc(end_dt),
            "silver_run_id": silver_run_id,
            "outputs": [o["path"] for o in outputs],
            "status": status,
            "errors": errors,
            "notes": " ".join(notes),
        },
        reports_dir / "gold_report.html",
    )

    log_event(
        logger,
        "RUN_END",
        "Gold run completed",
        {"duration_s": total_duration, "status": status, "output_dir": str(gold_dir)},
    )

    return 0 if status == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
