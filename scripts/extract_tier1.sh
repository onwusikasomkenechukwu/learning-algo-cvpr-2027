#!/usr/bin/env bash
# Extract Tier 1 archives from data/raw into data/<dataset>/.
# Uses Windows' bsdtar (reads .tar, .zip and .7z). Skips archives already extracted.
# Usage: bash scripts/extract_tier1.sh [raw_root] [out_root]
set -u

RAW="${1:-$(dirname "$0")/../data/raw}"
OUT="${2:-$(dirname "$0")/../data}"
TAR=/c/Windows/System32/tar.exe
[[ -x "$TAR" ]] || TAR=tar

status=0
for archive in "$RAW"/*/*.tar "$RAW"/*/*.zip "$RAW"/*/*.7z; do
  [[ -f "$archive" ]] || continue
  dest="$OUT/$(basename "$(dirname "$archive")")"
  marker="$dest/.extracted_$(basename "$archive")"
  [[ -f "$marker" ]] && { echo "SKIP $archive"; continue; }
  mkdir -p "$dest"
  echo "EXTRACT $archive -> $dest"
  if "$TAR" -xf "$archive" -C "$dest"; then touch "$marker"; else echo "FAIL $archive"; status=1; fi
done
# Copy the small plain-text files (README, query intrinsics) next to the extracted data.
for f in "$RAW"/*/*.md "$RAW"/*/*.txt; do
  [[ -f "$f" ]] && cp -n "$f" "$OUT/$(basename "$(dirname "$f")")/"
done
exit $status
