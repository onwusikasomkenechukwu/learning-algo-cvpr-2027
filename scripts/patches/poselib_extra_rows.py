"""Two estimators for the remaining rows of draft v5 in kocurvik/PoseLib @ 272ce27 (branch threeview), with Python
bindings. Run by scripts/build_seed_code.sh after poselib_sequential.py; edits in place, idempotent, fails loudly if
an anchor is missing.

estimate_3v_relative_pose_sequential (poselib.estimate_three_view_relative_pose_sequential), Table 3: the calibrated
  sequential pipeline, with the arguments and normalization of estimate_3v_relative_pose:
    stage 1  five-point LO-RANSAC (ransac_relpose) on views 1-2, refined on its inliers (refine_relpose);
    stage 2  the stage-1 inliers triangulated (in front of both cameras), then P3P LO-RANSAC (ransac_pnp) on view 3
             with the same threshold;
    finish   three-view inliers (get_inliers) and refine_3v_relpose, as the joint estimator ends.
  Both stages read the same RansacOptions, so a fixed iteration count (min = max) runs in both.

refine_3v_shared_focal_from_init (poselib.refine_three_view_shared_focal_from_init), Table 1 rows with a focal prior
  and the network row: three-view LO from given cameras (focal length in pixels, poses 1-2 and 1-3), in the
  normalization of estimate_3v_shared_focal_relative_pose: `rounds` times three-view inliers (get_inliers, the
  RANSAC threshold) and refine_3v_shared_focal_relpose on them, which refines the poses and the shared focal length.

  python scripts/patches/poselib_extra_rows.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "estimate_3v_relative_pose_sequential"

CC_ANCHOR = "RansacStats estimate_fundamental(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,"
CC_BLOCK = r"""// Calibrated sequential pipeline (draft v5 Table 3): five-point LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3
// against the triangulated stage-1 inliers, then the final three-view refinement of estimate_3v_relative_pose.
RansacStats estimate_3v_relative_pose_sequential(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                                 const std::vector<Point2D> &x3, const Camera &camera1,
                                                 const Camera &camera2, const Camera &camera3,
                                                 const RansacOptions &ransac_opt, const BundleOptions &bundle_opt,
                                                 ThreeViewCameraPose *three_view_pose, std::vector<char> *inliers,
                                                 std::vector<double> *diag) {
    const size_t num_pts = x1.size();
    std::vector<Point2D> x1_calib(num_pts), x2_calib(num_pts), x3_calib(num_pts);
    for (size_t k = 0; k < num_pts; ++k) {
        camera1.unproject(x1[k], &x1_calib[k]);
        camera2.unproject(x2[k], &x2_calib[k]);
        camera3.unproject(x3[k], &x3_calib[k]);
    }
    RansacOptions opt = ransac_opt;   // the joint estimator's threshold scaling
    opt.max_epipolar_error = ransac_opt.max_epipolar_error * (3.0 / (camera1.focal() + camera2.focal() + camera3.focal()));
    BundleOptions bundle_opt_scaled = bundle_opt;
    bundle_opt_scaled.loss_scale =
        bundle_opt.loss_scale * 0.5 * (1.0 / camera1.focal() + 1.0 / camera2.focal() + 1.0 / camera3.focal());

    RansacStats stats;
    inliers->assign(num_pts, 0);
    *three_view_pose = ThreeViewCameraPose();

    // Stage 1: views 1-2
    CameraPose pose12;
    std::vector<char> inliers12;
    RansacStats stats12 = ransac_relpose(x1_calib, x2_calib, opt, &pose12, &inliers12);
    if (inliers12.size() != num_pts)
        inliers12.assign(num_pts, 0);
    stats.iterations = stats12.iterations;
    stats.refinements = stats12.refinements;
    if (stats12.num_inliers > 5) {
        std::vector<Point2D> x1_in, x2_in;
        for (size_t k = 0; k < num_pts; ++k) {
            if (inliers12[k]) {
                x1_in.push_back(x1_calib[k]);
                x2_in.push_back(x2_calib[k]);
            }
        }
        refine_relpose(x1_in, x2_in, &pose12, bundle_opt_scaled);
    }

    // Stage 2: view 3 by P3P against the triangulated stage-1 inliers
    std::vector<Point2D> x3_s;
    std::vector<Point3D> X;
    for (size_t k = 0; k < num_pts; ++k) {
        if (!inliers12[k])
            continue;
        const Point3D Xk = triangulate(pose12, x1_calib[k].homogeneous(), x2_calib[k].homogeneous());
        const Eigen::Vector3d X2 = pose12.R() * Xk + pose12.t;
        if (!Xk.allFinite() || Xk(2) <= 0 || X2(2) <= 0)
            continue;
        X.push_back(Xk);
        x3_s.push_back(x3_calib[k]);
    }
    CameraPose pose13;
    size_t inl3 = 0;
    if (X.size() >= 4) {
        RansacOptions opt3 = opt;
        opt3.max_reproj_error = opt.max_epipolar_error;
        std::vector<char> inliers3;
        RansacStats stats3 = ransac_pnp(x3_s, X, opt3, &pose13, &inliers3);
        inl3 = stats3.num_inliers;
        stats.iterations += stats3.iterations;
        stats.refinements += stats3.refinements;
    }
    *three_view_pose = ThreeViewCameraPose(pose12, pose13);

    // Finish: the final three-view refinement of the joint estimator
    if (X.size() >= 4) {
        const size_t n = get_inliers(*three_view_pose, x1_calib, x2_calib, x3_calib,
                                     opt.max_epipolar_error * opt.max_epipolar_error, inliers);
        stats.num_inliers = n;
        stats.inlier_ratio = static_cast<double>(n) / static_cast<double>(num_pts);
        if (n > 4) {
            std::vector<Point2D> x1_in, x2_in, x3_in;
            for (size_t k = 0; k < num_pts; ++k) {
                if (!(*inliers)[k])
                    continue;
                x1_in.push_back(x1_calib[k]);
                x2_in.push_back(x2_calib[k]);
                x3_in.push_back(x3_calib[k]);
            }
            refine_3v_relpose(x1_in, x2_in, x3_in, three_view_pose, bundle_opt_scaled);
        }
    }
    if (diag != nullptr)   // stage-1 inliers, triangulated points, P3P inliers, final inliers
        *diag = {static_cast<double>(stats12.num_inliers), static_cast<double>(X.size()), static_cast<double>(inl3),
                 static_cast<double>(stats.num_inliers)};
    return stats;
}

