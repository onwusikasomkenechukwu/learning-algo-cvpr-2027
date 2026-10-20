"""Convert a Cambridge Landmarks scene's reconstruction.nvm into a COLMAP text model for threeview's
datasets/prepare_im.py, which expects <dataset>/<Scene>/model_train (the layout of hloc's retriangulated
Cambridge models, which we do not have). Only the training split (dataset_train.txt) is kept, as the name
model_train says.

Choices (write them into the settings sheet):
  - one SIMPLE_RADIAL camera per image: f from the NVM, principal point at the image center, k = -r, the
    first-order inverse of the NVM undistortion m_u = m (1 + r |m|^2 / f^2); prepare_im and eval only read f
    and the principal point (cam_to_K), so k is informational
  - 2D points are the NVM measurements as observed (distorted), shifted to COLMAP pixel coordinates
  - image names use the .png files on disk (the NVM lists .jpg)

Usage:
  python -I scripts/cambridge_nvm_to_colmap.py data/cambridge/KingsCollege D:/learning-algo-cvpr/data/cambridge_colmap
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene_dir")
    ap.add_argument("out_root")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()
    scene = Path(args.scene_dir)
    out = Path(args.out_root) / scene.name / "model_train"
    out.mkdir(parents=True, exist_ok=True)
    cx, cy = args.width / 2, args.height / 2

    train = {l.split()[0] for l in (scene / "dataset_train.txt").read_text().splitlines()[3:] if l.strip()}
    lines = (scene / "reconstruction.nvm").read_text().split("\n")
    i = 0
    while not lines[i].strip() or lines[i].startswith("NVM"):
        i += 1
    cams = []
    for line in lines[i + 1:i + 1 + int(lines[i])]:
        tok = line.split()
        name = str(Path(tok[0]).with_suffix(".png")).replace("\\", "/")
        cams.append(dict(name=name, f=float(tok[1]), q=np.array(tok[2:6], dtype=float),
                         C=np.array(tok[6:9], dtype=float), r=float(tok[9])))
    keep = {k: n for n, k in enumerate(k for k, c in enumerate(cams) if c["name"] in train)}  # nvm idx -> 0..
    missing = train - {c["name"] for c in cams}
    if missing:
        print(f"warning: {len(missing)} training images are not in the NVM", file=sys.stderr)

    j = i + 1 + len(cams)
    while not lines[j].strip():
        j += 1
    xys = {k: [] for k in keep}
    points = []
    for line in lines[j + 1:j + 1 + int(lines[j])]:
        tok = line.split()
        n = int(tok[6])
        m = np.array(tok[7:7 + 4 * n], dtype=float).reshape(n, 4)
        track = []
        pid = len(points) + 1
        for ci, _, mx, my in m:
            ci = int(ci)
            if ci in keep:
                track.append((keep[ci] + 1, len(xys[ci])))
                xys[ci].append((float(mx + cx), float(my + cy), pid))
        if track:  # points seen only by test images are dropped
            points.append((pid, tok[:3], tok[3:6], track))

    with open(out / "cameras.txt", "w") as fc, open(out / "images.txt", "w") as fi:
        fc.write("# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        fi.write("# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n# POINTS2D[] as (X, Y, POINT3D_ID)\n")
        for k, n in sorted(keep.items(), key=lambda kv: kv[1]):
            c = cams[k]
            q = c["q"] / np.linalg.norm(c["q"])
            R = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()
            t = -R @ c["C"]
            fc.write(f"{n + 1} SIMPLE_RADIAL {args.width} {args.height} {c['f']!r} {cx} {cy} {-c['r']!r}\n")
            fi.write(f"{n + 1} {' '.join(repr(float(v)) for v in q)} {' '.join(repr(float(v)) for v in t)} "
                     f"{n + 1} {c['name']}\n")
            fi.write(" ".join(f"{x!r} {y!r} {p}" for x, y, p in xys[k]) + "\n")
    with open(out / "points3D.txt", "w") as fp:
        fp.write("# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        for pid, xyz, rgb, track in points:
            fp.write(f"{pid} {' '.join(xyz)} {' '.join(rgb)} 0 " + " ".join(f"{a} {b}" for a, b in track) + "\n")
    print(f"{scene.name}: {len(keep)} training images, {len(points)} points -> {out}")


if __name__ == "__main__":
    main()
