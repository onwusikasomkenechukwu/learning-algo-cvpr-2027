"""Tables 1 and 3 of draft v5 from the result files of run_abl_dell.sh, as LaTeX rows and markdown.

Table 1 (shared focal), per row of mr_config.DEFAULT:
  Cambridge AUC@10, xi_f   eval_f.py at default settings, SP+LG, RANSAC seeds 0-2 (tags t1-s<seed>); AUC@10 is the
                           scene-equal mean per seed, averaged over seeds; xi_f the median over pooled triplets,
                           averaged over seeds
  Time (ms)                mean single-core time at default settings on the Cambridge scenes of splg_time (timing
                           step); the network row adds its network time apart (vggt_cameras.py times files)
  ETH3D AUC@10             as Cambridge, over the ETH3D scenes other than the tuning scene
  matched runtime          from matched_runtime.py summary.json: guarded SIFT w < W_MAX, semi-synthetic whole-track,
                           view-3 and measured mixture at w = 0.25
Table 3 (calibrated): PhotoTourism AUC@10 from eval.py at default settings on the released triplets (tag t3, all
triplets pooled as in compare_tzamos_table.py), matched-runtime columns from summary.json.
Missing values print as \\tbd, so the output can be pasted over the draft's rows.

  python scripts/paper_tables.py --results third_party/threeview/results --sets results/sets \
      --matched results/matched/summary.json --vggt results/vggt --out results/paper
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mr_config as C  # noqa: E402
from compare_tzamos_table import DATASETS, FEAT as PT_FEAT  # noqa: E402
from outlier_stats import SP, TUNING  # noqa: E402

CAMBRIDGE = ["GreatCourt", "KingsCollege", "OldHospital", "ShopFacade", "StMarysChurch"]
ETH3D = ["delivery_area", "electro", "kicker", "meadow", "office", "pipes", "playground", "relief", "relief_2",
         "terrace", "terrains"]


def load(path):
    """Results without crashed tasks and without rows whose focal prior or cameras were missing (threeview_extra.py)."""
    if not path.exists():
        return []
    return [r for r in json.loads(path.read_text()) if not r.get("crashed")
            and not r.get("info", {}).get("prior_missing") and not r.get("info", {}).get("init_missing")]


def err(r):
    e = r.get("Charalambos_P_err")
    if e is None:
        e = max(0.5 * (r["R_12_err"] + r["R_13_err"]), 0.5 * (r["t_12_err"] + r["t_13_err"]))
    return 180.0 if e is None or not np.isfinite(e) else e


def auc10(errs):
    e = np.asarray(errs, float)
    return 100 * float(np.mean([np.mean(e < t) for t in range(1, 11)])) if len(e) else None


def scene_equal(results, scenes, label, seeds, tag_fmt, feat):
    """(AUC@10 averaged over seeds of the scene-equal mean, median xi_f averaged over seeds, scenes found)."""
    aucs, xis, found = [], [], set()
    for sd in seeds:
        per, fe = [], []
        for s in scenes:
            rows = [r for r in load(results / f"focal_{s}-{tag_fmt.format(seed=sd)}-{feat}.json")
                    if r["experiment"] == label]
            if rows:
                found.add(s)
                per.append(auc10([err(r) for r in rows]))
                fe += [r["f_err"] for r in rows if r.get("f_err") is not None and np.isfinite(r["f_err"])]
        if per:
            aucs.append(np.mean(per))
            xis.append(np.median(fe) if fe else np.nan)
    return (float(np.mean(aucs)) if aucs else None, float(np.nanmean(xis)) if xis else None, len(found))


def tex(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "\\tbd"
    return f"{100 * v:.1f}\\%" if pct else f"{v:.{d}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--sets", type=Path, required=True)
    ap.add_argument("--matched", type=Path)
    ap.add_argument("--vggt", type=Path, help="folder with vggt_cameras.py <scene>.h5.times.txt files")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    R = args.results
    mt = json.loads(args.matched.read_text()) if args.matched and args.matched.exists() else {}
    man = json.loads((args.sets / "manifest.json").read_text()) if (args.sets / "manifest.json").exists() else {}
    time_scenes = [s for s in man.get("sets", {}).get("splg_time", {}).get("scenes", {}) if s in CAMBRIDGE]
    time_feat = man.get("sets", {}).get("splg_time", {}).get("feature", SP)

    def single_core_ms(label):
        ms = [r["info"]["runtime"] for s in time_scenes for r in load(R / f"focal_{s}-tm-splg_time-{time_feat}.json")
              if r["experiment"] == label and r.get("fixed_iterations") is None]
        return float(np.mean(ms)) if ms else None

    net_ms = None
    if args.vggt and args.vggt.exists():
        t = [float(l.split()[-1]) for f in args.vggt.glob("*.times.txt") for l in f.read_text().splitlines() if l.strip()]
        net_ms = 1000 * float(np.mean(t)) if t else None

    rows1, md = [], ["# Table 1 (shared focal length)", "",
                     "| Method | Cambridge AUC@10 | xi_f | ms | ETH3D AUC@10 | SIFT w<0.4 | whole | view-3 | mixture |",
                     "|---|---|---|---|---|---|---|---|---|"]
    ss = mt.get("semisynth", {})
    for key, label, name in C.DEFAULT:
        cam_auc, cam_xi, n_cam = scene_equal(R, CAMBRIDGE, label, args.seeds, "t1-s{seed}", SP)
        eth_auc, _, n_eth = scene_equal(R, [s for s in ETH3D if s != TUNING], label, args.seeds, "t1-s{seed}", SP)
        ms = single_core_ms(label)
        matched = [mt.get("auc", {}).get("sift_low", {}).get(key)] + \
                  [ss.get(k, {}).get("levels", {}).get("0.25", {}).get("auc", {}).get(key) for k in ("whole", "view3", "mixture")]
        if key == "vggt":
            matched = ["n/a"] * 4
            ms_txt = tex(ms) + (f" + {net_ms:.0f} net" if net_ms else "")
        else:
            ms_txt = tex(ms)
        cells = [tex(cam_auc), tex(cam_xi, pct=True), ms_txt, tex(eth_auc)] + [m if m == "n/a" else tex(m) for m in matched]
        rows1.append(f"{name} & " + " & ".join(cells) + " \\\\")
        md.append(f"| {name} | " + " | ".join(c.replace("\\tbd", "-").replace("\\%", "%") for c in cells) +
                  f" |{'' if n_cam == 5 else f' (Cambridge scenes found: {n_cam})'}")

    rows3, md3 = [], ["", "# Table 3 (calibrated)", "", "| Method | PhotoTourism AUC@10 | SIFT w<0.4 | whole |",
                      "|---|---|---|---|"]
    cal = mt.get("calibrated", {})
    for key, label, name in C.CALIB:
        errs = [err(r) for sc in DATASETS["PhotoTourism"]
                for r in load(R / f"{sc}{C.CALIB_MID}-t3-{PT_FEAT}.json") if r["experiment"] == label]
        cells = [tex(auc10(errs) if errs else None), tex(cal.get("sift_low", {}).get("auc", {}).get(key)),
                 tex(cal.get("whole_0.25", {}).get("auc", {}).get(key))]
        rows3.append(f"{name} & " + " & ".join(cells) + " \\\\")
        md3.append(f"| {name} | " + " | ".join(c.replace("\\tbd", "-") for c in cells) + " |")
    (args.out / "table1_rows.tex").write_text("\n".join(rows1) + "\n")
    (args.out / "table3_rows.tex").write_text("\n".join(rows3) + "\n")
    (args.out / "tables.md").write_text("\n".join(md + md3) + "\n")
    print("\n".join(md + md3))


if __name__ == "__main__":
    main()
