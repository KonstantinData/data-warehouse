"""
load_3_gold_layer_builder_agent.py

ROLE:
- Builds the final Gold ETL script using:
    (1) latest gold_mart_plan.json
    (2) latest gold_design_report.md
    (3) src/templates/load_3_gold_layer_template.py

- Generates a new src/runs/load_3_gold_layer.py based on LLM reasoning
- ALWAYS overwrites the script
- Executes the script automatically with the correct silver_run_id
"""

from __future__ import annotations

import json
import os
import subprocess
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


def find_latest_silver_run_id(silver_root: Path) -> str:
    run_ids = [p.name for p in silver_root.iterdir() if p.is_dir()]
    if not run_ids:
        raise FileNotFoundError("No Silver runs found!")
    return sorted(run_ids)[-1]


def find_latest_planning_dir(planning_root: Path) -> Path:
    runs = [p for p in planning_root.iterdir() if p.is_dir()]
    if not runs:
        raise FileNotFoundError("No planning runs found!")
    return sorted(runs, key=lambda x: x.name)[-1]


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
    mart_plan: Dict[str, Any],
    design_md: str,
    model_name: str = "gpt-4.1"
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
            "- Implement mart definitions found in gold_mart_plan.json.\n"
            "- Implement business logic and grain rules from the design report.\n"
            "- Do NOT invent tables or columns – only use what is present.\n"
            "- Output ONLY Python code, no markdown.\n\n"
            "=========== TEMPLATE ===========\n"
            f"{template_text}\n\n"
            "=========== GOLD MART PLAN ===========\n"
            f"{json.dumps(mart_plan, indent=2)}\n\n"
            "=========== GOLD DESIGN REPORT ===========\n"
            f"{design_md}\n\n"
            "RETURN ONLY THE PYTHON CODE."
        )
    }

    response = client.chat.completions.create(
        model=model_name,
        messages=[system_msg, user_msg],
        temperature=0.1
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
    planning_root = repo_root / "artifacts" / "gold" / "planning"

    # Silver Run ID
    if len(sys.argv) > 1:
        silver_run_id = sys.argv[1]
    else:
        silver_run_id = find_latest_silver_run_id(silver_root)

    print(f"[BUILDER] Using SILVER_RUN_ID={silver_run_id}")

    # Planning directory for this run
    planning_dir = planning_root / silver_run_id
    if not planning_dir.exists():
        planning_dir = find_latest_planning_dir(planning_root)
        print(f"[BUILDER] No matching planning directory; using latest: {planning_dir.name}")

    # Read planning artifacts
    mart_plan_path = planning_dir / "data" / "gold_mart_plan.json"
    design_md_path = planning_dir / "reports" / "gold_design_report.md"

    mart_plan = read_json(mart_plan_path)
    design_md = read_text(design_md_path)

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
        mart_plan=mart_plan,
        design_md=design_md
    )

    # Save script
    runner_path = repo_root / "src" / "runs" / "load_3_gold_layer.py"
    runner_path.write_text(python_code, encoding="utf-8")
    print(f"[BUILDER] Wrote load_3_gold_layer.py to: {runner_path}")

    if os.getenv("SKIP_RUNNER_EXECUTION") == "1":
        print("[BUILDER] SKIP_RUNNER_EXECUTION=1 set; skipping runner execution.")
        return 0

    # Execute script
    print("[BUILDER] Executing generated Gold ETL script...")
    cmd = [sys.executable, str(runner_path), silver_run_id]
    result = subprocess.run(cmd, cwd=repo_root)
    print(f"[BUILDER] Script exited with code: {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
