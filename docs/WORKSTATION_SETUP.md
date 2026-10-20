# Workstation setup (Ubuntu + NVIDIA GPU + internet)

Full setup on a lab workstation such as `abl-dell`, from a clean account to the Tzamos et al. table.
These are the steps that worked on an Ubuntu 24.04 / 2x RTX A6000 workstation on 2026-10-19, in order.
Data stays on the external SSD (exFAT, label `SSD`, folder `learning-algo-cvpr/`); nothing large is
copied to the internal disk. For a machine without internet, use `docs/CLUSTER_SETUP.md` instead.

Run the commands one at a time. Lines starting with `#` are notes, not commands.

## 0. Check the machine

```bash
lsb_release -d; nproc; free -g | head -2; df -h ~ | tail -1
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
which conda git g++ patch; ping -c1 -W3 github.com | tail -1
```

Need: Ubuntu 22.04+, an NVIDIA driver >= 525 (for the CUDA 12.6 PyTorch wheels), about 15 GB free in
your home folder, and internet. If `conda` is missing, install Miniconda for your user (no sudo needed)
from https://docs.conda.io/en/latest/miniconda.html, then open a new terminal.

## 1. Mount the SSD

Plug it in; Ubuntu mounts it at `/media/$USER/SSD`. Then:

```bash
export S=/media/$USER/SSD/learning-algo-cvpr
ls $S
```

Expect `apt-bundle code data papers private wheelhouse` (plus anything saved later, e.g. results).
`export` only lasts for this terminal; repeat it in any new terminal that needs `$S`.

## 2. System packages (needs sudo)

```bash
sudo apt install -y build-essential git patch libboost-dev libboost-system-dev libopencv-dev
```

Without sudo everything except SupeRANSAC still builds, as long as `g++` and `patch` exist.

## 3. Get the code

```bash
git clone https://github.com/onwusikasomkenechukwu/learning-algo-cvpr-2027.git ~/learning-algo
cd ~/learning-algo
cp $S/private/*.py src/
ls $S/private/*.py | xargs -n1 basename | sed 's|^|src/|' >> .git/info/exclude
git status --short
```

`git status --short` must print nothing: the private files are copied in but invisible to git.

## 4. Python environment

Use a separate conda env; do not install into `base`.

```bash
conda create -y -n cvpr python=3.12
conda activate cvpr
pip install -r requirements.lock -r requirements-extra.lock
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
pip install kornia==0.8.3 matplotlib prettytable seaborn "git+https://github.com/cvg/LightGlue@eb42fee2d71449efb0aa5c10549752b5d75384d8"
```

Check (expect `True` and the number of GPUs, then `OK` for 8 tests):

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
python -m unittest discover -s tests
```

Every new terminal needs `conda activate cvpr` and `cd ~/learning-algo` first.

## 5. Link the env, the wheelhouse and the data

The build script expects `.venv/` and `wheelhouse/` inside the repo; the datasets stay on the SSD.

```bash
ln -s "$CONDA_PREFIX" .venv
ln -s $S/wheelhouse wheelhouse
for d in $S/data/*/; do ln -sfn "$d" data/$(basename "$d"); done
ls data
```

## 6. Build the seed papers' code

Hruby et al. (`learning_minimal`), Tzamos et al. (PoseLib `threeview` fork + eval scripts, patched by
`scripts/patches/`), and SupeRANSAC, all from the pinned sources in the wheelhouse. Takes a few minutes.

```bash
bash scripts/build_seed_code.sh 2>&1 | tee ~/build.log
tail -4 ~/build.log
```

Success ends with these lines (paths will differ):

```
poselib (threeview fork) ok: ... ['ThreeViewCameraPose', 'estimate_three_view_relative_pose', ...]
pysuperansac ok: ...
done; run threeview evals from .../third_party/threeview ...
```

(`poselib` scrolls further up; `grep "poselib (threeview" ~/build.log` shows it.) If it fails:
`grep -n "error" ~/build.log | head -20`.

## 7. Tzamos et al. table (their code, 21 methods, 5 px)

If results were saved to the SSD from an earlier machine, restore them instead of re-running:

```bash
ls $S
mkdir -p third_party/threeview/results && cp $S/tzamos_results_dell/*.json third_party/threeview/results/
```

Otherwise run every triplet scene in the background (about 5 min per scene on 20 cores; 14 scenes):

```bash
nohup bash scripts/run_tzamos_table.sh > ~/table3.log 2>&1 &
```

Progress (each `==` line is a scene and its start time; finished at `== all done`):

```bash
grep "==" ~/table3.log
```

Key rows per scene once done:

```bash
grep -F -e "==" -e "5p3v  " -e "4p(HC)" -e "(M-D) + R + C  " -e FAILED ~/table3.log
```

On `FAILED`: `grep -m1 -A15 Traceback ~/tzamos_stderr.log`. Run nothing else heavy at the same time,
or the runtime columns are not comparable. The learned (L) variants are a separate pass:
`nohup bash scripts/run_tzamos_table.sh --learning -a > ~/table3_learning.log 2>&1 &`.

## 8. Before unplugging the SSD

```bash
cd ~
udisksctl unmount -b $(findmnt -no SOURCE /media/$USER/SSD)
```

Or right-click the SSD icon in the dock and choose Eject. Anything still using the SSD (a terminal
inside it, a running eval) makes this fail with "target is busy".
