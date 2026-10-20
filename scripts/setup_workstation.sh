#!/usr/bin/env bash
# One-shot setup of a lab workstation (Ubuntu + NVIDIA GPU + internet) from a fresh clone:
# checks, apt packages, private files, conda env, links to the SSD, seed-code build, then local copies
# of whatever SSD data fits on the internal disk (the rest stays linked to the SSD).
# Safe to re-run: finished steps are skipped or redone harmlessly. Asks for the sudo password once
# if apt packages are missing. Steps are explained in docs/WORKSTATION_SETUP.md.
#   bash scripts/setup_workstation.sh 2>&1 | tee ~/setup.log
# Optional: SSD=/path/to/learning-algo-cvpr  ENV_NAME=cvpr
#   LOCAL_COPY=0 (keep everything on the SSD)  KEEP_FREE_GB=50 (never fill the disk past this)
#   LOCAL_DIR=~/learning-algo-data (where local copies go)
set -eo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
S=${SSD:-/media/$USER/SSD/learning-algo-cvpr}
ENV_NAME=${ENV_NAME:-cvpr}
step() { echo; echo "=== $*"; }
die() { echo; echo "SETUP STOPPED: $*"; exit 1; }

step "0. Checks"
lsb_release -ds 2>/dev/null || true
echo "threads: $(nproc), RAM: $(free -g | awk '/^Mem/{print $2}') GB"
# The CUDA build of PyTorch needs a working NVIDIA driver to run and the CUDA toolkit for C++ code to
# link against it (the PoseLib fork does); without a GPU, install the CPU build, which needs neither.
if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
  GPU=1; TORCH_TAG=cu126
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  command -v nvcc >/dev/null || [[ -d /usr/local/cuda ]] || echo "WARNING: GPU but no CUDA toolkit (nvcc):
  the PoseLib fork build will fail at CMake; install one (e.g. sudo apt install nvidia-cuda-toolkit)"
else
  GPU=0; TORCH_TAG=cpu
  echo "No working NVIDIA GPU/driver: installing CPU-only PyTorch (all code here runs, neural nets just slower)"
  lspci 2>/dev/null | grep -i -E "vga|3d|nvidia" || true
fi
FREE_GB=$(df -Pk "$HOME" | awk 'NR==2{print int($4/1048576)}')
echo "free in home: ${FREE_GB} GB"
(( FREE_GB >= 15 )) || die "need about 15 GB free in $HOME, have ${FREE_GB} GB"
[[ -d $S/wheelhouse && -d $S/data ]] || die "SSD project folder not found at $S
  plug in the SSD, or re-run with SSD=/path/to/learning-algo-cvpr in front of the command"
