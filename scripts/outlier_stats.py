"""Task 2.8 steps 1, 2 and 4 (student instructions v5): where outliers sit in real triplets.

For every triplet and matcher, every track is labelled against the reference cameras (draft v4 Sec. 5):
  correct in views i-j   the point triangulated from views i and j reprojects within theta in both (and lies in
                         front of both cameras);
  inlier                 the point triangulated from all three views reprojects within theta in all three.
  a = fraction of tracks correct in views 1-2, b = fraction of those that are inliers, w = inlier ratio (= ab).
Outlier tracks are typed by which pairs stay consistent: view-3 (only 1-2 correct), view-1 (only 2-3), view-2
(only 1-3), whole-track (no pair correct), other. Matches are filtered as eval_f.py does (SP+LG: LightGlue scores
1-2 and 1-3 >= 0.5; SIFT: ratios <= 0.9), Cambridge keypoints are undistorted with the NVM radial terms, and
theta is in pixels at the paper's 800 px scale. Everything is computed at --theta and at the larger --theta2 to
bound label noise.

Outputs in --out: triplets.csv (one row per triplet, matcher and threshold), summary.json (per scene and
matcher: medians of a, b, w and track counts; the guard; the low-inlier SIFT set and its size; the outlier
mixture on the tuning scene's SIFT triplets) and histogram PNGs.

  python scripts/outlier_stats.py --cambridge $SSD/data/cambridge_triplets --nvm-root $SSD/data/cambridge \
      --eth3d $SSD/data/eth3d_triplets --out results/task28
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fourp3vf import _h5_flat  # noqa: E402

SP = "triplets-features_superpoint_800_2048-LG"
SIFT = "triplets-SIFT_triplet_correspondences-rootsift8000"
TUNING = "courtyard"
TYPES = ("view3", "view1", "view2", "whole", "other")


def read_nvm_radial(path):
    lines = Path(path).read_text().splitlines()
    i = 0
    while not lines[i].strip() or lines[i].startswith("NVM"):
        i += 1
    out = {}
    for line in lines[i + 1:i + 1 + int(lines[i])]:
        tok = line.split()
        out[tok[0].rsplit(".", 1)[0]] = (float(tok[1]), float(tok[9]))
    return out


def triangulate(Ps, us):
    """DLT for N tracks from k cameras: Ps list of 3x4, us list of (N, 2) pixel arrays."""
    rows = []
    for P, u in zip(Ps, us):
        rows += [u[:, :1] * P[2] - P[0], u[:, 1:] * P[2] - P[1]]
    X = np.linalg.svd(np.stack(rows, axis=1))[2][:, -1]
    with np.errstate(divide="ignore", invalid="ignore"):
        return X[:, :3] / X[:, 3:]


def reproj_ok(X, R, T, K, u, thr):
    C = X @ R.T + T
    with np.errstate(divide="ignore", invalid="ignore"):
        p = (C @ K.T)[:, :2] / C[:, 2:]
    return (C[:, 2] > 0) & (np.linalg.norm(p - u, axis=1) < thr)


def label_tracks(u, K, R, T, thr):
    """Boolean arrays c12, c13, c23, inlier for tracks u[i] (N, 2) in views i = 0, 1, 2."""
    P = [K[i] @ np.hstack([R[i], T[i][:, None]]) for i in range(3)]
    c = {}
    for i, j in ((0, 1), (0, 2), (1, 2)):
        X = triangulate([P[i], P[j]], [u[i], u[j]])
        c[i, j] = reproj_ok(X, R[i], T[i], K[i], u[i], thr) & reproj_ok(X, R[j], T[j], K[j], u[j], thr)
    X = triangulate(P, u)
    inl = np.logical_and.reduce([reproj_ok(X, R[i], T[i], K[i], u[i], thr) for i in range(3)])
    return c[0, 1], c[0, 2], c[1, 2], inl


def scene_rows(dataset, scene_dir, feature, thetas, radial=None, maxside=800, max_triplets=None):
    import h5py
    K, R, T = (_h5_flat(scene_dir / f"{n}.h5") for n in ("K", "R", "T"))
    lst = scene_dir / f"{feature}.txt"
    if not lst.exists():
        return []
    triplets = [l.split() for l in lst.read_text().splitlines() if l.strip()][:max_triplets]
    rows = []
    with h5py.File(scene_dir / f"{feature}.h5", "r") as fm:
        for names in triplets:
            m = np.array(fm["-".join(names)])
            keep = np.all(m[:, 6:8] <= 0.9, axis=1) if "SIFT" in feature else np.all(m[:, 6:8] >= 0.5, axis=1)
            m = m[keep]
            Ks = [K[n] for n in names]
            u = [m[:, 2 * i:2 * i + 2].copy() for i in range(3)]
            if radial:
                for i, n in enumerate(names):
                    if n in radial:
                        f, r = radial[n]
                        d = u[i] - Ks[i][:2, 2]
                        u[i] = Ks[i][:2, 2] + d * (1 + r * (d * d).sum(1, keepdims=True) / f ** 2)
            side = 2 * max(Ks[0][0, 2], Ks[0][1, 2])
            for th in thetas:
                row = dict(dataset=dataset, scene=scene_dir.name, matcher="SIFT" if "SIFT" in feature else "SP+LG",
                           triplet=" ".join(names), theta=th, n=len(m))
                if len(m):
                    c12, c13, c23, inl = label_tracks(u, Ks, [R[n] for n in names], [T[n].reshape(3) for n in names],
                                                      th * side / maxside)
                    out = ~inl
                    types = dict(view3=out & c12 & ~c13 & ~c23, view1=out & c23 & ~c12 & ~c13,
                                 view2=out & c13 & ~c12 & ~c23, whole=out & ~c12 & ~c13 & ~c23)
                    types["other"] = out & ~np.logical_or.reduce(list(types.values()))
                    n12 = int(c12.sum())
                    row.update(n12=n12, n_inl=int(inl.sum()), a=n12 / len(m),
                               b=float((inl & c12).sum() / n12) if n12 else 0.0, w=float(inl.mean()),
                               **{f"n_{k}": int(v.sum()) for k, v in types.items()})
                else:
                    row.update(n12=0, n_inl=0, a=0.0, b=0.0, w=0.0, **{f"n_{k}": 0 for k in TYPES})
                rows.append(row)
    return rows


def summarize(rows, theta, min_inl, sp_ratio, w_max, n_target):
    r = [x for x in rows if x["theta"] == theta]
    out = dict(theta=theta, per_scene={})
    for key in sorted({(x["dataset"], x["scene"], x["matcher"]) for x in r}):
        s = [x for x in r if (x["dataset"], x["scene"], x["matcher"]) == key]
        out["per_scene"]["/".join(key)] = dict(
            triplets=len(s), **{f"median_{k}": float(np.median([x[k] for x in s])) for k in ("a", "b", "w", "n", "n_inl")},
            share_w_below_0_4=float(np.mean([x["w"] < 0.4 for x in s])))
    sp = {(x["scene"], x["triplet"]): x for x in r if x["matcher"] == "SP+LG"}
    sift = [x for x in r if x["matcher"] == "SIFT" and x["scene"] != TUNING]
    guarded = [x for x in sift if x["n_inl"] >= min_inl and (x["scene"], x["triplet"]) in sp
               and sp[x["scene"], x["triplet"]]["w"] > sp_ratio]
    low = [x for x in guarded if x["w"] < w_max]
    ws = np.sort([x["w"] for x in guarded])
    w_needed = float(ws[n_target - 1]) if len(ws) >= n_target else None
    out["low_inlier"] = dict(guard=dict(min_inlier_tracks=min_inl, sp_lg_inlier_ratio_above=sp_ratio),
                             sift_triplets=len(sift), pass_guard=len(guarded), below_w=w_max, count=len(low),
                             share_of_all_sift=len(low) / len(sift) if sift else None,
                             enough=len(low) >= n_target, target=n_target,
                             # w of the n_target-th guarded triplet: the smallest threshold that yields the target
                             smallest_w_threshold_for_target=None if len(low) >= n_target or w_needed is None
                             else round(w_needed + 1e-6, 4))
    tune = [x for x in r if x["matcher"] == "SIFT" and x["scene"] == TUNING]
    tot = {k: sum(x[f"n_{k}"] for x in tune) for k in TYPES}
    n_out = sum(tot.values())
    out["mixture_tuning_sift"] = dict(scene=TUNING, triplets=len(tune), outlier_tracks=n_out,
                                      **{k: (tot[k] / n_out if n_out else None) for k in TYPES})
    return out


def plots(rows, theta, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    r = [x for x in rows if x["theta"] == theta]
    for matcher in sorted({x["matcher"] for x in r}):
        rm = [x for x in r if x["matcher"] == matcher]
        fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
        for scene in sorted({x["scene"] for x in rm}):
            ax[0].hist([x["w"] for x in rm if x["scene"] == scene], bins=40, range=(0, 1), histtype="step", label=scene)
        ax[0].axvline(0.4, color="k", ls="--", lw=0.8)
        ax[0].set_xlabel("inlier ratio w = ab")
        ax[0].legend(fontsize=6)
        ax[1].hexbin([x["a"] for x in rm], [x["b"] for x in rm], gridsize=35, extent=(0, 1, 0, 1), mincnt=1, bins="log")
        ax[1].set_xlabel("a (correct in views 1-2)")
        ax[1].set_ylabel("b (inliers among those)")
        ax[2].hist([x["n"] for x in rm], bins=50, histtype="step", label="tracks")
        ax[2].hist([x["n_inl"] for x in rm], bins=50, histtype="step", label="inlier tracks")
        ax[2].set_xlabel("tracks per triplet")
        ax[2].legend(fontsize=7)
        fig.suptitle(f"{matcher}, theta {theta} px at 800 px")
        fig.tight_layout()
        fig.savefig(out / f"hist_{matcher.replace('+', '')}_theta{theta}.png", dpi=130)
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cambridge", type=Path, help="Cambridge triplet folders (prepare_im.py output)")
    ap.add_argument("--nvm-root", type=Path, help="Cambridge scene folders with reconstruction.nvm (undistortion)")
    ap.add_argument("--eth3d", type=Path, help="ETH3D triplet folders (filtered to one intrinsics block)")
    ap.add_argument("--theta", type=float, default=2.0)
    ap.add_argument("--theta2", type=float, default=4.0)
    ap.add_argument("--min-inlier-tracks", type=int, default=12)
    ap.add_argument("--sp-ratio", type=float, default=0.5)
    ap.add_argument("--w-max", type=float, default=0.4)
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--max-triplets", type=int, default=None, help="per scene and matcher (quick checks)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    jobs = []
    for dataset, root in (("cambridge", args.cambridge), ("eth3d", args.eth3d)):
        if root and root.exists():
            for d in sorted(p for p in root.iterdir() if (p / "K.h5").exists()):
                radial = read_nvm_radial(args.nvm_root / d.name / "reconstruction.nvm") \
                    if dataset == "cambridge" and args.nvm_root else None
                for feat in (SP, SIFT):
                    jobs.append((dataset, d, feat, radial))
    rows = []
    for dataset, d, feat, radial in jobs:
        r = scene_rows(dataset, d, feat, (args.theta, args.theta2), radial, max_triplets=args.max_triplets)
        print(f"{dataset}/{d.name} {feat.split('-')[1][:20]}: {len(r) // 2} triplets", flush=True)
        rows += r
    if not rows:
        sys.exit("no triplets found")
    with open(args.out / "triplets.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    summary = {f"theta_{th}": summarize(rows, th, args.min_inlier_tracks, args.sp_ratio, args.w_max, args.target)
               for th in (args.theta, args.theta2)}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    for th in (args.theta, args.theta2):
        plots(rows, th, args.out)
    s = summary[f"theta_{args.theta}"]
    li, mx = s["low_inlier"], s["mixture_tuning_sift"]
    print(f"theta {args.theta}: {li['count']} guarded SIFT triplets with w < {args.w_max} "
          f"({li['share_of_all_sift'] or 0:.1%} of {li['sift_triplets']}); enough for the target {li['target']}: "
          f"{li['enough']}" + ("" if li["enough"] else f"; smallest w threshold giving it: "
                                                     f"{li['smallest_w_threshold_for_target']}"))
    print("outlier mixture on", mx["scene"], "SIFT:", {k: (round(mx[k], 3) if mx[k] is not None else None) for k in TYPES})


if __name__ == "__main__":
    main()
