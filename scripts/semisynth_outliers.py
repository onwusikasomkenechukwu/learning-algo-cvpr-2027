"""Semi-synthetic outliers (draft v5 Sec. 5.1): real Cambridge SP+LG inliers plus generated outlier tracks.

Per scene, --n (500) SP+LG triplets whose inlier ratio is above --w-min (0.8) and that have at least
--min-inliers (12) inlier tracks are drawn once with --seed; every outlier type and ratio uses the same triplets.
Labels are those of outlier_stats.py (score filter of eval_f.py, Cambridge keypoints undistorted with the NVM
radial terms, theta in pixels at the 800 px scale). The inlier tracks are kept, every other track is dropped, and
generated outlier tracks are added until the inlier ratio is w: n_out = round(n_in (1 - w) / w), for w in
--ratios (0.75 0.5 0.35 0.25). Outlier types (--types):
  whole    a random pixel in each of the three views
  view3    a random pixel of view 1, lifted to a scene depth (the depth of a random inlier of the triplet in
           view 1) and projected into view 2 with inlier noise; a random pixel in view 3
  single   the same with the random pixel in a uniformly chosen view k: the lifted pixel comes from the first of
           the two other views and is projected into the second
  mixture  per track whole / view3 / view1 / view2 in the proportions measured on the tuning scene's SIFT
           triplets (--outliers: outlier_stats.py summary.json; its 'other' share is left out, the rest renormalised)
Inlier noise is isotropic Gaussian with the RMS per-coordinate reprojection residual of the triplet's inliers in
that view. Every generated track is labelled like the real ones and redrawn until it shows its type's pattern
(whole: no pair of views consistent; wrong in view k: only the pair without k consistent), so under the labels the
inlier ratio is exact and every outlier has its type. For one triplet and type the outliers of a larger w are a
subset of those of a smaller w (one shuffled pool, prefixes), so curves over w are paired. Coordinates are
generated in undistorted pixels and written back with the NVM radial term, as the stored keypoints are. Scores
are set to 1 on every row (eval_f.py keeps them all, and PROSAC gets no ordering cue); rows are shuffled.

Output per scene in --out/<scene>: K.h5, R.h5, T.h5 (copied) and for every type and ratio
  triplets-semisynth_<type>_w<100 w>-features_superpoint_800_2048-LG.h5 / .txt   (eval_f.py's format)
  triplets-semisynth_<type>_w<100 w>-features_superpoint_800_2048-LG-labels.h5    (per row: 0 inlier,
                                                    1 / 2 / 3 wrong only in view 1 / 2 / 3, 4 whole-track)
and --out/manifest.json (settings, mixture, chosen triplets with inlier counts and noise, draws per accepted track).

  python scripts/semisynth_outliers.py --cambridge $SSD/data/cambridge_triplets --nvm-root $SSD/data/cambridge \
      --outliers results/task28/summary.json --out $SSD/data/semisynth
"""
import argparse
import json
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from outlier_stats import SP, label_tracks, read_nvm_radial, triangulate  # noqa: E402

TYPES = ("whole", "view3", "single", "mixture")
CODE = dict(view1=1, view2=2, view3=3, whole=4)
MIX_KEYS = ("whole", "view3", "view1", "view2")


def crc(s):
    return zlib.crc32(s.encode())


def feature_name(kind, w):
    return f"triplets-semisynth_{kind}_w{round(100 * w):02d}-{SP.split('-', 1)[1]}"


class View:
    """Reference camera of one view with the NVM radial term (undistorted <-> stored pixel coordinates)."""

    def __init__(self, K, R, T, radial):
        self.K, self.R, self.T = K, R, T.reshape(3)
        self.c = K[:2, 2]
        self.size = 2 * self.c                       # image width and height, as eval_f.py assumes
        self.f, self.r = radial if radial else (1.0, 0.0)

    def undistort(self, x):
        d = x - self.c
        return self.c + d * (1 + self.r * (d * d).sum(1, keepdims=True) / self.f ** 2)

    def distort(self, u):
        du = u - self.c
        d = du.copy()
        for _ in range(30):                          # fixed point of d (1 + r |d|^2 / f^2) = du
            d = du / (1 + self.r * (d * d).sum(1, keepdims=True) / self.f ** 2)
        return self.c + d

    def inside(self, x):
        return np.all((x >= 0) & (x < self.size), axis=1)

    def depth(self, X):
        return (X @ self.R.T + self.T)[:, 2]

    def project(self, X):
        C = X @ self.R.T + self.T
        with np.errstate(divide="ignore", invalid="ignore"):
            return (C @ self.K.T)[:, :2] / C[:, 2:], C[:, 2]

    def lift(self, u, z):
        ray = np.c_[u, np.ones(len(u))] @ np.linalg.inv(self.K).T
        return (ray * z[:, None] - self.T) @ self.R      # R^T (z K^-1 u - T), row-wise


