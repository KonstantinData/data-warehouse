"""
load_2_silver_layer_builder_agent.py

ROLE:
- Builds the final Silver ETL script using:
    (1) latest silver_run_agent_context.json in artifacts/tmp/draft_reports/silver/<run_id>
    (2) latest silver_run_human_report.md in artifacts/tmp/draft_reports/silver/<run_id>
    (3) src/templates/load_2_silver_layer_template.py

- Generates a new src/runs/load_2_silver_layer.py based on LLM reasoning
- ALWAYS overwrites the script
- Executes the script automatically with the correct bronze_run_id
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

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


def find_latest_bronze_run_id(bronze_root: Path) -> str:
    run_ids = [p.name for p in bronze_root.iterdir() if p.is_dir()]
    if not run_ids:
        raise FileNotFoundError("No Bronze runs found!")
    return sorted(run_ids)[-1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(read_text(path))


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

def generate_silver_script(
    client: OpenAI,
    template_text: str,
    agent_context: Dict[str, Any],
    human_report_md: str,
    model_name: str = "gpt-4.1",
) -> str:

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
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    return extract_python_block(raw)


# -------------------------------------------------------------
# Main Agent Logic
# -------------------------------------------------------------

def main() -> int:
    repo_root = find_repo_root(Path(__file__).resolve())
    print(f"[BUILDER] REPO_ROOT={repo_root}")

    bronze_root = repo_root / "artifacts" / "bronze"

    # Silver Run ID
    if len(sys.argv) > 1:
        bronze_run_id = sys.argv[1]
    else:
        bronze_run_id = find_latest_bronze_run_id(bronze_root)

    print(f"[BUILDER] Using BRONZE_RUN_ID={bronze_run_id}")

    report_dir = repo_root / "artifacts" / "tmp" / "draft_reports" / "silver" / bronze_run_id
    context_path = report_dir / "silver_run_agent_context.json"
    human_report_path = report_dir / "silver_run_human_report.md"

    agent_context = read_json(context_path)
    human_report_md = read_text(human_report_path)

    # Read template
    template_path = repo_root / "src" / "templates" / "load_2_silver_layer_template.py"
    template_text = read_text(template_path)

    # Build LLM
    client = build_llm_client()

    # Generate final Silver-layer script
    print("[BUILDER] Generating Silver script from LLM...")
    python_code = generate_silver_script(
        client=client,
        template_text=template_text,
        agent_context=agent_context,
        human_report_md=human_report_md,
    )

    # Save script
    runner_path = repo_root / "src" / "runs" / "load_2_silver_layer.py"
    runner_path.write_text(python_code, encoding="utf-8")
    print(f"[BUILDER] Wrote load_2_silver_layer.py to: {runner_path}")

    # Execute script
    if os.getenv("SKIP_RUNNER_EXECUTION") == "1":
        print("[BUILDER] SKIP_RUNNER_EXECUTION=1 set; skipping runner execution.")
        return 0

    bronze_run_id = agent_context.get("bronze_run_id") or bronze_run_id
    cmd = [sys.executable, str(runner_path), bronze_run_id]
    print(f"[BUILDER] Executing generated Silver ETL script with cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=repo_root)
    print(f"[BUILDER] Script exited with code: {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
