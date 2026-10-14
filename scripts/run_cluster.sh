#!/usr/bin/env bash
# Spread one evaluation over the cluster nodes by scene, then gather and merge results.
# No scheduler needed: plain SSH + rsync. Run from the repo root on the node you are logged into.
#
#   NODES="node1 node2 node3 node4" bash scripts/run_cluster.sh \
#       data/ransac_tutorial/RANSAC-Tutorial-Data-Test test --method poselib --ratio 0.8 --threshold 1.0
#
# Arguments: <split_dir> <results_name> [extra eval_relpose.py args...]
# Each node gets the code (rsync) and only the scene folders it needs; scenes already on a node are skipped.
# Every node must have run scripts/setup_node.sh once (REMOTE_DIR/.venv must exist).
set -euo pipefail
cd "$(dirname "$0")/.."
SPLIT=$1; NAME=$2; shift 2
read -r -a NODES <<<"${NODES:?set NODES to the space-separated node hostnames}"
REMOTE_DIR=${REMOTE_DIR:-$PWD}
mapfile -t SCENES < <(for d in "$SPLIT"/*/; do [[ -f "$d/matches.h5" ]] && basename "$d"; done)
echo "${#SCENES[@]} scenes over ${#NODES[@]} nodes"
mkdir -p "results/$NAME"

pids=()
for i in "${!NODES[@]}"; do
  node=${NODES[$i]}; mine=()
  for j in "${!SCENES[@]}"; do (( j % ${#NODES[@]} == i )) && mine+=("${SCENES[$j]}"); done
  [[ ${#mine[@]} -gt 0 ]] || continue
  echo "$node: ${mine[*]}"
  (
    ssh "$node" "mkdir -p '$REMOTE_DIR/$SPLIT'"
    rsync -a --exclude data --exclude results --exclude .venv --exclude .git ./ "$node:$REMOTE_DIR/"
    for s in "${mine[@]}"; do
      rsync -a --exclude images "$SPLIT/$s" "$node:$REMOTE_DIR/$SPLIT/"   # matches + poses only
    done
    ssh "$node" "cd '$REMOTE_DIR' && OMP_NUM_THREADS=1 .venv/bin/python src/eval_relpose.py \
        --data '$SPLIT' --scenes ${mine[*]} --out 'results/$NAME' $*"
    rsync -a "$node:$REMOTE_DIR/results/$NAME/" "results/$NAME/"
  ) > "results/$NAME.$node.log" 2>&1 &
  pids+=($!)
done
fail=0; for p in "${pids[@]}"; do wait "$p" || fail=1; done
[[ $fail -eq 0 ]] || { echo "a node failed; see results/$NAME.*.log"; exit 1; }
.venv/bin/python scripts/merge_results.py "results/$NAME"/*/