// Three-view LO from given cameras (draft v5 Table 1: focal priors, network row): `rounds` times three-view inliers
// and refine_3v_shared_focal_relpose, in the normalization of estimate_3v_shared_focal_relative_pose.
RansacStats refine_3v_shared_focal_from_init(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                             const std::vector<Point2D> &x3, const Point2D &pp, double focal,
                                             const CameraPose &pose12, const CameraPose &pose13,
                                             const RansacOptions &ransac_opt, const BundleOptions &bundle_opt,
                                             ImageTriplet *image_triplet, std::vector<char> *inliers, int rounds) {
    const size_t num_pts = x1.size();
    std::vector<Point2D> x1_norm = x1, x2_norm = x2, x3_norm = x3;
    double scale = 0.0;
    for (size_t k = 0; k < num_pts; ++k) {
        x1_norm[k] -= pp;
        x2_norm[k] -= pp;
        x3_norm[k] -= pp;
        scale += x1_norm[k].norm() + x2_norm[k].norm() + x3_norm[k].norm();
    }
    scale = num_pts > 0 ? scale / (3.0 * num_pts / std::sqrt(2)) : 1.0;
    for (size_t k = 0; k < num_pts; ++k) {
        x1_norm[k] /= scale;
        x2_norm[k] /= scale;
        x3_norm[k] /= scale;
    }
    const double thr = ransac_opt.max_epipolar_error / scale;
    BundleOptions bundle_opt_scaled = bundle_opt;
    bundle_opt_scaled.loss_scale = bundle_opt.loss_scale / scale;

    *image_triplet = ImageTriplet(ThreeViewCameraPose(pose12, pose13),
                                  Camera("SIMPLE_PINHOLE", {focal / scale, 0.0, 0.0}, -1, -1));
    RansacStats stats;
    inliers->assign(num_pts, 0);
    for (int r = 0; r <= rounds; ++r) {
        const size_t n = get_inliers(*image_triplet, x1_norm, x2_norm, x3_norm, thr * thr, inliers);
        stats.num_inliers = n;
        stats.inlier_ratio = num_pts > 0 ? static_cast<double>(n) / static_cast<double>(num_pts) : 0.0;
        if (r == rounds || n <= 4)
            break;
        std::vector<Point2D> x1_in, x2_in, x3_in;
        for (size_t k = 0; k < num_pts; ++k) {
            if (!(*inliers)[k])
                continue;
            x1_in.push_back(x1_norm[k]);
            x2_in.push_back(x2_norm[k]);
            x3_in.push_back(x3_norm[k]);
        }
        refine_3v_shared_focal_relpose(x1_in, x2_in, x3_in, image_triplet, bundle_opt_scaled);
        stats.refinements++;
    }
    image_triplet->camera.params[0] *= scale;
    image_triplet->camera.params[1] = pp(0);
    image_triplet->camera.params[2] = pp(1);
    return stats;
}

