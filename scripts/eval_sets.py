"""Evaluation sets of draft v5 Sec. 5 from the Task 2.8 labels (scripts/outlier_stats.py triplets.csv).

Sets (scripts/mr_config.py SETS), all without the tuning scene (courtyard):
  sift       guarded SIFT triplets, every inlier ratio: at least --min-inliers inlier tracks and an SP+LG inlier ratio
             above --sp-ratio for the same triplet under the same reference cameras (the guard of outlier_stats.py)
  sift_low   the guarded SIFT triplets with w < --w-max (the primary low-inlier set)
  splg       SP+LG triplets, at most --splg-n per scene (seeded draw)
  sift_time  --time-n triplets of sift_low, stratified by scene (single-core timing)
  splg_time  --time-n triplets of splg, stratified by scene
Each set is a folder per scene, <out>/<set>/<scene>/, that eval_f.py and eval.py read like a triplet folder: links to
K.h5, R.h5, T.h5 and the feature's .h5, and the feature's .txt with the set's triplets in their original order (so
eval_f.py's score filter, which depends on the feature name, is unchanged). Links are symbolic (copies where
symbolic links are not allowed). Also writes <out>/labels.csv (set, dataset, scene, matcher, triplet, a, b, w, n,
n_inl) and <out>/manifest.json (settings and counts).

  python scripts/eval_sets.py --labels results/task28/triplets.csv --cambridge $SSD/data/cambridge_triplets \
      --eth3d $SSD/data/eth3d_triplets --out results/sets
"""
import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from outlier_stats import SIFT, SP, TUNING  # noqa: E402


def link(src, dst):
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(src, dst)


def stratified(rows_by_scene, n, rng):
    """About n rows in total, spread over scenes in proportion to their size (at least one per non-empty scene)."""
    total = sum(len(r) for r in rows_by_scene.values())
    out = {}
    for s, r in rows_by_scene.items():
        k = min(len(r), max(1, round(n * len(r) / total))) if r else 0
        out[s] = [r[i] for i in sorted(rng.choice(len(r), k, replace=False))] if k else []
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", type=Path, required=True, help="outlier_stats.py triplets.csv")
    ap.add_argument("--cambridge", type=Path)
    ap.add_argument("--eth3d", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--theta", type=float, default=2.0)
    ap.add_argument("--min-inliers", type=int, default=12)
    ap.add_argument("--sp-ratio", type=float, default=0.5)
    ap.add_argument("--w-max", type=float, default=0.4)
    ap.add_argument("--splg-n", type=int, default=1000)
    ap.add_argument("--time-n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    roots = {"cambridge": args.cambridge, "eth3d": args.eth3d}
    rows = [r for r in csv.DictReader(open(args.labels, newline=""))
            if abs(float(r["theta"]) - args.theta) < 1e-9 and r["scene"] != TUNING and roots.get(r["dataset"])]
    for r in rows:
        for k in ("a", "b", "w"):
            r[k] = float(r[k])
        for k in ("n", "n_inl"):
            r[k] = int(r[k])
    sp = {(r["scene"], r["triplet"]): r for r in rows if r["matcher"] == "SP+LG"}
    scenes = sorted({(r["dataset"], r["scene"]) for r in rows}, key=lambda x: (x[0], x[1]))

    def by_scene(pred, matcher):
        return {s: [r for r in rows if r["scene"] == s and r["matcher"] == matcher and pred(r)] for _, s in scenes}

    guard = lambda r: r["n_inl"] >= args.min_inliers and (r["scene"], r["triplet"]) in sp \
        and sp[r["scene"], r["triplet"]]["w"] > args.sp_ratio
    sets = {"sift": (by_scene(guard, "SIFT"), SIFT),
            "sift_low": (by_scene(lambda r: guard(r) and r["w"] < args.w_max, "SIFT"), SIFT)}
    rng = np.random.default_rng(args.seed)
    splg_all = by_scene(lambda r: True, "SP+LG")
    sets["splg"] = ({s: [r[i] for i in sorted(rng.choice(len(r), min(len(r), args.splg_n), replace=False))]
                     if r else [] for s, r in splg_all.items()}, SP)
    sets["sift_time"] = (stratified(sets["sift_low"][0], args.time_n, rng), SIFT)
    sets["splg_time"] = (stratified(sets["splg"][0], args.time_n, rng), SP)

    manifest = dict(settings={k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}, sets={})
    label_rows = []
    for name, (per_scene, feat) in sets.items():
        manifest["sets"][name] = dict(feature=feat, scenes={})
        for dataset, s in scenes:
            chosen = per_scene.get(s) or []
            if not chosen:
                continue
            src = roots[dataset] / s
            dst = args.out / name / s
            dst.mkdir(parents=True, exist_ok=True)
            for f in ("K.h5", "R.h5", "T.h5", f"{feat}.h5"):
                link(src / f, dst / f)
            keep = {r["triplet"] for r in chosen}
            order = [l for l in (src / f"{feat}.txt").read_text().splitlines() if l.strip() and l.strip() in keep]
            (dst / f"{feat}.txt").write_text("".join(l.strip() + "\n" for l in order))
            manifest["sets"][name]["scenes"][s] = dict(dataset=dataset, triplets=len(order), dir=str(dst))
            label_rows += [dict(set=name, dataset=dataset, scene=s, matcher=r["matcher"], triplet=r["triplet"],
                                a=r["a"], b=r["b"], w=r["w"], n=r["n"], n_inl=r["n_inl"]) for r in chosen]
        n = sum(v["triplets"] for v in manifest["sets"][name]["scenes"].values())
        manifest["sets"][name]["triplets"] = n
        print(f"{name}: {n} triplets in {len(manifest['sets'][name]['scenes'])} scenes", flush=True)
    with open(args.out / "labels.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(label_rows[0]))
        wr.writeheader()
        wr.writerows(label_rows)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
