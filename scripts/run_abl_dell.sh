#!/usr/bin/env bash
# Everything the week-2 plan needs from abl-dell, in one command (student instructions v5):
#   setup      git pull, CPU patch for threeview, LightGlue weights from the SSD, import checks, smoke test
#   machine    Task 1.3 machine sheet (CPU, NUMA, AVX/FMA, governor, SMT, memory)
#   monodromy  Task 1.8 solution count on two more instances (background, ~2 h each, one core each)
#   triplets   Task 1.6 Cambridge SP+LG triplets for the scenes not finished on the laptop (resumable)
#   evalf      Tasks 1.7 / 1.9 / 2.2: released eval_f.py (6pt+P3P = 6p3v, 4p3vf(M), (M)+R, ...) on every
#              finished scene; one run each (eval_f.py has no RANSAC seed option)
#   killB      Kill test B on SP+LG all-inlier samples, one per triplet, sharded over all cores, then the
#              decision (continuation >= LM + 5 pp, McNemar p < 0.05)
#   collect    copy results to the SSD (abl_dell_results/) so the laptop can read them
# Not in the default list:
#   thresh     Task 2.1 step 1 / Task 1.5: the Tzamos table at threshold 1.0 on every released scene (long)
# Not possible yet: the kill test A re-fit (ENM-like) for the shared-focal estimator needs new C++ in the fork.
#
#   bash scripts/run_abl_dell.sh               # default steps, in the background; prints how to check
#   bash scripts/run_abl_dell.sh status        # one-screen progress summary (take a photo of this)
#   bash scripts/run_abl_dell.sh killB collect # only these steps
# Env: SSD=/media/$USER/SSD/learning-algo-cvpr  NSHARDS=<processes for killB, default nproc - 2>
#      KB_N=<max samples per killB process, default all>  PY=<python, default .venv/bin/python>
#      THETA=2.0 (inlier px at 800 px)  UNDISTORT=1 (undistort Cambridge keypoints with the NVM radial terms)
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
SSD=${SSD:-/media/$USER/SSD/learning-algo-cvpr}
PY=${PY:-$ROOT/.venv/bin/python}
TV=$ROOT/third_party/threeview
OUT=$ROOT/results/abl_dell
TRIP=$SSD/data/cambridge_triplets
CAM=$SSD/data/cambridge
FEAT=triplets-features_superpoint_800_2048-LG
SCENES=(KingsCollege OldHospital ShopFacade StMarysChurch GreatCourt)
mkdir -p "$OUT"

if [[ ${1:-} != status && -z ${ABL_BG:-} ]]; then
  ABL_BG=1 nohup bash "$ROOT/scripts/run_abl_dell.sh" "$@" >>"$OUT/run.log" 2>&1 &
  echo $! >"$OUT/runner.pid"
  echo "started in the background (pid $!), log: $OUT/run.log"
  echo "check progress with:  bash scripts/run_abl_dell.sh status"
  exit 0
fi

log() { echo "[$(date '+%F %T')] $*"; }
die() { log "FAILED: $*"; exit 1; }
ntrip() { [[ -f $TRIP/$1/$FEAT.txt ]] && wc -l <"$TRIP/$1/$FEAT.txt" || echo 0; }

step_setup() {
  [[ -d $SSD/data/cambridge ]] || die "SSD not found at $SSD (plug it in, or set SSD=...)"
  git pull --ff-only || log "git pull failed; continuing with the local checkout"
  [[ -d $TV ]] || die "third_party/threeview missing: run bash scripts/setup_workstation.sh first"
  grep -q "DEVICE = " "$TV/datasets/prepare_im.py" \
    || patch -d "$TV" -p1 --forward <scripts/patches/threeview-cpu.patch || die "threeview-cpu.patch"
  grep -q "Resuming with" "$TV/datasets/prepare_im.py" || die "threeview has an older CPU patch: re-extract it"
  local ck=$HOME/.cache/torch/hub/checkpoints
  mkdir -p "$ck"
  for w in superpoint_v1.pth superpoint_lightglue_v0-1_arxiv.pth; do
    [[ -f $ck/$w ]] || cp "$SSD/wheelhouse/weights/$w" "$ck/" || log "no $w on the SSD; LightGlue will download it"
  done
  "$PY" -c "import cv2" 2>/dev/null \
    || "$PY" -m pip install --no-index --find-links "$SSD/wheelhouse" opencv-python-headless || die "opencv"
  "$PY" -c "import poselib, lightglue, cv2, h5py, scipy; print('imports ok, opencv', cv2.__version__)" \
    || die "python imports"
  OMP_NUM_THREADS=1 "$PY" -W ignore src/homotopy_proto.py --n 3 --noise 0.5 --out "$OUT/smoke" >/dev/null \
    || die "prototype smoke test"
  log "setup ok"
}

step_machine() {
  {
    echo "== $(hostname) $(date '+%F %T')"; uname -a; nproc
    lscpu
    command -v numactl >/dev/null && numactl -H || echo "numactl not installed (sudo apt install numactl)"
    echo "== ISA flags"; grep -o -w -E 'avx|avx2|avx512f|fma' /proc/cpuinfo | sort | uniq -c
    echo "== governor"; cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort | uniq -c
    echo "== SMT"; cat /sys/devices/system/cpu/smt/active 2>/dev/null
    echo "== memory"; free -g
    echo "== compiler"; gcc --version | head -1
    echo "== python"; "$PY" -c "import numpy, scipy, torch; print(numpy.__version__, scipy.__version__, torch.__version__)"
  } >"$OUT/machine_sheet.txt" 2>&1
  log "machine sheet: $OUT/machine_sheet.txt"
}

