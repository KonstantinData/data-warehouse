from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AgentRequest:
    run_id: str
    target_path: str
    target_source: str
    system_prompt: str
    working_prompt: str


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    raw_markdown: str
    summary: Optional[List[str]] = None
    findings: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
