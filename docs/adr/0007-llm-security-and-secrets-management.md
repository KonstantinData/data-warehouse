# 0007 – LLM Security & Secrets Management

*Status:* Accepted

## Context

LLM-assisted workflows may handle sensitive data. API keys and credentials must remain protected at all times.

## Decision

Sensitive values are masked, and secrets are managed exclusively through secure secret stores. LLMs receive only the minimum required, approved context.

## Rationale

* **Data protection:** Minimizes leakage risk.
* **Compliance:** Aligns with security and privacy requirements.
* **Trust:** Maintains strict control over confidential information.

## Consequences

* Additional security checks in the pipeline.
* Team training for secure data handling practices.
