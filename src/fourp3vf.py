"""4p3vf (four points, three views, one unknown shared focal length): equations, synthetic instances and
mean-point seeds, numpy only (draft v4 Secs. 3-4, student instructions v5 Tasks 1.8 and 2.3).

Conventions
  x[i, j]  image point of track j in view i, 2-vector, principal point at the origin and coordinates divided by
           the larger image side, so the focal length f is O(1). p = x.reshape(24) is the parameter vector.
  z        12 unknowns [omega, l12, l13, l14, l21, l22, l23, l24, l31, l32, l33, l34] with omega = f^-2 and
           l11 = 1 (l_ij = depth of track j in view i; the draft numbers views and tracks from 1).
  F(z; x)  for views i = 2, 3 and pairs j < k (order PAIRS):
             omega |l1j x1j - l1k x1k|^2 + (l1j - l1k)^2 - omega |lij xij - lik xik|^2 - (lij - lik)^2,
           twelve cubics; rows 0-5 are view 2, rows 6-11 view 3. The free point is x[2, 3] (view 3, track 4);
           it enters rows FREE_ROWS only.
  Poses    camera 1 is (I, 0); P_ij = l_ij [x_ij sqrt(omega), 1] are the points in camera i, and (R_i, t_i) map
           camera-1 points to camera i: P_i = R_i P_1 + t_i.

Everything here works for real and complex z and x (no abs/conj on the equations), so the same code serves the
real tracker and the complex correct-root paths.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))

PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
EQ_VIEW = np.repeat([1, 2], 6)
EQ_J = np.tile([j for j, _ in PAIRS], 2)
EQ_K = np.tile([k for _, k in PAIRS], 2)
FREE_ROWS = np.array([6 + n for n, (j, k) in enumerate(PAIRS) if k == 3])  # rows 8, 10, 11
FIXED_ROWS = np.setdiff1d(np.arange(12), FREE_ROWS)
FREE_P = np.array([8 * 2 + 2 * 3, 8 * 2 + 2 * 3 + 1])  # p indices of x[2, 3]
L34 = 11  # z index of the free point's depth


def zcol(v, j):
    """Column of l_vj in z (l11 has none: it is fixed to 1)."""
    return 4 * v + j


def depths(z):
    lam = np.empty((3, 4), dtype=np.result_type(z, float))
    lam[0, 0] = 1.0
    lam.flat[1:] = z[1:]
    return lam


def to_z(omega, lam):
    lam = np.asarray(lam)
    return np.concatenate([[omega], lam.flat[1:]])


def _terms(z, x):
    lam = depths(z)
    Q = lam[..., None] * x                                  # (3, 4, 2)
    d0 = Q[0, EQ_J] - Q[0, EQ_K]                            # (12, 2) view-1 differences
    di = Q[EQ_VIEW, EQ_J] - Q[EQ_VIEW, EQ_K]                # (12, 2) view-i differences
    dl0 = lam[0, EQ_J] - lam[0, EQ_K]
    dli = lam[EQ_VIEW, EQ_J] - lam[EQ_VIEW, EQ_K]
    return lam, d0, di, dl0, dli


def F(z, x):
    _, d0, di, dl0, dli = _terms(z, x)
    return z[0] * ((d0 * d0).sum(1) - (di * di).sum(1)) + dl0 * dl0 - dli * dli


def jacobians(z, x):
    """(F, F_z (12x12), F_p (12x24)) at (z, x)."""
    x = np.asarray(x)
    lam, d0, di, dl0, dli = _terms(z, x)
    w = z[0]
    rows = np.arange(12)
    s0, si = (d0 * d0).sum(1), (di * di).sum(1)
    val = w * (s0 - si) + dl0 * dl0 - dli * dli
    dt = np.result_type(z, x, float)
    Jz = np.zeros((12, 12), dtype=dt)
    Jz[:, 0] = s0 - si
    g0j = 2 * w * (d0 * x[0, EQ_J]).sum(1) + 2 * dl0
    g0k = -2 * w * (d0 * x[0, EQ_K]).sum(1) - 2 * dl0
    gij = 2 * w * (di * x[EQ_VIEW, EQ_J]).sum(1) + 2 * dli
    gik = -2 * w * (di * x[EQ_VIEW, EQ_K]).sum(1) - 2 * dli
    m = EQ_J > 0                                            # l11 is fixed, so it has no column
    Jz[rows[m], zcol(0, EQ_J[m])] += g0j[m]
    Jz[rows, zcol(0, EQ_K)] += g0k
    Jz[rows, zcol(EQ_VIEW, EQ_J)] -= gij
    Jz[rows, zcol(EQ_VIEW, EQ_K)] -= gik
    Jp = np.zeros((12, 24), dtype=dt)
    pc = lambda v, j: 8 * v + 2 * j                         # noqa: E731  p index of x[v, j, 0]
    for c in range(2):
        Jp[rows, pc(0, EQ_J) + c] += 2 * w * lam[0, EQ_J] * d0[:, c]
        Jp[rows, pc(0, EQ_K) + c] -= 2 * w * lam[0, EQ_K] * d0[:, c]
        Jp[rows, pc(EQ_VIEW, EQ_J) + c] -= 2 * w * lam[EQ_VIEW, EQ_J] * di[:, c]
        Jp[rows, pc(EQ_VIEW, EQ_K) + c] += 2 * w * lam[EQ_VIEW, EQ_K] * di[:, c]
    return val, Jz, Jp


# ---------------------------------------------------------------- geometry of a root

def camera_points(z, x):
    """P[i, j] = l_ij [x_ij sqrt(omega), 1] (real roots with omega > 0)."""
    lam = depths(z)
    s = np.sqrt(z[0])
    return lam[..., None] * np.concatenate([x * s, np.ones((3, 4, 1))], axis=2)


def volumes(P):
    """Signed tetrahedron volume (times 6) of P[i, 0..3] per view."""
    return np.linalg.det(np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0], P[:, 3] - P[:, 0]], axis=2))


def planarity(P):
    """|v_1| over the cube of the mean edge length in view 1 (0 for coplanar points)."""
    e = [np.linalg.norm(P[0, j] - P[0, k]) for j, k in PAIRS]
    return abs(volumes(P[:1])[0]) / np.mean(e) ** 3


def orientation_class(z, x):
    """(eps2, eps3) = signs of v2/v1 and v3/v1; only (+1, +1) gives proper rotations."""
    v = volumes(camera_points(z, x))
    return int(np.sign(v[1] * v[0])), int(np.sign(v[2] * v[0]))


def kabsch(A, B):
    """Proper (R, t) minimizing |R A_j + t - B_j| and the RMS residual."""
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((B - cb).T @ (A - ca))
    D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    t = cb - R @ ca
    return R, t, np.sqrt(((A @ R.T + t - B) ** 2).sum(1).mean())


def poses_from_root(z, x):
    """f, [(R_i, t_i)] for views 2, 3 and the worst alignment residual relative to the scene size."""
    P = camera_points(z, x)
    scale = np.linalg.norm(P[0] - P[0].mean(0), axis=1).mean()
    out, worst = [], 0.0
    for i in (1, 2):
        R, t, res = kabsch(P[0], P[i])
        out.append((R, t))
        worst = max(worst, res / scale)
    return 1 / np.sqrt(z[0]), out, worst


def root_from_scene(f, R, t, X):
    """Depths (normalized so l11 = 1) of camera-1 points X (4, 3) in cameras (R[i], t[i]), as z."""
    lam = np.stack([X @ R[i].T + t[i] for i in range(3)])[..., 2]
    return to_z(1 / f ** 2, lam / lam[0, 0])


def project(f, R, t, X):
    """x[i, j] for cameras (R[i], t[i]) with K = diag(f, f, 1)."""
    C = np.stack([X @ R[i].T + t[i] for i in range(3)])
    return f * C[..., :2] / C[..., 2:]


def rot_err_deg(Ra, Rb):
    c = (np.trace(Ra @ Rb.T) - 1) / 2
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


# ---------------------------------------------------------------- synthetic instances

def _look_at(c, target, rng, jitter_deg):
    """World-to-camera rotation of a camera at c looking at target, with random roll and jitter."""
    fwd = (target - c) / np.linalg.norm(target - c)
    up = rng.normal(size=3)
    right = np.cross(up, fwd)
    right /= np.linalg.norm(right)
    down = np.cross(fwd, right)
    R = np.stack([right, down, fwd])
    return Rotation.from_rotvec(np.radians(jitter_deg) * rng.uniform(-1, 1, 3)).as_matrix() @ R


def flatten_points(X, thickness):
    """Move track 4 toward the plane of tracks 1-3, keeping the fraction `thickness` of its offset."""
    n = np.cross(X[1] - X[0], X[2] - X[0])
    n /= np.linalg.norm(n)
    off = n @ (X[3] - X[0])
    X = X.copy()
    X[3] -= (1 - thickness) * off * n
    return X


def _finish(f, R, t, X, maxside, aspect, noise_px, rng):
    """Shared tail of the generators: bounds and cheirality checks, noise, normalized ground truth."""
    C = np.stack([X @ R[i].T + t[i] for i in range(3)])
    if (C[..., 2] <= 0).any():
        return None
    x_gt = project(f, R, t, X)
    if (np.abs(x_gt[..., 0]) > 0.5).any() or (np.abs(x_gt[..., 1]) > 0.5 * aspect).any():
        return None
    x = x_gt + rng.normal(scale=noise_px / maxside, size=x_gt.shape)
    return dict(f=f, R=R, t=t, X=X, x_gt=x_gt, x=x, z_gt=root_from_scene(f, R, t, X), maxside=maxside,
                noise_px=noise_px)


def random_instance(rng, noise_px=0.0, thickness=1.0, maxside=800, aspect=0.75, f_range=(0.5, 1.5),
                    depth_range=(4.0, 8.0), baseline_range=(0.5, 2.0), jitter_deg=10.0):
    """Random 4p3vf instance; camera 1 is the world frame. `thickness` < 1 makes the points nearly coplanar."""
    while True:
        f = rng.uniform(*f_range)
        Z = rng.uniform(*depth_range, 4)
        uv = rng.uniform(-0.4, 0.4, (4, 2)) * [1, aspect]
        X = np.column_stack([uv * Z[:, None] / f, Z])
        if thickness < 1:
            X = flatten_points(X, thickness)
        target = X.mean(0)
        R, t = [np.eye(3)], [np.zeros(3)]
        for _ in range(2):
            c = rng.normal(size=3)
            c *= rng.uniform(*baseline_range) / np.linalg.norm(c)
            Ri = _look_at(c, target, rng, jitter_deg)
            R.append(Ri)
            t.append(-Ri @ c)
        inst = _finish(f, np.array(R), np.array(t), X, maxside, aspect, noise_px, rng)
        if inst is not None:
            return inst


class Eth3dScene:
    """Real cameras and 3D points of one ETH3D scene (tuning scene: courtyard) for realistic distances.
    The shared focal length is the mean fx of the scene's cameras; images are resized to `maxside` pixels."""

    def __init__(self, model_dir, maxside=800):
        from colmap_io import read_model, read_points3D
        cams, images = read_model(model_dir)
        self.points = read_points3D(model_dir)
        self.images = [im for im in images.values() if len(im.point3D_ids) >= 4]
        cam = next(iter(cams.values()))
        side = max(cam.width, cam.height)
        self.f = np.mean([c.K[0, 0] / max(c.width, c.height) for c in cams.values()])
        self.aspect = min(cam.width, cam.height) / side
        self.maxside = maxside

    def instance(self, rng, noise_px=0.0, thickness=1.0, min_shared=20):
        while True:
            a, b, c = rng.choice(len(self.images), 3, replace=False)
            ims = [self.images[a], self.images[b], self.images[c]]
            shared = np.intersect1d(np.intersect1d(ims[0].point3D_ids, ims[1].point3D_ids), ims[2].point3D_ids)
            shared = [p for p in shared if p in self.points]
            if len(shared) < min_shared:
                continue
            Xw = np.array([self.points[p] for p in rng.choice(shared, 4, replace=False)])
            R1, t1 = ims[0].R, ims[0].t
            X = Xw @ R1.T + t1
            if thickness < 1:
                X = flatten_points(X, thickness)
            R = np.array([im.R @ R1.T for im in ims])
            t = np.array([im.t - Ri @ t1 for im, Ri in zip(ims, R)])
            inst = _finish(self.f, R, t, X, self.maxside, self.aspect, noise_px, rng)
            if inst is not None:
                return inst


