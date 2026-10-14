"""Minimal COLMAP model reader (binary and text), numpy only.

Returns cameras {camera_id: Camera} and images {name: Image}, where Image carries the
world-to-camera pose (R, t), the camera id and the ids of observed 3D points
(-1 entries removed). Supported camera models are the ones ETH3D, Aachen and
PhotoTourism ship: SIMPLE_PINHOLE, PINHOLE, SIMPLE_RADIAL, RADIAL, OPENCV.
"""
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CAMERA_MODELS = {0: ("SIMPLE_PINHOLE", 3), 1: ("PINHOLE", 4), 2: ("SIMPLE_RADIAL", 4),
                 3: ("RADIAL", 5), 4: ("OPENCV", 8)}
MODEL_IDS = {name: i for i, (name, _) in CAMERA_MODELS.items()}


@dataclass
class Camera:
    model: str
    width: int
    height: int
    params: np.ndarray

    @property
    def K(self):
        p = self.params
        if self.model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
            fx = fy = p[0]; cx, cy = p[1], p[2]
        else:  # PINHOLE, OPENCV
            fx, fy, cx, cy = p[:4]
        return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


@dataclass
class Image:
    name: str
    R: np.ndarray        # 3x3 world-to-camera rotation
    t: np.ndarray        # (3,) world-to-camera translation
    camera_id: int
    point3D_ids: np.ndarray  # sorted unique ids of triangulated observations


def qvec_to_rotmat(q):
    w, x, y, z = np.asarray(q, dtype=float) / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def _valid_ids(ids):
    ids = np.asarray(ids, dtype=np.int64)
    return np.unique(ids[ids >= 0])


def read_cameras_bin(path):
    cams = {}
    with open(path, "rb") as f:
        for _ in range(struct.unpack("<Q", f.read(8))[0]):
            cam_id, model_id, w, h = struct.unpack("<iiQQ", f.read(24))
            name, n = CAMERA_MODELS[model_id]
            cams[cam_id] = Camera(name, w, h, np.array(struct.unpack(f"<{n}d", f.read(8 * n))))
    return cams


def read_images_bin(path, with_points=True):
    images = {}
    pt_dtype = np.dtype([("x", "<f8"), ("y", "<f8"), ("id", "<i8")])
    with open(path, "rb") as f:
        for _ in range(struct.unpack("<Q", f.read(8))[0]):
            _, qw, qx, qy, qz, tx, ty, tz, cam_id = struct.unpack("<i7di", f.read(64))
            name = bytearray()
            while (c := f.read(1)) != b"\0":
                name += c
            n_pts = struct.unpack("<Q", f.read(8))[0]
            if with_points:
                ids = _valid_ids(np.frombuffer(f.read(24 * n_pts), dtype=pt_dtype)["id"])
            else:
                f.seek(24 * n_pts, 1)
                ids = np.empty(0, dtype=np.int64)
            images[name.decode()] = Image(name.decode(), qvec_to_rotmat([qw, qx, qy, qz]),
                                          np.array([tx, ty, tz]), cam_id, ids)
    return images


def read_cameras_txt(path):
    cams = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        tok = line.split()
        cams[int(tok[0])] = Camera(tok[1], int(tok[2]), int(tok[3]), np.array(tok[4:], dtype=float))
    return cams


def read_images_txt(path, with_points=True):
    images = {}
    lines = [l for l in Path(path).read_text().splitlines() if not l.startswith("#")]
    for header, points in zip(lines[0::2], lines[1::2]):
        tok = header.split()
        if len(tok) < 10:
            continue
        q, t, cam_id, name = tok[1:5], tok[5:8], int(tok[8]), " ".join(tok[9:])
        ids = _valid_ids(np.array(points.split()[2::3], dtype=np.int64)) if with_points and points.strip() \
            else np.empty(0, dtype=np.int64)
        images[name] = Image(name, qvec_to_rotmat(np.array(q, dtype=float)), np.array(t, dtype=float), cam_id, ids)
    return images


def read_model(model_dir, with_points=True):
    """Read cameras + images from a COLMAP model folder (binary preferred, else text)."""
    d = Path(model_dir)
    if (d / "images.bin").exists():
        return read_cameras_bin(d / "cameras.bin"), read_images_bin(d / "images.bin", with_points)
    if (d / "images.txt").exists():
        return read_cameras_txt(d / "cameras.txt"), read_images_txt(d / "images.txt", with_points)
    raise FileNotFoundError(f"no COLMAP model (images.bin / images.txt) in {d}")


def read_points3D(model_dir):
    """{point3D_id: xyz} from points3D.bin or points3D.txt."""
    d = Path(model_dir)
    pts = {}
    if (d / "points3D.bin").exists():
        with open(d / "points3D.bin", "rb") as f:
            for _ in range(struct.unpack("<Q", f.read(8))[0]):
                pid, x, y, z = struct.unpack("<Q3d", f.read(32))
                f.seek(3 + 8, 1)  # rgb (3 x uint8) + reprojection error (double)
                track_len = struct.unpack("<Q", f.read(8))[0]
                f.seek(8 * track_len, 1)  # (image_id, point2D_idx) pairs, int32 each
                pts[pid] = np.array([x, y, z])
        return pts
    for line in (d / "points3D.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        tok = line.split()
        pts[int(tok[0])] = np.array(tok[1:4], dtype=float)
    return pts
