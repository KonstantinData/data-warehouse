"""Orchestrator definition for multi-agent review."""

from __future__ import annotations

from typing import Iterable, Tuple

from src.agents.llm_utils import build_openai_client, call_openai
from src.agents.agent_types import AgentRequest, AgentResult

ROLE_DESCRIPTION = """
You are the Lead Reviewer coordinating a multi-agent senior engineering review.

Your task:
- Decompose the problem
- Delegate to specialist agents
- Consolidate results into a coherent, non-overlapping final answer
- Resolve contradictions using industry standards as the final authority

Do not repeat agent outputs verbatim.
Synthesize them into a unified senior-level response.
""".strip()

ORCHESTRATOR_OUTPUT_TEMPLATE = """Return two markdown documents separated by the tag lines below.

<FINAL_ANSWER>
# Consolidated Review
## Findings
- ...
## Risks (optional)
- ...
## Recommendations
- ...
</FINAL_ANSWER>

<CONSOLIDATION_NOTES>
# Consolidation Notes
- Mention deduping, conflict resolution, and any omissions.
</CONSOLIDATION_NOTES>
""".strip()


def _build_messages(req: AgentRequest, agent_results: Iterable[AgentResult]) -> list[dict[str, str]]:
    agent_sections = []
    for result in agent_results:
        agent_sections.append(f"Agent: {result.agent_name}\n{result.raw_markdown}")
    agents_block = "\n\n".join(agent_sections)

    user_prompt = "\n".join(
        [
            "Working prompt:",
            req.working_prompt,
            "",
            "Orchestrator role:",
            ROLE_DESCRIPTION,
            "",
            "Priority for conflict resolution:",
            "1) Security/Governance/Compliance",
            "2) Architecture/Operations/SRE",
            "3) Code Quality/Maintainability",
            "",
            f"Target path: {req.target_path}",
            "",
            "Specialist agent outputs:",
            agents_block,
            "",
            ORCHESTRATOR_OUTPUT_TEMPLATE,
        ]
    )

    return [
        {"role": "system", "content": req.system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _normalize_items(items: Iterable[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        normalized = " ".join(item.strip().split()).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(item.strip())
    return deduped


def _collect_section(results: Iterable[AgentResult], section: str, priority: list[str]) -> list[str]:
    collected: list[str] = []
    for agent_name in priority:
        for result in results:
            if result.agent_name != agent_name:
                continue
            section_items: list[str] = []
            if section == "findings" and result.findings:
                section_items = result.findings
            elif section == "recommendations" and result.recommendations:
                section_items = result.recommendations
            elif section == "risks" and result.risks:
                section_items = result.risks
            collected.extend(section_items)
    return _normalize_items(collected)


def _fallback_consolidation(results: Iterable[AgentResult]) -> Tuple[str, str]:
    priority = [
        "code_security_governance_compliance",
        "code_architecture_and_operations",
        "code_quality_and_maintainability",
    ]
    findings = _collect_section(results, "findings", priority)
    risks = _collect_section(results, "risks", priority)
    recommendations = _collect_section(results, "recommendations", priority)

    markdown_lines = [
        "# Consolidated Review",
        "",
        "## Findings",
        *[f"- {item}" for item in findings],
        "",
    ]
    if risks:
        markdown_lines.extend(["## Risks", *[f"- {item}" for item in risks], ""])
    markdown_lines.extend(["## Recommendations", *[f"- {item}" for item in recommendations]])

    notes_lines = [
        "# Consolidation Notes",
        "",
        "- Deduplicated findings and recommendations across agents.",
        "- Applied fixed priority: Security/Governance, Architecture/Operations, Code Quality.",
    ]
    if not risks:
        notes_lines.append("- No explicit risks were raised by specialist agents.")

    return "\n".join(markdown_lines).strip() + "\n", "\n".join(notes_lines).strip() + "\n"


def _split_orchestrator_output(output: str) -> Tuple[str, str] | None:
    if "<FINAL_ANSWER>" not in output or "<CONSOLIDATION_NOTES>" not in output:
        return None
    try:
        final_part = output.split("<FINAL_ANSWER>", 1)[1].split("</FINAL_ANSWER>", 1)[0].strip()
        notes_part = output.split("<CONSOLIDATION_NOTES>", 1)[1].split("</CONSOLIDATION_NOTES>", 1)[0].strip()
    except IndexError:
        return None
    if not final_part or not notes_part:
        return None
    return final_part + "\n", notes_part + "\n"


def run_orchestrator(req: AgentRequest, agent_results: Iterable[AgentResult]) -> Tuple[str, str]:
    client = build_openai_client()
    messages = _build_messages(req, agent_results)
    response = call_openai(client, messages)
    split = _split_orchestrator_output(response)
    if split:
        return split
    return _fallback_consolidation(agent_results)
