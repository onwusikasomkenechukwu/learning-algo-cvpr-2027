"""Keep only triplets whose three images share one intrinsics block (draft v4 Sec. 6.1; student instructions
v5 Task 1.4): ETH3D scenes can hold several camera blocks, and the shared-focal evaluation reads view 1's K
for all three views. Rewrites <feature>.txt in the triplet folder and keeps the full list as
<feature>.all.txt (re-running starts from that full list). The .h5 file is left as it is; the evaluation
only reads triplets named in the list.

  python scripts/filter_same_camera.py $SSD/data/eth3d_triplets/courtyard $SSD/data/eth3d/courtyard/dslr_calibration_undistorted
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from colmap_io import read_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("triplet_dir", type=Path)
    ap.add_argument("model_dir", help="COLMAP model the triplets were built from")
    ap.add_argument("--feature", default="triplets-features_superpoint_800_2048-LG")
    args = ap.parse_args()
    lst, full = args.triplet_dir / f"{args.feature}.txt", args.triplet_dir / f"{args.feature}.all.txt"
    if not full.exists():
        full.write_text(lst.read_text())
    _, images = read_model(args.model_dir, with_points=False)
    cam = {name.rsplit(".", 1)[0]: im.camera_id for name, im in images.items()}
    triplets = [l.split() for l in full.read_text().splitlines() if l.strip()]
    kept = [t for t in triplets if len({cam[n] for n in t}) == 1]
    lst.write_text("".join(" ".join(t) + "\n" for t in kept))
    blocks = sorted({cam[n] for t in triplets for n in t})
    print(f"{args.triplet_dir.name}: kept {len(kept)} of {len(triplets)} triplets with one intrinsics block "
          f"(camera ids used: {blocks})")


if __name__ == "__main__":
    main()
