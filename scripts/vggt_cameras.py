"""VGGT cameras for the network row of draft v5 Table 1 ('0p3v(INIT)': VGGT, then the three-view LO).

VGGT (Wang et al., CVPR 2025; facebook/VGGT-1B, default preprocessing) predicts the three cameras of every triplet in
one pass. Its first camera is the identity, so poses 1-2 and 1-3 are the predicted extrinsics of views 2 and 3; both
translations are divided by |t12|. The shared focal length is the mean of the three predicted focal lengths, scaled
from the preprocessed width to the full image width. Rows are written to <out> (h5: 'img1-img2-img3' -> R12 (9),
t12 (3), R13 (9), t13 (3), f), which eval_f.py reads through $EVALF_INIT (threeview_extra.py); finished triplets are
skipped. Network time per triplet goes to <out>.times.txt, reported apart from the LO time as the draft asks.

Needs the vggt package (pip install "git+https://github.com/facebookresearch/vggt") and its weights (downloaded from
Hugging Face on first use). Not run on the laptop: written for abl-dell, where it runs on the CPU (or --device cuda).

  python scripts/vggt_cameras.py $SSD/data/cambridge_triplets/KingsCollege $SSD/data/cambridge/KingsCollege \
      --list triplets-features_superpoint_800_2048-LG.txt --out results/vggt/KingsCollege.h5 --shard 0 --nshards 8
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
    ap.add_argument("--list", default="triplets-features_superpoint_800_2048-LG.txt")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--max-triplets", type=int, default=None)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--merge", action="store_true", help="merge <out stem>.shard*.h5 (and times) into <out>, then exit")
    args = ap.parse_args()

    if args.merge:
        shards = sorted(args.out.parent.glob(f"{args.out.stem}.shard*{args.out.suffix}"))
        n = 0
        with h5py.File(args.out, "a") as fo, open(f"{args.out}.times.txt", "w") as ft:
            for sh in shards:
                with h5py.File(sh, "r") as fi:
                    def copy(k, v):
                        nonlocal n
                        if isinstance(v, h5py.Dataset) and k not in fo:
                            fo.create_dataset(k, data=np.array(v))
                            n += 1
                    fi.visititems(copy)
                t = Path(f"{sh}.times.txt")
                if t.exists():
                    ft.write(t.read_text())
        print(f"merged {len(shards)} shards into {args.out}: {n} new triplets")
        return

    import torch
    from PIL import Image
    from vggt.models.vggt import VGGT
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.utils.pose_enc import pose_encoding_to_extri_intri
    torch.set_num_threads(args.threads)

    triplets = [l.split() for l in (args.triplet_dir / args.list).read_text().splitlines() if l.strip()]
    triplets = triplets[:args.max_triplets][args.shard::args.nshards]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = args.out.with_name(f"{args.out.stem}.shard{args.shard}{args.out.suffix}") if args.nshards > 1 else args.out
    model = None
    with h5py.File(out, "a") as fh, open(f"{out}.times.txt", "a") as ft:
        t0, n_new = time.time(), 0
        for names in triplets:
            key = "-".join(names)
            if key in fh:
                continue
            if model is None:
                model = VGGT.from_pretrained("facebook/VGGT-1B").to(args.device).eval()
            paths = [find_image(str(args.image_root), n) for n in names]
            widths = [Image.open(p).size[0] for p in paths]
            images = load_and_preprocess_images(paths).to(args.device)      # 3 x 3 x H' x W'
            tic = time.time()
            with torch.no_grad():
                pred = model(images)
            extr, intr = pose_encoding_to_extri_intri(pred["pose_enc"], images.shape[-2:])
            net_s = time.time() - tic
            E = extr[0].double().cpu().numpy()          # 3 x 3 x 4, world-to-camera, camera 1 = identity
            Kp = intr[0].double().cpu().numpy()
            R1, c1 = E[0, :, :3], E[0, :, 3]
            R12 = E[1, :, :3] @ R1.T
            t12 = E[1, :, 3] - R12 @ c1
            R13 = E[2, :, :3] @ R1.T
            t13 = E[2, :, 3] - R13 @ c1
            s = np.linalg.norm(t12) or 1.0
            wp = images.shape[-1]
            f = float(np.mean([0.5 * (Kp[i, 0, 0] + Kp[i, 1, 1]) * widths[i] / wp for i in range(3)]))
            fh.create_dataset(key, data=np.r_[R12.ravel(), t12 / s, R13.ravel(), t13 / s, f])
            ft.write(f"{key} {net_s:.4f}\n")
            n_new += 1
            if n_new % 20 == 0:
                fh.flush()
                ft.flush()
                print(f"{out.name}: {n_new} new triplets, {(time.time() - t0) / n_new:.1f} s each", flush=True)
    print(f"done: {out} ({n_new} new)")


if __name__ == "__main__":
    main()
