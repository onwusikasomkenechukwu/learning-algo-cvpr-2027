#!/usr/bin/env bash
# Offline install of the GPU / feature-matching stack on one cluster node (after setup_node.sh).
# Installs PyTorch 2.14.1 (CUDA 12.6) + kornia + LightGlue into .venv and places the
# SuperPoint / ALIKED / LightGlue weights where torch.hub looks, so nothing is downloaded at runtime.
# NOT YET TESTED ON THE CLUSTER. Needs Python 3.14 (not 3.14.1 exactly: torchvision excludes it)
# and NVIDIA driver >= 560 for GPU use (CPU works regardless).
set -euo pipefail
cd "$(dirname "$0")/.."
UV=wheelhouse/tools/uv
PY=.venv/bin/python
"$UV" pip install --python "$PY" --offline --no-index --find-links wheelhouse/gpu -r requirements-gpu.lock

# LightGlue from the pinned source tarball; deps already installed (it asks for opencv-python,
# we use the headless build), so --no-deps.
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
tar -xzf wheelhouse/src/LightGlue-*.tar.gz -C "$tmp"
"$UV" pip install --python "$PY" --offline --no-index --no-deps --find-links wheelhouse/build "$tmp"/LightGlue-*

hub=$("$PY" -c "import torch, os; print(os.path.join(torch.hub.get_dir(), 'checkpoints'))")
mkdir -p "$hub" && cp -n wheelhouse/weights/*.pth "$hub/"
echo "weights -> $hub"

"$PY" - <<'EOF'
import torch
from lightglue import LightGlue, SuperPoint
print("torch", torch.__version__, "| CUDA available:", torch.cuda.is_available(),
      "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only")
dev = "cuda" if torch.cuda.is_available() else "cpu"
ext, matcher = SuperPoint(max_num_keypoints=2048).eval().to(dev), LightGlue(features="superpoint").eval().to(dev)
img = torch.rand(1, 1, 480, 640, device=dev)
with torch.no_grad():
    f = ext.extract(img)
    m = matcher({"image0": f, "image1": f})
print("SuperPoint+LightGlue ok:", f["keypoints"].shape[1], "keypoints,", m["matches"][0].shape[0], "self-matches")
EOF
