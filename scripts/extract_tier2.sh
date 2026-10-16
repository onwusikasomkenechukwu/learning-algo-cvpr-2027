#!/usr/bin/env bash
# Unpack the tier-2 archives from data/raw into data/<dataset>/, keeping the archives.
#   raw/cambridge/*.zip                 -> data/cambridge/<Scene>/
#   raw/phototourism/{test,train}/*.tgz -> data/phototourism/<scene>/
#   raw/phototourism/imw2020-*.tar.gz   -> data/phototourism/{imw2020-valid,imw-2020-test}/
#   raw/ransac_tutorial/homography      -> data/ransac_tutorial/homography/
#   raw/ransac_tutorial/...-PnP         -> data/ransac_tutorial/pnp/   (archive has loose top-level files)
# The 92 GB RANSAC-Tutorial-Data-EF.tar is NOT unpacked here (uncompressed tar; unpack on the cluster).
# Only archives with a .ok marker (verified download) are unpacked. Before each archive the free space
# is checked against its expected unpacked size (exact for zip, 2.1x the archive for tar.gz) and the
# run stops if less than MIN_FREE_GB (default 20) would remain. Re-running skips finished archives.
# Usage: bash scripts/extract_tier2.sh [data_root]   (default: data, whose subfolders are SSD junctions)
set -u
DATA="${1:-$(dirname "$0")/../data}"
RAW="$DATA/raw"
MIN_FREE_GB=${MIN_FREE_GB:-20}
LOG="$RAW/extract_tier2.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
free_bytes() { df -B1 --output=avail "$DATA/" | tail -1 | tr -dc 0-9; }

# archive (relative to raw) | destination (relative to data)
JOBS=()
for z in "$RAW"/cambridge/*.zip; do JOBS+=("${z#$RAW/}|cambridge"); done
for t in "$RAW"/phototourism/test/*.tar.gz "$RAW"/phototourism/train/*.tar.gz "$RAW"/phototourism/imw*.tar.gz; do
  JOBS+=("${t#$RAW/}|phototourism")
done
JOBS+=("ransac_tutorial/homography.tar.gz|ransac_tutorial" "ransac_tutorial/RANSAC-Tutorial-Data-PnP.tar.gz|ransac_tutorial/pnp")

status=0
for job in "${JOBS[@]}"; do
  IFS='|' read -r rel dest <<<"$job"
  src="$RAW/$rel"; out="$DATA/$dest"; marker="$out/.extracted_$(basename "$rel")"
  [[ -f "$marker" ]] && { log "SKIP $rel (already unpacked)"; continue; }
  [[ -f "$src.ok" ]] || { log "SKIP $rel (no verified download)"; continue; }
  if [[ "$src" == *.zip ]]; then need=$(unzip -l "$src" | tail -1 | awk '{print $1}')
  else need=$(( $(stat -c %s "$src") * 21 / 10 )); fi
  avail=$(free_bytes)
  if (( avail - need < MIN_FREE_GB * 1000000000 )); then
    log "STOP before $rel: needs ~$((need/1000000000)) GB, $((avail/1000000000)) GB free, floor $MIN_FREE_GB GB"; status=2; break
  fi
  mkdir -p "$out"
  log "UNPACK $rel -> $dest (~$((need/1000000000)) GB)"
  if [[ "$src" == *.zip ]]; then unzip -q -o "$src" -d "$out"; rc=$?
  else tar -xzf "$src" -C "$out"; rc=$?; fi
  if (( rc != 0 )); then log "FAIL $rel (exit $rc)"; status=1; continue; fi
  touch "$marker"
  log "DONE $rel ($((avail/1000000000 - $(free_bytes)/1000000000)) GB used, $(( $(free_bytes)/1000000000 )) GB free)"
done
log "finished with status $status"
exit $status
