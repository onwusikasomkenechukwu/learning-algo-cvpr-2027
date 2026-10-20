"""Single-path homotopy prototype for 4p3vf on synthetic data (student instructions v5, Tasks 2.3 and 2.4 in
miniature; draft v4 Secs. 4 and 6.2). Laptop-only: numpy/scipy/OpenCV, no PoseLib, no HC library.

For each instance: 4p3vf(M) seeds (fourp3vf.mean_point_seeds), the seed with the shortest free-point path,
then six ways to finish it, all from the same seed:
  cont        real parameter homotopy on the seed surface: x(t) = (1 - t) x0 + t x, x0 = simulated start
  newton_hom  global Newton homotopy F(z; x) - (1 - t) F(z0; x), no class test along it
  lm          Levenberg-Marquardt on the reprojection error of the 4 tracks in 3 views, run to convergence
  newton      Newton's method on F(z; x) from z0
The correct root comes from five complex paths (random gamma detours) from the ground truth at noise-free
coordinates to the observed ones; samples whose paths disagree are ambiguous, and a non-real common endpoint
means no real correct root. Strict success = endpoint at the correct root (unambiguous samples with a real
reference); practical success = rotation error < 2 deg for pairs (1,2) and (1,3) and focal error < 0.1.

Settings (tolerances, step control, planarity threshold, focal range) are first guesses on synthetic data,
not tuned values. Times are Python timings on the laptop: relative and indicative only; paper timings come
from C++ on abl-dell.

Usage:
  python -I src/homotopy_proto.py --n 1000 --noise 0.5 1 2 --mode random --out results/homotopy_proto/random
  python -I src/homotopy_proto.py --n 300 --noise 1 --mode eth3d --out results/homotopy_proto/eth3d
  python -I src/homotopy_proto.py --n 100 --noise 1 --seeds disturbed --out results/homotopy_proto/disturbed
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fourp3vf as M  # noqa: E402

SETTINGS = dict(h0=0.05, h_max=0.2, h_min=1e-6, max_steps=2000, newton_iters=3, step_tol=1e-9,
                end_newton=10, end_res=1e-10, f_range=(0.1, 10.0), planar_thr=1e-3, match_tol=1e-6,
                lm_max_nfev=2000, newton_max_iter=50, n_ref_paths=5, ref_agree=1e-7, ref_real=1e-8)
S = SETTINGS


# ---------------------------------------------------------------- tracker

def track(H, z0, monitor=None):
    """Follow H(z, t) = 0 from (z0, 0) to t = 1 with an RK4 predictor and <= newton_iters Newton corrections.
    H(z, t) returns (value, H_z, H_t). Returns dict(ok, z, t, steps, reason, events)."""
    z, t, h = z0.copy(), 0.0, S["h0"]
    steps, good, events = 0, 0, []

    def tangent(zz, tt):
        _, Hz, Ht = H(zz, tt)
        return -np.linalg.solve(Hz, Ht)

    while t < 1.0:
        if steps >= S["max_steps"]:
            return dict(ok=False, z=z, t=t, steps=steps, reason="max_steps", events=events)
        if h < S["h_min"]:
            sv = np.linalg.svd(H(z, t)[1], compute_uv=False)  # a fold shows as a vanishing singular value
            return dict(ok=False, z=z, t=t, steps=steps, reason="min_step", events=events,
                        sv_ratio=float(sv[-1] / sv[0]))
        h = min(h, 1.0 - t)
        steps += 1
        try:
            k1 = tangent(z, t)
            k2 = tangent(z + 0.5 * h * k1, t + 0.5 * h)
            k3 = tangent(z + 0.5 * h * k2, t + 0.5 * h)
            k4 = tangent(z + h * k3, t + h)
            zn = z + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            converged, prev = False, np.inf
            for _ in range(S["newton_iters"]):
                val, Hz, _ = H(zn, t + h)
                dz = np.linalg.solve(Hz, val)
                zn = zn - dz
                ndz = np.linalg.norm(dz)
                if ndz > 0.5 * prev:
                    break
                prev = ndz
                if ndz <= S["step_tol"] * (1 + np.linalg.norm(zn)):
                    converged = True
                    break
        except np.linalg.LinAlgError:
            converged = False
        if not converged or not np.isfinite(zn).all():
            h *= 0.5
            good = 0
            continue
        z, t = zn, t + h
        good += 1
        if good >= 3:
            h, good = min(2 * h, S["h_max"]), 0
        if np.linalg.norm(z) > 1e8:
            return dict(ok=False, z=z, t=t, steps=steps, reason="diverged", events=events)
        if monitor is not None:
            ev = monitor(z, t)
            if ev:
                events.append(ev)
    for _ in range(S["end_newton"]):                       # final polish at t = 1
        val, Hz, _ = H(z, 1.0)
        try:
            z = z - np.linalg.solve(Hz, val)
        except np.linalg.LinAlgError:
            break
    return dict(ok=True, z=z, t=1.0, steps=steps, reason="end", events=events)


def parameter_homotopy(x0, x1, gamma=None):
    """H(z, t) = F(z; x(t)) along x(t) = x0 + phi(t)(x1 - x0), phi(t) = t (+ gamma t (1 - t) if complex)."""
    d = (x1 - x0).reshape(-1)

    def H(z, t):
        phi, dphi = (t, 1.0) if gamma is None else (t + gamma * t * (1 - t), 1 + gamma * (1 - 2 * t))
        x = x0 + phi * (x1 - x0)
        val, Jz, Jp = M.jacobians(z, x)
        return val, Jz, Jp @ d * dphi
    return H


def class_monitor(x0, x1, start_class):
    """Flag omega <= 0 and orientation-class changes (only where the tetrahedron is thick enough)."""
    state = dict(cls=start_class)

    def mon(z, t):
        if z[0].real <= 0:
            return dict(t=t, kind="omega_nonpos")
        x = x0 + t * (x1 - x0)
        P = M.camera_points(z, x)
        if M.planarity(P) > S["planar_thr"]:
            cls = M.orientation_class(z, x)
            if cls != state["cls"]:
                ev = dict(t=t, kind="class_switch", frm=state["cls"], to=cls)
                state["cls"] = cls
                return ev
        return None
    return mon


# ---------------------------------------------------------------- endpoint checks and success

def check_endpoint(z, x):
    """Acceptance tests of Sec. 4 (Tracking and checks). Returns (accepted, reason)."""
    if z is None or not np.isfinite(z).all():
        return False, "none"
    if np.abs(M.F(z, x)).max() > S["end_res"]:
        return False, "residual"
    if z[0] <= 0:
        return False, "omega"
    if not S["f_range"][0] < 1 / np.sqrt(z[0]) < S["f_range"][1]:
        return False, "f_range"
    if (M.depths(z) <= 0).any():
        return False, "depth"
    P = M.camera_points(z, x)
    if M.planarity(P) > S["planar_thr"] and M.orientation_class(z, x) != (1, 1):
        return False, "class"
    return True, "ok"


def practical(z, x, inst):
    """Rotation error < 2 deg for pairs (1,2) and (1,3) and relative focal error < 0.1."""
    if z is None or not np.isfinite(z).all() or z[0] <= 0:
        return False, None, None
    f, poses, _ = M.poses_from_root(z, x)
    rerr = max(M.rot_err_deg(poses[i][0], inst["R"][i + 1]) for i in range(2))
    ferr = abs(f - inst["f"]) / inst["f"]
    return bool(rerr < 2 and ferr < 0.1), float(rerr), float(ferr)


def same_root(z, zc):
    return z is not None and np.isfinite(z).all() and \
        np.linalg.norm(z - zc) <= S["match_tol"] * (1 + np.linalg.norm(zc))


# ---------------------------------------------------------------- methods from one seed

def run_cont(seed, x):
    mon = class_monitor(seed["x0"], x, M.orientation_class(seed["z0"], seed["x0"]))
    r = track(parameter_homotopy(seed["x0"], x), seed["z0"], mon)
    return r["z"] if r["ok"] else None, r


def run_newton_hom(seed, x):
    r0 = M.F(seed["z0"], x)

    def H(z, t):
        val, Jz, _ = M.jacobians(z, x)
        return val - (1 - t) * r0, Jz, r0
    r = track(H, seed["z0"])
    return r["z"] if r["ok"] else None, r


def run_newton(seed, x):
    z = seed["z0"].copy()
    for it in range(S["newton_max_iter"]):
        val, Jz, _ = M.jacobians(z, x)
        try:
            dz = np.linalg.solve(Jz, val)
        except np.linalg.LinAlgError:
            return None, dict(reason="singular", steps=it)
        z = z - dz
        if not np.isfinite(z).all():
            return None, dict(reason="diverged", steps=it)
        if np.linalg.norm(dz) <= 1e-12 * (1 + np.linalg.norm(z)):
            return z, dict(reason="converged", steps=it + 1)
    return None, dict(reason="max_iter", steps=S["newton_max_iter"])


def run_lm(seed, x):
    """Converged LM on the 24 reprojection residuals; 24 unknowns: f, (rotvec, t) of views 2 and 3 relative
    to the seed, track 1 = (a, b, 1) in camera 1 (fixes the scale) and tracks 2-4."""
    s = 1 / seed["X"][0, 2]
    X0, R0, t0 = seed["X"] * s, seed["R"], seed["t"] * s

    def unpack(q):
        R = [np.eye(3)] + [Rotation.from_rotvec(q[1 + 6 * i:4 + 6 * i]).as_matrix() @ R0[i + 1] for i in range(2)]
        t = [np.zeros(3)] + [t0[i + 1] + q[4 + 6 * i:7 + 6 * i] for i in range(2)]
        X = np.vstack([[q[13], q[14], 1.0], q[15:24].reshape(3, 3)])
        return q[0], np.array(R), np.array(t), X

    def res(q):
        return (M.project(*unpack(q)) - x).ravel()

    q0 = np.concatenate([[seed["f"]], np.zeros(12), X0[0, :2], X0[1:].ravel()])
    sol = least_squares(res, q0, method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=S["lm_max_nfev"])
    f, R, t, X = unpack(sol.x)
    if f <= 0:
        return None, dict(reason="f_nonpos", steps=int(sol.nfev))
    return M.root_from_scene(f, R, t, X), dict(reason=f"status{sol.status}", steps=int(sol.nfev),
                                               cost=float(sol.cost))


METHODS = dict(cont=run_cont, newton_hom=run_newton_hom, lm=run_lm, newton=run_newton)


# ---------------------------------------------------------------- correct root

def correct_root(inst, rng):
    """Common endpoint of n_ref_paths complex gamma-detour paths from the ground truth at noise-free
    coordinates to the observed ones."""
    if inst["noise_px"] == 0:
        return dict(status="ok", z=inst["z_gt"])
    ends = []
    for _ in range(S["n_ref_paths"]):
        gamma = np.exp(2j * np.pi * rng.uniform()) * rng.uniform(0.5, 2.0)
        r = track(parameter_homotopy(inst["x_gt"].astype(complex), inst["x"].astype(complex), gamma),
                  inst["z_gt"].astype(complex))
        if not r["ok"]:
            return dict(status="ambiguous", why="path_failed")
        ends.append(r["z"])
    e0 = ends[0]
    if max(np.linalg.norm(e - e0) for e in ends) > S["ref_agree"] * (1 + np.linalg.norm(e0)):
        return dict(status="ambiguous", why="disagree")
    if np.abs(e0.imag).max() > S["ref_real"] * (1 + np.linalg.norm(e0)):
        return dict(status="not_real")
    return dict(status="ok", z=e0.real)


# ---------------------------------------------------------------- experiment

def disturbed_seeds(inst, rng):
    """Task 2.3 step 9: ground truth with views 2 and 3 rotated by 1-10 degrees, moved onto the seed surface."""
    ang = np.radians(rng.uniform(1, 10))
    axis = rng.normal(size=3)
    R2 = Rotation.from_rotvec(ang * axis / np.linalg.norm(axis)).as_matrix() @ inst["R"][1]
    return M.project_onto_surface(inst["x"], inst["f"], R2, inst["t"][1])


def run_instance(inst, rng, seed_mode):
    x = inst["x"]
    row = dict(noise_px=inst["noise_px"], names=inst.get("names"))
    t0 = time.perf_counter()
    seeds = M.mean_point_seeds(x) if seed_mode == "mean" else disturbed_seeds(inst, rng)
    row["t_seed_ms"] = 1e3 * (time.perf_counter() - t0)
    row["n_seeds"] = len(seeds)
    if not seeds:
        return row
    seed = min(seeds, key=lambda s: s["ell"])
    row.update(ell_px=float(seed["ell"] * inst["maxside"]), seed_off_free=float(seed["off_free"]),
               seed_rot_err=float(max(M.rot_err_deg(seed["R"][i], inst["R"][i]) for i in (1, 2))),
               seed_f_err=float(abs(seed["f"] - inst["f"]) / inst["f"]),
               seed_planarity=float(M.planarity(M.camera_points(seed["z0"], seed["x0"]))))
    ref = correct_root(inst, rng)
    row["ref"] = ref["status"]
    zc = ref.get("z")
    if zc is not None:
        row["ref_practical"] = practical(zc, x, inst)[0]
    for name, fn in METHODS.items():
        t0 = time.perf_counter()
        z, info = fn(seed, x)
        dt = 1e3 * (time.perf_counter() - t0)
        acc, why = check_endpoint(z, x)
        prac, rerr, ferr = practical(z, x, inst)
        row[name] = dict(ms=dt, reason=info.get("reason"), steps=info.get("steps"), accepted=acc, check=why,
                         strict=bool(zc is not None and same_root(z, zc)), practical=prac, rot_err=rerr,
                         f_err=ferr, events=[e["kind"] for e in info.get("events", [])],
                         t_stop=info.get("t"), sv_ratio=info.get("sv_ratio"))
    return row


def mcnemar(rows, a, b):
    """Exact McNemar test on strict success of methods a vs b (rows with a real, unambiguous reference)."""
    n10 = sum(r[a]["strict"] and not r[b]["strict"] for r in rows)
    n01 = sum(r[b]["strict"] and not r[a]["strict"] for r in rows)
    p = binomtest(n10, n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
    return dict(a_only=n10, b_only=n01, p=p)


def summarize(rows):
    out = dict(n=len(rows), no_seed=sum(r["n_seeds"] == 0 for r in rows))
    seeded = [r for r in rows if r["n_seeds"]]
    ref_ok = [r for r in seeded if r.get("ref") == "ok"]
    out.update(ambiguous=sum(r.get("ref") == "ambiguous" for r in seeded),
               not_real=sum(r.get("ref") == "not_real" for r in seeded), n_strict=len(ref_ok),
               ref_practical=float(np.mean([r["ref_practical"] for r in ref_ok])) if ref_ok else None)
    if seeded:
        out["ell_px_pct"] = np.percentile([r["ell_px"] for r in seeded], [10, 50, 90]).tolist()
        out["seed_rot_err_med"] = float(np.median([r["seed_rot_err"] for r in seeded]))
    for m in METHODS:
        if not seeded:
            break
        out[m] = dict(strict=float(np.mean([r[m]["strict"] for r in ref_ok])) if ref_ok else None,
                      practical=float(np.mean([r[m]["practical"] for r in seeded])),
                      accepted=float(np.mean([r[m]["accepted"] for r in seeded])),
                      ms_med=float(np.median([r[m]["ms"] for r in seeded])),
                      reasons={k: sum(r[m]["reason"] == k for r in seeded)
                               for k in sorted({r[m]["reason"] for r in seeded})},
                      class_switch=sum("class_switch" in r[m]["events"] for r in seeded))
    if ref_ok:
        out["mcnemar_cont_vs_lm"] = mcnemar(ref_ok, "cont", "lm")
    return out


def environment():
    def git(*a):
        try:
            return subprocess.run(["git", *a], capture_output=True, text=True,
                                  cwd=Path(__file__).resolve().parent).stdout.strip()
        except OSError:
            return None
    import cv2
    import scipy
    return dict(commit=git("rev-parse", "--short", "HEAD"), dirty=bool(git("status", "--porcelain", "src")),
                python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                opencv=cv2.__version__, cpu=platform.processor(), machine=platform.node(), threads=1,
                omp=os.environ.get("OMP_NUM_THREADS"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=200, help="instances per noise level")
    ap.add_argument("--noise", type=float, nargs="+", default=[1.0], help="pixel noise (image side 800 px)")
    ap.add_argument("--mode", choices=["random", "eth3d", "cambridge"], default="random")
    ap.add_argument("--scene", help="Cambridge scene folder with reconstruction.nvm (--mode cambridge); real "
                                    "observations, so --noise is ignored")
    ap.add_argument("--eth3d", default="data/eth3d/courtyard/dslr_calibration_undistorted",
                    help="tuning scene for --mode eth3d (only courtyard may be used for tuning)")
    ap.add_argument("--seeds", choices=["mean", "disturbed"], default="mean")
    ap.add_argument("--thickness", type=float, default=1.0, help="< 1 makes the four points nearly coplanar")
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--out", required=True, help="output prefix; writes <out>.jsonl and <out>_summary.json")
    args = ap.parse_args()

    rng = np.random.default_rng(args.rng)
    scene = M.Eth3dScene(args.eth3d) if args.mode == "eth3d" else         M.CambridgeScene(args.scene) if args.mode == "cambridge" else None
    if args.mode == "cambridge":
        args.noise = ["real"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(args=vars(args), settings=SETTINGS, environment=environment(), levels={})
    t_start = time.time()
    with open(out.with_suffix(".jsonl"), "w") as fh:
        for noise in args.noise:
            rows = []
            for k in range(args.n):
                inst = scene.instance(rng, noise, args.thickness) if scene else \
                    M.random_instance(rng, noise, args.thickness)
                row = run_instance(inst, rng, args.seeds)
                row["k"] = k
                rows.append(row)
                fh.write(json.dumps(row) + "\n")
            s = summarize(rows)
            summary["levels"][str(noise)] = s
            print(f"noise {noise} px: n={s['n']} no_seed={s['no_seed']} ambiguous={s['ambiguous']} "
                  f"not_real={s['not_real']} ref_practical={s.get('ref_practical')}")
            for m in METHODS:
                if m in s:
                    print(f"  {m:11s} strict={s[m]['strict']} practical={s[m]['practical']:.3f} "
                          f"accepted={s[m]['accepted']:.3f} ms_med={s[m]['ms_med']:.2f} reasons={s[m]['reasons']}")
            if "mcnemar_cont_vs_lm" in s:
                print("  McNemar cont vs lm:", s["mcnemar_cont_vs_lm"])
    summary["wall_s"] = time.time() - t_start
    Path(f"{out}_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
