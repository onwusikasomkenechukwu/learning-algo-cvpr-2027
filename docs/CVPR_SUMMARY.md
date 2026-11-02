# CVPR 2027: summary so far (2026-11-02)

Joint work with Dr. Saurav K. Aryal (Howard University). Working title of draft v5:
*Do Hard Minimal Problems Need Exact Solvers? Three-View Relative Pose from Four Points in RANSAC.*
All numbers below come from the complete runs on abl-dell (96 CPU threads, no GPU) unless marked otherwise.

## 1. Where the project stands

| Date | Step |
|---|---|
| Oct 20 | Draft v4: an exact single-path homotopy solver from approximate four-point seeds (4p3vf). |
| Oct 23–27 | Both pre-registered tests of that idea came out against it (Section 2). |
| Oct 27 | Draft v5 turns the tests into results and asks what *does* decide between four points and six. |
| Oct 28–30 | First comprehensive run: every experiment of draft v5, on a PoseLib fork with three memory bugs fixed. |
| Nov 2 | Large run started: supplement and robustness checks, and three fixes found in the first run. |

**Headline.** Exactness does not pay, and on real low-inlier matches four points do not pay either. Four points beat
six only for whole-track outliers on semi-synthetic data, and then at lower inlier ratios than the model predicted. On
real triplets, the sequential six-point pipeline and a focal-length prior help most.

## 2. Does exactness pay? (Table 2 of the draft)

Both thresholds were fixed before the runs. Data: Cambridge Landmarks, 5 scenes × 5,000 SuperPoint+LightGlue triplets.

**Test A: how much does a cheap two-view refit close?** Exactness has room only if the refitted approximate solver
still trails 6pt+P3P by at least 2.0 AUC@10.
- Best refitted variant: 4p3vf(M±δ)+R. It trails 6pt+P3P (54.81) by **1.14 AUC@10**. The 95% CI is [0.98, 1.30] with
  the scenes fixed and [0.72, 1.54] with scenes resampled; no bootstrap replicate reaches 2.0.
- Three RANSAC runs; the best variant is re-selected in every bootstrap replicate.
- Per scene: Great Court 1.64, King's College 0.43, Old Hospital 1.14, Shop Facade 1.22, St Mary's 1.25.
- The refit adds 4.0 to 5.1 AUC@10 to every mean-point variant.
- The plain mean point with the refit trails by 1.97.

**Test B: does the exact path find the right root?** It helps only if continuation reaches the correct root at least
5 points more often than converged Levenberg-Marquardt from the same seeds.
- 23,184 samples (one per triplet). 7,784 have no mean-point seed that passes, which leaves 15,400 seeded. Of those,
  9,367 are ambiguous and 254 have no real correct root, so 5,779 have a usable correct root.
- **Continuation 15.6% vs LM 21.6%: −6.0 points**, 95% CI [−6.9, −5.1], McNemar p = 2.4e-40. LM is ahead in all five
  scenes.
- Other methods, strict success: Newton homotopy 8.0%, Newton's method 5.2%, the released two-step refinement 0.0% (it
  cannot reach an exact root), L-shaped retry 16.7%, start off the solution surface 16.4%.
- The correct-root reference is a genuine solution: in a full solve from 2,672 start roots, the tool's root is one of
  the endpoints for 63/63 synthetic and 44/46 real King's College samples.
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
cameras).

| Comparison | Difference in AUC@10 | 95% CI (two-level bootstrap) | one-sided p |
|---|---|---|---|
| 4p3vf(M)+refit minus 6pt+P3P | **−8.8** | [−14.8, −2.8] | 0.998 |
| 4p3vf(M)+refit minus sequential | **−14.7** | [−20.9, −8.8] | 1 |

Intersection-union p = 1: not superior.

**AUC@10 at matched runtime**, read at the mean single-core time of 6pt+P3P at default settings:

| Method | SIFT, w < 0.4 | SP+LG |
|---|---|---|
| 6pt+P3P | 34.19 | 63.39 |
| Sequential, six points then P3P | 40.10 | 48.57 |
| 5pt+P3P+R+F at a guessed f | 18.71 | 27.97 |
| 5pt+P3P+R+F at a GeoCalib f | 45.94* | 64.38* |
| 4p3vf(M) | 25.04 | 45.43 |
| 4p3vf(M) with refit | 25.38 | 43.98 |
| 4p3vf(M±δ) with refit | 20.89 | 42.34 |
| 4p3vf(O), oracle (ground-truth virtual points) | 51.46 | 68.32 |