class CambridgeScene:
    """Real all-inlier samples from a Cambridge Landmarks scene's own SfM model (reconstruction.nvm): the
    observations of four 3D points in three images. Proxy for kill test B before SP+LG triplets exist.

    Triplets follow threeview's prepare_im.py: three random images, >= 5 covisible points, and the bounding box
    of the covisible points covering > 10% of every image. Observations are undistorted with the NVM convention
    m_u = m (1 + r |m|^2 / f^2) (median reprojection error 1.4 px at 1920 px, vs 3.1 px uncorrected). The
    shared focal length is the mean of the three NVM focals; x_gt reprojects the NVM points with the reference
    cameras and that focal, as in draft Sec. 6.2. Coordinates are divided by the image width (1920 px);
    pixel numbers are reported at the paper's 800 px."""

    def __init__(self, scene_dir, width=1920, height=1080, maxside=800):
        from colmap_io import qvec_to_rotmat
        lines = (Path(scene_dir) / "reconstruction.nvm").read_text().split("\n")
        i = 0
        while not lines[i].strip() or lines[i].startswith("NVM"):
            i += 1
        self.cams = []
        for line in lines[i + 1:i + 1 + int(lines[i])]:
            tok = line.split()
            R = qvec_to_rotmat(np.array(tok[2:6], dtype=float))
            C = np.array(tok[6:9], dtype=float)
            self.cams.append((tok[0], float(tok[1]), R, -R @ C, float(tok[9])))
        j = i + 1 + len(self.cams)
        while not lines[j].strip():
            j += 1
        self.X, obs = [], [dict() for _ in self.cams]
        for pid, line in enumerate(lines[j + 1:j + 1 + int(lines[j])]):
            tok = line.split()
            n = int(tok[6])
            m = np.array(tok[7:7 + 4 * n], dtype=float).reshape(n, 4)
            self.X.append(np.array(tok[:3], dtype=float))
            for ci, _, mx, my in m:
                _, f, _, _, r = self.cams[int(ci)]
                obs[int(ci)][pid] = np.array([mx, my]) * (1 + r * (mx * mx + my * my) / (f * f))
        self.X = np.array(self.X)
        self.obs = obs
        self.ids = [np.array(sorted(o)) for o in obs]
        self.width, self.height, self.maxside = width, height, maxside

    def _area(self, pts):
        return np.ptp(pts[:, 0]) * np.ptp(pts[:, 1]) / (self.width * self.height)

    def instance(self, rng, noise_px=None, thickness=1.0):
        n = len(self.cams)
        while True:
            a, b, c = rng.choice(n, 3, replace=False)
            shared = np.intersect1d(np.intersect1d(self.ids[a], self.ids[b]), self.ids[c])
            if len(shared) < 5:
                continue
            if min(self._area(np.array([self.obs[v][p] for p in shared])) for v in (a, b, c)) <= 0.1:
                continue
            pick = rng.choice(shared, 4, replace=False)
            cams = [self.cams[v] for v in (a, b, c)]
            R1, t1 = cams[0][2], cams[0][3]
            R = np.array([cm[2] @ R1.T for cm in cams])
            t = np.array([cm[3] - Ri @ t1 for cm, Ri in zip(cams, R)])
            X = self.X[pick] @ R1.T + t1
            f = np.mean([cm[1] for cm in cams]) / self.width
            x = np.array([[self.obs[v][p] for p in pick] for v in (a, b, c)]) / self.width
            if (np.stack([X @ R[i].T + t[i] for i in range(3)])[..., 2] <= 0).any():
                continue
            x_gt = project(f, R, t, X)
            err = np.sqrt(((x - x_gt) ** 2).sum(-1).mean()) * self.maxside
            return dict(f=f, R=R, t=t, X=X, x_gt=x_gt, x=x, z_gt=root_from_scene(f, R, t, X),
                        maxside=self.maxside, noise_px=float(err),
                        names=[self.cams[v][0] for v in (a, b, c)])


