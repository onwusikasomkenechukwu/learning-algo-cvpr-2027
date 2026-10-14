"""Build RANSAC-tutorial-style ground truth (K1_K2.h5, R.h5, T.h5) for the test pack
from the IMC 2020 COLMAP models fetched by download_imc2020_test_gt.sh.

Same conventions as the validation split: R, T are world-to-camera (COLMAP qvec/tvec),
T has shape (3, 1), K1_K2[pair] has shape (1, 2, 3, 3). Intrinsics are rescaled if the
tutorial image size differs from the COLMAP camera size. Files are written next to
matches.h5 in each test scene folder; scenes whose download is not complete are skipped.

Usage: python scripts/build_test_gt.py [test_dir] [gt_dir]
"""
import sys
from pathlib import Path

import cv2
import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from colmap_io import read_model  # noqa: E402


def build_scene(scene_dir, sparse_dir):
    cams, images = read_model(sparse_dir, with_points=False)
    models = {cams[im.camera_id].model for im in images.values()}
    K, R, T = {}, {}, {}
    rescaled = 0
    for img_path in sorted((scene_dir / "images").glob("*.jpg")):
        im = images[img_path.name]
        cam = cams[im.camera_id]
        k = cam.K
        h, w = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE).shape[:2]
        if (w, h) != (cam.width, cam.height):
            k = np.diag([w / cam.width, h / cam.height, 1.0]) @ k
            rescaled += 1
        K[img_path.stem], R[img_path.stem], T[img_path.stem] = k, im.R, im.t.reshape(3, 1)
    with h5py.File(scene_dir / "matches.h5", "r") as f:
        pairs = list(f.keys())
    for name, data in (("R.h5", R), ("T.h5", T)):
        with h5py.File(scene_dir / name, "w") as f:
            for k, v in data.items():
                f[k] = v
    with h5py.File(scene_dir / "K1_K2.h5", "w") as f:
        for p in pairs:
            a, b = p.split("-")
            f[p] = np.stack([K[a], K[b]])[None]
    return len(K), len(pairs), models, rescaled


def main():
    test_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data/ransac_tutorial/RANSAC-Tutorial-Data-Test")
    gt_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "data/imc2020_gt")
    for scene_dir in sorted(p for p in test_dir.iterdir() if (p / "matches.h5").exists()):
        if not (gt_dir / f".done_{scene_dir.name}").exists():  # marker written once a download is complete
            print(f"{scene_dir.name:28s} SKIP (no completed ground-truth download)")
            continue
        n_img, n_pairs, models, rescaled = build_scene(scene_dir, gt_dir / scene_dir.name / "dense" / "sparse")
        print(f"{scene_dir.name:28s} {n_img} images, {n_pairs} pairs, camera models {sorted(models)}, "
              f"{rescaled} intrinsics rescaled")


if __name__ == "__main__":
    main()
