"""GeoCalib focal lengths for the focal-prior row of draft v5 Table 1 ('5p3v + R + C + PRIOR(geocalib)').

For every image that is view 1 of a triplet in the given triplet lists, GeoCalib (Veicht et al., ECCV 2024; pinhole
model, defaults) predicts the focal length from that image alone. The prediction is rescaled to the image's full
resolution (the resolution of K.h5) and written to <triplet dir>/geocalib_focals.h5 (image name -> f in pixels), which
eval_f.py reads through $EVALF_FOCALS (threeview_extra.py). Images already in the file are skipped (resumable).

Needs the geocalib package (pip install "git+https://github.com/cvg/GeoCalib#egg=geocalib"; weights download on first
use). Not run on the laptop: written for abl-dell (CPU).

  python scripts/geocalib_focals.py $SSD/data/cambridge_triplets/KingsCollege $SSD/data/cambridge/KingsCollege \
      --lists triplets-features_superpoint_800_2048-LG.txt triplets-SIFT_triplet_correspondences-rootsift8000.txt
"""
import argparse
import time
from pathlib import Path

import h5py
import numpy as np

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".JPG", ".JPEG", ".PNG")


def find_image(root, stem):
    """The image file of a triplet name (as src/sift_triplets.py, without its OpenCV import)."""
    for ext in IMAGE_EXTS:
        p = Path(root) / (stem + ext)
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"no image for {stem} under {root}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("triplet_dir", type=Path)
    ap.add_argument("image_root", type=Path)
    ap.add_argument("--lists", nargs="+", required=True, help="triplet list files in triplet_dir")
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    import torch
    from geocalib import GeoCalib
    torch.set_num_threads(args.threads)

    names = []
    for lst in args.lists:
        p = args.triplet_dir / lst
        if p.exists():
            names += [l.split()[0] for l in p.read_text().splitlines() if l.strip()]
    names = list(dict.fromkeys(names))
    out = args.triplet_dir / "geocalib_focals.h5"
    with h5py.File(out, "a") as fh:
        done = set()
        fh.visititems(lambda k, v: done.add(k) if isinstance(v, h5py.Dataset) else None)
        todo = [n for n in names if n not in done]
        print(f"{args.triplet_dir.name}: {len(names)} view-1 images, {len(todo)} to predict", flush=True)
        if not todo:
            return
        model = GeoCalib().eval()
        t0 = time.time()
        for i, n in enumerate(todo):
            path = find_image(str(args.image_root), n)
            image = model.load_image(path)                 # 3 x H x W, full resolution
            h, w = image.shape[-2:]
            with torch.no_grad():
                cam = model.calibrate(image)["camera"]
            f = float(cam.f.reshape(-1, 2)[0].mean())
            size = cam.size.reshape(-1, 2)[0].tolist()     # the resolution the camera refers to
            if abs(size[0] - w) > 1:                        # rescale if GeoCalib answered for a resized image
                f *= w / size[0]
            fh.create_dataset(n, data=np.array([f]))
            if i % 50 == 0:
                fh.flush()
                print(f"  {i + 1}/{len(todo)} {n}: f = {f:.1f} px ({(time.time() - t0) / (i + 1):.2f} s per image)",
                      flush=True)
    print(f"done: {out}")


if __name__ == "__main__":
    main()
