"""Smoke test of the fork estimators added for draft v5 (scripts/patches/poselib_extra_rows.py) and of OOB fix 3, on a
synthetic triplet with half outliers. Run by run_abl_dell.sh setup after a fork build; exits non-zero on failure.

  joint calibrated 5pt+P3P with LO and final refinement   (refine_3v_relpose: OOB fix 3; Eigen asserted on it)
  calibrated sequential pipeline                            poses within 1 deg, fixed counts run in both stages
  shared-focal LO from given cameras                        from 10 % off: f within 5 %, poses within 2 deg

  python scripts/check_extra_rows.py
"""
import sys

import numpy as np

try:
    import torch  # noqa: F401  (the fork links libtorch; load it first)
except ImportError:
    pass
import poselib


def rot(a):
    a = np.asarray(a, float)
    t = np.linalg.norm(a)
    k = a / t
    S = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(t) * S + (1 - np.cos(t)) * S @ S


def ang(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def main():
    rng = np.random.default_rng(3)
    f, pp = 1200.0, np.array([640.0, 480.0])
    K = np.array([[f, 0, pp[0]], [0, f, pp[1]], [0, 0, 1]])
    R2, R3 = rot([0.05, 0.2, 0.01]), rot([-0.03, 0.35, 0.02])
    t2, t3 = np.array([-1.0, 0.05, 0.1]), np.array([-1.8, 0.1, 0.3])
    X = rng.uniform([-3, -2, 6], [3, 2, 12], (300, 3))

    def proj(R, t):
        p = (X @ R.T + t) @ K.T
        return p[:, :2] / p[:, 2:] + rng.normal(0, 0.5, (len(X), 2))

    x = [proj(np.eye(3), np.zeros(3)), proj(R2, t2), proj(R3, t3)]
    for xi in x:
        xi[:150] = rng.random((150, 2)) * [1280, 960]
    cam = {'model': 'SIMPLE_PINHOLE', 'width': 1280, 'height': 960, 'params': [f, pp[0], pp[1]]}
    ro = {'max_epipolar_error': 5.0, 'min_iterations': 50, 'max_iterations': 5000, 'lo_iterations': 25,
          'sample_sz': 5, 'delta': 0.0, 'inner_refine': 0}
    bo = {'max_iterations': 100}
    fails = []

    def check(name, ok, msg):
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {msg}")
        if not ok:
            fails.append(name)

    for name, fn in (("joint 5pt+P3P", poselib.estimate_three_view_relative_pose),
                     ("sequential 5pt then P3P", poselib.estimate_three_view_relative_pose_sequential)):
        out, info = fn(*x, cam, cam, cam, ro, bo)
        e = max(ang(out.pose12.R.T @ R2), ang(out.pose13.R.T @ R3))
        check(name, e < 1.0 and info['num_inliers'] >= 140, f"max rotation error {e:.3f} deg, {info['num_inliers']} inliers")
    _, info = poselib.estimate_three_view_relative_pose_sequential(
        *x, cam, cam, cam, dict(ro, min_iterations=40, max_iterations=40), bo)
    check("sequential fixed count", info['iterations'] == 80, f"40 per stage -> {info['iterations']} iterations")

    dR = rot([0.01, -0.02, 0.015])
    s = np.linalg.norm(t2)
    for f0 in (0.9 * f, 1.1 * f):
        trip, info = poselib.refine_three_view_shared_focal_from_init(
            *x, pp, f0, dR @ R2, t2 / s, dR @ R3, t3 / s, ro, bo, 2)
        e = max(ang(trip.poses.pose12.R.T @ R2), ang(trip.poses.pose13.R.T @ R3))
        ferr = abs(trip.camera.focal() - f) / f
        check(f"LO from cameras (f0 {f0:.0f})", ferr < 0.05 and e < 2.0 and np.isfinite(trip.camera.focal()),
              f"focal error {100 * ferr:.2f} % (start 10 %), max rotation error {e:.3f} deg, {info['num_inliers']} inliers")
    if fails:
        sys.exit(f"{len(fails)} check(s) failed: {', '.join(fails)}")
    print("all extra-row checks passed")


if __name__ == "__main__":
    main()