# ---------------------------------------------------------------- mean-point seeds (released fork, Sec. 3)

def mean_points(x):
    """Virtual correspondences of the fork's ThreeViewSharedFocalRelativePoseEstimator::generate_models:
    means of tracks {1, 2, 3} and {4, 2, 3} in views 1 and 2 (0-based {0, 1, 2} and {3, 1, 2})."""
    return np.stack([x[:2, [0, 1, 2]].mean(1), x[:2, [3, 1, 2]].mean(1)], axis=1)  # (2 views, 2, 2)


def _ray(x, f):
    return np.column_stack([x / f, np.ones(len(x))])


# Polynomials in (a, b, omega) as coefficient arrays c[i, j, k] of a^i b^j omega^k.
def _pmul(A, B):
    from scipy.signal import convolve
    return convolve(A, B, method="direct")


def _padd(*polys):
    shape = np.max([p.shape for p in polys], axis=0)
    out = np.zeros(shape)
    for p in polys:
        out[:p.shape[0], :p.shape[1], :p.shape[2]] += p
    return out


def _pmatmul(A, B):
    return [[_padd(*[_pmul(A[i][k], B[k][j]) for k in range(3)]) for j in range(3)] for i in range(3)]


MONOMIALS_AB = [(i, d - i) for d in (3, 2, 1, 0) for i in range(d, -1, -1)]  # a^3 ... 1, ten monomials


