# CVPR 2027 study: final summary (2026-11-03)

Joint work with Dr. Saurav K. Aryal (Howard University). Working title of draft v5:
*Do Hard Minimal Problems Need Exact Solvers? Three-View Relative Pose from Four Points in RANSAC.*
All numbers below come from the complete runs on abl-dell (96 CPU threads, no GPU). The raw summary of the last run is
in [`reports/abl_dell_20261103/REPORT.md`](../reports/abl_dell_20261103/REPORT.md).

## 1. Where the project stands

| Date | Step |
|---|---|
| Oct 20 | Draft v4: an exact single-path homotopy solver from approximate four-point seeds (4p3vf). |
| Oct 23–27 | Both pre-registered tests of that idea came out against it (Section 2). |
| Oct 27 | Draft v5 turns the tests into results and asks what *does* decide between four points and six. |
| Oct 28–30 | First comprehensive run: every experiment of draft v5, on a PoseLib fork with three memory bugs fixed. |
| Nov 2–3 | Large run: supplement and robustness checks (Section 5). It confirms every headline. |
| Nov 3 | Dr. Aryal's decision: a clear negative result, to be written up for **TMLR** (possibly with a per-regime selector). CVPR 2027 moves to a new topic. Results are archived; the study resumes in a few weeks. |

**Headline.** Exactness does not pay, and on real low-inlier matches four points do not pay either. Four points beat
six only for whole-track outliers on semi-synthetic data, and then at lower inlier ratios than the model predicted. On
real triplets, the sequential six-point pipeline, a focal-length prior and PROSAC ordering help most.

## 2. Does exactness pay? (Table 2 of the draft)

Both thresholds were fixed before the runs. Data: Cambridge Landmarks, 5 scenes × 5,000 SuperPoint+LightGlue triplets.

**Test A: how much does a cheap two-view refit close?** Exactness has room only if the refitted approximate solver
still trails 6pt+P3P by at least 2.0 AUC@10.
- Best refitted variant: 4p3vf(M±δ)+R. It trails 6pt+P3P (54.81) by **1.14 AUC@10**. The 95% CI is [0.98, 1.30] with
  the scenes fixed and [0.72, 1.54] with scenes resampled; no bootstrap replicate reaches 2.0.
- Three RANSAC runs; the best variant is re-selected in every bootstrap replicate.
- Per scene: Great Court 1.64, King's College 0.43, Old Hospital 1.14, Shop Facade 1.22, St Mary's 1.25.
- The refit adds 4.0 to 5.1 AUC@10 to every mean-point variant.
- A refit that re-selects the inliers after refitting closes the rest (Section 5): 54.85 against 54.81. That variant
  was not pre-registered, so it is reported in the supplement, but it points the same way: a cheap refit leaves
  nothing for an exact solver to recover.

**Test B: does the exact path find the right root?** It helps only if continuation reaches the correct root at least
5 points more often than converged Levenberg-Marquardt from the same seeds.
- 23,184 samples (one per triplet). 7,784 have no mean-point seed that passes, which leaves 15,400 seeded. Of those,
  9,367 are ambiguous and 254 have no real correct root, so 5,779 have a usable correct root.
- **Continuation 15.6% vs LM 21.6%: −6.0 points**, 95% CI [−6.9, −5.1], McNemar p = 2.4e-40. LM is ahead in all five
  scenes and at every path length of the free point.
- Other methods, strict success: Newton homotopy 8.0%, Newton's method 5.2%, the released two-step refinement 0.0% (it
  cannot reach an exact root), L-shaped retry 16.7%, start off the solution surface 16.4%.
- The correct-root reference is a genuine solution: in a full solve from 2,672 start roots, the tool's root is one of
  the endpoints for 63/63 synthetic, 44/46 real King's College samples in the first check and **234/238 (98.3%)** in
  the 500-sample check.
- Why exactness does not help: at real noise the four-point problem is badly conditioned. The correct root itself
  meets the 2°/10%-focal criterion on only **3.3%** of usable samples.

## 3. When do four points beat six? (Sec. 4, Fig. 2)

**Model.** With a = fraction of tracks correct in views 1–2 and b = fraction of those correct in view 3 (inlier ratio
w = ab), a joint pipeline with m points on views 1–2 needs about 1/(a^m b³) samples, an approximate four-point solver
1/(a⁴ b³) and a sequential pipeline 1/a^m + 1/b³. So four points gain 1/w² over six for whole-track outliers, nothing
for view-3 outliers, and the sequential pipeline can win for single-view outliers. Crossovers were predicted from rates
measured on the tuning scene and dated on Oct 28 at 14:01, before any low-inlier run (Oct 29).

**Primary test (fails).** The pre-registered test asks whether four points with the refit beat both six-point
pipelines at matched runtime on the 13,744 real SIFT triplets with w < 0.4 (16 scenes, guarded against wrong reference
cameras). Per-triplet values averaged over RANSAC seeds 0–2:

