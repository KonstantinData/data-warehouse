"""
load_2_silver_layer_builder_agent.py

ROLE:
- Builds the final Silver ETL script using:
    (1) silver_run_agent_context.json in tmp/draft_reports/silver/<run_id>
    (2) silver_run_human_report.md in tmp/draft_reports/silver/<run_id>
    (3) src/templates/load_2_silver_layer_template.py

- Generates a new src/runs/load_2_silver_layer.py deterministically
- ALWAYS overwrites the script
"""

from __future__ import annotations

import ast
import json
import logging
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.run_id import validate_run_id
from src.utils.secrets import get_required_secret, redact_dict, redact_text

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def find_repo_root(start: Path) -> Path:
    """Find the repository root by searching for expected top-level folders."""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "src").exists() and (cur / "artifacts").exists():
            return cur
        cur = cur.parent
    return start.resolve()


def read_text(path: Path) -> str:
    """Read a UTF-8 text file and return its contents."""
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    """Read a JSON file and return the parsed object."""
    return json.loads(read_text(path))


def ensure_file_exists(path: Path) -> None:
    """Validate that a required file exists before attempting to read it."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Required path is not a file: {path}")


def setup_logging() -> logging.Logger:
    """Configure structured logging for the builder agent."""
    logging.basicConfig(
        level=logging.INFO,
        format='{"level":"%(levelname)s","message":"%(message)s"}',
    )
    return logging.getLogger("silver_builder")


# -------------------------------------------------------------
# OpenAI Client
# -------------------------------------------------------------

def build_llm_client() -> OpenAI:
    """Build the OpenAI client using environment variables."""
    load_dotenv()
    api_key = get_required_secret("OPEN_AI_KEY", "OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def extract_python_block(content: str) -> str:
    """Extract a Python code block if wrapped in Markdown fences."""
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

def generate_silver_script(
    client: OpenAI,
    template_text: str,
    agent_context: Dict[str, Any],
    human_report_md: str,
    model_name: str = "gpt-4.1",
) -> str:
    """Generate the Silver-layer ETL script via the LLM."""

    system_msg = {
        "role": "system",
        "content": (
            "You are a senior Data Warehouse Architect and Python Engineer. "
            "Your task is to generate a COMPLETE Python module implementing "
            "the Silver ETL pipeline. You MUST use the given template as structural basis."
        ),
    }

    user_msg = {
        "role": "user",
        "content": (
            "Generate a final Silver-layer ETL script as a full Python module. "
            "Rules:\n"
            "- Use the template structure exactly.\n"
            "- Implement table-specific cleanup and standardization informed by the Silver run context.\n"
            "- Preserve the Bronze table grain (no aggregations, no star schema).\n"
            "- Do NOT invent tables or columns – only use what is present.\n"
            "- Output ONLY Python code, no markdown.\n\n"
            "=========== TEMPLATE ===========\n"
            f"{template_text}\n\n"
            "=========== SILVER RUN CONTEXT ===========\n"
            f"{json.dumps(agent_context, indent=2)}\n\n"
            "=========== SILVER HUMAN REPORT ===========\n"
            f"{human_report_md}\n\n"
            "RETURN ONLY THE PYTHON CODE."
        ),
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


def validate_python_syntax(code: str) -> None:
    """Validate generated Python code by parsing the AST."""
    ast.parse(code)


def compute_hash(text: str) -> str:
    """Compute a SHA-256 hash of text content."""
    return sha256(text.encode("utf-8")).hexdigest()


def build_provenance_header(
    run_id: str,
    model_name: str,
    template_text: str,
    agent_context: Dict[str, Any],
    human_report_md: str,
) -> str:
    """Build a metadata header for provenance and auditability."""
    metadata = {
        "run_id": run_id,
        "model": model_name,
        "template_sha256": compute_hash(template_text),
        "agent_context_sha256": compute_hash(
            json.dumps(agent_context, sort_keys=True)
        ),
        "human_report_sha256": compute_hash(human_report_md),
    }
    header_lines = ["# Auto-generated by load_2_silver_layer_builder_agent.py"]
    for key, value in metadata.items():
        header_lines.append(f"# {key}: {value}")
    return "\n".join(header_lines)


# -------------------------------------------------------------
# Main Agent Logic
# -------------------------------------------------------------

def main() -> int:
    """Entry point for the builder agent."""
    logger = setup_logging()
    repo_root = find_repo_root(Path(__file__).resolve())
    logger.info(f"[BUILDER] REPO_ROOT={repo_root}")

    if len(sys.argv) < 2:
        raise SystemExit("Usage: load_2_silver_layer_builder_agent.py <run_id>")

    run_id = sys.argv[1]
    validate_run_id(run_id)
    logger.info(f"[BUILDER] Using RUN_ID={run_id}")

    report_dir = repo_root / "tmp" / "draft_reports" / "silver" / run_id
    context_path = report_dir / "silver_run_agent_context.json"
    human_report_path = report_dir / "silver_run_human_report.md"
    template_path = repo_root / "src" / "templates" / "load_2_silver_layer_template.py"

    ensure_file_exists(context_path)
    ensure_file_exists(human_report_path)
    ensure_file_exists(template_path)

    agent_context = read_json(context_path)
    human_report_md = read_text(human_report_path)

    # Read template
    template_text = read_text(template_path)

    # Build LLM
    client = build_llm_client()

    # Generate final Silver-layer script
    logger.info("[BUILDER] Generating Silver script from LLM...")
    model_name = "gpt-4.1"
    python_code = generate_silver_script(
        client=client,
        template_text=template_text,
        agent_context=json.loads(json.dumps(agent_context, sort_keys=True)),
        human_report_md=human_report_md,
        model_name=model_name,
    )

    # Save script
    validate_python_syntax(python_code)
    provenance_header = build_provenance_header(
        run_id=run_id,
        model_name=model_name,
        template_text=template_text,
        agent_context=agent_context,
        human_report_md=human_report_md,
    )
    final_code = f"{provenance_header}\n\n{python_code.strip()}\n"
    runner_path = repo_root / "src" / "runs" / "load_2_silver_layer.py"
    runner_path.write_text(final_code, encoding="utf-8")
    logger.info(f"[BUILDER] Wrote load_2_silver_layer.py to: {runner_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
