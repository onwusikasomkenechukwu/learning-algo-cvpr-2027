"""Route eval_f.py experiment labels containing '+ SEQ' (e.g. '6p3v + SEQ') to the sequential baseline of Task 2.9,
poselib.estimate_three_view_shared_focal_sequential (scripts/patches/poselib_sequential.py). The call is timed
by eval_f.py's own perf_counter, like every other method. Edits eval_f.py in place (idempotent; fails loudly if
the call is not found). Other labels are unchanged.

  python scripts/patches/threeview_seq.py third_party/threeview
"""
import sys
from pathlib import Path

CALL = "    out, info = poselib.estimate_three_view_shared_focal_relative_pose(x1, x2, x3, pp, ransac_dict, bundle_dict)\n"
NEW = ("    if '+ SEQ' in experiment:  # Task 2.9 sequential baseline (six-point on views 1-2, then P3P)\n"
       "        out, info = poselib.estimate_three_view_shared_focal_sequential(x1, x2, x3, pp, ransac_dict, bundle_dict)\n"
       "    else:\n"
       "        out, info = poselib.estimate_three_view_shared_focal_relative_pose(x1, x2, x3, pp, ransac_dict, bundle_dict)\n")


def main():
    src = Path(sys.argv[1]) / "eval_f.py"
    text = src.read_text()
    if "estimate_three_view_shared_focal_sequential" in text:
        print(f"'+ SEQ' already routed in {src}")
        return
    if text.count(CALL) != 1:
        sys.exit(f"ERROR: expected one joint-estimator call in {src}, found {text.count(CALL)}")
    src.write_text(text.replace(CALL, NEW))
    print(f"'+ SEQ' routed to the sequential baseline in {src}")


if __name__ == "__main__":
    main()
