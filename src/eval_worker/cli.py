#!/usr/bin/env python3
"""CLI for auditing biological protocols, running A/B evaluations, and checking CI release gates."""

import argparse
import json
import sys
from pathlib import Path

from .eval_harness import run_ab_benchmark
from .verifier_agent import ProtocolComplianceWorker

ROOT = Path(__file__).resolve().parents[2]


def cmd_audit(args: argparse.Namespace) -> int:
    worker = ProtocolComplianceWorker(ROOT / "data" / "regulatory_policies.json")
    text = Path(args.protocol).read_text(encoding="utf-8")
    report = worker.audit_protocol(Path(args.protocol).stem.upper(), text, worker_mode=args.mode)
    print(report.model_dump_json(indent=2))
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    decisions = run_ab_benchmark(
        ROOT / "data" / "regulatory_policies.json",
        ROOT / "data" / "sample_protocols",
        ROOT / "data" / "benchmark_cases.json",
        ROOT / "configs" / "eval_suite.yaml",
    )
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "eval_ab_report.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Protocol Compliance Worker — A/B Evaluation & Release Gate Report",
        "",
        "| Worker Mode | Precision | Recall | F1 | FPR | HITL Routing Acc | Avg Latency (ms) | Release Gate |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for d in decisions:
        s = d.summary
        gate_badge = "PASS" if d.passed else "FAIL"
        lines.append(
            f"| `{s.worker_mode}` | {s.precision:.3f} | {s.recall:.3f} | {s.f1:.3f} "
            f"| {s.false_positive_rate:.3f} | {s.hitl_routing_accuracy:.3f} "
            f"| {s.avg_latency_ms:.3f} | **{gate_badge}** |"
        )
    md = "\n".join(lines) + "\n"
    (reports_dir / "eval_ab_report.md").write_text(md, encoding="utf-8")
    print(md)

    if args.enforce_gate:
        v2 = next(d for d in decisions if d.worker_mode == "v2_structured_checklist")
        if not v2.passed:
            print(f"[GATE FAILED] {v2.failed_checks}", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bio Protocol Compliance Digital Worker & Eval Harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="Audit a single protocol markdown file.")
    p_audit.add_argument("protocol", type=Path)
    p_audit.add_argument("--mode", default="v2_structured_checklist")
    p_audit.set_defaults(func=cmd_audit)

    p_bench = sub.add_parser("benchmark", help="Run A/B evaluation benchmark and check release gates.")
    p_bench.add_argument("--enforce-gate", action="store_true")
    p_bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