def six_point_focal(x1, x2):
    """All roots (f, R, t) of the shared-focal six-point relative pose problem, |t| = 1, as a 10x10 quadratic
    eigenvalue problem in omega = f^-2 (Kukelova, Bujnak, Pajdla, BMVC 2008): F = a F1 + b F2 + F3 from the null
    space of the epipolar equations, then det F = 0 and 2 F D F^T D F - tr(F D F^T D) F = 0 with
    D = diag(1, 1, omega). Stand-in for the fork's relpose_6pt_focal (Stewenius et al.), which the laptop lacks.
    Of the four decompositions of E, the one with the first four (real) tracks in front of both cameras is kept."""
    A = np.einsum("ni,nj->nij", np.column_stack([x2, np.ones(6)]), np.column_stack([x1, np.ones(6)]))
    N = np.linalg.svd(A.reshape(6, 9))[2][-3:]              # null space, rows F1, F2, F3 (row-major 3x3)
    Fp = [[np.zeros((2, 2, 1)) for _ in range(3)] for _ in range(3)]
    for r in range(3):
        for c in range(3):
            Fp[r][c][1, 0, 0], Fp[r][c][0, 1, 0], Fp[r][c][0, 0, 0] = N[0, 3 * r + c], N[1, 3 * r + c], N[2, 3 * r + c]
    one, om, zero = np.ones((1, 1, 1)), np.zeros((1, 1, 2)), np.zeros((1, 1, 1))
    om[0, 0, 1] = 1
    D = [[one, zero, zero], [zero, one, zero], [zero, zero, om]]
    FT = [[Fp[c][r] for c in range(3)] for r in range(3)]
    FDFtD = _pmatmul(_pmatmul(_pmatmul(Fp, D), FT), D)
    tr = _padd(FDFtD[0][0], FDFtD[1][1], FDFtD[2][2])
    G = _pmatmul(FDFtD, Fp)
    eqs = [_padd(2 * G[r][c], -_pmul(tr, Fp[r][c])) for r in range(3) for c in range(3)]
    det = _padd(_pmul(Fp[0][0], _padd(_pmul(Fp[1][1], Fp[2][2]), -_pmul(Fp[1][2], Fp[2][1]))),
                -_pmul(Fp[0][1], _padd(_pmul(Fp[1][0], Fp[2][2]), -_pmul(Fp[1][2], Fp[2][0]))),
                _pmul(Fp[0][2], _padd(_pmul(Fp[1][0], Fp[2][1]), -_pmul(Fp[1][1], Fp[2][0]))))
    C = np.zeros((3, 10, 10))
    for e, p in enumerate(eqs + [det]):
        p = _padd(p, np.zeros((4, 4, 3)))
        for m, (i, j) in enumerate(MONOMIALS_AB):
            C[:, e, m] = p[i, j, :3]
    from scipy.linalg import eig
    I, Z = np.eye(10), np.zeros((10, 10))
    vals, vecs = eig(np.block([[Z, I], [-C[0], -C[1]]]), np.block([[I, Z], [Z, C[2]]]))
    out = []
    ia, ib, i1 = MONOMIALS_AB.index((1, 0)), MONOMIALS_AB.index((0, 1)), MONOMIALS_AB.index((0, 0))
    for w, v in zip(vals, vecs.T):
        if not np.isfinite(w) or abs(w.imag) > 1e-8 * max(1, abs(w)) or w.real <= 0:
            continue
        v = v[:10]
        if abs(v[i1]) < 1e-12 * np.abs(v).max():
            continue
        a, b = (v[ia] / v[i1]).real, (v[ib] / v[i1]).real
        Fm = (a * N[0] + b * N[1] + N[2]).reshape(3, 3)
        f = 1 / np.sqrt(w.real)
        K = np.diag([f, f, 1.0])
        E = K @ Fm @ K
        for R, t in _decompose_essential(E):
            X = triangulate(f, R, t, x1[:4], x2[:4])
            if X[:, 2].min() > 0 and (X @ R.T + t)[:, 2].min() > 0:
                pol = polish_pair(x1, x2, f, R, t)
                if pol is not None:
                    out.append(pol)
                break
    return out


