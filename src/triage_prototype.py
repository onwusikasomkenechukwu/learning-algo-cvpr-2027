"""Prototype: can a cheap classifier tell, before solving, whether a minimal sample will give a good pose?

Setting: three-view RANSAC with the 5pt+P3P minimal solver on Tzamos et al.'s PhotoTourism triplets
(real SuperPoint+LightGlue tracks with outliers). For each triplet we draw random 5-track samples,
solve each one (5pt on views 1-2, triangulate 3 of the tracks, P3P for view 3) and label the sample
GOOD if any returned solution has pose error < --good-deg (Tzamos error: max of mean R and mean t error
over pairs 1-2 and 1-3). GT is used only for labels; features use only what RANSAC sees before
solving: track positions, LightGlue scores, and sample geometry (spread, near-collinearity).

Compared rankings of the samples inside each triplet:
  random      : uniform order (plain RANSAC)
  confidence  : product of the tracks' LightGlue scores (PROSAC-style, free)
  learned     : gradient-boosted classifier on the features (trained on other scenes)
Metrics on held-out scenes: ROC AUC of good-vs-bad, and the rank of the first GOOD sample per triplet
(= how many solver calls RANSAC needs before it first sees a good model).

Usage:
  python src/triage_prototype.py generate --scenes <train+test scenes> --triplets 1000 --samples 40
  python src/triage_prototype.py evaluate --train <scenes> --test <scenes>
"""
import argparse
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import h5py
import numpy as np
import poselib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_threeview import FEATURES, load_h5_flat, rot_err, t_err  # noqa: E402

DATA = Path("data/tzamos_triplets/threeview/phototourism")
OUT = Path("results/triage")


def bearings(x, K):
    b = np.c_[(x - K[:2, 2]) / np.array([K[0, 0], K[1, 1]]), np.ones(len(x))]
    return b / np.linalg.norm(b, axis=1, keepdims=True)


def sampson_px(x1, x2, K1, K2, R, t):
    tx = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]])
    F = np.linalg.inv(K2).T @ tx @ R @ np.linalg.inv(K1)
    h1, h2 = np.c_[x1, np.ones(len(x1))], np.c_[x2, np.ones(len(x2))]
    Fx1, Ftx2 = h1 @ F.T, h2 @ F
    num = np.sum(h2 * Fx1, axis=1) ** 2
    return np.sqrt(num / (Fx1[:, 0] ** 2 + Fx1[:, 1] ** 2 + Ftx2[:, 0] ** 2 + Ftx2[:, 1] ** 2))


def triangulate(b1, b2, R, t):
    out = []
    for a, b in zip(b1, b2):
        # midpoint-free linear triangulation on bearing vectors: solve d1*a = d2*R^T(b) - R^T t
        A = np.c_[a, -(R.T @ b)]
        d, *_ = np.linalg.lstsq(A, -(R.T @ t), rcond=None)
        out.append(d[0] * a)
    return np.array(out)


def solve_sample(b1, b2, b3):
    """5pt on views 1-2, then P3P for view 3 on the first 3 tracks. Returns list of (R12,t12,R13,t13)."""
    cands = []
    for p12 in poselib.relpose_5pt(b1, b2):
        R12, t12 = p12.R, p12.t
        X = triangulate(b1[:3], b2[:3], R12, t12)
        if np.any(X[:, 2] <= 0) or np.any((X @ R12.T + t12)[:, 2] <= 0):
            continue
        for p13 in poselib.p3p(b3[:3], X):
            cands.append((R12, t12, p13.R, p13.t))
    return cands


def pose_err(c, gt):
    R12, t12, R13, t13 = c
    (G12, g12), (G13, g13) = gt
    e = [rot_err(R12, G12), rot_err(R13, G13), t_err(t12, g12), t_err(t13, g13)]
    return max(0.5 * (e[0] + e[1]), 0.5 * (e[2] + e[3]))


def features(x, scores, Ks):
    """x: (5, 6) pixel coords of the sample, scores: (5, 3) LightGlue scores. Order tracks by confidence."""
    order = np.argsort(-np.prod(scores, axis=1))
    x, scores = x[order], scores[order]
    f = []
    for v, K in enumerate(Ks):
        p = x[:, 2 * v:2 * v + 2] / (2 * K[:2, 2])  # roughly [0,1] image coordinates
        f += list(p.ravel())
        d = np.linalg.norm(p[:, None] - p[None], axis=2)[np.triu_indices(5, 1)]
        tri = 0.5 * abs(np.cross(p[1] - p[0], p[2] - p[0]))  # P3P triangle area (degeneracy)
        sv = np.linalg.svd(p - p.mean(0), compute_uv=False)
        f += [d.min(), d.mean(), tri, sv[1] / (sv[0] + 1e-12)]  # spread and collinearity
    flow = [x[:, 2:4] - x[:, 0:2], x[:, 4:6] - x[:, 0:2]]
    f += [np.std(np.linalg.norm(fl, axis=1)) / (2 * Ks[0][0, 2]) for fl in flow]
    f += list(scores.ravel()) + [np.log(scores).sum(), scores.min()]
    return np.array(f, dtype=np.float32)


