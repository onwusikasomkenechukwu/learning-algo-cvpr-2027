"""Three-view relative pose baselines on the Tzamos et al. (CVPR 2025) triplets, using upstream PoseLib.

Data: data/tzamos_triplets/threeview/<dataset>/<scene>/ with K.h5, R.h5, T.h5 (per image,
world-to-camera) and triplets-features_superpoint_noresize_2048-LG.{h5,txt}. Each triplet
dataset is an (N, 9) array: x1 y1 x2 y2 x3 y3 + three LightGlue scores.

Protocol copied from their eval.py (kocurvik/threeview @ b43383e):
  - keep tracks whose first two scores are >= 0.5
  - epipolar threshold 1 px, RANSAC min 100 / max 1000 iterations
  - errors: R_ij error = rotation angle of R_est^T R_gt; t_ij error = angle between t_est and t_gt
    (not sign-agnostic); P_err = max(mean(R12, R13), mean(t12, t13)) ("Charalambos_P_err")
  - summary: median / mean P_err, "AUC@k" = mean over integer thresholds 1..k deg of the
    fraction of triplets below threshold (k = 5, 10, 20), reported in percent; NaN errors -> 180

Methods (their own 4p3v / 5p3v solvers need the PoseLib@threeview fork; see build_seed_code.sh):
  seq_5pt_p3p   5-point LO-RANSAC on views 1-2, triangulate inlier tracks, P3P LO-RANSAC for view 3
  pairwise_5pt  independent 5-point LO-RANSAC on pairs 1-2 and 1-3 (the angular metric ignores the
                relative scale of t12 vs t13, so this is a fair, slightly optimistic, reference)
"""
import argparse
import csv
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import h5py
import numpy as np
import poselib

FEATURES = "triplets-features_superpoint_noresize_2048-LG"


def rot_err(R_est, R_gt):
    return float(np.degrees(np.arccos(np.clip((np.trace(R_est.T @ R_gt) - 1) / 2, -1, 1))))


def t_err(t_est, t_gt):
    t_est, t_gt = np.ravel(t_est), np.ravel(t_gt)
    n = np.linalg.norm(t_est) * np.linalg.norm(t_gt)
    if n < 1e-12:
        return 180.0
    return float(np.degrees(np.arccos(np.clip(t_est @ t_gt / n, -1, 1))))


def camera(K):
    return {"model": "PINHOLE", "width": int(2 * K[0, 2]), "height": int(2 * K[1, 2]),
            "params": [K[0, 0], K[1, 1], K[0, 2], K[1, 2]]}


def triangulate(n1, n2, R, t):
    """Linear triangulation of normalized points with P1 = [I|0], P2 = [R|t]; returns X in camera-1 frame."""
    P1 = np.c_[np.eye(3), np.zeros(3)]
    P2 = np.c_[R, t]
    X = np.empty((len(n1), 3))
    for i, (a, b) in enumerate(zip(n1, n2)):
        A = np.stack([a[0] * P1[2] - P1[0], a[1] * P1[2] - P1[1], b[0] * P2[2] - P2[0], b[1] * P2[2] - P2[1]])
        Xh = np.linalg.svd(A)[2][-1]
        X[i] = Xh[:3] / Xh[3]
    return X


def normalize(x, K):
    return (x - K[:2, 2]) / np.array([K[0, 0], K[1, 1]])


def relpose(xa, xb, Ka, Kb, args):
    ransac = {"max_epipolar_error": args.threshold, "min_iterations": 100, "max_iterations": args.max_iters,
              "seed": args.seed}
    pose, info = poselib.estimate_relative_pose(xa, xb, camera(Ka), camera(Kb), ransac, {})
    return pose.R, pose.t, np.asarray(info["inliers"], dtype=bool)


def seq_5pt_p3p(x1, x2, x3, K1, K2, K3, args):
    R12, t12, inl = relpose(x1, x2, K1, K2, args)
    X = triangulate(normalize(x1[inl], K1), normalize(x2[inl], K2), R12, t12)
    depth1, depth2 = X[:, 2], (X @ R12.T + t12)[:, 2]
    ok = (depth1 > 0) & (depth2 > 0) & (depth1 < 1e3)
    if ok.sum() < 4:
        return R12, t12, np.eye(3), np.zeros(3)
    ransac = {"max_reproj_error": args.reproj_threshold, "min_iterations": 100, "max_iterations": args.max_iters,
              "seed": args.seed}
    pose3, _ = poselib.estimate_absolute_pose(x3[inl][ok], X[ok], camera(K3), ransac, {})
    return R12, t12, pose3.R, pose3.t


def pairwise_5pt(x1, x2, x3, K1, K2, K3, args):
    R12, t12, _ = relpose(x1, x2, K1, K2, args)
    R13, t13, _ = relpose(x1, x3, K1, K3, args)
    return R12, t12, R13, t13


METHODS = {"seq_5pt_p3p": seq_5pt_p3p, "pairwise_5pt": pairwise_5pt}


