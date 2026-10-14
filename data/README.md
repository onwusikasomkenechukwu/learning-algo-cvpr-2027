# Tier 1 datasets

Downloaded and extracted 2026-10-14 with `scripts/download_tier1.sh` and `scripts/extract_tier1.sh`.
Original archives are kept in `raw/` (about 21 GB). Every archive's size matched the server's Content-Length.
All three datasets are for non-commercial research use only. Cite the papers each dataset's README names.

| Folder | Source | Contents (verified counts) |
|---|---|---|
| `ransac_tutorial/` | CVPR 2020 RANSAC tutorial (cmp.felk.cvut.cz/~mishkdmy) | `RANSAC-Tutorial-Data-Test/`: 11 PhotoTourism test scenes, each with `images/`, `matches.h5` and `match_conf.h5`. `RANSAC-Tutorial-Data-ValOnly/val/`: `sacre_coeur`, `st_peters_square`, plus `parse_EF_data.ipynb` |
| `eth3d/` | ETH3D high-res multi-view training | 13 scenes, each with `images/dslr_images_undistorted`, `dslr_calibration_undistorted` (COLMAP, **SfM poses from images only, not laser ground truth**) and `dslr_scan_eval` (laser-scan ground truth) |
| `aachen_v1_1/` | Aachen Day-Night v1.1 (data.ciirc.cvut.cz) | `images_upright/db`: 4,479 images; `sequences`: 2,371; `query/day`: 834 and `query/night`: 206 on disk. `3D-models/aachen_v_1_1/`: COLMAP bin + nvm + `database_intrinsics_v1_1.txt` |

## Gotchas
- **RANSAC tutorial test pack has no ground truth.** `RANSAC-Tutorial-Data-Test/<scene>/` holds only
  `matches.h5` + `match_conf.h5` (no `K1_K2.h5`, `R.h5`, `T.h5`; the 2020 challenge kept test GT private).
  Scoring it needs the IMC 2020 test calibration (public since 2022, cs.ubc.ca/~kmyi/imw2020/data.html), not downloaded yet.
- **Aachen query lists.** Use `aachen_v1_1/day_time_queries_with_intrinsics.txt` (824 day) and
  `aachen_v1_1/queries/night_time_queries_with_intrinsics.txt` (191 night, v1.1).
  The 98-line `aachen_v1_1/night_time_queries_with_intrinsics.txt` at the top level is the **old v1.0 list**.
  All 1,015 listed queries exist on disk. The extra query images on disk are not part of the benchmark.
- **Aachen query poses are withheld.** Evaluation goes through visuallocalization.net. For pose
  ground truth, use database images with the COLMAP model.
- `aachen_v1_1/__MACOSX/` is macOS zip junk (7 MB) and can be ignored or deleted.
