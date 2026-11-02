"""Experiment options of draft v5 in threeview's eval_f.py (shared focal) and eval.py (calibrated). Run after
threeview_enm.py, threeview_seq.py and threeview_seed.py; edits in place, idempotent, fails loudly if an anchor is
missing.

Both scripts
  EVALF_ITERS   comma-separated iteration counts for -g (fixed min = max, so no early termination; the sequential
                pipelines run that count in both stages). Default: the released list 100,...,10000.
  fixed_iterations  stored in every result, so the -g curves can be split by iteration count.
eval.py
  '+ SEQ'       e.g. '5p3v + SEQ': the calibrated sequential pipeline (poselib_extra_rows.py).
  EVALF_SEED    RANSAC seed, as in eval_f.py.
eval_f.py, rows that run the three-view shared-focal LO from given cameras (poselib_extra_rows.py), timed with it:
  '5p3v + R + C + PRIOR(guess)'     5pt+P3P+R+F at f = 1.25 x the larger image side of view 1 (the COLMAP default)
  '5p3v + R + C + PRIOR(geocalib)'  the same at the focal length in $EVALF_FOCALS (h5: image name -> f in pixels,
                                    from scripts/geocalib_focals.py); an image without one runs at the
                                    guessed f and is flagged (prior_missing)
  '5p3v + R + C + PRIOR(fundamental)'  the same at a focal length per triplet in $EVALF_FFOCALS (h5: 'img1-img2-img3'
                                    -> f, from the fundamental matrix of views 1-2, scripts/fundamental_focals.py)
  '<label> + PROSAC'                tracks ordered by match quality and PoseLib's progressive sampling (PROSAC)
  EVALF_THRESHOLD                   RANSAC threshold in pixels (default 5, the released value)
  '0p3v(INIT)'                      cameras from $EVALF_INIT (h5: 'img1-img2-img3' -> R12 (9), t12 (3), R13 (9),
                                    t13 (3), f; from scripts/vggt_cameras.py); a missing triplet starts from identity
                                    poses at the guessed focal length and is flagged (init_missing)

  python scripts/patches/threeview_extra.py third_party/threeview
"""
import sys
from pathlib import Path

MARK = "EVALF_ITERS"

GRID_OLD = "        iterations_list = [100, 200, 500, 1000, 2000, 5000, 10000]\n"
GRID_NEW = ("        # draft v5 matched runtime: iteration counts from $EVALF_ITERS (default: the released list)\n"
            "        iterations_list = [int(x) for x in os.environ.get('EVALF_ITERS', '100,200,500,1000,2000,5000,10000')"
            ".split(',')]\n")
FIXED_OLD = "    result_dict['experiment'] = experiment\n"
FIXED_NEW = FIXED_OLD + "    result_dict['fixed_iterations'] = iterations  # -g curves (None at default settings)\n"

F_CALL = "    if '+ SEQ' in experiment:  # Task 2.9 sequential baseline (six-point on views 1-2, then P3P)\n"
F_BRANCH = ("    if 'PRIOR(' in experiment or '(INIT)' in experiment:  # draft v5: focal priors, network row\n"
            "        out, info = prior_or_init(experiment, x1, x2, x3, pp, img1, img2, img3, camera_dicts, ransac_dict,\n"
            "                                  bundle_dict)\n"
            "    el")
