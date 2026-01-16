"""Code quality and maintainability specialist agent."""

from __future__ import annotations

from src.agents.llm_utils import build_openai_client, call_openai, extract_section_items
from src.agents.agent_types import AgentRequest, AgentResult

ROLE_DESCRIPTION = """
You are a Senior Data Engineer specializing in code quality and maintainability.

Focus on:
- Readability
- Correctness
- Separation of concerns
- Testability
- Long-term maintainability

Deliver concise, senior-level principles.
Avoid tool-specific details unless necessary.
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
            "# Code Quality & Maintainability",
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
        findings = ["No explicit findings were returned; review the source for maintainability issues."]
    if not recommendations:
        recommendations = ["Add targeted tests and documentation to improve long-term maintainability."]

    return AgentResult(
        agent_name="code_quality_and_maintainability",
        raw_markdown=markdown.strip() + "\n",
        findings=findings,
        recommendations=recommendations,
        risks=risks or None,
    )
