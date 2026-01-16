"""
load_2_report_agent.py

Called to generate a Silver draft context using Bronze run artifacts.

Responsibilities:
- Reads metadata.yaml, run_log.txt, and CSVs from the Bronze run
- Uses the Data Analytics Process (steps 1–10) as guiding framework
- Calls an OpenAI LLM using environment variables (OPEN_AI_KEY / OPENAI_API_KEY)
- Produces (under tmp/draft_reports/silver/<run_id>/):
    1) silver_run_human_report.md   (human-readable Markdown report)
    2) silver_run_agent_context.json (structured context for downstream agents)

IMPORTANT:
- This agent does NOT perform any numeric calculations or ML.
- It only describes business problems, scope options, KPI candidates, and
  segmentation/clustering opportunities based on the data and process context.
- It adds automated profiling for schema overview, inferred types, nulls,
  duplicates, key candidates, and suggested Silver transforms.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Analytics Process (1–10) – extended system context
# (based on the version adapted to your concrete data structure)
# --------------------------------------------------------------------
PROCESS_DESCRIPTION = r"""
Data Analytics Process (for customer, product, sales, location and category data)

Core tables:
- Customers: cst_info, CST_AZ12
- Products: prd_info, PX_CAT_G1V2
- Transactions: sales_details
- Locations: LOC_A101

1. Problem Definition & Objectives
   - Define clear business questions linked to customer, product and sales data.
   - Examples of potential business problems:
     * Declining repeat purchase rates or customer retention.
     * High return rates in specific product categories.
     * Strong regional differences in sales performance without clear explanation.
     * High dependency on discounts to achieve sales targets.
   - Why these are problems (impact / cost / risk / opportunity):
     * Impact: revenue loss, margin erosion, increased logistics cost.
     * Cost: churn-related LTV loss, inefficient marketing spend, misallocated inventory.
     * Risk: wrong pricing, wrong product mix, unreliable forecasts.
     * Opportunity: pricing optimization, better targeting, assortment optimization.
   - Stakeholders that may be affected:
     * C-level and executives (revenue, profitability).
     * Marketing (segmentation, targeting, acquisition cost).
     * Sales (conversion, pipeline quality, pricing strategy).
     * Operations & logistics (stock levels, fulfillment, delivery).
     * Finance (budgeting, forecasting).
     * Product management (category performance, lifecycle).
   - Decisions that analysis should support:
     * Which customers or segments to target or retain.
     * Which product categories to expand, maintain or phase out.
     * How to allocate marketing budget across channels and segments.
     * How to adjust price levels, discount strategies or promotions.
   - Assumptions that can be derived and later tested:
     * Customers with shorter delivery times have higher repeat purchase probability.
     * Certain product categories perform better in specific countries.
     * Discount-heavy behaviour may correlate with higher return rates or churn.
     * Age or other demographics may correlate with higher LTV.

2. Data Identification & Understanding
   - Tables: cst_info, CST_AZ12, prd_info, LOC_A101, PX_CAT_G1V2, sales_details.
   - Clarify key relationships (customer key, product key, location ID).
   - Distinguish master data (customers, products, locations, categories) from transactional data (sales_details).
   - Ensure consistent key usage and referential integrity.

3. Data Ingestion & Integration (Bronze)
   - Raw data from sources as CSV in Bronze (no transformations).
   - 1:1 file mapping to operational tables.
   - Bronze is about fidelity and traceability, not cleanliness.

4. Data Cleaning & Transformation (Bronze -> Silver)
   - Whitespace trimming, empty strings -> NA.
   - Type standardization for IDs, date columns, numeric columns.
   - Harmonized codes (e.g. gender, flags like MAINTENANCE).
   - No aggregations, no star schema; Silver keeps the original grain per table.
   - Silver is the "clean but not yet aggregated" layer.

5. Exploratory Data Analysis (on Silver, structural)
   - Focus on structural and quality checks (cardinalities, nulls, value ranges).
   - Identify obvious structural data-quality issues (missing keys, inconsistent dimensions).
   - Provide indicators that a later analysis or modeling step can rely on.

6. Modeling & Analytical Methods
   - Silver prepares the ground for:
     * Customer views (per customer aggregated behaviour if desired, in later layers).
     * Product views (per product/category performance).
     * Sales fact tables (for BI and analytics).
   - The actual modeling (predictive, prescriptive, clustering) happens in downstream steps.

