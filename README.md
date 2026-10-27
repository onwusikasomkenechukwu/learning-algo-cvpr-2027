# learning-algo: minimal solvers + RANSAC for multi-view relative pose

Evaluation stack, reproductions of the seed papers and research prototypes for minimal solvers inside
RANSAC: calibrated two- and three-view relative pose, and three-view relative pose with an unknown shared
focal length (4p3vf).

## Status (2026-10-27)
The CVPR 2027 plan was single-path homotopy continuation from approximate (mean-point) seeds for 4p3vf.
**Both pre-registered kill tests failed, so that paper is off.** The work continues as a controlled study of
when solver exactness matters: outlier measurements and crossover predictions (Task 2.8) and the sequential
six-point → P3P baseline (Task 2.9), both now run on the complete datasets.

The final numbers come from one complete rerun on abl-dell (2026-10-26) after the seed-code fixes below:
5 Cambridge scenes × 5,000 SuperPoint+LightGlue triplets, all 12 ETH3D scenes (3,239 same-camera triplets),
SIFT tracks for both, and no PoseLib crashes. Statistics: [`scripts/kill_test_stats.py`](scripts/kill_test_stats.py).

| Kill test | Rule | Result |
|---|---|---|
| **B**: does continuation reach the correct root more often than converged LM from identical seeds? | ≥ +5 points, McNemar clear | **FAIL**: 15.6% vs 21.6%, **−6.0 points**, 95% CI [−6.9, −5.1] (two-level bootstrap over scenes [−7.2, −4.7]), McNemar p = 2.4e-40; 23,184 samples, 5,779 with an unambiguous correct root; LM ahead in all 5 scenes |
| **A**: does the best re-fitted mean-point variant still trail 6pt+P3P? | ≥ 2.0 AUC@10 | **FAIL**: **1.61 AUC@10**, 95% CI [1.44, 1.78] with the five scenes fixed, [0.99, 2.18] with scenes resampled; best variant re-selected in every bootstrap replicate; mean of 3 RANSAC runs (1.41 / 1.69 / 1.74) |

Kill test B, per scene (continuation − LM, points, 95% CI): Great Court −4.1 [−6.1, −2.2], King's College
−7.5 [−9.4, −5.6], Old Hospital −5.9 [−8.1, −3.8], Shop Facade −6.0 [−8.1, −4.0], St Mary's −5.7 [−7.7, −3.8];
heterogeneity across scenes not significant (Q = 6.0, df 4, p = 0.2). The +5-point target and 0 are outside
every interval. Continuation does beat Newton homotopy (+7.6 points) and plain Newton (+10.5) from the same
seeds, so the tracker works; converged LM is simply better at reaching the correct root.

Kill test A, per scene (AUC@10, mean of 3 RANSAC runs; rows without the re-fit are one run):

| Method | Great Court | King's College | Old Hospital | Shop Facade | St Mary's | Mean |
|---|---|---|---|---|---|---|
| 6pt+P3P (`6p3v`) | 37.88 | 64.33 | 47.83 | 64.90 | 58.23 | **54.63** |
| 4p3vf(M) | 28.44 | 57.32 | 42.02 | 57.40 | 49.49 | 46.93 |
| 4p3vf(M±δ)+R (best without re-fit) | 28.97 | 58.03 | 42.84 | 58.64 | 50.85 | 47.87 |
| **4p3vf(M±δ) + two-view re-fit** (best) | 35.45 | 63.78 | 46.24 | 63.43 | 56.20 | **53.02** |
| Gap | 2.43 | 0.55 | 1.59 | 1.47 | 2.03 | **1.61** |

Leaving out one scene at a time gives gaps of 1.41–1.88. The fail is clear on this benchmark; two scenes
clear 2.0 on their own, so a different set of scenes could. The single-run value before the out-of-bounds
fix (1.37 on four scenes) and after it (1.41 on five) agree: the seed-code bugs did not decide the outcome.

**What we learned**
- **The minimal 4p3vf problem is badly conditioned at real noise.** The exact root that continues the ground
  truth to the observed points meets a 2°/10%-focal criterion on only about 5% of real samples, and
  mean-point seeds start a median 40° off. Real continuation paths fold or end at a wrong exact root of the
  right orientation class, which no check can reject.
