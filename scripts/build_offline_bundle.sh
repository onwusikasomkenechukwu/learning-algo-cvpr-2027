#!/usr/bin/env bash
# Run on an ONLINE machine. Fetches everything beyond the baseline wheelhouse that the
# offline cluster needs, pinned to exact versions/commits:
#   wheelhouse/gpu/      PyTorch 2.14.1 (CUDA 12.6) + torchvision, kornia, matplotlib wheels (Python 3.14)
#   wheelhouse/build/    cmake, ninja, pybind11, scikit-build-core, setuptools, wheel (build tools)
#   wheelhouse/src/      source tarballs: LightGlue, threeview, PoseLib@threeview (+pybind11),
#                        learning_minimal, superansac, Eigen 3.4.0
#   wheelhouse/weights/  SuperPoint / ALIKED / LightGlue weights (torch hub checkpoint names)
#   data/raw/tzamos/     Tzamos et al. CVPR 2025 extracted triplets (Zenodo 16603086)
#   papers/              seed papers from arXiv
# Re-running skips files that are already complete.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
mkdir -p wheelhouse/{gpu,build,src,weights} data/raw/tzamos papers

fetch() {  # fetch <url> <out> : skip if present and non-empty
  [[ -s "$2" ]] && { echo "have $2"; return; }
  echo "get  $2"; curl -fL --retry 5 -C - -o "$2.part" "$1" && mv "$2.part" "$2"
}

echo "== GPU wheels"
"$PY" -m pip download --no-deps -r requirements-gpu.lock -d wheelhouse/gpu \
  --only-binary=:all: --implementation cp --python-version 3.14 \
  --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 \
  --platform manylinux_2_18_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu126

echo "== build tools"
"$PY" -m pip download -d wheelhouse/build --only-binary=:all: --implementation cp --python-version 3.14 \
  --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
  cmake==4.4.4 ninja==1.13.2 pybind11==3.1.0 scikit-build-core==1.1.1 setuptools==84.0.0 wheel==0.48.0

echo "== sources (pinned commits)"
gh_src() { fetch "https://github.com/$1/archive/$2.tar.gz" "wheelhouse/src/$(basename "$1")-$2.tar.gz"; }
gh_src cvg/LightGlue                eb42fee2d71449efb0aa5c10549752b5d75384d8
gh_src kocurvik/threeview           b43383efba129b8d90e2709092dac6dc87cbbea1
gh_src kocurvik/PoseLib             272ce27dc3b6f44637c3bdea7ff460f06cb538d6   # branch threeview
gh_src pybind/pybind11              a34596bfe1947b4a6b0bcc4218e1f72d0c2e9b4c   # PoseLib submodule
gh_src petrhruby97/learning_minimal 9d7739bccb1b0978c70a2e643378a53d531e3a3f
gh_src danini/superansac            27de48676f07704856fb5619dd31cde807d0661d
fetch https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz wheelhouse/src/eigen-3.4.0.tar.gz

echo "== weights (names match torch hub cache files LightGlue expects)"
LG=https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv
fetch $LG/superpoint_v1.pth          wheelhouse/weights/superpoint_v1.pth
for w in superpoint_lightglue aliked_lightglue sift_lightglue; do
  fetch "$LG/$w.pth" "wheelhouse/weights/${w}_v0-1_arxiv.pth"
done
fetch https://github.com/Shiaoming/ALIKED/raw/main/models/aliked-n16.pth wheelhouse/weights/aliked-n16.pth

echo "== Tzamos triplets (Zenodo, md5-checked)"
"$PY" - <<'EOF'
import hashlib, json, os, subprocess, urllib.request
rec = json.load(urllib.request.urlopen(urllib.request.Request(
    "https://zenodo.org/api/records/16603086", headers={"Accept": "application/json"}), timeout=60))
for f in rec["files"]:
    out = os.path.join("data/raw/tzamos", f["key"])
    algo, want = f["checksum"].split(":")
    if not (os.path.exists(out) and os.path.getsize(out) == f["size"]):
        subprocess.run(["curl", "-fL", "--retry", "5", "-C", "-", "-o", out, f["links"]["self"]], check=True)
    h = hashlib.new(algo)
    with open(out, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == want, f"checksum mismatch for {out}"
    print(f"ok   {out} ({f['size']} bytes, {algo} verified)")
EOF

echo "== papers (arXiv)"
fetch https://arxiv.org/pdf/2112.03424v1 papers/hruby2022_learning_to_solve_hard_minimal_problems.pdf
fetch https://arxiv.org/pdf/2303.16078v5 papers/tzamos2025_relative_pose_three_calibrated_cameras.pdf
fetch https://arxiv.org/pdf/2506.04803v1 papers/barath2025_superansac.pdf

du -sh wheelhouse/gpu wheelhouse/build wheelhouse/src wheelhouse/weights data/raw/tzamos papers
