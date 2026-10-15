#!/usr/bin/env bash
# Remaining datasets from Datasets.pdf, in priority order (sizes/MD5s read from the hosts on 2026-10-15):
#   1. Cambridge Landmarks, 5 scenes used by Tzamos et al. (Street excluded)      26.5 GB  MD5-checked
#   2. PhotoTourism / IMC 2020 full scene archives (train, val, test) + bundles     85.1 GB  size-checked
#   3. CVPR 2020 RANSAC tutorial PnP + homography packs                              1.4 GB  size-checked
#   4. CVPR 2020 RANSAC tutorial epipolar training pack (largest, last)             92.1 GB  size-checked
# Not included: LaMAR (access form), Aachen aachen.db, ETH3D raw/distorted images (unused by the seed papers).
# Cambridge sizes are pinned: HEAD on its download links returns a redirect page, not the zip size.
# Resumable: re-run to continue partial files; complete files are skipped.
# Usage: bash scripts/download_tier2.sh [raw_root]   (default: data/raw, a junction to the SSD)
# ONLY=<regex> limits a run to entries whose "folder/file" matches, so different hosts can download in
# parallel without two processes ever touching the same file, e.g.
#   ONLY=phototourism    bash scripts/download_tier2.sh &
#   ONLY=ransac_tutorial bash scripts/download_tier2.sh &
# Each filtered run logs to download_tier2_<TAG>.log (TAG defaults to ONLY with symbols replaced). DRY_RUN=1 lists the selection only.
set -u
ROOT="${1:-$(dirname "$0")/../data/raw}"
ONLY="${ONLY:-}"
TAG="${TAG:-$(printf %s "$ONLY" | tr -c "A-Za-z0-9_" "_")}"
LOG="$ROOT/download_tier2${TAG:+_$TAG}.log"
mkdir -p "$ROOT"

CAM=https://www.repository.cam.ac.uk/bitstreams
IMC=https://www.cs.ubc.ca/research/kmyi_data/imw2020
TUT=http://cmp.felk.cvut.cz/~mishkdmy/CVPR-RANSAC-Tutorial-2020

# dir|url|output name|expected bytes|md5 (optional)
FILES=(
  "cambridge|$CAM/1cd2b04b-ada9-4841-8023-8207f1f3519b/download|KingsCollege.zip|6051902618|6639105c5edb2de826b29fa87975c305"
  "cambridge|$CAM/ae577bfb-bdce-488c-8ce6-3765eabe420e/download|OldHospital.zip|5050655612|882ecbf7a89d4c0c72d21fe744b74f63"
  "cambridge|$CAM/4e5c67dd-9497-4a1d-add4-fd0e00bcb8cb/download|ShopFacade.zip|1357125530|c786c0c12a83a439ae430d68cc18b0dc"
  "cambridge|$CAM/2559ba20-c4d1-4295-b77f-183f580dbc56/download|StMarysChurch.zip|7387128866|69c896779a7f909638ff5e519e2d2a7a"
  "cambridge|$CAM/bceda7ac-e51c-40ca-b9d7-d758d40cdcf4/download|GreatCourt.zip|6678049207|95c35929d9194baed37a5adb5e5f40d1"
)
for s in british_museum florence_cathedral_side lincoln_memorial_statue milan_cathedral mount_rushmore \
         piazza_san_marco sagrada_familia st_pauls_cathedral; do
  FILES+=("phototourism/test|$IMC/TestData/$s.tar.gz|$s.tar.gz||")
done
for s in reichstag sacre_coeur st_peters_square brandenburg_gate buckingham_palace colosseum_exterior \
         grand_place_brussels notre_dame_front_facade palace_of_westminster pantheon_exterior taj_mahal \
         temple_nara_japan trevi_fountain; do
  FILES+=("phototourism/train|$IMC/TrainingData/$s.tar.gz|$s.tar.gz||")
done
FILES+=(
  "phototourism|$IMC/ValidationData/imw2020-valid.tar.gz|imw2020-valid.tar.gz||"
  "phototourism|$IMC/TestData/imw2020-test.tar.gz|imw2020-test.tar.gz||"
  "ransac_tutorial|$TUT/RANSAC-Tutorial-Data-PnP.tar.gz|RANSAC-Tutorial-Data-PnP.tar.gz||"
  "ransac_tutorial|$TUT/homography.tar.gz|homography.tar.gz||"
  "ransac_tutorial|$TUT/RANSAC-Tutorial-Data-EF.tar|RANSAC-Tutorial-Data-EF.tar||"
)

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
remote_size() { curl -sIL -m 60 "$1" | grep -i '^content-length' | tail -1 | tr -dc 0-9; }

status=0
for entry in "${FILES[@]}"; do
  IFS='|' read -r dir url name size md5 <<<"$entry"
  [[ -z "$ONLY" || "$dir/$name" =~ $ONLY ]] || continue
  if [[ -n "${DRY_RUN:-}" ]]; then echo "would get $dir/$name"; continue; fi
  out="$ROOT/$dir/$name"; mkdir -p "$ROOT/$dir"
  [[ -n "$size" ]] || size=$(remote_size "$url")
  if [[ -f "$out.ok" ]]; then log "SKIP $dir/$name (verified earlier)"; continue; fi
  for attempt in 1 2 3 4 5; do
    log "GET  $dir/$name (${size:-?} bytes, attempt $attempt)"
    curl -fsSL --retry 5 --retry-delay 10 -C - -o "$out" "$url" && break
    sleep 20
  done
  got=$(stat -c %s "$out" 2>/dev/null || echo 0)
  if [[ -n "$size" && "$got" -ne "$size" ]]; then log "FAIL $dir/$name: $got of $size bytes"; status=1; continue; fi
  if [[ -n "$md5" ]]; then
    have=$(md5sum "$out" | cut -d' ' -f1)
    if [[ "$have" != "$md5" ]]; then log "FAIL $dir/$name: md5 $have != $md5"; status=1; continue; fi
  fi
  touch "$out.ok"
  log "DONE $dir/$name ($got bytes${md5:+, md5 ok})"
done
log "finished with status $status"
exit $status
