# learning-algo: do hard minimal problems need exact solvers?

Code, data pipeline and results for a CVPR 2027 submission with Dr. Saurav K. Aryal (Howard University) on
three-view relative pose from four points inside RANSAC: calibrated cameras (4p3v) and one camera with an
unknown shared focal length (4p3vf).

## Status (2026-10-28)
**Direction (draft v5, 2026-10-27).** Four tracks in three views are enough for the poses, and with one camera
also for the focal length, but these minimal problems have hundreds to thousands of complex solutions. Exact
solvers therefore track many homotopy paths, and practice samples five or six points or uses approximate
four-point solvers. The paper asks whether exactness pays inside RANSAC. Our two pre-registered tests of an exact
single-path solver both came out against it, and the paper reports them as results. It then studies what does
decide between four points and six: the sample size and which views the outliers corrupt. It compares four points
with a two-view refit against the joint and the sequential six-point pipelines at matched runtime, on real
low-inlier SIFT triplets and semi-synthetic outliers of three types, for the shared-focal and the calibrated
problem.

**Where it stands.** Everything the draft needs is built ([experiments below](#what-the-comprehensive-run-produces))
and waits for one comprehensive run on abl-dell. A third bug found in the seed code
([below](#known-issues-in-the-seed-code-fixed-here)) changes every number that comes from the PoseLib fork, so
the run starts from scratch (`fresh`) and the fork-based numbers on this page are superseded when it finishes.
Kill test B uses our Python prototype and is not affected.

## The two tests of exactness (results)
Fixed before the runs: exactness has room only if a cheap two-view refit of the approximate seeds still trails
6pt+P3P by at least 2.0 AUC@10 (test A), and it helps only if continuation from the same seeds reaches the correct
root at least 5 points more often than converged Levenberg-Marquardt (test B). Data: 5 Cambridge scenes × 5,000
SuperPoint+LightGlue triplets (complete rerun of 2026-10-26, no PoseLib crashes). Statistics:
[`scripts/kill_test_stats.py`](scripts/kill_test_stats.py).

| Test | Rule | Result |
|---|---|---|
| **A**: how much does a two-view refit close? | gap ≥ 2.0 AUC@10 | **Against exactness**: the best refitted variant, 4p3vf(M±δ), trails 6pt+P3P by **1.61**, 95% CI [1.44, 1.78] with the scenes fixed, [0.99, 2.18] with scenes resampled (best variant re-selected per replicate); mean of 3 RANSAC runs. The plain mean point with the refit trails by 1.97. *Fork-based: rerun pending.* |
| **B**: does the exact path find the right root? | ≥ +5 points, McNemar clear | **Against exactness**: 15.6% vs 21.6% for converged LM, **−6.0 points**, 95% CI [−6.9, −5.1], McNemar p = 2.4e-40; 23,184 samples, 5,779 with an unambiguous real correct root; LM ahead in all 5 scenes |

- **Test A per scene** (gap to 6pt+P3P): Great Court 2.43, King's College 0.54, Old Hospital 1.59, Shop Facade
  1.47, St Mary's 2.03. The refit adds 5.2 to 6.3 AUC@10 to every mean-point variant (the plain mean point trails by 7.70 without it).
- **Test B against the other equation solvers** (strict success, continuation minus each, 2026-10-27 run):
  Newton homotopy +7.6, Newton's method +10.5 and the released two-step refinement +15.6, but the L-shaped retry
  −1.1, the start off the solution surface −0.8 and converged LM −6.0. The tracker works; refining the seed
  against the images does better.
- **The correct-root tool checks out against a full solve:** its root is one of the full solve's endpoints in
  63 of 63 synthetic and 44 of 46 King's College samples (2,672 start solutions; about 400 real endpoints and 3
  to 4 accepted ones per sample).
- **Why exactness does not help here:** at real noise the four-point problem is badly conditioned. The exact
  continuation of the ground truth meets a 2°/10%-focal criterion on only about 5% of real samples, and paths
  fold or end at a wrong exact root of the right orientation class.

## When do four points beat six?
Let a be the fraction of tracks correct in views 1 and 2 and b the fraction of those also correct in view 3
(inlier ratio w = ab). A joint pipeline that solves views 1–2 from m points and view 3 by P3P draws a clean
sample with probability about a^m b^3. An approximate four-point solver needs a^4 b^3 (an exact one a^4 b^4); a
sequential pipeline needs about 1/a^m + 1/b^3 samples. Hence:
- **whole-track outliers** (b = 1): four points need 1/w² times fewer samples than six and 1/w fewer than five;
- **view-3 outliers** (a = 1): no advantage;
- **single-view outliers**: the sequential pipeline can win (for m = 6 whenever b < about 0.73).

With per-sample success rates s and costs c measured on the tuning scene (ETH3D courtyard), the model predicts
crossover inlier ratios, written dated before any low-inlier run
([`scripts/success_rates.py`](scripts/success_rates.py), [`scripts/crossovers.py`](scripts/crossovers.py)).
On 2026-10-27 it predicted that four points with the refit beat 6pt+P3P below w = 0.575 for whole-track,
0.363 for single-view and 0.404 for the measured mixture of outliers, never for view-3 outliers, and beat the
sequential pipeline only for whole-track outliers below w = 0.174. *Fork-based: the comprehensive run rewrites
these predictions with the fixed fork before any low-inlier run.*

Measured on real triplets ([`scripts/outlier_stats.py`](scripts/outlier_stats.py), labels against the reference
cameras at 2 px on the 800 px scale):
- **Low-inlier set:** 13,744 guarded SIFT triplets with w < 0.4 (49% of 28,042; guard: at least 12 inlier tracks
  and an SP+LG inlier ratio above 0.5 under the same cameras).
- **Outlier mixture** on the tuning scene's SIFT triplets: whole-track 43%, view-3 29%, view-1 18%, view-2 5%,
  other 5%.

## What the comprehensive run produces
| Draft item | What runs | Code |
|---|---|---|
| Table 1, default settings | every shared-focal row on Cambridge and ETH3D SP+LG, RANSAC seeds 0–2: 6pt+P3P, the sequential pipeline, 5pt+P3P+R+F at a guessed and at a GeoCalib focal length, the 4p3vf(M) family with and without the refit, the oracle, VGGT then three-view LO | [`mr_config.py`](scripts/mr_config.py), [`geocalib_focals.py`](scripts/geocalib_focals.py), [`vggt_cameras.py`](scripts/vggt_cameras.py) |
| Matched runtime | accuracy at fixed iteration counts (10 to 30,000, no early termination) and single-core time on one pinned core; every method read at the mean time of 6pt+P3P at default settings, interpolated in log time | [`matched_runtime.py`](scripts/matched_runtime.py) |
| Primary test | 4p3vf(M) with the refit against both six-point pipelines on the 13,744 low-inlier triplets: intersection-union test, two-level bootstrap over scenes and triplets, α = 0.05 | [`matched_runtime.py`](scripts/matched_runtime.py) |
| Fig. 2 | AUC@10 against inlier ratio on real triplets (binned) and semi-synthetic whole-track, view-3, single-view and mixed outliers at w = 0.75–0.25, with measured and predicted crossovers; accuracy against runtime | [`semisynth_outliers.py`](scripts/semisynth_outliers.py), [`eval_sets.py`](scripts/eval_sets.py), [`matched_runtime.py`](scripts/matched_runtime.py) |
| Table 2 | tests A and B (above), recomputed where fork-based | [`kill_test_stats.py`](scripts/kill_test_stats.py) |
| Table 3 | calibrated: PhotoTourism at default settings, and matched runtime on the low-inlier set and semi-synthetic whole-track outliers; 5pt+P3P, the calibrated sequential pipeline, the refitted four-point variants, the learned HC solver | [`paper_tables.py`](scripts/paper_tables.py) |

Not built yet: the depth-prior row (needs a monocular-depth solver and network) and the supplement's extras
(PROSAC, focal sampling, the all-pairs sequential variant, Hfff+P3P).

Sequential pipeline, first results (2026-10-26, SP+LG; fork-based):

| Method | Cambridge AUC@10 | median error | f within 10% | ETH3D AUC@10 |
|---|---|---|---|---|
| 6pt+P3P (joint) | **54.54** | 3.80° | 60.3% | **70.95** |
| 4p3vf(M) | 46.93 | 4.75° | 52.4% | 55.79 |
| Sequential 6pt → P3P | 44.09 | 5.39° | 47.0% | 45.82 |

On clean matches the sequential pipeline is the least accurate: where the two-view focal length is far off, the
triangulated points are distorted and P3P finds no consensus on view 3.

## Known issues in the seed code (fixed here)
- **Uninitialized and out-of-bounds Jacobian entry in PoseLib@threeview** (found 2026-10-28): both three-view
  Jacobians zero the part of J12 that does not depend on view 3 starting at column 6, but view 3's parameters
  start at column 5. Column 5 was never set, so every LM step of the three-view refinement (LO and the final
  refinement of every three-view estimator, calibrated and shared-focal) used stack garbage; the calibrated one
  also wrote one value past the end. **Every result from the fork before this fix is superseded.**
- **Out-of-bounds read in `inner_refine`** (both three-view estimators): it copies `sample[k]` for
  k < 4 + `inner_refine_extra`, but a 4p3v sample holds 4 entries, so every '+R' method refined on an arbitrary
  fifth track or faulted (general protection faults on abl-dell). A `reserve(3)` also left P3P reading an empty
  vector. Fixes 1–3: [`scripts/patches/poselib_oob_fixes.py`](scripts/patches/poselib_oob_fixes.py).
- `eval_f.py` forks a `Pool` it never closes; a crashed worker makes it wait forever.
  [`scripts/eval_f_safe.py`](scripts/eval_f_safe.py) runs it unchanged with a pool that survives worker
  crashes, retries the task once and saves it for [`scripts/poselib_crash_repro.py`](scripts/poselib_crash_repro.py).
- `eval_f.py` never sets the RANSAC seed (PoseLib's default is 0), so repeating a run repeats its draws.
  [`scripts/patches/threeview_seed.py`](scripts/patches/threeview_seed.py) reads it from `EVALF_SEED`.
- `eval_f.py` scores the focal length against view 1 only (`gt_focal_2/3` read `img1`); the released
  `ThreeViewSharedFocalRelativePoseEstimator::delta` dehomogenizes the shifted point by its y coordinate.
  Both left as released and noted.

## Running on abl-dell (no GPU)
Setup once ([`docs/WORKSTATION_SETUP.md`](docs/WORKSTATION_SETUP.md)), then in `~/learning-algo` with
`conda activate cvpr` and the data SSD plugged in:
```bash
ALLOW_DOWNLOADS=1 bash scripts/run_abl_dell.sh fresh   # the comprehensive run, from scratch, in the background
bash scripts/run_abl_dell.sh status                     # one-screen progress summary
bash scripts/run_abl_dell.sh stop                       # stop the runner and every job it started
```
Steps in default order (each skips work already done; name steps to run only those): `setup` (git pull,
patches, fork rebuild when needed, import checks and a smoke test of the new estimators), `machine`,
`monodromy`, `triplets`, `eth3d`, `sift`, `evalf`, `killA`, `seq`, `control`, `followup` (kill test B with every
method, the full-solve check, Task 2.8 with the refit and its dated predictions, statistics), `semisynth`,
`sets`, `geocalib`, `vggt`, `table1`, `curves`, `calib`, `timing` (one pinned core, after every background job),
`paper` (results/matched and results/paper), `compare`, `crashdebug`, `collect` (copy to the SSD, flushed;
eject before unplugging). Every low-inlier run comes after the predictions are written. `ALLOW_DOWNLOADS=1`
lets `geocalib` and `vggt` create `.venv-nets` (CPU PyTorch, GeoCalib, VGGT-1B weights, about 6 GB); without it
those two rows stay empty. `fresh` archives earlier results to `results/archive/<time>/` (and
`third_party/threeview/results/archive_<time>/`, the SSD copy to `abl_dell_results_<time>/`); triplets, SIFT
tracks and network outputs are kept.

## Earlier work
Details in [`docs/REPORT.md`](docs/REPORT.md) (written 2026-10-20, before the change of direction).
- **Tzamos et al. (CVPR 2025) reproduced with their own code:** their best method, 4p3v(M±δ)+R+F+ENM, gets
  AUC@5 65.99 vs 66.12 in the paper (PhotoTourism). The shared-focal gap also reproduces: 6pt+P3P leads
  4p3vf(M) by 7.70 AUC@10 on our five Cambridge scenes against 6.91 published, while absolute values sit 2 to
  3 points below the published ones. *Fork-based: rerun pending.*
- **The 4p3vf equations behave as derived:** residuals of 3e-15, rank loss of exactly two at coplanar points,
  the orientation class kept through 98/98 coplanar crossings, and 2,672 = 4 × 668 solutions by monodromy.
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
