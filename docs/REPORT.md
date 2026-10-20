# Project status report — three-view relative pose (CVPR 2027)

*Somkenechukwu Onwusika, 2026-10-20. Everything below was run in this repository; the commands to
reproduce each number are at the end.*

## Summary

- **Infrastructure is done.** The full pipeline runs on `abl-dell` (Ubuntu 24.04, 96 threads, 754 GB RAM,
  no GPU) from one setup script. All three seed papers' own code builds: Hruby et al.'s HC solver,
  Tzamos et al.'s PoseLib fork and evaluation, and SupeRANSAC.
- **Tzamos et al. (CVPR 2025) reproduces with their own code where it matters.** Their best method,
  4p3v(M±δ)+R+F+ENM, gets AUC@5 65.99 vs 66.12 in the paper on PhotoTourism; every variant with inner
  refinement (+R) is within 0.2–1.8. Variants *without* refinement come out 3–9 points below the paper,
  and Aachen comes out 4–8 points above it. A second run on another machine changes nothing by more than
  0.2, so these gaps are systematic: the released code or data differs from what produced the paper.
- **Their unpublished learned 5th point (L) does not pay off.** Before refinement it adds +14 AUC@5 over
  the mean point; after refinement the two are identical (65.45 vs 65.45), and L costs 4–6× the runtime.
- **Our own learned sample-triage prototype shows the same pattern.** A classifier picks good minimal
  samples 1.8× faster than random before refinement, but after refinement it ties a one-line
  "prefer well-spread samples" rule (2.88 vs 2.90 draws).
- **Direction (set by Dr. Aryal, 2026-10-20):** the paper targets three-view relative pose with an
  unknown focal length shared by the three views (the 4p3vf problem) inside LO-RANSAC, evaluated against
  the six-point pipeline (6pt+P3P) on Cambridge Landmarks and ETH3D, including low-inlier SIFT matches.
  The method is in Dr. Aryal's draft and is not described here before submission. Key dates: author order
  Nov 3, paper enrollment Nov 10, supplementary material Nov 23 (2026). Section 6 lists what this repository
  contributes and what is still open.
- Sections 4–5 show that learned improvements to individual hypotheses are erased by refinement; they
  close the triage direction of the brief and remain as background for the paper's design choices.

The research brief with the paper analysis is in [`docs/research_brief.md`](research_brief.md) (also as
[`.docx`](research_brief.docx)). It predates both the Tzamos reproduction and the chosen direction, so its
ranked directions are superseded by section 6.

## 1. Setup

| | |
|---|---|
| Machine | `abl-dell`: Ubuntu 24.04.2, 96 threads, 754 GB RAM, no NVIDIA GPU (CPU PyTorch), ~170 GB free |
| Data | External SSD, ~380 GB, linked into `data/` (see [`data/README.md`](../data/README.md)) |
| Environment | conda env `cvpr`: Python 3.12, PyTorch 2.14.1 (CPU), PoseLib, OpenCV, LightGlue |
| Setup | `bash scripts/setup_workstation.sh` (guide: [`docs/WORKSTATION_SETUP.md`](WORKSTATION_SETUP.md)) |

Building the seed code against current PyTorch / Python 3.12 / CMake 4 needed real fixes, kept as reviewed
patches on the pinned commits rather than ad-hoc edits:
- [`scripts/patches/poselib-threeview.patch`](../scripts/patches/poselib-threeview.patch) — Tzamos's PoseLib
  fork: find libtorch through the target Python (it hard-coded the author's path), C++20 (required by
  libtorch ≥ 2.10), no `-Werror` (GCC 13 false positives in Eigen), and a current pybind11 (the vendored
  one predates Python 3.12).
- [`scripts/patches/threeview.patch`](../scripts/patches/threeview.patch) — their released evaluation
  crashes on the published Aachen triplets (image names like `db/123.jpg` are nested HDF5 groups); fixed
  without changing PhotoTourism results.

## 2. Our own baselines (2026-10-14/15)

