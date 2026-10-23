"""Kill test A (student instructions v5, Tasks 1.9 and 2.2): the best re-fitted mean-point variant must still
trail 6pt+P3P by at least 2.0 AUC@10 on Cambridge. Reads eval_f.py results: 6p3v and the plain mean-point rows
from focal_<scene>-<feature>.json, the re-fitted rows ('+ ENM', two-view refit) from
focal_<scene>-killA-<feature>.json.

AUC@10 per scene as compare_tzamos_focal.py (error = max(mean rotation, mean translation error) over pairs
(1,2) and (1,3), NaN -> 180, mean over integer thresholds 1..10 of the fraction below, in percent), averaged
over scenes with equal weights. The interval is a paired two-level bootstrap: scenes with replacement, then
triplets with replacement within each drawn scene, the same triplets for both methods (rows of one experiment
follow the triplet list, so they pair by position). One run per method (eval_f.py has no RANSAC seed option);
the instructions ask for three.

  python scripts/kill_test_a.py third_party/threeview/results
"""
import argparse
import json
from pathlib import Path

import numpy as np

SCENES = ["GreatCourt", "KingsCollege", "OldHospital", "ShopFacade", "StMarysChurch"]
MARGIN = 2.0


def errors(rows):
    e = np.array([max(0.5 * (r["R_12_err"] + r["R_13_err"]), 0.5 * (r["t_12_err"] + r["t_13_err"])) for r in rows],
                 dtype=float)
    e[np.isnan(e)] = 180
    return e


def below(e):
    """(n, 10) indicator of error < t for t = 1..10; AUC@10 of any subset = 100 * mean of its rows."""
    return (e[:, None] < np.arange(1, 11)[None, :]).astype(float)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir", type=Path)
    ap.add_argument("--feat", default="triplets-features_superpoint_800_2048-LG")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    per = {}   # experiment -> {scene: errors}
    for s in SCENES:
        for tag in ("", "-killA"):
            p = args.results_dir / f"focal_{s}{tag}-{args.feat}.json"
            if not p.exists():
                continue
            rows = json.loads(p.read_text())
            for exp in sorted({r["experiment"] for r in rows}):
                per.setdefault(exp, {})[s] = errors([r for r in rows if r["experiment"] == exp])
    scenes = [s for s in SCENES if "6p3v" in per and s in per["6p3v"]]
    enm = sorted(e for e in per if "+ ENM" in e and all(s in per[e] for s in scenes))
    if not scenes or not enm:
        raise SystemExit(f"need 6p3v and '+ ENM' results for the same scenes in {args.results_dir} "
                         f"(have 6p3v for {scenes}, ENM rows {sorted(e for e in per if '+ ENM' in e)})")
    missing = sorted(set(SCENES) - set(scenes))

    def pooled(exp):
        return float(np.mean([100 * below(per[exp][s]).mean() for s in scenes]))

    print(f"Kill test A on {len(scenes)}/{len(SCENES)} Cambridge scenes"
          + (f" (MISSING: {', '.join(missing)})" if missing else "") + f", {args.feat}, one run")
    print(f"{'method':<28}" + "".join(f"{s[:10]:>11}" for s in scenes) + f"{'mean':>9}")
    shown = ["6p3v"] + sorted(e for e in per if e.startswith("4p3v(M") and all(s in per[e] for s in scenes))
    for exp in shown:
        print(f"{exp:<28}" + "".join(f"{100 * below(per[exp][s]).mean():11.2f}" for s in scenes)
              + f"{pooled(exp):9.2f}")

    for e in enm:   # the refit must change something, or early_nonminimal never reached the estimator
        plain = e.replace(" + ENM", "")
        if plain in per and all(len(per[plain][s]) == len(per[e][s]) and np.array_equal(per[plain][s], per[e][s])
                                for s in scenes):
            print(f"WARNING: {e} equals {plain} on every triplet: the refit had no effect (check the build)")

    best = max(enm, key=pooled)
    diff = pooled("6p3v") - pooled(best)
    rng = np.random.default_rng(args.seed)
    ind = {m: {s: below(per[m][s]) for s in scenes} for m in ("6p3v", best)}
    for s in scenes:
        if len(ind["6p3v"][s]) != len(ind[best][s]):
            raise SystemExit(f"{s}: 6p3v has {len(ind['6p3v'][s])} triplets but {best} has {len(ind[best][s])}")
    boot = np.empty(args.boot)
    for b in range(args.boot):
        d = []
        for s in rng.choice(scenes, len(scenes)):
            idx = rng.integers(0, len(ind["6p3v"][s]), len(ind["6p3v"][s]))
            d.append(100 * (ind["6p3v"][s][idx].mean() - ind[best][s][idx].mean()))
        boot[b] = np.mean(d)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    passes = diff >= MARGIN
    print(f"best re-fitted variant: {best} ({pooled(best):.2f})")
    print(f"KILL TEST A: 6p3v - best re-fitted = {diff:+.2f} AUC@10 (needs >= +{MARGIN}), "
          f"95% two-level bootstrap [{lo:+.2f}, {hi:+.2f}] -> {'PASS' if passes else 'FAIL'}"
          + ("" if not missing else " (incomplete: not all scenes)"))
    out = args.results_dir / f"kill_test_a-{args.feat}.json"
    out.write_text(json.dumps(dict(scenes=scenes, best=best, diff=diff, ci95=[lo, hi], passes=bool(passes),
                                   pooled={e: pooled(e) for e in shown + enm}, runs=1), indent=1))


if __name__ == "__main__":
    main()
