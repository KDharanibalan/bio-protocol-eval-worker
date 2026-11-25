"""Unit and release-gate tests for bio-protocol-eval-worker."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval_worker.eval_harness import run_ab_benchmark
from eval_worker.verifier_agent import ProtocolComplianceWorker


def test_compliant_protocol_auto_approved():
    worker = ProtocolComplianceWorker(ROOT / "data" / "regulatory_policies.json")
    text = (ROOT / "data" / "sample_protocols" / "protocol_ev_compliant.md").read_text(encoding="utf-8")
    report = worker.audit_protocol("PROT-001", text, worker_mode="v2_structured_checklist")
    assert report.violated_rules == []
    assert report.requires_human_review is False
    assert report.human_review_ticket is None
    assert len(report.audit_trace) == 4


def test_critical_safety_gap_triggers_p0_hitl_ticket():
    worker = ProtocolComplianceWorker(ROOT / "data" / "regulatory_policies.json")
    text = (ROOT / "data" / "sample_protocols" / "protocol_dex_safety_gap.md").read_text(encoding="utf-8")
    report = worker.audit_protocol("PROT-003", text, worker_mode="v2_structured_checklist")
    assert set(report.violated_rules) == {"POL-BSL2-001", "POL-CHEM-002"}
    assert report.requires_human_review is True
    assert report.human_review_ticket is not None
    assert report.human_review_ticket.priority == "P0_CRITICAL"


def test_v2_structured_checklist_outperforms_v1_and_passes_gate():
    decisions = run_ab_benchmark(
        ROOT / "data" / "regulatory_policies.json",
        ROOT / "data" / "sample_protocols",
        ROOT / "data" / "benchmark_cases.json",
        ROOT / "configs" / "eval_suite.yaml",
    )
    by_mode = {d.worker_mode: d for d in decisions}
    v1 = by_mode["v1_naive_single_check"]
    v2 = by_mode["v2_structured_checklist"]

    assert v1.passed is False
    assert v2.passed is True
    assert v2.summary.f1 > v1.summary.f1
    assert v2.summary.hitl_routing_accuracy == 1.0