def triplet_inliers(views, x, thr):
    """Inlier mask of stored tracks x[i] (N, 2), noise sigma per view and inlier depths per view."""
    u = [v.undistort(xi) for v, xi in zip(views, x)]
    *_, inl = label_tracks(u, [v.K for v in views], [v.R for v in views], [v.T for v in views], thr)
    if inl.sum() < 2:
        return inl, None, None
    P = [v.K @ np.hstack([v.R, v.T[:, None]]) for v in views]
    X = triangulate(P, [ui[inl] for ui in u])
    sigma, depth = [], []
    for v, ui in zip(views, u):
        p, z = v.project(X)
        sigma.append(float(np.sqrt(np.mean((p - ui[inl]) ** 2))))   # RMS per coordinate
        depth.append(z)
    return inl, sigma, depth


def draw(kinds, views, sigma, depth, thr, rng, max_rounds=200):
    """Outlier tracks (undistorted pixels) for the per-track kinds in `kinds`; returns u (3 arrays) and draws used."""
    n = len(kinds)
    u = [np.zeros((n, 2)) for _ in range(3)]
    todo = np.arange(n)
    draws = 0
    for _ in range(max_rounds):
        if not len(todo):
            return u, draws
        m = len(todo)
        draws += m
        cand = [v.undistort(rng.random((m, 2)) * v.size) for v in views]    # a random pixel in every view
        ok = np.ones(m, bool)
        k = kinds[todo]
        for bad in range(3):                          # tracks wrong only in view bad + 1: lift src, project to dst
            sel = np.flatnonzero(k == f"view{bad + 1}")
            if not len(sel):
                continue
            src, dst = [i for i in range(3) if i != bad]
            X = views[src].lift(cand[src][sel], rng.choice(depth[src], len(sel)))
            p, zd = views[dst].project(X)
            p = p + rng.normal(0, sigma[dst], p.shape)
            fin = np.isfinite(p).all(1)               # (non-finite ones keep the random pixel and are rejected)
            ok[sel] = fin & (zd > 0) & views[dst].inside(views[dst].distort(np.where(fin[:, None], p, 0)))
            cand[dst][sel[fin]] = p[fin]
        c12, c13, c23, inl = label_tracks(cand, [v.K for v in views], [v.R for v in views], [v.T for v in views], thr)
        good = ok & ~inl & np.select(
            [k == "whole", k == "view1", k == "view2", k == "view3"],
            [~c12 & ~c13 & ~c23, c23 & ~c12 & ~c13, c13 & ~c12 & ~c23, c12 & ~c13 & ~c23], False)
        for i in range(3):
            u[i][todo[good]] = cand[i][good]
        todo = todo[~good]
    raise RuntimeError(f"{len(todo)} of {n} outlier tracks not accepted after {max_rounds} rounds")


def kinds_for(kind, n, mixture, rng):
    if kind == "whole":
        return np.array(["whole"] * n)
    if kind == "view3":
        return np.array(["view3"] * n)
    if kind == "single":
        return rng.choice(["view1", "view2", "view3"], n)
    return rng.choice(MIX_KEYS, n, p=[mixture[k] for k in MIX_KEYS])


