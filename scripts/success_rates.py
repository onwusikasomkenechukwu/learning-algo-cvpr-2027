"""Task 2.8 step 3 (student instructions v5): success rates and hypothesis counts per clean minimal sample on the
tuning data, the inputs s and h of the cost model (draft v4 Sec. 5) for 6pt+P3P, 4p3vf(M), ours, 4p3vf(M) with
the two-view refit and each stage of the sequential pipeline.

For each triplet (one sample per triplet) the inlier tracks are labelled against the reference cameras as in
scripts/outlier_stats.py, then
  6pt+P3P   six random inlier tracks: every root of the shared-focal six-point solver on views 1-2, every P3P
            pose of view 3 on tracks 1-3 (as the PoseLib fork does) -> hypotheses (h_6);
  seeds     four random inlier tracks: the 4p3vf(M) mean-point seeds (h_M);
  endpoints if no seed succeeds: single-path continuation from the seeds in order of path length, at most
            B = 3 paths, keeping accepted endpoints.
Success means local optimization from a hypothesis ends within 2 degrees (rotation, pairs 1-2 and 1-3) with a
relative focal error below 0.1 (draft Sec. 6.2). Local optimization here is a stand-in for PoseLib's LO: a
Levenberg-Marquardt fit of f and the poses of views 2 and 3 to the Sampson errors of pairs 1-2, 1-3 and 2-3
over the triplet's reference-labelled inlier tracks (oracle inliers), so the rates bound what LO can reach from
each hypothesis. s_6 and s_M are success probabilities per clean sample; s_E is the probability that the
endpoints succeed when every seed fails. Python timings are reported for reference only; the cost model takes
per-sample times from eval_f.py runs in C++ (scripts/crossovers.py).

  python scripts/success_rates.py --scene $SSD/data/eth3d_triplets/courtyard --n 500 --out results/task28/success.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fourp3vf as M  # noqa: E402
from homotopy_proto import check_endpoint, run_cont  # noqa: E402
from outlier_stats import label_tracks, read_nvm_radial  # noqa: E402

SP = "triplets-features_superpoint_800_2048-LG"


def skew(t):
    return np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]])


def sampson(F, xi, xj):
    hi, hj = np.column_stack([xi, np.ones(len(xi))]), np.column_stack([xj, np.ones(len(xj))])
    Fx, Ftx = hi @ F.T, hj @ F
    return np.einsum("ni,ni->n", hj, Fx) / np.sqrt(Fx[:, 0] ** 2 + Fx[:, 1] ** 2 + Ftx[:, 0] ** 2 + Ftx[:, 1] ** 2)


def local_opt(f0, R2, t2, R3, t3, x):
    """LO stand-in: fit f, (R2, t2), (R3, t3) to the Sampson errors of the three pairs over the inlier tracks x
    (3, N, 2), normalized coordinates. Returns (f, R2, R3) or None."""
    s = np.linalg.norm(t2)
    if not (np.isfinite(f0) and f0 > 0 and s > 0):
        return None
    t2, t3 = t2 / s, t3 / s
    e1 = np.cross(t2, [1.0, 0, 0] if abs(t2[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(t2, e1)

    def unpack(q):
        a = t2 + q[4] * e1 + q[5] * e2
        return (f0 * np.exp(q[0]), Rotation.from_rotvec(q[1:4]).as_matrix() @ R2, a / np.linalg.norm(a),
                Rotation.from_rotvec(q[6:9]).as_matrix() @ R3, t3 + q[9:12])

    def res(q):
        f, Ra, ta, Rb, tb = unpack(q)
        Ki = np.diag([1 / f, 1 / f, 1.0])
        Rab, tab = Rb @ Ra.T, tb - Rb @ Ra.T @ ta
        return np.concatenate([sampson(Ki @ skew(t) @ R @ Ki, x[i], x[j])
                               for (i, j), (R, t) in (((0, 1), (Ra, ta)), ((0, 2), (Rb, tb)), ((1, 2), (Rab, tab)))])

    if len(x[0]) * 3 < 12 or not np.isfinite(res(np.zeros(12))).all():
        return None
    sol = least_squares(res, np.zeros(12), method="lm", max_nfev=200)
    f, Ra, _, Rb, _ = unpack(sol.x)
    return f, Ra, Rb


def success(hyp, x_inl, inst):
    out = local_opt(*hyp, x_inl)
    if out is None:
        return False
    f, Ra, Rb = out
    rerr = max(M.rot_err_deg(Ra, inst["R"][1]), M.rot_err_deg(Rb, inst["R"][2]))
    return bool(rerr < 2 and abs(f - inst["f"]) / inst["f"] < 0.1)


def two_view_lo(f0, R2, t2, x):
    """Sampson LM over pair 1-2 only (stage 1 of the sequential pipeline): (f, R2, t2) or None."""
    s = np.linalg.norm(t2)
    if not (np.isfinite(f0) and f0 > 0 and s > 0) or len(x[0]) < 6:
        return None
    t2 = t2 / s
    e1 = np.cross(t2, [1.0, 0, 0] if abs(t2[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(t2, e1)

    def unpack(q):
        a = t2 + q[4] * e1 + q[5] * e2
        return f0 * np.exp(q[0]), Rotation.from_rotvec(q[1:4]).as_matrix() @ R2, a / np.linalg.norm(a)

    def res(q):
        f, R, t = unpack(q)
        Ki = np.diag([1 / f, 1 / f, 1.0])
        return sampson(Ki @ skew(t) @ R @ Ki, x[0], x[1])

    if not np.isfinite(res(np.zeros(6))).all():
        return None
    return unpack(least_squares(res, np.zeros(6), method="lm", max_nfev=200).x)


def refit_hypotheses(x4, x_all, thr):
    """4p3vf(M) with the two-view refit as built into the fork (poselib_shared_focal_refit.py): for every
    six-point root of the four tracks plus the two mean points, the tracks of views 1-2 with Sampson error below
    thr (all tracks, not oracle inliers), a Cauchy-loss LM refit of f and the two-view pose on them (at most
    25 iterations), then triangulation of tracks 1-3 of the sample and P3P on view 3."""
    m = M.mean_points(x4)
    hyps = []
    for f, R2, t2 in M.six_point_focal(np.vstack([x4[0], m[0]]), np.vstack([x4[1], m[1]])):
        if not 0.05 < f < 20:
            continue
        Ki = np.diag([1 / f, 1 / f, 1.0])
        sel = np.abs(sampson(Ki @ skew(t2) @ R2 @ Ki, x_all[0], x_all[1])) < thr
        if sel.sum() >= 6:
            s = np.linalg.norm(t2)
            tn = t2 / s
            e1 = np.cross(tn, [1.0, 0, 0] if abs(tn[0]) < 0.9 else [0, 1.0, 0])
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(tn, e1)
            xa, xb = x_all[0][sel], x_all[1][sel]

            def unpack(q):
                a = tn + q[4] * e1 + q[5] * e2
                return f * np.exp(q[0]), Rotation.from_rotvec(q[1:4]).as_matrix() @ R2, s * a / np.linalg.norm(a)

            def res(q):
                ff, R, t = unpack(q)
                K2 = np.diag([1 / ff, 1 / ff, 1.0])
                return sampson(K2 @ skew(t) @ R @ K2, xa, xb)

            if np.isfinite(res(np.zeros(6))).all():
                f, R2, t2 = unpack(least_squares(res, np.zeros(6), method="trf", loss="cauchy", f_scale=thr,
                                                 max_nfev=25).x)
        X = M.triangulate(f, R2, t2, x4[0][:3], x4[1][:3])
        for R3, t3 in M.p3p(X, x4[2][:3], f):
            hyps.append((f, R2, t2, R3, t3))
    return hyps


def six_point_hypotheses(x6):
    """(f, R2, t2, R3, t3) for every six-point root and every P3P pose of view 3 on tracks 1-3."""
    hyps = []
    for f, R2, t2 in M.six_point_focal(x6[0], x6[1]):
        if not 0.05 < f < 20:
            continue
        X = M.triangulate(f, R2, t2, x6[0][:3], x6[1][:3])
        for R3, t3 in M.p3p(X, x6[2][:3], f):
            hyps.append((f, R2, t2, R3, t3))
    return hyps


def load_triplets(scene, feature, theta, radial, maxside=800):
    """Yield (instance dict, all tracks x (3, N, 2) normalized, inlier mask) per triplet in a shuffled order."""
    import h5py
    K, R, T = (M._h5_flat(scene / f"{n}.h5") for n in ("K", "R", "T"))
    trip = [l.split() for l in (scene / f"{feature}.txt").read_text().splitlines() if l.strip()]
    with h5py.File(scene / f"{feature}.h5", "r") as fm:
        for names in (trip[i] for i in np.random.default_rng(0).permutation(len(trip))):
            m = np.array(fm["-".join(names)])
            m = m[np.all(m[:, 6:8] >= 0.5, axis=1)]
            Ks = [K[n] for n in names]
            u = [m[:, 2 * i:2 * i + 2].copy() for i in range(3)]
            for i, n in enumerate(names):
                if radial and n in radial:
                    f_n, r = radial[n]
                    d = u[i] - Ks[i][:2, 2]
                    u[i] = Ks[i][:2, 2] + d * (1 + r * (d * d).sum(1, keepdims=True) / f_n ** 2)
            Rs, Ts = [R[n] for n in names], [T[n].reshape(3) for n in names]
            side = 2 * max(Ks[0][0, 2], Ks[0][1, 2])
            *_, inl = label_tracks(u, Ks, Rs, Ts, theta * side / maxside)
            x = np.stack([(u[i] - Ks[i][:2, 2]) / side for i in range(3)])
            Rr = np.array([Ri @ Rs[0].T for Ri in Rs])
            tr = np.array([Ts[i] - Rr[i] @ Ts[0] for i in range(3)])
            inst = dict(f=np.mean([(k[0, 0] + k[1, 1]) / 2 for k in Ks]) / side, R=Rr, t=tr, names=names, n=len(m),
                        side=side)
            yield inst, x, inl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", type=Path, required=True, help="tuning scene triplet folder (ETH3D courtyard)")
    ap.add_argument("--nvm", type=Path, help="reconstruction.nvm for undistortion (Cambridge only)")
    ap.add_argument("--feature", default=SP)
    ap.add_argument("--theta", type=float, default=2.0)
    ap.add_argument("--n", type=int, default=500, help="samples (one per triplet)")
    ap.add_argument("--budget", type=int, default=3, help="B, continuation paths per sample")
    ap.add_argument("--ransac-px", type=float, default=5.0, help="the fork's threshold (eval_f.py), full-resolution px")
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rng = np.random.default_rng(args.rng)
    radial = read_nvm_radial(args.nvm) if args.nvm else None

    rows = []
    for inst, x, inl in load_triplets(args.scene, args.feature, args.theta, radial):
        if len(rows) >= args.n:
            break
        idx = np.flatnonzero(inl)
        if len(idx) < 8:
            continue
        x_inl = x[:, idx]
        row = dict(triplet=" ".join(inst["names"]), n_tracks=inst["n"], n_inliers=int(len(idx)))
        # ceiling: does LO started at the reference cameras meet the criterion on this triplet at all?
        row["gt_ok"] = success((inst["f"], inst["R"][1], inst["t"][1], inst["R"][2], inst["t"][2]), x_inl, inst)
        t0 = time.perf_counter()
        x6 = x[:, rng.choice(idx, 6, replace=False)]
        hyps6 = six_point_hypotheses(x6)
        row["t6_ms"] = 1e3 * (time.perf_counter() - t0)
        row["h6"] = len(hyps6)
        row["s6"] = any(success(h, x_inl, inst) for h in hyps6)
        x4 = x[:, rng.choice(idx, 4, replace=False)]
        t0 = time.perf_counter()
        seeds = M.mean_point_seeds(x4)
        row["tM_ms"] = 1e3 * (time.perf_counter() - t0)
        row["hM"] = len(seeds)
        row["sM"] = any(success((s["f"], s["R"][1], s["t"][1], s["R"][2], s["t"][2]), x_inl, inst) for s in seeds)
        # 4p3vf(M) with the two-view refit, on the same four tracks (fork threshold: --ransac-px at full resolution)
        t0 = time.perf_counter()
        hypsR = refit_hypotheses(x4, x, args.ransac_px / inst["side"])
        row["tR_ms"] = 1e3 * (time.perf_counter() - t0)
        row["hR"] = len(hypsR)
        row["sR"] = any(success(h, x_inl, inst) for h in hypsR)
        # sequential pipeline, per stage: the six tracks of 6pt+P3P on views 1-2 (two-view LO over the inliers),
        # then P3P on three further inlier tracks triangulated with the first stage-1 model that succeeded
        roots = [r for r in M.six_point_focal(x6[0], x6[1]) if 0.05 < r[0] < 20]
        row["h_seq1"] = len(roots)
        good = None
        for f, R2, t2 in roots:
            lo = two_view_lo(f, R2, t2, x_inl[:2])
            if lo and M.rot_err_deg(lo[1], inst["R"][1]) < 2 and abs(lo[0] - inst["f"]) / inst["f"] < 0.1:
                good = lo
                break
        row["s_seq1"] = good is not None
        if good is not None:
            x3 = x_inl[:, rng.choice(x_inl.shape[1], 3, replace=False)]
            Xg = M.triangulate(good[0], good[1], good[2], x3[0], x3[1])
            poses = M.p3p(Xg, x3[2], good[0]) if np.isfinite(Xg).all() else []
            row["h_seq2"] = len(poses)
            row["s_seq2"] = any(success((good[0], good[1], good[2], R3, t3), x_inl, inst) for R3, t3 in poses)
        if not row["sM"] and seeds:
            ends, t0 = [], time.perf_counter()
            for s in sorted(seeds, key=lambda s: s["ell"])[:args.budget]:
                z, _ = run_cont(s, x4)
                if check_endpoint(z, x4)[0]:
                    f, poses, _ = M.poses_from_root(z, x4)
                    ends.append((f, poses[0][0], poses[0][1], poses[1][0], poses[1][1]))
            row["t_track_ms"] = 1e3 * (time.perf_counter() - t0)
            row["hE"] = len(ends)
            row["sE"] = any(success(h, x_inl, inst) for h in ends)
        rows.append(row)
        if len(rows) % 50 == 0:
            print(f"{len(rows)} samples", flush=True)

    def rate(key, subset=None):
        r = [x[key] for x in (subset if subset is not None else rows) if key in x]
        return (float(np.mean(r)), len(r)) if r else (None, 0)

    seeds_fail = [r for r in rows if not r["sM"] and r["hM"] > 0]
    ok = [r for r in rows if r["gt_ok"]]
    out = dict(scene=str(args.scene), feature=args.feature, theta=args.theta, samples=len(rows),
               lo="oracle-inlier Sampson LM over pairs 1-2, 1-3, 2-3 (stand-in for PoseLib LO)",
               ceiling=rate("gt_ok")[0],
               given_ceiling=dict(samples=len(ok), s_6=rate("s6", ok)[0], s_M=rate("sM", ok)[0],
                                  s_E=rate("sE", [r for r in seeds_fail if r["gt_ok"]])[0]),
               s_6=rate("s6")[0], s_M=rate("sM")[0], s_E=rate("sE", seeds_fail)[0], n_seeds_fail=len(seeds_fail),
               h_6=rate("h6")[0], h_M=rate("hM")[0], h_E=rate("hE", seeds_fail)[0],
               s_R=rate("sR")[0], h_R=rate("hR")[0],
               s_seq1=rate("s_seq1")[0], h_seq1=rate("h_seq1")[0],
               s_seq2=rate("s_seq2")[0], h_seq2=rate("h_seq2")[0], n_seq1_ok=rate("s_seq2")[1],
               median_tracks=float(np.median([r["n_tracks"] for r in rows])) if rows else None,
               python_ms=dict(t6=rate("t6_ms")[0], tM=rate("tM_ms")[0], tR=rate("tR_ms")[0],
                              track=rate("t_track_ms")[0]),
               rows=rows)
    out["given_ceiling"].update(s_R=rate("sR", ok)[0], s_seq1=rate("s_seq1", ok)[0],
                                s_seq2=rate("s_seq2", ok)[0])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1))
    g = out["given_ceiling"]
    print(f"{out['samples']} samples: s_6 = {out['s_6']}, s_M = {out['s_M']}, s_E = {out['s_E']} "
          f"(on {out['n_seeds_fail']} samples whose seeds all fail); h_6 = {out['h_6']}, h_M = {out['h_M']}")
    print(f"ceiling (LO from the reference cameras succeeds): {out['ceiling']}; on those {g['samples']} samples: "
          f"s_6 = {g['s_6']}, s_M = {g['s_M']}, s_E = {g['s_E']}")
    print(f"refit: s_R = {out['s_R']}, h_R = {out['h_R']}; sequential: stage 1 s = {out['s_seq1']} "
          f"(h = {out['h_seq1']}), stage 2 given stage 1 s = {out['s_seq2']} (h = {out['h_seq2']})")


if __name__ == "__main__":
    main()
