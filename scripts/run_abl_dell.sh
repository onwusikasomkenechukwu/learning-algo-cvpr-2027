#!/usr/bin/env bash
# Everything the week-2 plan needs from abl-dell, in one command (student instructions v5):
#   setup      git pull, threeview patches (CPU, eval options), LightGlue weights from the SSD, import checks,
#              smoke test, and a fork rebuild when the OOB fixes or the refit are missing (fork_build.log)
#   machine    Task 1.3 machine sheet (scripts/machine_sheet.sh -> results/abl_dell/machine_sheet.md)
#   monodromy  Task 1.8 solution count on two more instances (background, ~2 h each, one core each)
#   triplets   Task 1.6 Cambridge SP+LG triplets for the scenes not finished on the laptop (resumable)
#   sift       Task 1.6 SIFT (RootSIFT 8000 + ratio test) tracks on the same triplets, Cambridge and ETH3D
#   evalf      Tasks 1.7 / 1.9 / 2.2: released eval_f.py (6pt+P3P = 6p3v, 4p3vf(M), (M)+R, ...) on every
#              finished scene and feature type; one run each (eval_f.py has no RANSAC seed option)
#   killB      Kill test B on SP+LG all-inlier samples, one per triplet, sharded over all cores, then the
#              decision (continuation >= LM + 5 pp, McNemar p < 0.05)
#   killA      Kill test A: rebuild the fork with the shared-focal two-view refit, run the re-fitted mean-point
#              rows ('+ ENM') per Cambridge scene, decide (best re-fitted variant trails 6p3v by >= 2.0 AUC@10)
#   seq        Task 2.9 sequential baseline ('6p3v + SEQ') per Cambridge scene, next to 6pt+P3P
#   control    5pt+P3P+R+F control row (eval.py '5p3v + R + C') on the released triplets, own results file
#   eth3d      ETH3D SP+LG triplets (12 scenes, every qualifying triplet, 800 px), filtered to one
#              intrinsics block per triplet (Tasks 1.4 / 1.6)
#   compare    pooled shared-focal tables per dataset and feature (scripts/compare_tzamos_focal.py)
#   requeue    (not default) move results computed before the OOB fix aside so evalf / killA / control rerun
#   crashdebug replay saved poselib crashes under gdb -> results/abl_dell/crash_report.txt (native backtraces)
#   collect    copy results to the SSD (abl_dell_results/) so the laptop can read them
# The default list runs eth3d after the Cambridge work and repeats sift / evalf for ETH3D afterwards.
# Not in the default list:
#   thresh     Task 2.1 step 1 / Task 1.5: the Tzamos table at threshold 1.0 on every released scene (long)
#   runtime    single-core timing (scripts/runtime_single_core.sh): only in the booked timing window
#
#   bash scripts/run_abl_dell.sh               # default steps, in the background; prints how to check
#   bash scripts/run_abl_dell.sh status        # one-screen progress summary (take a photo of this)
#   bash scripts/run_abl_dell.sh killB collect # only these steps
# Env: SSD=/media/$USER/SSD/learning-algo-cvpr  NSHARDS=<processes for killB, default nproc - 2>
#      KB_N=<max samples per killB process, default all>  PY=<python, default .venv/bin/python>
#      THETA=2.0 (inlier px at 800 px)  UNDISTORT=1 (undistort Cambridge keypoints with the NVM radial terms)
#      EVALF_TIMEOUT=14400 (outer bound per eval_f.py run; hung, idle runs are killed after 2 min by a watchdog)
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
SSD=${SSD:-/media/$USER/SSD/learning-algo-cvpr}
PY=${PY:-$ROOT/.venv/bin/python}
TV=$ROOT/third_party/threeview
OUT=$ROOT/results/abl_dell
TRIP=$SSD/data/cambridge_triplets
CAM=$SSD/data/cambridge
ETRIP=$SSD/data/eth3d_triplets
ETH=$SSD/data/eth3d
FEAT=triplets-features_superpoint_800_2048-LG
SIFT=triplets-SIFT_triplet_correspondences-rootsift8000
SCENES=(KingsCollege OldHospital ShopFacade StMarysChurch GreatCourt)
# Tzamos et al.'s ETH3D list (the 13 training scenes without facade)
ETH_SCENES=(courtyard delivery_area electro kicker meadow office pipes playground relief relief_2 terrace terrains)
NW=$(( $(nproc) - 2 ))   # leave two cores for interactive work (ground rule 6)
# One thread per worker process (ground rule 6): without this every eval_f.py worker's PyTorch / BLAS starts
# a thread per core, and 94 workers x 96 threads stalled the first King's College run for a day.
ONE_THREAD=(env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1)
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
nlines() { [[ -f $1 ]] && wc -l <"$1" || echo 0; }
cam_done() { (( $(nlines "$TRIP/$1/$FEAT.txt") >= 5000 )); }
eth_done() { [[ -f $ETRIP/$1/$FEAT.all.txt ]]; }   # written by filter_same_camera.py at the end of a scene
finished_dirs() {   # "<triplet dir> <image root>" for every scene with finished SP+LG triplets
  for s in "${SCENES[@]}"; do cam_done "$s" && echo "$TRIP/$s $CAM/$s"; done
  for s in "${ETH_SCENES[@]}"; do eth_done "$s" && echo "$ETRIP/$s $ETH/$s/images"; done
}