command -v conda >/dev/null || die "conda not found: install Miniconda for your user
  (https://docs.conda.io/en/latest/miniconda.html), open a new terminal, re-run"
curl -sfI --max-time 10 https://github.com >/dev/null || die "no internet; use docs/CLUSTER_SETUP.md"

step "1. System packages"
PKGS=(build-essential git patch rsync libboost-dev libboost-system-dev libopencv-dev)
MISSING=()
for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
if (( ${#MISSING[@]} )); then
  echo "installing: ${MISSING[*]} (asks for your sudo password)"
  sudo apt-get install -y "${MISSING[@]}" || echo "WARNING: apt failed; SupeRANSAC will be skipped"
else
  echo "all present"
fi
command -v g++ >/dev/null && command -v patch >/dev/null || die "g++ and patch are required (apt: build-essential patch)"

step "2. Private files (kept out of git)"
for f in "$S"/private/*.py; do
  [[ -e $f ]] || { echo "none on the SSD"; break; }
  n=src/$(basename "$f")
  [[ -e $n ]] || cp "$f" "$n"
  grep -qxF "$n" .git/info/exclude || echo "$n" >> .git/info/exclude
  [[ -z $(git status --porcelain -- "$n") ]] || die "$n is visible to git"
  echo "copied $n"
done

step "3. Conda env '$ENV_NAME' (Python 3.12, PyTorch 2.14.1+$TORCH_TAG)"
source "$(conda info --base)/etc/profile.d/conda.sh"
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  # conda-forge only: avoids the defaults channel's terms-of-service prompt on new Miniconda installs.
  conda create -y -n "$ENV_NAME" -c conda-forge --override-channels python=3.12
fi
conda activate "$ENV_NAME"
# Upstream poselib is left out: the build step installs the threeview fork as `poselib`, and a re-run
# must not replace the fork with upstream 2.0.5.
python -m pip install -q -r <(grep -v '^poselib' requirements.lock) -r requirements-extra.lock
# Exact local version (+cpu / +cu126), so a re-run on a changed machine swaps the build instead of
# keeping the old one as "already satisfied".
python -m pip install -q "torch==2.14.1+$TORCH_TAG" "torchvision==0.29.1+$TORCH_TAG"   --index-url "https://download.pytorch.org/whl/$TORCH_TAG"
if (( ! GPU )); then  # CUDA runtime wheels left over from a CUDA build: several GB, unused now
  python -m pip uninstall -y -q $(python -m pip list --format=freeze | grep -oE '^(nvidia-[^=]+|triton)') 2>/dev/null || true
fi
python -m pip install -q kornia==0.8.3 matplotlib prettytable seaborn \
  "git+https://github.com/cvg/LightGlue@eb42fee2d71449efb0aa5c10549752b5d75384d8"
python -c "import torch; n = torch.cuda.device_count(); print('torch', torch.__version__, '| CUDA available:', torch.cuda.is_available(), '| GPUs:', n)"

step "4. Links: .venv -> conda env, wheelhouse and data -> SSD"
for l in .venv wheelhouse; do
  [[ -e $l && ! -L $l ]] && die "$ROOT/$l exists and is not a link; move it away and re-run"
done
ln -sfn "$CONDA_PREFIX" .venv
ln -sfn "$S/wheelhouse" wheelhouse
for d in "$S"/data/*/; do ln -sfn "$d" "data/$(basename "$d")"; done
echo "data: $(ls data | tr '\n' ' ')"

step "5. Build seed-paper code (learning_minimal, PoseLib@threeview, superansac)"
bash scripts/build_seed_code.sh

step "5b. Check: the fork is the poselib Python sees; repo tests"
python -c "import poselib; assert hasattr(poselib, 'estimate_three_view_relative_pose'), poselib.__file__; print('poselib fork ok:', poselib.__file__)" \n  || die "python imports a poselib without the three-view estimators (see above); re-run this script"
python -m unittest discover -s tests 2>&1 | tail -3

step "6. Local copies of SSD data (whatever fits while keeping ${KEEP_FREE_GB:=50} GB free)"
if [[ ${LOCAL_COPY:-1} == 0 ]]; then
  echo "skipped (LOCAL_COPY=0): everything stays on the SSD"
else
  LOCAL=${LOCAL_DIR:-$HOME/learning-algo-data}
  mkdir -p "$LOCAL"
  echo "measuring sizes on the SSD (can take a few minutes)..."
  ON_SSD=(); COPIED=()
  # Smallest first, so as many datasets as possible end up local. A copy only counts once
  # .copied_ok exists; an interrupted copy resumes on the next run and stays linked to the SSD until then.
  while IFS=$'\t' read -r kb src; do
    src=${src%/}; name=$(basename "$src"); dest=$LOCAL/$name
    # data/raw holds the downloaded archives, already unpacked into the other folders: not worth the space.
    [[ $src == */data/raw ]] && { ON_SSD+=("raw (archives)"); continue; }
    if [[ ! -f $dest/.copied_ok ]]; then
      have_kb=$(du -sk "$dest" 2>/dev/null | cut -f1); have_kb=${have_kb:-0}
      free_kb=$(df -Pk "$LOCAL" | awk 'NR==2{print $4}')
      if (( free_kb - (kb - have_kb) < KEEP_FREE_GB * 1048576 )); then
        ON_SSD+=("$name ($(( kb / 1048576 )) GB)"); continue
      fi
      echo "copying $name ($(( kb / 1048576 )) GB) to $dest"
      rsync -rt --info=progress2 "$src/" "$dest/"
      touch "$dest/.copied_ok"
    fi
    case $src in
      */data/*) ln -sfn "$dest" "data/$name" ;;
      *) ln -sfn "$dest" "$name" ;;   # wheelhouse, papers
    esac
    COPIED+=("$name")
  done < <(du -sk "$S"/data/*/ "$S/wheelhouse" "$S/papers" 2>/dev/null | sort -n)
  echo "local (in $LOCAL): ${COPIED[*]:-none}"
  echo "still on the SSD: ${ON_SSD[*]:-none}"
  df -h "$LOCAL" | tail -1
  (( ${#ON_SSD[@]} )) || echo "everything is local: the SSD is no longer needed on this machine"
fi

step "Setup finished"
echo "Every new terminal: conda activate $ENV_NAME && cd $ROOT"
echo "Tzamos et al. table (about an hour, runs in the background):"
echo "  nohup bash scripts/run_tzamos_table.sh > ~/table3.log 2>&1 &"
