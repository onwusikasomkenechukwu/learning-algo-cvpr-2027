# learning-algo: learned minimal solvers + RANSAC (CVPR target)

Calibrated relative pose baselines, set up to run on an **offline 4-node cluster** (CPU work now; T1000 GPUs available later).

## Layout
```
src/eval_relpose.py           5-point RANSAC (PoseLib / OpenCV) + mAA / AUC evaluation
scripts/download_tier1.sh     dataset downloads (online machine)
scripts/extract_tier1.sh      unpack archives into data/
scripts/build_wheelhouse.sh   Linux wheels (Python 3.10-3.14) + uv binary for offline install (online machine)
scripts/setup_node.sh         offline venv setup on one cluster node
scripts/run_baseline.sh       baseline sweep on the RANSAC tutorial val split (one machine)
scripts/run_cluster.sh        split one evaluation across nodes by scene over SSH, gather + merge
scripts/merge_results.py      recompute summary.json from per-scene CSVs
requirements.lock             exact package versions (installed from wheelhouse/)
data/README.md                what each dataset contains + gotchas
```
`data/`, `wheelhouse/` and `results/` are not in git. Copy them separately.

## Cluster
Four identical nodes: i9-12900 (8P + 8E cores, 24 threads), 30 GB RAM, ~935 GB SSD, NVIDIA T1000 8 GB,
Ubuntu 26.04.1 LTS x86_64, gigabit Ethernet, SSH between nodes, **no internet**.

### One-time setup
On a machine with internet (done 2026-10-14; `wheelhouse/` is 254 MB, all Python 3.10-3.14 resolutions
checked offline for `x86_64-manylinux_2_28`):
```bash
bash scripts/build_wheelhouse.sh
```
Copy the repo including `wheelhouse/` and the data you need to the first node, then from there to the others:
```bash
rsync -av --exclude data/raw --exclude .venv ./ node1:learning-algo/
```
On **each** node (no sudo or apt needed; the bundled `uv` makes the venv, so `python3-venv` is not required):
```bash
cd ~/learning-algo && bash scripts/setup_node.sh      # prints python/glibc/GPU info and "ok: ..."
```

### Running
Single node (all 24 threads):
```bash
PYTHON=.venv/bin/python bash scripts/run_baseline.sh
```
All four nodes, scenes split round-robin (each node gets code + only its scenes' match files via rsync):
```bash
NODES="node1 node2 node3 node4" bash scripts/run_cluster.sh     data/ransac_tutorial/RANSAC-Tutorial-Data-Test test --method poselib --ratio 0.8 --threshold 1.0
```
Per-node logs: `results/<name>.<node>.log`. Merged summary: `results/<name>/<method>_.../summary.json`.

### Notes
- **Runtimes:** the i9-12900 mixes fast P-cores and slow E-cores, so ms/pair is noisy when the pool
  spans both. For runtime numbers in the paper, pin to P-cores and use fewer workers, e.g.
  `taskset -c 0-15 .venv/bin/python src/eval_relpose.py ... --workers 8` (check `lscpu -e` for which
  logical CPUs are P-cores).
- **GPUs:** the T1000s (Turing, 8 GB) are enough for SuperPoint + LightGlue feature extraction and
  small-network training. That needs CUDA PyTorch wheels in the wheelhouse (several GB) matched to
  the driver version that `setup_node.sh` prints. Not added yet.
- **Disk:** 935 GB per node means PhotoTourism (~70 GB compressed) fits on one node.

## Evaluation protocol
- Data: CVPR 2020 RANSAC tutorial epipolar split (PhotoTourism, RootSIFT + mutual NN matches).
  Validation = `sacre_coeur`, `st_peters_square`, 4,950 pairs each. Test = 11 scenes.
- Ground truth: `dR = R2 R1^T`, `dT = T2 - dR T1` (checked to reproduce the shipped `Egt.h5` exactly).
- Error per pair = max(rotation geodesic error, translation direction error) in degrees.
- **mAA@10**: mean over 1..10 deg thresholds of the fraction of pairs below each threshold (tutorial / IMC 2020 metric).
  **AUC@5/10/20**: SuperGlue-style area under the recall curve.
- Per-pair CSVs and `summary.json` go to `results/val/<method>_th<px>_r<ratio>/`.

## Baseline results (validation, 2026-10-14)
RANSAC tutorial val split, 9,900 pairs (sacre_coeur + st_peters_square), threshold in pixels,
`ratio` = SNN ratio filter on matches. Run on a 16-thread Windows laptop; timings are per pair, single thread.

| Method | Ratio | Thr (px) | mAA@10 | AUC@5 | AUC@10 | AUC@20 | ms/pair |
|---|---|---|---|---|---|---|---|
| PoseLib 5pt LO-RANSAC | all | 1.0 | 0.493 | 0.368 | 0.467 | 0.576 | ~278 |
| **PoseLib 5pt LO-RANSAC** | **0.8** | **1.0** | **0.767** | **0.630** | **0.733** | **0.816** | ~20 |
| PoseLib 5pt LO-RANSAC | 0.8 | 0.5 | 0.754 | 0.613 | 0.719 | 0.805 | ~28 |
| PoseLib 5pt LO-RANSAC | 0.8 | 2.0 | 0.748 | 0.608 | 0.714 | 0.805 | ~15 |
| OpenCV USAC_MAGSAC | 0.8 | 1.0 | 0.597 | 0.416 | 0.560 | 0.700 | ~39 |
| OpenCV RANSAC | 0.8 | 1.0 | 0.643 | 0.449 | 0.603 | 0.737 | ~274 |

The test pack has no ground truth (see data/README.md), so there are no test numbers yet.
MAGSAC's threshold means something different (max sigma), so 1 px is probably not its best setting.
