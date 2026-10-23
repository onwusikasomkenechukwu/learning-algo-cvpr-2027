"""Fix two out-of-bounds accesses in kocurvik/PoseLib @ 272ce27 (branch threeview), robust/estimators/
relative_pose.cc. Run by scripts/build_seed_code.sh after poselib-threeview.patch; edits in place, idempotent,
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

Every '+ R' result computed before this fix used the undefined fifth point and should be rerun.

  python scripts/patches/poselib_oob_fixes.py third_party/PoseLib-threeview
"""
import sys
from pathlib import Path

MARK = "OOB fix"
EDITS = [
    ("    size_t n = 4 + opt.inner_refine_extra;\n",
     "    // OOB fix: `sample` holds sample_sz entries (4 for 4p3v); never read past it\n"
     "    size_t n = std::min(sample.size(), static_cast<size_t>(4 + opt.inner_refine_extra));\n", 2),
    ("    std::vector<Point3D> triangulated_12;\n    triangulated_12.reserve(3);\n",
     "    std::vector<Point3D> triangulated_12(3);  // OOB fix: was reserve(3), so p3p read past the end\n", 1),
]


def main():
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
