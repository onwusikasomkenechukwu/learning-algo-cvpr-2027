# learning-algo: minimal solvers + RANSAC for multi-view relative pose

Evaluation stack, reproductions of the seed papers and research prototypes for minimal solvers inside
RANSAC: calibrated two- and three-view relative pose, and three-view relative pose with an unknown shared
focal length (4p3vf).

## Status (2026-10-23)
The CVPR 2027 plan was single-path homotopy continuation from approximate (mean-point) seeds for 4p3vf.
**Both pre-registered kill tests failed, so that paper is off.** The work continues as a controlled study of
when solver exactness matters, starting with the outlier measurements and crossover predictions (Task 2.8)
and the sequential six-point → P3P baseline (Task 2.9).

| Kill test | Rule | Result |
|---|---|---|
| **B**: does continuation reach the correct root more often than converged LM from identical seeds? | ≥ +5 points, McNemar clear | **FAIL**: 15.4% vs 21.3% (−5.9 points), McNemar p = 5e-23, 12,859 all-inlier Cambridge samples (SP+LG); LM ahead in every scene |
| **A**: does the best re-fitted mean-point variant still trail 6pt+P3P? | ≥ 2.0 AUC@10 | **FAIL**: 1.37 AUC@10 (95% two-level bootstrap [0.85, 1.83]), 4 of 5 Cambridge scenes, one run |

Kill test A, per scene (AUC@10, Cambridge, SuperPoint+LightGlue, 5,000 triplets each):

| Method | King's College | Old Hospital | Shop Facade | St Mary's | Mean |
|---|---|---|---|---|---|
| 6pt+P3P (`6p3v`) | 64.50 | 47.69 | 64.86 | 58.24 | **58.83** |
| 4p3vf(M) | 57.90 | 42.32 | 57.60 | 49.96 | 51.94 |
| 4p3vf(M±δ)+R (best without re-fit) | 59.19 | 43.33 | 59.25 | 51.29 | 53.26 |
| **4p3vf(M±δ) + two-view re-fit** (best) | 63.85 | 46.24 | 63.19 | 56.53 | **57.45** |

Great Court is missing because the PoseLib fork crashed on some of its triplets (see *Known issues*); it
would need a gap of 4.5 or more on its own to change the decision.

**What we learned**
- **The minimal 4p3vf problem is badly conditioned at real noise.** The exact root that continues the ground
  truth to the observed points meets a 2°/10%-focal criterion on only about 5% of real samples, and
  mean-point seeds start a median 40° off. Real continuation paths fold or end at a wrong exact root of the
  right orientation class, which no check can reject.
- **A cheap two-view re-fit, not exactness, closes most of the gap.** Re-fitting focal length and pose of
  views 1–2 on each seed's inliers adds 4–5 AUC@10 to every mean-point variant (gap to 6pt+P3P 5.6 → 1.4).
- **The equations behave as derived.** Residuals of 3e-15 on 1,000 instances; the Jacobian loses rank by
  exactly two at coplanar points; the true root keeps its orientation class through 98/98 coplanar
  crossings; monodromy finds 2,672 = 4 × 668 solutions, stable over three instances (668 per class, as
  listed by Chien et al.).
- **The shared-focal baseline reproduces:** on the same four scenes 6pt+P3P leads the mean-point solver by
  6.89 AUC@10, against 6.91 in Tzamos et al.'s extended paper.

**Earlier results** (details in [`docs/REPORT.md`](docs/REPORT.md), written 2026-10-20)
- **Tzamos et al. (CVPR 2025) reproduced with their own code:** their best method, 4p3v(M±δ)+R+F+ENM,
  gets AUC@5 65.99 vs 66.12 in the paper (PhotoTourism); variants with inner refinement match within
  0.1–1.8, variants without it and Aachen differ systematically. These '+R' rows were computed before the
  out-of-bounds fix below and are being rerun.
- **Their unpublished learned 5th point:** +14 AUC@5 before refinement, nothing after it, 4–6× slower.
- **Our learned sample-triage prototype (negative result):** 1.8× fewer draws than random before
  refinement, but ties a one-line spread rule after it (2.88 vs 2.90 draws). Outliers are not the
  bottleneck; sample conditioning is.
- **2-view baseline:** PoseLib 5pt LO-RANSAC, mAA@10 0.767 (tutorial val) / 0.709 (test, rebuilt GT).

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
- `eval_f.py` scores the focal length against view 1 only (`gt_focal_2/3` read `img1`); the released
  `ThreeViewSharedFocalRelativePoseEstimator::delta` dehomogenizes the shifted point by its y coordinate.
  Both left as released and noted.

## Running on abl-dell (no GPU)
Setup once ([`docs/WORKSTATION_SETUP.md`](docs/WORKSTATION_SETUP.md)), then in `~/learning-algo` with
`conda activate cvpr` and the data SSD plugged in:
```bash
bash scripts/run_abl_dell.sh            # everything below, in the background
bash scripts/run_abl_dell.sh status     # one-screen progress summary
```
Steps (each skips work already done; name steps to run only those): `setup` (patches, fork rebuild when a
source fix is missing, import checks), `machine` (Task 1.3 machine sheet), `monodromy`, `triplets`
(Cambridge SP+LG, resumable), `sift`, `evalf` (Tzamos et al.'s `eval_f.py` via the crash-safe wrapper),
`killB`, `killA`, `control` (5pt+P3P+R+F), `eth3d`, `compare`, `crashdebug`, `collect` (copy to the SSD,
flushed; eject before unplugging). `requeue` moves results computed before the out-of-bounds fix aside so
they are recomputed.

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
scripts/kill_test_a.py          kill test A: 6p3v vs the best re-fitted mean-point variant, two-level bootstrap
scripts/eval_f_safe.py          run eval_f.py unchanged with a pool that survives poselib crashes
scripts/poselib_crash_repro.py  replay one saved crashing task (gdb backtrace)
scripts/patches/poselib_*.py    source edits on the fork at build time: OOB fixes, kill test A two-view refit
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