def camera(K):
    return {"model": "PINHOLE", "width": int(2 * K[0, 2]), "height": int(2 * K[1, 2]),
            "params": [K[0, 0], K[1, 1], K[0, 2], K[1, 2]]}


def ransac_like_outcome(cands, x, Ks, thr_px):
    """What a RANSAC iteration would do with this sample: score every candidate by three-view inliers
    (Sampson error < thr in pairs 1-2 and 1-3, no GT), keep the best, then refine pairs 1-2 and 1-3 on
    their inliers (PoseLib LM, Cauchy loss). Returns (raw best candidate, refined candidate) or (None, None)."""
    best, best_n, best_mask = None, -1, None
    for c in cands:
        m = (sampson_px(x[:, 0:2], x[:, 2:4], Ks[0], Ks[1], c[0], c[1]) < thr_px) & \
            (sampson_px(x[:, 0:2], x[:, 4:6], Ks[0], Ks[2], c[2], c[3]) < thr_px)
        if m.sum() > best_n:
            best, best_n, best_mask = c, int(m.sum()), m
    if best is None:
        return None, None
    refined = []
    for (R, t), v in (((best[0], best[1]), 1), ((best[2], best[3]), 2)):
        init = poselib.CameraPose(); init.R = R; init.t = np.asarray(t, float).ravel()
        if best_mask.sum() >= 5:
            pose, _ = poselib.refine_relative_pose(x[best_mask, 0:2], x[best_mask, 2 * v:2 * v + 2], init,
                                                   camera(Ks[0]), camera(Ks[v]), {"loss_scale": thr_px})
            refined += [pose.R, pose.t]
        else:
            refined += [R, t]
    return best, tuple(refined)


def triplet_task(task):
    key, pts, Ks, Rs, Ts, n_samples, good_deg, seed, lo_thr = task
    keep = np.all(pts[:, 6:8] >= 0.5, axis=1)
    pts = pts[keep]
    if len(pts) < 10:
        return None
    rng = np.random.default_rng(seed)
    x, scores = pts[:, :6], np.clip(pts[:, 6:9], 1e-6, 1)
    gt = []
    for j in (1, 2):
        R = Rs[j] @ Rs[0].T
        gt.append((R, Ts[j].ravel() - R @ Ts[0].ravel()))
    inl = (sampson_px(x[:, 0:2], x[:, 2:4], Ks[0], Ks[1], *gt[0]) < 3) & \
          (sampson_px(x[:, 0:2], x[:, 4:6], Ks[0], Ks[2], *gt[1]) < 3)
    B = [bearings(x[:, 2 * v:2 * v + 2], Ks[v]) for v in range(3)]
    F, y, all_inl, conf, y_pick, y_lo = [], [], [], [], [], []
    for _ in range(n_samples):
        s = rng.choice(len(pts), 5, replace=False)
        cands = solve_sample(B[0][s], B[1][s], B[2][s])
        best = min((pose_err(c, gt) for c in cands), default=180.0)
        F.append(features(x[s], scores[s], Ks))
        y.append(best < good_deg)
        all_inl.append(bool(inl[s].all()))
        conf.append(np.log(scores[s]).sum())
        if lo_thr:
            raw, refined = ransac_like_outcome(cands, x, Ks, lo_thr)
            y_pick.append(raw is not None and pose_err(raw, gt) < good_deg)
            y_lo.append(refined is not None and pose_err(refined, gt) < good_deg)
    return (key, np.array(F), np.array(y), np.array(all_inl), np.array(conf), float(inl.mean()),
            np.array(y_pick), np.array(y_lo))


def generate(args):
    out_dir = OUT.parent / "triage_lo" if args.lo else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    for scene in args.scenes:
        out = out_dir / f"{scene}.npz"
        if out.exists():
            print(f"{scene}: exists, skipping"); continue
        d = DATA / scene
        K, R, T = (load_h5_flat(d / n) for n in ("K.h5", "R.h5", "T.h5"))
        trips = [l.split() for l in (d / f"{FEATURES}.txt").read_text().splitlines() if l.strip()][: args.triplets]
        t0 = time.time()
        with h5py.File(d / f"{FEATURES}.h5", "r") as f, Pool(args.workers) as pool:
            tasks = ((f"{a}-{b}-{c}", f[f"{a}-{b}-{c}"][()], [K[a], K[b], K[c]], [R[a], R[b], R[c]],
                      [T[a], T[b], T[c]], args.samples, args.good_deg, i, args.lo_thr if args.lo else 0)
                     for i, (a, b, c) in enumerate(trips))
            res = [r for r in pool.imap(triplet_task, tasks, chunksize=4) if r is not None]
        keys = np.repeat(np.arange(len(res)), [len(r[2]) for r in res])
        cat = lambda i: np.concatenate([r[i] for r in res])
        extra = {"y_pick": cat(6), "y_lo": cat(7)} if args.lo else {}
        np.savez_compressed(out, X=cat(1), y=cat(2), all_inl=cat(3), conf=cat(4), triplet=keys,
                            inlier_ratio=np.array([r[5] for r in res]), **extra)
        msg = f"{scene}: {len(res)} triplets, {len(cat(2))} samples, any-candidate good {cat(2).mean():.3f}"
        if args.lo:
            msg += f", raw-winner good {cat(6).mean():.3f}, after-refinement good {cat(7).mean():.3f}"
        print(f"{msg}, {time.time() - t0:.0f}s", flush=True)