\* GeoCalib's timing included a one-off file load. The fix is in, and the large run re-times it.

**Semi-synthetic outliers against the dated predictions** (crossover = inlier ratio below which the refit wins):

| Outlier type | vs 6pt+P3P: predicted → measured | vs sequential: predicted → measured |
|---|---|---|
| whole-track | 0.572 → **0.40** [0.33, 0.49] | 0.173 → **0.72** [0.67, 0.75] |
| view-3 | none → none ✓ | none → none ✓ |
| single-view | 0.358 → **none** (refit never wins) | none → none ✓ |
| measured mixture | 0.399 → **none** | none → none ✓ |

The model gets the qualitative picture right (whole-track yes, view-3 no, sequential strong for single-view outliers),
but it overestimates the advantage of four points. On real triplets binned by inlier ratio, the sequential pipeline is
best below w = 0.3, and the refit beats it only around w = 0.4–0.7.

## 4. Default settings (Table 1 left, Table 3)

Shared focal length, AUC@10, three RANSAC runs:

| Method | Cambridge | median ξ_f | ETH3D (11 scenes) |
|---|---|---|---|
| 6pt+P3P | 54.81 | 7.5% | 71.79 |
| Sequential | 46.80 | 9.6% | 48.37 |
| 5pt+P3P+R+F at a guessed f | 52.46 | 7.7% | 18.68 |
| 5pt+P3P+R+F at a GeoCalib f | **56.93** | 6.8% | 69.53 |
| 4p3vf(M) | 48.02 | 8.8% | 53.02 |
| 4p3vf(M) with refit | 52.84 | 7.8% | 58.19 |
| 4p3vf(M±δ) with refit | 53.36 | 7.7% | 59.43 |
| Oracle | 55.34 | 7.4% | 74.54 |
| VGGT, then three-view LO | **60.10** | 5.9% | 72.69 |

- VGGT's network costs about 25 s per triplet on the CPU.
- The guessed focal length (1.25 × the larger image side, the COLMAP default) fails on ETH3D's DSLR images.
- The Cambridge gap between 6pt+P3P and 4p3vf(M), 6.79, matches the published 6.91.

Calibrated cameras:
- **PhotoTourism** (released triplets, default settings): 5pt+P3P 77.16, sequential 75.41, refitted four-point variants
  77.13–77.36, learned HC 76.27.
- **Low-inlier SIFT at matched runtime:** sequential 64.48 against 43.73 for 5pt+P3P and 25.6–36.3 for the four-point
  variants.

## 5. Engineering findings

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

## 6. Open items

**Running now (large run, started Nov 2):**
- re-timed GeoCalib and VGGT rows, and the missing calibrated semi-synthetic column;
- RANSAC seeds 1–2 for the primary-test curves;
- matched runtime at ¼× and 4× the budget, and the primary test with labels at 4 px;
- PROSAC variants and a focal prior from the fundamental matrix;
- threshold 3 / 10 px, three refit ablations and the choice of view 3;
- Tzamos et al.'s full Table 2 with the fixed fork (the effect of the fixes);
- a 500-sample full-solve check;
- the supplement tables.

**Not buildable offline:** the depth-prior row (needs a monocular-depth solver and network), per-iteration focal
sampling, Hfff+P3P and alphaCertified certification.

**Decisions for Dr. Aryal:**
- The primary hypothesis is rejected. Does the paper keep "four points vs six" as its second half, now as a largely
  negative finding with the model's partial confirmation? Or does it shift toward what does help on poor matches (the
  sequential pipeline, focal priors, feed-forward cameras)?
- The draft's text, abstract and Table 1 need updating to these numbers. The 2.0 threshold result for test A stands,
  now with a gap of 1.14.
- Deadlines (student instructions and draft): go/no-go and author order Nov 3, paper enrollment Nov 10, submission
  Nov 16 (only on a go), supplement Nov 23.
