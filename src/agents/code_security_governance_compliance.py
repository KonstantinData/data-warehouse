"""Security governance and compliance specialist agent."""

from __future__ import annotations

from src.agents.llm_utils import build_openai_client, call_openai, extract_section_items
from src.agents.agent_types import AgentRequest, AgentResult

ROLE_DESCRIPTION = """
You are a Security & Data Governance Specialist.

Focus on:
- Secure SDLC
- Secrets management
- Auditability
- GDPR / privacy-by-design implications in code
- Governance-related code practices

Avoid legal interpretation; focus on engineering controls.
""".strip()


def _build_messages(req: AgentRequest) -> list[dict[str, str]]:
    user_prompt = "\n".join(
        [
            "Working prompt:",
            req.working_prompt,
            "",
            "Agent role:",
            ROLE_DESCRIPTION,
            "",
            f"Target path: {req.target_path}",
            "",
            "Target source:",
            "```python",
            req.target_source,
            "```",
            "",
            "Return Markdown with:",
            "# Security, Governance & Compliance",
            "## Findings (bullet list)",
            "## Recommendations (bullet list)",
            "Optional: ## Risks (bullet list)",
        ]
    )
    return [
        {"role": "system", "content": req.system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def run_agent(req: AgentRequest) -> AgentResult:
    client = build_openai_client()
    messages = _build_messages(req)
    markdown = call_openai(client, messages)

    findings = extract_section_items(markdown, "Findings")
    recommendations = extract_section_items(markdown, "Recommendations")
    risks = extract_section_items(markdown, "Risks")

    if not findings:
        findings = ["No explicit security findings were returned; validate with a threat-focused review."]
    if not recommendations:
        recommendations = ["Ensure secrets, logging, and access controls align with governance policies."]

    return AgentResult(
        agent_name="code_security_governance_compliance",
        raw_markdown=markdown.strip() + "\n",
        findings=findings,
        recommendations=recommendations,
        risks=risks or None,
    )
