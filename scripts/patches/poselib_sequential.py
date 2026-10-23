"""Add the sequential baseline of Task 2.9 (student instructions v5) to kocurvik/PoseLib @ 272ce27 (branch
threeview): estimate_3v_shared_focal_sequential in PoseLib/robust.cc, its declaration in robust.h and the Python
binding poselib.estimate_three_view_shared_focal_sequential. Run by scripts/build_seed_code.sh after
poselib-threeview.patch; edits in place, idempotent, fails loudly if an anchor is missing.

The function takes the same arguments and normalization as estimate_3v_shared_focal_relative_pose:
  stage 1  shared-focal six-point LO-RANSAC (ransac_shared_focal_relpose) on views 1-2, refined on its inliers
           (refine_shared_focal_relpose), as estimate_shared_focal_relative_pose does;
  stage 2  the stage-1 inliers triangulated at the stage-1 focal length (in front of both cameras), then P3P
           LO-RANSAC (ransac_pnp) on view 3 with the same threshold in pixels;
  finish   the joint estimator's final step: three-view inliers (get_inliers) and refine_3v_shared_focal_relpose.
Threshold, iteration limits and stopping rule come from the same RansacOptions for both stages, so a fixed
iteration count (min = max) runs in both. The returned stats sum the iterations and refinements of both stages;
eval_f.py times the whole call like every other method. threeview_seq.py routes the label '+ SEQ' here.

  python scripts/patches/poselib_sequential.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "estimate_3v_shared_focal_sequential"

CC_ANCHOR = "RansacStats estimate_fundamental(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,"
CC_BLOCK = r"""// Sequential baseline (Task 2.9): shared-focal six-point LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3 against
// the triangulated stage-1 inliers, then the final three-view refinement of estimate_3v_shared_focal_relative_pose.
RansacStats estimate_3v_shared_focal_sequential(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                                const std::vector<Point2D> &x3, const RansacOptions &ransac_opt,
                                                const BundleOptions &bundle_opt, ImageTriplet *image_triplet,
                                                std::vector<char> *inliers, const Point2D &pp) {
    const size_t num_pts = x1.size();
    std::vector<Point2D> x1_norm = x1;
    std::vector<Point2D> x2_norm = x2;
    std::vector<Point2D> x3_norm = x3;
    for (size_t i = 0; i < num_pts; i++) {
        x1_norm[i] -= pp;
        x2_norm[i] -= pp;
        x3_norm[i] -= pp;
    }
    double scale = 0.0;   // the joint estimator's normalization
    for (size_t k = 0; k < num_pts; ++k) {
        scale += x1_norm[k].norm();
        scale += x2_norm[k].norm();
        scale += x3_norm[k].norm();
    }
    scale /= 3.0 * num_pts / std::sqrt(2);
    for (size_t i = 0; i < num_pts; i++) {
        x1_norm[i] /= scale;
        x2_norm[i] /= scale;
        x3_norm[i] /= scale;
    }

    RansacOptions opt = ransac_opt;
    opt.max_epipolar_error = ransac_opt.max_epipolar_error / scale;
    BundleOptions bundle_opt_scaled = bundle_opt;
    bundle_opt_scaled.loss_scale = bundle_opt.loss_scale / scale;

    RansacStats stats;
    inliers->assign(num_pts, 0);

    // Stage 1: views 1-2
    ImagePair pair;
    std::vector<char> inliers12;
    RansacStats stats12 = ransac_shared_focal_relpose(x1_norm, x2_norm, opt, &pair, &inliers12);
    if (inliers12.size() != num_pts)   // RANSAC can return early (too few matches) without a mask
        inliers12.assign(num_pts, 0);
    stats.iterations = stats12.iterations;
    stats.refinements = stats12.refinements;
    if (stats12.num_inliers > 6) {
        std::vector<Point2D> x1_in, x2_in;
        for (size_t k = 0; k < num_pts; ++k) {
            if (inliers12[k]) {
                x1_in.push_back(x1_norm[k]);
                x2_in.push_back(x2_norm[k]);
            }
        }
        refine_shared_focal_relpose(x1_in, x2_in, &pair, bundle_opt_scaled);
    }
    pair.camera2 = pair.camera1;

    // Stage 2: view 3 by P3P against the stage-1 inliers, triangulated at the stage-1 focal length
    const double f = pair.camera1.focal();
    std::vector<Point2D> x3_calib;
    std::vector<Point3D> X;
    for (size_t k = 0; k < num_pts && f > 0; ++k) {
        if (!inliers12[k])
            continue;
        const Point3D Xk = triangulate(pair, x1_norm[k].homogeneous(), x2_norm[k].homogeneous());
        const Eigen::Vector3d X2 = pair.pose.R() * Xk + pair.pose.t;
        if (!Xk.allFinite() || Xk(2) <= 0 || X2(2) <= 0)
            continue;
        X.push_back(Xk);
        x3_calib.push_back(x3_norm[k] / f);
    }
    CameraPose pose13;
    if (X.size() >= 4) {
        RansacOptions opt3 = opt;
        opt3.max_reproj_error = opt.max_epipolar_error / f;
        std::vector<char> inliers3;
        RansacStats stats3 = ransac_pnp(x3_calib, X, opt3, &pose13, &inliers3);
        stats.iterations += stats3.iterations;
        stats.refinements += stats3.refinements;
    }
    *image_triplet = ImageTriplet(ThreeViewCameraPose(pair.pose, pose13), pair.camera1);

    // Finish: the final three-view refinement of the joint estimator
    if (X.size() >= 4) {
        const size_t n = get_inliers(*image_triplet, x1_norm, x2_norm, x3_norm,
                                     opt.max_epipolar_error * opt.max_epipolar_error, inliers);
        stats.num_inliers = n;
        stats.inlier_ratio = static_cast<double>(n) / static_cast<double>(num_pts);
        if (n > 4) {
            std::vector<Point2D> x1_in, x2_in, x3_in;
            for (size_t k = 0; k < num_pts; ++k) {
                if (!(*inliers)[k])
                    continue;
                x1_in.push_back(x1_norm[k]);
                x2_in.push_back(x2_norm[k]);
                x3_in.push_back(x3_norm[k]);
            }
            refine_3v_shared_focal_relpose(x1_in, x2_in, x3_in, image_triplet, bundle_opt_scaled);
        }
    }

    image_triplet->camera.params[0] *= scale;
    image_triplet->camera.params[1] = pp(0);
    image_triplet->camera.params[2] = pp(1);
    return stats;
}

