"""
load_3_gold_layer_draft_agent.py

Role:
- Drafting-only agent for the Gold layer.
- It does NOT generate or execute ETL code.
- It reads the latest (or given) Silver-layer run context and metadata,
  calls a live OpenAI LLM, and produces:

  1) gold_run_human_report.md     (human-readable Gold-layer design and rationale)
  2) gold_run_agent_context.json  (structured machine-readable plan for Gold marts)

Outputs are stored under:
  tmp/draft_reports/gold/<silver_run_id>/
    - gold_run_human_report.md
    - gold_run_agent_context.json

This agent is intended to work together with a static, hand-maintained
load_3_gold_layer.py implementation that reads gold_mart_plan.json (optionally)
to decide which marts to build or how to prioritize them.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
from openai import OpenAI


LOGGER = logging.getLogger(__name__)

RUN_ID_PATTERN = r"^(?P<ts>\d{8}_\d{6})_#(?P<suffix>[A-Za-z0-9]+)$"
RUN_ID_RE = re.compile(RUN_ID_PATTERN)
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.5
DEFAULT_LOG_LEVEL = "INFO"
ENV_SNAPSHOT_KEYS = (
    "OPEN_AI_KEY",
    "OPENAI_API_KEY",
    "GOLD_DRAFT_MODEL",
    "GOLD_DRAFT_MAX_RETRIES",
    "GOLD_DRAFT_BACKOFF_SECONDS",
    "GOLD_DRAFT_LOG_LEVEL",
)
REDACTED_ENV_KEYS = {"OPEN_AI_KEY", "OPENAI_API_KEY"}
REQUIRED_PLAN_KEYS = {
    "silver_run_id",
    "gold_layer_objective",
    "dimensions",
    "facts",
    "marts",
    "risks",
    "assumptions",
    "next_steps",
}


class PlanningError(RuntimeError):
    """Base class for planning failures."""


class ConfigError(PlanningError):
    """Configuration is missing or invalid."""


class FileReadError(PlanningError):
    """Raised when reading files fails."""


class PlanParseError(PlanningError):
    """Raised when LLM plan parsing fails."""


class PlanValidationError(PlanningError):
    """Raised when LLM plan schema validation fails."""


class LLMCallError(PlanningError):
    """Raised when LLM calls fail after retries."""


@dataclass(frozen=True)
class AgentConfig:
    model_name: str
    max_retries: int
    backoff_seconds: float
    log_level: str
    api_key: str


# ---------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------
def find_repo_root(start: Path) -> Path:
    """
    Walk up from 'start' until we find a directory containing both
    'artifacts' and 'src'. Fallback: two levels up.
    """
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "artifacts").exists() and (cur / "src").exists():
            return cur
        cur = cur.parent
    return start.resolve().parents[2]


def extract_run_suffix(run_id: str) -> str | None:
    match = RUN_ID_RE.match(run_id)
    return match.group("suffix") if match else None


def find_latest_silver_run_id(
    silver_root: Path,
    *,
    suffix: str | None = None,
    require_agent_context: bool = False,
) -> str:
    """
    Return the lexicographically latest directory name under silver_root.
    Assumes run_id pattern YYYYMMDD_HHMMSS_#suffix, so lexicographic
    sorting corresponds to chronological order.
    """
    if not silver_root.exists():
        raise FileNotFoundError(f"Silver root does not exist: {silver_root}")

    run_ids: List[str] = []
    for p in silver_root.iterdir():
        if not p.is_dir():
            continue
        if not RUN_ID_RE.match(p.name):
            continue
        if suffix and extract_run_suffix(p.name) != suffix:
            continue
        if require_agent_context and not (p / "reports" / "silver_run_agent_context.json").exists():
            continue
        run_ids.append(p.name)

    if not run_ids:
        raise FileNotFoundError(f"No Silver runs found under: {silver_root}")

    return sorted(run_ids)[-1]


def read_text(path: Path) -> str:
    try:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileReadError(f"Failed to read file: {path}") from exc


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise FileReadError(f"Failed to parse JSON file: {path}") from exc


def read_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise FileReadError(f"Failed to parse YAML file: {path}") from exc
    except OSError as exc:
        raise FileReadError(f"Failed to read YAML file: {path}") from exc


def validate_run_id(run_id: str) -> None:
    if Path(run_id).name != run_id:
        raise ValueError("Run id must not contain path separators.")
    if not RUN_ID_RE.match(run_id):
        raise ValueError(
            f"Run id '{run_id}' does not match expected pattern {RUN_ID_PATTERN}."
        )


def resolve_silver_run_id(silver_root: Path, requested_run_id: str | None) -> str:
    if requested_run_id:
        validate_run_id(requested_run_id)
        return requested_run_id
    return find_latest_silver_run_id(silver_root)


def resolve_silver_context_run_id(silver_root: Path, silver_run_id: str) -> str:
    agent_ctx_path = silver_root / silver_run_id / "reports" / "silver_run_agent_context.json"
    if agent_ctx_path.exists():
        return silver_run_id

    suffix = extract_run_suffix(silver_run_id)
    if suffix:
        try:
            fallback_run_id = find_latest_silver_run_id(
                silver_root,
                suffix=suffix,
                require_agent_context=True,
            )
        except FileNotFoundError:
            fallback_run_id = None
        if fallback_run_id:
            LOGGER.warning(
                "Requested Silver run missing context; falling back to latest run with "
                "suffix #%s: %s",
                suffix,
                fallback_run_id,
            )
            return fallback_run_id

    try:
        fallback_run_id = find_latest_silver_run_id(silver_root, require_agent_context=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "No Silver runs with silver_run_agent_context.json found under: "
            f"{silver_root}"
        ) from exc

    LOGGER.warning(
        "Requested Silver run missing context; falling back to latest run with "
        "available context: %s",
        fallback_run_id,
    )
    return fallback_run_id


# ---------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------
def build_llm_client(api_key: str) -> OpenAI:
    if not api_key:
        raise ConfigError(
            "No OPEN_AI_KEY or OPENAI_API_KEY found; cannot call OpenAI LLM."
        )
    return OpenAI(api_key=api_key)


def _parse_json_from_llm(raw: str) -> Dict[str, Any]:
    """
    Robustly extract JSON from an LLM response:

    - Strip leading/trailing whitespace
    - Remove ```json ... ``` or ``` ... ``` fences if present
    - Extract the main {...} block
    - json.loads on the result
    """
    text = raw.strip()

    # Remove code fences if present
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            lines = candidate.splitlines()
            if lines and lines[0].strip().lower().startswith("json"):
                lines = lines[1:]
            text = "\n".join(lines).strip()

    # Extract first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanParseError("Failed to parse JSON from LLM response.") from exc


def validate_gold_plan(plan: Dict[str, Any]) -> None:
    missing = REQUIRED_PLAN_KEYS - set(plan)
    if missing:
        raise PlanValidationError(f"Gold plan missing keys: {sorted(missing)}")
    list_fields = ["dimensions", "facts", "marts", "risks", "assumptions", "next_steps"]
    for field in list_fields:
        if not isinstance(plan.get(field), list):
            raise PlanValidationError(f"Gold plan field '{field}' must be a list.")
    for section in ("dimensions", "facts", "marts"):
        for item in plan.get(section, []):
            if not isinstance(item, dict):
                raise PlanValidationError(
                    f"Gold plan section '{section}' must contain objects."
                )


def load_config() -> AgentConfig:
    model_name = os.getenv("GOLD_DRAFT_MODEL", DEFAULT_MODEL)
    log_level = os.getenv("GOLD_DRAFT_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    try:
        max_retries = int(os.getenv("GOLD_DRAFT_MAX_RETRIES", DEFAULT_MAX_RETRIES))
        backoff_seconds = float(
            os.getenv("GOLD_DRAFT_BACKOFF_SECONDS", DEFAULT_BACKOFF_SECONDS)
        )
    except ValueError as exc:
        raise ConfigError("Retry configuration must be numeric.") from exc

    if max_retries < 1:
        raise ConfigError("GOLD_DRAFT_MAX_RETRIES must be >= 1.")
    if backoff_seconds <= 0:
        raise ConfigError("GOLD_DRAFT_BACKOFF_SECONDS must be > 0.")

    api_key = os.getenv("OPEN_AI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConfigError(
            "No OPEN_AI_KEY or OPENAI_API_KEY found; cannot call OpenAI LLM."
        )

    return AgentConfig(
        model_name=model_name,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        log_level=log_level,
        api_key=api_key,
    )


def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def build_env_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    for key in ENV_SNAPSHOT_KEYS:
        if key in os.environ:
            snapshot[key] = (
                "<redacted>" if key in REDACTED_ENV_KEYS else os.environ[key]
            )
    return snapshot


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise FileReadError(f"Failed to write JSON file: {path}") from exc


def with_retry(
    action: str,
    func,
    *,
    max_retries: int,
    backoff_seconds: float,
) -> Any:
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            if attempt >= max_retries:
                raise LLMCallError(f"{action} failed after {attempt} attempts.") from exc
            sleep_for = backoff_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "%s failed on attempt %s/%s: %s. Retrying in %.1fs.",
                action,
                attempt,
                max_retries,
                exc,
                sleep_for,
            )
            time.sleep(sleep_for)


# ---------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------
def create_gold_design_report(
    client: OpenAI,
    silver_run_id: str,
    silver_agent_context: Dict[str, Any],
    silver_metadata: Dict[str, Any],
    *,
    model_name: str,
    max_retries: int,
    backoff_seconds: float,
) -> str:
    """
    Ask the LLM to produce a human-readable Gold-layer design report
    in Markdown format, based on the Silver context and metadata.
    """
    system_msg = {
        "role": "system",
        "content": (
            "You are a senior data warehouse and BI architect. "
            "You design clear, pragmatic Gold-layer architectures on top of "
            "a Silver layer. Your writing style is concise, structured and "
            "business-friendly. You never output code in this mode, only "
            "Markdown explanations."
        ),
    }

    user_msg = {
        "role": "user",
        "content": (
            "You are given a Silver-layer ETL run context and metadata. "
            "Use them to design a Phase-1 Gold layer that serves BI and "
            "analytics (NO ML feature store in this step).\n\n"
            f"Silver run id: {silver_run_id}\n\n"
            "Silver agent context (JSON):\n"
            "----------------------------\n"
            f"{json.dumps(silver_agent_context, indent=2)}\n\n"
            "Silver metadata.yaml (YAML):\n"
            "----------------------------\n"
            f"{yaml.safe_dump(silver_metadata, sort_keys=False)}\n\n"
            "Write a Markdown report with the following structure:\n"
            "1. Executive summary (3–6 bullet points)\n"
            "2. Available Silver tables and their role (sales, customers, products, locations, categories)\n"
            "3. Proposed Gold-layer objectives (for BI & analytics only)\n"
            "4. Recommended Gold Data Marts (dimensions, facts, aggregates, wide-table), "
            "   with a short description per mart:\n"
            "   - business purpose\n"
            "   - primary keys, grain\n"
            "   - main measures and dimensions\n"
            "5. Join and data-quality considerations (keys, cardinalities, potential pitfalls)\n"
            "6. Risks & assumptions (what might be missing or fragile)\n"
            "7. Recommended next steps for implementation and testing\n"
            "\n"
            "Do NOT output any Python or SQL code. Focus on design, rationale and structure."
        ),
    }

    def _call():
        return client.chat.completions.create(
            model=model_name,
            messages=[system_msg, user_msg],
            temperature=0.2,
        )

    resp = with_retry(
        "Gold design report LLM call",
        _call,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )

    content = resp.choices[0].message.content or ""
    return content.strip()


def create_gold_mart_plan(
    client: OpenAI,
    silver_run_id: str,
    silver_agent_context: Dict[str, Any],
    silver_metadata: Dict[str, Any],
    *,
    model_name: str,
    max_retries: int,
    backoff_seconds: float,
) -> Dict[str, Any]:
    """
    Ask the LLM to produce a strict JSON Gold-layer plan that a static
    Gold-runner can consume.

    The plan does NOT contain code, only structure:
    - dimensions, facts, and marts
    - grain, keys, measures
    - SCD guidance and aggregation opportunities
    """
    system_msg = {
        "role": "system",
        "content": (
            "You are a data warehouse orchestrator. "
            "Your task is to produce a STRICT JSON plan for Gold-layer Data Marts "
            "based on a Silver-layer context. You do NOT output any code, only JSON."
        ),
    }

    user_msg = {
        "role": "user",
        "content": (
            "From the following Silver context and metadata, derive a Gold-layer mart plan.\n\n"
            f"Silver run id: {silver_run_id}\n\n"
            "Silver agent context (JSON):\n"
            "----------------------------\n"
            f"{json.dumps(silver_agent_context, indent=2)}\n\n"
            "Silver metadata.yaml (YAML):\n"
            "----------------------------\n"
            f"{yaml.safe_dump(silver_metadata, sort_keys=False)}\n\n"
            "Return ONLY valid JSON (no Markdown, no comments) with the following schema:\n"
            "{\n"
            '  \"silver_run_id\": string,\n'
            '  \"gold_layer_objective\": string,\n'
            '  \"dimensions\": [\n'
            "    {\n"
            '      \"name\": string,\n'
            '      \"source_tables\": [string],\n'
            '      \"grain\": string,\n'
            '      \"primary_keys\": [string],\n'
            '      \"attributes\": [string],\n'
            '      \"scd_guidance\": string,\n'
            '      \"notes\": [string]\n'
            "    }\n"
            "  ],\n"
            '  \"facts\": [\n'
            "    {\n"
            '      \"name\": string,\n'
            '      \"source_tables\": [string],\n'
            '      \"grain\": string,\n'
            '      \"primary_keys\": [string],\n'
            '      \"measures\": [string],\n'
            '      \"dimensions\": [string],\n'
            '      \"aggregation_opportunities\": [string],\n'
            '      \"notes\": [string]\n'
            "    }\n"
            "  ],\n"
            '  \"marts\": [\n'
            "    {\n"
            '      \"name\": string,\n'
            '      \"type\": \"dim\" | \"fact\" | \"agg\" | \"wide\" | \"other\",\n'
            '      \"priority\": \"mandatory\" | \"optional\",\n'
            '      \"source_tables\": [string],\n'
            '      \"grain\": string,\n'
            '      \"primary_keys\": [string],\n'
            '      \"measures\": [string],\n'
            '      \"dimensions\": [string],\n'
            '      \"scd_guidance\": string,\n'
            '      \"aggregation_opportunities\": [string],\n'
            '      \"notes\": [string]\n'
            "    }\n"
            "  ],\n"
            '  \"risks\": [string],\n'
            '  \"assumptions\": [string],\n'
            '  \"next_steps\": [string]\n'
            "}\n"
            "\n"
            "Constraints and hints:\n"
            "- Use only table and column names that are present in the Silver context/metadata.\n"
            "- At minimum, consider marts for:\n"
            "  * gold_dim_customer\n"
            "  * gold_dim_product\n"
            "  * gold_dim_location\n"
            "  * gold_fact_sales\n"
            "  * gold_agg_exec_kpis\n"
            "  * gold_agg_product_performance\n"
            "  * gold_agg_geo_performance\n"
            "  * gold_wide_sales_enriched (may be optional if joins are risky)\n"
            "- For each mart, set 'priority' to 'mandatory' or 'optional' depending on how\n"
            "  critical it is for BI/analytics in Phase 1.\n"
            "- Provide explicit SCD guidance for dimensions (e.g., SCD1 vs SCD2).\n"
            "- Include aggregation opportunities for facts and marts.\n"
            "- Use 'notes' to capture important design decisions or caveats.\n"
        ),
    }

    def _call():
        return client.chat.completions.create(
            model=model_name,
            messages=[system_msg, user_msg],
            temperature=0.1,
        )

    resp = with_retry(
        "Gold mart plan LLM call",
        _call,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )

    raw = resp.choices[0].message.content or ""
    try:
        plan = _parse_json_from_llm(raw)
        validate_gold_plan(plan)
        return plan
    except (PlanParseError, PlanValidationError) as exc:
        LOGGER.error("Gold mart plan parsing/validation failed: %s", exc)
        # Fallback minimal plan if JSON parsing fails
        return {
            "silver_run_id": silver_run_id,
            "gold_layer_objective": (
                "Fallback Gold plan: basic dims/fact/aggregates due to JSON parse error."
            ),
            "dimensions": [
                {
                    "name": "gold_dim_customer",
                    "source_tables": ["cst_info"],
                    "grain": "one row per customer",
                    "primary_keys": ["customer_id"],
                    "attributes": ["customer_name", "country"],
                    "scd_guidance": "SCD Type 1 unless historical changes are required.",
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                },
                {
                    "name": "gold_dim_product",
                    "source_tables": ["prd_info"],
                    "grain": "one row per product",
                    "primary_keys": ["product_id"],
                    "attributes": ["product_name"],
                    "scd_guidance": "SCD Type 1 unless historical changes are required.",
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                },
            ],
            "facts": [
                {
                    "name": "gold_fact_sales",
                    "source_tables": ["sales_details"],
                    "grain": "one row per transaction/line",
                    "primary_keys": ["sales_id"],
                    "measures": ["sales_amount"],
                    "dimensions": ["customer_id", "product_id"],
                    "aggregation_opportunities": [
                        "daily sales by product",
                        "monthly sales by customer",
                    ],
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                }
            ],
            "marts": [
                {
                    "name": "gold_dim_customer",
                    "type": "dim",
                    "priority": "mandatory",
                    "source_tables": ["cst_info"],
                    "grain": "one row per customer",
                    "primary_keys": ["customer_id"],
                    "measures": [],
                    "dimensions": ["customer_name", "country"],
                    "scd_guidance": "SCD Type 1 unless historical changes are required.",
                    "aggregation_opportunities": [],
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                },
                {
                    "name": "gold_dim_product",
                    "type": "dim",
                    "priority": "mandatory",
                    "source_tables": ["prd_info"],
                    "grain": "one row per product",
                    "primary_keys": ["product_id"],
                    "measures": [],
                    "dimensions": ["product_name"],
                    "scd_guidance": "SCD Type 1 unless historical changes are required.",
                    "aggregation_opportunities": [],
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                },
                {
                    "name": "gold_fact_sales",
                    "type": "fact",
                    "priority": "mandatory",
                    "source_tables": ["sales_details"],
                    "grain": "one row per transaction/line",
                    "primary_keys": ["sales_id"],
                    "measures": ["sales_amount"],
                    "dimensions": ["customer_id", "product_id"],
                    "scd_guidance": "Facts are typically append-only; no SCD needed.",
                    "aggregation_opportunities": [
                        "daily sales by product",
                        "monthly sales by customer",
                    ],
                    "notes": [
                        "Minimal fallback definition; please refine based on real schema."
                    ],
                },
            ],
            "risks": [f"JSON parsing/validation failed in planning agent: {exc}"],
            "assumptions": ["Silver schema is stable and consistent."],
            "next_steps": [
                "Inspect the source Silver metadata and refine the Gold plan manually."
            ],
        }


# ---------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------
def main() -> int:
    try:
        load_dotenv()
        config = load_config()
        setup_logging(config.log_level)

        # Determine repo root and relevant directories
        repo_root = find_repo_root(Path(__file__).resolve())
        silver_root = repo_root / "artifacts" / "silver"
        planning_root = repo_root / "tmp" / "draft_reports" / "gold"

        # Determine which Silver run to use
        requested_run_id = sys.argv[1] if len(sys.argv) > 1 else None
        silver_run_id = resolve_silver_run_id(silver_root, requested_run_id)
        silver_run_id = resolve_silver_context_run_id(silver_root, silver_run_id)

        silver_run_dir = silver_root / silver_run_id

        # Input paths (Silver)
        agent_ctx_path = silver_run_dir / "reports" / "silver_run_agent_context.json"
        metadata_path = silver_run_dir / "metadata.yaml"

        silver_agent_context = read_json(agent_ctx_path)
        silver_metadata = read_yaml(metadata_path)

        # Output directories and paths (Gold planning)
        planning_run_dir = planning_root / silver_run_id
        planning_run_dir.mkdir(parents=True, exist_ok=True)

        design_report_path = planning_run_dir / "gold_run_human_report.md"
        mart_plan_path = planning_run_dir / "gold_run_agent_context.json"
        inputs_path = planning_run_dir / "gold_run_inputs.json"
        env_snapshot_path = planning_run_dir / "gold_run_env_snapshot.json"

        write_json(
            inputs_path,
            {
                "requested_run_id": requested_run_id,
                "silver_run_id": silver_run_id,
                "silver_root": str(silver_root),
                "planning_root": str(planning_root),
            },
        )
        write_json(env_snapshot_path, build_env_snapshot())

        # LLM client
        client = build_llm_client(config.api_key)

        # 1) Human-readable design report
        design_md = create_gold_design_report(
            client=client,
            silver_run_id=silver_run_id,
            silver_agent_context=silver_agent_context,
            silver_metadata=silver_metadata,
            model_name=config.model_name,
            max_retries=config.max_retries,
            backoff_seconds=config.backoff_seconds,
        )
        design_report_path.write_text(design_md, encoding="utf-8")
        LOGGER.info("Wrote Gold design report to: %s", design_report_path)

        # 2) Machine-readable mart plan
        mart_plan = create_gold_mart_plan(
            client=client,
            silver_run_id=silver_run_id,
            silver_agent_context=silver_agent_context,
            silver_metadata=silver_metadata,
            model_name=config.model_name,
            max_retries=config.max_retries,
            backoff_seconds=config.backoff_seconds,
        )
        write_json(mart_plan_path, mart_plan)
        LOGGER.info("Wrote Gold mart plan to: %s", mart_plan_path)

        LOGGER.info("Gold-layer planning completed successfully.")
        return 0
    except PlanningError as exc:
        LOGGER.error("Gold-layer planning failed: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Gold-layer planning failed with unexpected error.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
