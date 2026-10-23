#!/usr/bin/env bash
# Build the seed papers' code from the pinned sources in wheelhouse/src (no network needed).
# Needs: g++ and patch; apt libboost-dev libboost-system-dev libopencv-dev for superansac; the Python
# env at .venv with torch installed (PoseLib@threeview links the libtorch inside the torch package).
# CMake/Ninja/pybind11 come from wheelhouse/build, Eigen 3.4.0 from source.
# Builds into third_party/ (not in git):
#   learning_minimal (Hruby et al. CVPR 2022): 4p3v + 5p2v binaries
#   PoseLib@threeview (Tzamos et al. CVPR 2025) as the python package `poselib` in .venv
#     (replaces upstream poselib); fixes in scripts/patches/poselib-threeview.patch
#   threeview evaluation scripts (python, nothing to compile)
#   superansac: built only if Boost (incl. system) + OpenCV C++ dev packages are present
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
UV=$ROOT/wheelhouse/tools/uv   # absolute: the PoseLib step runs uv from inside third_party/
PY=$ROOT/.venv/bin/python
TP=$ROOT/third_party
mkdir -p "$TP"
command -v g++ >/dev/null || { echo "ERROR: no g++; sudo apt install build-essential"; exit 1; }
command -v patch >/dev/null || { echo "ERROR: no patch; sudo apt install patch"; exit 1; }
"$PY" -c "import torch" || { echo "ERROR: torch not importable from $PY"; exit 1; }

"$UV" pip install --python "$PY" --offline --no-index --find-links wheelhouse/build cmake ninja pybind11 setuptools wheel
export PATH="$ROOT/.venv/bin:$PATH"   # pip-installed cmake / ninja
JOBS=$(nproc)

unpack() {  # unpack <tarball-glob> <dest-name>
  [[ -d "$TP/$2" ]] && return
  tar -xzf $1 -C "$TP" && mv "$TP"/$(tar -tzf $1 | head -1 | cut -d/ -f1) "$TP/$2"
}
unpack "wheelhouse/src/eigen-3.4.0.tar.gz" eigen
unpack "wheelhouse/src/learning_minimal-*.tar.gz" learning_minimal
unpack "wheelhouse/src/threeview-*.tar.gz" threeview
# Patch once; threeview/ also holds eval results, so it is not re-extracted. The patch adds
# h5_flat_items, so its presence means the patch is in.
grep -q h5_flat_items "$TP/threeview/eval.py" \
  || patch -d "$TP/threeview" -p1 --forward < scripts/patches/threeview.patch
grep -q "DEVICE = " "$TP/threeview/datasets/prepare_im.py" \
  || patch -d "$TP/threeview" -p1 --forward < scripts/patches/threeview-cpu.patch
grep -q -- "--exps" "$TP/threeview/eval_f.py" \
  || patch -d "$TP/threeview" -p1 --forward < scripts/patches/threeview-eval.patch
"$PY" scripts/patches/threeview_enm.py "$TP/threeview"   # '+ ENM' -> two-view refit in eval_f.py
"$PY" scripts/patches/threeview_seq.py "$TP/threeview"   # '+ SEQ' -> sequential baseline in eval_f.py
rm -f "$TP"/threeview/*.rej "$TP"/threeview/*/*.rej "$TP"/threeview/*.orig "$TP"/threeview/*/*.orig
unpack "wheelhouse/src/superansac-*.tar.gz" superansac
# Eigen 3.4 is header-only but ships its CMake config only after configuring; do that once.
[[ -f "$TP/eigen/build/Eigen3Config.cmake" ]] || cmake -S "$TP/eigen" -B "$TP/eigen/build" -G Ninja >/dev/null
export Eigen3_DIR="$TP/eigen/build"   # find_package(Eigen3) also reads this from the environment
EIGEN_ARGS=(-DEigen3_DIR="$TP/eigen/build" -DEIGEN3_INCLUDE_DIR="$TP/eigen")
# Eigen's build-tree config reports EIGEN3_INCLUDE_DIRS as the (non-existent) install prefix
# (<repo>/include/eigen3), which learning_minimal uses verbatim; put the source tree on the
# compiler's default include path so <Eigen/Core> resolves regardless.
export CPATH="$TP/eigen${CPATH:+:$CPATH}"

if [[ ${ONLY:-} != poselib ]]; then   # ONLY=poselib rebuilds just the fork (e.g. after a patch change)
echo "== learning_minimal"
for p in 4p3v 5p2v; do
  # CMakeLists asks for CMake 2.8; CMake 4 needs an explicit policy floor to accept it.
  cmake -S "$TP/learning_minimal/$p" -B "$TP/learning_minimal/$p/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "${EIGEN_ARGS[@]}"
  cmake --build "$TP/learning_minimal/$p/build" -j "$JOBS"
done
fi

echo "== PoseLib@threeview (python package, links libtorch)"
# Always start from the pristine pinned source so the patch applies exactly (and fails loudly if not);
# this also discards the build directory and its CMake cache from earlier attempts.
rm -rf "$TP/PoseLib-threeview"
unpack "wheelhouse/src/PoseLib-*.tar.gz" PoseLib-threeview
patch -d "$TP/PoseLib-threeview" -p1 --forward < scripts/patches/poselib-threeview.patch
"$PY" scripts/patches/poselib_oob_fixes.py "$TP/PoseLib-threeview"   # sample[4] read past the end in inner_refine
"$PY" scripts/patches/poselib_shared_focal_refit.py "$TP/PoseLib-threeview"   # kill test A two-view refit
"$PY" scripts/patches/poselib_sequential.py "$TP/PoseLib-threeview"   # Task 2.9 sequential baseline + binding
# setup.py only forwards Python_EXECUTABLE to CMake; the patched CMakeLists find torch and pybind11
# through that interpreter. --no-cache: uv would otherwise reuse a wheel built from an older patch.
( cd "$TP/PoseLib-threeview" && \
  "$UV" pip install --python "$PY" --offline --no-index --no-build-isolation --no-cache --reinstall-package poselib . )
"$PY" -c "import poselib; print('poselib (threeview fork) ok:', poselib.__file__, [n for n in dir(poselib) if 'three' in n.lower() or '3v' in n.lower()][:8])"

echo "== superansac"
if [[ ${ONLY:-} == poselib ]]; then
  echo "SKIP (ONLY=poselib)"
elif [[ -d /usr/include/opencv4 ]] && compgen -G "/usr/lib/*/cmake/boost_system-*/boost_system-config.cmake" >/dev/null; then
  cmake -S "$TP/superansac" -B "$TP/superansac/build" -G Ninja -DCMAKE_BUILD_TYPE=Release "${EIGEN_ARGS[@]}" \
    -DPython_EXECUTABLE="$PY" -Dpybind11_DIR="$("$PY" -m pybind11 --cmakedir)"
  cmake --build "$TP/superansac/build" -j "$JOBS"
  SA_MOD=$(find "$TP/superansac/build" -name 'pysuperansac*.so' | head -1)
  PYTHONPATH="$(dirname "${SA_MOD:-missing/x}")" "$PY" -c "import pysuperansac; print('pysuperansac ok:', pysuperansac.__file__)"
else
  echo "SKIP: needs sudo apt install libboost-dev libboost-system-dev libopencv-dev"
fi
# The fork loads res/epoch28_sampson.pt, res/anchors.txt, res/nn.txt relative to the working directory;
# those files live in the threeview repo, so run its evaluation scripts from there.
echo "done; run threeview evals from $TP/threeview (cd there; export PYTHONPATH=$TP/threeview)"
