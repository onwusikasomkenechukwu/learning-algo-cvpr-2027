#!/usr/bin/env bash
# Task 1.3 machine sheet (student instructions v5) for the timing server, as Markdown: CPU model, processors,
# cores, threads, clocks, memory per processor, disk, OS, AVX/FMA, governor, turbo, SMT, compiler and Python
# versions, a proposed timing core with its pinning command, and the questions for the administrator.
# Read-only: changes no setting.
#   bash scripts/machine_sheet.sh                          # writes results/abl_dell/machine_sheet.md and prints it
#   bash scripts/machine_sheet.sh OUT.md /path/to/SSD/learning-algo-cvpr
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
OUTF=${1:-$ROOT/results/abl_dell/machine_sheet.md}
SSD=${2:-/media/$USER/SSD/learning-algo-cvpr}
PY=${PY:-$ROOT/.venv/bin/python}
mkdir -p "$(dirname "$OUTF")"

lsv() { lscpu | awk -F: -v k="$1" '$1 == k { sub(/^[ \t]+/, "", $2); print $2; exit }'; }
rd() { [[ -r $1 ]] && cat "$1" || echo "n/a"; }

model=$(lsv "Model name"); sockets=$(lsv "Socket(s)"); cps=$(lsv "Core(s) per socket")
tpc=$(lsv "Thread(s) per core"); ncpu=$(lsv "CPU(s)"); maxmhz=$(lsv "CPU max MHz"); minmhz=$(lsv "CPU min MHz")
nnodes=$(lsv "NUMA node(s)")
base=n/a
if [[ -r /sys/devices/system/cpu/cpu0/cpufreq/base_frequency ]]; then
  base="$(( $(cat /sys/devices/system/cpu/cpu0/cpufreq/base_frequency) / 1000 )) MHz"
elif [[ $model =~ @\ *([0-9.]+GHz) ]]; then
  base=${BASH_REMATCH[1]}
