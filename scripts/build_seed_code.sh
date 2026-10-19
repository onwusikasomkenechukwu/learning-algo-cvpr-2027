#!/usr/bin/env bash
# Offline build of the seed papers' code on one cluster node, from wheelhouse/src.
# Requires a C++ compiler (g++) on the node; CMake/Ninja come from wheelhouse/build, Eigen from source.
# Builds into third_party/ (not in git):
#   learning_minimal (Hruby et al. CVPR 2022): 4p3v + 5p2v binaries
#   PoseLib@threeview (Tzamos et al. CVPR 2025) as the python package `poselib` in .venv
#     (replaces upstream poselib; needs setup_node_gpu.sh first because it links libtorch)
#   threeview evaluation scripts (python, nothing to compile)
#   superansac: built only if Boost + OpenCV C++ dev packages are present (apt: libboost-dev libopencv-dev)
# NOT YET TESTED ON THE CLUSTER.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
UV=$ROOT/wheelhouse/tools/uv   # absolute: the PoseLib step runs uv from inside third_party/
PY=$ROOT/.venv/bin/python
TP=$ROOT/third_party
mkdir -p "$TP"
command -v g++ >/dev/null || { echo "ERROR: no g++ on this node; ask the admin for build-essential"; exit 1; }

"$UV" pip install --python "$PY" --offline --no-index --find-links wheelhouse/build cmake ninja pybind11 setuptools wheel
export PATH="$ROOT/.venv/bin:$PATH"   # pip-installed cmake / ninja
JOBS=$(nproc)

unpack() {  # unpack <tarball-glob> <dest-name>
  [[ -d "$TP/$2" ]] && return
  tar -xzf $1 -C "$TP" && mv "$TP"/$(tar -tzf $1 | head -1 | cut -d/ -f1) "$TP/$2"
}
unpack "wheelhouse/src/eigen-3.4.0.tar.gz" eigen
unpack "wheelhouse/src/learning_minimal-*.tar.gz" learning_minimal
unpack "wheelhouse/src/PoseLib-*.tar.gz" PoseLib-threeview
unpack "wheelhouse/src/threeview-*.tar.gz" threeview
unpack "wheelhouse/src/superansac-*.tar.gz" superansac
# PoseLib's pybind11 submodule is not in GitHub's archive; drop in the pinned copy.
if [[ ! -f "$TP/PoseLib-threeview/pybind/pybind11/CMakeLists.txt" ]]; then
  rm -rf "$TP/PoseLib-threeview/pybind/pybind11"
  tar -xzf wheelhouse/src/pybind11-*.tar.gz -C "$TP/PoseLib-threeview/pybind"
  mv "$TP"/PoseLib-threeview/pybind/pybind11-* "$TP/PoseLib-threeview/pybind/pybind11"
fi
# Eigen 3.4 is header-only but ships its CMake config only after configuring; do that once.
[[ -f "$TP/eigen/build/Eigen3Config.cmake" ]] || cmake -S "$TP/eigen" -B "$TP/eigen/build" -G Ninja >/dev/null
EIGEN_ARGS=(-DEigen3_DIR="$TP/eigen/build" -DEIGEN3_INCLUDE_DIR="$TP/eigen")
# Eigen's build-tree config reports EIGEN3_INCLUDE_DIRS as the (non-existent) install prefix
# (<repo>/include/eigen3), which learning_minimal uses verbatim; put the source tree on the
# compiler's default include path so <Eigen/Core> resolves regardless.
export CPATH="$TP/eigen${CPATH:+:$CPATH}"

echo "== learning_minimal"
for p in 4p3v 5p2v; do
  # CMakeLists asks for CMake 2.8; CMake 4 needs an explicit policy floor to accept it.
  cmake -S "$TP/learning_minimal/$p" -B "$TP/learning_minimal/$p/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "${EIGEN_ARGS[@]}"
  cmake --build "$TP/learning_minimal/$p/build" -j "$JOBS"
done

echo "== PoseLib@threeview (python package, links libtorch)"
TORCH_DIR=$("$PY" -c "import torch.utils; print(torch.utils.cmake_prefix_path)")/Torch
# The fork hard-codes its author's libtorch path; point it at the venv's torch instead.
sed -i "s|^set(Torch_DIR .*)|set(Torch_DIR $TORCH_DIR)|" "$TP/PoseLib-threeview/CMakeLists.txt"
( cd "$TP/PoseLib-threeview" && \
  CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DEigen3_DIR=$TP/eigen/build" \
  Eigen3_DIR="$TP/eigen/build" \
  "$UV" pip install --python "$PY" --offline --no-index --no-build-isolation --find-links "$ROOT/wheelhouse/build" . )
"$PY" -c "import poselib; print('poselib (threeview fork) ok:', [n for n in dir(poselib) if 'three' in n.lower() or '3v' in n.lower()][:8])"

echo "== superansac"
if [[ -d /usr/include/boost && ( -d /usr/include/opencv4 || -d /usr/local/include/opencv4 ) ]]; then
  cmake -S "$TP/superansac" -B "$TP/superansac/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "${EIGEN_ARGS[@]}"
  cmake --build "$TP/superansac/build" -j "$JOBS"
else
  echo "SKIP: Boost / OpenCV C++ headers not found (need libboost-dev libopencv-dev from the admin)"
fi
echo "done; threeview eval scripts are in $TP/threeview (export PYTHONPATH=$TP/threeview)"