"""

H_ANCHOR = "// Estimates relative pose with shared unknown focal length using LO-RANSAC followed by non-linear refinement"
H_BLOCK = """// Calibrated sequential pipeline (draft v5 Table 3): five-point LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3,
// then the three-view refinement of estimate_3v_relative_pose (same arguments and normalization).
RansacStats estimate_3v_relative_pose_sequential(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                                 const std::vector<Point2D> &x3, const Camera &camera1,
                                                 const Camera &camera2, const Camera &camera3,
                                                 const RansacOptions &ransac_opt, const BundleOptions &bundle_opt,
                                                 ThreeViewCameraPose *three_view_pose, std::vector<char> *inliers,
                                                 std::vector<double> *diag = nullptr);

// Three-view LO from given cameras (focal length in pixels, poses 1-2 and 1-3): `rounds` times three-view inliers
// and refine_3v_shared_focal_relpose, in the normalization of estimate_3v_shared_focal_relative_pose.
RansacStats refine_3v_shared_focal_from_init(const std::vector<Point2D> &x1, const std::vector<Point2D> &x2,
                                             const std::vector<Point2D> &x3, const Point2D &pp, double focal,
                                             const CameraPose &pose12, const CameraPose &pose13,
                                             const RansacOptions &ransac_opt, const BundleOptions &bundle_opt,
                                             ImageTriplet *image_triplet, std::vector<char> *inliers, int rounds);

"""

PY_ANCHOR = "std::pair<ImagePair, py::dict>\nestimate_shared_focal_relative_pose_wrapper("
PY_BLOCK = """std::pair<ThreeViewCameraPose, py::dict> estimate_three_view_relative_pose_sequential_wrapper(
    const std::vector<Eigen::Vector2d> points2D_1, const std::vector<Eigen::Vector2d> points2D_2,
    const std::vector<Eigen::Vector2d> points2D_3, const py::dict &camera1_dict, const py::dict &camera2_dict,
    const py::dict &camera3_dict, const py::dict &ransac_opt_dict, const py::dict &bundle_opt_dict) {
    Camera camera1 = camera_from_dict(camera1_dict);
    Camera camera2 = camera_from_dict(camera2_dict);
    Camera camera3 = camera_from_dict(camera3_dict);
    RansacOptions ransac_opt;
    update_ransac_options(ransac_opt_dict, ransac_opt);
    BundleOptions bundle_opt;
    bundle_opt.loss_scale = 0.5 * ransac_opt.max_epipolar_error;
    update_bundle_options(bundle_opt_dict, bundle_opt);
    ThreeViewCameraPose three_view_pose;
    std::vector<char> inlier_mask;
    std::vector<double> diag;
    RansacStats stats = estimate_3v_relative_pose_sequential(points2D_1, points2D_2, points2D_3, camera1, camera2,
                                                             camera3, ransac_opt, bundle_opt, &three_view_pose,
                                                             &inlier_mask, &diag);
    py::dict output_dict;
    write_to_dict(stats, output_dict);
    const char *names[] = {"stage1_inliers", "triangulated", "stage2_inliers", "final_inliers"};
    for (size_t k = 0; k < diag.size(); ++k)
        output_dict[names[k]] = diag[k];
    output_dict["inliers"] = convert_inlier_vector(inlier_mask);
    return std::make_pair(three_view_pose, output_dict);
}

