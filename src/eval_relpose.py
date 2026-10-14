"""Calibrated relative pose (5-point RANSAC) baseline on the CVPR 2020 RANSAC tutorial data.

Each scene folder holds matches.h5, match_conf.h5, K1_K2.h5, R.h5, T.h5 keyed by
"<img1>-<img2>" (pairs) or "<img>" (absolute poses). Ground truth relative pose
follows the tutorial notebook: dR = R2 R1^T, dT = T2 - dR T1.

Metrics: rotation geodesic error and translation direction error (sign-agnostic),
both in degrees. A pair's pose error is max(err_R, err_t). Reported:
  - mAA@10: mean over thresholds 1..10 deg of the fraction of pairs under threshold
    (the RANSAC tutorial / IMC 2020 metric)
  - AUC@5/10/20: area under the recall curve (SuperGlue-style, used by newer papers)

CPU only, no network access needed. Parallel over pairs with multiprocessing;
worker count defaults to os.cpu_count() (24 on a cluster node).
"""
import argparse
import csv
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import cv2
import h5py
import numpy as np
import poselib

cv2.setNumThreads(1)  # parallelism comes from the process pool


def load_h5(path):
    with h5py.File(path, "r") as f:
        return {k: f[k][()] for k in f.keys()}


def rotation_error_deg(R_est, R_gt):
    cos = (np.trace(R_est @ R_gt.T) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def translation_error_deg(t_est, t_gt):
    n_est, n_gt = np.linalg.norm(t_est), np.linalg.norm(t_gt)
    if n_est < 1e-12 or n_gt < 1e-12:
        return 180.0
    cos = abs(float(t_est.ravel() @ t_gt.ravel())) / (n_est * n_gt)
    return float(np.degrees(np.arccos(np.clip(cos, 0.0, 1.0))))


def pose_auc(errors, thresholds):
    """Area under the recall-vs-error curve up to each threshold (SuperGlue protocol)."""
    errors = np.sort(np.asarray(errors))
    recall = (np.arange(len(errors)) + 1) / len(errors)
    errors = np.r_[0.0, errors]
    recall = np.r_[0.0, recall]
    aucs = []
    for t in thresholds:
        last = np.searchsorted(errors, t)
        r = np.r_[recall[:last], recall[last - 1]]
        e = np.r_[errors[:last], t]
        aucs.append(float(np.trapezoid(r, x=e) / t))
    return aucs


def mean_average_accuracy(errors, thresholds=range(1, 11)):
    errors = np.asarray(errors)
    return float(np.mean([(errors < t).mean() for t in thresholds]))


def estimate_poselib(p1, p2, K1, K2, args):
    cam1 = {"model": "PINHOLE", "width": int(2 * K1[0, 2]), "height": int(2 * K1[1, 2]),
            "params": [K1[0, 0], K1[1, 1], K1[0, 2], K1[1, 2]]}
    cam2 = {"model": "PINHOLE", "width": int(2 * K2[0, 2]), "height": int(2 * K2[1, 2]),
            "params": [K2[0, 0], K2[1, 1], K2[0, 2], K2[1, 2]]}
    ransac = {"max_epipolar_error": args.threshold, "max_iterations": args.max_iters,
              "min_iterations": args.min_iters, "success_prob": 0.9999, "seed": args.seed}
    pose, info = poselib.estimate_relative_pose(p1, p2, cam1, cam2, ransac, {})
    return pose.R, pose.t, int(np.sum(info["inliers"])), int(info["iterations"])


def estimate_opencv(p1, p2, K1, K2, args, method):
    # Normalize so one essential matrix call handles two different intrinsics;
    # scale the pixel threshold by the mean focal length.
    n1 = cv2.undistortPoints(p1.reshape(-1, 1, 2), K1, None).reshape(-1, 2)
    n2 = cv2.undistortPoints(p2.reshape(-1, 1, 2), K2, None).reshape(-1, 2)
    f = 0.25 * (K1[0, 0] + K1[1, 1] + K2[0, 0] + K2[1, 1])
    E, mask = cv2.findEssentialMat(n1, n2, np.eye(3), method, 0.9999, args.threshold / f,
                                   maxIters=args.max_iters)
    if E is None or E.shape != (3, 3):
        return np.eye(3), np.zeros(3), 0, 0
    _, R, t, mask = cv2.recoverPose(E, n1, n2, np.eye(3), mask=mask)
    return R, t.ravel(), int(mask.astype(bool).sum()), 0


METHODS = {
    "poselib": estimate_poselib,
    "cv2_magsac": lambda *a: estimate_opencv(*a, cv2.USAC_MAGSAC),
    "cv2_ransac": lambda *a: estimate_opencv(*a, cv2.RANSAC),
}


def run_pair(task):
    key, m, conf, K1, K2, R_gt, t_gt, args = task
    if args.ratio < 1.0:
        keep = conf < args.ratio  # match_conf is the SNN ratio: lower is better
        m = m[keep]
    p1, p2 = np.ascontiguousarray(m[:, :2]), np.ascontiguousarray(m[:, 2:])
    t0 = time.perf_counter()
    if len(m) < 5:
        R, t, n_inl, iters = np.eye(3), np.zeros(3), 0, 0
    else:
        R, t, n_inl, iters = METHODS[args.method](p1, p2, K1, K2, args)
    dt = time.perf_counter() - t0
    err_R = rotation_error_deg(np.asarray(R), R_gt)
    err_t = translation_error_deg(np.asarray(t), t_gt)
    return {"pair": key, "n_matches": len(m), "n_inliers": n_inl, "iterations": iters,
            "err_R": err_R, "err_t": err_t, "err": max(err_R, err_t), "time_ms": 1000 * dt}


def scene_tasks(scene_dir, args):
    matches = load_h5(scene_dir / "matches.h5")
    conf = load_h5(scene_dir / "match_conf.h5")
    K1_K2 = load_h5(scene_dir / "K1_K2.h5")
    R = load_h5(scene_dir / "R.h5")
    T = load_h5(scene_dir / "T.h5")
    keys = sorted(matches)
    if args.max_pairs:
        keys = keys[: args.max_pairs]
    for k in keys:
        i1, i2 = k.split("-")
        dR = R[i2] @ R[i1].T
        dT = (T[i2] - dR @ T[i1]).ravel()
        K = K1_K2[k][0]
        yield (k, matches[k], conf[k], K[0], K[1], dR, dT, args)


def summarize(rows):
    errs = [r["err"] for r in rows]
    auc5, auc10, auc20 = pose_auc(errs, [5, 10, 20])
    return {"pairs": len(rows), "mAA@10": mean_average_accuracy(errs),
            "AUC@5": auc5, "AUC@10": auc10, "AUC@20": auc20,
            "median_err_R": float(np.median([r["err_R"] for r in rows])),
            "median_err_t": float(np.median([r["err_t"] for r in rows])),
            "mean_time_ms": float(np.mean([r["time_ms"] for r in rows]))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, type=Path, help="split dir, e.g. .../RANSAC-Tutorial-Data-ValOnly/val")
    ap.add_argument("--scenes", nargs="*", help="default: every subfolder of --data")
    ap.add_argument("--method", choices=METHODS, default="poselib")
    ap.add_argument("--threshold", type=float, default=1.0, help="epipolar inlier threshold in pixels")
    ap.add_argument("--ratio", type=float, default=1.0, help="keep matches with SNN ratio below this (1.0 = all)")
    ap.add_argument("--max-iters", type=int, default=10000)
    ap.add_argument("--min-iters", type=int, default=100)
    ap.add_argument("--max-pairs", type=int, default=0, help="limit pairs per scene (0 = all) for quick tests")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()

    scenes = args.scenes or sorted(p.name for p in args.data.iterdir() if (p / "matches.h5").exists())
    gt_files = ("matches.h5", "match_conf.h5", "K1_K2.h5", "R.h5", "T.h5")
    missing = {s: [f for f in gt_files if not (args.data / s / f).exists()] for s in scenes}
    missing = {s: m for s, m in missing.items() if m}
    if missing:
        ap.error(f"scenes without ground truth / matches (the tutorial test pack ships no GT): {missing}")
    tag = f"{args.method}_th{args.threshold:g}_r{args.ratio:g}"
    out_dir = args.out / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"config": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, "scenes": {}}
    all_rows = []
    with Pool(args.workers) as pool:
        for scene in scenes:
            t0 = time.time()
            rows = list(pool.imap(run_pair, scene_tasks(args.data / scene, args), chunksize=16))
            with open(out_dir / f"{scene}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
            summary["scenes"][scene] = s = summarize(rows)
            all_rows += rows
            print(f"{scene:28s} pairs={s['pairs']:5d} mAA@10={s['mAA@10']:.4f} AUC@5/10/20="
                  f"{s['AUC@5']:.4f}/{s['AUC@10']:.4f}/{s['AUC@20']:.4f} "
                  f"{s['mean_time_ms']:.1f} ms/pair  ({time.time() - t0:.0f}s wall)", flush=True)
    summary["all"] = s = summarize(all_rows)
    print(f"{'ALL':28s} pairs={s['pairs']:5d} mAA@10={s['mAA@10']:.4f} AUC@5/10/20="
          f"{s['AUC@5']:.4f}/{s['AUC@10']:.4f}/{s['AUC@20']:.4f}")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
