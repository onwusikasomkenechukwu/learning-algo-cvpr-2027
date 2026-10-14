#!/usr/bin/env bash
# Stream the IMC 2020 (PhotoTourism) scene archives and keep only the COLMAP camera/pose
# files (<scene>/dense/sparse/{cameras,images}.bin), which supply ground truth for the
# RANSAC tutorial test pack. Archives are not stored: ~10.6 GB is downloaded, little lands on disk.
# london_bridge and united_states_capitol have no public GT and are not covered.
# Usage: bash scripts/download_imc2020_test_gt.sh [out_dir]   (default: data/imc2020_gt)
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-data/imc2020_gt}
B=https://www.cs.ubc.ca/research/kmyi_data/imw2020
SCENES=(TrainingData/reichstag TestData/florence_cathedral_side TestData/milan_cathedral
        TestData/mount_rushmore TestData/piazza_san_marco TestData/sagrada_familia
        TestData/british_museum TestData/st_pauls_cathedral TestData/lincoln_memorial_statue)
mkdir -p "$OUT"
status=0
for s in "${SCENES[@]}"; do
  name=$(basename "$s")
  if [[ -f "$OUT/.done_$name" ]]; then echo "SKIP $name"; continue; fi
  url="$B/$s.tar.gz"
  expected=$(curl -sIL "$url" | grep -i '^content-length' | tail -1 | tr -dc 0-9)
  for attempt in 1 2 3; do
    echo "$(date '+%F %T') GET $name ($expected bytes, attempt $attempt)"
    curl -fsSL -w '%{stderr}%{size_download}' "$url" 2>"$OUT/.bytes_$name" \
      | tar -xz -C "$OUT" --wildcards "$name/dense/sparse/cameras.bin" "$name/dense/sparse/images.bin"
    got=$(tr -dc 0-9 < "$OUT/.bytes_$name")
    if [[ -n "$got" && "$got" -eq "$expected" && -f "$OUT/$name/dense/sparse/images.bin" ]]; then
      touch "$OUT/.done_$name"; rm -f "$OUT/.bytes_$name"
      echo "$(date '+%F %T') DONE $name: $(du -sh "$OUT/$name" | cut -f1) kept"
      break
    fi
    echo "$(date '+%F %T') incomplete $name (got '${got}' of $expected bytes)"; sleep 10
  done
  [[ -f "$OUT/.done_$name" ]] || status=1
done
exit $status
