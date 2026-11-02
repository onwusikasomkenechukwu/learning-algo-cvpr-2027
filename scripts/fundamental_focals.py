"""Focal length per triplet from the fundamental matrix of views 1-2 (draft v5 supplement: the focal-prior row
'5p3v + R + C + PRIOR(fundamental)', after Kocur et al., CVPR 2024).

For every triplet of a feature's list: the matches eval_f.py keeps (same score filter), F from upstream PoseLib's
LO-RANSAC (estimate_fundamental, 5 px), then focals_from_fundamental_iterative (Kocur et al.) for both views from the
principal points of K.h5, and their mean as the shared focal length. When that fails (fewer than 8 matches, no F, or a
focal length outside 0.1-10 x the larger image side) the triplet gets the guessed value 1.25 x the larger side (the
COLMAP default, as the guessed-f row) and is counted as a fallback, so no triplet is dropped. Writes
<triplet dir>/fundamental_focals-<feature>.h5 ('img1-img2-img3' -> f in pixels; attribute 'fallbacks') and a times
file (mean ms per triplet for F and the focal lengths, reported apart from the LO time). eval_f.py reads it through
$EVALF_FFOCALS (threeview_extra.py).

Runs in .venv-nets with upstream PoseLib 2.0.5 (installed offline from the SSD wheelhouse), never next to the fork.

  .venv-nets/bin/python scripts/fundamental_focals.py $SSD/data/cambridge_triplets/KingsCollege \
      --feature triplets-SIFT_triplet_correspondences-rootsift8000
"""
import argparse
import time
from pathlib import Path

import h5py
import numpy as np


def flat(path):
    out = {}
    with h5py.File(path, "r") as f:
        f.visititems(lambda k, v: out.__setitem__(k.replace("\\", "/"), np.array(v)) if isinstance(v, h5py.Dataset) else None)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("triplet_dir", type=Path)
    ap.add_argument("--feature", required=True)
    ap.add_argument("--threshold", type=float, default=5.0)
    args = ap.parse_args()

    import poselib
    K = flat(args.triplet_dir / "K.h5")
    out = args.triplet_dir / f"fundamental_focals-{args.feature}.h5"
    lines = [l.split() for l in (args.triplet_dir / f"{args.feature}.txt").read_text().splitlines() if l.strip()]
    sift = "SIFT_triplet_correspondences" in args.feature
    n_fb, n_new, ms = 0, 0, []
    with h5py.File(args.triplet_dir / f"{args.feature}.h5", "r") as fm, h5py.File(out, "a") as fo:
        for names in lines:
            key = "-".join(names)
            if key in fo:
                continue
            m = np.array(fm[key])
            keep = np.all(m[:, 6:8] <= 0.9, axis=1) if sift else np.all(m[:, 6:8] >= 0.5, axis=1)
            m = m[keep]
            K1, K2 = K[names[0]], K[names[1]]
            side = 2 * max(K1[0, 2], K1[1, 2])
            f_guess = 1.25 * side
            f = None
            tic = time.perf_counter()
            if len(m) >= 8:
                F, info = poselib.estimate_fundamental(m[:, 0:2], m[:, 2:4], {"max_epipolar_error": args.threshold}, {})
                if info.get("num_inliers", 0) >= 8 and np.all(np.isfinite(F)):
                    cams = [{"model": "SIMPLE_PINHOLE", "width": int(2 * Ki[0, 2]), "height": int(2 * Ki[1, 2]),
                             "params": [f_guess, Ki[0, 2], Ki[1, 2]]} for Ki in (K1, K2)]
                    c1, c2, _ = poselib.focals_from_fundamental_iterative(F, cams[0], cams[1])
                    fc = 0.5 * (c1.focal() + c2.focal())
                    if np.isfinite(fc) and 0.1 * side < fc < 10 * side:
                        f = float(fc)
            ms.append(1000 * (time.perf_counter() - tic))
            if f is None:
                f, n_fb = f_guess, n_fb + 1
            fo.create_dataset(key, data=np.array([f]))
            n_new += 1
        fo.attrs["fallbacks"] = int(fo.attrs.get("fallbacks", 0)) + n_fb
        total = sum(1 for _ in lines)
    if ms:
        with open(f"{out}.times.txt", "a") as ft:
            ft.write(f"{n_new} {float(np.mean(ms)):.4f}\n")
    print(f"{args.triplet_dir.name} {args.feature}: {n_new} new of {total} triplets, {n_fb} fallbacks, "
          f"{np.mean(ms) if ms else 0:.2f} ms each")


if __name__ == "__main__":
    main()