def polish_pair(x1, x2, f0, R0, t0):
    """Newton (LM) polish of a six-point root on its six epipolar equations; None if it does not converge."""
    from scipy.optimize import least_squares
    t0 = t0 / np.linalg.norm(t0)
    e1 = np.cross(t0, [1.0, 0, 0] if abs(t0[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(t0, e1)

    def unpack(q):
        t = t0 + q[4] * e1 + q[5] * e2
        return np.exp(q[0]) * f0, Rotation.from_rotvec(q[1:4]).as_matrix() @ R0, t / np.linalg.norm(t)

    def res(q):
        f, R, t = unpack(q)
        r1, r2 = _ray(x1, f), _ray(x2, f)
        E = np.cross(np.eye(3), t) @ R                      # [t]_x R
        return np.einsum("ni,ij,nj->n", r2, E, r1) / np.linalg.norm(r1, axis=1) / np.linalg.norm(r2, axis=1)

    sol = least_squares(res, np.zeros(6), method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=50)
    if not np.isfinite(sol.x).all() or np.abs(res(sol.x)).max() > 1e-12:
        return None
    return unpack(sol.x)


def _decompose_essential(E):
    U, _, Vt = np.linalg.svd(E)
    U *= np.sign(np.linalg.det(U))
    Vt *= np.sign(np.linalg.det(Vt))
    W = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.0]])
    return [(U @ W @ Vt, U[:, 2]), (U @ W @ Vt, -U[:, 2]), (U @ W.T @ Vt, U[:, 2]), (U @ W.T @ Vt, -U[:, 2])]


