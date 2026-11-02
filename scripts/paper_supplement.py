"""Supplement tables of draft v5 from the result files of run_abl_dell.sh (sections appear when their files exist).

  per scene        Table 1 rows at default settings (tags t1-s<seed>), every Cambridge and ETH3D scene: AUC@5/10/20,
                   AUC@10 of the pair (2,3), median xi_f and focal mAA (mean over 1..10 % of the share with xi_f below)
  timing           single-core time per triplet at default settings (timing step): mean, median, 90th, 99th percentile
  threshold        3 / 5 / 10 px (tags th3, t1-s0, th10), Cambridge, scene-equal AUC@10
  refit ablations  squared loss, reselected inliers, refit only new best roots (tags ra-<switch>-s<seed>) against the
                   default refit, Cambridge, RANSAC seeds 0-2
  view 3           views 2 and 3 swapped (sets <set>_v3, tag v3) against the original order (tag vo), paired per triplet
  focal from F     the fundamental-matrix focal prior at default settings (tag sup-s0) and its fallbacks
  Test B           where samples go (no seed, ambiguous, no real root, usable), exclusions against the planarity
                   index and the reference cameras' reprojection error, absolute strict and practical rates, success
                   against the free point's path length
  full solve       the correct-root tool against a full solve (fullsolve/*_summary.json)
Writes <out>/supplement.md and <out>/supplement.json.

  python scripts/paper_supplement.py --results third_party/threeview/results --sets results/sets \
      --killb results/killB --fullsolve results/abl_dell/fullsolve --out results/paper
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mr_config as C  # noqa: E402
from outlier_stats import SIFT, SP  # noqa: E402
from paper_tables import CAMBRIDGE, ETH3D, load  # noqa: E402


def err(r, key="Charalambos_P_err"):
    e = r.get(key)
    return 180.0 if e is None or not np.isfinite(e) else float(e)


def auc(errs, k):
    e = np.asarray(errs, float)
    return 100 * float(np.mean([np.mean(e < t) for t in range(1, k + 1)])) if len(e) else None


def focal_maa(fe):
    f = np.asarray([x for x in fe if x is not None and np.isfinite(x)], float)
    return 100 * float(np.mean([np.mean(f < t / 100) for t in range(1, 11)])) if len(f) else None


def fmt(v, d=2):
    return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{d}f}"


def rows_of(R, scene, tag, feat, label):
    return [r for r in load(R / f"focal_{scene}-{tag}-{feat}.json") if r["experiment"] == label]


def scene_mean(R, scenes, tag, feat, label, key="Charalambos_P_err"):
    v = [auc([err(r, key) for r in rows], 10) for s in scenes for rows in [rows_of(R, s, tag, feat, label)] if rows]
    return float(np.mean(v)) if v else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--sets", type=Path)
    ap.add_argument("--killb", type=Path)
    ap.add_argument("--fullsolve", type=Path)
    ap.add_argument("--table2", type=Path, help="compare_tzamos_table.py output (fixed fork) to include")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    R = args.results
    S, md = {}, ["# Supplement tables (draft v5)", ""]
    names = {k: n for k, _, n in C.DEFAULT + C.EXTRA}

    # ---- per scene, default settings
    per = {}
    for key, label, name in C.DEFAULT:
        for s in CAMBRIDGE + ETH3D:
            a5, a10, a20, p23, xi, maa = [], [], [], [], [], []
            for sd in (0, 1, 2):
                rows = rows_of(R, s, f"t1-s{sd}", SP, label)
                if not rows:
                    continue
                e = [err(r) for r in rows]
                a5.append(auc(e, 5)); a10.append(auc(e, 10)); a20.append(auc(e, 20))
                p23.append(auc([err(r, "P_23_err") for r in rows], 10))
                fe = [r.get("f_err") for r in rows]
                fv = [x for x in fe if x is not None and np.isfinite(x)]
                if fv:
                    xi.append(float(np.median(fv)))
                maa.append(focal_maa(fe))
            if a10:
                per.setdefault(key, {})[s] = dict(auc5=np.mean(a5), auc10=np.mean(a10), auc20=np.mean(a20),
                                                  pair23_auc10=np.mean(p23), xi_median=np.mean(xi) if xi else np.nan,
                                                  focal_maa=np.mean([m for m in maa if m is not None] or [np.nan]),
                                                  seeds=len(a10))
    if per:
        S["per_scene"] = per
        md += ["## Table 1 per scene (default settings, mean over RANSAC seeds)", "",
               "| Method | Scene | AUC@5 | AUC@10 | AUC@20 | pair (2,3) AUC@10 | median xi_f | focal mAA |",
               "|---|---|---|---|---|---|---|---|"]
        for key, d in per.items():
            for s, v in d.items():
                md.append(f"| {names[key]} | {s} | {fmt(v['auc5'])} | {fmt(v['auc10'])} | {fmt(v['auc20'])} | "
                          f"{fmt(v['pair23_auc10'])} | {fmt(100 * v['xi_median'], 1)}% | {fmt(v['focal_maa'])} |")
        md.append("")

    # ---- timing percentiles (default settings, one pinned core)
    if args.sets and (args.sets / "manifest.json").exists():
        man = json.loads((args.sets / "manifest.json").read_text())
        tim = {}
        for set_name in ("splg_time", "sift_time"):
            st = man["sets"].get(set_name)
            if not st:
                continue
            for key, label, _ in C.DEFAULT + C.EXTRA:
                ms = [r["info"]["runtime"] for s in st["scenes"]
                      for r in load(R / f"focal_{s}-tm-{set_name}-{st['feature']}.json")
                      if r["experiment"] == label and r.get("fixed_iterations") is None]
                if ms:
                    tim.setdefault(set_name, {})[key] = dict(
                        n=len(ms), mean=float(np.mean(ms)), median=float(np.median(ms)),
                        p90=float(np.percentile(ms, 90)), p99=float(np.percentile(ms, 99)))
        if tim:
            S["timing"] = tim
            md += ["## Single-core time per triplet at default settings (ms)", "",
                   "| Set | Method | n | mean | median | 90th | 99th |", "|---|---|---|---|---|---|---|"]
            for st, d in tim.items():
                for key, v in d.items():
                    md.append(f"| {st} | {names[key]} | {v['n']} | {fmt(v['mean'])} | {fmt(v['median'])} | "
                              f"{fmt(v['p90'])} | {fmt(v['p99'])} |")
            md.append("")

    # ---- threshold ablation
    th = {}
    for key, label in C.ABLATION:
        row = {"5.0": scene_mean(R, CAMBRIDGE, "t1-s0", SP, label)}
        for t in C.THRESHOLDS:
            row[str(t)] = scene_mean(R, CAMBRIDGE, f"th{int(t)}", SP, label)
        if any(v is not None for v in row.values()):
            th[key] = row
    if th:
        S["threshold"] = th
        md += ["## RANSAC threshold (Cambridge SP+LG, AUC@10, seed 0)", "",
               "| Method | " + " | ".join(f"{t} px" for t in sorted(th[next(iter(th))], key=float)) + " |",
               "|---" * (1 + len(th[next(iter(th))])) + "|"]
        for key, row in th.items():
            md.append(f"| {names.get(key, '4p3vf(M±δ)+R with refit')} | " +
                      " | ".join(fmt(row[t]) for t in sorted(row, key=float)) + " |")
        md.append("")

    # ---- refit ablations (baseline: Table 1 runs for the plain refit, kill test A runs for M+-d + R + refit)
    base_tags = {"Mrefit": ["t1-s0", "t1-s1", "t1-s2"], "MDRrefit": ["killA", "killA-s1", "killA-s2"]}
    ra = {}
    for key, label in C.ABLATION:
        if key not in base_tags:
            continue
        b = [scene_mean(R, CAMBRIDGE, t, SP, label) for t in base_tags[key]]
        row = {"default": float(np.mean([x for x in b if x is not None])) if any(x is not None for x in b) else None}
        for sw in C.REFIT_SWITCHES:
            v = [scene_mean(R, CAMBRIDGE, f"ra-{sw}-s{sd}", SP, label) for sd in (0, 1, 2)]
            v = [x for x in v if x is not None]
            row[sw] = float(np.mean(v)) if v else None
        ra[key] = row
    if any(any(v is not None for k, v in r.items() if k != "default") for r in ra.values()):
        S["refit_ablations"] = ra
        md += ["## Refit ablations (Cambridge SP+LG, AUC@10, mean of RANSAC seeds 0-2)", "",
               "| Method | default (Cauchy, once, every root) | " + " | ".join(C.REFIT_SWITCHES) + " |",
               "|---" * (2 + len(C.REFIT_SWITCHES)) + "|"]
        lab = {"Mrefit": "4p3vf(M) with refit", "MDRrefit": "4p3vf(M±δ)+R with refit"}
        for key, row in ra.items():
            md.append(f"| {lab[key]} | " + " | ".join(fmt(row[k]) for k in ["default", *C.REFIT_SWITCHES]) + " |")
        md.append("")

    # ---- view 3: swapped views 2 and 3 against the original order, paired per triplet
    v3 = {}
    if args.sets and (args.sets / "manifest.json").exists():
        man = json.loads((args.sets / "manifest.json").read_text())
        for base in ("splg", "sift_low"):
            st, sv = man["sets"].get(base), man["sets"].get(f"{base}_v3")
            if not st or not sv:
                continue
            for key, label in C.ABLATION:
                diffs = {}
                for s in sv["scenes"]:
                    o = {(r["img1"], r["img2"], r["img3"]): auc([err(r)], 10)
                         for r in rows_of(R, s, "vo", st["feature"], label)}
                    w = {(r["img1"], r["img3"], r["img2"]): auc([err(r)], 10)
                         for r in rows_of(R, s, "v3", sv["feature"], label)}
                    d = [w[k] - o[k] for k in o if k in w]
                    if d:
                        diffs[s] = d
                if diffs:
                    v3.setdefault(base, {})[key] = dict(
                        diff=float(np.mean([np.mean(d) for d in diffs.values()])),
                        triplets=sum(len(d) for d in diffs.values()))
    if v3:
        S["view3"] = v3
        md += ["## Choice of view 3: views 2 and 3 swapped minus original order (AUC@10, scene-equal, seed 0)", ""]
        for base, d in v3.items():
            md.append(f"- {base}: " + ", ".join(f"{k} {fmt(v['diff'])} ({v['triplets']})" for k, v in d.items()))
        md.append("")

    # ---- focal from the fundamental matrix, default settings
    fl = "5p3v + R + C + PRIOR(fundamental)"
    fc, fe_ = scene_mean(R, CAMBRIDGE, "sup-s0", SP, fl), scene_mean(R, ETH3D, "sup-s0", SP, fl)
    if fc is not None or fe_ is not None:
        S["fundamental_prior"] = dict(cambridge=fc, eth3d=fe_)
        md += [f"## 5pt+P3P+R+F at f from the fundamental matrix (default settings, seed 0): Cambridge {fmt(fc)}, "
               f"ETH3D {fmt(fe_)} AUC@10", ""]

    # ---- Test B
    if args.killb and args.killb.exists():
        recs = [json.loads(l) for f in sorted(args.killb.glob("*_shard*.jsonl")) for l in open(f) if l.strip()]
        if recs:
            seeded = [r for r in recs if r.get("n_seeds", 0) > 0]
            refs = Counter(r.get("ref") for r in seeded)
            tb = dict(samples=len(recs), no_seed=len(recs) - len(seeded), seeded=len(seeded),
                      ref={str(k): v for k, v in refs.items()})
            methods = sorted({k for r in seeded for k, v in r.items() if isinstance(v, dict)})
            hit = lambda r, m, what: bool((r.get(m) or {}).get(what))
            strict = [r for r in seeded if r.get("ref") == "ok"]
            tb["strict_pct"] = {m: 100 * float(np.mean([hit(r, m, "strict") for r in strict])) for m in methods}
            tb["practical_pct"] = {m: 100 * float(np.mean([hit(r, m, "practical") for r in seeded])) for m in methods}
            tb["ref_practical_pct"] = 100 * float(np.mean([bool(r.get("ref_practical")) for r in strict])) if strict else None

            def by_quartile(field):
                v = np.array([r.get(field, np.nan) for r in seeded], float)
                qs = np.nanpercentile(v, [25, 50, 75])
                out = []
                for lo, hi in zip([-np.inf, *qs], [*qs, np.inf]):
                    grp = [r for r, x in zip(seeded, v) if lo <= x < hi]
                    c = Counter(r.get("ref") for r in grp)
                    out.append(dict(lo=None if lo == -np.inf else float(lo), hi=None if hi == np.inf else float(hi),
                                    n=len(grp), ambiguous=100 * c["ambiguous"] / max(len(grp), 1),
                                    not_real=100 * c["not_real"] / max(len(grp), 1)))
                return out
            tb["exclusions_by_planarity"] = by_quartile("seed_planarity")
            tb["exclusions_by_reprojection"] = by_quartile("noise_px")
            edges = [0, 25, 50, 100, 200, 400, np.inf]
            tb["by_path_length"] = []
            for lo, hi in zip(edges[:-1], edges[1:]):
                grp = [r for r in strict if lo <= r.get("ell_px", np.nan) < hi]
                tb["by_path_length"].append(dict(lo=lo, hi=None if hi == np.inf else hi, n=len(grp), **{
                    m: 100 * float(np.mean([hit(r, m, "strict") for r in grp])) if grp else None for m in methods}))
            S["test_b"] = tb
            md += ["## Test B: where the samples go", "",
                   f"{tb['samples']} samples; {tb['no_seed']} without a mean-point seed that passes; of the "
                   f"{tb['seeded']} seeded: " + ", ".join(f"{k} {v}" for k, v in tb["ref"].items()) + ".", "",
                   "| Method | strict % (usable correct root) | practical % (all seeded) |", "|---|---|---|"]
            md += [f"| {m} | {fmt(tb['strict_pct'][m], 1)} | {fmt(tb['practical_pct'][m], 1)} |" for m in methods]
            md += ["", f"The correct root itself meets the practical criterion on {fmt(tb['ref_practical_pct'], 1)}% of "
                   "the usable samples.", "", "Exclusions (% ambiguous / % no real root) by quartile:"]
            for field in ("planarity", "reprojection"):
                md.append(f"- {field}: " + "; ".join(
                    f"[{fmt(q['lo'], 3)}, {fmt(q['hi'], 3)}) n {q['n']}: {fmt(q['ambiguous'], 1)} / {fmt(q['not_real'], 1)}"
                    for q in tb[f"exclusions_by_{field}"]))
            md += ["", "Strict success by the free point's path length (px at 800 px):"]
            for b in tb["by_path_length"]:
                md.append(f"- {b['lo']}-{b['hi'] or 'inf'} (n {b['n']}): " + ", ".join(
                    f"{m} {fmt(b[m], 1)}" for m in methods))
            md.append("")

    # ---- full solve
    if args.fullsolve and args.fullsolve.exists():
        fs = {}
        for f in sorted(args.fullsolve.glob("*_summary.json")):
            d = json.loads(f.read_text())
            fs[f.stem.replace("_summary", "")] = {k: d.get(k) for k in ("samples", "ref", "start_roots",
                                                                        "real_median", "accepted_real_median",
                                                                        "tool_in_full_solve", "tool_accepted")}
        if fs:
            S["full_solve"] = fs
            md += ["## Correct-root tool against a full solve", ""]
            md += [f"- {k}: {v['samples']} samples, reference {v['ref']}, tool root in the full solve "
                   f"{v['tool_in_full_solve']}" for k, v in fs.items()] + [""]

    if args.table2 and args.table2.exists():
        md += ["## Tzamos et al. Table 2 with the fixed fork", "", "```", args.table2.read_text().rstrip(), "```", ""]

    (args.out / "supplement.json").write_text(json.dumps(S, indent=1, default=float))
    (args.out / "supplement.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