F_FUNC_ANCHOR = "def eval_experiment(x):\n"
F_FUNC = '''_prior_cache = {}


def _h5_table(env):
    """{key: array} from the h5 file named by $env (nested groups joined with '/'), loaded once per worker."""
    if env not in _prior_cache:
        d = {}
        path = os.environ.get(env)
        if path and os.path.exists(path):
            with h5py.File(path, 'r') as f:
                f.visititems(lambda k, v: d.__setitem__(k, np.array(v)) if isinstance(v, h5py.Dataset) else None)
        _prior_cache[env] = d
    return _prior_cache[env]


def prior_or_init(experiment, x1, x2, x3, pp, img1, img2, img3, camera_dicts, ransac_dict, bundle_dict):
    """Draft v5 Table 1 rows that start the three-view shared-focal LO from given cameras (threeview_extra.py)."""
    w, h = camera_dicts[img1]['width'], camera_dicts[img1]['height']
    f_guess = 1.25 * max(w, h)
    extra = {'iterations': 0}
    if '(INIT)' in experiment:
        init = _h5_table('EVALF_INIT').get(f'{img1}-{img2}-{img3}')
        if init is None:
            R12, t12, R13, t13, f0 = np.eye(3), np.array([1.0, 0, 0]), np.eye(3), np.array([1.0, 0, 0]), f_guess
            extra['init_missing'] = 1
        else:
            init = np.asarray(init, dtype=float).reshape(-1)
            R12, t12, R13, t13, f0 = init[:9].reshape(3, 3), init[9:12], init[12:21].reshape(3, 3), init[21:24], init[24]
    else:
        f0 = f_guess
        if 'PRIOR(geocalib)' in experiment:
            fp = _h5_table('EVALF_FOCALS').get(img1)
            if fp is None:
                extra['prior_missing'] = 1   # no prediction for this image: flagged, left out by the analysis
            else:
                f0 = float(np.asarray(fp).reshape(-1)[0])
        cam = {'model': 'SIMPLE_PINHOLE', 'width': w, 'height': h, 'params': [f0, pp[0], pp[1]]}
        poses, info0 = poselib.estimate_three_view_relative_pose(x1, x2, x3, cam, cam, cam, ransac_dict, bundle_dict)
        R12, t12, R13, t13 = poses.pose12.R, poses.pose12.t, poses.pose13.R, poses.pose13.t
        extra['iterations'] = info0['iterations']
    out, info = poselib.refine_three_view_shared_focal_from_init(x1, x2, x3, pp, f0, R12, t12, R13, t13, ransac_dict,
                                                                bundle_dict, 2)
    info.update(extra)
    info['prior_focal'] = float(f0)
    return out, info


'''

C_CALL = ("    three_view_pose, info = poselib.estimate_three_view_relative_pose(x1, x2, x3, camera_dicts[img1],\n"
          "                                                                      camera_dicts[img2], camera_dicts[img3],\n"
          "                                                                      ransac_dict, bundle_dict)\n")
C_NEW = ("    # '+ SEQ': the calibrated sequential pipeline (draft v5 Table 3, threeview_extra.py)\n"
         "    estimate = poselib.estimate_three_view_relative_pose_sequential if '+ SEQ' in experiment \\\n"
         "        else poselib.estimate_three_view_relative_pose\n"
         "    three_view_pose, info = estimate(x1, x2, x3, camera_dicts[img1], camera_dicts[img2], camera_dicts[img3],\n"
         "                                     ransac_dict, bundle_dict)\n")
C_SEED_OLD = "        ransac_dict['max_iterations'] = iterations\n"
C_SEED_NEW = C_SEED_OLD + "    ransac_dict['seed'] = int(os.environ.get('EVALF_SEED', '0'))  # repeated runs (draft v5)\n"


def replace(text, old, new, path):
    if text.count(old) != 1:
        sys.exit(f"ERROR: expected one {old.strip()[:60]!r} in {path}, found {text.count(old)}")
    return text.replace(old, new)


PRELOAD_MARK = "untimed: the side files"
PRELOAD_OLD = "    start = perf_counter()\n"
PRELOAD_NEW = ("    # untimed: the side files of the focal-prior and network rows load once per worker, outside the timer\n"
               "    if 'PRIOR(geocalib)' in experiment:\n"
               "        _h5_table('EVALF_FOCALS')\n"
               "    if '(INIT)' in experiment:\n"
               "        _h5_table('EVALF_INIT')\n") + PRELOAD_OLD


