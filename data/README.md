# Tier 1 datasets

Downloaded and extracted 2026-10-14 with `scripts/download_tier1.sh` and `scripts/extract_tier1.sh`.
Original archives are kept in `raw/` (about 21 GB). Every archive's size matched the server's Content-Length.
All three datasets are for non-commercial research use only. Cite the papers each dataset's README names.

| Folder | Source | Contents (verified counts) |
|---|---|---|
| `ransac_tutorial/` | CVPR 2020 RANSAC tutorial (cmp.felk.cvut.cz/~mishkdmy) | `RANSAC-Tutorial-Data-Test/`: 11 PhotoTourism test scenes, each with `images/`, `matches.h5` and `match_conf.h5`. `RANSAC-Tutorial-Data-ValOnly/val/`: `sacre_coeur`, `st_peters_square`, plus `parse_EF_data.ipynb` |
| `eth3d/` | ETH3D high-res multi-view training | 13 scenes, each with `images/dslr_images_undistorted`, `dslr_calibration_undistorted` (COLMAP, **SfM poses from images only, not laser ground truth**) and `dslr_scan_eval` (laser-scan ground truth) |
| `imc2020_gt/` | IMC 2020 PhotoTourism archives, streamed by `scripts/download_imc2020_test_gt.sh` | Only `<scene>/dense/sparse/{cameras,images}.bin` kept for 9 scenes (reichstag + 8 test scenes); `.done_<scene>` marks a complete download |
| `tzamos_triplets/threeview/` | Tzamos et al. CVPR 2025 extracted triplets, Zenodo 16603086 (CC-BY-4.0, md5 checked) | 13 PhotoTourism scenes + Aachen v1.1; per scene `K.h5`, `R.h5`, `T.h5` and `triplets-features_superpoint_noresize_2048-LG.{h5,txt}` (SuperPoint + LightGlue, 2048 kp) |
| `aachen_v1_1/` | Aachen Day-Night v1.1 (data.ciirc.cvut.cz) | `images_upright/db`: 4,479 images; `sequences`: 2,371; `query/day`: 834 and `query/night`: 206 on disk. `3D-models/aachen_v_1_1/`: COLMAP bin + nvm + `database_intrinsics_v1_1.txt` |

## Gotchas
- **RANSAC tutorial test pack ships no ground truth.** `scripts/build_test_gt.py` adds `K1_K2.h5`, `R.h5`,
  `T.h5` to 9 of the 11 test scenes from `imc2020_gt/` (IMC 2020 COLMAP models, public since 2022).
  `london_bridge` and `united_states_capitol` have no public GT and stay unscored.
  Check (`scripts/check_gt.py`): median fraction of confident matches within 2 px of the GT epipolar
  geometry is 0.85-0.95 on most scenes vs 0.74-0.83 with the shipped validation GT; piazza_san_marco is 0.48.
- **Aachen query lists.** Use `aachen_v1_1/day_time_queries_with_intrinsics.txt` (824 day) and
  `aachen_v1_1/queries/night_time_queries_with_intrinsics.txt` (191 night, v1.1).
  The 98-line `aachen_v1_1/night_time_queries_with_intrinsics.txt` at the top level is the **old v1.0 list**.
  All 1,015 listed queries exist on disk. The extra query images on disk are not part of the benchmark.
- **Aachen query poses are withheld.** Evaluation goes through visuallocalization.net. For pose
  ground truth, use database images with the COLMAP model.
- `aachen_v1_1/__MACOSX/` is macOS zip junk (7 MB) and can be ignored or deleted.
