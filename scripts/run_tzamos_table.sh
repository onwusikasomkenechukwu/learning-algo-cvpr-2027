#!/usr/bin/env bash
# Reproduce the main table of Tzamos et al. CVPR 2025 with their own code (threeview eval.py +
# PoseLib@threeview fork, built by build_seed_code.sh) on every extracted triplet scene, at the 5 px
# threshold their table script reads (results/<scene>-5.0t-<features>.json).
#   bash scripts/run_tzamos_table.sh                 # eval.py --table (21 methods)
#   bash scripts/run_tzamos_table.sh --learning -a   # learned (L) variants, appended to the same json
# Results land in third_party/threeview/results/; each scene's summary table is printed, errors and
# progress bars go to ~/tzamos_stderr.log.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PY=$ROOT/.venv/bin/python
FEAT=triplets-features_superpoint_noresize_2048-LG
ARGS=("${@:---table}")
cd third_party/threeview   # the fork loads res/*.pt / res/*.txt relative to the working directory
export PYTHONPATH=$PWD
for s in "$ROOT"/data/tzamos_triplets/threeview/*/ "$ROOT"/data/tzamos_triplets/threeview/*/*/; do
  s=${s%/}
  [[ -f "$s/$FEAT.h5" ]] || continue
  echo "== $(basename "$s")  $(date +%T)"
  "$PY" eval.py -nw "$(nproc)" -t 5.0 "${ARGS[@]}" "$FEAT" "$s" 2>>"$HOME/tzamos_stderr.log" | tail -28 || echo "FAILED: $s"
done
echo "== all done  $(date +%T)"
