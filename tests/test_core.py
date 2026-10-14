"""Unit tests for metrics, pose conventions, the COLMAP reader and the tuple sampler.
Standard library unittest only (no pytest needed on the cluster):
    python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import eval_relpose as ev  # noqa: E402
from colmap_io import Image, qvec_to_rotmat, read_model  # noqa: E402
from sample_tuples import covisibility_graph, sample  # noqa: E402


def random_rotation(rng):
    q = rng.normal(size=4)
    return qvec_to_rotmat(q / np.linalg.norm(q))


class TestMetrics(unittest.TestCase):
    def test_rotation_error(self):
        rng = np.random.default_rng(0)
        R = random_rotation(rng)
        self.assertAlmostEqual(ev.rotation_error_deg(R, R), 0.0, places=5)
        a = np.radians(7.0)
        Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        self.assertAlmostEqual(ev.rotation_error_deg(Rz @ R, R), 7.0, places=6)

    def test_translation_error_is_sign_and_scale_agnostic(self):
        t = np.array([1.0, 2.0, 3.0])
        self.assertAlmostEqual(ev.translation_error_deg(-5 * t, t), 0.0, places=5)
        self.assertAlmostEqual(ev.translation_error_deg(np.array([1.0, 0, 0]), np.array([0, 1.0, 0])), 90.0)
        self.assertEqual(ev.translation_error_deg(np.zeros(3), t), 180.0)

    def test_auc_and_maa(self):
        self.assertEqual(ev.pose_auc([0.0] * 10, [5, 10, 20]), [1.0, 1.0, 1.0])
        self.assertEqual(ev.pose_auc([50.0] * 10, [5, 10, 20]), [0.0, 0.0, 0.0])
        # Half the pairs perfect, half hopeless -> 0.5 everywhere.
        self.assertTrue(np.allclose(ev.pose_auc([0.0] * 5 + [90.0] * 5, [5, 10]), 0.5))
        self.assertAlmostEqual(ev.mean_average_accuracy([0.0, 0.0]), 1.0)
        # Error 5.5 deg passes thresholds 6..10 -> 5 of 10 thresholds.
        self.assertAlmostEqual(ev.mean_average_accuracy([5.5]), 0.5)


class TestPoseConvention(unittest.TestCase):
    def test_relative_pose_and_solver_recovery(self):
        """World-to-camera poses: X2 = R_rel X1 + t_rel with R_rel = R2 R1^T, t_rel = t2 - R_rel t1;
        PoseLib must recover that pose from noiseless projections."""
        rng = np.random.default_rng(1)
        R1, R2 = random_rotation(rng), random_rotation(rng)
        t1, t2 = rng.normal(size=3), rng.normal(size=3)
        R_rel, t_rel = R2 @ R1.T, t2 - (R2 @ R1.T) @ t1
        X = rng.uniform(-1, 1, size=(200, 3))
        X1 = X @ R1.T + t1
        self.assertTrue(np.allclose(X @ R2.T + t2, X1 @ R_rel.T + t_rel))

        # Place points in front of camera 1 and project into both views.
        X1 = np.c_[rng.uniform(-1, 1, (200, 2)), rng.uniform(4, 8, 200)]
        X2 = X1 @ R_rel.T + t_rel
        keep = X2[:, 2] > 0.5
        if keep.sum() < 20:  # degenerate draw; flip the second camera's viewing direction
            R_rel = np.diag([1, -1, -1.0]) @ R_rel
            t_rel = np.diag([1, -1, -1.0]) @ t_rel
            X2 = X1 @ R_rel.T + t_rel
            keep = X2[:, 2] > 0.5
        K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1.0]])
        p1 = (X1[keep] @ K.T)[:, :2] / X1[keep][:, 2:]
        p2 = (X2[keep] @ K.T)[:, :2] / X2[keep][:, 2:]

        class Args:
            threshold, max_iters, min_iters, seed = 1.0, 1000, 100, 0
        R_est, t_est, n_inl, _ = ev.estimate_poselib(p1, p2, K, K, Args)
        self.assertLess(ev.rotation_error_deg(np.asarray(R_est), R_rel), 0.1)
        self.assertLess(ev.translation_error_deg(np.asarray(t_est), t_rel), 0.1)
        self.assertEqual(n_inl, keep.sum())


class TestColmapReader(unittest.TestCase):
    def test_text_model(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cameras.txt").write_text("# c\n1 PINHOLE 640 480 500 510 320 240\n")
            Path(d, "images.txt").write_text(
                "# i\n1 1 0 0 0 0.5 0 0 1 a.jpg\n10 20 7 11 22 -1 12 22 8\n"
                "2 0.7071068 0 0.7071068 0 0 0 1 1 b.jpg\n\n")
            cams, ims = read_model(d)
            self.assertTrue(np.allclose(cams[1].K, [[500, 0, 320], [0, 510, 240], [0, 0, 1]]))
            self.assertTrue(np.allclose(ims["a.jpg"].R, np.eye(3)))
            self.assertEqual(ims["a.jpg"].point3D_ids.tolist(), [7, 8])  # -1 dropped, sorted
            self.assertEqual(len(ims["b.jpg"].point3D_ids), 0)
            self.assertAlmostEqual(np.linalg.det(ims["b.jpg"].R), 1.0)
            self.assertTrue(np.allclose(ims["b.jpg"].R @ [1, 0, 0], [0, 0, -1], atol=1e-6))


class TestSampler(unittest.TestCase):
    def setUp(self):
        mk = lambda n, ids: Image(n, np.eye(3), np.zeros(3), 1, np.array(sorted(ids)))
        # a, b, c share points 0..19; d shares only 3 points with a.
        self.images = {"a": mk("a", range(0, 40)), "b": mk("b", range(0, 30)),
                       "c": mk("c", list(range(0, 20)) + list(range(100, 120))),
                       "d": mk("d", [0, 1, 2] + list(range(200, 260)))}

    def test_graph_filters(self):
        _, shared = covisibility_graph(self.images, min_shared=10, min_overlap=0.1)
        self.assertEqual(shared, {("a", "b"): 30, ("a", "c"): 20, ("b", "c"): 20})

    def test_triplets(self):
        out = sample(self.images, 3, 10, 10, 0.1, np.random.default_rng(0))
        self.assertEqual([t[0] for t in out], [("a", "b", "c")])
        self.assertEqual(out[0][1], 20)


class TestHrubyNormalization(unittest.TestCase):
    def test_normalized_problem_properties(self):
        """Port of data_sampler.cxx normalize(): view 3's ray centroid maps to the optical axis and its
        4th point onto y = 0, and the rotations are proper (det = +1)."""
        from sample_hruby4p3v import normalize
        rng = np.random.default_rng(3)
        for _ in range(50):
            views = [[np.r_[rng.uniform(-0.5, 0.5, 2), 1.0] for _ in range(4)] for _ in range(3)]
            C, perm3, perm4 = normalize(views)
            self.assertEqual(sorted(perm3), [0, 1, 2])
            self.assertEqual(sorted(perm4), [0, 1, 2, 3])
            for M in C:
                self.assertAlmostEqual(np.linalg.det(M), 1.0)
            old_view3 = perm3.index(2)
            rays = [C[2] @ (v / np.linalg.norm(v)) for v in views[old_view3]]
            centroid = np.mean(rays, axis=0)
            self.assertLess(np.hypot(centroid[0], centroid[1]), 1e-12)
            self.assertLess(abs(rays[perm4[3]][1]), 1e-12)


if __name__ == "__main__":
    unittest.main()
