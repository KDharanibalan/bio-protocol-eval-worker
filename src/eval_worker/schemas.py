"""Pydantic v2 contracts for protocol compliance auditing, HITL routing, and AI release gates."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    rule_id: str
    category: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    applies_when_keywords: List[str]
    required_evidence_groups: List[List[str]]
    description: str


class ComplianceFinding(BaseModel):
    rule_id: str
    category: str
    severity: str
    status: Literal["PASS", "VIOLATION"]
    confidence: float = Field(ge=0.0, le=1.0)
    matched_evidence: List[str]
    missing_requirements: List[str]
    rationale: str


class HumanReviewTicket(BaseModel):
    ticket_id: str
    protocol_id: str
    priority: Literal["P0_CRITICAL", "P1_HIGH", "P2_STANDARD"]
    reason: str
    flagged_rules: List[str]


class AuditReport(BaseModel):
    protocol_id: str
    worker_mode: str
    applicable_rules: List[str]
    findings: List[ComplianceFinding]
    violated_rules: List[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
    human_review_ticket: Optional[HumanReviewTicket] = None
    audit_trace: List[str]
    latency_ms: float


class EvalSummary(BaseModel):
    worker_mode: str
    num_cases: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    hitl_routing_accuracy: float
    avg_latency_ms: float
    error_taxonomy: Dict[str, int]


class ReleaseGateDecision(BaseModel):
    passed: bool
    worker_mode: str
    failed_checks: List[str]
    summary: EvalSummary
