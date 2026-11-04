# learning-algo: do hard minimal problems need exact solvers?

Code, data pipeline and results of a study with Dr. Saurav K. Aryal (Howard University) on three-view relative pose
from four points inside RANSAC: calibrated cameras (4p3v) and one camera with an unknown shared focal length (4p3vf).
**Final summary: [`docs/CVPR_SUMMARY.md`](docs/CVPR_SUMMARY.md); raw report of the last run:
[`reports/abl_dell_20261103/REPORT.md`](reports/abl_dell_20261103/REPORT.md).**

## Status (2026-11-03)
**Finished, with a clear negative result.** Planned for CVPR 2027; it goes to TMLR instead (possibly with a
per-regime selector), and CVPR 2027 moves to a new topic. The results are archived and the study resumes in a few
weeks.


**Direction (draft v5).** Four tracks in three views determine the poses, and with one camera also the focal length,
but these minimal problems have hundreds to thousands of complex solutions. Exact solvers therefore track many
homotopy paths, and practice samples five or six points or uses approximate four-point solvers. The paper asks
whether exactness pays inside RANSAC, and what does decide between four points and six: the sample size and which
views the outliers corrupt.

**Results.**
- Exactness does not pay: both pre-registered tests came out against it.
- The primary hypothesis is rejected. On 13,744 real low-inlier triplets, four points with a two-view refit lose to
  both six-point pipelines at matched runtime, over three RANSAC seeds, at ¼× and 4× the budget and with 4 px labels.
- Four points beat six only for whole-track outliers on semi-synthetic data, below w ≈ 0.40.
- On real poor matches, the sequential six-point pipeline, a focal-length prior and PROSAC ordering help most.

## The two tests of exactness
Thresholds fixed before the runs. Data: 5 Cambridge scenes × 5,000 SuperPoint+LightGlue triplets. Statistics:
[`scripts/kill_test_stats.py`](scripts/kill_test_stats.py).

| Test | Rule | Result |
|---|---|---|
| **A**: how much does a two-view refit close? | gap to 6pt+P3P ≥ 2.0 AUC@10 | **Against exactness**: the best refitted variant, 4p3vf(M±δ)+R, trails 6pt+P3P by **1.14**, 95% CI [0.98, 1.30] with the scenes fixed, [0.72, 1.54] with scenes resampled; no bootstrap replicate reaches 2.0; three RANSAC runs |
| **B**: does the exact path find the right root? | ≥ +5 points over converged LM, from identical seeds | **Against exactness**: 15.6% vs 21.6%, **−6.0 points**, 95% CI [−6.9, −5.1], McNemar p = 2.4e-40; 23,184 samples, 5,779 with a usable correct root; LM ahead in all 5 scenes |

- Test A per scene: Great Court 1.64, King's College 0.43, Old Hospital 1.14, Shop Facade 1.22, St Mary's 1.25. The
  refit adds 4.0 to 5.1 AUC@10 to every mean-point variant.
- Test B, strict success from the same seeds: Newton homotopy 8.0%, Newton's method 5.2%, L-shaped retry 16.7%, start
  off the solution surface 16.4%.
- The correct-root reference is a genuine solution: it is one of the full solve's endpoints in 63/63 synthetic and
  44/46 real samples, and in 234/238 of the 500-sample King's College check.
- At real noise the problem is badly conditioned: the correct root itself meets a 2°/10%-focal criterion on only 3.3%
  of usable samples.

## Main results (comprehensive run Oct 28–30, large run Nov 2–3)
**Primary test (pre-registered, fails).** 4p3vf(M) with the refit against both six-point pipelines at matched runtime,
on the 13,744 guarded SIFT triplets with inlier ratio w < 0.4 (16 scenes, RANSAC seeds 0–2): **−9.3** AUC@10 against
6pt+P3P (95% CI [−14.8, −3.9]) and **−15.9** against the sequential pipeline ([−21.4, −10.7]); intersection-union
p = 1. It also fails at ¼× and 4× the budget and with labels at 4 px.

