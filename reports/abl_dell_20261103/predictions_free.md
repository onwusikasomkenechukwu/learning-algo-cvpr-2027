# Predicted crossovers, 2026-10-28 (Task 2.8, written before any low-inlier run)

Inputs (all samples of success.json; per-sample time c = eval_f.py runtime / RANSAC iterations in C++ on courtyard):

| method | s | c (ms per sample) | h (hypotheses per sample) |
|---|---|---|---|
| 6pt+P3P | 0.462 | 0.1395 | 3.645 |
| 4p3vf(M) | 0.403 | 0.1422 | 2.753 |
| ours (seeds + endpoints) | s_E = 0.033 | 0.1422 (tracking 0.000) | 0.410 endpoints |
| 4p3vf(M) + two-view refit | 0.387 | 0.3572 | 2.941 |
| sequential, stage 1 (6pt, views 1-2) | 0.387 | 0.0107 (both stages, per iteration) | 2.059 |
| sequential, stage 2 (P3P, given stage 1) | 0.875 | | 2.139 |

Scoring cost: 89.8 ns per hypothesis and match (time per iteration of 6pt+P3P = 0.1005 ms + 327.2 ns x N over 192 triplets, divided by h_6; median N = 113).

Measured outlier mixture (view3 0.29, view1 0.18, view2 0.05, whole 0.43, other 0.05).

| Outlier type | ours vs 6pt+P3P | ours vs 4p3vf(M) | ours vs sequential | refit vs 6pt+P3P | refit vs sequential |
|---|---|---|---|---|---|
| whole-track | w = 0.947 (ours faster below) | none: ours faster everywhere (ratio 0.95-0.95) | w = 0.287 (ours faster below) | w = 0.572 (refit faster below) | w = 0.173 (refit faster below) |
| view-3 | none: ours slower everywhere (ratio 1.11-1.17) | none: ours faster everywhere (ratio 0.95-1.00) | none: ours slower everywhere (ratio 8.41-28.71) | none: refit slower everywhere (ratio 3.06-3.06) | none: refit slower everywhere (ratio 23.06-75.20) |
| single-view | w = 0.920 (ours faster below) | none: ours faster everywhere (ratio 0.95-1.00) | none: ours slower everywhere (ratio 8.41-1587.16) | w = 0.358 (refit faster below) | none: refit slower everywhere (ratio 23.06-4165.07) |
| measured mixture | w = 0.925 (ours faster below) | none: ours faster everywhere (ratio 0.95-1.00) | none: ours slower everywhere (ratio 8.41-1845.35) | w = 0.399 (refit faster below) | none: refit slower everywhere (ratio 23.06-4844.62) |

w* by the closed form for whole-track outliers against 6pt+P3P (draft Sec. 5): 0.947 (no crossover in (0, 1] when it is >= 1).
