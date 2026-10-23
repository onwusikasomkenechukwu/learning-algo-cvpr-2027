"""Let threeview's eval_f.py switch on the shared-focal two-view refit (poselib_shared_focal_refit.py): an
experiment label containing '+ ENM' sets RansacOptions.early_nonminimal, as eval.py's calibrated '+ ENM'
labels do. Edits eval_f.py in place after its ransac_dict literal (idempotent; fails loudly if the literal
is not found). Labels without '+ ENM' are unchanged.

  python scripts/patches/threeview_enm.py third_party/threeview
"""
import re
import sys
from pathlib import Path

MARK = "ransac_dict['early_nonminimal']"


def main():
    src = Path(sys.argv[1]) / "eval_f.py"
    lines = src.read_text().splitlines(keepends=True)
    if any(MARK in l for l in lines):
        print(f"'+ ENM' already mapped in {src}")
        return
    start = next((i for i, l in enumerate(lines) if re.match(r"\s*ransac_dict = \{", l)), None)
    if start is None:
        sys.exit(f"ERROR: no 'ransac_dict = {{' line in {src}")
    end = next((i for i in range(start, len(lines)) if "'oracle': oracle}" in lines[i]), None)
    if end is None:
        sys.exit(f"ERROR: the ransac_dict literal in {src} does not end with 'oracle': oracle}}")
    indent = re.match(r"\s*", lines[start]).group(0)
    lines.insert(end + 1, f"{indent}{MARK} = '+ ENM' in experiment  # two-view refit (kill test A)\n")
    src.write_text("".join(lines))
    print(f"'+ ENM' mapped to early_nonminimal in {src}")


if __name__ == "__main__":
    main()