| Method | Matched runtime, SIFT w < 0.4 | Cambridge, default settings | ETH3D, default settings |
|---|---|---|---|
| 6pt+P3P | 34.41 | 54.81 | 71.79 |
| 6pt+P3P with PROSAC | **53.31** | – | – |
| Sequential, six points then P3P | 41.05 | 46.80 | 48.37 |
| 5pt+P3P+R+F at a GeoCalib focal length | 45.94 | **56.93** | 69.53 |
| 4p3vf(M) | 25.02 | 48.02 | 53.02 |
| 4p3vf(M) with two-view refit | 25.12 | 52.84 | 58.19 |
| 4p3vf(M) with two-view refit and PROSAC | 44.01 | – | – |
| VGGT, then three-view LO | n/a | **60.10** | 72.69 |
| Oracle (ground-truth virtual points) | 51.49 | 55.34 | 74.54 |

AUC@10. Default settings: three RANSAC runs. Matched runtime: read at the mean single-core time of 6pt+P3P. PROSAC
adds about 19 AUC@10 to both 6pt+P3P and the refit, so the gap between them stays at 9.3.

**Outlier types against the predictions** (dated Oct 28, before any low-inlier run; crossover = inlier ratio below
which four points with the refit win):

| Outlier type | vs 6pt+P3P: predicted → measured | vs sequential: predicted → measured |
|---|---|---|
| whole-track | 0.57 → 0.40 [0.34, 0.50] | 0.17 → 0.74 [0.68, 0.75] |
| view-3 | none → none | none → none |
| single-view | 0.36 → none | none → none |
| measured mixture | 0.40 → none | none → none |

The model's qualitative picture holds (whole-track yes, view-3 no, sequential strong for single-view outliers), but
it overestimates the advantage of four points.

**Calibrated cameras:**
- PhotoTourism at default settings: all methods land between 75.4 and 77.4 AUC@10.
- Low-inlier SIFT at matched runtime: the sequential pipeline leads clearly, 64.5 against 43.7 for 5pt+P3P.

## When do four points beat six?
Let a be the fraction of tracks correct in views 1–2 and b the fraction of those also correct in view 3 (w = ab). A
joint pipeline that solves views 1–2 from m points and view 3 by P3P needs about 1/(a^m b³) samples, an approximate
four-point solver 1/(a⁴ b³) (an exact one 1/(a⁴ b⁴)), and a sequential pipeline 1/a^m + 1/b³. Hence:
- **whole-track outliers** (b = 1): four points need 1/w² times fewer samples than six and 1/w fewer than five;
- **view-3 outliers** (a = 1): no advantage;
- **single-view outliers**: the sequential pipeline can win (for m = 6 whenever b < about 0.73).

Success rates and costs measured on the tuning scene turn this into the dated crossover predictions
([`scripts/success_rates.py`](scripts/success_rates.py), [`scripts/crossovers.py`](scripts/crossovers.py)). The
outlier labels come from [`scripts/outlier_stats.py`](scripts/outlier_stats.py). The tuning scene's SIFT outliers are
43% whole-track, 29% view-3, 23% single-view and 5% other.

## What the runs produce
| Draft item | What runs | Code |
|---|---|---|
| Table 1 | every shared-focal row on Cambridge and ETH3D SP+LG, RANSAC seeds 0–2 | [`mr_config.py`](scripts/mr_config.py), [`paper_tables.py`](scripts/paper_tables.py) |
| Matched runtime and the primary test | accuracy at fixed iteration counts (10 to 30,000) plus single-core time on one pinned core; per-triplet values read at the 6pt+P3P budget in log time; intersection-union test with a two-level bootstrap | [`matched_runtime.py`](scripts/matched_runtime.py) |
| Fig. 2 | real triplets binned by inlier ratio; semi-synthetic whole-track, view-3, single-view and mixed outliers at w = 0.75–0.25 | [`semisynth_outliers.py`](scripts/semisynth_outliers.py), [`eval_sets.py`](scripts/eval_sets.py) |
| Table 2 | tests A and B | [`kill_test_stats.py`](scripts/kill_test_stats.py) |
| Table 3 | calibrated rows on PhotoTourism and at matched runtime | [`paper_tables.py`](scripts/paper_tables.py) |
| Supplement (large run) | per-scene tables, AUC@5/20, pair (2,3), focal mAA, timing percentiles, RANSAC seeds, ¼× and 4× budgets, 4 px labels, PROSAC, focal prior from the fundamental matrix, threshold 3 / 10 px, refit ablations, choice of view 3, Tzamos et al. Table 2 with the fixed fork, 500-sample full solve, Test B exclusions | [`paper_supplement.py`](scripts/paper_supplement.py) |