STAGE3_MARK = "EVALF_THRESHOLD"
STAGE3 = [   # third edit (2026-11-02, the large run), eval_f.py only
    # threshold ablation (3 and 10 px) and PROSAC rows; after the seed line of threeview_seed.py
    ("    ransac_dict['seed'] = int(os.environ.get('EVALF_SEED', '0'))  # repeated runs (kill test A)\n",
     "    ransac_dict['seed'] = int(os.environ.get('EVALF_SEED', '0'))  # repeated runs (kill test A)\n"
     "    ransac_dict['max_epipolar_error'] = float(os.environ.get('EVALF_THRESHOLD', '5.0'))  # threshold ablation\n"
     "    ransac_dict['progressive_sampling'] = '+ PROSAC' in experiment  # tracks come ordered by match quality\n"),
    # PROSAC rows get the tracks ordered by match quality (SIFT: the larger SNN ratio of 1-2 and 1-3, smallest first;
    # LightGlue: the smaller score of 1-2 and 1-3, largest first); every other row keeps the file order
    ("                for iterations in iterations_list:\n",
     "                q = pts[l, 6:8]\n"
     "                order = np.argsort(q.max(axis=1), kind='stable') if 'SIFT_triplet_correspondences' in "
     "matches_basename \\\n"
     "                    else np.argsort(-q.min(axis=1), kind='stable')\n"
     "                if len(order) != len(x1):   # force_inliers changed the tracks: keep their order\n"
     "                    order = np.arange(len(x1))\n"
     "                xq = (x1[order], x2[order], x3[order])\n"
     "                for iterations in iterations_list:\n"),
    ("                        yield experiment, iterations, img1, img2, img3, x1, x2, x3, R_dict_l, T_dict_l, camera_dicts_l\n",
     "                        xx = xq if '+ PROSAC' in experiment else (x1, x2, x3)\n"
     "                        yield (experiment, iterations, img1, img2, img3) + xx + (R_dict_l, T_dict_l, camera_dicts_l)\n"),
    # focal prior per triplet from the fundamental matrix of views 1-2 (scripts/fundamental_focals.py)
    ("        if 'PRIOR(geocalib)' in experiment:\n            fp = _h5_table('EVALF_FOCALS').get(img1)\n",
     "        if 'PRIOR(geocalib)' in experiment or 'PRIOR(fundamental)' in experiment:\n"
     "            fp = _h5_table('EVALF_FOCALS').get(img1) if 'PRIOR(geocalib)' in experiment \\\n"
     "                else _h5_table('EVALF_FFOCALS').get(f'{img1}-{img2}-{img3}')\n"),
    ("    if '(INIT)' in experiment:\n        _h5_table('EVALF_INIT')\n",
     "    if '(INIT)' in experiment:\n        _h5_table('EVALF_INIT')\n"
     "    if 'PRIOR(fundamental)' in experiment:\n        _h5_table('EVALF_FFOCALS')\n"),
]


def stage3(src):
    """Threshold override, PROSAC rows and the fundamental-matrix focal prior (applied after preload)."""
    text = src.read_text()
    if STAGE3_MARK in text:
        return
    for old, new in STAGE3:
        text = replace(text, old, new, src)
    src.write_text(text)
    print(f"threshold, PROSAC and fundamental-matrix prior added to {src}")


def preload(src):
    """Second edit (2026-11-02), applied also where the first one is in: keep the side-file load out of the timing."""
    text = src.read_text()
    if PRELOAD_MARK in text:
        return
    src.write_text(replace(text, PRELOAD_OLD, PRELOAD_NEW, src))
    print(f"side-file load moved out of the timing in {src}")


def main():
    root = Path(sys.argv[1])
    for name in ("eval_f.py", "eval.py"):
        src = root / name
        text = src.read_text()
        if MARK in text:
            print(f"draft v5 options already in {src}")
            if name == "eval_f.py":
                preload(src)
                stage3(src)
            continue
        if "\nimport os\n" not in text:
            sys.exit(f"ERROR: {src} does not import os")
        text = replace(text, GRID_OLD, GRID_NEW, src)
        text = replace(text, FIXED_OLD, FIXED_NEW, src)
        if name == "eval_f.py":
            text = replace(text, F_CALL, F_BRANCH + F_CALL.lstrip(), src)
            text = replace(text, F_FUNC_ANCHOR, F_FUNC + F_FUNC_ANCHOR, src)
        else:
            text = replace(text, C_CALL, C_NEW, src)
            text = replace(text, C_SEED_OLD, C_SEED_NEW, src)
        src.write_text(text)
        print(f"draft v5 options added to {src}")
        if name == "eval_f.py":
            preload(src)
            stage3(src)


if __name__ == "__main__":
    main()
