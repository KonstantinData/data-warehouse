"""Run code quality multi-agent analysis and persist artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents import code_architecture_and_operations
from src.agents import code_quality_and_maintainability
from src.agents import code_security_governance_compliance
from src.agents import code_quality_orchestrator
from src.agents.agent_types import AgentRequest, AgentResult

DEFAULT_SYSTEM_PROMPT_CANDIDATES = (
    Path("docs/prompts/systemprompt Senior Principal Data Engineer.txt"),
    Path("docs/prompts/system_prompt.txt"),
)
DEFAULT_WORKING_PROMPT_CANDIDATES = (
    Path("docs/prompts/code_review_prompt.txt"),
    Path("docs/prompts/working_prompt.txt"),
)
OUTPUT_ROOT = Path("tmp/prompt_analysis")


def _generate_run_id() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{timestamp}_#{suffix}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _log_line(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def _resolve_prompt_path(path_value: str | None, candidates: tuple[Path, ...]) -> Path:
    if path_value:
        return Path(path_value)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    candidate_list = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"No prompt file found. Checked: {candidate_list}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run code quality multi-agent analysis.")
    parser.add_argument("target_path", help="Path to the Python target file.")
    parser.add_argument(
        "--system",
        default=None,
        help="Path to the system prompt.",
    )
    parser.add_argument(
        "--working",
        default=None,
        help="Path to the working prompt.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_id = _generate_run_id()
    output_dir = OUTPUT_ROOT / run_id
    log_path = output_dir / "logs" / "run_log.txt"

    _log_line(log_path, f"Start: {datetime.utcnow().isoformat()}Z")
    _log_line(log_path, f"Run ID: {run_id}")
    _log_line(log_path, f"Target path: {args.target_path}")
    try:
        target_path = Path(args.target_path)
        system_prompt_path = _resolve_prompt_path(args.system, DEFAULT_SYSTEM_PROMPT_CANDIDATES)
        working_prompt_path = _resolve_prompt_path(args.working, DEFAULT_WORKING_PROMPT_CANDIDATES)

        _log_line(log_path, f"System prompt: {system_prompt_path}")
        _log_line(log_path, f"Working prompt: {working_prompt_path}")

        target_source = _read_text(target_path)
        system_prompt = _read_text(system_prompt_path)
        working_prompt = _read_text(working_prompt_path)

        _write_text(output_dir / "inputs" / "target_path.txt", str(target_path))
        _write_text(output_dir / "inputs" / "target_source.py", target_source)
        _write_text(output_dir / "inputs" / "system_prompt.txt", system_prompt)
        _write_text(output_dir / "inputs" / "working_prompt.txt", working_prompt)

        request = AgentRequest(
            run_id=run_id,
            target_path=str(target_path),
            target_source=target_source,
            system_prompt=system_prompt,
            working_prompt=working_prompt,
        )

        results: list[AgentResult] = []
        timings: dict[str, float] = {}

        agent_sequence = [
            ("code_quality_and_maintainability", code_quality_and_maintainability.run_agent),
            ("code_architecture_and_operations", code_architecture_and_operations.run_agent),
            ("code_security_governance_compliance", code_security_governance_compliance.run_agent),
        ]

        total_start = perf_counter()
        for name, agent_fn in agent_sequence:
            _log_line(log_path, f"Agent start: {name}")
            start = perf_counter()
            result = agent_fn(request)
            duration = perf_counter() - start
            timings[name] = duration
            results.append(result)
            _write_text(output_dir / "agents" / f"{name}.md", result.raw_markdown)
            _log_line(log_path, f"Agent success: {name} ({duration:.3f}s)")

        _log_line(log_path, "Orchestrator start: code_quality_orchestrator")
        orchestrator_start = perf_counter()
        final_answer, notes = code_quality_orchestrator.run_orchestrator(request, results)
        orchestrator_duration = perf_counter() - orchestrator_start
        timings["orchestrator"] = orchestrator_duration
        _log_line(log_path, f"Orchestrator success: code_quality_orchestrator ({orchestrator_duration:.3f}s)")
        _write_text(output_dir / "synthesis" / "final_answer.md", final_answer)
        _write_text(output_dir / "synthesis" / "consolidation_notes.md", notes)

        total_duration = perf_counter() - total_start
        timings["total"] = total_duration
        _write_text(output_dir / "metrics" / "timings.json", json.dumps(timings, indent=2))

        _log_line(log_path, f"End: {datetime.utcnow().isoformat()}Z")
        _log_line(log_path, f"Output root: {output_dir}")
        return 0
    except Exception:
        _log_line(log_path, "Run failed with exception:")
        _log_line(log_path, traceback.format_exc())
        _log_line(log_path, f"End (failed): {datetime.utcnow().isoformat()}Z")
        _log_line(log_path, f"Output root: {output_dir}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