fork_current() {   # the built fork carries every source edit of scripts/build_seed_code.sh
  local src=$ROOT/third_party/PoseLib-threeview/PoseLib/robust/estimators/relative_pose.cc
  grep -q "OOB fix" "$src" 2>/dev/null && grep -q "Two-view refit (kill test A" "$src" 2>/dev/null \
    && grep -q "estimate_3v_shared_focal_sequential" "$ROOT/third_party/PoseLib-threeview/PoseLib/robust.cc" 2>/dev/null
}

step_setup() {
  [[ -d $SSD/data/cambridge ]] || die "SSD not found at $SSD (plug it in, or set SSD=...)"
  git pull --ff-only || log "git pull failed; continuing with the local checkout"
  [[ -d $TV ]] || die "third_party/threeview missing: run bash scripts/setup_workstation.sh first"
  grep -q "DEVICE = " "$TV/datasets/prepare_im.py" \
    || patch -d "$TV" -p1 --forward <scripts/patches/threeview-cpu.patch || die "threeview-cpu.patch"
  grep -q "Resuming with" "$TV/datasets/prepare_im.py" || die "threeview has an older CPU patch: re-extract it"
  grep -q -- "--exps" "$TV/eval_f.py" \
    || patch -d "$TV" -p1 --forward <scripts/patches/threeview-eval.patch || die "threeview-eval.patch"
  "$PY" scripts/patches/threeview_enm.py "$TV" >/dev/null || die "threeview_enm.py"   # '+ ENM' (kill test A)
  "$PY" scripts/patches/threeview_seq.py "$TV" >/dev/null || die "threeview_seq.py"   # '+ SEQ' (Task 2.9)
  local ck=$HOME/.cache/torch/hub/checkpoints
  mkdir -p "$ck"
  for w in superpoint_v1.pth superpoint_lightglue_v0-1_arxiv.pth; do
    [[ -f $ck/$w ]] || cp "$SSD/wheelhouse/weights/$w" "$ck/" || log "no $w on the SSD; LightGlue will download it"
  done
  "$PY" -c "import cv2" 2>/dev/null \
    || "$PY" -m pip install --no-index --find-links "$SSD/wheelhouse" opencv-python-headless || die "opencv"
  "$PY" -c "import poselib, lightglue, cv2, h5py, scipy; cv2.SIFT_create(); print('imports ok, opencv', cv2.__version__)" \
    || die "python imports"
  OMP_NUM_THREADS=1 "$PY" -W ignore src/homotopy_proto.py --n 3 --noise 0.5 --out "$OUT/smoke" >/dev/null \
    || die "prototype smoke test"
  if ! fork_current; then   # out-of-bounds fixes and the kill test A refit (scripts/patches/poselib_*.py)
    log "setup: rebuilding the PoseLib fork with the OOB fixes and the refit (log $OUT/fork_build.log)"
    ONLY=poselib bash scripts/build_seed_code.sh >"$OUT/fork_build.log" 2>&1 && fork_current \
      && log "setup: fork rebuilt" \
      || log "setup: fork rebuild FAILED (see $OUT/fork_build.log); the old poselib stays installed"
  fi
  log "setup ok"
}

