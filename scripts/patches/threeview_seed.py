"""Let threeview's eval_f.py take the RANSAC seed from $EVALF_SEED (default 0, PoseLib's own default, so runs
without it are unchanged). eval_f.py never sets RansacOptions.seed, so repeating a run gives identical results;
kill test A asks for three runs (student instructions v5), which need different seeds. Edits eval_f.py in place
after the '+ ENM' line of threeview_enm.py (run that first; idempotent; fails loudly if the line is missing).

  python scripts/patches/threeview_seed.py third_party/threeview
"""
import re
import sys
from pathlib import Path

MARK = "ransac_dict['seed']"
ANCHOR = "ransac_dict['early_nonminimal']"


def main():
    src = Path(sys.argv[1]) / "eval_f.py"
    lines = src.read_text().splitlines(keepends=True)
    if any(MARK in l for l in lines):
        print(f"RANSAC seed already read from EVALF_SEED in {src}")
        return
    at = next((i for i, l in enumerate(lines) if ANCHOR in l), None)
    if at is None:
        sys.exit(f"ERROR: no {ANCHOR} line in {src} (run threeview_enm.py first)")
    if not any(re.match(r"import os\b", l) for l in lines):
        sys.exit(f"ERROR: {src} does not import os")
    indent = re.match(r"\s*", lines[at]).group(0)
    lines.insert(at + 1, f"{indent}{MARK} = int(os.environ.get('EVALF_SEED', '0'))  # repeated runs (kill test A)\n")
    src.write_text("".join(lines))
    print(f"RANSAC seed read from EVALF_SEED in {src}")


if __name__ == "__main__":
    main()
