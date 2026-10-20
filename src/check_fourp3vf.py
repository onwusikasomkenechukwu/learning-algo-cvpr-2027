"""Numerical checks of the 4p3vf equations for Task 1.8 (student instructions v5) and Propositions 1-2 of
draft v4, on synthetic instances and the ETH3D courtyard tuning scene. Laptop-only (numpy/scipy/matplotlib).

  residual     F(z_gt; x_gt) on 1000 noise-free instances (500 random, 500 courtyard)
  signs        flipping the depths of view 2 or 3 keeps F = 0 and flips that view's volume; four classes
  omega0       Prop. 1(b): at omega = 0, adding a constant to all depths of a view stays a root (a curve)
  coplanar     Prop. 1(c): two smallest singular values of F_z at the true root against flatness, and the
               left null space of [F_z F_p] at exactly coplanar points (self-stresses)
  crossing     Prop. 1(a): track the true root through a family whose track 4 crosses the plane of tracks 1-3
  surface      Prop. 2: seeds solve the nine fixed equations at the data, which leave a 2-D set; plot of g
  monodromy    solution count by monodromy with the sign symmetry, split by orientation class (slow)

Usage:
  python -I src/check_fourp3vf.py --out results/fourp3vf_checks
  python -I src/check_fourp3vf.py --out results/fourp3vf_checks --only monodromy --instances 3
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fourp3vf as M  # noqa: E402
from homotopy_proto import track, parameter_homotopy  # noqa: E402

COURTYARD = "data/eth3d/courtyard/dslr_calibration_undistorted"


def instances(rng, n, scene, **kw):
    return [M.random_instance(rng, **kw) if k % 2 == 0 or scene is None else scene.instance(rng, **kw)
            for k in range(n)]


def check_residual(rng, scene):
    worst, worst_rel = 0.0, 0.0
    for inst in instances(rng, 1000, scene):
        r = np.abs(M.F(inst["z_gt"], inst["x_gt"])).max()
        worst = max(worst, r)
        worst_rel = max(worst_rel, r / (np.abs(inst["z_gt"]).max() ** 3))
    return dict(n=1000, max_abs_residual=worst, max_residual_over_z3=worst_rel, passed=bool(worst < 1e-10))


def check_signs(rng, scene):
    bad, classes = 0, set()
    for inst in instances(rng, 200, scene):
        z, x = inst["z_gt"], inst["x_gt"]
        found = []
        for s2 in (1, -1):
            for s3 in (1, -1):
                lam = M.depths(z).copy()
                lam[1] *= s2
                lam[2] *= s3
                zz = M.to_z(z[0], lam)
                bad += np.abs(M.F(zz, x)).max() > 1e-10
                v = M.volumes(M.camera_points(zz, x))
                bad += not (np.sign(v[1] * v[0]) == s2 and np.sign(v[2] * v[0]) == s3)
                found.append(M.orientation_class(zz, x))
        bad += len(set(found)) != 4
        classes |= set(found)
    return dict(n=200, failures=int(bad), classes=sorted(classes), passed=bool(bad == 0))


def check_omega0(rng):
    worst_F, worst_sv = 0.0, 0.0
    for _ in range(200):
        x = rng.uniform(-0.5, 0.5, (3, 4, 2))
        lam1 = np.concatenate([[1.0], rng.uniform(0.5, 2, 3)])
        for c2, c3 in rng.normal(size=(5, 2)):
            signs = rng.choice([-1, 1], 2)
            lam = np.stack([lam1, signs[0] * lam1 + c2, signs[1] * lam1 + c3])
            z = M.to_z(0.0, lam)
            _, Jz, _ = M.jacobians(z, x)
            sv = np.linalg.svd(Jz, compute_uv=False)
            worst_F = max(worst_F, np.abs(M.F(z, x)).max())
            worst_sv = max(worst_sv, sv[-1] / sv[0])
    return dict(n=1000, note="l_ij = +-l_1j + c_i is a root at omega = 0 for every x and every c_i",
                max_residual=worst_F, max_smallest_sv_ratio=worst_sv,
                passed=bool(worst_F < 1e-12 and worst_sv < 1e-12))


def check_coplanar(rng, out):
    thick = np.logspace(0, -8, 33)
    curves = []
    for _ in range(20):
        base = M.random_instance(rng)
        rows = []
        for th in thick:
            X = M.flatten_points(base["X"], th)
            x = M.project(base["f"], base["R"], base["t"], X)
            z = M.root_from_scene(base["f"], base["R"], base["t"], X)
            _, Jz, Jp = M.jacobians(z, x)
            sv = np.linalg.svd(Jz, compute_uv=False)
            rows.append([M.planarity(M.camera_points(z, x)), sv[-1] / sv[0], sv[-2] / sv[0], sv[-3] / sv[0]])
        curves.append(rows)
    curves = np.array(curves)
    # exactly coplanar instances: corank of F_z and left null space of [F_z F_p]
    corank_z, left_null = [], []
    for _ in range(50):
        base = M.random_instance(rng, thickness=0.0)
        z, x = base["z_gt"], base["x_gt"]
        _, Jz, Jp = M.jacobians(z, x)
        s_z = np.linalg.svd(Jz, compute_uv=False)
        s_full = np.linalg.svd(np.hstack([Jz, Jp]), compute_uv=False)
        corank_z.append(int((s_z / s_z[0] < 1e-10).sum()))
        left_null.append(int((s_full / s_full[0] < 1e-10).sum()))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3.6))
    med = np.median(curves, axis=0)
    for c, lab in zip((1, 2, 3), ("smallest", "second", "third")):
        ax.loglog(med[:, 0], med[:, c], marker=".", label=f"{lab} singular value")
    ax.set_xlabel("planarity index |v1| / mean edge^3")
    ax.set_ylabel("singular value of F_z / largest")
    ax.set_title("F_z at the true root vs flatness (median of 20)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "coplanar_singular_values.png", dpi=150)
    plt.close(fig)
    slopes = [np.polyfit(np.log(med[-12:, 0]), np.log(med[-12:, c]), 1)[0] for c in (1, 2, 3)]
    return dict(n_curves=20, loglog_slopes_smallest_three=slopes, corank_Fz_at_coplanar=sorted(set(corank_z)),
                left_null_dim_FzFp_at_coplanar=sorted(set(left_null)),
                passed=bool(min(corank_z) >= 2 and min(left_null) >= 2), plot="coplanar_singular_values.png")


def check_crossing(rng):
    """Track the true root along a scene family whose track 4 crosses the plane of tracks 1-3 at s = 0.5."""
    stats = dict(n=0, reached=0, true_root=0, class_switch_events=0, other_root_class=[])
    for _ in range(100):
        base = M.random_instance(rng, thickness=0.0)
        X0 = base["X"]
        n = np.cross(X0[1] - X0[0], X0[2] - X0[0])
        n /= np.linalg.norm(n)
        h = rng.uniform(0.05, 0.5) * np.linalg.norm(X0[1] - X0[0])

        def scene(s):
            X = X0.copy()
            X[3] += (2 * s - 1) * h * n
            return X

        xs = lambda s: M.project(base["f"], base["R"], base["t"], scene(s))  # noqa: E731
        if any((np.abs(xs(s)) > 0.6).any() for s in (0, 1)):
            continue

        def H(z, s, eps=1e-7):
            val, Jz, Jp = M.jacobians(z, xs(s))
            return val, Jz, Jp @ ((xs(s + eps) - xs(s - eps)) / (2 * eps)).reshape(-1)

        z_start = M.root_from_scene(base["f"], base["R"], base["t"], scene(0))
        z_end = M.root_from_scene(base["f"], base["R"], base["t"], scene(1))
        cls0 = M.orientation_class(z_start, xs(0))
        state = dict(cls=cls0)

        def mon(z, s):
            P = M.camera_points(z, xs(s))
            if M.planarity(P) > 1e-3:
                c = M.orientation_class(z, xs(s))
                if c != state["cls"]:
                    state["cls"] = c
                    return dict(kind="class_switch")
            return None
        r = track(H, z_start, mon)
        stats["n"] += 1
        stats["reached"] += r["ok"]
        stats["class_switch_events"] += len(r["events"])
        if r["ok"]:
            if np.linalg.norm(r["z"] - z_end) < 1e-6 * (1 + np.linalg.norm(z_end)):
                stats["true_root"] += 1
            elif r["z"][0] > 0:
                stats["other_root_class"].append(M.orientation_class(r["z"], xs(1)))
    stats["passed"] = None  # descriptive: see note
    stats["note"] = ("start class (+,+); 'true_root' = tracked endpoint equals the ground truth at s = 1, so the "
                     "class was kept through the coplanar crossing; failures at the crossing are expected where "
                     "F_z loses rank (Prop. 1(c))")
    return stats


def _surface_chart(z, x, N, a, iters=20):
    """Point of the seed surface near z + N a (Gauss-Newton on the nine fixed equations, l34 left free)."""
    keep = np.setdiff1d(np.arange(12), [M.L34])
    zz = z.copy()
    zz[keep] += N @ a
    for _ in range(iters):
        val, Jz, _ = M.jacobians(zz, x)
        J = Jz[M.FIXED_ROWS][:, keep]
        step = np.linalg.lstsq(J, val[M.FIXED_ROWS], rcond=None)[0]
        zz[keep] -= step
        if np.linalg.norm(step) < 1e-14:
            break
    return zz, np.abs(M.F(zz, x)[M.FIXED_ROWS]).max()


def g_map(z, x):
    """Both mirror positions of the free point in view 3 for a point of the seed surface."""
    P = M.camera_points(z, x)
    R, t, _ = M.kabsch(P[0, :3], P[2, :3])
    q = R @ P[0, 3] + t
    nrm = np.cross(P[2, 1] - P[2, 0], P[2, 2] - P[2, 0])
    nrm /= np.linalg.norm(nrm)
    q_mirror = q - 2 * nrm @ (q - P[2, 0]) * nrm
    f = 1 / np.sqrt(z[0])
    return f * q[:2] / q[2], f * q_mirror[:2] / q_mirror[2]


def check_surface(rng, out):
    keep = np.setdiff1d(np.arange(12), [M.L34])
    on_surface, ranks, g_ok, n = [], [], [], 0
    example = None
    while n < 300:
        inst = M.random_instance(rng, noise_px=1.0)
        seeds = M.mean_point_seeds(inst["x"])
        for s in seeds:
            n += 1
            val, Jz, _ = M.jacobians(s["z0"], inst["x"])
            on_surface.append(np.abs(val[M.FIXED_ROWS]).max())
            ranks.append(np.linalg.matrix_rank(Jz[M.FIXED_ROWS][:, keep], tol=1e-9))
            g_ok.append(np.linalg.norm(g_map(s["z0"], inst["x"])[0] - s["x0"][2, 3]))
            if example is None and 0.005 < s["ell"] < 0.05:
                example = (inst, s)
    res = dict(n_seeds=n, max_fixed_residual_at_data=float(max(on_surface)), rank_counts={
        int(r): ranks.count(r) for r in set(ranks)}, max_g_vs_simulated_start=float(max(g_ok)))
    res["passed"] = bool(res["max_fixed_residual_at_data"] < 1e-10 and set(ranks) == {9})
    if example is not None:
        inst, s = example
        x = inst["x"]
        _, Jz, _ = M.jacobians(s["z0"], x)
        N = np.linalg.svd(Jz[M.FIXED_ROWS][:, keep])[2][9:].T      # 11 x 2 tangent basis of the surface
        scale = 0.02 * np.linalg.norm(s["z0"])
        pts, mir = [], []
        for a in np.linspace(-1, 1, 41):
            for b in np.linspace(-1, 1, 41):
                zz, r = _surface_chart(s["z0"], x, N, scale * np.array([a, b]))
                if r < 1e-10 and zz[0] > 0:
                    g1, g2 = g_map(zz, x)
                    pts.append(g1)
                    mir.append(g2)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pts, mir = np.array(pts) * inst["maxside"], np.array(mir) * inst["maxside"]
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.scatter(*pts.T, s=2, label="g, seed branch")
        ax.scatter(*mir.T, s=2, label="g, mirror branch")
        ax.scatter(*(s["x0"][2, 3] * inst["maxside"]), marker="o", facecolors="none", edgecolors="k", s=60,
                   label="seed g(s)")
        ax.scatter(*(x[2, 3] * inst["maxside"]), marker="x", c="r", s=60, label="observed free point")
        ax.set_xlabel("x, view 3 (px, 800 px image)")
        ax.set_ylabel("y (px)")
        ax.set_title(f"g on a chart of the seed surface (path {s['ell'] * inst['maxside']:.1f} px)")
        ax.legend(fontsize=7)
        ax.set_aspect("equal", "datalim")
        fig.tight_layout()
        fig.savefig(out / "seed_surface_g.png", dpi=150)
        plt.close(fig)
        res["plot"] = "seed_surface_g.png"
    return res


# ---------------------------------------------------------------- monodromy solution count

def _flips(z):
    lam = M.depths(z)
    out = []
    for s2, s3 in ((-1, 1), (1, -1), (-1, -1)):
        l = lam.copy()
        l[1] *= s2
        l[2] *= s3
        out.append(M.to_z(z[0], l))
    return out


def _add(sols, z, tol=1e-6):
    for s in sols:
        if np.linalg.norm(s - z) < tol * (1 + np.linalg.norm(s)):
            return False
    sols.append(z)
    return True


def monodromy(rng, stable_loops=5, max_loops=60, log=print):
    inst = M.random_instance(rng)
    pA = (rng.normal(size=(3, 4, 2)) + 1j * rng.normal(size=(3, 4, 2))) * 0.3
    gamma = np.exp(2j * np.pi * rng.uniform())
    r = track(parameter_homotopy(inst["x_gt"].astype(complex), pA, gamma), inst["z_gt"].astype(complex))
    if not r["ok"]:
        return None
    sols = [r["z"]]
    for z in _flips(r["z"]):
        _add(sols, z)
    quiet, loops, history, t0 = 0, 0, [], time.time()
    while quiet < stable_loops and loops < max_loops:
        loops += 1
        pB = (rng.normal(size=(3, 4, 2)) + 1j * rng.normal(size=(3, 4, 2))) * 0.3
        pC = (rng.normal(size=(3, 4, 2)) + 1j * rng.normal(size=(3, 4, 2))) * 0.3
        new = 0
        for z in list(sols):
            zz, ok = z, True
            for a, b in ((pA, pB), (pB, pC), (pC, pA)):
                rr = track(parameter_homotopy(a, b), zz)
                if not rr["ok"]:
                    ok = False
                    break
                zz = rr["z"]
            if ok and _add(sols, zz):
                new += 1
                for w in _flips(zz):
                    new += _add(sols, w)
        history.append(len(sols))
        quiet = quiet + 1 if new == 0 else 0
        log(f"  loop {loops}: {len(sols)} solutions (+{new}), {time.time() - t0:.0f} s")
    # classify at pA: eps_i = v_i / v_1 (= +-1 for every root, complex ones included, by Cayley-Menger)
    classes, zero_vol, zero_depth, omega0 = {}, 0, 0, 0
    for z in sols:
        lam = M.depths(z)
        s = np.sqrt(z[0] + 0j)
        P = lam[..., None] * np.concatenate([pA * s, np.ones((3, 4, 1))], axis=2)
        v = np.linalg.det(np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0], P[:, 3] - P[:, 0]], axis=2))
        if abs(v[0]) < 1e-8:
            zero_vol += 1
            continue
        key = (int(np.sign((v[1] / v[0]).real)), int(np.sign((v[2] / v[0]).real)))
        classes[str(key)] = classes.get(str(key), 0) + 1
        zero_depth += bool((np.abs(lam) < 1e-8).any())
        omega0 += abs(z[0]) < 1e-8
    return dict(count=len(sols), loops=loops, history=history, classes=classes, zero_volume=zero_vol,
                zero_depth=int(zero_depth), omega_zero=int(omega0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", help="subset of checks to run")
    ap.add_argument("--instances", type=int, default=3, help="monodromy instances")
    ap.add_argument("--rng", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.rng)
    scene = M.Eth3dScene(COURTYARD) if Path(COURTYARD).exists() else None
    checks = dict(residual=lambda: check_residual(rng, scene), signs=lambda: check_signs(rng, scene),
                  omega0=lambda: check_omega0(rng), coplanar=lambda: check_coplanar(rng, out),
                  crossing=lambda: check_crossing(rng), surface=lambda: check_surface(rng, out),
                  monodromy=lambda: [monodromy(rng) for _ in range(args.instances)])
    todo = args.only or [k for k in checks if k != "monodromy"]
    results = {}
    for name in todo:
        t0 = time.time()
        print(f"== {name}", flush=True)
        results[name] = checks[name]()
        results[name + "_seconds"] = round(time.time() - t0, 1)
        print(json.dumps(results[name], default=float), flush=True)
    path = out / ("checks.json" if not args.only else f"checks_{'_'.join(args.only)}.json")
    path.write_text(json.dumps(results, indent=1, default=float))


if __name__ == "__main__":
    main()
