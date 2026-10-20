"""Compare our run of Tzamos et al.'s own evaluation (scripts/run_tzamos_table.sh) with Table 2 of the paper.

Pools all triplets of a dataset, as their utils/tables.py does: error = max(mean rotation error, mean
translation error) over pairs (1,2) and (1,3); NaN -> 180; AUC@k = mean over integer thresholds 1..k deg
of the fraction below threshold, in percent. PhotoTourism = their 12 scenes (st_peters_square excluded).

    python scripts/compare_tzamos_table.py [results_dir]
"""
import json
import sys
from pathlib import Path

import numpy as np

FEAT = "triplets-features_superpoint_noresize_2048-LG"
DATASETS = {
    "PhotoTourism": ["brandenburg_gate", "buckingham_palace", "colosseum_exterior", "grand_place_brussels",
                     "notre_dame_front_facade", "palace_of_westminster", "pantheon_exterior", "reichstag",
                     "sacre_coeur", "taj_mahal", "temple_nara_japan", "trevi_fountain"],
    "Aachen": ["aachen_v1.1"],
}
# Tzamos et al., CVPR 2025, Table 2 (arXiv 2303.16078v5): AUC@5, @10, @20. Paper names -> code names:
# 5pt+P3P = 5p3v, +F = + C, M±δ = M-D.
PAPER = {
    "4p(HC)":                  {"PhotoTourism": (62.41, 73.53, 81.94), "Aachen": (42.28, 55.20, 66.55)},
    "5p3v":                    {"PhotoTourism": (62.93, 74.30, 83.00), "Aachen": (43.43, 56.73, 68.28)},
    "5p3v + ENM":              {"PhotoTourism": (63.77, 75.03, 83.50), "Aachen": (43.32, 56.64, 68.06)},
    "4p3v(A)":                 {"PhotoTourism": (22.91, 28.59, 35.16), "Aachen": (24.41, 31.73, 39.24)},
    "4p3v(A) + ENM":           {"PhotoTourism": (65.49, 76.47, 84.53), "Aachen": (43.62, 56.99, 68.55)},
    "4p3v(A) + R":             {"PhotoTourism": (25.86, 32.22, 39.16), "Aachen": (25.27, 32.77, 40.29)},
    "4p3v(A) + R + C":         {"PhotoTourism": (23.99, 29.97, 36.64), "Aachen": (23.94, 31.23, 38.58)},
    "4p3v(A) + R + C + ENM":   {"PhotoTourism": (65.62, 76.56, 84.55), "Aachen": (43.57, 56.95, 68.56)},
    "4p3v(M)":                 {"PhotoTourism": (60.86, 72.56, 81.73), "Aachen": (41.78, 55.06, 66.67)},
    "4p3v(M) + ENM":           {"PhotoTourism": (63.61, 74.96, 83.46), "Aachen": (43.31, 56.61, 68.08)},
    "4p3v(M) + R":             {"PhotoTourism": (63.66, 74.88, 83.37), "Aachen": (43.28, 56.39, 67.88)},
    "4p3v(M) + R + C":         {"PhotoTourism": (63.99, 75.14, 83.51), "Aachen": (43.04, 56.28, 67.73)},
    "4p3v(M) + R + C + ENM":   {"PhotoTourism": (65.18, 76.16, 84.28), "Aachen": (43.74, 57.21, 68.80)},
    "4p3v(M-D)":               {"PhotoTourism": (61.86, 73.73, 82.78), "Aachen": (42.74, 56.11, 67.74)},
    "4p3v(M-D) + ENM":         {"PhotoTourism": (64.02, 75.51, 84.01), "Aachen": (43.66, 56.99, 68.55)},
    "4p3v(M-D) + R":           {"PhotoTourism": (65.97, 77.00, 85.01), "Aachen": (43.93, 57.26, 68.82)},
    "4p3v(M-D) + R + C":       {"PhotoTourism": (65.85, 76.87, 84.90), "Aachen": (43.79, 57.17, 68.73)},
    "4p3v(M-D) + R + C + ENM": {"PhotoTourism": (66.12, 77.14, 85.15), "Aachen": (44.02, 57.42, 68.97)},
}


def err(r):
    return max(0.5 * (r["R_12_err"] + r["R_13_err"]), 0.5 * (r["t_12_err"] + r["t_13_err"]))


def aucs(errs):
    e = np.array(errs, dtype=float)
    e[np.isnan(e)] = 180
    frac = np.array([np.mean(e < t) for t in range(1, 21)])
    return 100 * frac[:5].mean(), 100 * frac[:10].mean(), 100 * frac.mean()


def runtime(rows):
    """Mean wall time per RANSAC call in ms, as recorded by eval.py (one call per worker process)."""
    return float(np.mean([r["info"]["runtime"] for r in rows]))


def main():
    rdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "third_party/threeview/results"
    for ds, scenes in DATASETS.items():
        results, missing = [], []
        for sc in scenes:
            p = rdir / f"{sc}-5.0t-{FEAT}.json"
            if p.exists():
                results += json.loads(p.read_text())
            else:
                missing.append(sc)
        print(f"\n{ds}: {len(scenes) - len(missing)}/{len(scenes)} scenes"
              + (f" (MISSING: {', '.join(missing)})" if missing else ""))
        print(f"{'method':<24} {'ours AUC@5/10/20':>20} {'ms':>6}   {'paper AUC@5/10/20':>20}   {'diff @5/10/20':>18}")
        for exp, paper in PAPER.items():
            rows = [r for r in results if r["experiment"] == exp]
            if not rows:
                continue
            o, ms = aucs([err(r) for r in rows]), runtime(rows)
            p = paper[ds]
            d = [a - b for a, b in zip(o, p)]
            print(f"{exp:<24} {o[0]:6.2f} {o[1]:6.2f} {o[2]:6.2f} {ms:6.1f}   {p[0]:6.2f} {p[1]:6.2f} {p[2]:6.2f}   "
                  f"{d[0]:+5.2f} {d[1]:+5.2f} {d[2]:+5.2f}")
        # Methods not in Table 2 (e.g. the learned (L) variants from --learning): ours only.
        for exp in sorted({r["experiment"] for r in results} - PAPER.keys()):
            rows = [r for r in results if r["experiment"] == exp]
            o, ms = aucs([err(r) for r in rows]), runtime(rows)
            print(f"{exp:<24} {o[0]:6.2f} {o[1]:6.2f} {o[2]:6.2f} {ms:6.1f}   {'(not in paper)':>20}")


if __name__ == "__main__":
    main()