def first_good_rank(score, y, trip):
    """Per triplet: 1-based position of the first GOOD sample when samples are drawn by descending score."""
    ranks = []
    for t in np.unique(trip):
        m = trip == t
        if not y[m].any():
            continue
        order = np.argsort(-score[m], kind="stable")
        ranks.append(int(np.argmax(y[m][order])) + 1)
    return np.array(ranks)


def evaluate(args):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    src = Path(args.dir)
    load = lambda s: np.load(src / f"{s}.npz")
    tr = [load(s) for s in args.train]
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=0)
    t0 = time.time()
    clf.fit(np.concatenate([d["X"] for d in tr]), np.concatenate([d[args.label] for d in tr]))
    print(f"label '{args.label}': trained on {sum(len(d['y']) for d in tr)} samples from {len(tr)} scenes "
          f"in {time.time() - t0:.0f}s")
    rng = np.random.default_rng(0)
    names = ("random", "confidence", "min-distance rule", "learned")
    report = {"train": args.train, "label": args.label, "good_deg": args.good_deg, "scenes": {}}
    for s in args.test:
        d = load(s)
        X, y, trip = d["X"], d[args.label].astype(bool), d["triplet"]
        t1 = time.perf_counter()
        learned = clf.predict_proba(X)[:, 1]
        us = 1e6 * (time.perf_counter() - t1) / len(X)
        # smallest pairwise distance between the sample's points over the three views (features 14v+10)
        min_dist = np.min(np.stack([X[:, 14 * v + 10] for v in range(3)], 1), 1)
        scores = dict(zip(names, (rng.random(len(y)), d["conf"], min_dist, learned)))
        r = {"samples": int(len(y)), "good_rate": float(y.mean()), "predict_us_per_sample": us}
        for name, sc in scores.items():
            fr = first_good_rank(sc, y, trip)
            r[name] = {"auc": float(roc_auc_score(y, sc)), "mean_first_good": float(fr.mean()),
                       "median_first_good": float(np.median(fr)), "top1_good": float((fr == 1).mean())}
        report["scenes"][s] = r
        print(f"{s:24s} good={y.mean():.3f}  " + "  ".join(
            f"{n}: AUC {r[n]['auc']:.3f} first-good {r[n]['mean_first_good']:.2f}" for n in scores), flush=True)
    agg = {n: {k: float(np.mean([report["scenes"][s][n][k] for s in args.test]))
               for k in ("auc", "mean_first_good", "top1_good")} for n in names}
    report["mean_over_test_scenes"] = agg
    for n, v in agg.items():
        print(f"MEAN {n:18s} AUC {v['auc']:.3f}  mean draws to first good {v['mean_first_good']:.2f}  "
              f"top-1 good {v['top1_good']:.3f}")
    (src / f"report_{args.label}.json").write_text(json.dumps(report, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--scenes", nargs="+", required=True)
    g.add_argument("--triplets", type=int, default=1000)
    g.add_argument("--samples", type=int, default=40)
    g.add_argument("--good-deg", type=float, default=5.0)
    g.add_argument("--workers", type=int, default=os.cpu_count())
    g.add_argument("--lo", action="store_true", help="also label by RANSAC-style scoring + refinement (to results/triage_lo)")
    g.add_argument("--lo-thr", type=float, default=5.0, help="inlier threshold in px for scoring/refinement (Tzamos: 5)")
    e = sub.add_parser("evaluate")
    e.add_argument("--train", nargs="+", required=True)
    e.add_argument("--test", nargs="+", required=True)
    e.add_argument("--good-deg", type=float, default=5.0)
    e.add_argument("--dir", default=str(OUT), help="folder with generated .npz files")
    e.add_argument("--label", default="y", choices=["y", "y_pick", "y_lo"],
                   help="y: any candidate good; y_pick: RANSAC-scored winner good; y_lo: winner good after refinement")
    args = ap.parse_args()
    generate(args) if args.cmd == "generate" else evaluate(args)


if __name__ == "__main__":
    main()
