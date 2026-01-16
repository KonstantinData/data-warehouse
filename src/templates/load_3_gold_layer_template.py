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
import platform
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
- prd_info.csv
    prd_key        : product key (string)
    prd_nm         : product name
- cst_info.csv
    cst_id         : numeric customer id (joins to sales_details.sls_cust_id)
    cst_key        : business key (string)
    cst_firstname, cst_lastname
- LOC_A101.csv
    CID            : location/customer business id (e.g. 'AW-00011000')
    CNTRY          : country name

OUTPUT:
  artifacts/gold/marts/<gold_run_id>/
    data/
      kpi_totals.csv
      kpi_sales_by_product.csv
      kpi_sales_by_country.csv
      top_customers.csv
    _meta/metadata.yaml
    reports/gold_report.html
    run_log.txt

RUN ID
- silver_run_id must match: YYYYMMDD_HHMMSS_#<suffix>
- gold_run_id = <UTC timestamp>_#<same suffix>

GOLD_MART_PLAN (injected by agent):
- dict with at least: {"mart_list": ["kpi_totals", "kpi_sales_by_product", ...]}
- If absent or invalid, all marts are treated as enabled.
"""

RUN_ID_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})_#(?P<suffix>[0-9a-fA-F]{6,32})$")


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
    candidates = [
        repo_root / "artifacts" / "silver",          # PREFERRED
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
GOLD_ROOT = REPO_ROOT / "artifacts" / "gold" / "marts"


# -----------------------------
# IO helpers
# -----------------------------
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_yaml(obj: Dict[str, Any], path: Path) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_html(report_ctx: Dict[str, Any], path: Path) -> None:
    from jinja2 import Template

    path.write_text(Template(HTML_REPORT_TEMPLATE).render(**report_ctx), encoding="utf-8")


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
    return pd.read_csv(p)


# -----------------------------
# GOLD_MART_PLAN handling
# -----------------------------
def mart_enabled(mart_name: str) -> bool:
    """
    Decide whether a mart should be built based on GOLD_MART_PLAN,
    which is injected by the agent as a global variable.

    If GOLD_MART_PLAN is missing or invalid, all marts are treated as enabled.
    """
    try:
        plan = GOLD_MART_PLAN  # type: ignore[name-defined]
    except NameError:
        return True

    if not isinstance(plan, dict):
        return True

    mart_list = plan.get("mart_list")
    if not isinstance(mart_list, list) or not mart_list:
        return True

    return mart_name in mart_list


# -----------------------------
# Business mart builders
# -----------------------------
def build_kpi_totals(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Executive KPI Overview
    - total_revenue
    - total_orders
    - avg_order_value

    Uses:
      - sls_sales as primary revenue column
      - sls_ord_num as order id
    """
    tmp = sales.copy()

    if "sls_sales" in tmp.columns:
        tmp["_revenue"] = pd.to_numeric(tmp["sls_sales"], errors="coerce").fillna(0.0)
    else:
        # Fallback: quantity * price
        qty = pd.to_numeric(tmp.get("sls_quantity", 0), errors="coerce").fillna(0.0)
        price = pd.to_numeric(tmp.get("sls_price", 0), errors="coerce").fillna(0.0)
        tmp["_revenue"] = qty * price

    if "sls_ord_num" in tmp.columns:
        total_orders = int(tmp["sls_ord_num"].nunique())
    else:
        total_orders = int(len(tmp))

    total_revenue = float(tmp["_revenue"].sum())
    avg_order_value = float(total_revenue / total_orders) if total_orders else 0.0

    return pd.DataFrame(
        [
            {"metric": "total_revenue", "value": total_revenue},
            {"metric": "total_orders", "value": total_orders},
            {"metric": "avg_order_value", "value": avg_order_value},
        ]
    )


