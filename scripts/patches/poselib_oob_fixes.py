"""Fix three out-of-bounds or uninitialized accesses in kocurvik/PoseLib @ 272ce27 (branch threeview), in
robust/estimators/relative_pose.cc and robust/jacobian_impl.h. Run by scripts/build_seed_code.sh after poselib-threeview.patch; edits in place, idempotent,
fails loudly if an anchor is missing.

1. inner_refine of ThreeViewRelativePoseEstimator (eval.py) and ThreeViewSharedFocalRelativePoseEstimator
   (eval_f.py) copies sample[k] for k < 4 + inner_refine_extra (default 1), but `sample` holds sample_sz
   entries, 4 for every 4p3v method. sample[4] is read past the end: whatever lies there becomes an index into
   the matches, so '+ R' either refines on an arbitrary fifth track or, when the junk is large, reads far out
   of bounds. On abl-dell this produced general protection faults in poselib (kernel log 2026-10-23) and
   eval_f.py runs that never finished. Now n = min(sample.size(), 4 + inner_refine_extra): 4p3v refines on
   its four sampled tracks, 5p3v and 6p3v (sample_sz >= 5) are unchanged.
2. The shared-focal estimate_models declared `std::vector<Point3D> triangulated_12; reserve(3);` and wrote
   triangulated_12[i]: the vector stays empty and p3p read X[0..2] past its end (inside the reserved memory, so
   it worked by luck). It is now constructed with three elements, as the calibrated estimator does.

3. The three-view Jacobians (jacobian_impl.h) zero the part of J12 that does not depend on view 3 with
   J12.block<1, 6>(0, 6), but view 3's parameters start at column 5. Column 5 (first rotation parameter of view 3)
   was never set, so every LM step of the three-view refinement added stack garbage to JtJ; in the calibrated
   accumulator (1 x 11) the block also wrote one double past the end (Eigen asserts on it in a build with
   assertions, found 2026-10-28). It affects LO and the final refinement of every three-view estimator
   (refine_3v_relpose and refine_3v_shared_focal_relpose). Now block<1, 6>(0, 5) in both.

Every '+ R' result computed before fix 1 used the undefined fifth point and should be rerun; every result computed
before fix 3 used the uninitialized Jacobian entry.

  python scripts/patches/poselib_oob_fixes.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "OOB fix"
JAC_MARK = "OOB fix 3"
JAC_EDIT = ("            J12.block<1, 6>(0, 6).setZero();\n",
            "            J12.block<1, 6>(0, 5).setZero();  // OOB fix 3: view 3's parameters start at column 5\n", 2)
EDITS = [
    ("    size_t n = 4 + opt.inner_refine_extra;\n",
     "    // OOB fix: `sample` holds sample_sz entries (4 for 4p3v); never read past it\n"
     "    size_t n = std::min(sample.size(), static_cast<size_t>(4 + opt.inner_refine_extra));\n", 2),
    ("    std::vector<Point3D> triangulated_12;\n    triangulated_12.reserve(3);\n",
     "    std::vector<Point3D> triangulated_12(3);  // OOB fix: was reserve(3), so p3p read past the end\n", 1),
]


def fix_jacobians(root):
    src = root / "PoseLib" / "robust" / "jacobian_impl.h"
    text = src.read_text()
    if JAC_MARK in text:
        print(f"OOB fix 3 already in {src}")
        return
    old, new, count = JAC_EDIT
    if text.count(old) != count:
        sys.exit(f"ERROR: expected {count} x {old.strip()!r} in {src}, found {text.count(old)}")
    src.write_text(text.replace(old, new))
    print(f"OOB fix 3 applied to {src}")


def main():
    fix_jacobians(Path(sys.argv[1]))
    src = Path(sys.argv[1]) / "PoseLib" / "robust" / "estimators" / "relative_pose.cc"
    text = src.read_text()
    if MARK in text:
        print(f"OOB fixes already in {src}")
        return
    for old, new, count in EDITS:
        found = text.count(old)
        if found != count:
            sys.exit(f"ERROR: expected {count} x {old.strip()!r} in {src}, found {found}")
        text = text.replace(old, new)
    if "#include <algorithm>" not in text:
        first = text.index("#include")
        text = text[:first] + "#include <algorithm>\n" + text[first:]
    src.write_text(text)
    print(f"OOB fixes applied to {src}")


if __name__ == "__main__":
    main()
