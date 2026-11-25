"""Multi-step Protocol Compliance Verification Digital Worker with HITL Escalation."""

import json
import re
import time
from pathlib import Path
from typing import List

from .schemas import AuditReport, ComplianceFinding, HumanReviewTicket, PolicyRule


class ProtocolComplianceWorker:
    """Autonomous multi-step protocol auditor with traceable reasoning and confidence-gated HITL routing.

    Supports two evaluation modes for reproducible A/B experimentation:
    - ``v1_naive_single_check``: checks only whether ANY single required evidence group appears
      (simulates an under-specified prompt that misses multi-clause compliance gaps).
    - ``v2_structured_checklist``: decomposes every applicable policy into mandatory evidence clauses,
      verifies each clause independently, calibrates confidence, and routes critical/uncertain cases
      to a Human-in-the-Loop review queue.
    """

    def __init__(
        self,
        policies_path: Path,
        escalation_threshold: float = 0.80,
        critical_always_escalate: bool = True,
    ):
        raw = json.loads(Path(policies_path).read_text(encoding="utf-8"))
        self.policies: List[PolicyRule] = [PolicyRule.model_validate(item) for item in raw]
        self.escalation_threshold = escalation_threshold
        self.critical_always_escalate = critical_always_escalate

    def _retrieve_applicable_policies(self, text_lower: str) -> List[PolicyRule]:
        applicable = []
        for rule in self.policies:
            if any(re.search(rf"\b{re.escape(kw.lower())}\b", text_lower) for kw in rule.applies_when_keywords):
                applicable.append(rule)
        return applicable

    def audit_protocol(
        self,
        protocol_id: str,
        protocol_text: str,
        worker_mode: str = "v2_structured_checklist",
    ) -> AuditReport:
        t0 = time.perf_counter()
        low = protocol_text.lower()
        trace: List[str] = [f"Step 1 [Parse]: Ingested protocol '{protocol_id}' ({len(protocol_text.split())} words)."]

        applicable = self._retrieve_applicable_policies(low)
        trace.append(
            f"Step 2 [Policy Retrieval]: Matched {len(applicable)} applicable clauses: "
            f"{[r.rule_id for r in applicable]}."
        )

        findings: List[ComplianceFinding] = []
        violated_rules: List[str] = []

        for rule in applicable:
            matched_evidence: List[str] = []
            missing_reqs: List[str] = []

            for group in rule.required_evidence_groups:
                hit = next((kw for kw in group if kw.lower() in low), None)
                if hit:
                    matched_evidence.append(hit)
                else:
                    missing_reqs.append(" OR ".join(group))

            if worker_mode == "v1_naive_single_check":
                # Naive baseline: passes if ANY single evidence group is present
                is_violation = len(matched_evidence) == 0
                confidence = 0.72 if is_violation else 0.78
            elif worker_mode == "v2_structured_checklist":
                # Structured verification: ALL required evidence clauses must be satisfied
                is_violation = len(missing_reqs) > 0
                clause_ratio = len(matched_evidence) / max(1, len(rule.required_evidence_groups))
                confidence = round(0.95 if is_violation else 0.85 + 0.12 * clause_ratio, 3)
            else:
                raise ValueError(f"Unsupported worker_mode: {worker_mode}")

            status = "VIOLATION" if is_violation else "PASS"
            if is_violation:
                violated_rules.append(rule.rule_id)
                rationale = f"Missing mandatory requirement(s): {missing_reqs}. Policy: {rule.description}"
            else:
                rationale = f"All required compliance evidence verified: {matched_evidence}."

            findings.append(
                ComplianceFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    status=status,
                    confidence=confidence,
                    matched_evidence=matched_evidence,
                    missing_requirements=missing_reqs,
                    rationale=rationale,
                )
            )

        trace.append(
            f"Step 3 [Cross-Check ({worker_mode})]: Evaluated {len(findings)} policies; "
            f"detected {len(violated_rules)} violation(s): {violated_rules}."
        )

        overall_conf = round(
            sum(f.confidence for f in findings) / max(1, len(findings)),
            3,
        )
        has_critical = any(f.status == "VIOLATION" and f.severity == "CRITICAL" for f in findings)
        has_any_violation = len(violated_rules) > 0
        requires_hitl = (
            has_any_violation
            or overall_conf < self.escalation_threshold
            or (self.critical_always_escalate and has_critical)
        )

        ticket = None
        if requires_hitl:
            priority = "P0_CRITICAL" if has_critical else ("P1_HIGH" if has_any_violation else "P2_STANDARD")
            reason = (
                f"Flagged {len(violated_rules)} policy violation(s) ({violated_rules})."
                if has_any_violation
                else f"Confidence ({overall_conf}) below auto-approval threshold ({self.escalation_threshold})."
            )
            ticket = HumanReviewTicket(
                ticket_id=f"HITL-{protocol_id}",
                protocol_id=protocol_id,
                priority=priority,
                reason=reason,
                flagged_rules=violated_rules,
            )
            trace.append(f"Step 4 [HITL Routing]: Escalated to human review queue ({ticket.ticket_id}, {priority}).")
        else:
            trace.append("Step 4 [Auto-Approve]: All applicable policies satisfied above confidence threshold.")

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        return AuditReport(
            protocol_id=protocol_id,
            worker_mode=worker_mode,
            applicable_rules=[r.rule_id for r in applicable],
            findings=findings,
            violated_rules=violated_rules,
            overall_confidence=overall_conf,
            requires_human_review=requires_hitl,
            human_review_ticket=ticket,
            audit_trace=trace,
            latency_ms=latency_ms,
        )