def triangulate(f, R, t, x1, x2):
    """Linear triangulation in the frame of camera 1 = (I, 0) and camera 2 = (R, t)."""
    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = np.hstack([R, t[:, None]])
    out = []
    for a, b in zip(_ray(x1, f), _ray(x2, f)):
        A = np.stack([a[0] * P1[2] - P1[0], a[1] * P1[2] - P1[1], b[0] * P2[2] - P2[0], b[1] * P2[2] - P2[1]])
        X = np.linalg.svd(A)[2][-1]
        out.append(X[:3] / X[3])
    return np.array(out)


def p3p(Xc, x3, f):
    """All P3P poses (R, t) of view 3 from camera-1 points Xc (3, 3) and observations x3 (3, 2)."""
    import cv2
    K = np.diag([f, f, 1.0])
    from scipy.optimize import least_squares
    n, rvecs, tvecs = cv2.solveP3P(Xc.astype(np.float64), x3.astype(np.float64), K, None,
                                   flags=cv2.SOLVEPNP_P3P)
    out = []
    for r, tv in zip(rvecs, tvecs):                         # OpenCV's P3P is good to ~1e-6 only: polish
        R0, t0 = cv2.Rodrigues(r)[0], tv.ravel()

        def res(q):
            C = Xc @ (Rotation.from_rotvec(q[:3]).as_matrix() @ R0).T + t0 + q[3:]
            return (f * C[:, :2] / C[:, 2:] - x3).ravel()

        sol = least_squares(res, np.zeros(6), method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=50)
        if np.abs(res(sol.x)).max() < 1e-12:
            out.append((Rotation.from_rotvec(sol.x[:3]).as_matrix() @ R0, t0 + sol.x[3:]))
    return out


