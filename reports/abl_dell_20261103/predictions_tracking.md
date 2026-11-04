# Predicted crossovers, 2026-10-28 (Task 2.8, written before any low-inlier run)

Inputs (all samples of success.json; per-sample time c = eval_f.py runtime / RANSAC iterations in C++ on courtyard):

| method | s | c (ms per sample) | h (hypotheses per sample) |
|---|---|---|---|
| 6pt+P3P | 0.462 | 0.1395 | 3.645 |
| 4p3vf(M) | 0.403 | 0.1422 | 2.753 |
| ours (seeds + endpoints) | s_E = 0.033 | 127.8505 (tracking 127.708) | 0.410 endpoints |
| 4p3vf(M) + two-view refit | 0.387 | 0.3572 | 2.941 |
| sequential, stage 1 (6pt, views 1-2) | 0.387 | 0.0107 (both stages, per iteration) | 2.059 |
| sequential, stage 2 (P3P, given stage 1) | 0.875 | | 2.139 |

Scoring cost: 89.8 ns per hypothesis and match (time per iteration of 6pt+P3P = 0.1005 ms + 327.2 ns x N over 192 triplets, divided by h_6; median N = 113).

Measured outlier mixture (view3 0.29, view1 0.18, view2 0.05, whole 0.43, other 0.05).

| Outlier type | ours vs 6pt+P3P | ours vs 4p3vf(M) | ours vs sequential | refit vs 6pt+P3P | refit vs sequential |
|---|---|---|---|---|---|
| whole-track | w = 0.032 (ours faster below) | none: ours slower everywhere (ratio 857.64-857.64) | none: ours slower everywhere (ratio 4.36-7558.82) | w = 0.572 (refit faster below) | w = 0.173 (refit faster below) |
| view-3 | none: ours slower everywhere (ratio 1001.95-1049.55) | none: ours slower everywhere (ratio 857.64-898.39) | none: ours slower everywhere (ratio 7558.82-25815.27) | none: refit slower everywhere (ratio 3.06-3.06) | none: refit slower everywhere (ratio 23.06-75.20) |
| single-view | none: ours slower everywhere (ratio 125.90-1001.95) | none: ours slower everywhere (ratio 857.64-896.75) | none: ours slower everywhere (ratio 7558.82-1427274.36) | w = 0.358 (refit faster below) | none: refit slower everywhere (ratio 23.06-4165.07) |
| measured mixture | none: ours slower everywhere (ratio 95.17-1001.95) | none: ours slower everywhere (ratio 857.64-896.37) | none: ours slower everywhere (ratio 7558.82-1659445.87) | w = 0.399 (refit faster below) | none: refit slower everywhere (ratio 23.06-4844.62) |

w* by the closed form for whole-track outliers against 6pt+P3P (draft Sec. 5): 0.032 (no crossover in (0, 1] when it is >= 1).