- **A cheap two-view re-fit, not exactness, closes most of the gap.** Re-fitting focal length and pose of
  views 1–2 on each seed's inliers adds 5.2–6.3 AUC@10 to every mean-point variant (gap to 6pt+P3P
  6.8 → 1.6).
- **The equations behave as derived.** Residuals of 3e-15 on 1,000 instances; the Jacobian loses rank by
  exactly two at coplanar points; the true root keeps its orientation class through 98/98 coplanar
  crossings; monodromy finds 2,672 = 4 × 668 solutions, stable over five instances (668 per class, as
  listed by Chien et al.).
- **The shared-focal baseline reproduces:** on King's College, Old Hospital, Shop Facade and St Mary's,
  6pt+P3P leads 4p3vf(M) by 7.09 AUC@10 in the rerun (6.89 in the first run), against 6.91 in Tzamos et al.'s
  extended paper.

**Earlier results** (details in [`docs/REPORT.md`](docs/REPORT.md), written 2026-10-20)
- **Tzamos et al. (CVPR 2025) reproduced with their own code:** their best method, 4p3v(M±δ)+R+F+ENM,
  gets AUC@5 65.99 vs 66.12 in the paper (PhotoTourism); variants with inner refinement match within
  0.1–1.8, variants without it and Aachen differ systematically. These '+R' rows were computed before the
  out-of-bounds fix below and have not been rerun yet.
- **Their unpublished learned 5th point:** +14 AUC@5 before refinement, nothing after it, 4–6× slower.
- **Our learned sample-triage prototype (negative result):** 1.8× fewer draws than random before
  refinement, but ties a one-line spread rule after it (2.88 vs 2.90 draws). Outliers are not the
  bottleneck; sample conditioning is.
- **2-view baseline:** PoseLib 5pt LO-RANSAC, mAA@10 0.767 (tutorial val) / 0.709 (test, rebuilt GT).

## The study: Tasks 2.8 and 2.9
**Task 2.9, sequential baseline** (`6p3v + SEQ` in `eval_f.py`): shared-focal six-point LO-RANSAC on views 1–2,
P3P LO-RANSAC on view 3 against the stage-1 inliers triangulated at the stage-1 focal length, then the joint
estimator's final three-view refinement; same threshold, iteration limits and stopping rule in both stages.
Added to the PoseLib fork in C++ ([`scripts/patches/poselib_sequential.py`](scripts/patches/poselib_sequential.py))
with a Python binding, timed by `eval_f.py` like every other method. Exact on noise-free synthetic scenes and
equal to the joint estimator with 0.5 px noise and 30% view-3 outliers. Results (SuperPoint+LightGlue):

| Method | Cambridge AUC@10 | median error | f within 10% | ms | ETH3D AUC@10 | ms |
|---|---|---|---|---|---|---|
| 6pt+P3P (joint) | **54.54** | 3.80° | 60.3% | 16.9 | **70.95** | 212 |
| 4p3vf(M) | 46.93 | 4.75° | 52.4% | 17.8 | 55.79 | 180 |
| Sequential 6pt → P3P | 44.09 | 5.39° | 47.0% | 10.0 | 45.82 | 20 |

The sequential pipeline is the fastest per call and the least accurate. It fails where the two-view shared
focal length is far off (e.g. 944 px against 1667 px): the triangulated points are then distorted and P3P
finds no consensus on view 3. Scoring hypotheses on all three views, as the joint estimator does, avoids this.

**Task 2.8, where outliers sit** ([`scripts/outlier_stats.py`](scripts/outlier_stats.py)): every track labelled
against the reference cameras as correct in views 1–2 (fraction a), inlier (fraction b of those, w = ab) and
outlier type (whole-track, view-3, single-view), at 2 and 4 px, on every Cambridge and ETH3D triplet.
- Guarded SIFT low-inlier set: 13,744 triplets with w < 0.4 (49% of 28,042); the target of 1,000 is met.
- Outlier mixture on the tuning scene (ETH3D courtyard, SIFT): whole-track 43%, view-3 29%, view-1 18%,
  view-2 5%, other 5%.

**Task 2.8, success rates and crossovers** ([`scripts/success_rates.py`](scripts/success_rates.py),
[`scripts/crossovers.py`](scripts/crossovers.py)): success rates from clean samples of courtyard (186 samples;
it has 197 same-camera triplets), then the draft's cost model (Eqs. 3–4) for predicted crossover inlier ratios,
written dated (2026-10-26) before any low-inlier run.
- Success rates: s_6 = 0.54 (6pt+P3P), s_M = 0.42 (mean-point seeds). Continuation endpoints rescue
  s_E = 1.8% of the samples whose seeds all fail. Local optimization from the reference cameras succeeds on
  81% (the ceiling).