Not built (needs code or packages that are not available offline): the depth-prior row, per-iteration focal
sampling, Hfff+P3P and alphaCertified certification.

## Known issues in the seed code (fixed here)
- **Uninitialized and out-of-bounds Jacobian entry in PoseLib@threeview** (found 2026-10-28): both three-view
  Jacobians zero the part of J12 that does not depend on view 3 starting at column 6, but view 3's parameters start at
  column 5. Column 5 was never set, so every LM step of the three-view refinement (LO and the final refinement of every
  three-view estimator) used stack garbage; the calibrated one also wrote one value past the end. Fixing it moved
  test A from 1.61 to 1.14 AUC@10.
- **Out-of-bounds read in `inner_refine`** (both three-view estimators): it copies `sample[k]` for
  k < 4 + `inner_refine_extra`, but a 4p3v sample holds 4 entries, so every '+R' method refined on an arbitrary
  fifth track or faulted (general protection faults on abl-dell). A `reserve(3)` also left P3P reading an empty
  vector. All three fixes: [`scripts/patches/poselib_oob_fixes.py`](scripts/patches/poselib_oob_fixes.py).
- `eval_f.py` forks a `Pool` it never closes; a crashed worker makes it wait forever.
  [`scripts/eval_f_safe.py`](scripts/eval_f_safe.py) runs it unchanged with a pool that survives worker crashes.
