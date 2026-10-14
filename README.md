# learning-algo: learned minimal solvers + RANSAC (CVPR target)

Relative pose baselines and tooling, set up to run on an **offline 4-node cluster** (CPU now, T1000 GPUs for feature matching).

## Layout
```
src/eval_relpose.py             5-point RANSAC (PoseLib / OpenCV) + mAA / AUC evaluation
src/colmap_io.py                COLMAP model reader (bin + txt), numpy only
src/sample_tuples.py            GT pairs / triplets from any COLMAP model with co-visibility filters
src/eval_threeview.py           three-view baselines on Tzamos et al. triplets (their protocol)
src/sample_hruby4p3v.py         Python port of Hruby et al.'s 4p3v problem-solution sampler
scripts/make_hruby_data.sh      Hruby Sec. 5.1 data split from ETH3D (anchors / val / train)
tests/test_core.py              unit tests (stdlib unittest): python -m unittest discover -s tests -v
scripts/download_tier1.sh       dataset downloads (online machine)
scripts/extract_tier1.sh        unpack archives into data/
scripts/download_imc2020_test_gt.sh  stream IMC 2020 archives, keep only COLMAP GT (online machine)
scripts/build_test_gt.py        turn that GT into K1_K2/R/T.h5 for the tutorial test pack
scripts/check_gt.py             sanity check: fraction of confident matches consistent with the GT
scripts/build_wheelhouse.sh     baseline Linux wheels (Python 3.10-3.14) + uv binary (online machine)
scripts/build_offline_bundle.sh GPU wheels, build tools, pinned sources, weights, Tzamos triplets, papers (online machine)
scripts/setup_node.sh           offline venv setup on one cluster node
scripts/setup_node_gpu.sh       offline PyTorch (CUDA 12.6) + LightGlue + weights on one node   [untested on cluster]
scripts/build_seed_code.sh      build learning_minimal, PoseLib@threeview, superansac offline   [untested on cluster]
scripts/run_baseline.sh         baseline sweep on the RANSAC tutorial val split (one machine)
scripts/run_cluster.sh          split one evaluation across nodes by scene over SSH, gather + merge
scripts/merge_results.py        recompute summary.json from per-scene CSVs
requirements.lock               baseline package versions (wheelhouse/)
requirements-gpu.lock           GPU stack versions (wheelhouse/gpu/)
data/README.md                  what each dataset contains + gotchas
```
`data/`, `wheelhouse/`, `third_party/`, `papers/` and `results/` are not in git. Copy them separately.

## Offline bundle (`wheelhouse/`, built 2026-10-14)
| Folder | Contents | Size |
|---|---|---|
| `wheelhouse/*.whl`, `tools/uv` | numpy, h5py, poselib, opencv-headless, tqdm for Python 3.10-3.14; uv 0.13.1 (sha256 checked) | 254 MB |
| `wheelhouse/gpu/` | torch 2.14.1+cu126, torchvision 0.29.1, kornia 0.8.3, matplotlib + NVIDIA CUDA 12.6 libs (44 wheels, Python 3.14) | 3.6 GB |
| `wheelhouse/build/` | cmake 4.4.4, ninja, pybind11, scikit-build-core, setuptools, wheel | 31 MB |
| `wheelhouse/src/` | pinned tarballs: LightGlue, kocurvik/threeview, kocurvik/PoseLib@threeview (+ pybind11 submodule), learning_minimal, superansac, Eigen 3.4.0 | 24 MB |
| `wheelhouse/weights/` | superpoint_v1, aliked-n16, {superpoint,aliked,sift}_lightglue (torch hub cache names) | 144 MB |

Exact commits are in `scripts/build_offline_bundle.sh`. Seed papers (arXiv) are in `papers/`.

## Cluster
Four identical nodes: i9-12900 (8P + 8E cores, 24 threads), 30 GB RAM, ~935 GB SSD, NVIDIA T1000 8 GB,
Ubuntu 26.04.1 LTS x86_64, gigabit Ethernet, SSH between nodes, **no internet**.

