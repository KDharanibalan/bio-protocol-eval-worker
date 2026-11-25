# Protocol Compliance Worker — A/B Evaluation & Release Gate Report

| Worker Mode | Precision | Recall | F1 | FPR | HITL Routing Acc | Avg Latency (ms) | Release Gate |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `v1_naive_single_check` | 1.000 | 0.600 | 0.750 | 0.000 | 0.750 | 0.875 | **FAIL** |
| `v2_structured_checklist` | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.508 | **PASS** |
