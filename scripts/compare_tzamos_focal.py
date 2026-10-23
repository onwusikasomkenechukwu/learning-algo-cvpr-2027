"""Pool the shared-focal results of Tzamos et al.'s eval_f.py (run per scene by scripts/run_abl_dell.sh) per dataset,
as their utils/tables_f.py does: error = max(mean rotation error, mean translation error) over pairs
(1,2) and (1,3), NaN -> 180; AUC@k = mean over integer thresholds 1..k deg of the fraction below, in
percent; ms = mean wall time per RANSAC call. Adds the focal error eval_f.py records (|f - f_gt| / f_gt
of view 1): median in percent and the fraction below 5% / 10%.

    python scripts/compare_tzamos_focal.py                       # SuperPoint + LightGlue
    python scripts/compare_tzamos_focal.py --feat triplets-SIFT_triplet_correspondences-rootsift8000
    python scripts/compare_tzamos_focal.py --tag 1core            # runs made with eval_f.py --tag 1core
"""
import argparse
import json
from pathlib import Path

import numpy as np

DATASETS = {
    "Cambridge": ["GreatCourt", "KingsCollege", "OldHospital", "ShopFacade", "StMarysChurch"],
    "ETH3D": ["courtyard", "delivery_area", "electro", "kicker", "meadow", "office", "pipes", "playground",
              "relief", "relief_2", "terrace", "terrains"],
    "PhotoTourism": ["brandenburg_gate", "buckingham_palace", "colosseum_exterior", "grand_place_brussels",
                     "notre_dame_front_facade", "palace_of_westminster", "pantheon_exterior", "reichstag",
                     "sacre_coeur", "taj_mahal", "temple_nara_japan", "trevi_fountain"],
    "Aachen": ["aachen_v1.1"],
}
# Row order of their tables_f.py first, anything else after it.
ORDER = ["6p3v", "6p3v + R", "6p3v + R + C", "4p3v(M)", "4p3v(M) + R", "4p3v(M) + R + C", "4p3v(M) + C",
         "4p3v(M-D)", "4p3v(M-D) + R", "4p3v(M-D) + R + C", "4p3v(M-D) + C"]


def err(r):
    return max(0.5 * (r["R_12_err"] + r["R_13_err"]), 0.5 * (r["t_12_err"] + r["t_13_err"]))


def row(rows):
    e = np.array([err(r) for r in rows], dtype=float)
    e[np.isnan(e)] = 180
    frac = np.array([np.mean(e < t) for t in range(1, 21)])
    f = np.array([r["f_err"] for r in rows], dtype=float)
    f[np.isnan(f)] = 1.0
    ok = [r["info"]["runtime"] for r in rows if not r.get("crashed")]   # crashed rows carry a copied runtime
    ms = np.mean(ok) if ok else float("nan")
    return [e.mean(), np.median(e), 100 * frac[:5].mean(), 100 * frac[:10].mean(), 100 * frac.mean(), ms,
            100 * np.median(f), 100 * np.mean(f < 0.05), 100 * np.mean(f < 0.10)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir", nargs="?", type=Path,
                    default=Path(__file__).resolve().parents[1] / "third_party/threeview/results")
    ap.add_argument("--feat", default="triplets-features_superpoint_800_2048-LG")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    tag = f"-{args.tag}" if args.tag else ""
    for ds, scenes in DATASETS.items():
        results, found = [], []
        for sc in scenes:
            p = args.results_dir / f"focal_{sc}{tag}-{args.feat}.json"
            if p.exists():
                results += json.loads(p.read_text())
                found.append(sc)
        if not found:
            continue
        missing = sorted(set(scenes) - set(found))
        print(f"\n{ds}: {len(found)}/{len(scenes)} scenes, {args.feat}"
              + (f" (MISSING: {', '.join(missing)})" if missing else ""))
        print(f"{'method':<22} {'n':>6} {'AVG':>6} {'MED':>6} {'AUC@5':>6} {'@10':>6} {'@20':>6} {'ms':>7}"
              f"   {'f med%':>6} {'f<5%':>6} {'f<10%':>6}")
        exps = sorted({r["experiment"] for r in results},
                      key=lambda x: (ORDER.index(x) if x in ORDER else len(ORDER), x))
        for exp in exps:
            rows = [r for r in results if r["experiment"] == exp]
            v = row(rows)
            print(f"{exp:<22} {len(rows):>6} " + " ".join(f"{x:6.2f}" for x in v[:5]) + f" {v[5]:7.1f}"
                  + "   " + " ".join(f"{x:6.2f}" for x in v[6:]))


if __name__ == "__main__":
    main()
