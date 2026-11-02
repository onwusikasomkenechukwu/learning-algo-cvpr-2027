"""Add the two-view refit (kill test A, student instructions v5 Task 1.9; draft v4 'two-view refit') to the
shared-focal three-view estimator of kocurvik/PoseLib @ 272ce27 (branch threeview). Run by
scripts/build_seed_code.sh after poselib-threeview.patch; it edits the source in place and fails loudly if
its anchors are missing.

With RansacOptions.early_nonminimal set (eval_f.py label '+ ENM', see threeview_enm.py), every six-point
solution of ThreeViewSharedFocalRelativePoseEstimator::estimate_models is refitted before P3P adds view 3:
the matches whose Sampson error under that solution is below max_epipolar_error re-estimate the focal length
and the two-view pose by Levenberg-Marquardt (refine_shared_focal_relpose: Sampson error, Cauchy loss,
lo_iterations steps), and triangulation and P3P then use the refitted pair. Nothing else changes, and the
option was unused by this estimator before, so every existing label behaves as released. Three ablation switches
(environment variables, all off by default) are described at the top of BLOCK.

  python scripts/patches/poselib_shared_focal_refit.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "// Two-view refit (kill test A"
ANCHOR = "void ThreeViewSharedFocalRelativePoseEstimator::estimate_models(std::vector<ImageTriplet> *models) {"
LOOP = "for (ImagePair pair12 : models12){"
BLOCK = """        // Two-view refit (kill test A, Task 1.9): refit f and the pose of views 1-2 on every match whose
        // Sampson error under this solution is below the threshold, before triangulation and P3P add view 3.
        // Ablations (draft v5 supplement), environment variables read once per process, all off by default:
        //   POSELIB_REFIT_LOSS=squared   least squares instead of the Cauchy loss
        //   POSELIB_REFIT_RESELECT=1     reselect the inliers under the refitted pair and refit once more
        //   POSELIB_REFIT_NEWBEST=1      refit only roots whose two-view support beats the best so far
        if (opt.early_nonminimal) {
            static const bool refit_squared = std::getenv("POSELIB_REFIT_LOSS") != nullptr &&
                                              std::string(std::getenv("POSELIB_REFIT_LOSS")) == "squared";
            static const bool refit_reselect = std::getenv("POSELIB_REFIT_RESELECT") != nullptr &&
                                               std::string(std::getenv("POSELIB_REFIT_RESELECT")) == "1";
            static const bool refit_newbest = std::getenv("POSELIB_REFIT_NEWBEST") != nullptr &&
                                              std::string(std::getenv("POSELIB_REFIT_NEWBEST")) == "1";
            const double sq_thr = opt.max_epipolar_error * opt.max_epipolar_error;
            std::vector<Point2D> x1_inl, x2_inl;
            auto two_view_inliers = [&](const ImagePair &pair) {
                Eigen::Matrix3d E12;
                essential_from_motion(pair.pose, &E12);
                Eigen::DiagonalMatrix<double, 3> K_inv(1, 1, pair.camera1.focal());
                const Eigen::Matrix3d F12 = K_inv * E12 * K_inv;
                x1_inl.clear();
                x2_inl.clear();
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
            };
            two_view_inliers(pair12);
            if (x1_inl.size() >= 6 && (!refit_newbest || x1_inl.size() > refit_best_support)) {
                if (refit_newbest)
                    refit_best_support = x1_inl.size();
                BundleOptions refit_opt;
                refit_opt.loss_type = refit_squared ? BundleOptions::TRIVIAL : BundleOptions::CAUCHY;
                refit_opt.loss_scale = opt.max_epipolar_error;
                refit_opt.max_iterations = opt.lo_iterations;
                refine_shared_focal_relpose(x1_inl, x2_inl, &pair12, refit_opt);
                if (refit_reselect) {
                    two_view_inliers(pair12);
                    if (x1_inl.size() >= 6)
                        refine_shared_focal_relpose(x1_inl, x2_inl, &pair12, refit_opt);
                }
            }
        }
"""

# the estimator's best two-view support so far (POSELIB_REFIT_NEWBEST); estimate_models is not const
H_ANCHOR = "    void generate_nn_init_delta_models(std::vector<ImageTriplet> *models);\n"
H_MEMBER = "    size_t refit_best_support = 0;  // two-view refit ablation (poselib_shared_focal_refit.py)\n"


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
    text = text[:eol] + BLOCK + text[eol:]
    first = text.index("#include")
    src.write_text(text[:first] + "#include <cstdlib>\n#include <string>\n" + text[first:])
    hdr = src.with_suffix(".h")
    h = hdr.read_text()
    if h.count(H_ANCHOR) != 1:
        sys.exit(f"ERROR: expected one {H_ANCHOR.strip()!r} in {hdr}")
    hdr.write_text(h.replace(H_ANCHOR, H_ANCHOR + H_MEMBER))
    print(f"two-view refit added to {src}")


if __name__ == "__main__":
    main()
