"""
start_run.py

Convenience wrapper to launch the end-to-end orchestrator.
"""

from __future__ import annotations

import sys
from pathlib import Path


def run() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "src"))
    from runs.orchestrator import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
