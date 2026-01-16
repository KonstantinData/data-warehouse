"""
orchestrator.py

End-to-end pipeline orchestrator for Bronze -> Silver -> Gold -> Summary.

Responsibilities:
- Validate .env and required keys
- Validate raw source directories
- Generate a single orchestration run_id and pass it to all steps
- Execute steps with timing + status capture
- Short-circuit downstream steps when no new data is detected
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from runs.load_summary_report import write_summary_report

import yaml
from dotenv import dotenv_values, load_dotenv

RUN_ID_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})_#(?P<suffix>[0-9a-fA-F]{6,32})$")


@dataclass
class StepResult:
    name: str
    status: str
    started_utc: str
    ended_utc: str
    duration_s: float
    return_code: Optional[int] = None
    details: Optional[str] = None
    log_path: Optional[str] = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "src").exists() and (cur / "artifacts").exists():
            return cur
        cur = cur.parent
    return start.resolve()


def validate_env(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Missing .env file at {env_path}")

    env_values = dotenv_values(env_path)
    load_dotenv(env_path)

    has_api_key = bool(
        os.getenv("OPEN_AI_KEY")
        or os.getenv("OPENAI_API_KEY")
        or env_values.get("OPEN_AI_KEY")
        or env_values.get("OPENAI_API_KEY")
    )
    if not has_api_key:
        raise RuntimeError("Missing OPEN_AI_KEY or OPENAI_API_KEY in .env")


def validate_raw_sources(repo_root: Path) -> None:
    crm_dir = repo_root / "raw" / "source_crm"
    erp_dir = repo_root / "raw" / "source_erp"
    missing = [str(p) for p in (crm_dir, erp_dir) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required raw source directories: {', '.join(missing)}")


def generate_run_id() -> str:
    stamp = utc_now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{stamp}_#{suffix}"


def find_latest_run_id(root: Path) -> str:
    if not root.exists():
        raise FileNotFoundError(f"Missing run root directory: {root}")
    run_ids = [p.name for p in root.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name)]
    if not run_ids:
        raise FileNotFoundError(f"No runs found in {root}")
    return sorted(run_ids)[-1]


def read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_subprocess_step(
    name: str,
    cmd: List[str],
    env: Dict[str, str],
    cwd: Path,
    log_dir: Path,
) -> StepResult:
    log_path = log_dir / f"{name.replace(' ', '_').lower()}.log"
    started = utc_now()
    t0 = time.perf_counter()
    return_code: Optional[int] = None
    status = "success"
    details = None
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        return_code = result.returncode
        if result.returncode != 0:
            status = "failed"
            details = f"Command exited with code {result.returncode}" \
                f" (see {log_path})"
    except Exception as exc:
        status = "failed"
        details = f"Execution failed: {exc}"
    ended = utc_now()
    return StepResult(
        name=name,
        status=status,
        started_utc=iso_utc(started),
        ended_utc=iso_utc(ended),
        duration_s=time.perf_counter() - t0,
        return_code=return_code,
        details=details,
        log_path=str(log_path),
    )


def run_silver_draft_step(repo_root: Path, log_dir: Path) -> StepResult:
    name = "silver draft"
    started = utc_now()
    t0 = time.perf_counter()
    status = "success"
    details = None
    log_path = log_dir / "silver_draft.log"
    try:
        bronze_root = repo_root / "artifacts" / "bronze"
        bronze_run_id = find_latest_run_id(bronze_root)

        from agents.load_2_silver_layer_draft_agent import run_report_agent

        run_report_agent(
            run_id=bronze_run_id,
        )
        log_path.write_text(
            f"Regenerated draft outputs for bronze_run_id={bronze_run_id}\n",
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        status = "skipped"
        details = f"Skipped: {exc}"
    except Exception as exc:
        status = "failed"
        details = f"Execution failed: {exc}"
    ended = utc_now()
    return StepResult(
        name=name,
        status=status,
        started_utc=iso_utc(started),
        ended_utc=iso_utc(ended),
        duration_s=time.perf_counter() - t0,
        details=details,
        log_path=str(log_path),
    )


def detect_no_new_data(bronze_metadata: Dict[str, Any]) -> bool:
    summary = bronze_metadata.get("summary", {})
    files_success = summary.get("files_success", 0)
    files_failed = summary.get("files_failed", 0)
    files_total = summary.get("files_total", 0)
    return files_total > 0 and files_success == 0 and files_failed == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end ELT orchestration.")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-driven draft/builder steps.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    validate_env(repo_root)
    validate_raw_sources(repo_root)

    orchestrator_run_id = generate_run_id()
    started = utc_now()

    output_root = repo_root / "artifacts" / "orchestrator" / orchestrator_run_id
    log_dir = output_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["ORCHESTRATOR_RUN_ID"] = orchestrator_run_id
    env["RUN_ID"] = orchestrator_run_id

    step_results: List[StepResult] = []
    bronze_run_id = None
    silver_run_id = None
    gold_run_id = None
    no_new_data = False
    should_stop = False

    bronze_cmd = [sys.executable, str(repo_root / "src" / "runs" / "load_1_bronze_layer.py")]
    bronze_result = run_subprocess_step(
        name="bronze",
        cmd=bronze_cmd,
        env=env,
        cwd=repo_root,
        log_dir=log_dir,
    )
    step_results.append(bronze_result)
    if bronze_result.status != "success":
        should_stop = True
    else:
        bronze_root = repo_root / "artifacts" / "bronze"
        bronze_run_id = find_latest_run_id(bronze_root)
        bronze_metadata_path = bronze_root / bronze_run_id / "data" / "metadata.yaml"
        bronze_metadata = read_yaml(bronze_metadata_path)
        no_new_data = detect_no_new_data(bronze_metadata)

    if no_new_data:
        for step_name in [
            "silver draft",
            "silver builder",
            "silver runner",
            "gold draft",
            "gold builder",
            "gold runner",
        ]:
            step_results.append(
                StepResult(
                    name=step_name,
                    status="skipped",
                    started_utc=iso_utc(utc_now()),
                    ended_utc=iso_utc(utc_now()),
                    duration_s=0.0,
                    details="Skipped due to no new data.",
                )
            )
    else:
        if should_stop:
            for step_name in [
                "silver draft",
                "silver builder",
                "silver runner",
                "gold draft",
                "gold builder",
                "gold runner",
            ]:
                step_results.append(
                    StepResult(
                        name=step_name,
                        status="skipped",
                        started_utc=iso_utc(utc_now()),
                        ended_utc=iso_utc(utc_now()),
                        duration_s=0.0,
                        details="Skipped due to prior failure.",
                    )
                )
        else:
            if args.skip_llm:
                for step_name in ["silver draft", "silver builder", "gold draft", "gold builder"]:
                    step_results.append(
                        StepResult(
                            name=step_name,
                            status="skipped",
                            started_utc=iso_utc(utc_now()),
                            ended_utc=iso_utc(utc_now()),
                            duration_s=0.0,
                            details="Skipped via --skip-llm.",
                        )
                    )
            else:
                step_results.append(run_silver_draft_step(repo_root, log_dir))

                silver_builder_cmd = [
                    sys.executable,
                    str(repo_root / "src" / "agents" / "load_2_silver_layer_builder_agent.py"),
                ]
                if bronze_run_id:
                    silver_builder_cmd.append(bronze_run_id)
                step_results.append(
                    run_subprocess_step(
                        name="silver builder",
                        cmd=silver_builder_cmd,
                        env=env,
                        cwd=repo_root,
                        log_dir=log_dir,
                    )
                )

            silver_runner_cmd = [
                sys.executable,
                str(repo_root / "src" / "runs" / "load_2_silver_layer.py"),
            ]
            if bronze_run_id:
                silver_runner_cmd.append(bronze_run_id)
            silver_runner_result = run_subprocess_step(
                name="silver runner",
                cmd=silver_runner_cmd,
                env=env,
                cwd=repo_root,
                log_dir=log_dir,
            )
            step_results.append(silver_runner_result)
            if silver_runner_result.status == "success":
                silver_root = repo_root / "artifacts" / "silver"
                silver_run_id = find_latest_run_id(silver_root)
            else:
                should_stop = True

            if should_stop:
                for step_name in ["gold draft", "gold builder", "gold runner"]:
                    step_results.append(
                        StepResult(
                            name=step_name,
                            status="skipped",
                            started_utc=iso_utc(utc_now()),
                            ended_utc=iso_utc(utc_now()),
                            duration_s=0.0,
                            details="Skipped due to prior failure.",
                        )
                    )
            else:
                if args.skip_llm:
                    for step_name in ["gold draft", "gold builder"]:
                        step_results.append(
                            StepResult(
                                name=step_name,
                                status="skipped",
                                started_utc=iso_utc(utc_now()),
                                ended_utc=iso_utc(utc_now()),
                                duration_s=0.0,
                                details="Skipped via --skip-llm.",
                            )
                        )
                else:
                    gold_draft_cmd = [
                        sys.executable,
                        str(repo_root / "src" / "agents" / "load_3_gold_layer_draft_agent.py"),
                    ]
                    if silver_run_id:
                        gold_draft_cmd.append(silver_run_id)
                    step_results.append(
                        run_subprocess_step(
                            name="gold draft",
                            cmd=gold_draft_cmd,
                            env=env,
                            cwd=repo_root,
                            log_dir=log_dir,
                        )
                    )

                    gold_builder_cmd = [
                        sys.executable,
                        str(repo_root / "src" / "agents" / "load_3_gold_layer_builder_agent.py"),
                    ]
                    builder_env = env.copy()
                    builder_env["SKIP_RUNNER_EXECUTION"] = "1"
                    step_results.append(
                        run_subprocess_step(
                            name="gold builder",
                            cmd=gold_builder_cmd,
                            env=builder_env,
                            cwd=repo_root,
                            log_dir=log_dir,
                        )
                    )

                gold_runner_cmd = [
                    sys.executable,
                    str(repo_root / "src" / "runs" / "load_3_gold_layer.py"),
                ]
                if silver_run_id:
                    gold_runner_cmd.append(silver_run_id)
                gold_runner_result = run_subprocess_step(
                    name="gold runner",
                    cmd=gold_runner_cmd,
                    env=env,
                    cwd=repo_root,
                    log_dir=log_dir,
                )
                step_results.append(gold_runner_result)
                if gold_runner_result.status == "success":
                    gold_root = repo_root / "artifacts" / "gold" / "marts"
                    if gold_root.exists():
                        gold_run_id = find_latest_run_id(gold_root)

    ended = utc_now()
    summary_dir = repo_root / "artifacts" / "reports" / orchestrator_run_id
    write_summary_report(
        output_dir=summary_dir,
        run_id=orchestrator_run_id,
        started_utc=iso_utc(started),
        ended_utc=iso_utc(ended),
        step_results=step_results,
        bronze_run_id=bronze_run_id,
        silver_run_id=silver_run_id,
        gold_run_id=gold_run_id,
        no_new_data=no_new_data,
    )

    return 0 if all(s.status in {"success", "skipped"} for s in step_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