| Comparison | Difference in AUC@10 | 95% CI (two-level bootstrap) | scene-stratified CI | one-sided p |
|---|---|---|---|---|
| 4p3vf(M)+refit minus 6pt+P3P | **−9.3** | [−14.8, −3.9] | [−10.8, −7.9] | 0.9999 |
| 4p3vf(M)+refit minus sequential | **−15.9** | [−21.4, −10.7] | [−18.3, −13.8] | 1 |

Intersection-union p = 1: not superior. The comprehensive run (seed 0 only) gave −8.8 and −14.7. The result holds
under every robustness check (intersection-union p = 1 in each):

| Check | vs 6pt+P3P | vs sequential |
|---|---|---|
| labels at 4 px instead of 2 px (13,304 triplets) | −9.3 [−14.8, −4.0] | −16.4 [−21.6, −10.9] |
| budget × ¼ | −9.7 [−14.9, −5.3] | −21.2 [−26.7, −16.1] |
| budget × 4 | −8.7 [−13.3, −4.1] | −10.1 [−15.2, −5.1] |

**AUC@10 at matched runtime**, read at the mean single-core time of 6pt+P3P at default settings (186 ms on SIFT, 34 ms
on SP+LG):

| Method | SIFT, w < 0.4 | SP+LG |
|---|---|---|
| 6pt+P3P | 34.41 | 63.38 |
| Sequential, six points then P3P | 41.05 | 48.57 |
| 5pt+P3P+R+F at a guessed f | 18.71 | 27.96 |
| 5pt+P3P+R+F at a GeoCalib f | 45.94 | 64.38 |
| 5pt+P3P+R+F at f from the fundamental matrix | 23.88 | – |
| 4p3vf(M) | 25.02 | 45.40 |
| 4p3vf(M) with refit | 25.12 | 44.01 |
| 4p3vf(M±δ) with refit | 20.97 | 42.37 |
| 6pt+P3P, PROSAC | **53.31** | – |
| Sequential, PROSAC | 47.03 | – |
| 4p3vf(M) with refit, PROSAC | 44.01 | – |
| 4p3vf(O), oracle (ground-truth virtual points) | 51.49 | 68.31 |

**Semi-synthetic outliers against the dated predictions** (crossover = inlier ratio below which the refit wins):

| Outlier type | vs 6pt+P3P: predicted → measured | vs sequential: predicted → measured |
|---|---|---|
| whole-track | 0.572 → **0.40** [0.34, 0.50] | 0.173 → **0.74** [0.68, 0.75] |
| view-3 | none → none ✓ | none → none ✓ |
| single-view | 0.358 → **none** (refit never wins) | none → none ✓ |
| measured mixture | 0.399 → **none** | none → none ✓ |

The model gets the qualitative picture right (whole-track yes, view-3 no, sequential strong for single-view outliers),
but it overestimates the advantage of four points. On real triplets binned by inlier ratio, the refit never crosses
6pt+P3P (a crossing appears in only 18% of bootstrap replicates; predicted 0.40), and it beats the sequential pipeline
only between w ≈ 0.4 and 0.7 (upper crossing 0.705 [0.63, 0.95]; predicted: never). The sequential pipeline is best
below w = 0.3.

## 4. Default settings (Table 1, Table 3)

Shared focal length, AUC@10, three RANSAC runs:

| Method | Cambridge | median ξ_f | ETH3D (11 scenes) | single-core ms (SP+LG) |
|---|---|---|---|---|
| 6pt+P3P | 54.81 | 7.5% | 71.79 | 34 |
| Sequential | 46.80 | 9.6% | 48.37 | 7 |
| 5pt+P3P+R+F at a guessed f | 52.46 | 7.7% | 18.68 | 62 |
| 5pt+P3P+R+F at a GeoCalib f | **56.93** | 6.8% | 69.53 | 27 |
| 5pt+P3P+R+F at f from F (seed 0) | 53.76 | – | 28.22 | – |
| 4p3vf(M) | 48.02 | 8.8% | 53.02 | 33 |
| 4p3vf(M) with refit | 52.84 | 7.8% | 58.19 | 56 |
| 4p3vf(M±δ) with refit | 53.36 | 7.7% | 59.43 | 79 |
| Oracle | 55.34 | 7.4% | 74.54 | 14 |
| VGGT, then three-view LO | **60.10** | 5.9% | 72.69 | 2 + about 25 s network |

- VGGT's network costs about 25 s per triplet on the CPU; the three-view LO after it takes 2 ms.
- The guessed focal length (1.25 × the larger image side, the COLMAP default) fails on ETH3D's DSLR images; the focal
  length from the fundamental matrix only partly repairs it (28.2).
- The Cambridge gap between 6pt+P3P and 4p3vf(M), 6.79, matches the published 6.91.

