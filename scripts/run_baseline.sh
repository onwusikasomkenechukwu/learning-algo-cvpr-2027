#!/usr/bin/env bash
# Five-point relative pose baselines on the RANSAC tutorial validation scenes.
# Runs on one machine with all cores; see run_cluster.sh to spread scenes over nodes.
# Usage: bash scripts/run_baseline.sh [split_dir]
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
DATA=${1:-data/ransac_tutorial/RANSAC-Tutorial-Data-ValOnly/val}
run() { "$PY" src/eval_relpose.py --data "$DATA" --out results/val "$@"; }
run --method poselib    --ratio 1.0 --threshold 1.0
run --method poselib    --ratio 0.8 --threshold 1.0
run --method poselib    --ratio 0.8 --threshold 0.5
run --method poselib    --ratio 0.8 --threshold 2.0
run --method cv2_magsac --ratio 0.8 --threshold 1.0
run --method cv2_ransac --ratio 0.8 --threshold 1.0
