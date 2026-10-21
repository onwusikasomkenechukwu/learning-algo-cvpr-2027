"""SIFT + ratio-test correspondences for an existing set of triplets, in Tzamos et al.'s file format, for
the low-inlier setting (no learned matcher).

Reads the triplet list that datasets/prepare_im.py wrote (default: the SuperPoint + LightGlue one), so
both feature types are evaluated on exactly the same triplets and the same K/R/T files, and writes
next to it

    triplets-SIFT_triplet_correspondences-rootsift<N>.h5 / .txt

Each row is x1 y1 x2 y2 x3 y3 r12 r13 r23, with r the SNN ratio (nearest / second nearest descriptor
distance) of the 1-2, 1-3 and 2-3 matches; r23 = 1 when 2-3 nearest neighbour disagrees with the
track. Tzamos et al.'s eval.py / eval_f.py recognise the 'SIFT_triplet_correspondences' name and keep
rows with r12 <= 0.9 and r13 <= 0.9, so tracks are stored up to --max-ratio (0.95) and filtered there.
Tracks: view-1 keypoint i, its nearest neighbour j in view 2 and k in view 3 (no mutual check).

Keypoints are found on the full-resolution images, so their coordinates match K.h5 like the SuperPoint ones.

    python src/sift_triplets.py $SSD/data/cambridge_triplets/KingsCollege $SSD/data/cambridge/KingsCollege
    python src/sift_triplets.py $SSD/data/eth3d_triplets/courtyard $SSD/data/eth3d/courtyard/images -nw 48
"""
import argparse
import os
from multiprocessing import Pool
from pathlib import Path

import cv2
import h5py
import numpy as np
from tqdm import tqdm

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".JPG", ".JPEG", ".PNG")
_ctx = {}


def find_image(root, stem):
    for ext in IMAGE_EXTS:
        p = os.path.join(root, stem + ext)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"no image for {stem} under {root}")


def rootsift(path, n):
    cv2.setNumThreads(1)
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    kps, desc = cv2.SIFT_create(nfeatures=n).detectAndCompute(img, None)
    if desc is None:
        return np.zeros((0, 2), np.float32), np.zeros((0, 128), np.float32)
    desc = desc / (np.abs(desc).sum(axis=1, keepdims=True) + 1e-7)  # RootSIFT: L1-normalise, sqrt
    return np.array([k.pt for k in kps], np.float32), np.sqrt(desc).astype(np.float32)


def _extract(job):
    stem, path, n = job
    return stem, *rootsift(path, n)


def nn_ratio(d1, d2):
    """For each row of d1: index of its nearest neighbour in d2 and the SNN ratio."""
    if len(d1) == 0 or len(d2) < 2:
        return np.full(len(d1), -1), np.ones(len(d1))
    knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2)
    idx = np.array([m[0].trainIdx for m in knn])
    ratio = np.array([m[0].distance / max(m[1].distance, 1e-12) for m in knn])
    return idx, ratio


def triplet_rows(f1, f2, f3, max_ratio):
    (k1, d1), (k2, d2), (k3, d3) = f1, f2, f3
    j, r12 = nn_ratio(d1, d2)
    k, r13 = nn_ratio(d1, d3)
    jj, r23 = nn_ratio(d2, d3)
    keep = np.flatnonzero((r12 <= max_ratio) & (r13 <= max_ratio) & (j >= 0) & (k >= 0))
    j, k = j[keep], k[keep]
    s23 = np.where(jj[j] == k, r23[j], 1.0)
    return np.column_stack([k1[keep], k2[j], k3[k], r12[keep], r13[keep], s23]).astype(np.float64)


def _init(cache_path):
    cv2.setNumThreads(1)
    _ctx["cache"] = h5py.File(cache_path, "r")


def _load(stem):
    g = _ctx["cache"][stem]
    return np.array(g["kp"]), np.array(g["desc"], np.float32)


def _match(job):
    names, max_ratio = job
    return names, triplet_rows(*(_load(s) for s in names), max_ratio)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("triplet_dir", type=Path, help="folder with K.h5 / R.h5 / T.h5 and the triplet list")
    ap.add_argument("image_root", help="folder the triplet image names are relative to")
    ap.add_argument("--from-feature", default="triplets-features_superpoint_800_2048-LG",
                    help="feature file whose .txt triplet list is reused")
    ap.add_argument("--first", type=int, default=None, help="only the first N triplets (quick checks)")
    ap.add_argument("-n", "--num-features", type=int, default=8000)
    ap.add_argument("--max-ratio", type=float, default=0.95)
    ap.add_argument("-nw", "--num-workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    triplets = [l.split() for l in open(args.triplet_dir / f"{args.from_feature}.txt") if l.strip()]
    triplets = triplets[:args.first]
    stems = sorted({s for t in triplets for s in t})
    cache = args.triplet_dir / f"sift_rootsift{args.num_features}.h5"
    out = args.triplet_dir / f"triplets-SIFT_triplet_correspondences-rootsift{args.num_features}"
    print(f"{len(triplets)} triplets over {len(stems)} images from {args.from_feature}.txt")

    done = set()
    if cache.exists():
        with h5py.File(cache, "r") as fh:
            fh.visititems(lambda name, obj: done.add(name[:-len("/kp")]) if name.endswith("/kp") else None)
    todo = [(s, find_image(args.image_root, s), args.num_features) for s in stems if s not in done]
    if todo:
        with h5py.File(cache, "a") as fh, Pool(args.num_workers) as pool:
            for stem, kp, desc in tqdm(pool.imap_unordered(_extract, todo), total=len(todo), desc="RootSIFT"):
                g = fh.require_group(stem)
                g.create_dataset("kp", data=kp)
                g.create_dataset("desc", data=desc.astype(np.float16), compression="lzf")

    n_rows = []
    with h5py.File(f"{out}.h5", "w") as fo, open(f"{out}.txt", "w") as ft, \
            Pool(args.num_workers, initializer=_init, initargs=(str(cache),)) as pool:
        jobs = [(tuple(t), args.max_ratio) for t in triplets]
        for names, rows in tqdm(pool.imap(_match, jobs, chunksize=4), total=len(jobs), desc="matching"):
            if len(rows) < 10:  # prepare_im.py drops triplets with fewer than 10 tracks too
                continue
            fo.create_dataset("-".join(names), data=rows)
            ft.write(" ".join(names) + "\n")
            n_rows.append(len(rows))
    kept = np.array(n_rows)
    print(f"wrote {out}.h5: {len(kept)}/{len(triplets)} triplets, median {np.median(kept):.0f} tracks "
          f"(<= {args.max_ratio}), eval keeps r12, r13 <= 0.9")


if __name__ == "__main__":
    main()