def seeds_from_pair(x, f, R2, t2, f_range=(0.1, 10.0)):
    """Complete a two-view (f, R2, t2) that is exact on the four real tracks of views 1-2: triangulate, register
    view 3 from tracks 1-3 by P3P and build the simulated start of each P3P pose (Sec. 4). Seeds failing the
    focal-range or cheirality test are dropped."""
    if not f_range[0] < f < f_range[1]:
        return []
    X = triangulate(f, R2, t2, x[0], x[1])
    out = []
    for R3, t3 in p3p(X[:3], x[2, :3], f):
        R = np.array([np.eye(3), R2, R3])
        t = np.array([np.zeros(3), t2, t3])
        C = np.stack([X @ R[i].T + t[i] for i in range(3)])
        if (C[..., 2] <= 0).any():
            continue
        x0 = project(f, R, t, X)
        out.append(dict(f=f, R=R, t=t, X=X, x0=x0, z0=root_from_scene(f, R, t, X),
                        ell=np.linalg.norm(x0[2, 3] - x[2, 3]),  # normalized units (fraction of the image side)
                        off_free=np.abs(np.delete((x0 - x).reshape(-1), FREE_P)).max()))
    return out


def mean_point_seeds(x):
    """4p3vf(M) seeds of a sample: two mean-point virtual correspondences, every six-point root, then
    triangulation and P3P on tracks 1-3 for each."""
    m = mean_points(x)
    return [s for sol in six_point_focal(np.vstack([x[0], m[0]]), np.vstack([x[1], m[1]]))
            for s in seeds_from_pair(x, *sol)]


def project_onto_surface(x, f, R2, t2):
    """Move an outside two-view guess onto the seed surface (Task 2.3): virtual matches at the view-1 mean
    points with view-2 partners on the guess's own epipolar lines (closest to the view-2 means), then the
    six-point root nearest to the guess on the four real and two virtual matches."""
    m = mean_points(x)
    E = np.cross(np.eye(3), t2 / np.linalg.norm(t2)) @ R2
    Fm = np.diag([1 / f, 1 / f, 1]) @ E @ np.diag([1 / f, 1 / f, 1])
    v2 = []
    for a, b in zip(m[0], m[1]):
        l = Fm @ np.append(a, 1)                            # epipolar line in view 2
        d = (l[:2] @ b + l[2]) / (l[:2] @ l[:2])
        v2.append(b - d * l[:2])
    sols = six_point_focal(np.vstack([x[0], m[0]]), np.vstack([x[1], v2]))
    if not sols:
        return []
    near = min(sols, key=lambda s: rot_err_deg(s[1], R2) + 100 * abs(np.log(s[0] / f)))
    return seeds_from_pair(x, *near)
