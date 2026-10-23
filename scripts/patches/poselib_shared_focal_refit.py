"""Add the two-view refit (kill test A, student instructions v5 Task 1.9; draft v4 'two-view refit') to the
shared-focal three-view estimator of kocurvik/PoseLib @ 272ce27 (branch threeview). Run by
scripts/build_seed_code.sh after poselib-threeview.patch; it edits the source in place and fails loudly if
its anchors are missing.

With RansacOptions.early_nonminimal set (eval_f.py label '+ ENM', see threeview_enm.py), every six-point
solution of ThreeViewSharedFocalRelativePoseEstimator::estimate_models is refitted before P3P adds view 3:
the matches whose Sampson error under that solution is below max_epipolar_error re-estimate the focal length
and the two-view pose by Levenberg-Marquardt (refine_shared_focal_relpose: Sampson error, Cauchy loss,
lo_iterations steps), and triangulation and P3P then use the refitted pair. Nothing else changes, and the
option was unused by this estimator before, so every existing label behaves as released.

  python scripts/patches/poselib_shared_focal_refit.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "// Two-view refit (kill test A"
ANCHOR = "void ThreeViewSharedFocalRelativePoseEstimator::estimate_models(std::vector<ImageTriplet> *models) {"
LOOP = "for (ImagePair pair12 : models12){"
BLOCK = """        // Two-view refit (kill test A, Task 1.9): refit f and the pose of views 1-2 on every match whose
        // Sampson error under this solution is below the threshold, before triangulation and P3P add view 3.
        if (opt.early_nonminimal) {
            Eigen::Matrix3d E12;
            essential_from_motion(pair12.pose, &E12);
            Eigen::DiagonalMatrix<double, 3> K_inv(1, 1, pair12.camera1.focal());
            const Eigen::Matrix3d F12 = K_inv * E12 * K_inv;
            const double sq_thr = opt.max_epipolar_error * opt.max_epipolar_error;
            std::vector<Point2D> x1_inl, x2_inl;
            for (size_t k = 0; k < x1.size(); ++k) {
                const Eigen::Vector3d p1 = x1[k].homogeneous(), p2 = x2[k].homogeneous();
                const Eigen::Vector3d Fp1 = F12 * p1, Ftp2 = F12.transpose() * p2;
                const double r = p2.dot(Fp1);
                const double den = Fp1.head<2>().squaredNorm() + Ftp2.head<2>().squaredNorm();
                if (den > 0 && r * r / den < sq_thr) {
                    x1_inl.push_back(x1[k]);
                    x2_inl.push_back(x2[k]);
                }
            }
            if (x1_inl.size() >= 6) {
                BundleOptions refit_opt;
                refit_opt.loss_type = BundleOptions::CAUCHY;
                refit_opt.loss_scale = opt.max_epipolar_error;
                refit_opt.max_iterations = opt.lo_iterations;
                refine_shared_focal_relpose(x1_inl, x2_inl, &pair12, refit_opt);
            }
        }
"""


def main():
    src = Path(sys.argv[1]) / "PoseLib" / "robust" / "estimators" / "relative_pose.cc"
    text = src.read_text()
    if MARK in text:
        print(f"refit already in {src}")
        return
    a = text.find(ANCHOR)
    if a < 0:
        sys.exit(f"ERROR: {ANCHOR!r} not found in {src}")
    b = text.find(LOOP, a)
    nxt = text.find("::estimate_models(", a + len(ANCHOR))
    if b < 0 or (0 <= nxt < b):
        sys.exit(f"ERROR: {LOOP!r} not found in the shared-focal estimate_models of {src}")
    eol = text.index("\n", b) + 1
    src.write_text(text[:eol] + BLOCK + text[eol:])
    print(f"two-view refit added to {src}")


if __name__ == "__main__":
    main()
