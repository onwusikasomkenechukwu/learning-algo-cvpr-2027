"""Run threeview's datasets/prepare_im.py one scene at a time (task 1.6) for Cambridge or ETH3D, with the
settings of draft v4: images resized to 800 px on the larger side, at most 2048 SuperPoint keypoints,
LightGlue, up to 5000 random triplets per scene (-n 0: every qualifying triplet, used for ETH3D, whose scenes
have only 14-76 images; prepare_im.py -n never stops when fewer unique triplets qualify than asked).
Needs the threeview tree patched with scripts/patches/threeview-cpu.patch, LightGlue importable, TORCH_HOME
(or ~/.cache/torch) holding the LightGlue weights, and for Cambridge model_train in each scene folder
(scripts/cambridge_nvm_to_colmap.py). The name of DATA_DIR selects prepare_im.py's layout: it must contain
'cambridge' or 'eth3d'. For ETH3D, run scripts/filter_same_camera.py afterwards.

prepare_im.py is loaded by path because its folder name `datasets` clashes with the Hugging Face package.

Usage (from the patched threeview folder):
  python ~/learning-algo/scripts/prepare_triplets.py OUT_DIR $SSD/data/cambridge KingsCollege OldHospital ...
  python ~/learning-algo/scripts/prepare_triplets.py -n 0 OUT_DIR $SSD/data/eth3d courtyard delivery_area ...
"""
import argparse
import importlib.util
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("data_dir", help="folder holding the scene folders (name contains 'cambridge' or 'eth3d')")
    ap.add_argument("scenes", nargs="+")
    ap.add_argument("-n", type=int, default=5000, help="triplets per scene; 0 = every qualifying triplet")
    ap.add_argument("-r", "--resize", type=int, default=800, help="larger image side for feature extraction")
    ap.add_argument("--threeview", default=".", help="patched threeview checkout")
    args = ap.parse_args()
    tv = Path(args.threeview).resolve()
    sys.path.insert(0, str(tv))
    spec = importlib.util.spec_from_file_location("prepare_im", tv / "datasets" / "prepare_im.py")
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    n = ["-n", str(args.n)] if args.n > 0 else []
    sys.argv = ["prepare_im.py", *n, "-r", str(args.resize), "-mf", "2048", "-s", "100", args.out_dir,
                args.data_dir]
    pargs = prep.parse_args()
    for scene in args.scenes:
        t0 = time.time()
        print(f"== {scene}", flush=True)
        prep.prepare_single(pargs, scene)
        print(f"== {scene} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
