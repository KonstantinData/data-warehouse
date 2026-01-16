# 0013 – Code Security, Governance, and Compliance Evaluation

*Status:* Accepted

## Context

Security and compliance reviews require a consistent lens to detect vulnerabilities, policy drift, and governance gaps in generated code.

## Decision

Define the responsibilities and evaluation criteria for the **code_security_governance_compliance** agent.

## Rationale

* **Security posture:** Findings focus on protecting secrets, inputs, and access controls.
* **Governance:** Reviews track auditability and policy adherence.
* **Regulatory alignment:** Compliance requirements are surfaced early.

## Consequences

* Reviews must inspect authentication, authorization, data handling, and logging.
* Findings should include clear remediation steps for risk reduction.