7. Validation & Quality Control
   - Per-table checks: row counts, schema, dtypes, obvious breaks.
   - Logging of successes/errors, checks for orphan keys.
   - Assess readiness of the Silver layer for:
     * Business reporting.
     * BI tools (e.g. Tableau).
     * ML feature engineering.

8. Interpretation & Communication
   - Summarise what the Silver run achieved and what it did not.
   - Describe data quality and structural readiness for:
     * Business problem exploration.
     * KPI calculation and dashboarding.
     * Segmentation and clustering work.
   - Highlight which questions can be answered well or poorly with the current Silver state.

9. Operationalization
   - Silver layer as a stable layer for BI, ad-hoc queries and downstream pipelines.
   - Clean metadata for lineage (Bronze -> Silver).
   - Standardisation that allows consistent KPI definitions across tools (e.g. Tableau).

10. Monitoring & Continuous Improvement
   - Repeatable runs with comparable metrics across time.
   - Trend observation for data quality and pipeline stability.
   - Feedback loop back to sources or ETL logic if recurring issues appear.


Additional conceptual catalogues the agent should use descriptively (never to perform calculations):

A. Business Problems Catalogue
   - Provide examples of possible business problems, including:
     * Name / short label.
     * Description of the problem.
     * Impact, cost, risk and opportunity.
     * Stakeholders affected.
     * Decisions that should be supported.
     * Assumptions that could be tested.

B. Scope Definition Options
   - Time scope examples:
     * Last 12 months, year-to-date, rolling windows (e.g. 90 days).
   - Geographic scope examples:
     * DACH, EMEA, specific countries from LOC_A101.
   - Data scope examples:
     * Only customers with at least one purchase.
     * Only active customers (purchases in last N days).
     * Only products with minimum sales volume.
   - System/source scope:
     * CRM for customer data, ERP for sales, product systems for product data, etc.
   - Output format expectations:
     * Dashboards, static reports, ML-ready feature tables, etc.

C. KPI Definition Catalogue (for BI/Tableau usage)
   - For each KPI, define:
     * Name.
     * Business description.
     * Formula (high-level, not tied to a specific SQL dialect).
     * Typical usage in Tableau or BI.
   - Example KPIs:
     * Conversion Rate.
       - Formula: (Number of purchases / number of unique customers or visits) * 100%.
     * Customer Lifetime Value (LTV, simplified).
       - Formula: (Average order value * purchase frequency * customer lifespan).
     * Return Rate.
       - Formula: (Returned units / sold units) * 100%.
     * Cost per Acquisition (CPA).
       - Formula: marketing spend / number of newly acquired customers.
     * Revenue Growth %.
       - Formula: ((Revenue_period_2 - Revenue_period_1) / Revenue_period_1) * 100%.
     * Average Order Value (AOV).
       - Formula: total revenue / total number of orders.
     * Purchase Frequency.
       - Formula: number of orders / number of unique customers.
     * Customer Retention Rate.
       - Formula: ((customers_end_period - new_customers) / customers_start_period) * 100%.

D. Segmentation & Clustering for ML
   - Never perform ML in this agent, but describe:
     * Useful features for segmentation:
       - Demographics (age from DOB in CST_AZ12, gender, country from LOC_A101).
       - Behaviour (recency, frequency, monetary value, discount usage).
       - Product preferences (categories from PX_CAT_G1V2 joined to prd_info and sales_details).
     * Typical methods:
       - K-Means, hierarchical clustering, DBSCAN.
       - RFM-based segmentation (Recency, Frequency, Monetary value).
       - Market basket analysis (for product affinity).
     * Example segment descriptions:
       - High-value loyal customers.
       - Discount-sensitive customers.
       - Seasonal category shoppers.
       - One-time buyers.