| Experiment | Result | Reference |
|---|---|---|
| 2-view, CVPR 2020 RANSAC tutorial val (9,900 pairs), PoseLib 5pt LO-RANSAC | mAA@10 0.767 | — |
| 2-view, tutorial test, 9 of 11 scenes (42,301 pairs) | mAA@10 0.709 | — |
| Tutorial test ground truth (not shipped) rebuilt from IMC 2020 COLMAP models | 79–95% of confident matches within 2 px on 8/9 scenes (official val GT: 74–83%) | — |
| ETH3D pair sampler | 1,969 pairs | SupeRANSAC: 1,969 |
| Hruby et al. 4p3v training sampler, Python port | invariants exact to 1e-13; their released script has a bug | — |
| 3-view, our Python 5pt→P3P, PhotoTourism 12 scenes, AUC@5/10/20 | 59.2 / 70.8 / 79.6 | paper 5pt+P3P 62.9 / 74.3 / 83.0 |
| 3-view, our Python 5pt→P3P, Aachen | 39.5 / 55.6 / 68.7 | paper 43.4 / 56.7 / 68.3 |

## 3. Tzamos et al. (CVPR 2025) with their own code

Their `eval.py --table` at 5 px on all extracted triplets (12 PhotoTourism scenes as in the paper, plus
Aachen v1.1), compared with Table 2 of arXiv 2303.16078v5. Error and AUC computed exactly as in their
`utils/tables.py` (all triplets of a dataset pooled). Paper names → code names: 5pt+P3P = `5p3v`,
+F = `+ C`, M±δ = `M-D`. "ms" = mean time per RANSAC call on abl-dell (96 processes in parallel, so compare
rows with each other, not with the paper's milliseconds).

**PhotoTourism, AUC@5 / @10 / @20**

| Method | Ours | Paper | Δ AUC@5 | ms |
|---|---|---|---|---|
| 4p(HC) [Hruby] | 65.03 / 75.92 / 83.90 | 62.41 / 73.53 / 81.94 | +2.62 | 67.7 |
| 5pt+P3P | 56.45 / 69.90 / 80.43 | 62.93 / 74.30 / 83.00 | −6.48 | 57.5 |
| 5pt+P3P + ENM | 58.55 / 71.53 / 81.51 | 63.77 / 75.03 / 83.50 | −5.22 | 86.1 |
| 4p3v(A) + R + F + ENM | 65.73 / 76.72 / 84.72 | 65.62 / 76.56 / 84.55 | +0.11 | 55.4 |
| 4p3v(M) | 51.28 / 65.86 / 77.85 | 60.86 / 72.56 / 81.73 | −9.58 | 59.3 |
| 4p3v(M) + R | 65.45 / 76.47 / 84.52 | 63.66 / 74.88 / 83.37 | +1.79 | 67.3 |
| 4p3v(M) + R + F | 65.40 / 76.43 / 84.49 | 63.99 / 75.14 / 83.51 | +1.41 | 50.8 |
| 4p3v(M±δ) | 55.18 / 69.25 / 80.25 | 61.86 / 73.73 / 82.78 | −6.68 | 133.5 |
| 4p3v(M±δ) + R | 65.75 / 76.84 / 84.90 | 65.97 / 77.00 / 85.01 | −0.22 | 157.6 |
| 4p3v(M±δ) + R + F | 65.74 / 76.83 / 84.90 | 65.85 / 76.87 / 84.90 | −0.11 | 113.4 |
| **4p3v(M±δ) + R + F + ENM** | **65.99 / 77.08 / 85.16** | **66.12 / 77.14 / 85.15** | **−0.13** | 189.6 |

**Aachen Day-Night v1.1, AUC@5 / @10 / @20**

| Method | Ours | Paper | Δ AUC@5 | ms |
|---|---|---|---|---|
| 4p(HC) | 47.48 / 63.73 / 75.32 | 42.28 / 55.20 / 66.55 | +5.20 | 60.7 |
| 5pt+P3P | 44.65 / 61.49 / 74.22 | 43.43 / 56.73 / 68.28 | +1.22 | 36.6 |
| 4p3v(M) | 38.57 / 55.58 / 69.68 | 41.78 / 55.06 / 66.67 | −3.21 | 36.4 |
| 4p3v(M) + R + F | 47.26 / 63.56 / 75.50 | 43.04 / 56.28 / 67.73 | +4.22 | 29.2 |
| 4p3v(M±δ) + R + F + ENM | 48.60 / 64.97 / 76.77 | 44.02 / 57.42 / 68.97 | +4.58 | 111.2 |

All 18 Table 2 rows are printed by `scripts/compare_tzamos_table.py`.

**Findings**
1. Every variant with inner refinement (+R) reproduces on PhotoTourism (within 0.1–1.8 AUC@5), including
   their headline method.
2. Variants without +R are 3–9 AUC@5 below the paper on PhotoTourism; ENM halves the gap.
3. On Aachen nearly everything is 4–8 points *above* the paper (except the affine variants without ENM,
   10–15 below), even though our independent 5pt→P3P matched the paper there within ~1 point at @10/@20.
4. Repeatability: the full run on abl-dell vs an earlier run on another workstation — all +R rows are
   bit-identical, the rest differ by ≤ 0.2 AUC@5. So findings 2–3 are systematic, not noise. The pinned
   commits are the latest upstream; the last fork commit only adds rebuttal options that are off by default.
5. For our purposes the trustworthy, cheap baselines are 4p3v(M)+R+F (65.40 @ 51 ms) and
   4p3v(A)+R+F+ENM (65.73 @ 55 ms).

## 4. Tzamos et al.'s unpublished learned 5th point

Their fork ships `4p3v(L)` variants that replace the mean point with a network-predicted 5th point
(`res/epoch28_sampson.pt`); it is not in the paper. Run with `eval.py --learning`.

| PhotoTourism | AUC@5 / @10 / @20 | ms | | Hand-designed counterpart | AUC@5 | ms |
|---|---|---|---|---|---|---|
| 4p3v(L) | 65.37 / 76.41 / 84.49 | 308.3 | | 4p3v(M) | 51.28 | 59.3 |
| 4p3v(L) + R | 65.45 / 76.49 / 84.55 | 311.8 | | 4p3v(M) + R | 65.45 | 67.3 |
| 4p3v(L) + R + F | 65.40 / 76.45 / 84.51 | 282.0 | | 4p3v(M) + R + F | 65.40 | 50.8 |
| 4p3v(L-D) | 65.68 / 76.78 / 84.88 | 439.9 | | 4p3v(M±δ) | 55.18 | 133.5 |
| 4p3v(L-D) + R | 65.74 / 76.84 / 84.90 | 471.3 | | 4p3v(M±δ) + R | 65.75 | 157.6 |
| 4p3v(L-D) + R + F | 65.73 / 76.83 / 84.90 | 394.6 | | 4p3v(M±δ) + R + F | 65.74 | 113.4 |
| 4p3v(L-ID) | 64.00 / 75.49 / 84.03 | 602.0 | | | | |

Aachen shows the same: 4p3v(L) 47.15 vs 4p3v(M) 38.57 AUC@5 without refinement, 47.50 vs 47.44 with +R;
4p3v(L) 214.6 ms vs 4p3v(M)+R 41.9 ms.

**Findings.** The learned point is a large win before refinement (+14 AUC@5 PhotoTourism, +8.6 Aachen) and
exactly nothing after it, at 4–6× the runtime (CPU inference inside every RANSAC iteration). This answers
direction 2 of the brief: measuring and extending their learned point is not a promising contribution.

## 5. Our prototype: learned pre-solve sample triage (negative result)

Can a cheap classifier look at a minimal sample *before solving* and predict whether it leads to a good
pose? Tzamos's PhotoTourism triplets, 5pt+P3P, 40 random samples per triplet; trained on 6 scenes, tested
on 6 others (~230K samples each). Features: only what RANSAC sees before solving. Metric: mean number of
draws until the first good sample (pose error < 5°), lower is better.

| What counts as "good" | Random | Match confidence | Min-distance rule | Learned |
|---|---|---|---|---|
| Raw solver output | 10.05 | 11.01 | 5.77 | **5.50** |
| Raw, best-scoring candidate | 10.20 | 11.22 | 5.80 | **5.52** |
| **After refinement (what matters)** | 3.87 | 4.37 | **2.90** | **2.88** |

1. **Outliers are not the bottleneck:** most minimal samples (83–98% per scene) contain no outlier, yet
   only 4–20% give a good raw pose. Failures come from poorly conditioned samples, so ranking by match
   confidence is no better than random.
2. **Refinement equalises:** after local refinement 27–52% of samples are good and every ranking needs
   3–4 draws.
3. **Learning ties a one-line rule where it counts** (2.88 vs 2.90 draws).

Code: [`src/triage_prototype.py`](../src/triage_prototype.py); per-scene results:
[`results/triage/report.json`](../results/triage/report.json) (raw labels) and
[`results/triage_lo/`](../results/triage_lo/) (`report_y.json` raw, `report_y_lo.json` after refinement,
`report_y_pick.json` best-scoring candidate).

## 6. Plan and open work for the paper

The paper works on the shared-focal three-view problem and is evaluated with the PoseLib fork of
Tzamos et al. (commit `272ce27`, branch `threeview`, the latest upstream; built here with the patches of
section 1). What this repository provides and what is still to do:

| Item | Status |
|---|---|
| Fork builds and runs (C++20 / current PyTorch / Python 3.12 patches) | **done** (section 1) |
| Reproduction of Tzamos et al. CVPR 2025 Table 2 on the released triplets (supplement) | **done** (section 3): +R rows within 0.2–1.8 AUC@5; rows without refinement and Aachen miss a 0.5 tolerance systematically |
| Calibrated control rows (5pt+P3P, 4p3v(HC), (M), (M)+R, (M)+ENM, (M)+R+F+ENM, (A)+R+F+ENM, (M±δ)+R+F+ENM) | **done** (section 3); 5pt+P3P+R+F still to add (not in their `--table` set) |
| Learned (L) variants | weights are released (`res/epoch28_sampson.pt`) and load in the shared-focal estimator too, so the (L) rows are runnable; calibrated results in section 4 |
| Shared-focal evaluation (their `eval_f.py`) on released data | to do |
| Cambridge triplets regenerated with SuperPoint + LightGlue and with SIFT; ETH3D triplets | to do: their `datasets/prepare_im.py` hard-codes CUDA, and abl-dell has no GPU (patch for CPU or use a GPU machine) |
| Reproduction of the shared-focal table of arXiv 2303.16078 on regenerated Cambridge triplets | to do, after the triplets |
| Runtime on one pinned core with the CPU model named | to do (abl-dell CPU model to record) |
| Hruby et al. 4p3v sampler and HC solver (background for the homotopy work) | sampler ported and verified (section 2), solver built |

## 7. Open questions

1. **Roles:** which student takes which part (geometry / HC, learning, evaluation, writing).
2. **Reproduction tolerance:** how to report the Table 2 rows that miss the paper systematically
   (section 3, findings 2–4): as measured, with a note on the released code and data?
3. **Compute:** a GPU for SuperPoint/LightGlue triplet generation, or the CPU route on abl-dell?

## Reproducing

```bash
git clone https://github.com/onwusikasomkenechukwu/learning-algo-cvpr-2027.git ~/learning-algo
bash ~/learning-algo/scripts/setup_workstation.sh 2>&1 | tee ~/setup.log      # needs the data SSD
cd ~/learning-algo && conda activate cvpr
nohup bash scripts/run_tzamos_table.sh > ~/table3.log 2>&1 &                    # section 3 (~20 min)
nohup bash scripts/run_tzamos_table.sh --learning -a > ~/table3_L.log 2>&1 &   # section 4, after it
python scripts/compare_tzamos_table.py                                         # tables 3 and 4
python src/eval_relpose.py --help; python src/eval_threeview.py --help          # section 2
python src/triage_prototype.py --help                                          # section 5
```
