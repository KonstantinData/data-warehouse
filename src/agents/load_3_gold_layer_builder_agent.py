"""
load_3_gold_layer_builder_agent.py

ROLE:
- Builds the final Gold ETL script using:
    (1) artifacts/silver/<run_id>/metadata.yaml
    (2) artifacts/silver/<run_id>/reports/elt_report.html
    (3) tmp/draft_reports/gold/<run_id>/gold_run_agent_context.json
    (4) tmp/draft_reports/gold/<run_id>/gold_run_human_report.md
    (5) src/templates/load_3_gold_layer_template.py

- Generates a new src/runs/load_3_gold_layer.py deterministically
- ALWAYS overwrites the script
- Does NOT execute the script; the orchestrator controls execution
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping

import yaml
from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.run_id import RUN_ID_RE, validate_run_id
from src.utils.secrets import get_required_secret, redact_dict, redact_text

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "src").exists() and (cur / "artifacts").exists():
            return cur
        cur = cur.parent
    return start.resolve()


def find_latest_silver_run_id(silver_root: Path) -> str:
    if not silver_root.exists():
        raise FileNotFoundError(f"Silver root does not exist: {silver_root}")

    run_ids: List[str] = []
    for p in silver_root.iterdir():
        if p.is_dir() and RUN_ID_RE.match(p.name):
            run_ids.append(p.name)

    if not run_ids:
        raise FileNotFoundError(f"No Silver runs found under: {silver_root}")

    run_id = sorted(run_ids)[-1]
    validate_run_id(run_id)
    return run_id


def resolve_silver_run_id(silver_root: Path, requested_run_id: str | None) -> str:
    if requested_run_id:
        validate_run_id(requested_run_id)
        return requested_run_id
    return find_latest_silver_run_id(silver_root)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(read_text(path))


def read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# -------------------------------------------------------------
# Logging
# -------------------------------------------------------------
def setup_logger(run_id: str, correlation_id: str) -> logging.Logger:
    logger = logging.getLogger("gold_layer_builder")
    if logger.handlers:
        return logging.LoggerAdapter(logger, {"run_id": run_id, "correlation_id": correlation_id})  # type: ignore[return-value]

    log_level = os.getenv("GOLD_BUILDER_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s %(levelname)s [run_id=%(run_id)s correlation_id=%(correlation_id)s] "
            "%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
    logger.propagate = False
    adapter = logging.LoggerAdapter(logger, {"run_id": run_id, "correlation_id": correlation_id})
    return adapter  # type: ignore[return-value]


# -------------------------------------------------------------
# OpenAI Client
# -------------------------------------------------------------
def build_llm_client() -> OpenAI:
    load_dotenv()
    api_key = get_required_secret("OPEN_AI_KEY", "OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def extract_python_block(content: str) -> str:
    content = content.strip()

    if content.startswith("```"):
        inner = content.split("```")[1]
        # remove possible `python` tag
        lines = inner.splitlines()
        if lines and lines[0].strip().lower().startswith("python"):
            lines = lines[1:]
        return "\n".join(lines).strip()

    return content


# -------------------------------------------------------------
# LLM Code Generation
# -------------------------------------------------------------
def generate_gold_script(
    client: OpenAI,
    template_text: str,
    silver_metadata: Dict[str, Any],
    silver_elt_report_html: str,
    gold_agent_context: Dict[str, Any],
    gold_human_report_md: str,
    model_name: str = "gpt-4.1",
) -> str:

    system_msg = {
        "role": "system",
        "content": (
            "You are a senior Data Warehouse Architect and Python Engineer. "
            "Your task is to generate a COMPLETE Python module implementing "
            "the Gold ETL pipeline. You MUST use the given template as structural basis."
        )
    }

    user_msg = {
        "role": "user",
        "content": (
            "Generate a final Gold-layer ETL script as a full Python module. "
            "Rules:\n"
            "- Use the template structure exactly.\n"
            "- Implement mart definitions found in the Gold run context.\n"
            "- Implement business logic and grain rules from the Gold human report.\n"
            "- Use the Silver metadata and ELT report for schema fidelity.\n"
            "- Do NOT invent tables or columns – only use what is present.\n"
            "- Output ONLY Python code, no markdown.\n\n"
            "=========== TEMPLATE ===========\n"
            f"{template_text}\n\n"
            "=========== SILVER METADATA (YAML) ===========\n"
            f"{yaml.safe_dump(silver_metadata, sort_keys=False)}\n\n"
            "=========== SILVER ELT REPORT (HTML) ===========\n"
            f"{silver_elt_report_html}\n\n"
            "=========== GOLD RUN CONTEXT ===========\n"
            f"{json.dumps(gold_agent_context, indent=2)}\n\n"
            "=========== GOLD HUMAN REPORT ===========\n"
            f"{gold_human_report_md}\n\n"
            "RETURN ONLY THE PYTHON CODE."
        )
    }

    response = client.chat.completions.create(
        model=model_name,
        messages=[system_msg, user_msg],
        temperature=0,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    raw = response.choices[0].message.content
    return extract_python_block(raw)


# -------------------------------------------------------------
# Main Agent Logic
# -------------------------------------------------------------
SAFE_PROMPT_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def sanitize_prompt_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not SAFE_PROMPT_KEY_RE.match(key):
            continue
        sanitized[key] = value
    return sanitized


def validate_inputs(paths: Mapping[str, Path]) -> None:
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        missing_str = ", ".join(f"{name}={paths[name]}" for name in missing)
        raise FileNotFoundError(f"Missing required inputs: {missing_str}")


def call_llm_with_retries(
    call: Callable[[], str],
    logger: logging.Logger,
    retries: int = 3,
    base_delay_s: float = 1.0,
) -> str:
    for attempt in range(1, retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                logger.exception("LLM call failed after retries.")
                raise
            sleep_s = base_delay_s * (2 ** (attempt - 1))
            logger.warning("LLM call failed (attempt %s/%s): %s. Retrying in %.1fs.", attempt, retries, exc, sleep_s)
            time.sleep(sleep_s)
    raise RuntimeError("Unexpected retry loop exit.")


@dataclass(frozen=True)
class BuilderConfig:
    repo_root: Path
    silver_run_id: str
    model_name: str = "gpt-4.1"


def parse_args(argv: List[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Gold-layer ETL script.")
    parser.add_argument("silver_run_id", nargs="?", help="Optional Silver run ID to use.")
    parser.add_argument("--model", default="gpt-4.1", help="OpenAI model name.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None, llm_client_factory: Callable[[], OpenAI] = build_llm_client) -> int:
    args = parse_args(argv)
    repo_root = find_repo_root(Path(__file__).resolve())
    silver_root = repo_root / "artifacts" / "silver"
    silver_run_id = resolve_silver_run_id(silver_root, args.silver_run_id)
    validate_run_id(silver_run_id)
    correlation_id = uuid.uuid4().hex
    logger = setup_logger(silver_run_id, correlation_id)
    config = BuilderConfig(repo_root=repo_root, silver_run_id=silver_run_id, model_name=args.model)

    logger.info("Resolved repository root: %s", repo_root)
    logger.info("Using SILVER_RUN_ID=%s", silver_run_id)

    silver_run_dir = silver_root / config.silver_run_id
    metadata_path = silver_run_dir / "metadata.yaml"
    elt_report_path = silver_run_dir / "reports" / "elt_report.html"

    gold_report_dir = repo_root / "tmp" / "draft_reports" / "gold" / config.silver_run_id
    gold_context_path = gold_report_dir / "gold_run_agent_context.json"
    gold_human_report_path = gold_report_dir / "gold_run_human_report.md"

    template_path = repo_root / "src" / "templates" / "load_3_gold_layer_template.py"
    runner_path = repo_root / "src" / "runs" / "load_3_gold_layer.py"

    validate_inputs(
        {
            "metadata": metadata_path,
            "elt_report": elt_report_path,
            "gold_context": gold_context_path,
            "gold_human_report": gold_human_report_path,
            "template": template_path,
        }
    )

    silver_metadata = read_yaml(metadata_path)
    silver_elt_report_html = read_text(elt_report_path)
    gold_agent_context = sanitize_prompt_payload(read_json(gold_context_path))
    gold_human_report_md = read_text(gold_human_report_path)

    # Read template
    template_text = read_text(template_path)

    # Build LLM
    client = llm_client_factory()

    # Generate final Gold-layer script
    logger.info("Generating Gold script from LLM.")
    python_code = call_llm_with_retries(
        lambda: generate_gold_script(
            client=client,
            template_text=template_text,
            silver_metadata=silver_metadata,
            silver_elt_report_html=silver_elt_report_html,
            gold_agent_context=json.loads(json.dumps(gold_agent_context, sort_keys=True)),
            gold_human_report_md=gold_human_report_md,
            model_name=config.model_name,
        ),
        logger=logger,
    )

    # Save script
    runner_path.write_text(python_code, encoding="utf-8")
    logger.info("Wrote load_3_gold_layer.py to: %s", runner_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001
        logging.exception("Gold layer builder failed.")
        raise