def scene(scene_dir, radial, args, mixture, out_root):
    import h5py
    from fourp3vf import _h5_flat
    K, R, T = (_h5_flat(scene_dir / f"{n}.h5") for n in ("K", "R", "T"))
    lines = [l for l in (scene_dir / f"{SP}.txt").read_text().splitlines() if l.strip()]
    order = np.random.default_rng([args.seed, crc(scene_dir.name)]).permutation(len(lines))
    out = out_root / scene_dir.name
    out.mkdir(parents=True, exist_ok=True)
    chosen = []
    with h5py.File(scene_dir / f"{SP}.h5", "r") as fm:
        for t in order:                               # the first --n qualifying triplets in a seeded random order
            names = lines[t].split()
            m = np.array(fm["-".join(names)])
            m = m[np.all(m[:, 6:8] >= 0.5, axis=1)]   # the score filter of eval_f.py
            if not len(m):
                continue
            views = [View(K[n], R[n], T[n], radial.get(n) if radial else None) for n in names]
            thr = args.theta * views[0].size.max() / 800
            inl, sigma, depth = triplet_inliers(views, [m[:, 2 * i:2 * i + 2] for i in range(3)], thr)
            if inl.mean() > args.w_min and inl.sum() >= args.min_inliers:
                chosen.append(dict(line=lines[t], names=names, rows=m[inl], views=views, thr=thr, sigma=sigma,
                                   depth=depth, n=len(m), n_inl=int(inl.sum())))
                if len(chosen) == args.n:
                    break
    if len(chosen) < args.n:
        print(f"{scene_dir.name}: only {len(chosen)} triplets qualify (wanted {args.n})", flush=True)
    for f in ("K", "R", "T"):
        shutil.copy2(scene_dir / f"{f}.h5", out / f"{f}.h5")

    w_min = min(args.ratios)
    files = {(k, w): (h5py.File(out / f"{feature_name(k, w)}.h5", "w"), h5py.File(out / f"{feature_name(k, w)}-labels.h5", "w"))
             for k in args.types for w in args.ratios}
    stats = {k: dict(tracks=0, draws=0) for k in args.types}
    try:
        for c in chosen:
            key = "-".join(c["names"])
            n_in = len(c["rows"])
            n_pool = round(n_in * (1 - w_min) / w_min)
            for ki, kind in enumerate(args.types):
                rng = np.random.default_rng([args.seed, crc(scene_dir.name), crc(key), ki])
                kinds = kinds_for(kind, n_pool, mixture, rng)
                u, draws = draw(kinds, c["views"], c["sigma"], c["depth"], c["thr"], rng)
                stats[kind]["tracks"] += n_pool
                stats[kind]["draws"] += draws
                pool = np.zeros((n_pool, c["rows"].shape[1]))
                for i, v in enumerate(c["views"]):
                    pool[:, 2 * i:2 * i + 2] = v.distort(u[i])
                codes = np.array([CODE[k] for k in kinds], np.int8)
                for w in args.ratios:
                    n_out = round(n_in * (1 - w) / w)
                    rows = np.vstack([c["rows"], pool[:n_out]])
                    rows[:, 6:] = 1.0
                    lab = np.r_[np.zeros(n_in, np.int8), codes[:n_out]]
                    perm = rng.permutation(len(rows))
                    fh, fl = files[kind, w]
                    fh.create_dataset(key, data=rows[perm])
                    fl.create_dataset(key, data=lab[perm])
    finally:
        for fh, fl in files.values():
            fh.close()
            fl.close()
    for k in args.types:
        for w in args.ratios:
            (out / f"{feature_name(k, w)}.txt").write_text("".join(c["line"] + "\n" for c in chosen))
    print(f"{scene_dir.name}: {len(chosen)} triplets, median {np.median([c['n_inl'] for c in chosen]):.0f} inliers, "
          + ", ".join(f"{k} {s['draws'] / max(s['tracks'], 1):.2f} draws per track" for k, s in stats.items()), flush=True)
    return dict(triplets=len(chosen), draws=stats,
                chosen=[dict(triplet=c["line"], tracks=c["n"], inliers=c["n_inl"], sigma_px=[round(s, 3) for s in c["sigma"]])
                        for c in chosen])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cambridge", type=Path, required=True, help="Cambridge triplet folders (prepare_im.py output)")
    ap.add_argument("--nvm-root", type=Path, help="Cambridge scene folders with reconstruction.nvm (undistortion)")
    ap.add_argument("--outliers", type=Path, help="outlier_stats.py summary.json (the measured mixture)")
    ap.add_argument("--scenes", nargs="*", help="default: every scene folder with SP+LG triplets")
    ap.add_argument("--types", nargs="+", default=list(TYPES), choices=TYPES)
    ap.add_argument("--ratios", nargs="+", type=float, default=[0.75, 0.5, 0.35, 0.25])
    ap.add_argument("--n", type=int, default=500, help="triplets per scene")
    ap.add_argument("--w-min", type=float, default=0.8, help="keep triplets with an inlier ratio above this")
    ap.add_argument("--min-inliers", type=int, default=12)
    ap.add_argument("--theta", type=float, default=2.0, help="label threshold, px at the 800 px scale")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    mixture = None
    if "mixture" in args.types:
        if not args.outliers or not args.outliers.exists():
            sys.exit("the mixture needs --outliers (outlier_stats.py summary.json)")
        s = json.loads(args.outliers.read_text())
        mx = s[f"theta_{args.theta}"]["mixture_tuning_sift"]
        tot = sum(mx[k] for k in MIX_KEYS)
        mixture = {k: mx[k] / tot for k in MIX_KEYS}
        print("mixture (renormalised without 'other'):", {k: round(v, 3) for k, v in mixture.items()}, flush=True)

    dirs = sorted(p for p in args.cambridge.iterdir() if (p / f"{SP}.txt").exists() and (p / "K.h5").exists())
    if args.scenes:
        dirs = [d for d in dirs if d.name in args.scenes]
    if not dirs:
        sys.exit("no scene folders with SP+LG triplets")
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = dict(settings={k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
                    mixture=mixture, features={k: {str(w): feature_name(k, w) for w in args.ratios} for k in args.types},
                    scenes={})
    for d in dirs:
        radial = read_nvm_radial(args.nvm_root / d.name / "reconstruction.nvm") if args.nvm_root else None
        manifest["scenes"][d.name] = scene(d, radial, args, mixture, args.out)
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("done:", args.out / "manifest.json")


if __name__ == "__main__":
    main()
