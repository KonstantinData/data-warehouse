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

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from openai import OpenAI


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(read_text(path))


def read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# -------------------------------------------------------------
# OpenAI Client
# -------------------------------------------------------------
def build_llm_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPEN_AI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPEN_AI_KEY / OPENAI_API_KEY")
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
def main() -> int:

    repo_root = find_repo_root(Path(__file__).resolve())
    print(f"[BUILDER] REPO_ROOT={repo_root}")

    silver_root = repo_root / "artifacts" / "silver"

    if len(sys.argv) < 2:
        raise SystemExit("Usage: load_3_gold_layer_builder_agent.py <run_id>")

    silver_run_id = sys.argv[1]
    print(f"[BUILDER] Using SILVER_RUN_ID={silver_run_id}")

    silver_run_dir = silver_root / silver_run_id
    metadata_path = silver_run_dir / "metadata.yaml"
    elt_report_path = silver_run_dir / "reports" / "elt_report.html"

    gold_report_dir = repo_root / "tmp" / "draft_reports" / "gold" / silver_run_id
    gold_context_path = gold_report_dir / "gold_run_agent_context.json"
    gold_human_report_path = gold_report_dir / "gold_run_human_report.md"

    silver_metadata = read_yaml(metadata_path)
    silver_elt_report_html = read_text(elt_report_path)
    gold_agent_context = read_json(gold_context_path)
    gold_human_report_md = read_text(gold_human_report_path)

    # Read template
    template_path = repo_root / "src" / "templates" / "load_3_gold_layer_template.py"
    template_text = read_text(template_path)

    # Build LLM
    client = build_llm_client()

    # Generate final Gold-layer script
    print("[BUILDER] Generating Gold script from LLM...")
    python_code = generate_gold_script(
        client=client,
        template_text=template_text,
        silver_metadata=silver_metadata,
        silver_elt_report_html=silver_elt_report_html,
        gold_agent_context=json.loads(json.dumps(gold_agent_context, sort_keys=True)),
        gold_human_report_md=gold_human_report_md,
    )

    # Save script
    runner_path = repo_root / "src" / "runs" / "load_3_gold_layer.py"
    runner_path.write_text(python_code, encoding="utf-8")
    print(f"[BUILDER] Wrote load_3_gold_layer.py to: {runner_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