step_monodromy() {
  for r in 8 9; do
    [[ -f $OUT/monodromy_rng$r/checks_monodromy.json ]] && continue
    OMP_NUM_THREADS=1 nohup "$PY" -u -W ignore src/check_fourp3vf.py --only monodromy --instances 1 --rng $r \
      --out "$OUT/monodromy_rng$r" >"$OUT/monodromy_rng$r.log" 2>&1 &
  done
  log "monodromy started in the background (logs $OUT/monodromy_rng*.log)"
}

step_triplets() {
  local todo=()
  for s in "${SCENES[@]}"; do
    (( $(ntrip "$s") >= 5000 )) && continue
    [[ -d $CAM/$s/model_train ]] || "$PY" scripts/cambridge_nvm_to_colmap.py "$CAM/$s" "$CAM" || die "model $s"
    todo+=("$s")
  done
  (( ${#todo[@]} )) || { log "triplets: all scenes done"; return; }
  log "triplets for: ${todo[*]}"
  ( cd "$TV" && "$PY" -u -W ignore "$ROOT/scripts/prepare_cambridge_triplets.py" --threeview . "$TRIP" "$CAM" \
      "${todo[@]}" ) >>"$OUT/triplets.log" 2>&1 || die "triplets (see $OUT/triplets.log)"
  log "triplets done"
}

step_evalf() {
  mkdir -p "$TV/results"
  for s in "${SCENES[@]}"; do
    (( $(ntrip "$s") >= 5000 )) || { log "evalf: skip $s (triplets not finished)"; continue; }
    [[ -f $TV/results/focal_$s-$FEAT.json ]] && { log "evalf: $s already done"; continue; }
    log "evalf: $s"
    ( cd "$TV" && PYTHONPATH=$PWD "$PY" -W ignore eval_f.py -nw "$(( $(nproc) - 2 ))" "$FEAT" "$TRIP/$s" ) \
      >"$OUT/evalf_$s.log" 2>&1 || log "evalf $s failed (see $OUT/evalf_$s.log)"
    tail -16 "$OUT/evalf_$s.log"
  done
}

step_killB() {
  local n=${NSHARDS:-$(( $(nproc) - 2 ))} kb=$ROOT/results/killB files=() pids
  mkdir -p "$kb"
  for s in "${SCENES[@]}"; do
    (( $(ntrip "$s") >= 5000 )) || { log "killB: skip $s (triplets not finished)"; continue; }
    local nvm=()
    [[ ${UNDISTORT:-1} == 1 ]] && nvm=(--nvm "$CAM/$s/reconstruction.nvm")
    log "killB: $s on $n processes"
    pids=()
    for ((i = 0; i < n; i++)); do
      files+=("$kb/${s}_shard$i.jsonl")
      [[ -f $kb/${s}_shard${i}_summary.json ]] && continue
      OMP_NUM_THREADS=1 "$PY" -W ignore src/homotopy_proto.py --mode triplets --scene "$TRIP/$s" "${nvm[@]}" \
        --theta "${THETA:-2.0}" --shard $i --nshards "$n" --n "${KB_N:-100000}" --rng $i --out "$kb/${s}_shard$i" \
        >/dev/null 2>>"$OUT/killB.err" &
      pids+=($!)
    done
    (( ${#pids[@]} )) && wait "${pids[@]}"   # only the shards: monodromy keeps running in the background
  done
  (( ${#files[@]} )) || { log "killB: no finished scenes"; return; }
  "$PY" -W ignore src/homotopy_proto.py --merge "${files[@]}" --out "$OUT/killB" | tee "$OUT/killB.txt"
}

step_thresh() {
  bash scripts/run_tzamos_table.sh --table -t 1.0 >"$OUT/thresh1.log" 2>&1
  log "threshold 1.0 table done (see $OUT/thresh1.log)"
}

step_collect() {
  local dst=$SSD/abl_dell_results
  mkdir -p "$dst"
  cp -r "$OUT" "$dst/" 2>/dev/null
  cp -r "$ROOT/results/killB" "$dst/" 2>/dev/null
  cp "$TV"/results/focal_*.json "$dst/" 2>/dev/null
  log "copied results to $dst"
}

step_status() {
  echo "== $(date '+%F %T')  SSD: $SSD"
  for s in "${SCENES[@]}"; do
    printf '%-14s triplets %5s  evalf %-4s  killB shards %s\n' "$s" "$(ntrip "$s")" \
      "$([[ -f $TV/results/focal_$s-$FEAT.json ]] && echo done || echo -)" \
      "$(ls "$ROOT/results/killB/${s}_shard"*_summary.json 2>/dev/null | wc -l)"
  done
  tail -c 300 "$OUT/triplets.log" 2>/dev/null | tr '\r' '\n' | grep -v '^\s*$' | tail -1
  for r in 8 9; do echo "monodromy rng$r: $(tail -1 "$OUT/monodromy_rng$r.log" 2>/dev/null)"; done
  [[ -f $OUT/killB.txt ]] && tail -1 "$OUT/killB.txt"
  echo "== last log lines"; tail -4 "$OUT/run.log" 2>/dev/null
  if [[ -f $OUT/runner.pid ]] && kill -0 "$(cat "$OUT/runner.pid")" 2>/dev/null; then
    echo "runner: RUNNING"
  else
    echo "runner: not running"
  fi
}

STEPS=("$@")
(( ${#STEPS[@]} )) || STEPS=(setup machine monodromy triplets evalf killB collect)
for st in "${STEPS[@]}"; do
  declare -F "step_$st" >/dev/null || die "unknown step: $st"
  [[ $st == status ]] || log "== $st"
  "step_$st"
done
if [[ " ${STEPS[*]} " == *" monodromy "* ]]; then
  log "waiting for monodromy"; wait; step_collect
fi
[[ ${STEPS[*]} == status ]] || log "all requested steps finished"
