#!/usr/bin/env bash
# Generate Hruby et al. (CVPR 2022) 4p3v problem-solution data from ETH3D, following their Sec. 5.1 split:
#   anchors:    office + terrains, 40k samples each   (their Tab. 1-3)
#   validation: delivery_area + facade, 30k each      (their test scenes)
#   training:   remaining ETH3D training scenes, ~1M each
# The paper trains on "23 other sequences"; only 13 DSLR training scenes are public with GT here,
# so training uses the 9 that are left (see data/README.md, OQ4 in Datasets.pdf).
# Output: results/hruby/{anchor,val,train}_<scene>.txt in the C++ pipeline's format.
# Usage: bash scripts/make_hruby_data.sh [train_target]   (default 1000000; use e.g. 20000 for a quick run)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}
TRAIN=${1:-1000000}
OUT=results/hruby; mkdir -p "$OUT"
model() { echo "data/eth3d/$1/dslr_calibration_undistorted"; }
for s in office terrains;        do "$PY" src/sample_hruby4p3v.py "$(model $s)" "$OUT/anchor_$s.txt" --target 40000 --seed 1; done
for s in delivery_area facade;   do "$PY" src/sample_hruby4p3v.py "$(model $s)" "$OUT/val_$s.txt"    --target 30000 --seed 2; done
for s in courtyard electro kicker meadow pipes playground relief relief_2 terrace; do
  "$PY" src/sample_hruby4p3v.py "$(model $s)" "$OUT/train_$s.txt" --target "$TRAIN" --seed 3 &
done
wait
wc -l "$OUT"/*.txt
