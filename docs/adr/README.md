# Architecture Decision Records (ADR) Governance

## Scope
- Covers the policy for recording, approving, and maintaining ADRs in `docs/adr/`.
- Does not describe individual architectural decisions; see the ADR index for those.

## Guarantees
- Every architectural decision is tracked in a versioned ADR and indexed in `0000-adr-index.md`.
- Accepted ADRs are immutable; changes are represented by a new ADR that supersedes the prior one.
- Status, ownership, and decision authority are explicit for each ADR.

## Non-goals
- Onboarding guidance or system overviews (see the root `README.md`).
- Implementation details for any specific decision.

## Role of ADRs in This Repository
- **Why ADRs exist:** Provide a durable, auditable record of architectural decisions and their rationale.
- **Decisions that require an ADR:**
  - Data layer contracts and invariants.
  - Artifact lifecycle and storage policies.
  - Orchestration entry points and execution model.
  - Security, compliance, and governance policies that affect system behavior.
- **Decisions that do not require an ADR:**
  - Local refactors that do not change system behavior or contracts.
  - Documentation fixes or formatting changes.
  - Routine dependency bumps without architectural impact.

## ADR Lifecycle
- **Proposed:** Draft under review; not binding.
- **Accepted:** Approved and binding; supersedes prior conflicting guidance.
- **Superseded:** Replaced by a newer ADR; retained for history.
- **Deprecated:** No longer recommended; use is actively discouraged.

**Modification rules**
- Accepted ADRs are immutable; any change must be made via a new ADR that supersedes the old one.
- Proposed ADRs may be edited until accepted.
- Superseded and Deprecated ADRs must remain in the repository for auditability.

## ADR Index Contract
- `0000-adr-index.md` is the single, authoritative index of ADRs.
- All ADRs must be registered in the index before being treated as Proposed or Accepted.
- **Naming/numbering scheme:** strictly monotonic numeric prefixes; numbers are never reused.

## Decision Authority
- **Approvers:** repository maintainers with write access.
- **Disagreement resolution:** maintainers seek consensus; if unresolved, the decision remains Proposed.
- **No decision made:** the ADR stays Proposed and has no binding effect.

## Change Discipline
- Any architectural change that alters a contract or invariant must update or supersede the relevant ADR.
- If a README conflicts with an ADR, the ADR is authoritative and the README must be corrected.
- Violations of ADR consistency block release or review approval until resolved.

## Links
- **Upstream:** Root system overview and terminology: `README.md`.
- **Downstream:** ADR index: `0000-adr-index.md`.