- `eval_f.py` never sets the RANSAC seed (PoseLib's default is 0), so repeating a run repeats its draws.
  [`scripts/patches/threeview_seed.py`](scripts/patches/threeview_seed.py) reads it from `EVALF_SEED`.
- `eval_f.py` scores the focal length against view 1 only (`gt_focal_2/3` read `img1`); the released
  `ThreeViewSharedFocalRelativePoseEstimator::delta` dehomogenizes the shifted point by its y coordinate.
  Both left as released and noted.

## Running on abl-dell (no GPU)
Setup once ([`docs/WORKSTATION_SETUP.md`](docs/WORKSTATION_SETUP.md)), then in `~/learning-algo` with
`conda activate cvpr` and the data SSD plugged in. Run `git pull` first when new steps were added:
```bash
ALLOW_DOWNLOADS=1 bash scripts/run_abl_dell.sh fresh    # the comprehensive run, from scratch, in the background
bash scripts/run_abl_dell.sh setup fundamental sets calib seeds extras ablations table2 fullsolve500 timing paper compare collect
bash scripts/run_abl_dell.sh status                      # one-screen progress summary
bash scripts/run_abl_dell.sh stop                        # stop the runner and every job it started
bash scripts/run_abl_dell.sh report                      # summaries into reports/abl_dell_<date>/, committed and pushed
bash scripts/run_abl_dell.sh archive                     # pack and verify everything (ARCHIVE_REMOVE=1 frees the space)
```
The second command is the large run of supplement and robustness checks.

- **Default steps**, in order: `setup`, `machine`, `monodromy`, `triplets`, `eth3d`, `sift`, `evalf`, `killA`, `seq`,
  `control`, `followup`, `semisynth`, `sets`, `geocalib`, `vggt`, `table1`, `curves`, `calib`, `timing`, `paper`,
  `compare`, `crashdebug`, `collect`.
  - `followup` holds kill test B, the full-solve check, Task 2.8 with its dated predictions, and the statistics.
  - Every low-inlier run comes after the predictions are written.
  - `timing` waits for every background job and pins one core.
  - `ALLOW_DOWNLOADS=1` lets `geocalib` and `vggt` create `.venv-nets` (CPU PyTorch, GeoCalib, VGGT-1B weights, about
    6 GB).
- **Large-run steps:** `fundamental`, `seeds`, `extras`, `ablations`, `table2`, `fullsolve500`; the header of
  [`scripts/run_abl_dell.sh`](scripts/run_abl_dell.sh) describes each one.

## Earlier work
Details in [`docs/REPORT.md`](docs/REPORT.md) (written 2026-10-20, before the change of direction).
- **Tzamos et al. (CVPR 2025) reproduced with their own code:** their best method, 4p3v(M±δ)+R+F+ENM, gets AUC@5
  65.99 vs 66.12 in the paper (PhotoTourism). The shared-focal gap reproduces too: with the fixed fork, 6pt+P3P leads
  4p3vf(M) by 6.79 AUC@10 on our five Cambridge scenes, against 6.91 published.
- **The 4p3vf equations behave as derived:** residuals of 3e-15, rank loss of exactly two at coplanar points, the
  orientation class kept through 98/98 coplanar crossings, and 2,672 = 4 × 668 solutions by monodromy.
- **Their unpublished learned 5th point:** +14 AUC@5 before refinement, nothing after it, 4–6× slower.
- **Our learned sample-triage prototype (negative result):** ties a one-line spread rule after refinement.
- **2-view baseline:** PoseLib 5pt LO-RANSAC, mAA@10 0.767 (tutorial val) / 0.709 (test, rebuilt GT).

## Quick start (new machine)
On Ubuntu with internet and the data SSD plugged in:
```bash
git clone https://github.com/onwusikasomkenechukwu/learning-algo-cvpr-2027.git ~/learning-algo
bash ~/learning-algo/scripts/setup_workstation.sh 2>&1 | tee ~/setup.log
```
It checks the machine, installs apt packages and a conda env `cvpr` (CUDA or CPU PyTorch, whichever fits),
links the SSD data, builds the seed papers' code and runs the tests. Then, in `~/learning-algo` with
`conda activate cvpr`:
```bash
nohup bash scripts/run_tzamos_table.sh > ~/table3.log 2>&1 &                    # Tzamos et al. Table 2
nohup bash scripts/run_tzamos_table.sh --learning -a > ~/table3_L.log 2>&1 &   # their learned variants
python scripts/compare_tzamos_table.py                                         # ours vs paper, with runtimes
```

## Layout
```
src/eval_relpose.py             5-point RANSAC (PoseLib / OpenCV) + mAA / AUC evaluation
src/colmap_io.py                COLMAP model reader (bin + txt), numpy only
src/sample_tuples.py            GT pairs / triplets from any COLMAP model with co-visibility filters
src/eval_threeview.py           three-view baselines on Tzamos et al. triplets (their protocol)
src/sample_hruby4p3v.py         Python port of Hruby et al.'s 4p3v problem-solution sampler
src/triage_prototype.py         learned pre-solve sample triage prototype (negative result, see the report)
src/fourp3vf.py                 4p3vf equations, instance generators (synthetic, ETH3D, Cambridge, SP+LG triplets), mean-point seeds
src/check_fourp3vf.py           structure checks of the 4p3vf equations (residuals, signs, Props. 1-2, monodromy count)
src/homotopy_proto.py           single-path homotopy prototype vs LM / Newton from identical seeds; kill test B (--mode triplets, --merge)
src/sift_triplets.py            RootSIFT + ratio-test tracks for an existing triplet list (low-inlier setting)
tests/test_core.py              unit tests (stdlib unittest): python -m unittest discover -s tests -v

scripts/setup_workstation.sh    one-shot workstation setup (checks, apt, conda env, SSD links, build)
scripts/build_seed_code.sh      build learning_minimal (Hruby), PoseLib@threeview (Tzamos), superansac
scripts/patches/                fixes applied to the pinned seed code (rationale at the top of each patch)
scripts/run_tzamos_table.sh     Tzamos et al.'s own eval.py on every triplet scene (5 px, their table set)
scripts/compare_tzamos_table.py pool results like their tables.py and compare with the paper's Table 2
scripts/run_abl_dell.sh         every abl-dell run in one background command (status: ... status)
scripts/machine_sheet.sh        Task 1.3 machine sheet of the timing server (read-only)
scripts/prepare_triplets.py     their prepare_im.py one scene at a time (Cambridge, ETH3D), CPU ok, resumable
scripts/cambridge_nvm_to_colmap.py  Cambridge reconstruction.nvm -> COLMAP model_train for prepare_im.py
scripts/filter_same_camera.py   keep triplets whose three images share one intrinsics block (ETH3D)
scripts/compare_tzamos_focal.py pool shared-focal eval_f.py results per dataset (AUC, runtime, focal error)
scripts/runtime_single_core.sh  main estimators on one pinned core, CPU model recorded (timing window only)
scripts/kill_test_a.py          kill test A, first check: 6p3v vs the best re-fitted mean-point variant (one run)
scripts/kill_test_stats.py      both kill tests with paired intervals, scene-aware and selection-aware bootstraps
scripts/check_triplets.py       triplet files on the SSD complete and readable (run by setup)
scripts/eval_f_safe.py          run eval_f.py unchanged with a pool that survives poselib crashes
scripts/poselib_crash_repro.py  replay one saved crashing task (gdb backtrace)
scripts/patches/poselib_*.py    source edits on the fork at build time: OOB fixes, kill test A refit, Task 2.9 sequential
scripts/patches/threeview_*.py  eval_f.py: '+ ENM' (two-view refit), '+ SEQ' (sequential baseline), EVALF_SEED
scripts/outlier_stats.py        Task 2.8: track labels a / b / w, outlier types, histograms, guard, low-inlier set
scripts/success_rates.py        Task 2.8: s_6, s_M, s_E and hypothesis counts on the tuning scene
scripts/crossovers.py           Task 2.8: predicted crossover inlier ratios from the cost model, dated
scripts/semisynth_outliers.py   semi-synthetic outliers (whole-track / view-3 / single-view / mixture) on Cambridge
scripts/paper_supplement.py     supplement tables of draft v5 (per scene, ablations, Test B, full solve, Table 2)
scripts/fundamental_focals.py   focal length per triplet from the fundamental matrix (upstream PoseLib, .venv-nets)
scripts/eval_sets.py            draft v5 evaluation sets: guarded SIFT (primary w < 0.4), SP+LG, timing subsets
scripts/mr_config.py            draft v5 methods, iteration grids and sets (shared by the runner and the analysis)
scripts/matched_runtime.py      matched-runtime AUC@10, primary test, inlier-ratio bins, crossovers, Fig. 2
scripts/paper_tables.py         Tables 1 and 3 of draft v5 as LaTeX rows from the result files
scripts/geocalib_focals.py      GeoCalib focal lengths (focal-prior row; runs in .venv-nets)
scripts/vggt_cameras.py         VGGT cameras (network row; runs in .venv-nets)
scripts/check_extra_rows.py     smoke test of the draft v5 fork estimators and OOB fix 3 (run by setup)
scripts/patches/poselib_extra_rows.py  fork: calibrated sequential pipeline, three-view LO from given cameras
scripts/patches/threeview_extra.py     eval_f.py / eval.py: iteration grid, focal-prior / network rows, '+ SEQ'
scripts/make_hruby_data.sh      Hruby Sec. 5.1 data split from ETH3D (anchors / val / train)
scripts/run_baseline.sh         2-view baseline sweep on the RANSAC tutorial val split
scripts/download_tier1.sh       dataset downloads (online machine)
scripts/extract_tier1.sh        unpack archives into data/
scripts/download_tier2.sh       remaining datasets: Cambridge, full PhotoTourism, tutorial PnP/H/EF-train
scripts/download_imc2020_test_gt.sh  stream IMC 2020 archives, keep only COLMAP GT
scripts/build_test_gt.py        turn that GT into K1_K2/R/T.h5 for the tutorial test pack
scripts/check_gt.py             sanity check: fraction of confident matches consistent with the GT
scripts/move_to_ssd.ps1         move data/, wheelhouse/, papers/ to an external drive, leave junctions (Windows)

Offline cluster only (see docs/CLUSTER_SETUP.md):
scripts/build_wheelhouse.sh     baseline Linux wheels (Python 3.10-3.14) + uv binary (online machine)
scripts/build_offline_bundle.sh GPU wheels, build tools, pinned sources, weights, Tzamos triplets, papers
scripts/build_apt_bundle.py     offline apt bundle for the cluster nodes
scripts/setup_node.sh           offline venv setup on one cluster node
scripts/setup_node_gpu.sh       offline PyTorch (CUDA 12.6) + LightGlue + weights on one node
scripts/run_cluster.sh          split one evaluation across nodes by scene over SSH, gather + merge
scripts/merge_results.py        recompute summary.json from per-scene CSVs

requirements.lock               baseline package versions
requirements-extra.lock         analysis packages (scikit-learn)
requirements-gpu.lock           GPU stack versions
data/README.md                  what each dataset contains + gotchas
results/triage*/report*.json    per-scene results of the triage prototype
```
`data/`, `wheelhouse/`, `third_party/`, `papers/` and the rest of `results/` are not in git.

**Storage:** datasets (~380 GB), the pinned source/wheel bundle (`wheelhouse/`) and the papers live on an
external SSD (`learning-algo-cvpr/`, exFAT). `setup_workstation.sh` links them into the repo (and copies
whatever fits to the internal disk unless `LOCAL_COPY=0`), so all paths in the scripts stay the same.
Seed code commits are pinned in `scripts/build_offline_bundle.sh`.

## Compute
- **abl-dell** (current): Ubuntu 24.04, 96 threads, 754 GB RAM, no NVIDIA GPU (CPU PyTorch).
- Earlier runs: a 2x RTX A6000 workstation (2026-10-19) and a Windows laptop (2-view baselines). An offline
  4-node cluster (i9-12900, T1000) was set up first and is retired for this project.

## Sampling GT pairs / triplets
`src/sample_tuples.py` reads any COLMAP model and samples pairs or triplets whose images share
enough 3D points. Check against the literature: ETH3D training, pairs sharing >= 500 points gives
**1,969 pairs, exactly SupeRANSAC's count**.
```bash
python src/sample_tuples.py data/eth3d/courtyard/dslr_calibration_undistorted --size 2 --min-shared 500 --out results/tuples/courtyard.json
python src/sample_tuples.py data/aachen_v1_1/3D-models/aachen_v_1_1 --size 3 --num 5000 --out results/tuples/aachen.json   # ~30 s
```

## Evaluation protocol (2-view)
- Data: CVPR 2020 RANSAC tutorial epipolar split (PhotoTourism, RootSIFT + mutual NN matches).
  Validation = `sacre_coeur`, `st_peters_square`, 4,950 pairs each. Test = 11 scenes, 9 with public GT.
- Ground truth: `dR = R2 R1^T`, `dT = T2 - dR T1` (checked to reproduce the shipped `Egt.h5` exactly).
- Error per pair = max(rotation geodesic error, translation direction error) in degrees.
- **mAA@10**: mean over 1..10 deg thresholds of the fraction of pairs below each threshold (tutorial / IMC 2020 metric).
  **AUC@5/10/20**: SuperGlue-style area under the recall curve.
- Per-pair CSVs and `summary.json` go to `results/<split>/<method>_th<px>_r<ratio>/`.

## Baseline results (validation, 2026-10-14)
RANSAC tutorial val split, 9,900 pairs (sacre_coeur + st_peters_square), threshold in pixels,
`ratio` = SNN ratio filter on matches. Run on a 16-thread Windows laptop; timings are per pair, single thread.

| Method | Ratio | Thr (px) | mAA@10 | AUC@5 | AUC@10 | AUC@20 | ms/pair |
|---|---|---|---|---|---|---|---|
| PoseLib 5pt LO-RANSAC | all | 1.0 | 0.493 | 0.368 | 0.467 | 0.576 | ~278 |
| **PoseLib 5pt LO-RANSAC** | **0.8** | **1.0** | **0.767** | **0.630** | **0.733** | **0.816** | ~20 |
| PoseLib 5pt LO-RANSAC | 0.8 | 0.5 | 0.754 | 0.613 | 0.719 | 0.805 | ~28 |
| PoseLib 5pt LO-RANSAC | 0.8 | 2.0 | 0.748 | 0.608 | 0.714 | 0.805 | ~15 |
| OpenCV USAC_MAGSAC (best thr) | 0.8 | 0.1 | 0.753 | 0.608 | 0.717 | 0.804 | ~546 |
| OpenCV USAC_MAGSAC | 0.8 | 1.0 | 0.597 | 0.416 | 0.560 | 0.700 | ~39 |
| OpenCV RANSAC | 0.8 | 1.0 | 0.643 | 0.449 | 0.603 | 0.737 | ~274 |

### Test (9 of 11 scenes with public GT, 42,301 pairs)
PoseLib 5pt LO-RANSAC, ratio 0.8, 1 px: **mAA@10 0.709**, AUC@5/10/20 0.540 / 0.670 / 0.767.
Per scene: reichstag 0.845, milan 0.824, florence 0.792, lincoln 0.760, sagrada 0.746, st_pauls 0.692,
british_museum 0.675, mount_rushmore 0.612, piazza_san_marco 0.499.

MAGSAC++ sweep (mAA@10): 0.05 → 0.729, 0.1 → 0.753, 0.25 → 0.741, 0.5 → 0.689, 1 → 0.597, 2 → 0.484, 5 → 0.332.
Its accuracy peaks near 0.1 px but it then hits the 10k-iteration cap (~27x slower than PoseLib).

## Three-view (Tzamos et al. CVPR 2025 triplets)
Their protocol: tracks with both LightGlue scores >= 0.5, 5 px epipolar threshold, 100-1000 iterations,
pose error = max(mean R error, mean t error) over pairs 1-2 and 1-3; "AUC@k" = mean recall at 1..k deg (%).
PhotoTourism = 12 scenes (St. Peter's Square held out, as in the paper), 5,000 triplets each.

| Method | PT AUC@5/10/20 | Aachen AUC@5/10/20 |
|---|---|---|
| Paper: 5pt+P3P | 62.93 / 74.30 / 83.00 | 43.43 / 56.73 / 68.28 |
| Paper: 4p3v(M±δ)+R+F+ENM (best) | 66.12 / 77.14 / 85.15 | 44.02 / 57.42 / 68.97 |
| **Their code (our run): 5pt+P3P** | 56.45 / 69.90 / 80.43 | 44.65 / 61.49 / 74.22 |
| **Their code (our run): 4p3v(M±δ)+R+F+ENM** | 65.99 / 77.08 / 85.16 | 48.60 / 64.97 / 76.77 |
| Ours: `seq_5pt_p3p` (Python, upstream PoseLib) | 59.22 / 70.81 / 79.59 | 39.50 / 55.62 / 68.66 |
| Ours: `pairwise_5pt` | 57.04 / 69.59 / 79.12 | 40.19 / 57.40 / 70.92 |

All 18 rows of their Table 2, the learned (L) variants and runtimes are in [`docs/REPORT.md`](docs/REPORT.md)
(sections 3-4). Our own Python baselines:
```bash
python src/eval_threeview.py --method seq_5pt_p3p --threshold 5 --reproj-threshold 5 --scenes <12 scenes>
python src/eval_threeview.py --data data/tzamos_triplets/threeview/aachen --threshold 5 --reproj-threshold 5
```

## Hruby et al. 4p3v training data
`src/sample_hruby4p3v.py` reproduces `data_sampler.cxx` (same sampling caps, normalization and output
format, so their connectivity / anchors / labels binaries read it unchanged). Checked: reconstructed
inter-point distances agree across the 3 views to 1e-13, view-3 centroid on the optical axis and 4th
point on y = 0 to 1e-15. `bash scripts/make_hruby_data.sh` builds their split (anchors office+terrains
40k, val delivery_area+facade 30k, train the other 9 public scenes; the paper used 23 sequences).
