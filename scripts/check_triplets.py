"""Check triplet folders before an evaluation run (scripts/run_abl_dell.sh setup): every triplet in a list must
be in its .h5 file, and a SIFT list must be complete.

src/sift_triplets.py before 671f878 wrote its .txt while matching, so a run that was killed left a partial
list that the runner takes as a finished scene. Its rows follow the SP+LG list in order, so a complete SIFT
list ends near the end of the SP+LG list; one that ends before 95 % of it is a cut-off run. With --fix such a
SIFT list (and its .h5) is renamed to *.incomplete so the sift step recomputes it. An unreadable .h5 or a
listed triplet missing from it is reported (exit status 1); those need the scene's triplets regenerated.

  python scripts/check_triplets.py --fix $SSD/data/cambridge_triplets/* $SSD/data/eth3d_triplets/*
"""
import argparse
import sys
from pathlib import Path

import h5py

SP = "triplets-features_superpoint_800_2048-LG"
SIFT = "triplets-SIFT_triplet_correspondences-rootsift8000"


def read_list(p):
    return [" ".join(l.split()) for l in p.read_text().splitlines() if l.strip()]


def missing_in_h5(h5, triplets):
    """Number of listed triplets without a dataset in h5 (None if the file cannot be read)."""
    try:
        with h5py.File(h5, "r") as f:
            return sum("-".join(t.split()) not in f for t in triplets)
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--fix", action="store_true", help="rename cut-off SIFT lists so they are recomputed")
    args = ap.parse_args()
    bad = 0
    for d in args.dirs:
        sp_txt = d / f"{SP}.txt"
        if not sp_txt.exists():
            print(f"{d.name}: no SP+LG list yet")
            continue
        sp = read_list(sp_txt)
        notes = [f"SP+LG {len(sp)}"]
        m = missing_in_h5(d / f"{SP}.h5", sp)
        if m is None or m:
            bad += 1
            notes.append(f"SP+LG h5 {'UNREADABLE' if m is None else f'MISSING {m} triplets'}")
        sift_txt = d / f"{SIFT}.txt"
        if sift_txt.exists():
            sift = read_list(sift_txt)
            pos = {t: i for i, t in enumerate(sp)}
            last = max((pos.get(t, -1) for t in sift), default=-1)
            m = missing_in_h5(d / f"{SIFT}.h5", sift)
            if last + 1 < 0.95 * len(sp) or m is None or m:
                why = f"ends at {last + 1}/{len(sp)}" if last + 1 < 0.95 * len(sp) else \
                    ("h5 unreadable" if m is None else f"{m} missing in h5")
                if args.fix:
                    for p in (sift_txt, d / f"{SIFT}.h5"):
                        if p.exists():
                            p.rename(p.with_name(p.name + ".incomplete"))
                    notes.append(f"SIFT {len(sift)} INCOMPLETE ({why}): moved aside, will be recomputed")
                else:
                    notes.append(f"SIFT {len(sift)} INCOMPLETE ({why})")
            else:
                notes.append(f"SIFT {len(sift)} ok")
        print(f"{d.name}: " + ", ".join(notes))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