def build_kpi_sales_by_product(
    sales: pd.DataFrame,
    products: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Product Performance Mart

    Group by:
      - sales.sls_prd_key

    Enrich (if possible):
      - prd_info.prd_nm as product_name
    """
    tmp = sales.copy()

    if "sls_sales" in tmp.columns:
        tmp["_revenue"] = pd.to_numeric(tmp["sls_sales"], errors="coerce").fillna(0.0)
    else:
        qty = pd.to_numeric(tmp.get("sls_quantity", 0), errors="coerce").fillna(0.0)
        price = pd.to_numeric(tmp.get("sls_price", 0), errors="coerce").fillna(0.0)
        tmp["_revenue"] = qty * price

    if "sls_prd_key" not in tmp.columns:
        raise ValueError("sls_prd_key column missing in sales_details")

    by_prod = (
        tmp.groupby("sls_prd_key", dropna=False)["_revenue"]
        .sum()
        .reset_index()
        .rename(columns={"sls_prd_key": "product_key", "_revenue": "revenue"})
    )

    if products is not None:
        if "prd_key" in products.columns:
            cols = ["prd_key"]
            if "prd_nm" in products.columns:
                cols.append("prd_nm")
            prod_dim = products[cols].drop_duplicates(subset=["prd_key"])
            by_prod = by_prod.merge(
                prod_dim,
                left_on="product_key",
                right_on="prd_key",
                how="left",
            )
            if "prd_key" in by_prod.columns and "product_key" in by_prod.columns:
                by_prod = by_prod.drop(columns=["prd_key"])
            if "prd_nm" in by_prod.columns:
                by_prod = by_prod.rename(columns={"prd_nm": "product_name"})

    return by_prod


def build_kpi_sales_by_country(
    sales: pd.DataFrame,
    customers: Optional[pd.DataFrame],
    loc: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Geographic Performance Mart

    Steps:
      1) sales_details join cst_info on:
           sales.sls_cust_id (float) -> cst_info.cst_id (float)
      2) cst_info join LOC_A101 on:
           canonical cst_key from cst_info.cst_key
           canonical CID from LOC_A101.CID (remove '-')
      3) group by CNTRY

    If joins are not possible, raises ValueError.
    """
    if customers is None or loc is None:
        raise ValueError("cst_info and LOC_A101 are required for kpi_sales_by_country")

    tmp = sales.copy()
    tmp["sls_cust_id"] = pd.to_numeric(tmp["sls_cust_id"], errors="coerce")

    cust = customers.copy()
    cust["cst_id"] = pd.to_numeric(cust["cst_id"], errors="coerce")

    # join sales -> customers
    joined = tmp.merge(
        cust[["cst_id", "cst_key"]],
        left_on="sls_cust_id",
        right_on="cst_id",
        how="left",
    )

    # build canonical keys
    joined["cst_key_norm"] = joined["cst_key"].astype(str).str.replace("-", "", regex=False)

    loc_df = loc.copy()
    loc_df["CID_norm"] = loc_df["CID"].astype(str).str.replace("-", "", regex=False)

    joined = joined.merge(
        loc_df[["CID_norm", "CNTRY"]],
        left_on="cst_key_norm",
        right_on="CID_norm",
        how="left",
    )

    if "sls_sales" in joined.columns:
        joined["_revenue"] = pd.to_numeric(joined["sls_sales"], errors="coerce").fillna(0.0)
    else:
        qty = pd.to_numeric(joined.get("sls_quantity", 0), errors="coerce").fillna(0.0)
        price = pd.to_numeric(joined.get("sls_price", 0), errors="coerce").fillna(0.0)
        joined["_revenue"] = qty * price

    if "sls_ord_num" in joined.columns:
        grp = joined.groupby("CNTRY", dropna=False).agg(
            revenue=("_revenue", "sum"),
            orders=("sls_ord_num", "nunique"),
        )
    else:
        grp = joined.groupby("CNTRY", dropna=False).agg(
            revenue=("_revenue", "sum"),
            orders=("_revenue", "size"),
        )

    grp = grp.reset_index().rename(columns={"CNTRY": "country"})
    return grp


def build_top_customers(
    sales: pd.DataFrame,
    customers: Optional[pd.DataFrame],
    top_n: int = 50,
) -> pd.DataFrame:
    """
    Customer Value Mart (Top Customers by Revenue)

    - revenue
    - order_count
    - rank
    - customer name (if available)
    """
    tmp = sales.copy()

    if "sls_sales" in tmp.columns:
        tmp["_revenue"] = pd.to_numeric(tmp["sls_sales"], errors="coerce").fillna(0.0)
    else:
        qty = pd.to_numeric(tmp.get("sls_quantity", 0), errors="coerce").fillna(0.0)
        price = pd.to_numeric(tmp.get("sls_price", 0), errors="coerce").fillna(0.0)
        tmp["_revenue"] = qty * price

    tmp["sls_cust_id"] = pd.to_numeric(tmp["sls_cust_id"], errors="coerce")

    grp = (
        tmp.groupby("sls_cust_id", dropna=False)
        .agg(
            revenue=("_revenue", "sum"),
            order_count=("sls_ord_num", "nunique") if "sls_ord_num" in tmp.columns else ("_revenue", "size"),
        )
        .reset_index()
        .rename(columns={"sls_cust_id": "customer_id"})
        .sort_values("revenue", ascending=False)
    )

    grp["rank"] = grp["revenue"].rank(method="dense", ascending=False).astype(int)
    grp = grp.sort_values("rank").head(top_n)

    if customers is not None:
        cust = customers.copy()
        cust["cst_id"] = pd.to_numeric(cust["cst_id"], errors="coerce")
        cust["customer_name"] = cust["cst_firstname"].astype(str) + " " + cust["cst_lastname"].astype(str)

        grp = grp.merge(
            cust[["cst_id", "customer_name"]],
            left_on="customer_id",
            right_on="cst_id",
            how="left",
        )
        if "cst_id" in grp.columns:
            grp = grp.drop(columns=["cst_id"])

    return grp


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    silver_run_id = sys.argv[1] if len(sys.argv) > 1 else find_latest_run_id(SILVER_ROOT)
    silver_data_dir = resolve_silver_data_dir(silver_run_id)

    start_dt = utc_now()
    gold_run_id = make_gold_run_id_from_silver(silver_run_id, now=start_dt)

    m = RUN_ID_RE.match(silver_run_id)
    suffix = m.group("suffix") if m else None

    gold_dir = GOLD_ROOT / gold_run_id
    data_dir = gold_dir / "data"
    meta_dir = gold_dir / "_meta"
    reports_dir = gold_dir / "reports"

    ensure_dir(data_dir)
    ensure_dir(meta_dir)
    ensure_dir(reports_dir)

    run_log_path = gold_dir / "run_log.txt"

    def log(msg: str) -> None:
        line = f"{iso_utc(utc_now())} | {msg}"
        print(line)
        if run_log_path.exists():
            run_log_path.write_text(run_log_path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
        else:
            run_log_path.write_text(line + "\n", encoding="utf-8")

    outputs: List[Dict[str, Any]] = []
    errors: List[str] = []
    notes: List[str] = []

    log("RUN_START")
    log(f"silver_run_id={silver_run_id}")
    log(f"gold_run_id={gold_run_id}")
    log(f"REPO_ROOT={REPO_ROOT}")
    log(f"SILVER_DATA_DIR={silver_data_dir}")
    log(f"GOLD_DIR={gold_dir}")

    try:
        sales = load_csv(silver_data_dir, "sales_details.csv")
        products = load_csv(silver_data_dir, "prd_info.csv")
        customers = load_csv(silver_data_dir, "cst_info.csv")
        loc = load_csv(silver_data_dir, "LOC_A101.csv")

        if sales is None:
            raise FileNotFoundError("Missing required table: sales_details.csv")

        # 1) KPI totals
        if mart_enabled("kpi_totals"):
            try:
                kpi_totals = build_kpi_totals(sales)
                out = data_dir / "kpi_totals.csv"
                kpi_totals.to_csv(out, index=False)
                outputs.append(
                    {
                        "name": "kpi_totals",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(kpi_totals)),
                        "schema": list(kpi_totals.columns),
                        "sha256": sha256_file(out),
                    }
                )
                log(f"CREATED kpi_totals rows={len(kpi_totals)}")
            except Exception as e:
                msg = f"Failed kpi_totals: {e}"
                errors.append(msg)
                log(msg)

        # 2) KPI by product
        if mart_enabled("kpi_sales_by_product"):
            try:
                if products is None:
                    raise FileNotFoundError("prd_info.csv not found; cannot build kpi_sales_by_product.")
                by_prod = build_kpi_sales_by_product(sales, products)
                out = data_dir / "kpi_sales_by_product.csv"
                by_prod.to_csv(out, index=False)
                outputs.append(
                    {
                        "name": "kpi_sales_by_product",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(by_prod)),
                        "schema": list(by_prod.columns),
                        "sha256": sha256_file(out),
                    }
                )
                log(f"CREATED kpi_sales_by_product rows={len(by_prod)}")
            except Exception as e:
                msg = f"Failed kpi_sales_by_product: {e}"
                errors.append(msg)
                log(msg)

        # 3) KPI by country
        if mart_enabled("kpi_sales_by_country"):
            try:
                if customers is None or loc is None:
                    raise FileNotFoundError("cst_info.csv or LOC_A101.csv missing; cannot build kpi_sales_by_country.")
                by_country = build_kpi_sales_by_country(sales, customers, loc)
                out = data_dir / "kpi_sales_by_country.csv"
                by_country.to_csv(out, index=False)
                outputs.append(
                    {
                        "name": "kpi_sales_by_country",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(by_country)),
                        "schema": list(by_country.columns),
                        "sha256": sha256_file(out),
                    }
                )
                log(f"CREATED kpi_sales_by_country rows={len(by_country)}")
            except Exception as e:
                msg = f"Failed kpi_sales_by_country: {e}"
                errors.append(msg)
                log(msg)

        # 4) Top customers
        if mart_enabled("top_customers"):
            try:
                if customers is None:
                    raise FileNotFoundError("cst_info.csv not found; cannot build top_customers.")
                top = build_top_customers(sales, customers, top_n=50)
                out = data_dir / "top_customers.csv"
                top.to_csv(out, index=False)
                outputs.append(
                    {
                        "name": "top_customers",
                        "path": str(out.relative_to(REPO_ROOT)),
                        "rows": int(len(top)),
                        "schema": list(top.columns),
                        "sha256": sha256_file(out),
                    }
                )
                log(f"CREATED top_customers rows={len(top)}")
            except Exception as e:
                msg = f"Failed top_customers: {e}"
                errors.append(msg)
                log(msg)

        notes.append("Gold marts built based on Silver sales, product, customer and location data, where available.")

    except Exception as e:
        errors.append(f"UNHANDLED gold build failure: {type(e).__name__}: {e}")
        log("UNHANDLED_EXCEPTION")
        log(traceback.format_exc())

    end_dt = utc_now()
    status = "success" if not errors else "partial"

    meta: Dict[str, Any] = {
        "run": {
            "layer": "gold",
            "pipeline": "load_3_gold_layer",
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
        "outputs": outputs,
        "errors": errors,
        "notes": notes,
    }

    write_yaml(meta, meta_dir / "metadata.yaml")

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

    log(f"RUN_END duration_s={(end_dt - start_dt).total_seconds():.3f} status={status}")
    log(f"OUTPUT={gold_dir}")

    return 0 if status == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
