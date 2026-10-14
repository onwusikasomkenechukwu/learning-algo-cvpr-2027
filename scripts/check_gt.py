"""Sanity-check a scene's ground truth by how well it explains the matches.

For each pair, builds F = K2^-T [t]x R K1^-1 from the GT and measures the Sampson error of
the confident matches (SNN ratio < 0.8). Correct GT gives a large fraction of matches
under 2 px; wrong conventions (transposed R, unscaled K, swapped images) give almost none.
Run on validation scenes (shipped GT) and test scenes (built GT) to compare.
Usage: python scripts/check_gt.py <scene_dir> [<scene_dir> ...]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eval_relpose import load_h5  # noqa: E402


def sampson(F, p1, p2):
    x1 = np.c_[p1, np.ones(len(p1))]
    x2 = np.c_[p2, np.ones(len(p2))]
    Fx1, Ftx2 = x1 @ F.T, x2 @ F
    num = np.sum(x2 * Fx1, axis=1) ** 2
    den = Fx1[:, 0] ** 2 + Fx1[:, 1] ** 2 + Ftx2[:, 0] ** 2 + Ftx2[:, 1] ** 2
    return np.sqrt(num / den)


for scene in map(Path, sys.argv[1:]):
    M, C, KK = load_h5(scene / "matches.h5"), load_h5(scene / "match_conf.h5"), load_h5(scene / "K1_K2.h5")
    R, T = load_h5(scene / "R.h5"), load_h5(scene / "T.h5")
    fracs = []
    for k in sorted(M)[:1000]:
        a, b = k.split("-")
        dR = R[b] @ R[a].T
        t = (T[b] - dR @ T[a]).ravel()
        tx = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]])
        K1, K2 = KK[k][0]
        F = np.linalg.inv(K2).T @ tx @ dR @ np.linalg.inv(K1)
        m = M[k][C[k] < 0.8]
        if len(m):
            fracs.append(np.mean(sampson(F, m[:, :2], m[:, 2:]) < 2.0))
    print(f"{scene.name:28s} pairs={len(fracs)} median fraction of confident matches with "
          f"Sampson error < 2 px: {np.median(fracs):.3f}")
