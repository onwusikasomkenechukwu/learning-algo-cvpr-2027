#!/usr/bin/env bash
# One-shot setup of a lab workstation (Ubuntu + NVIDIA GPU + internet) from a fresh clone:
# checks, apt packages, private files, conda env, links to the SSD, seed-code build.
# Safe to re-run: finished steps are skipped or redone harmlessly. Asks for the sudo password once
# if apt packages are missing. Steps are explained in docs/WORKSTATION_SETUP.md.
#   bash scripts/setup_workstation.sh 2>&1 | tee ~/setup.log
# Optional: SSD=/path/to/learning-algo-cvpr  ENV_NAME=cvpr
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
if command -v nvidia-smi >/dev/null; then
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
  echo "WARNING: no nvidia-smi, so no NVIDIA driver: PyTorch will run on CPU only"
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
PKGS=(build-essential git patch libboost-dev libboost-system-dev libopencv-dev)
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

step "3. Conda env '$ENV_NAME' (Python 3.12, PyTorch 2.14.1 + CUDA 12.6)"
source "$(conda info --base)/etc/profile.d/conda.sh"
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  # conda-forge only: avoids the defaults channel's terms-of-service prompt on new Miniconda installs.
  conda create -y -n "$ENV_NAME" -c conda-forge --override-channels python=3.12
fi
conda activate "$ENV_NAME"
python -m pip install -q -r requirements.lock -r requirements-extra.lock
python -m pip install -q torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -q kornia==0.8.3 matplotlib prettytable seaborn \
  "git+https://github.com/cvg/LightGlue@eb42fee2d71449efb0aa5c10549752b5d75384d8"
python -c "import torch; n = torch.cuda.device_count(); print('torch', torch.__version__, '| CUDA available:', torch.cuda.is_available(), '| GPUs:', n)"
python -m unittest discover -s tests 2>&1 | tail -3

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

step "Setup finished"
echo "Every new terminal: conda activate $ENV_NAME && cd $ROOT"
echo "Tzamos et al. table (about an hour, runs in the background):"
echo "  nohup bash scripts/run_tzamos_table.sh > ~/table3.log 2>&1 &"
