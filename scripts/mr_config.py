"""Methods, iteration grids and evaluation sets of draft v5, shared by run_abl_dell.sh and the analysis scripts.

  python scripts/mr_config.py labels focal        # 'key<TAB>eval_f.py label' per line (also: calib, default)
  python scripts/mr_config.py exps focal          # the labels joined with ';' for --exps
  python scripts/mr_config.py grid curves         # iteration counts for -g (also: timing)
"""
import sys

# Table 1, matched-runtime columns (eval_f.py). 'ours' is the method of the primary test, 'baselines' the two
# six-point pipelines it must beat.
FOCAL = [
    ("6p", "6p3v", "6pt+P3P"),
    ("seq", "6p3v + SEQ", "Sequential, six points then P3P"),
    ("guess", "5p3v + R + C + PRIOR(guess)", "5pt+P3P+R+F at guessed f"),
    ("geocalib", "5p3v + R + C + PRIOR(geocalib)", "5pt+P3P+R+F at GeoCalib f"),
    ("M", "4p3v(M)", "4p3vf(M)"),
    ("MR", "4p3v(M) + R", "4p3vf(M)+R"),
    ("Mrefit", "4p3v(M) + ENM", "4p3vf(M) with refit"),
    ("MDrefit", "4p3v(M-D) + ENM", "4p3vf(M±δ) with refit"),
    ("O", "4p3v(O)", "4p3vf(O), oracle"),
]
# Table 1, default-settings columns: the rows above plus the network row (cameras from scripts/vggt_cameras.py)
DEFAULT = FOCAL + [("vggt", "0p3v(INIT)", "VGGT, then three-view LO")]
# Table 3 (eval.py, calibrated)
CALIB = [
    ("5p", "5p3v", "5pt+P3P"),
    ("seq5", "5p3v + SEQ", "Sequential, 5pt then P3P"),
    ("Menm", "4p3v(M) + ENM", "4p3v(M)+ENM"),
    ("Aenm", "4p3v(A) + R + C + ENM", "4p3v(A)+R+F+ENM"),
    ("MDenm", "4p3v(M-D) + R + C + ENM", "4p3v(M±δ)+R+F+ENM"),
    ("hc", "4p(HC)", "4p3v(HC)"),
]
OURS, BASELINES = "Mrefit", ("6p", "seq")
CALIB_REF = "5p"          # budget of the calibrated matched runtime
CALIB_T = 5.0             # eval.py -t: the released calibrated table script uses 5 px (100-1000 iterations)
CALIB_MID = f"-{CALIB_T}t"  # eval.py puts the threshold into its results file name
FOCAL_REF = "6p"          # budget of the shared-focal matched runtime

GRIDS = {
    "curves": [10, 30, 100, 300, 1000, 3000, 10000, 30000],
    "timing": [10, 30, 100, 300, 1000, 3000],   # above 3000: linear fit in the iteration count (matched_runtime.py)
}

# Evaluation sets (scripts/eval_sets.py writes them under results/sets/<name>/<scene>/)
SETS = {
    "sift": "guarded SIFT triplets, every inlier ratio (bins; the primary set is w < W_MAX of it)",
    "sift_low": "guarded SIFT triplets with w < W_MAX (calibrated runs)",
    "splg": "SP+LG triplets, at most SPLG_N per scene (bins, Fig. 2e)",
    "sift_time": "TIME_N guarded SIFT triplets with w < W_MAX, stratified by scene (single-core timing)",
    "splg_time": "TIME_N SP+LG triplets, stratified by scene (single-core timing)",
}
W_MAX = 0.4


def table(name):
    return {"focal": FOCAL, "default": DEFAULT, "calib": CALIB}[name]


def main():
    what, arg = sys.argv[1], sys.argv[2]
    if what == "labels":
        print("\n".join(f"{k}\t{label}" for k, label, _ in table(arg)))
    elif what == "exps":
        print(";".join(label for _, label, _ in table(arg)))
    elif what == "grid":
        print(",".join(map(str, GRIDS[arg])))
    else:
        sys.exit(f"unknown: {what}")


if __name__ == "__main__":
    main()