"""


# --------------------------------------------------------------------
# OpenAI client & helpers
# --------------------------------------------------------------------
def _build_openai_client() -> OpenAI:
    load_dotenv()

    api_key = (
        os.getenv("OPEN_AI_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "No OPEN_AI_KEY or OPENAI_API_KEY found in environment/.env "
            "- cannot call OpenAI LLM."
        )

    api_key = api_key.strip()
    if len(api_key) < 20:
        raise RuntimeError(
            "OpenAI API key found but appears too short; check environment configuration."
        )

    try:
        client = OpenAI(api_key=api_key)
    except Exception as exc:
        raise RuntimeError("Failed to initialize OpenAI client.") from exc
    return client


def _read_text(path: Path) -> str:
    if not path.exists():
        logger.warning("Text file not found: %s", path)
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("Failed to read text file: %s", path)
        raise RuntimeError(f"Failed to read text file: {path}") from exc


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("YAML file not found: %s", path)
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.exception("Failed to read YAML file: %s", path)
        raise RuntimeError(f"Failed to read YAML file: {path}") from exc


# --------------------------------------------------------------------
# Profiling helpers
# --------------------------------------------------------------------
def _detect_datetime_format(values: pd.Series) -> Optional[str]:
    sample = values.dropna().astype(str).str.strip()
    if sample.empty:
        return None
    sample = sample.head(20)

    format_patterns = [
        ("%Y-%m-%d %H:%M:%S", r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
        ("%Y-%m-%d %H:%M", r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
        ("%m/%d/%Y %H:%M:%S", r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}:\d{2}$"),
        ("%m/%d/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%Y/%m/%d", r"^\d{4}/\d{2}/\d{2}$"),
    ]

    for fmt, pattern in format_patterns:
        if sample.str.match(pattern).all():
            return fmt

    return None


def _infer_series_type(series: pd.Series) -> str:
    cleaned = series.dropna()
    if cleaned.empty:
        return "unknown"

    if cleaned.dtype == object:
        cleaned = cleaned.astype(str).str.strip()
        cleaned = cleaned[cleaned != ""]
        if cleaned.empty:
            return "unknown"

    numeric = pd.to_numeric(cleaned, errors="coerce")
    numeric_ratio = float(numeric.notna().mean())

    detected_format = _detect_datetime_format(cleaned)
    if detected_format:
        datetime_values = pd.to_datetime(cleaned, errors="coerce", format=detected_format)
    else:
        datetime_values = pd.to_datetime(cleaned, errors="coerce")
    datetime_ratio = float(datetime_values.notna().mean())

    if numeric_ratio >= 0.9:
        if (numeric.dropna() % 1 == 0).all():
            return "integer"
        return "float"

    if datetime_ratio >= 0.9:
        return "datetime"

    if cleaned.dtype == object:
        lowered = cleaned.astype(str).str.lower()
        bool_like = lowered.isin({"true", "false", "yes", "no", "0", "1"})
        if bool_like.mean() >= 0.9:
            return "boolean"

    return "string"


def _detect_trim_needed(series: pd.Series) -> bool:
    if series.dtype != object:
        return False
    stripped = series.astype(str).str.strip()
    return (stripped != series.astype(str)).any()


def _profile_table(df: pd.DataFrame, filename: str) -> Dict[str, Any]:
    rows = len(df)
    columns = list(df.columns)
    inferred_types: Dict[str, str] = {}
    null_counts: Dict[str, int] = {}
    key_candidates: List[Dict[str, Any]] = []
    suggested_transforms: List[str] = []

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        suggested_transforms.append(
            f"Remove or consolidate {duplicate_rows} duplicate rows in {filename}."
        )

    for col in columns:
        series = df[col]
        nulls = int(series.isna().sum())
        if series.dtype == object:
            nulls += int((series == "").sum())
        null_counts[col] = nulls

        inferred = _infer_series_type(series)
        inferred_types[col] = inferred

        dtype_name = str(series.dtype)
        col_lower = col.lower()
        if inferred in {"integer", "float"} and dtype_name == "object":
            suggested_transforms.append(f"Cast {col} to numeric ({inferred}).")
        if inferred == "datetime" and dtype_name == "object":
            suggested_transforms.append(f"Parse {col} as datetime.")
        if _detect_trim_needed(series):
            suggested_transforms.append(f"Trim whitespace in {col}.")
        if nulls > 0:
            suggested_transforms.append(f"Standardize missing values in {col}.")

        unique_non_null = int(series.nunique(dropna=True))
        uniqueness_ratio = (unique_non_null / rows) if rows else 0.0
        if nulls == 0 and unique_non_null == rows and rows > 0:
            key_candidates.append(
                {"column": col, "reason": "unique_non_null"}
            )
        elif ("id" in col_lower or col_lower.endswith("_id") or col_lower.endswith("key")) and uniqueness_ratio >= 0.98:
            key_candidates.append(
                {
                    "column": col,
                    "reason": f"high_uniqueness_{uniqueness_ratio:.2%}",
                }
            )

    if not suggested_transforms:
        suggested_transforms.append("No obvious Silver transformations detected.")

    return {
        "table": filename,
        "row_count": rows,
        "column_count": len(columns),
        "columns": columns,
        "inferred_types": inferred_types,
        "null_counts": null_counts,
        "duplicate_rows": duplicate_rows,
        "key_candidates": key_candidates,
        "suggested_silver_transforms": sorted(set(suggested_transforms)),
    }


def _profile_bronze_run(data_dir: Path) -> Dict[str, Any]:
    tables: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []
    for csv_path in sorted(data_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_path)
            tables[csv_path.name] = _profile_table(df, csv_path.name)
        except Exception as exc:
            logger.exception("Failed to profile CSV: %s", csv_path.name)
            error_message = str(exc)
            errors.append({"file": csv_path.name, "error": error_message})
            tables[csv_path.name] = {"error": error_message}

    schema_overview = {
        "table_count": len(tables),
        "tables": [
            {
                "table": tbl["table"],
                "row_count": tbl["row_count"],
                "column_count": tbl["column_count"],
            }
            for tbl in tables.values()
            if "error" not in tbl
        ],
    }

    return {
        "schema_overview": schema_overview,
        "tables": tables,
        "errors": errors,
    }


def _render_profile_markdown(profile: Dict[str, Any]) -> str:
    lines = [
        "## Automated Bronze Profiling (for Silver Draft)",
        "",
        "### Schema Overview",
    ]
    overview = profile.get("schema_overview", {})
    for table in overview.get("tables", []):
        lines.append(
            f"- {table['table']}: {table['row_count']} rows, {table['column_count']} columns"
        )

    for table_name, table in profile.get("tables", {}).items():
        if "error" in table:
            lines.extend(
                [
                    "",
                    f"### Table: {table_name}",
                    f"- Error: {table['error']}",
                ]
            )
            continue
        lines.extend(
            [
                "",
                f"### Table: {table_name}",
                f"- Rows: {table['row_count']}",
                f"- Columns: {', '.join(table['columns'])}",
                "- Inferred types:",
            ]
        )
        for col, inferred in table["inferred_types"].items():
            lines.append(f"  - {col}: {inferred}")
        lines.append("- Null counts:")
        for col, nulls in table["null_counts"].items():
            lines.append(f"  - {col}: {nulls}")
        lines.append(f"- Duplicate rows: {table['duplicate_rows']}")
        lines.append("- Key candidates:")
        if table["key_candidates"]:
            for candidate in table["key_candidates"]:
                lines.append(
                    f"  - {candidate['column']}: {candidate['reason']}"
                )
        else:
            lines.append("  - None detected")
        lines.append("- Suggested Silver transforms:")
        for transform in table["suggested_silver_transforms"]:
            lines.append(f"  - {transform}")

    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------
# Main function, called from load_2_silver_layer.py
# --------------------------------------------------------------------
def run_report_agent(
    run_id: str,
    silver_run_id: str | None = None,
    model_name: str = "gpt-4.1-mini",
) -> None:
    """
    Produces two outputs in tmp/draft_reports/silver/<run_id>/:
      - silver_run_human_report.md
      - silver_run_agent_context.json
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Starting Silver draft report generation. run_id=%s", run_id)
    start_time = time.monotonic()

    bronze_run_dir = Path("artifacts") / "bronze" / run_id
    data_dir = bronze_run_dir / "data"
    reports_dir = bronze_run_dir / "reports"

    metadata_path = data_dir / "metadata.yaml"
    log_path = data_dir / "run_log.txt"
    html_report_path = reports_dir / "elt_report.html"

    client = _build_openai_client()

    # Paths
    output_dir = Path("tmp") / "draft_reports" / "silver" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_text = _read_text(metadata_path)
    log_text = _read_text(log_path)
    html_text = _read_text(html_report_path)
    metadata_dict = _read_yaml(metadata_path)

    logger.info("Profiling Bronze run artifacts.")
    profile = _profile_bronze_run(data_dir)
    profile_md = _render_profile_markdown(profile)
    generated_at = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------
    # 1) Human-readable report (Markdown)
    # ------------------------------------------------------------
    human_messages = [
        {
            "role": "system",
            "content": (
                "You are a senior Data & Analytics expert. "
                "You produce concise but complete reports for humans. "
                "Use the following Data Analytics process and catalogues as your guiding framework:\n\n"
                + PROCESS_DESCRIPTION
            ),
        },
        {
            "role": "user",
            "content": (
                "Create a human-readable Markdown report (in English) for this Silver-layer run.\n\n"
                f"Bronze run id: {run_id}\n"
                f"Silver run id (if available): {silver_run_id or 'N/A'}\n\n"
                "Input 1: metadata.yaml (YAML) from Bronze:\n"
                "-----------------------------\n"
                f"{metadata_text}\n\n"
                "Input 2: run_log.txt from Bronze:\n"
                "----------------------\n"
                f"{log_text}\n\n"
                "Input 3: HTML report (structure only, if helpful):\n"
                "---------------------------------------------------\n"
                f"{html_text[:8000]}\n\n"
                "Input 4: Automated Bronze profiling for Silver draft:\n"
                "-------------------------------------------------------\n"
                f"{json.dumps(profile, indent=2)}\n\n"
                "Requirements for the Markdown report:\n"
                "- Short executive summary at the top (3–5 bullet points).\n"
                "- Sections aligned to the Data Analytics process (1–10), but only where relevant to this run.\n"
                "- Highlight data quality, structural integrity and readiness of the Silver layer.\n"
                "- Mention which source tables were processed and which failed (if any).\n"
                "- Do NOT perform any numeric calculations or statistics; stay conceptual.\n"
                "- Include a dedicated section for schema overview, inferred types, nulls, duplicates,\n"
                "  key candidates, and suggested Silver transforms (use the provided profiling inputs).\n"
                "- In addition, add four dedicated sections:\n"
                "  1) 'Potential business problems and decisions' – describe examples of business problems\n"
                "     that could be analysed based on the available tables, including impact, stakeholders,\n"
                "     decisions and assumptions (do not calculate any KPIs).\n"
                "  2) 'Scope definition options' – provide time, geography, data, system/source and output\n"
                "     scope options that a downstream agent or analyst could choose for further work.\n"
                "  3) 'KPI candidates for BI/Tableau' – list KPI definitions (name, description, high-level\n"
                "     formula) that would be suitable for Tableau dashboards, without computing any values.\n"
                "  4) 'Segmentation & clustering opportunities' – describe which features, methods and example\n"
                "     segments could be used in later ML workflows, again without running any models.\n"
                "- Focus on what is possible and how the Silver layer enables it, not on executing calculations.\n"
            ),
        },
    ]

    logger.info("Requesting human-readable report from OpenAI.")
    try:
        human_resp = client.chat.completions.create(
            model=model_name,
            messages=human_messages,
        )
    except Exception as exc:
        logger.exception("OpenAI call failed for human report generation.")
        raise RuntimeError("OpenAI call failed for human report generation.") from exc
    human_report_md = human_resp.choices[0].message.content or ""

    human_report_path = output_dir / "silver_run_human_report.md"
    human_report_path.write_text(
        f"{human_report_md}\n\n{profile_md}",
        encoding="utf-8",
    )
    logger.info("Wrote human-readable report: %s", human_report_path)

    # ------------------------------------------------------------
    # 2) Machine-readable context for downstream agents (JSON)
    # ------------------------------------------------------------
    summary = metadata_dict.get("summary", {}) if isinstance(metadata_dict, dict) else {}
    files_total = summary.get("files_total", 0)
    files_success = summary.get("files_success", 0)
    files_failed = summary.get("files_failed", 0)

    tables_meta = metadata_dict.get("tables", {}) if isinstance(metadata_dict, dict) else {}
    tables: Dict[str, Any] = {}
    for fname, tmeta in tables_meta.items():
        if not isinstance(tmeta, dict):
            continue
        tables[fname] = {
            "status": tmeta.get("status", "UNKNOWN"),
            "rows_in": tmeta.get("rows_in", 0),
            "rows_out": tmeta.get("rows_out", 0),
            "schema_in": tmeta.get("schema_in", []),
            "schema_out": tmeta.get("schema_out", []),
        }

    json_data = {
        "run_id": run_id,
        "silver_run_id": silver_run_id,
        "layer": "silver",
        "source_layer": "bronze",
        "bronze_run_id": run_id,
        "generated_at_utc": generated_at,
        "files_total": files_total,
        "files_success": files_success,
        "files_failed": files_failed,
        "bronze_tables": tables,
        "profile": profile,
        "schema_overview": profile.get("schema_overview"),
    }

    json_out_path = output_dir / "silver_run_agent_context.json"
    json_out_path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote agent context JSON: %s", json_out_path)
    elapsed = time.monotonic() - start_time
    logger.info("Completed Silver draft report generation in %.2fs.", elapsed)


# Optional: manual test
if __name__ == "__main__":
    # Example call (adjust paths or read from args as needed)
    example_run_id = "TEST_000000_#abcdef"

    run_report_agent(
        run_id=example_run_id,
        silver_run_id="DUMMY_SILVER",
    )
