#!/usr/bin/env bash
# Offline environment setup on one cluster node (Ubuntu 26.04, x86_64). Run from the repo root.
# Needs only the repo + wheelhouse/ on local disk; no internet, no sudo, no python3-venv package.
# Usage: bash scripts/setup_node.sh [python]   (default: python3 on PATH)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${1:-$(command -v python3)}
UV=wheelhouse/tools/uv
chmod +x "$UV"
echo "node: $(hostname)  python: $("$PY" --version)  $(ldd --version | head -1)"
[[ -d .venv ]] || "$UV" venv --python "$PY" .venv
"$UV" pip install --python .venv/bin/python --offline --no-index --find-links wheelhouse -r requirements.lock
.venv/bin/python -c "import numpy, h5py, poselib, cv2; print('ok: numpy', numpy.__version__, 'poselib', poselib.__version__, 'cv2', cv2.__version__)"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || echo "no nvidia-smi"
