# Machine sheet: abl-dell (Task 1.3)

Generated 2026-10-28 11:28:48 by scripts/machine_sheet.sh (read-only), repo commit 068571c.

## Hardware
| Item | Value |
|---|---|
| CPU model | Intel(R) Xeon(R) Gold 6240R CPU @ 2.40GHz |
| Processors (sockets) | 2 |
| Physical cores | 24 per socket, 48 total |
| Hardware threads | 2 per core, 96 total |
| Base clock | 2.40GHz |
| Max (turbo) clock | n/a MHz (min n/a MHz) |
| NUMA nodes | 2 |
| Memory | 754 GB total, 737 GB available |
| Memory per processor | node 0: 377 GB, CPUs 0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,54,56,58,60,62,64,66,68,70,72,74,76,78,80,82,84,86,88,90,92,94; node 1: 378 GB, CPUs 1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47,49,51,53,55,57,59,61,63,65,67,69,71,73,75,77,79,81,83,85,87,89,91,93,95 |
| Free disk | home: 213G free of 1.8T; SSD: 18G free of 466G |
| Operating system | Ubuntu 24.04.2 LTS, kernel 7.0.0-28-generic |
| GPU | VGA compatible controller: Matrox Electronics Systems Ltd. Integrated Matrox G200eW3 Graphics Controller (rev 04) |

## Instruction sets (Hruby et al.'s HC solver is compiled with AVX and FMA)
avx yes, avx2 yes, fma yes, avx512f yes

## Frequency and threading (current state)
| Item | Value |
|---|---|
| Frequency driver | n/a |
| Governor | n/a |
| Turbo boost | unknown (no intel_pstate/no_turbo or cpufreq/boost) |
| Simultaneous multithreading | active=1, control=on |

## Proposed timing core
- Physical core **2** on NUMA node **0**, hardware threads **2,50**. Time on CPU 2 only and keep
  the other thread(s) of this core idle during timing runs.
- Pinning: `taskset -c 2 numactl --membind=0 --physcpubind=2 <command>` (numactl installed: yes),
  with OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1.

## Questions for the administrator (fill in the answers)
| Question | Current | Answer |
|---|---|---|
| Can the governor be set to performance? | n/a | |
| Can turbo boost be turned off? | unknown (no intel_pstate/no_turbo or cpufreq/boost) | |
| Can SMT be turned off (or must sibling threads stay idle)? | active=1, control=on | |

## Timing window
Proposed: every night 22:00-06:00, nothing else runs (to agree with the team and Dr. Aryal, then book it in the
team sheet). Agreed: ______

## Software (one version for the whole team)
- Compiler: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; cmake version 4.4.4
- Python env (/home/abl-dell/learning-algo/.venv/bin/python): Python 3.12.15, numpy 2.3.5, scipy 1.18.1, torch 2.14.1+cpu, cv2 5.0.0, h5py 3.16.0, poselib 2.0.1, lightglue installed
- PoseLib fork pin: PoseLib@

## Folder layout
- Repository: /home/abl-dell/learning-algo (code, scripts, results/ for result files and logs)
- Data: /home/abl-dell/learning-algo/data/<dataset> links to the SSD (/media/abl-dell/SSD/learning-algo-cvpr/data); Cambridge triplets in /media/abl-dell/SSD/learning-algo-cvpr/data/cambridge_triplets
- Seed code builds: /home/abl-dell/learning-algo/third_party (PoseLib fork, threeview, learning_minimal, superansac)
- Results copied for the laptop: /media/abl-dell/SSD/learning-algo-cvpr/abl_dell_results