step_machine() {
  PY=$PY bash scripts/machine_sheet.sh "$OUT/machine_sheet.md" "$SSD" >/dev/null 2>"$OUT/machine_sheet.err"
  { lscpu; command -v numactl >/dev/null && numactl -H; } >"$OUT/machine_raw.txt" 2>&1   # raw output, for checking
  log "machine sheet: $OUT/machine_sheet.md"
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
    cam_done "$s" && continue
    [[ -d $CAM/$s/model_train ]] || "$PY" scripts/cambridge_nvm_to_colmap.py "$CAM/$s" "$CAM" || die "model $s"
    todo+=("$s")
  done
  (( ${#todo[@]} )) || { log "triplets: all scenes done"; return; }
  log "triplets for: ${todo[*]}"
  ( cd "$TV" && "$PY" -u -W ignore "$ROOT/scripts/prepare_triplets.py" --threeview . "$TRIP" "$CAM" "${todo[@]}" ) \
    >>"$OUT/triplets.log" 2>&1 || die "triplets (see $OUT/triplets.log)"
  log "triplets done"
}

step_eth3d() {
  for s in "${ETH_SCENES[@]}"; do
    eth_done "$s" && continue
    log "eth3d triplets: $s"
    ( cd "$TV" && "$PY" -u -W ignore "$ROOT/scripts/prepare_triplets.py" -n 0 --threeview . "$ETRIP" "$ETH" "$s" ) \
      >>"$OUT/eth3d.log" 2>&1 || { log "eth3d $s failed (see $OUT/eth3d.log)"; continue; }
    "$PY" scripts/filter_same_camera.py "$ETRIP/$s" "$ETH/$s/dslr_calibration_undistorted" | tee -a "$OUT/eth3d.log"
  done
}

step_sift() {
  local dir img
  while read -r dir img; do
    [[ -f $dir/$SIFT.txt ]] && continue
    log "sift: $(basename "$dir")"
    "$PY" -W ignore src/sift_triplets.py "$dir" "$img" -nw "$NW" >>"$OUT/sift.log" 2>&1 \
      || log "sift $(basename "$dir") failed (see $OUT/sift.log)"
  done < <(finished_dirs)
}

group_cpu() {   # cumulative CPU seconds of every process in process group $1 (empty if ps cannot tell)
  ps -eo pgid=,times= 2>/dev/null | awk -v g="$1" '$1 == g {s += $2; n++} END {if (n) print s}'
}

run_evalf() {   # run_evalf <triplet dir> <feature> <tag or ""> [eval_f.py options...]
  # eval_f.py forks a Pool it never closes, and on abl-dell runs sometimes froze for good (St Mary's: 3 of 5
  # tries on 2026-10-22/23), idle. A watchdog polls the CPU time of the run's process group (timeout makes
  # one) every 30 s: no CPU for 2 min after it was busy means a hang, and the group is killed and the run
  # retried (at most four tries). Once the results file exists the run is not waited for any more.
  # EVALF_TIMEOUT stays as an outer bound for the case where ps cannot read the group.
  local dir=$1 f=$2 tag=$3 s try pid cpu last idle; shift 3
  s=$(basename "$dir")
  local short=splg; [[ $f == *SIFT* ]] && short=sift   # SP+LG and SIFT logs must not share a name
  local json=$TV/results/focal_$s${tag:+-$tag}-$f.json logf=$OUT/evalf_${s}${tag:+_$tag}_$short.log
  for try in 1 2 3 4; do
    [[ -f $json ]] && return 0
    log "evalf: $s $f${tag:+ ($tag)} (try $try)"
    # eval_f_safe.py runs eval_f.py unchanged with a pool that survives poselib crashes (general protection
    # faults on some Great Court / St Mary's triplets) and saves each crashing task for crashdebug.
    ( cd "$TV" && exec env PYTHONPATH="$PWD" MPLBACKEND=Agg EVALF_CRASH_DIR="$OUT/crashes/${s}${tag:+_$tag}_$short" \
        timeout -k 60 "${EVALF_TIMEOUT:-14400}" "${ONE_THREAD[@]}" \
        "$PY" -W ignore "$ROOT/scripts/eval_f_safe.py" -nw "$NW" ${tag:+--tag "$tag"} "$@" "$f" "$dir" ) \
      >"$logf" 2>&1 &
    pid=$! last=0 idle=0      # after exec this pid is timeout's, which leads its own process group
    while kill -0 "$pid" 2>/dev/null; do
      sleep 30
      if [[ -f $json ]]; then                      # results written: give it a minute to exit, then stop it
        sleep 60; kill -0 "$pid" 2>/dev/null && kill -TERM -- "-$pid" 2>/dev/null; break
      fi
      cpu=$(group_cpu "$pid")
      [[ -n $cpu ]] || continue                    # ps cannot read the group: rely on the outer timeout
      if (( last > 0 && cpu <= last )); then idle=$((idle + 1)); else idle=0; fi
      last=$cpu
      if (( idle >= 4 )); then
        log "evalf $s $f: no CPU use for 2 min, killing the hung run"
        kill -TERM -- "-$pid" 2>/dev/null; sleep 10; kill -KILL -- "-$pid" 2>/dev/null; break
      fi
    done
    wait "$pid" 2>/dev/null || log "evalf $s $f: exit $? (124 = outer timeout, 143/137 = stopped; see $logf)"
  done
  [[ -f $json ]] || { log "evalf $s $f${tag:+ ($tag)}: no results after 4 tries"; return 1; }
}

step_evalf() {
  mkdir -p "$TV/results"
  local dir img f
  while read -r dir img; do
    for f in "$FEAT" "$SIFT"; do
      [[ -f $dir/$f.txt ]] && run_evalf "$dir" "$f" ""
    done
  done < <(finished_dirs)
}

step_killA() {
  # Kill test A (Tasks 1.9 / 2.2): the mean-point family with the two-view refit ('+ ENM') against 6pt+P3P on
  # the five Cambridge scenes. The fork is rebuilt once with scripts/patches/poselib_shared_focal_refit.py.
  fork_current || { log "killA: the fork lacks the refit (see setup); kill test A skipped"; return; }
  "$PY" scripts/patches/threeview_enm.py "$TV" || { log "killA: could not map '+ ENM' in eval_f.py"; return; }
  local exps="4p3v(M) + ENM;4p3v(M) + R + ENM;4p3v(M) + R + C + ENM;4p3v(M-D) + ENM;4p3v(M-D) + R + ENM;4p3v(M-D) + R + C + ENM"
  local s
  for s in "${SCENES[@]}"; do
    cam_done "$s" || { log "killA: skip $s (triplets not finished)"; continue; }
    run_evalf "$TRIP/$s" "$FEAT" "" || true                      # 6p3v and the plain rows
    run_evalf "$TRIP/$s" "$FEAT" killA --exps "$exps" || true    # the refitted rows
  done
  "$PY" scripts/kill_test_a.py "$TV/results" --feat "$FEAT" | tee "$OUT/killA.txt"
}

step_killB() {
  local n=${NSHARDS:-$NW} kb=$ROOT/results/killB files=() pids
  mkdir -p "$kb"
  for s in "${SCENES[@]}"; do
    cam_done "$s" || { log "killB: skip $s (triplets not finished)"; continue; }
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

step_requeue() {
  # Results computed before the OOB fix (every '+ R' row used an undefined fifth point) are moved aside so the
  # next run recomputes them: eval_f.py / eval.py results, kill test A, the control row.
  local dst=$TV/results/before_oob_fix_$(date +%Y%m%d_%H%M)
  mkdir -p "$dst"
  mv "$TV"/results/focal_*.json "$TV"/results/kill_test_a-*.json "$TV"/results/*-control-*.json "$dst/" 2>/dev/null
  rm -f "$OUT/control.done" "$OUT/killA.txt"
  log "requeue: moved $(ls "$dst" | wc -l) result files to $dst; evalf, killA and control will rerun"
}

step_crashdebug() {
  # Replay up to CRASH_N saved crashing tasks under gdb (native backtrace) and summarize all crash logs.
  local rep=$OUT/crash_report.txt n=0 item
  {
    echo "== crash logs ($(date '+%F %T'))"
    cat "$OUT"/crashes/*/crashes.jsonl 2>/dev/null | cut -c1-400 || echo "no crashes logged"
    for item in "$OUT"/crashes/*/item_*.pkl; do
      [[ -f $item ]] || continue
      (( n++ < ${CRASH_N:-3} )) || break
      echo; echo "== replay $item"
      ( cd "$TV" && PYTHONPATH="$PWD" timeout 600 "$PY" -W ignore "$ROOT/scripts/poselib_crash_repro.py" \
          $(command -v gdb >/dev/null && echo --gdb) "$item" ) 2>&1 | tail -60
    done
  } >"$rep" 2>&1
  log "crash report: $rep ($(cat "$OUT"/crashes/*/crashes.jsonl 2>/dev/null | wc -l) crashing tasks logged)"
}

step_seq() {
  # Task 2.9: the sequential baseline ('6p3v + SEQ': six-point LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3,
  # three-view refinement) through eval_f.py next to 6pt+P3P, SP+LG and SIFT, every finished Cambridge scene.
  fork_current || { log "seq: the fork lacks the sequential baseline (see setup); skipped"; return; }
  local s f
  for s in "${SCENES[@]}"; do
    cam_done "$s" || continue
    for f in "$FEAT" "$SIFT"; do
      [[ -f $TRIP/$s/$f.txt ]] && { run_evalf "$TRIP/$s" "$f" seq --exps "6p3v + SEQ" || true; }
    done
  done
  { "$PY" scripts/compare_tzamos_focal.py "$TV/results" --feat "$FEAT" --tag seq
    "$PY" scripts/compare_tzamos_focal.py "$TV/results" --feat "$FEAT"; } 2>&1 | tee "$OUT/seq.txt"
}

step_control() {
  [[ -f $OUT/control.done ]] && { log "control row already done"; return; }
  "${ONE_THREAD[@]}" bash scripts/run_tzamos_table.sh --exps "5p3v + R + C" --tag control >"$OUT/control.log" 2>&1 \
    && touch "$OUT/control.done"
  log "control row done (see $OUT/control.log)"
}

step_compare() {
  { "$PY" scripts/compare_tzamos_focal.py "$TV/results" --feat "$FEAT"
    "$PY" scripts/compare_tzamos_focal.py "$TV/results" --feat "$SIFT"; } >"$OUT/compare_focal.txt" 2>&1
  log "pooled shared-focal tables: $OUT/compare_focal.txt"
}

step_thresh() {
  "${ONE_THREAD[@]}" bash scripts/run_tzamos_table.sh --table -t 1.0 >"$OUT/thresh1.log" 2>&1
  log "threshold 1.0 table done (see $OUT/thresh1.log)"
}

step_runtime() {
  bash scripts/runtime_single_core.sh >"$OUT/runtime.log" 2>&1
  log "single-core runtime done (see $OUT/runtime.log and results/runtime_1core_$(hostname -s).txt)"
}

step_collect() {
  local dst=$SSD/abl_dell_results
  mkdir -p "$dst"
  cp -r "$OUT" "$dst/" 2>/dev/null
  cp -r "$ROOT/results/killB" "$dst/" 2>/dev/null
  cp "$TV"/results/focal_*.json "$TV"/results/kill_test_a-*.json "$TV"/results/*-control-*.json "$ROOT"/results/runtime_1core_*.txt "$dst/" 2>/dev/null
  # Flush to the SSD before saying it is done: on 2026-10-23 the SSD was unplugged right after a copy and all
  # 669 copied files arrived empty (data still in the write cache). Then check that nothing came out empty.
  sync -f "$dst" 2>/dev/null || sync
  local empty
  empty=$(find "$dst" -type f -size 0 ! -name control.done ! -name runner.pid 2>/dev/null | wc -l)
  log "copied results to $dst and flushed to disk ($empty empty files); eject the SSD before unplugging it"
}

step_status() {
  echo "== $(date '+%F %T')  SSD: $SSD"
  local s
  for s in "${SCENES[@]}"; do
    printf '%-14s SP+LG %5s  SIFT %5s  evalf %-4s  killB shards %s\n' "$s" "$(nlines "$TRIP/$s/$FEAT.txt")" \
      "$(nlines "$TRIP/$s/$SIFT.txt")" "$([[ -f $TV/results/focal_$s-$FEAT.json ]] && echo done || echo -)" \
      "$(ls "$ROOT/results/killB/${s}_shard"*_summary.json 2>/dev/null | wc -l)"
  done
  local n_eth=0 n_trip=0
  for s in "${ETH_SCENES[@]}"; do
    eth_done "$s" && { n_eth=$((n_eth + 1)); n_trip=$((n_trip + $(nlines "$ETRIP/$s/$FEAT.txt"))); }
  done
  echo "ETH3D: $n_eth/${#ETH_SCENES[@]} scenes, $n_trip same-camera triplets"
  echo "control row: $([[ -f $OUT/control.done ]] && echo done || echo -)   poselib crashes logged:" \
       "$(cat "$OUT"/crashes/*/crashes.jsonl 2>/dev/null | wc -l)"
  local last newest=""
  for last in "$OUT/triplets.log" "$OUT"/evalf_*.log "$OUT/eth3d.log"; do   # progress bar of the newest job
    [[ -f $last && ( -z $newest || $last -nt $newest ) ]] && newest=$last
  done
  [[ -n $newest ]] && echo "$(basename "$newest"): $(tail -c 400 "$newest" | tr '\r' '\n' | grep -a -v '^\s*$' | tail -1)"
  for r in 8 9; do echo "monodromy rng$r: $(tail -1 "$OUT/monodromy_rng$r.log" 2>/dev/null)"; done
  [[ -f $OUT/killB.txt ]] && tail -1 "$OUT/killB.txt"
  [[ -f $OUT/killA.txt ]] && grep -a "KILL TEST A\|WARNING" "$OUT/killA.txt"
  [[ -f $OUT/seq.txt ]] && grep -a -E "^(6p3v|6p3v \+ SEQ) " "$OUT/seq.txt" | sed "s/^/Task 2.9: /"
  echo "== last log lines"; tail -4 "$OUT/run.log" 2>/dev/null
  if [[ -f $OUT/runner.pid ]] && kill -0 "$(cat "$OUT/runner.pid")" 2>/dev/null; then
    echo "runner: RUNNING"
  else
    echo "runner: not running"
  fi
}

STEPS=("$@")
(( ${#STEPS[@]} )) || STEPS=(setup machine monodromy triplets sift evalf killB killA seq control eth3d sift evalf compare crashdebug collect)
for st in "${STEPS[@]}"; do
  declare -F "step_$st" >/dev/null || die "unknown step: $st"
  [[ $st == status ]] || log "== $st"
  "step_$st"
done
if [[ " ${STEPS[*]} " == *" monodromy "* ]]; then
  log "waiting for monodromy"; wait; step_collect
fi
[[ ${STEPS[*]} == status ]] || log "all requested steps finished"