fi
if [[ -r /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
  turbo=$([[ $(cat /sys/devices/system/cpu/intel_pstate/no_turbo) == 0 ]] && echo "on (intel_pstate)" || echo "off (intel_pstate)")
elif [[ -r /sys/devices/system/cpu/cpufreq/boost ]]; then
  turbo=$([[ $(cat /sys/devices/system/cpu/cpufreq/boost) == 1 ]] && echo on || echo off)
else
  turbo="unknown (no intel_pstate/no_turbo or cpufreq/boost)"
fi
gov=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort | uniq -c | awk '{printf "%s%s x%s", (NR>1?", ":""), $2, $1}')
drv=$(rd /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver)
smt="active=$(rd /sys/devices/system/cpu/smt/active), control=$(rd /sys/devices/system/cpu/smt/control)"
flags=$(grep -m1 '^flags' /proc/cpuinfo)
isa=""
for f in avx avx2 fma avx512f; do
  [[ " $flags " == *" $f "* ]] && isa+="$f yes, " || isa+="$f NO, "
done
isa=${isa%, }
memtot=$(free -g | awk '/^Mem:/ {print $2 " GB total, " $7 " GB available"}')
pernode=""
for d in /sys/devices/system/node/node[0-9]*; do
  [[ -d $d ]] || continue
  n=${d##*node}
  gb=$(awk '/MemTotal/ {printf "%.0f", $4 / 1048576}' "$d/meminfo")
  pernode+="node $n: ${gb} GB, CPUs $(cat "$d/cpulist"); "
done
pernode=${pernode%; }
os=$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"); kern=$(uname -r)
disk_home=$(df -h --output=avail,size "$HOME" | tail -1 | awk '{print $1 " free of " $2}')
disk_ssd=$( [[ -d $SSD ]] && df -h --output=avail,size "$SSD" | tail -1 | awk '{print $1 " free of " $2}' || echo "not mounted")
gccv=$(gcc --version 2>/dev/null | head -1); gxxv=$(g++ --version 2>/dev/null | head -1)
cmakev=$(cmake --version 2>/dev/null | head -1)
pyv=$("$PY" -c "
import platform, importlib
out = ['Python ' + platform.python_version()]
for m in ('numpy', 'scipy', 'torch', 'cv2', 'h5py', 'poselib', 'lightglue'):
    try:
        out.append(m + ' ' + str(getattr(importlib.import_module(m), '__version__', 'installed')))
    except Exception:
        out.append(m + ' MISSING')
print(', '.join(out))" 2>/dev/null || echo "python env not found at $PY")
commit=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null)
fork=$(grep -o 'PoseLib@[0-9a-f]*\|PoseLib-[0-9a-f]\{7\}' scripts/build_offline_bundle.sh 2>/dev/null | head -1)

# Timing core: the second physical core of node 0 (core 0 takes most interrupts); its sibling threads stay idle.
topo=$(lscpu -p=CPU,CORE,SOCKET,NODE | grep -v '^#')
tcore=$(echo "$topo" | awk -F, '$4 == 0 {print $2}' | sort -n -u | sed -n 2p)
tcpus=$(echo "$topo" | awk -F, -v c="$tcore" '$2 == c {print $1}' | paste -sd, -)
tcpu=${tcpus%%,*}
tnode=$(echo "$topo" | awk -F, -v c="$tcore" '$2 == c {print $4; exit}')
numactl_ok=$(command -v numactl >/dev/null && echo yes || echo "no (sudo apt install numactl)")

cat >"$OUTF" <<EOF
# Machine sheet: $(hostname) (Task 1.3)

Generated $(date '+%F %T') by scripts/machine_sheet.sh (read-only), repo commit $commit.

## Hardware
| Item | Value |
|---|---|
| CPU model | $model |
| Processors (sockets) | $sockets |
| Physical cores | $cps per socket, $(( ${sockets:-0} * ${cps:-0} )) total |
| Hardware threads | $tpc per core, $ncpu total |
| Base clock | $base |
| Max (turbo) clock | ${maxmhz:-n/a} MHz (min ${minmhz:-n/a} MHz) |
| NUMA nodes | $nnodes |
| Memory | $memtot |
| Memory per processor | $pernode |
| Free disk | home: $disk_home; SSD: $disk_ssd |
| Operating system | $os, kernel $kern |
| GPU | $(lspci 2>/dev/null | grep -i -E 'vga|3d|display' | sed 's/^[^ ]* //' | paste -sd ';' - | cut -c1-120) |

## Instruction sets (Hruby et al.'s HC solver is compiled with AVX and FMA)
$isa

## Frequency and threading (current state)
| Item | Value |
|---|---|
| Frequency driver | $drv |
| Governor | ${gov:-n/a} |
| Turbo boost | $turbo |
| Simultaneous multithreading | $smt |

## Proposed timing core
- Physical core **$tcore** on NUMA node **$tnode**, hardware threads **$tcpus**. Time on CPU $tcpu only and keep
  the other thread(s) of this core idle during timing runs.
- Pinning: \`taskset -c $tcpu numactl --membind=$tnode --physcpubind=$tcpu <command>\` (numactl installed: $numactl_ok),
  with OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1.

## Questions for the administrator (fill in the answers)
| Question | Current | Answer |
|---|---|---|
| Can the governor be set to performance? | ${gov:-n/a} | |
| Can turbo boost be turned off? | $turbo | |
| Can SMT be turned off (or must sibling threads stay idle)? | $smt | |

## Timing window
Proposed: every night 22:00-06:00, nothing else runs (to agree with the team and Dr. Aryal, then book it in the
team sheet). Agreed: ______

## Software (one version for the whole team)
- Compiler: $gccv; $gxxv; $cmakev
- Python env ($PY): $pyv
- PoseLib fork pin: ${fork:-see scripts/build_offline_bundle.sh}

## Folder layout
- Repository: $ROOT (code, scripts, results/ for result files and logs)
- Data: $ROOT/data/<dataset> links to the SSD ($SSD/data); Cambridge triplets in $SSD/data/cambridge_triplets
- Seed code builds: $ROOT/third_party (PoseLib fork, threeview, learning_minimal, superansac)
- Results copied for the laptop: $SSD/abl_dell_results
EOF
cat "$OUTF"