std::pair<ImageTriplet, py::dict> refine_three_view_shared_focal_from_init_wrapper(
    const std::vector<Eigen::Vector2d> points2D_1, const std::vector<Eigen::Vector2d> points2D_2,
    const std::vector<Eigen::Vector2d> points2D_3, const Eigen::Vector2d pp, double focal, const Eigen::Matrix3d R12,
    const Eigen::Vector3d t12, const Eigen::Matrix3d R13, const Eigen::Vector3d t13, const py::dict &ransac_opt_dict,
    const py::dict &bundle_opt_dict, int rounds) {
    RansacOptions ransac_opt;
    update_ransac_options(ransac_opt_dict, ransac_opt);
    BundleOptions bundle_opt;
    bundle_opt.loss_scale = 0.5 * ransac_opt.max_epipolar_error;
    update_bundle_options(bundle_opt_dict, bundle_opt);
    ImageTriplet image_triplet;
    std::vector<char> inlier_mask;
    RansacStats stats = refine_3v_shared_focal_from_init(points2D_1, points2D_2, points2D_3, pp, focal,
                                                         CameraPose(R12, t12), CameraPose(R13, t13), ransac_opt,
                                                         bundle_opt, &image_triplet, &inlier_mask, rounds);
    py::dict output_dict;
    write_to_dict(stats, output_dict);
    output_dict["inliers"] = convert_inlier_vector(inlier_mask);
    return std::make_pair(image_triplet, output_dict);
}

"""

DEF_ANCHOR = '    m.def("estimate_shared_focal_relative_pose", &poselib::estimate_shared_focal_relative_pose_wrapper,'
DEF_BLOCK = """    m.def("estimate_three_view_relative_pose_sequential",
          &poselib::estimate_three_view_relative_pose_sequential_wrapper, py::arg("points2D_1"),
          py::arg("points2D_2"), py::arg("points2D_3"), py::arg("camera1_dict"), py::arg("camera2_dict"),
          py::arg("camera3_dict"), py::arg("ransac_opt") = py::dict(), py::arg("bundle_opt") = py::dict(),
          "Calibrated sequential pipeline: 5pt LO-RANSAC on views 1-2, P3P LO-RANSAC on view 3, 3-view refinement.");
    m.def("refine_three_view_shared_focal_from_init", &poselib::refine_three_view_shared_focal_from_init_wrapper,
          py::arg("points2D_1"), py::arg("points2D_2"), py::arg("points2D_3"), py::arg("pp"), py::arg("focal"),
          py::arg("R12"), py::arg("t12"), py::arg("R13"), py::arg("t13"), py::arg("ransac_opt") = py::dict(),
          py::arg("bundle_opt") = py::dict(), py::arg("rounds") = 2,
          "Three-view shared-focal LO (inliers + refinement, `rounds` times) from given cameras.");
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
        print(f"extra rows already in {root}")
        return
    insert_before(cc, CC_ANCHOR, CC_BLOCK)
    insert_before(h, H_ANCHOR, H_BLOCK)
    insert_before(py, PY_ANCHOR, PY_BLOCK)
    insert_before(py, DEF_ANCHOR, DEF_BLOCK)
    print(f"extra rows added to {root}")


if __name__ == "__main__":
    main()