Calibrated cameras:
- **PhotoTourism** (released triplets, default settings): 5pt+P3P 77.16, sequential 75.41, refitted four-point variants
  77.13–77.36, learned HC 76.27.
- **Low-inlier SIFT at matched runtime:** sequential 64.47 against 43.68 for 5pt+P3P and 25.6–36.3 for the four-point
  variants.
- **Semi-synthetic whole-track outliers at w = 0.25:** sequential 60.68, 5pt+P3P 51.66, four-point variants 19.0–43.8.
  With calibrated cameras four points gain only 1/w over five, and that does not cover their cost.

## 5. Supplement and robustness (large run, Nov 2–3)

- **RANSAC seeds 1–2** for the primary-test curves: the result moved from −8.8/−14.7 to −9.3/−15.9 (Section 3).
- **¼× and 4× budgets, labels at 4 px:** the primary test fails in each (Section 3).
- **PROSAC** (correspondences ordered by match quality) is the largest single gain found: +18.9 AUC@10 for 6pt+P3P
  [14.1, 24.4] and for the refit [14.4, 24.0], +6.0 for the sequential pipeline [3.0, 9.2]. It lifts every method by
  about the same amount, so four points still trail six by 9.3 under PROSAC.
- **Focal length from the fundamental matrix (views 1–2):** 23.88 at matched runtime, 53.76 Cambridge and 28.22 ETH3D at
  default settings; far below the GeoCalib prior.
- **RANSAC threshold** (Cambridge SP+LG, seed 0): 10 px helps every method; the ranking does not change.

  | Method | 3 px | 5 px | 10 px |
  |---|---|---|---|
  | 6pt+P3P | 53.20 | 54.82 | 56.13 |
  | Sequential | 40.89 | 46.77 | 50.97 |
  | 4p3vf(M) | 45.50 | 47.98 | 49.64 |
  | 4p3vf(M) with refit | 49.37 | 52.94 | 55.12 |

- **Refit ablations** (Cambridge SP+LG, seeds 0–2): squared loss instead of Cauchy changes nothing (52.80 vs 52.84);
  re-selecting the inliers after the refit adds 1.25 (54.09; 54.85 for 4p3vf(M±δ)+R, level with 6pt+P3P's 54.81);
  keeping only refits that set a new best loses 3.3 (49.55).
- **Choice of view 3** (views 2 and 3 swapped): small for the four-point methods (−3.0 to +0.8); the sequential
  pipeline gains 3.8 (SP+LG) and 5.6 (low-inlier SIFT).
- **Tzamos et al.'s Table 2 with the fixed fork:** our numbers lie above the published ones, by 0.2 to 4.4 AUC@10 on
  PhotoTourism and 7.2 to 8.6 on Aachen, except the 4p3v(A) rows without ENM on Aachen (7.6 to 10.0 below). Every
  variant with ENM lands between 77.07 and 77.37 on PhotoTourism.
- **Full solve, 500 King's College samples:** the correct-root tool's root is a full-solve endpoint for 234 of 238
  usable samples (98.3%).
- **Test B exclusions** do not depend on reprojection error (58.8–62.5% ambiguous per quartile) and fall slowly with
  planarity (67.1% to 53.7%).

## 6. Engineering findings

- **Three memory bugs in the authors' PoseLib fork, fixed and to be released:**
  - an out-of-bounds read in inner refinement (every "+R" method refined on an arbitrary fifth track; it caused day-long
    hangs);
  - P3P reading an empty vector;
  - a Jacobian column that was never set, so every three-view LO and final refinement used stack garbage. The
    calibrated version also wrote past the end of the array.

  Fixing the last one moved test A from 1.61 to 1.14 AUC@10.
- **New estimators in the fork:** a calibrated sequential 5pt → P3P pipeline, and a three-view LO started from given
  cameras (used by the focal-prior and VGGT rows). Both pass a smoke test on the server.
- **Evaluation data:**
  - a semi-synthetic outlier generator whose inlier ratios and outlier types hold exactly under the labels, including
    with real lens distortion;
  - per-view track labels for about 28,000 real triplets, two matchers each.
- **Matched-runtime protocol:** fixed-iteration accuracy curves (10 to 30,000 iterations) plus single-core timing on
  one pinned core. It produces per-triplet matched values, so every comparison is paired.

## 7. Next steps (TMLR)

- Archive the results, raw outputs and weights on abl-dell and the SSD (`bash scripts/run_abl_dell.sh archive`).
- Rewrite draft v5 as a negative-result paper for TMLR with these numbers. A per-regime selector (sequential at low w,
  6pt+P3P or a focal prior otherwise, PROSAC throughout) is the candidate positive contribution.
- Not built (needs code or packages that are not available offline): the depth-prior row, per-iteration focal
  sampling, Hfff+P3P and alphaCertified certification.