"""

H_ANCHOR = "// Estimates relative pose with shared unknown focal length using LO-RANSAC followed by non-linear refinement"
H_BLOCK = """// Sequential baseline (Task 2.9): shared-focal six-point LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3,
// then the three-view refinement of estimate_3v_shared_focal_relative_pose (same arguments and normalization).
RansacStats estimate_3v_shared_focal_sequential(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                                const std::vector<Point2D> &x3, const RansacOptions &ransac_opt,
                                                const BundleOptions &bundle_opt, ImageTriplet *image_triplet,
                                                std::vector<char> *inliers, const Point2D &pp);

"""

PY_ANCHOR = "std::pair<ImagePair, py::dict>\nestimate_shared_focal_relative_pose_wrapper("
PY_BLOCK = """std::pair<ImageTriplet, py::dict>
estimate_three_view_shared_focal_sequential_wrapper(const std::vector<Eigen::Vector2d> points2D_1,
                                                    const std::vector<Eigen::Vector2d> points2D_2,
                                                    const std::vector<Eigen::Vector2d> points2D_3,
                                                    const Eigen::Vector2d pp,
                                                    const py::dict &ransac_opt_dict,
                                                    const py::dict &bundle_opt_dict) {
    RansacOptions ransac_opt;
    update_ransac_options(ransac_opt_dict, ransac_opt);

    BundleOptions bundle_opt;
    bundle_opt.loss_scale = 0.5 * ransac_opt.max_epipolar_error;
    update_bundle_options(bundle_opt_dict, bundle_opt);

    ImageTriplet image_triplet;
    std::vector<char> inlier_mask;

    RansacStats stats = estimate_3v_shared_focal_sequential(points2D_1, points2D_2, points2D_3, ransac_opt,
                                                            bundle_opt, &image_triplet, &inlier_mask, pp);
    py::dict output_dict;
    write_to_dict(stats, output_dict);
    output_dict["inliers"] = convert_inlier_vector(inlier_mask);
    return std::make_pair(image_triplet, output_dict);
}

"""

DEF_ANCHOR = '    m.def("estimate_shared_focal_relative_pose", &poselib::estimate_shared_focal_relative_pose_wrapper,'
DEF_BLOCK = """    m.def("estimate_three_view_shared_focal_sequential",
          &poselib::estimate_three_view_shared_focal_sequential_wrapper, py::arg("points2D_1"),
          py::arg("points2D_2"), py::arg("points2D_3"), py::arg("pp") = Eigen::Vector2d(0.0, 0.0),
          py::arg("ransac_opt") = py::dict(), py::arg("bundle_opt") = py::dict(),
          "Sequential baseline: shared-focal 6pt LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3, 3-view refinement.");
"""


def insert_before(path, anchor, block):
    text = path.read_text()
    if text.count(anchor) != 1:
        sys.exit(f"ERROR: expected one {anchor[:60]!r} in {path}, found {text.count(anchor)}")
    path.write_text(text.replace(anchor, block + anchor))


def main():
    root = Path(sys.argv[1])
    cc, h, py = root / "PoseLib" / "robust.cc", root / "PoseLib" / "robust.h", root / "pybind" / "pyposelib.cc"
    if MARK in cc.read_text():
        print(f"sequential baseline already in {root}")
        return
    insert_before(cc, CC_ANCHOR, CC_BLOCK)
    insert_before(h, H_ANCHOR, H_BLOCK)
    insert_before(py, PY_ANCHOR, PY_BLOCK)
    insert_before(py, DEF_ANCHOR, DEF_BLOCK)
    print(f"sequential baseline added to {root}")


if __name__ == "__main__":
    main()
