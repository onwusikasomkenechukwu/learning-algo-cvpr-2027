"""Run threeview's datasets/prepare_im.py one scene at a time (task 1.6) for Cambridge or ETH3D, with the
settings of draft v4: images resized to 800 px on the larger side, at most 2048 SuperPoint keypoints,
LightGlue, up to 5000 random triplets per scene. For ETH3D (14-76 images per scene) use -n 0 --cap N: every
qualifying image triplet, or a seeded random N of them (prepare_im.py -n N never stops when fewer qualify).
Needs the threeview tree patched with scripts/patches/threeview-cpu.patch, LightGlue importable, TORCH_HOME
(or ~/.cache/torch) holding the LightGlue weights, and for Cambridge model_train in each scene folder
(scripts/cambridge_nvm_to_colmap.py). The name of DATA_DIR selects prepare_im.py's layout: it must contain
'cambridge' or 'eth3d'. For ETH3D, run scripts/filter_same_camera.py afterwards.

prepare_im.py is loaded by path because its folder name `datasets` clashes with the Hugging Face package.

Usage (from the patched threeview folder):
  python ~/learning-algo/scripts/prepare_triplets.py OUT_DIR $SSD/data/cambridge KingsCollege OldHospital ...
  python ~/learning-algo/scripts/prepare_triplets.py -n 0 --cap 2000 OUT_DIR $SSD/data/eth3d courtyard delivery_area ...
"""
import argparse
import importlib.util
import itertools
import random
import sys
import time
import types
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("data_dir", help="folder holding the scene folders (name contains 'cambridge' or 'eth3d')")
    ap.add_argument("scenes", nargs="+")
    ap.add_argument("-n", type=int, default=5000, help="triplets per scene; 0 = every qualifying triplet")
    ap.add_argument("-r", "--resize", type=int, default=800, help="larger image side for feature extraction")
    ap.add_argument("--cap", type=int, default=0,
                    help="with -n 0: at most this many triplets, a seeded random choice among the image triplets "
                         "that pass prepare_im.py's overlap test (0 = all of them)")
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
        if args.n <= 0 and args.cap > 0:
            capped_combinations(prep, args.data_dir, scene, args.cap)
        prep.prepare_single(pargs, scene)
        print(f"== {scene} done in {time.time() - t0:.0f} s", flush=True)


def capped_combinations(prep, data_dir, scene, cap, seed=100, min_area=0.1):
    """Make prepare_im.py's every-triplet mode (-n 0) visit at most `cap` image triplets: those passing its own
    overlap test (co-visible area > min_area in all three images), a seeded random choice when there are more.
    Asking prepare_im.py for -n cap instead could loop forever when fewer triplets survive its later checks."""
    _, model_path, _ = prep.get_dataset_paths(Path(data_dir).name, data_dir, scene)
    cameras, images, points = prep.read_model(model_path)
    ids = list(images.keys())
    ok = [c for c in itertools.combinations(ids, 3)
          if min(prep.get_overlap_areas(cameras, images, points, c)) > min_area]
    chosen = ok if len(ok) <= cap else random.Random(seed).sample(ok, cap)
    print(f"{scene}: {len(ok)} image triplets pass the overlap test; matching {len(chosen)}", flush=True)
    prep.itertools = types.SimpleNamespace(combinations=lambda *_: list(chosen))


if __name__ == "__main__":
    main()
