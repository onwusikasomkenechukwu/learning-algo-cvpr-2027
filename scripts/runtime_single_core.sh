#!/usr/bin/env bash
# Runtime of the main estimators on ONE pinned core, one process, with the CPU model recorded (the
# table runs use every core in parallel, so their ms only compare rows with each other). Run it inside the
# booked timing window with nothing else running (ground rules 4-6).
# Runs Tzamos et al.'s eval.py (calibrated, released triplets) and eval_f.py (shared focal, our Cambridge
# triplets) with --tag 1core, so the main results files are not touched, on the first N triplets of one
# scene each. --exps / --tag come from scripts/patches/threeview-eval.patch.
#   bash scripts/runtime_single_core.sh                  # N=500, the timing core of scripts/machine_sheet.sh
#   N=1000 CORE=5 CALIB_SCENE=sacre_coeur FOCAL_SCENE=/path/to/KingsCollege bash scripts/runtime_single_core.sh
# Output: results/runtime_1core_<host>.txt (CPU, governor, then the per-method tables).
# For stable numbers: the performance governor if the administrator allows it
# (sudo cpupower frequency-set -g performance); the governor in use is recorded either way.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PY=$ROOT/.venv/bin/python
SSD=${SSD:-/media/$USER/SSD/learning-algo-cvpr}
N=${N:-500}
# Default core: the second physical core of NUMA node 0, first hardware thread (as in machine_sheet.sh).
topo=$(lscpu -p=CPU,CORE,SOCKET,NODE | grep -v '^#')
tcore=$(echo "$topo" | awk -F, '$4 == 0 {print $2}' | sort -n -u | sed -n 2p)
CORE=${CORE:-$(echo "$topo" | awk -F, -v c="$tcore" '$2 == c {print $1; exit}')}
NODE=$(echo "$topo" | awk -F, -v c="$CORE" '$1 == c {print $4; exit}')
CALIB_FEAT=triplets-features_superpoint_noresize_2048-LG
FOCAL_FEAT=${FOCAL_FEAT:-triplets-features_superpoint_800_2048-LG}
CALIB=$(realpath -m "data/tzamos_triplets/threeview/${CALIB_SCENE:-sacre_coeur}")
[[ -d $CALIB ]] || CALIB=$(realpath -m "data/tzamos_triplets/threeview/phototourism/${CALIB_SCENE:-sacre_coeur}")
FOCAL=$(realpath -m "${FOCAL_SCENE:-$SSD/data/cambridge_triplets/KingsCollege}")
CALIB_EXPS=${CALIB_EXPS:-"5p3v;5p3v + R + C;4p3v(M) + R + C;4p3v(M-D) + R + C + ENM;4p3v(A) + R + C + ENM;4p(HC)"}
FOCAL_EXPS=${FOCAL_EXPS:-"6p3v;6p3v + R + C;4p3v(M) + R + C;4p3v(M-D) + R + C"}
OUT=$ROOT/results/runtime_1core_$(hostname -s).txt
mkdir -p "$ROOT/results"
command -v taskset >/dev/null || { echo "ERROR: taskset missing (sudo apt install util-linux)"; exit 1; }
PIN=(taskset -c "$CORE")
command -v numactl >/dev/null && PIN=(numactl --physcpubind="$CORE" --membind="$NODE")

{
  echo "# single-core runtime, $(date -Is), host $(hostname -s), cpu $CORE (node $NODE), first $N triplets"
  echo "# pinning: ${PIN[*]}"
  echo "# CPU: $(lscpu | sed -n 's/^Model name: *//p' | head -1)"
  echo "# max MHz: $(lscpu | sed -n 's/^CPU max MHz: *//p' | head -1), governor: $(cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_governor 2>/dev/null || echo unknown)"
  echo "# repo $(git rev-parse --short HEAD), poselib: $("$PY" -c 'import poselib; print(poselib.__file__)'), torch threads forced to 1 by eval.py"
} | tee "$OUT"

cd third_party/threeview
grep -q -- "--exps" eval_f.py || { echo "ERROR: threeview-eval.patch not applied (bash scripts/run_abl_dell.sh setup)"; exit 1; }
export PYTHONPATH=$PWD OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MPLBACKEND=Agg
run() {  # run <script> <scene_dir> <feature> <exps> <extra args...>
  local script=$1 scene=$2 feat=$3 exps=$4; shift 4
  [[ -f "$scene/$feat.h5" ]] || { echo "SKIP $script: no $feat.h5 in $scene" | tee -a "$OUT"; return; }
  echo -e "\n## $script $(basename "$scene") ($exps)" | tee -a "$OUT"
  "${PIN[@]}" "$PY" "$script" -nw 1 -f "$N" --tag 1core --exps "$exps" "$@" "$feat" "$scene" \
    2>>"$HOME/runtime_1core_stderr.log" | tail -$(( $(tr -cd ';' <<<"$exps" | wc -c) + 6 )) | tee -a "$OUT"
}
run eval.py "$CALIB" "$CALIB_FEAT" "$CALIB_EXPS" -t 5.0
run eval_f.py "$FOCAL" "$FOCAL_FEAT" "$FOCAL_EXPS"
echo -e "\nwritten to $OUT"
