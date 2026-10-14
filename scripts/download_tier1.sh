#!/usr/bin/env bash
# Tier 1 dataset downloads for the CVPR RANSAC project.
# Resumable: re-run the script and curl continues partial files (-C -).
# Usage: bash scripts/download_tier1.sh [data_root]   (default: ./data/raw)
set -u

ROOT="${1:-$(dirname "$0")/../data/raw}"
LOG="$ROOT/download.log"
mkdir -p "$ROOT"

RANSAC=http://cmp.felk.cvut.cz/~mishkdmy/CVPR-RANSAC-Tutorial-2020
ETH3D=https://www.eth3d.net/data
AACHEN=https://data.ciirc.cvut.cz/public/projects/2020VisualLocalization/Aachen-Day-Night

# dir|url|expected_bytes  (sizes from Content-Length on 2026-10-14)
FILES=(
  "ransac_tutorial|$RANSAC/RANSAC-Tutorial-Data-ValOnly.tar|2206976000"
  "ransac_tutorial|$RANSAC/RANSAC-Tutorial-Data-EF-Test.tar|4136847360"
  "eth3d|$ETH3D/multi_view_training_dslr_undistorted.7z|5887406146"
  "eth3d|$ETH3D/multi_view_training_dslr_scan_eval.7z|1920731473"
  "aachen_v1_1|$AACHEN/aachen_v1_1.zip|4190982935"
  "aachen_v1_1|$AACHEN/images/database_and_query_images.zip|2687366300"
  "aachen_v1_1|$AACHEN/README_Aachen-Day-Night_v1_1.md|"
  "aachen_v1_1|$AACHEN/queries/day_time_queries_with_intrinsics.txt|"
  "aachen_v1_1|$AACHEN/queries/night_time_queries_with_intrinsics.txt|"
)

status=0
for entry in "${FILES[@]}"; do
  IFS='|' read -r dir url size <<<"$entry"
  out="$ROOT/$dir/$(basename "$url")"
  mkdir -p "$ROOT/$dir"
  if [[ -s "$out" && ( -z "$size" || $(stat -c %s "$out") -eq $size ) ]]; then
    echo "$(date '+%F %T') SKIP $out (complete)" | tee -a "$LOG"; continue
  fi
  echo "$(date '+%F %T') GET  $url" | tee -a "$LOG"
  for attempt in 1 2 3 4 5; do
    curl -fL --retry 5 --retry-delay 10 -C - -o "$out" "$url" && break
    echo "$(date '+%F %T') retry $attempt for $url" | tee -a "$LOG"; sleep 15
  done
  got=$(stat -c %s "$out" 2>/dev/null || echo 0)
  if [[ -n "$size" && $got -ne $size ]]; then
    echo "$(date '+%F %T') FAIL $out: $got of $size bytes" | tee -a "$LOG"; status=1
  else
    echo "$(date '+%F %T') DONE $out ($got bytes)" | tee -a "$LOG"
  fi
done
exit $status
