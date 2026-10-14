"""Sample image pairs or triplets with ground-truth poses from a COLMAP model.

Co-visibility is measured with the model's 3D points: two images share a point if both
observe it. Filters follow the seed papers' style:
  --min-shared   minimum 3D points seen by all images of the tuple
                 (SupeRANSAC on ETH3D uses pairs sharing >= 500 GT keypoints)
  --min-overlap  minimum shared / min(#points of each image) (Tzamos et al. use >= 10%)
Triplets are drawn by picking a random co-visible pair and then a third image
co-visible with both, so dense models (Aachen, PhotoTourism) never enumerate all triplets.

Output is a JSON list; each entry has the image names, per-image K (3x3), R (3x3,
world-to-camera), t (3,), the shared-point count and overlap. Relative pose for
images i, j: R_ij = R_j R_i^T, t_ij = t_j - R_ij t_i (same convention as eval_relpose.py).

Example (ETH3D, SupeRANSAC-style pairs):
  python src/sample_tuples.py data/eth3d/courtyard/dslr_calibration_undistorted \
      --size 2 --min-shared 500 --num 1000 --out results/tuples/eth3d_courtyard_pairs.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colmap_io import read_model  # noqa: E402


def covisibility_graph(images, min_shared, min_overlap):
    """Return {name: set(neighbors)} and {(a, b): shared_count} for pairs passing the filters."""
    names = sorted(images)
    # Invert observations: point id -> images observing it, then count shared points per pair.
    pt_to_imgs = {}
    for i, n in enumerate(names):
        for pid in images[n].point3D_ids:
            pt_to_imgs.setdefault(int(pid), []).append(i)
    counts = {}
    for imgs in pt_to_imgs.values():
        for x in range(len(imgs)):
            for y in range(x + 1, len(imgs)):
                key = (imgs[x], imgs[y])
                counts[key] = counts.get(key, 0) + 1
    sizes = [len(images[n].point3D_ids) for n in names]
    nbrs, shared = {n: set() for n in names}, {}
    for (i, j), c in counts.items():
        if c >= min_shared and c / max(1, min(sizes[i], sizes[j])) >= min_overlap:
            a, b = names[i], names[j]
            nbrs[a].add(b); nbrs[b].add(a)
            shared[(a, b) if a < b else (b, a)] = c
    return nbrs, shared


def tuple_stats(images, tup):
    common = images[tup[0]].point3D_ids
    for n in tup[1:]:
        common = np.intersect1d(common, images[n].point3D_ids, assume_unique=True)
    overlap = len(common) / max(1, min(len(images[n].point3D_ids) for n in tup))
    return len(common), overlap


def sample(images, size, num, min_shared, min_overlap, rng):
    nbrs, shared = covisibility_graph(images, min_shared, min_overlap)
    edges = sorted(shared)
    if size == 2:
        idx = rng.permutation(len(edges))[:num]
        return [(edges[i], shared[edges[i]], tuple_stats(images, edges[i])[1]) for i in sorted(idx)]
    out, seen = [], set()
    for i in rng.permutation(len(edges)):
        a, b = edges[i]
        third = sorted(nbrs[a] & nbrs[b])
        for c in rng.permutation(third):
            tup = tuple(sorted((a, b, str(c))))
            if tup in seen:
                continue
            seen.add(tup)
            n_common, overlap = tuple_stats(images, tup)
            if n_common >= min_shared and overlap >= min_overlap:
                out.append((tup, n_common, overlap))
                break
        if len(out) >= num:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", type=Path, help="COLMAP model folder (cameras/images .bin or .txt)")
    ap.add_argument("--size", type=int, choices=[2, 3], default=3)
    ap.add_argument("--num", type=int, default=1000, help="tuples to sample (fewer if not enough exist)")
    ap.add_argument("--min-shared", type=int, default=10)
    ap.add_argument("--min-overlap", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    cams, images = read_model(args.model)
    tuples = sample(images, args.size, args.num, args.min_shared, args.min_overlap,
                    np.random.default_rng(args.seed))
    records = []
    for names, n_common, overlap in tuples:
        ims = [images[n] for n in names]
        records.append({"images": list(names), "shared_points": int(n_common), "overlap": round(float(overlap), 4),
                        "K": [cams[im.camera_id].K.tolist() for im in ims],
                        "R": [im.R.tolist() for im in ims], "t": [im.t.tolist() for im in ims]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"model": str(args.model), "config": {k: str(v) for k, v in vars(args).items()},
                                    "tuples": records}))
    print(f"{args.model}: {len(images)} images -> {len(records)} {'pairs' if args.size == 2 else 'triplets'} "
          f"(min_shared={args.min_shared}, min_overlap={args.min_overlap}) -> {args.out}")


if __name__ == "__main__":
    main()
