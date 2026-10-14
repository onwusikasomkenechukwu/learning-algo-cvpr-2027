"""Python port of Hruby et al.'s 4p3v problem-solution sampler (learning_minimal/4p3v/src/data_sampler.cxx
@ 9d7739b) plus the header line their sample_data.py adds, so the output feeds their C++
connectivity / anchors / labels binaries unchanged.

For every image triplet i < j < k of a COLMAP model, points seen by all three are re-projected
exactly (noise-free) with the GT poses; 4 of them are sampled per draw; the 4-point / 3-view
problem is normalized (rays to unit sphere, centroid to the optical axis, the point farthest from
its view's centroid onto the y = 0 axis, views and points reordered) and written as one line:
  24 normalized image coords: u1..u4 v1..v4 (view 1), same for views 2 and 3
  12 depths:                  d1..d4 (view 1), views 2 and 3
  a trailing 0 (as the C++ writes)
The first line of the file is the number of samples.

Differences from the C++ (behavior otherwise identical): numpy RNG with --seed instead of
srand(time); camera ids read correctly (the C++ reads them from the wrong stream, which is harmless
because K is not used for the projections); reads text or binary models.

Usage (paper setup, Sec. 5.1: ~1M train samples per ETH3D model, 30k validation, 40k for anchors):
  python src/sample_hruby4p3v.py data/eth3d/office/dslr_calibration_undistorted results/hruby/anchor_office.txt --per-triplet 10
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colmap_io import read_model, read_points3D  # noqa: E402

ZZ = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], dtype=float)


def order_points(P, ix):
    """perm4[3] = ix, perm4[0..2] = the other points by increasing angle relative to point ix."""
    two_pi = 2 * np.arccos(-1.0)
    angle1 = np.arctan2(P[ix][1], P[ix][0])
    if angle1 < 0:
        angle1 += two_pi
    angles = [7.0] * 4
    for i in range(4):
        if i == ix:
            continue
        cur = np.arctan2(P[i][1], P[i][0])
        if cur < 0:
            cur += two_pi
        ang = cur - angle1
        if ang < 0:
            ang += two_pi
        angles[i] = ang
    perm4 = [0, 0, 0, ix]
    for i in range(3):
        nxt = min(range(4), key=lambda j: (angles[j], j))  # first index wins ties, like the C++ strict '<'
        perm4[i] = nxt
        angles[nxt] = 7.0
    return perm4


def rotation_to_axis(centroid, far_point):
    c0 = centroid / np.linalg.norm(centroid)
    c1 = np.cross(c0, far_point); c1 /= np.linalg.norm(c1)
    c2 = np.cross(c0, c1); c2 /= np.linalg.norm(c2)
    return ZZ @ np.column_stack([c0, c1, c2]).T


def normalize(views):
    """views: three lists of 4 homogeneous rays. Returns (C matrices per new view, perm3, perm4)."""
    V = [[v / np.linalg.norm(v) for v in view] for view in views]
    cent = [np.mean(view, axis=0) for view in V]
    cent = [c / np.linalg.norm(c) for c in cent]
    best, ix, view = 99999999.0, 0, 0
    for i in range(4):
        for vw in range(3):  # same check order as the C++: P, Q, R for each point
            ang = V[vw][i] @ cent[vw]
            if ang < best:
                best, ix, view = ang, i, vw
    others = [v for v in range(3) if v != view]
    a, b = others
    # The other view whose ix-ray is farther from its centroid becomes "second".
    if V[a][ix] @ cent[a] < V[b][ix] @ cent[b]:
        second, first = a, b
    else:
        second, first = b, a
    C = [rotation_to_axis(cent[v], V[v][ix]) for v in range(3)]
    rotated = [[(C[v] @ p) / (C[v] @ p)[2] for p in V[v]] for v in range(3)]
    perm3 = [0, 0, 0]
    perm3[first], perm3[second], perm3[view] = 0, 1, 2
    perm4 = order_points(rotated[view], ix)
    return [C[first], C[second], C[view]], perm3, perm4


def sample_model(model_dir, per_triplet, rng, max_triplets=0):
    cams, images = read_model(model_dir)
    X = read_points3D(model_dir)
    names = sorted(images)
    proj = []  # per image: {point_id: normalized projection} for observed points
    for n in names:
        im = images[n]
        d = {}
        for pid in im.point3D_ids:
            c = im.R @ X[int(pid)] + im.t
            d[int(pid)] = c[:2] / c[2]
        proj.append(d)
    lines, n_trip = [], 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            common_ij = proj[i].keys() & proj[j].keys()
            if not common_ij:
                continue
            for k in range(j + 1, len(names)):
                ok = sorted(common_ij & proj[k].keys())
                if not ok:
                    continue
                n_trip += 1
                if max_triplets and n_trip > max_triplets:
                    return lines
                s2 = per_triplet
                if len(ok) == 5 and per_triplet > 1:
                    s2 = 1
                elif len(ok) == 6 and per_triplet > 6:
                    s2 = 6
                elif len(ok) == 7 and per_triplet > 42:
                    s2 = 42
                elif len(ok) < 10 and per_triplet > 100:
                    s2 = 100
                for _ in range(s2):
                    smpl = rng.integers(0, len(ok), size=4)
                    if len(set(smpl.tolist())) < 4:
                        continue  # the C++ also rejects draws with repeats
                    pts = [ok[s] for s in smpl]
                    rays = [[np.r_[proj[v][p], 1.0] for p in pts] for v in (i, j, k)]
                    C, perm3, perm4 = normalize(rays)
                    cam = [0, 0, 0]
                    cam[perm3[0]], cam[perm3[1]], cam[perm3[2]] = i, j, k
                    problem, depths = np.empty(24), np.empty(12)
                    for a in range(4):
                        Xa = X[pts[perm4[a]]]
                        for v in range(3):
                            im = images[names[cam[v]]]
                            p = C[v] @ (im.R @ Xa + im.t)
                            depths[a + 4 * v] = p[2]
                            problem[a + 8 * v] = p[0] / p[2]
                            problem[a + 4 + 8 * v] = p[1] / p[2]
                    lines.append(" ".join(f"{x:.15g}" for x in np.r_[problem, depths]) + " 0")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", type=Path, help="COLMAP model folder (ETH3D: <scene>/dslr_calibration_undistorted)")
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-triplet", type=int, default=10, help="samples per image triplet (C++ argv[2])")
    ap.add_argument("--max-triplets", type=int, default=0, help="stop after this many co-visible triplets (0 = all)")
    ap.add_argument("--target", type=int, default=0,
                    help="approximate total samples wanted; like sample_data.py, a 10-per-triplet trial run sets "
                         "--per-triplet = 10 * target / trial_count + 1 (overrides --per-triplet)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    if args.target:
        trial = len(sample_model(args.model, 10, np.random.default_rng(args.seed + 1), args.max_triplets))
        args.per_triplet = int(10 * args.target / max(1, trial)) + 1
        print(f"trial run: {trial} samples at 10/triplet -> --per-triplet {args.per_triplet}")
    lines = sample_model(args.model, args.per_triplet, rng, args.max_triplets)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(f"{len(lines)}\n" + "\n".join(lines) + "\n")
    print(f"{args.model}: {len(lines)} problem-solution pairs -> {args.out}")


if __name__ == "__main__":
    main()
