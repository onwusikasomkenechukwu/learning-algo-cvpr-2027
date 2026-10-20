"""Run threeview's datasets/prepare_im.py on Cambridge scenes one at a time (task 1.6), with the settings of
draft v4: images resized to 800 px on the larger side, at most 2048 SuperPoint keypoints, LightGlue, up to
5000 random triplets per scene. Needs the threeview tree patched with scripts/patches/threeview-cpu.patch,
LightGlue on PYTHONPATH, TORCH_HOME holding the LightGlue weights, and model_train in each scene folder
(scripts/cambridge_nvm_to_colmap.py).

prepare_im.py is loaded by path because its folder name `datasets` clashes with the Hugging Face package.

Usage (from the patched threeview folder):
  python ../../learning-algo/scripts/prepare_cambridge_triplets.py OUT_DIR DATA_DIR KingsCollege OldHospital ...
"""
import argparse
import importlib.util
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("data_dir", help="folder holding the scene folders (its name must contain 'cambridge')")
    ap.add_argument("scenes", nargs="+")
    ap.add_argument("-n", type=int, default=5000)
    ap.add_argument("--threeview", default=".", help="patched threeview checkout")
    args = ap.parse_args()
    tv = Path(args.threeview).resolve()
    sys.path.insert(0, str(tv))
    spec = importlib.util.spec_from_file_location("prepare_im", tv / "datasets" / "prepare_im.py")
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    sys.argv = ["prepare_im.py", "-n", str(args.n), "-r", "800", "-mf", "2048", "-s", "100", args.out_dir,
                args.data_dir]
    pargs = prep.parse_args()
    for scene in args.scenes:
        t0 = time.time()
        print(f"== {scene}", flush=True)
        prep.prepare_single(pargs, scene)
        print(f"== {scene} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