- With the prototype's tracking time (91 ms per sample, Python) ours is 615–630× slower than 4p3vf(M) at
  every inlier ratio, and 77–845× slower than 6pt+P3P except for whole-track outliers below w = 0.035.
- Even with free tracking, ours is no faster than 4p3vf(M) (time ratio 0.98). It beats 6pt+P3P below
  w = 0.87 (whole-track outliers), 0.81 (single-view) and 0.82 (measured mixture), but not for view-3 outliers,
  and is slower than the sequential pipeline except for whole-track outliers below w = 0.24. Any time
  advantage comes from sampling 4 points instead of 6, not from continuation.

The control row 5pt+P3P+R+F (calibrated, `eval.py`) was run on the released triplets for the same comparison.

## Known issues in the seed code (fixed here)
- **Out-of-bounds read in PoseLib@threeview's `inner_refine`** (both three-view estimators): it copies
  `sample[k]` for k < 4 + `inner_refine_extra` (default 1), but a 4p3v sample holds 4 entries, so every '+R'
  method reads `sample[4]` past the end and refines on an arbitrary fifth track, or faults when the junk
  index is large. On abl-dell this produced general protection faults in poselib (kernel log) and
  evaluations that never finished. [`scripts/patches/poselib_oob_fixes.py`](scripts/patches/poselib_oob_fixes.py)
  refines on the sampled tracks only and also fixes a `reserve(3)` that left P3P reading an empty vector.
  **Every '+R' result computed before the fix used the undefined fifth point.**
- `eval_f.py` forks a `Pool` it never closes; a crashed worker makes it wait forever.
  [`scripts/eval_f_safe.py`](scripts/eval_f_safe.py) runs it unchanged with a pool that survives worker
  crashes, retries the task once and saves it for [`scripts/poselib_crash_repro.py`](scripts/poselib_crash_repro.py)
  (gdb backtrace).
- `eval_f.py` never sets the RANSAC seed (PoseLib's default is 0), so repeating a run repeats its RANSAC
  draws. [`scripts/patches/threeview_seed.py`](scripts/patches/threeview_seed.py) reads it from `EVALF_SEED`;
  kill test A uses seeds 0–2.
- `eval_f.py` scores the focal length against view 1 only (`gt_focal_2/3` read `img1`); the released
  `ThreeViewSharedFocalRelativePoseEstimator::delta` dehomogenizes the shifted point by its y coordinate.
  Both left as released and noted.

## Running on abl-dell (no GPU)
Setup once ([`docs/WORKSTATION_SETUP.md`](docs/WORKSTATION_SETUP.md)), then in `~/learning-algo` with
`conda activate cvpr` and the data SSD plugged in:
```bash
bash scripts/run_abl_dell.sh            # everything below, in the background
bash scripts/run_abl_dell.sh fresh      # the same, after moving every earlier result aside (full retest)
bash scripts/run_abl_dell.sh status     # one-screen progress summary
bash scripts/run_abl_dell.sh stop       # stop the runner and every job it started
```
Steps, in default order (each skips work already done; name steps to run only those): `setup` (git pull,
patches, fork rebuild when the installed fork was not built from the current patches, import checks),
`machine` (Task 1.3 machine sheet), `monodromy`, `triplets` (Cambridge SP+LG, resumable), `eth3d` (every
qualifying triplet within one camera block, at most `ETH_N=2000` per scene), `sift`, `evalf` (Tzamos et al.'s `eval_f.py` via the
crash-safe wrapper), `killB`, `killA` (three RANSAC seeds, then `stats`), `seq` (Task 2.9), `control`
(5pt+P3P+R+F), `task28` (Task 2.8),
`compare`, `crashdebug`, `collect` (copy to the SSD, flushed; eject before unplugging). All datasets are
built before any evaluation. `fresh` archives earlier results to `results/archive/<time>/` (and
`third_party/threeview/results/archive_<time>/`, the SSD copy to `abl_dell_results_<time>/`); triplets and
SIFT tracks are kept.

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
scripts/run_abl_dell.sh         week-2 compute on abl-dell in one background command (status: ... status)
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
