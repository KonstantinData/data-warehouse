"""
load_summary_report.py

Aggregate pipeline summary across Bronze/Silver/Gold steps.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

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


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(payload: Dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def extract_dq_summary(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("dq_summary", "dq", "data_quality"):
        if key in metadata and metadata[key]:
            return metadata[key]
    summary = metadata.get("summary", {})
    for key in ("dq_summary", "dq", "data_quality"):
        if key in summary and summary[key]:
            return summary[key]
    return None


def iter_token_usage(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "token_usage" and isinstance(value, dict):
                yield value
            yield from iter_token_usage(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_token_usage(item)


def aggregate_token_usage(metadatas: Iterable[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    totals: Dict[str, int] = {}
    for metadata in metadatas:
        for usage in iter_token_usage(metadata):
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    totals[key] = totals.get(key, 0) + int(value)
    return totals or None


def safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def summarize_bronze(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / "artifacts" / "bronze" / run_id
    metadata_path = root / "data" / "metadata.yaml"
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / "data").relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / "reports" / "elt_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    summary = metadata.get("summary", {})
    tables = metadata.get("tables", {})
    row_total = sum(safe_int(table.get("rows")) for table in tables.values())
    row_success = sum(
        safe_int(table.get("rows"))
        for table in tables.values()
        if table.get("status") == "SUCCESS"
    )
    status = "success" if summary.get("files_failed", 0) == 0 else "failed"
    run_meta = metadata.get("run", {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / "data").relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / "reports" / "elt_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "files_total": summary.get("files_total"),
            "files_success": summary.get("files_success"),
            "files_skipped": summary.get("files_skipped"),
            "files_failed": summary.get("files_failed"),
            "rows_total": row_total,
            "rows_success": row_success,
        },
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_silver(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / "artifacts" / "silver" / run_id
    metadata_path = root / "metadata.yaml"
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / "data").relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / "reports" / "elt_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    summary = metadata.get("summary", {})
    tables = metadata.get("tables", {})
    rows_in = sum(safe_int(table.get("rows_in")) for table in tables.values())
    rows_out = sum(safe_int(table.get("rows_out")) for table in tables.values())
    status = "success" if summary.get("files_failed", 0) == 0 else "failed"
    run_meta = metadata.get("run", {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / "data").relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / "reports" / "elt_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "files_total": summary.get("files_total"),
            "files_success": summary.get("files_success"),
            "files_failed": summary.get("files_failed"),
            "rows_in": rows_in,
            "rows_out": rows_out,
        },
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_gold(repo_root: Path, run_id: Optional[str]) -> Dict[str, Any]:
    if not run_id:
        return {"run_id": None, "status": "missing"}
    root = repo_root / "artifacts" / "gold" / "marts" / run_id
    metadata_path = root / "metadata.yaml"
    if not metadata_path.exists():
        return {
            "run_id": run_id,
            "status": "missing",
            "paths": {
                "root": str(root.relative_to(repo_root)),
                "data_dir": str((root / "data").relative_to(repo_root)),
                "metadata": str(metadata_path.relative_to(repo_root)),
                "report_html": str((root / "reports" / "gold_report.html").relative_to(repo_root)),
            },
        }
    metadata = read_yaml(metadata_path)
    outputs = metadata.get("outputs", [])
    rows_total = sum(safe_int(output.get("rows")) for output in outputs)
    status = metadata.get("run", {}).get("status") or ("success" if not metadata.get("errors") else "partial")
    run_meta = metadata.get("run", {})
    return {
        "run_id": run_id,
        "status": status,
        "timings": {
            "started_utc": run_meta.get("started_utc"),
            "ended_utc": run_meta.get("ended_utc"),
            "duration_s": run_meta.get("duration_s"),
        },
        "paths": {
            "root": str(root.relative_to(repo_root)),
            "data_dir": str((root / "data").relative_to(repo_root)),
            "metadata": str(metadata_path.relative_to(repo_root)),
            "report_html": str((root / "reports" / "gold_report.html").relative_to(repo_root)),
        },
        "row_counts": {
            "outputs_total": len(outputs),
            "rows_total": rows_total,
        },
        "dq_summary": extract_dq_summary(metadata),
        "metadata": metadata,
    }


def summarize_steps(step_results: List[Any]) -> Dict[str, Any]:
    def to_dict(result: Any) -> Dict[str, Any]:
        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, dict):
            return result
        return {
            "name": getattr(result, "name", None),
            "status": getattr(result, "status", None),
            "started_utc": getattr(result, "started_utc", None),
            "ended_utc": getattr(result, "ended_utc", None),
            "duration_s": getattr(result, "duration_s", None),
            "return_code": getattr(result, "return_code", None),
            "details": getattr(result, "details", None),
            "log_path": getattr(result, "log_path", None),
        }

    return {
        "statuses": {getattr(result, "name", None): getattr(result, "status", None) for result in step_results},
        "timings_s": {getattr(result, "name", None): getattr(result, "duration_s", None) for result in step_results},
        "details": [to_dict(result) for result in step_results],
    }


def build_summary_payload(
    repo_root: Path,
    run_id: str,
    started_utc: str,
    ended_utc: str,
    step_results: List[Any],
    bronze_run_id: Optional[str],
    silver_run_id: Optional[str],
    gold_run_id: Optional[str],
    no_new_data: bool,
) -> Dict[str, Any]:
    bronze_summary = summarize_bronze(repo_root, bronze_run_id)
    silver_summary = summarize_silver(repo_root, silver_run_id)
    gold_summary = summarize_gold(repo_root, gold_run_id)

    payload = {
        "run_id": run_id,
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "duration_s": (datetime.fromisoformat(ended_utc.replace("Z", "+00:00")) - datetime.fromisoformat(started_utc.replace("Z", "+00:00"))).total_seconds(),
        "no_new_data": no_new_data,
        "steps": summarize_steps(step_results),
        "layers": {
            "bronze": bronze_summary,
            "silver": silver_summary,
            "gold": gold_summary,
        },
        "token_usage": aggregate_token_usage(
            [
                bronze_summary.get("metadata", {}),
                silver_summary.get("metadata", {}),
                gold_summary.get("metadata", {}),
            ]
        ),
    }
    return payload


def write_summary_report(
    output_dir: Path,
    run_id: str,
    started_utc: str,
    ended_utc: str,
    step_results: List[Any],
    bronze_run_id: Optional[str],
    silver_run_id: Optional[str],
    gold_run_id: Optional[str],
    no_new_data: bool,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_root = find_repo_root(Path(__file__).resolve())
    payload = build_summary_payload(
        repo_root=repo_root,
        run_id=run_id,
        started_utc=started_utc,
        ended_utc=ended_utc,
        step_results=step_results,
        bronze_run_id=bronze_run_id,
        silver_run_id=silver_run_id,
        gold_run_id=gold_run_id,
        no_new_data=no_new_data,
    )

    json_path = output_dir / "summary_report.json"
    write_json(payload, json_path)

    md_lines = [
        f"# Orchestration Summary: {run_id}",
        "",
        f"- Started (UTC): {started_utc}",
        f"- Ended (UTC): {ended_utc}",
        f"- No new data: {no_new_data}",
        "",
        "## Step Statuses",
    ]
    for name, status in payload["steps"]["statuses"].items():
        duration = payload["steps"]["timings_s"].get(name)
        md_lines.append(f"- {name}: {status} ({duration:.3f}s)" if duration is not None else f"- {name}: {status}")

    md_lines.extend(["", "## Layer Rollups"])
    for layer_name, layer in payload["layers"].items():
        md_lines.extend(
            [
                f"### {layer_name.capitalize()}",
                f"- Run ID: {layer.get('run_id') or 'N/A'}",
                f"- Status: {layer.get('status')}",
                f"- Duration (s): {layer.get('timings', {}).get('duration_s')}",
                f"- Data dir: {layer.get('paths', {}).get('data_dir')}",
            ]
        )

    md_lines.extend(["", "## Token Usage", f"- {payload.get('token_usage') or 'N/A'}"])

    md_path = output_dir / "summary_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a summary report for a run.")
    parser.add_argument("run_id", help="Orchestrator run ID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    run_id = args.run_id
    output_dir = repo_root / "artifacts" / "reports" / run_id

    now = utc_now()
    write_summary_report(
        output_dir=output_dir,
        run_id=run_id,
        started_utc=iso_utc(now),
        ended_utc=iso_utc(now),
        step_results=[],
        bronze_run_id=None,
        silver_run_id=None,
        gold_run_id=None,
        no_new_data=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