### Still unknown (needed before GPU / C++ steps)
1. `python3 --version` (torchvision 0.29.1 refuses exactly 3.14.1)
2. `nvidia-smi` driver version (CUDA 12.6 build needs >= 560)
3. `g++ --version` (all C++ builds need a compiler; it cannot be installed offline without the admin)
4. Whether the admin can install `libboost-dev libopencv-dev` (superansac only)

### One-time setup
Copy the repo including `wheelhouse/` and the data you need to the first node, then from there to the others:
```bash
rsync -av --exclude data/raw --exclude .venv ./ node1:learning-algo/
```
On **each** node (no sudo or apt needed; the bundled `uv` makes the venv, so `python3-venv` is not required):
```bash
cd ~/learning-algo
bash scripts/setup_node.sh          # baseline stack; prints python/glibc/GPU info and "ok: ..."
bash scripts/setup_node_gpu.sh      # PyTorch + LightGlue + weights; runs a SuperPoint+LightGlue smoke test
bash scripts/build_seed_code.sh     # C++ seed code into third_party/ (needs g++)
.venv/bin/python -m unittest discover -s tests -v
```

### Running
Single node (all 24 threads):
```bash
PYTHON=.venv/bin/python bash scripts/run_baseline.sh
```
All four nodes, scenes split round-robin (each node gets code + only its scenes' match files via rsync):
```bash
NODES="node1 node2 node3 node4" bash scripts/run_cluster.sh \
    data/ransac_tutorial/RANSAC-Tutorial-Data-Test test --method poselib --ratio 0.8 --threshold 1.0
```
Per-node logs: `results/<name>.<node>.log`. Merged summary: `results/<name>/<method>_.../summary.json`.

### Notes
- **Runtimes:** the i9-12900 mixes fast P-cores and slow E-cores, so ms/pair is noisy when the pool
  spans both. For runtime numbers in the paper, pin workers to P-cores with `--cpus`, e.g.
  `.venv/bin/python src/eval_relpose.py ... --cpus 0-15 --workers 8` (check `lscpu -e` for which
  logical CPUs are P-cores).
- **Disk:** 935 GB per node means PhotoTourism (~70 GB compressed) fits on one node.

## Sampling GT pairs / triplets
`src/sample_tuples.py` reads any COLMAP model and samples pairs or triplets whose images share
enough 3D points. Check against the literature: ETH3D training, pairs sharing >= 500 points gives
**1,969 pairs, exactly SupeRANSAC's count**.
```bash
python src/sample_tuples.py data/eth3d/courtyard/dslr_calibration_undistorted --size 2 --min-shared 500 --out results/tuples/courtyard.json
python src/sample_tuples.py data/aachen_v1_1/3D-models/aachen_v_1_1 --size 3 --num 5000 --out results/tuples/aachen.json   # ~30 s
```

## Evaluation protocol
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

## Three-view baselines (Tzamos et al. CVPR 2025 triplets)
Their protocol: tracks with both LightGlue scores >= 0.5, 5 px epipolar threshold, 100-1000 iterations,
pose error = max(mean R error, mean t error) over pairs 1-2 and 1-3; "AUC@k" = mean recall at 1..k deg (%).
PhotoTourism = 12 scenes (St. Peter's Square held out, as in the paper), 5,000 triplets each.

| Method | PT median | PT mean | PT AUC@5/10/20 | Aachen AUC@5/10/20 |
|---|---|---|---|---|
| Paper: 5pt+P3P (Table 3) | 1.60 | 5.40 | 62.93 / 74.30 / 83.00 | 43.43 / 56.73 / 68.28 |
| Paper: 4p3v(M±δ)+R+F+ENM (best) | 1.46 | 4.66 | 66.12 / 77.14 / 85.15 | 44.02 / 57.42 / 68.97 |
| Ours: `seq_5pt_p3p` (Python, upstream PoseLib) | 1.82 | 11.82 | 59.22 / 70.81 / 79.59 | 39.50 / 55.62 / 68.66 |
| Ours: `pairwise_5pt` | 1.99 | 11.56 | 57.04 / 69.59 / 79.12 | 40.19 / 57.40 / 70.92 |

Our sequential baseline runs two separate RANSACs; theirs scores and refines all three views jointly,
which explains most of the PhotoTourism gap (and the higher mean = more outright failures). Exact
reproduction needs their PoseLib fork (`scripts/build_seed_code.sh`).
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
