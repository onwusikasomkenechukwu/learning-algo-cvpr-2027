#!/usr/bin/env bash
# Run on an ONLINE machine. Downloads everything the offline cluster needs to install:
#   wheelhouse/*.whl            Linux x86_64 wheels for each Python version
#   wheelhouse/tools/uv         standalone uv binary (makes venvs without python3-venv/ensurepip)
# Usage: bash scripts/build_wheelhouse.sh [python_versions...]   (default: 3.10 ... 3.14)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
UV_VERSION=${UV_VERSION:-0.13.1}
REQ_DIR=$(mktemp -d); trap 'rm -rf "$REQ_DIR"' EXIT
VERSIONS=("$@"); [[ ${#VERSIONS[@]} -gt 0 ]] || VERSIONS=(3.10 3.11 3.12 3.13 3.14)
mkdir -p wheelhouse/tools
for v in "${VERSIONS[@]}"; do
  echo "== Python $v"
  "$PY" scripts/resolve_markers.py "$v" requirements.lock > "$REQ_DIR/req-$v.txt"
  "$PY" -m pip download -r "$REQ_DIR/req-$v.txt" -d wheelhouse \
    --only-binary=:all: --implementation cp --python-version "$v" \
    --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64
done
url=https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz
curl -fsSL "$url" -o wheelhouse/tools/uv.tar.gz
curl -fsSL "$url.sha256" -o wheelhouse/tools/uv.tar.gz.sha256
(cd wheelhouse/tools && echo "$(cut -d' ' -f1 uv.tar.gz.sha256)  uv.tar.gz" | sha256sum -c -)
tar -xzf wheelhouse/tools/uv.tar.gz -C wheelhouse/tools --strip-components=1
ls -lh wheelhouse wheelhouse/tools
