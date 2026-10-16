# Cluster setup (offline, from the SSD)

Copy-paste guide for the 4-node cluster (node0–node3, 192.168.10.10–13, Ubuntu 26.04, kernel
7.0.0-30-generic, Secure Boot on, no internet). Everything comes from the SSD
(`learning-algo-cvpr/` on the exFAT drive labelled **SSD**). Do node0 first; the other nodes are
set up from node0 over SSH (no password needed between nodes). Each step ends with a **check**.

SSD layout:
```
learning-algo-cvpr/
  code/        git checkout of this repo (scripts, src, tests, lock files)
  apt-bundle/  529 Ubuntu .debs + Packages index (compiler, Boost/OpenCV dev, NVIDIA 580 driver)
  wheelhouse/  offline Python wheels, uv, PyTorch CUDA 12.6, sources, weights
  data/        all datasets (~380 GB; EF.tar still packed)
  papers/      seed papers
  private/     unpublished prototype code (not in git)
```

## 0. Mount the SSD (node0)
```bash
lsblk -f                                   # find the ~466G exfat partition labelled SSD, e.g. sdb1
udisksctl mount -b /dev/sdb1               # or: sudo mkdir -p /mnt/ssd && sudo mount -t exfat /dev/sdb1 /mnt/ssd
export S=/media/$USER/SSD/learning-algo-cvpr   # adjust if it mounted elsewhere (e.g. /mnt/ssd/learning-algo-cvpr)
ls $S
```
**Check:** `ls` shows `apt-bundle code data papers private wheelhouse`.

## 1. Copy code, packages and Python bundle to node0's disk (small, a few minutes)
```bash
cp -r $S/code ~/learning-algo
rsync -a --info=progress2 $S/apt-bundle $S/wheelhouse $S/papers ~/learning-algo/
cp $S/private/*.py ~/learning-algo/src/
cd ~/learning-algo && git log --oneline | head -1
```
**Check:** the last command prints the latest commit; `ls ~/learning-algo/apt-bundle | wc -l` prints 531 (529 packages + Packages + Release).

## 2. Start the dataset copy in the background (~380 GB, 1–2 hours over USB)
```bash
nohup rsync -a $S/data/ ~/learning-algo/data/ > ~/data_copy.log 2>&1 &
```
**Check later:** `tail ~/data_copy.log` is empty and `jobs` shows nothing running, then
`du -sh ~/learning-algo/data` is ~380G. Keep the SSD plugged in until it finishes.

## 3. Install system packages from the offline bundle (node0, needs your sudo password)
```bash
echo "deb [trusted=yes] file:$HOME/learning-algo/apt-bundle ./" | sudo tee /etc/apt/sources.list.d/offline.list
sudo apt update -o Acquire::Check-Date=false -o Dir::Etc::sourcelist=sources.list.d/offline.list -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
sudo apt install -o Dir::Etc::sourcelist=sources.list.d/offline.list -o Dir::Etc::sourceparts=- --no-install-recommends -y build-essential unzip pkg-config \
    libboost1.88-dev libboost-system1.88-dev libopencv-dev \
    linux-modules-nvidia-580-server-open-7.0.0-30-generic nvidia-headless-no-dkms-580-server-open nvidia-utils-580-server
sudo rm /etc/apt/sources.list.d/offline.list
```
The package versions match the node exactly (resolved from the Ubuntu archive as of 2026-08-25:
libc6 2.43-2ubuntu2.3, NVIDIA 580.173.02 with Canonical-signed modules for kernel 7.0.0-30), so apt
installs without upgrading the system. Both `apt update` and `apt install` must get the
`-o Dir::Etc::...` options: without them, `apt install` also reads the node's old internet package lists,
prefers newer versions from them and tries (and fails) to download.
**Check:** `g++ --version` prints GCC 15; `unzip -v | head -1` works.

## 4. Reboot once for the GPU driver
```bash
sudo reboot
```
After logging back in:
```bash
nvidia-smi
```
**Check:** shows "NVIDIA T1000 8GB" and driver 580.173.02. (If it says "couldn't communicate with the
NVIDIA driver", run `sudo modprobe nvidia` and send me the output of `sudo dmesg | grep -i nvidia | tail`.)

## 5. Python environments and tests (node0, no sudo)
```bash
cd ~/learning-algo
bash scripts/setup_node.sh          # base stack + scikit-learn; prints "ok: ..." lines
.venv/bin/python -m unittest discover -s tests -v
bash scripts/setup_node_gpu.sh      # PyTorch CUDA 12.6 + LightGlue; ends with a SuperPoint+LightGlue smoke test
bash scripts/build_seed_code.sh     # learning_minimal, PoseLib@threeview, superansac into third_party/
```
**Check:** all tests say OK; the GPU script prints `CUDA available: True ... T1000`; the build script
ends with `done`. Send me any error output — these have not run on Linux before.

## 6. Unpack the 92 GB tutorial training pack (node0, after step 2 finished)
```bash
nohup tar -xf ~/learning-algo/data/raw/ransac_tutorial/RANSAC-Tutorial-Data-EF.tar -C ~/learning-algo/data/ransac_tutorial/ > ~/ef_unpack.log 2>&1 &
```
**Check later:** `ls ~/learning-algo/data/ransac_tutorial/` shows a new `RANSAC-Tutorial-Data` folder.

## 7. Set up node1–node3 from node0
Copy code, packages and Python bundle (data is copied per experiment by `scripts/run_cluster.sh`):
```bash
for n in node1 node2 node3; do rsync -a ~/learning-algo/ $n:learning-algo/ --exclude data --exclude .venv --exclude third_party; done
```
Then on each node (asks for the sudo password on that node):
```bash
for n in node1 node2 node3; do
  ssh -t $n 'echo "deb [trusted=yes] file:$HOME/learning-algo/apt-bundle ./" | sudo tee /etc/apt/sources.list.d/offline.list &&
    sudo apt update -o Acquire::Check-Date=false -o Dir::Etc::sourcelist=sources.list.d/offline.list -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0 &&
    sudo apt install -o Dir::Etc::sourcelist=sources.list.d/offline.list -o Dir::Etc::sourceparts=- --no-install-recommends -y build-essential unzip pkg-config libboost1.88-dev libboost-system1.88-dev libopencv-dev linux-modules-nvidia-580-server-open-7.0.0-30-generic nvidia-headless-no-dkms-580-server-open nvidia-utils-580-server &&
    sudo rm /etc/apt/sources.list.d/offline.list && sudo reboot'
done
```
After they come back up:
```bash
for n in node1 node2 node3; do ssh $n 'nvidia-smi --query-gpu=name,driver_version --format=csv,noheader && cd learning-algo && bash scripts/setup_node.sh | tail -2'; done
```
**Check:** each node prints its T1000 with driver 580.173.02 and the `ok:` lines.

## Notes
- Only kernel **7.0.0-30-generic** is covered by the bundled GPU modules. Do not install a different
  kernel on the nodes, or the driver will stop loading until a matching bundle is built.
- To rebuild or extend the package bundle on an online machine:
  `python scripts/build_apt_bundle.py download --seeds-file scripts/apt/cluster_seeds.txt --snapshot 20260825T000000Z --assume-installed linux-image-7.0.0-30-generic --out <dir>`