def run_triplet(task):
    key, pts, Ks, Rs, Ts, args = task
    keep = np.all(pts[:, 6:8] >= 0.5, axis=1)
    x1, x2, x3 = (np.ascontiguousarray(pts[keep, i:i + 2]) for i in (0, 2, 4))
    t0 = time.perf_counter()
    if keep.sum() >= 5:
        R12, t12, R13, t13 = METHODS[args.method](x1, x2, x3, *Ks, args)
    else:
        R12, t12, R13, t13 = np.eye(3), np.zeros(3), np.eye(3), np.zeros(3)
    ms = 1000 * (time.perf_counter() - t0)
    gt = {}
    for name, (i, j) in {"12": (0, 1), "13": (0, 2)}.items():
        R = Rs[j] @ Rs[i].T
        gt[name] = (R, Ts[j].ravel() - R @ Ts[i].ravel())
    e = {"R_12_err": rot_err(np.asarray(R12), gt["12"][0]), "R_13_err": rot_err(np.asarray(R13), gt["13"][0]),
         "t_12_err": t_err(t12, gt["12"][1]), "t_13_err": t_err(t13, gt["13"][1])}
    e = {k: (180.0 if np.isnan(v) else v) for k, v in e.items()}
    e["P_err"] = max(0.5 * (e["R_12_err"] + e["R_13_err"]), 0.5 * (e["t_12_err"] + e["t_13_err"]))
    return {"triplet": key, "n_tracks": int(keep.sum()), **e, "time_ms": ms}


def summarize(rows):
    errs = np.array([r["P_err"] for r in rows])
    recall = np.array([(errs < t).mean() for t in range(1, 21)])
    return {"triplets": len(rows), "median_P_err": float(np.median(errs)), "mean_P_err": float(np.mean(errs)),
            "AUC@5": 100 * float(recall[:5].mean()), "AUC@10": 100 * float(recall[:10].mean()),
            "AUC@20": 100 * float(recall.mean()), "mean_time_ms": float(np.mean([r["time_ms"] for r in rows]))}


def load_h5_flat(path):
    """{name: array} for every dataset; nested groups (Aachen's 'db/123.jpg' names) become 'db/123.jpg'."""
    out = {}
    with h5py.File(path, "r") as f:
        f.visititems(lambda name, obj: out.__setitem__(name, obj[()]) if isinstance(obj, h5py.Dataset) else None)
    return out


def scene_tasks(scene_dir, args):
    K, R, T = (load_h5_flat(scene_dir / n) for n in ("K.h5", "R.h5", "T.h5"))
    triplets = [l.split() for l in (scene_dir / f"{FEATURES}.txt").read_text().splitlines() if l.strip()]
    if args.max_triplets:
        triplets = triplets[: args.max_triplets]
    with h5py.File(scene_dir / f"{FEATURES}.h5", "r") as f:
        for a, b, c in triplets:
            key = f"{a}-{b}-{c}"
            yield key, f[key][()], [K[a], K[b], K[c]], [R[a], R[b], R[c]], [T[a], T[b], T[c]], args


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/tzamos_triplets/threeview/phototourism"))
    ap.add_argument("--scenes", nargs="*", help="default: every scene folder under --data")
    ap.add_argument("--method", choices=METHODS, default="seq_5pt_p3p")
    ap.add_argument("--threshold", type=float, default=1.0, help="epipolar threshold in px (paper: 1.0)")
    ap.add_argument("--reproj-threshold", type=float, default=2.0, help="P3P reprojection threshold in px")
    ap.add_argument("--max-iters", type=int, default=1000, help="paper: min 100, max 1000")
    ap.add_argument("--max-triplets", type=int, default=0, help="per scene, 0 = all (5,000)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--out", type=Path, default=Path("results/threeview"))
    args = ap.parse_args()

    scenes = args.scenes or sorted(p.name for p in args.data.iterdir() if (p / f"{FEATURES}.h5").exists())
    out_dir = args.out / args.data.name / f"{args.method}_th{args.threshold:g}"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary, all_rows = {"config": {k: str(v) for k, v in vars(args).items()}, "scenes": {}}, []
    with Pool(args.workers) as pool:
        for scene in scenes:
            t0 = time.time()
            rows = list(pool.imap(run_triplet, scene_tasks(args.data / scene, args), chunksize=8))
            with open(out_dir / f"{scene}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
            summary["scenes"][scene] = s = summarize(rows)
            all_rows += rows
            print(f"{scene:26s} n={s['triplets']:5d} median={s['median_P_err']:6.2f} mean={s['mean_P_err']:6.2f} "
                  f"AUC@5/10/20={s['AUC@5']:5.2f}/{s['AUC@10']:5.2f}/{s['AUC@20']:5.2f} "
                  f"{s['mean_time_ms']:.1f} ms ({time.time() - t0:.0f}s)", flush=True)
    summary["all"] = s = summarize(all_rows)
    print(f"{'ALL':26s} n={s['triplets']:5d} median={s['median_P_err']:6.2f} mean={s['mean_P_err']:6.2f} "
          f"AUC@5/10/20={s['AUC@5']:5.2f}/{s['AUC@10']:5.2f}/{s['AUC@20']:5.2f} {s['mean_time_ms']:.1f} ms")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
