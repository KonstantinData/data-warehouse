"""
load_2_report_agent.py

Called at the end of load_2_silver_layer.py.

Responsibilities:
- Reads metadata.yaml and run_log.txt of the Silver run
- Uses the Data Analytics Process (steps 1–10) as guiding framework
- Calls an OpenAI LLM using environment variables (OPEN_AI_KEY / OPENAI_API_KEY)
- Produces:
    1) silver_run_human_report.md   (human-readable Markdown report)
    2) silver_run_agent_context.json (structured context for downstream agents)

IMPORTANT:
- This agent does NOT perform any numeric calculations or ML.
- It only describes business problems, scope options, KPI candidates, and
  segmentation/clustering opportunities based on the data and process context.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from openai import OpenAI

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

    client = OpenAI(api_key=api_key)
    return client


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_llm_json(text: str) -> Dict[str, Any]:
    """
    Try to robustly extract a JSON object from an LLM response.

    Strategy:
    - Strip whitespace.
    - Remove surrounding code fences if present.
    - Extract the largest {...} block.
    - Attempt json.loads on the extracted text.
    """
    stripped = text.strip()

    # Remove ```json ... ``` or ``` ... ``` fences if present
    if stripped.startswith("```"):
        parts = stripped.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            candidate_lines = candidate.splitlines()
            if candidate_lines and candidate_lines[0].strip().lower().startswith("json"):
                candidate_lines = candidate_lines[1:]
            stripped = "\n".join(candidate_lines).strip()

    # Extract the main JSON block between first '{' and last '}'
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
    else:
        candidate = stripped

    return json.loads(candidate)


# --------------------------------------------------------------------
# Main function, called from load_2_silver_layer.py
# --------------------------------------------------------------------
def run_report_agent(
    silver_run_id: str,
    bronze_run_id: str,
    silver_run_dir: str,
    metadata_path: str,
    log_path: str,
    html_report_path: str,
    model_name: str = "gpt-4.1-mini",
) -> None:
    """
    Produces two outputs in the reports/ folder of the Silver run:
      - silver_run_human_report.md
      - silver_run_agent_context.json
    """

    client = _build_openai_client()

    # Paths
    silver_run_dir_path = Path(silver_run_dir)
    reports_dir = silver_run_dir_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    metadata_text = _read_text(Path(metadata_path))
    log_text = _read_text(Path(log_path))
    html_text = _read_text(Path(html_report_path))
    metadata_dict = _read_yaml(Path(metadata_path))  # used for fallback JSON

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
                f"Silver run id: {silver_run_id}\n"
                f"Bronze run id: {bronze_run_id}\n\n"
                "Input 1: metadata.yaml (YAML):\n"
                "-----------------------------\n"
                f"{metadata_text}\n\n"
                "Input 2: run_log.txt:\n"
                "----------------------\n"
                f"{log_text}\n\n"
                "Input 3: HTML report (structure only, if helpful):\n"
                "---------------------------------------------------\n"
                f"{html_text[:8000]}\n\n"
                "Requirements for the Markdown report:\n"
                "- Short executive summary at the top (3–5 bullet points).\n"
                "- Sections aligned to the Data Analytics process (1–10), but only where relevant to this run.\n"
                "- Highlight data quality, structural integrity and readiness of the Silver layer.\n"
                "- Mention which source tables were processed and which failed (if any).\n"
                "- Do NOT perform any numeric calculations or statistics; stay conceptual.\n"
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

    human_resp = client.chat.completions.create(
        model=model_name,
        messages=human_messages,
    )
    human_report_md = human_resp.choices[0].message.content or ""

    human_report_path = reports_dir / "silver_run_human_report.md"
    human_report_path.write_text(human_report_md, encoding="utf-8")

    # ------------------------------------------------------------
    # 2) Machine-readable context for downstream agents (JSON)
    # ------------------------------------------------------------
    json_messages = [
        {
            "role": "system",
            "content": (
                "You are a data-engineering orchestrator. "
                "Your task is to produce a compact JSON summary of a Silver-layer ETL run, "
                "to be consumed by a downstream agent in another run.\n\n"
                "Use this Data Analytics process and the business/KPI/segmentation catalogues as conceptual background:\n"
                + PROCESS_DESCRIPTION
            ),
        },
        {
            "role": "user",
            "content": (
                "From the following metadata.yaml and log text, derive a strict JSON object.\n\n"
                f"Silver run id: {silver_run_id}\n"
                f"Bronze run id: {bronze_run_id}\n\n"
                "metadata.yaml (YAML):\n"
                "----------------------\n"
                f"{metadata_text}\n\n"
                "run_log.txt:\n"
                "-------------\n"
                f"{log_text}\n\n"
                "Return ONLY valid JSON, no explanations, no comments.\n"
                "JSON schema (keys) MUST be exactly:\n"
                "{\n"
                '  \"run_id\": string,\n'
                '  \"bronze_run_id\": string,\n'
                '  \"layer\": \"silver\",\n'
                '  \"status\": \"SUCCESS\" | \"PARTIAL\" | \"FAILED\",\n'
                '  \"files_total\": integer,\n'
                '  \"files_success\": integer,\n'
                '  \"files_failed\": integer,\n'
                '  \"tables\": {\n'
                '     \"<filename>.csv\": {\n'
                '        \"status\": \"SUCCESS\" | \"FAILED\",\n'
                '        \"rows_in\": integer,\n'
                '        \"rows_out\": integer,\n'
                '        \"schema_in\": [string],\n'
                '        \"schema_out\": [string]\n'
                "     },\n"
                "     ...\n"
                "  },\n"
                '  \"data_analytics_process_focus\": [string],\n'
                '  \"quality_flags\": [string],\n'
                '  \"recommended_next_steps\": [string],\n'
                '  \"business_problems\": [\n'
                "     {\n"
                '       \"name\": string,\n'
                '       \"description\": string,\n'
                '       \"impact\": string,\n'
                '       \"stakeholders\": [string],\n'
                '       \"decisions\": [string],\n'
                '       \"assumptions\": [string]\n'
                "     }\n"
                "  ],\n"
                '  \"scope_definition\": {\n'
                '     \"time\": [string],\n'
                '     \"geography\": [string],\n'
                '     \"data\": [string],\n'
                '     \"systems\": [string],\n'
                '     \"outputs\": [string]\n'
                "  },\n"
                '  \"kpi_definitions\": [\n'
                "     {\n"
                '       \"name\": string,\n'
                '       \"description\": string,\n'
                '       \"formula\": string,\n'
                '       \"tableau_usage\": string\n'
                "     }\n"
                "  ],\n"
                '  \"segmentation_clustering\": {\n'
                '     \"features\": [string],\n'
                '     \"methods\": [string],\n'
                '     \"example_segments\": [string]\n'
                "  }\n"
                "}\n"
                "Populate the fields from the metadata/logs as precisely as possible, but:\n"
                "- Do NOT compute any numeric KPIs.\n"
                "- Do NOT run or simulate any clustering or ML.\n"
                "- Use the catalogues in the system message to provide generic but meaningful examples.\n"
                "If you are unsure, make a best effort guess but stay internally consistent.\n"
            ),
        },
    ]

    json_resp = client.chat.completions.create(
        model=model_name,
        messages=json_messages,
    )
    json_raw = json_resp.choices[0].message.content or ""

    # Robust parsing with fallback
    try:
        json_data = _parse_llm_json(json_raw)
    except Exception:
        # Fallback: build a minimal valid JSON using metadata.yaml only,
        # and flag that the LLM JSON could not be parsed.
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
            "run_id": silver_run_id,
            "bronze_run_id": bronze_run_id,
            "layer": "silver",
            "status": "PARTIAL" if files_failed and files_failed > 0 else "SUCCESS",
            "files_total": files_total,
            "files_success": files_success,
            "files_failed": files_failed,
            "tables": tables,
            "data_analytics_process_focus": [
                "Data Cleaning & Transformation",
                "Validation & Quality Control",
                "Readiness for BI/ML",
            ],
            "quality_flags": [
                "LLM_JSON_PARSE_FAILED",
            ],
            "recommended_next_steps": [
                "Inspect metadata.yaml and run_log.txt manually.",
                "Re-run the LLM-based context generation if necessary.",
            ],
            # Provide empty but schema-conforming structures
            "business_problems": [],
            "scope_definition": {
                "time": [],
                "geography": [],
                "data": [],
                "systems": [],
                "outputs": [],
            },
            "kpi_definitions": [],
            "segmentation_clustering": {
                "features": [],
                "methods": [],
                "example_segments": [],
            },
        }

    json_out_path = reports_dir / "silver_run_agent_context.json"
    json_out_path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# Optional: manual test
if __name__ == "__main__":
    # Example call (adjust paths or read from args as needed)
    example_run_id = "TEST_000000_#abcdef"
    example_bronze = "DUMMY_BRONZE"
    example_dir = "artifacts/silver/" + example_run_id
    example_metadata = os.path.join(example_dir, "data", "metadata.yaml")
    example_log = os.path.join(example_dir, "data", "run_log.txt")
    example_html = os.path.join(example_dir, "reports", "elt_report.html")

    run_report_agent(
        silver_run_id=example_run_id,
        bronze_run_id=example_bronze,
        silver_run_dir=example_dir,
        metadata_path=example_metadata,
        log_path=example_log,
        html_report_path=example_html,
    )
