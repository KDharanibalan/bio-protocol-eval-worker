"""Reproducible AI evaluation harness with A/B mode comparison, error taxonomy, and CI release gates."""

import json
from pathlib import Path
from typing import Dict, List

import yaml

from .schemas import EvalSummary, ReleaseGateDecision
from .verifier_agent import ProtocolComplianceWorker


def evaluate_worker_mode(
    worker: ProtocolComplianceWorker,
    protocols_dir: Path,
    benchmark_path: Path,
    worker_mode: str = "v2_structured_checklist",
) -> EvalSummary:
    """Evaluate a worker strategy against gold-labeled protocol compliance cases."""
    cases = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    tp = fp = fn = 0
    total_negatives = 0
    hitl_correct = 0
    latencies: List[float] = []
    taxonomy: Dict[str, int] = {
        "missed_violation": 0,
        "false_positive_flag": 0,
        "hitl_routing_mismatch": 0,
    }

    all_rule_ids = {r.rule_id for r in worker.policies}

    for case in cases:
        text = (Path(protocols_dir) / case["file"]).read_text(encoding="utf-8")
        report = worker.audit_protocol(case["case_id"], text, worker_mode=worker_mode)
        latencies.append(report.latency_ms)

        pred = set(report.violated_rules)
        gold = set(case["expected_violated_rules"])

        case_tp = len(pred & gold)
        case_fp = len(pred - gold)
        case_fn = len(gold - pred)
        tp += case_tp
        fp += case_fp
        fn += case_fn
        total_negatives += len(all_rule_ids - gold)

        taxonomy["false_positive_flag"] += case_fp
        taxonomy["missed_violation"] += case_fn

        if report.requires_human_review == bool(case["expected_requires_human_review"]):
            hitl_correct += 1
        else:
            taxonomy["hitl_routing_mismatch"] += 1

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = fp / max(1, total_negatives)

    return EvalSummary(
        worker_mode=worker_mode,
        num_cases=len(cases),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        false_positive_rate=round(fpr, 4),
        hitl_routing_accuracy=round(hitl_correct / max(1, len(cases)), 4),
        avg_latency_ms=round(sum(latencies) / max(1, len(latencies)), 3),
        error_taxonomy=taxonomy,
    )


def check_release_gate(summary: EvalSummary, config_path: Path) -> ReleaseGateDecision:
    """Enforce CI/CD production release criteria before deploying a Digital Worker update."""
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    gate = cfg["release_gate"]
    failed: List[str] = []

    if summary.precision < gate["min_precision"]:
        failed.append(f"precision {summary.precision:.3f} < {gate['min_precision']:.3f}")
    if summary.recall < gate["min_recall"]:
        failed.append(f"recall {summary.recall:.3f} < {gate['min_recall']:.3f}")
    if summary.f1 < gate["min_f1"]:
        failed.append(f"f1 {summary.f1:.3f} < {gate['min_f1']:.3f}")
    if summary.false_positive_rate > gate["max_false_positive_rate"]:
        failed.append(f"fpr {summary.false_positive_rate:.3f} > {gate['max_false_positive_rate']:.3f}")
    if summary.avg_latency_ms > gate["max_avg_latency_ms"]:
        failed.append(f"latency {summary.avg_latency_ms:.2f}ms > {gate['max_avg_latency_ms']:.2f}ms")

    return ReleaseGateDecision(
        passed=len(failed) == 0,
        worker_mode=summary.worker_mode,
        failed_checks=failed,
        summary=summary,
    )


def run_ab_benchmark(
    policies_path: Path,
    protocols_dir: Path,
    benchmark_path: Path,
    config_path: Path,
) -> List[ReleaseGateDecision]:
    """Compare v1 naive prompt logic against v2 structured multi-clause verification."""
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    worker = ProtocolComplianceWorker(
        policies_path,
        escalation_threshold=cfg["worker"]["escalation_confidence_threshold"],
        critical_always_escalate=cfg["worker"]["critical_severity_always_escalate"],
    )
    decisions = []
    for mode in ("v1_naive_single_check", "v2_structured_checklist"):
        summary = evaluate_worker_mode(worker, protocols_dir, benchmark_path, worker_mode=mode)
        decisions.append(check_release_gate(summary, config_path))
    return decisions
