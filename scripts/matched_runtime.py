"""Matched-runtime results of draft v5 (Sec. 5.1 'RANSAC and runtime', Sec. 5.4, Fig. 2, Tables 1 and 3 right columns).

Inputs, all written by run_abl_dell.sh (steps curves, timing, calib):
  accuracy curves  eval_f.py / eval.py -g at the fixed iteration counts of mr_config.GRIDS['curves'], many workers:
                   <results>/focal_<scene>-graph-mr-<set>-<key>-<feature>.json   (sets sift, splg; one per method)
                   <results>/focal_<scene>-graph-mr-ss-<feature>.json            (semi-synthetic; all methods)
                   <results>/<scene>-graph-5.0t-mrc-<set>-<key>-<feature>.json    (calibrated, eval.py -t 5)
  timing           the same estimators on one pinned core, at default settings and at mr_config.GRIDS['timing']:
                   <results>/focal_<scene>[-graph]-tm-<set>-<feature>.json       (sets sift_time, splg_time, ss)
                   <results>/<scene>[-graph]-5.0t-tmc-<set>-<feature>.json       (calibrated)
Per method and set, T(k) is the mean single-core time at iteration count k (above the timing grid: least squares
a + b k on the counts >= 300) and the budget B is the mean single-core time of the reference method (6pt+P3P, or
5pt+P3P for calibrated cameras) at default settings. A method is read where T(k) = B, interpolated in log time
between the two neighbouring counts and never extrapolated: below its fastest count it is read at that count (which
favours it), above its slowest at that one. The reading is linear in the per-triplet AUC@10 values, so every
triplet gets a matched value and the statistics are paired:
  AUC@10           mean over scenes (equal weights) of the mean over triplets, x 100
  primary test     ours (mr_config.OURS) minus each baseline on the guarded SIFT triplets with w < W_MAX; two-level
                   bootstrap (scenes, then triplets in each drawn scene), one-sided p = (1 + #(diff <= 0)) / (n + 1);
                   intersection-union p = the larger of the two; scene-stratified bootstrap as sensitivity
  bins (Fig. 2a)   guarded SIFT and SP+LG triplets by their inlier ratio (0.1 wide, merged below --min-bin triplets)
  semi-synthetic   per outlier type and inlier ratio (Fig. 2b-d)
  crossover        the inlier ratio where the bootstrap mean gain changes sign, interpolated between bins or ratios,
                   with a bootstrap interval, next to the dated prediction (crossovers.py, 'refit vs ...')
Writes <out>/summary.json, <out>/matched.md and <out>/fig2.png.

  python scripts/matched_runtime.py --results third_party/threeview/results --sets results/sets \
      --semisynth $SSD/data/semisynth/manifest.json --predictions results/task28/predictions_free.json \
      --out results/matched
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mr_config as C  # noqa: E402

SS_KINDS = {"whole": "whole-track", "view3": "view-3", "single": "single-view", "mixture": "measured mixture"}


# ---------------------------------------------------------------------------------------------------- loading
def load(path):
    """Results without crashed tasks and without rows whose focal prior or cameras were missing (threeview_extra.py)."""
    if not path.exists():
        return []
    return [r for r in json.loads(path.read_text()) if not r.get("crashed")
            and not r.get("info", {}).get("prior_missing") and not r.get("info", {}).get("init_missing")]


def auc10(err):
    err = 180.0 if err is None or not np.isfinite(err) else err
    return float(np.mean([err < t for t in range(1, 11)]))


def trip_key(r):
    return f"{r['img1']} {r['img2']} {r['img3']}"


def curves_from(rows, label):
    """{triplet: {k: auc}} for one experiment label of -g results."""
    out = defaultdict(dict)
    for r in rows:
        if r["experiment"] == label and r.get("fixed_iterations") is not None:
            out[trip_key(r)][int(r["fixed_iterations"])] = auc10(r["Charalambos_P_err"])
    return out


def timing_from(rows, label):
    """({k: mean ms}, default mean ms or None, default AUC@10 x 100 or None) for one label; -g and default rows mixed."""
    by_k = defaultdict(list)
    default, default_auc = [], []
    for r in rows:
        if r["experiment"] != label:
            continue
        k = r.get("fixed_iterations")
        if k is None:
            default.append(r["info"]["runtime"])
            default_auc.append(auc10(r["Charalambos_P_err"]))
        else:
            by_k[int(k)].append(r["info"]["runtime"])
    return ({k: float(np.mean(v)) for k, v in by_k.items()}, float(np.mean(default)) if default else None,
            100 * float(np.mean(default_auc)) if default_auc else None)


def time_curve(T, ks):
    """T at every count in ks: measured where available, else a + b k fitted on the measured counts >= 300."""
    meas = {k: v for k, v in T.items()}
    fit_k = [k for k in meas if k >= 300] or list(meas)
    if len(fit_k) >= 2:
        b, a = np.polyfit(fit_k, [meas[k] for k in fit_k], 1)
    else:
        a, b = 0.0, (meas[fit_k[0]] / fit_k[0]) if fit_k else np.nan
    return {k: meas.get(k, a + b * k) for k in ks}


def reading(Tk, B):
    """(k_lo, k_hi, lam): where the time curve Tk ({k: ms}) meets the budget B, in log time, never extrapolated."""
    ks = sorted(Tk)
    t = np.array([Tk[k] for k in ks])
    if B <= t[0]:
        return ks[0], ks[0], 0.0
    if B >= t[-1]:
        return ks[-1], ks[-1], 0.0
    j = int(np.searchsorted(t, B)) - 1
    j = max(0, min(j, len(ks) - 2))
    lam = (np.log(B) - np.log(t[j])) / (np.log(t[j + 1]) - np.log(t[j]))
    return ks[j], ks[j + 1], float(np.clip(lam, 0, 1))


def matched_values(cur, rd):
    k0, k1, lam = rd
    out = {}
    for tr, c in cur.items():
        if k0 in c and k1 in c:
            out[tr] = (1 - lam) * c[k0] + lam * c[k1]
    return out


# ------------------------------------------------------------------------------------------------- statistics
def scene_auc(vals):
    """vals: {scene: array} -> scene-equal mean x 100."""
    v = [np.mean(a) for a in vals.values() if len(a)]
    return 100 * float(np.mean(v)) if v else None


def boot_two_level(diffs, n=10000, rng=None, stratified=False):
    """diffs: {scene: array}; replicates of the scene-equal mean (x 100)."""
    rng = rng or np.random.default_rng(0)
    arrs = [np.asarray(a) for a in diffs.values() if len(a)]
    S = len(arrs)
    out = np.empty(n)
    for i in range(n):
        pick = range(S) if stratified else rng.integers(0, S, S)
        out[i] = np.mean([arrs[s][rng.integers(0, len(arrs[s]), len(arrs[s]))].mean() for s in pick])
    return 100 * out


def summarize_diff(diffs, n, rng):
    """Paired difference (x 100) with two-level and stratified intervals; p = 1 when there is nothing to compare."""
    diffs = {s: a for s, a in diffs.items() if len(a)}
    if not diffs:
        return dict(estimate=None, ci95=None, p_one_sided=1.0, ci95_stratified=None, triplets=0, scenes=0)
    est = scene_auc(diffs)
    rep = boot_two_level(diffs, n, rng)
    strat = boot_two_level(diffs, max(n // 5, 1000), rng, stratified=True)
    return dict(estimate=est, ci95=[float(np.percentile(rep, 2.5)), float(np.percentile(rep, 97.5))],
                p_one_sided=float((1 + np.sum(rep <= 0)) / (len(rep) + 1)),
                ci95_stratified=[float(np.percentile(strat, 2.5)), float(np.percentile(strat, 97.5))],
                triplets=int(sum(len(a) for a in diffs.values())), scenes=len(diffs))


def crossings(x, g):
    """Every x where g changes sign between strictly positive and strictly negative neighbours (zeros and missing
    values skipped), linearly interpolated, from high to low x."""
    x, g = np.asarray(x, float), np.asarray(g, float)
    ok = np.isfinite(g) & (g != 0)
    x, g = x[ok], g[ok]
    o = np.argsort(x)[::-1]
    x, g = x[o], g[o]
    return [float(x[i] + (x[i + 1] - x[i]) * g[i] / (g[i] - g[i + 1]))
            for i in range(len(x) - 1) if np.sign(g[i]) != np.sign(g[i + 1])]


def crossing(x, g):
    """The crossover: the largest x where the gain changes sign (below it the sign of the low-w side holds)."""
    c = crossings(x, g)
    return c[0] if c else None


def crossing_ci(x, groups, n, rng):
    """groups: list over x of {scene: diff array}; bootstrap the crossing (two-level within every group)."""
    reps = []
    for _ in range(n):
        g = []
        for d in groups:
            arrs = [np.asarray(a) for a in d.values() if len(a)]
            pick = rng.integers(0, len(arrs), len(arrs))
            g.append(np.mean([arrs[s][rng.integers(0, len(arrs[s]), len(arrs[s]))].mean() for s in pick]))
        reps.append(crossing(x, g))
    found = [r for r in reps if r is not None]
    return dict(share_with_crossing=len(found) / n,
                ci95=[float(np.percentile(found, 2.5)), float(np.percentile(found, 97.5))] if found else None)


def predicted(pred, kind, base):
    """Predicted crossover inlier ratios for 'refit vs <base>' from crossovers.py output, or the text if none."""
    if not pred:
        return None
    name = {"6p": "refit vs 6pt+P3P", "seq": "refit vs sequential"}[base]
    txt = pred.get("crossovers", {}).get(kind, {}).get(name)
    if txt is None:
        return None
    ws = [float(v) for v in re.findall(r"w = ([0-9.]+)", txt)]
    return dict(text=txt, w=ws)


# ------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True, help="threeview results folder")
    ap.add_argument("--sets", type=Path, required=True, help="eval_sets.py output folder (labels.csv, manifest.json)")
    ap.add_argument("--semisynth", type=Path, help="semisynth_outliers.py manifest.json")
    ap.add_argument("--predictions", type=Path, help="crossovers.py predictions .json (with the refit)")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--min-bin", type=int, default=200)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    R = args.results
    man = json.loads((args.sets / "manifest.json").read_text())
    labels = {}
    for r in csv.DictReader(open(args.sets / "labels.csv", newline="")):
        labels[r["set"], r["scene"], r["triplet"]] = dict(w=float(r["w"]), a=float(r["a"]), b=float(r["b"]),
                                                          matcher=r["matcher"])
    pred = json.loads(args.predictions.read_text()) if args.predictions and args.predictions.exists() else None
    summary = dict(settings=dict(grids=C.GRIDS, ours=C.OURS, baselines=C.BASELINES, w_max=C.W_MAX, boot=args.boot),
                   budgets={}, readings={}, auc={}, primary={}, bins={}, semisynth={}, calibrated={})
    md = ["# Matched runtime (draft v5)", ""]

    def set_scenes(name):
        return man["sets"].get(name, {}).get("scenes", {})

    def timing(prefix, tag_set, feature, scenes, table, graph_tag, mid=""):
        rows = []
        for s in scenes:
            rows += load(R / f"{prefix}{s}-graph{mid}-{graph_tag}-{tag_set}-{feature}.json")
            rows += load(R / f"{prefix}{s}{mid}-{graph_tag}-{tag_set}-{feature}.json")
        out = {}
        for key, label, _ in table:
            Tk, Td, Da = timing_from(rows, label)
            if Tk:
                out[key] = (Tk, Td, Da)
        return out

    def budget(tim, ref):
        return tim[ref][1] if ref in tim else None

    def read_at(tim, key, B, curs):
        """(reading, time curve) of one method: its time curve at the counts present in its accuracy curves."""
        ks = sorted({k for cur in curs for c in cur.values() for k in c})
        if key not in tim or B is None or not ks:
            return None, None
        Tk = time_curve(tim[key][0], ks)
        return reading(Tk, B), Tk

    # ---- shared focal: sets sift (primary = w < W_MAX) and splg
    per_trip = {}       # (set, key) -> {(scene, triplet): matched value}
    for set_name, time_set in (("sift", "sift_time"), ("splg", "splg_time")):
        feat = man["sets"].get(set_name, {}).get("feature")
        if not feat:
            continue
        tim = timing("focal_", time_set, man["sets"][time_set]["feature"], set_scenes(time_set), C.FOCAL, "tm")
        B = budget(tim, C.FOCAL_REF)
        summary["budgets"][set_name] = B
        summary["readings"][set_name] = {}
        keep = (lambda s, tr: ("sift", s, tr) in labels and labels["sift", s, tr]["w"] < C.W_MAX) \
            if set_name == "sift" else (lambda s, tr: True)
        summary.setdefault("curves", {})[set_name] = {}
        for key, label, _ in C.FOCAL:
            curs = {s: curves_from(load(R / f"focal_{s}-graph-mr-{set_name}-{key}-{feat}.json"), label)
                    for s in set_scenes(set_name)}
            rd, Tk = read_at(tim, key, B, curs.values())
            if rd is None:
                continue
            summary["readings"][set_name][key] = dict(k_lo=rd[0], k_hi=rd[1], lam=rd[2])
            vals, at_k = {}, defaultdict(lambda: defaultdict(list))
            for s, cur in curs.items():
                for tr, v in matched_values(cur, rd).items():
                    vals[s, tr] = v
                for tr, c in cur.items():
                    if keep(s, tr):
                        for k, v in c.items():
                            at_k[k][s].append(v)
            per_trip[set_name, key] = vals
            ks = sorted(at_k)          # Fig. 2e: AUC@10 against mean single-core time (sift: w < W_MAX)
            summary["curves"][set_name][key] = dict(
                k=ks, ms=[Tk.get(k) for k in ks], auc=[scene_auc({s: np.array(v) for s, v in at_k[k].items()})
                                                       for k in ks], default_ms=tim[key][1],
                default_auc_timing_subset=tim[key][2])

    def by_scene(vals, keep=None):
        d = defaultdict(list)
        for (s, tr), v in vals.items():
            if keep is None or keep(s, tr):
                d[s].append(v)
        return {s: np.array(v) for s, v in d.items()}

    low = lambda s, tr: ("sift", s, tr) in labels and labels["sift", s, tr]["w"] < C.W_MAX
    summary["auc"]["sift_low"] = {k: scene_auc(by_scene(per_trip[("sift", k)], low)) for _, k in
                                  [(None, k) for k, _, _ in C.FOCAL] if ("sift", k) in per_trip}
    summary["auc"]["splg"] = {k: scene_auc(by_scene(per_trip[("splg", k)])) for k, _, _ in C.FOCAL
                              if ("splg", k) in per_trip}

    # ---- primary test
    if ("sift", C.OURS) in per_trip:
        ours = per_trip["sift", C.OURS]
        res = {}
        for base in C.BASELINES:
            if ("sift", base) not in per_trip:
                continue
            other = per_trip["sift", base]
            common = {k: ours[k] - other[k] for k in ours if k in other and low(*k)}
            res[base] = summarize_diff(by_scene(common), args.boot, rng)
        if len(res) == len(C.BASELINES):
            p = max(r["p_one_sided"] for r in res.values())
            res["intersection_union_p"] = p
            res["superior_at_0.05"] = bool(p < 0.05)
        summary["primary"] = res

    # ---- bins (Fig. 2a): guarded SIFT and SP+LG pooled
    pooled = []
    for set_name in ("sift", "splg"):
        if (set_name, C.OURS) not in per_trip:
            continue
        for (s, tr), v in per_trip[set_name, C.OURS].items():
            lab = labels.get((set_name, s, tr))
            if lab:
                pooled.append((set_name, s, tr, lab["w"]))
    if pooled:
        w_all = np.array([p[3] for p in pooled])
        edges = list(np.round(np.arange(0, 1.0001, 0.1), 2))
        counts = np.histogram(w_all, edges)[0].tolist()
        while len(counts) > 1:            # merge small bins into their right neighbour (the last into its left)
            small = [i for i, c in enumerate(counts) if c < args.min_bin]
            if not small:
                break
            i = small[0]
            lo, hi = (i, i + 1) if i + 1 < len(counts) else (i - 1, i)
            counts[lo] += counts[hi]
            del counts[hi]
            del edges[hi]                 # the edge between bins lo and hi
        bins = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            members = [p for p in pooled if lo <= p[3] < hi or (hi == edges[-1] and p[3] == hi)]
            b = dict(lo=lo, hi=hi, triplets=len(members), mean_w=float(np.mean([p[3] for p in members])) if members else None,
                     share_splg=float(np.mean([p[0] == "splg" for p in members])) if members else None, auc={}, gain={})
            for key, _, _ in C.FOCAL:
                vals = defaultdict(list)
                for set_name, s, tr, _ in members:
                    v = per_trip.get((set_name, key), {}).get((s, tr))
                    if v is not None:
                        vals[s].append(v)
                b["auc"][key] = scene_auc({s: np.array(v) for s, v in vals.items()})
            for base in C.BASELINES:
                d = defaultdict(list)
                for set_name, s, tr, _ in members:
                    o, x = per_trip.get((set_name, C.OURS), {}).get((s, tr)), per_trip.get((set_name, base), {}).get((s, tr))
                    if o is not None and x is not None:
                        d[s].append(o - x)
                b["gain"][base] = {s: np.array(v) for s, v in d.items()}
            bins.append(b)
        out_bins = []
        for base in C.BASELINES:
            x = [b["mean_w"] for b in bins if b["gain"][base]]
            groups = [b["gain"][base] for b in bins if b["gain"][base]]
            g = [scene_auc(gr) for gr in groups]
            summary["bins"][f"crossover_vs_{base}"] = dict(
                measured=crossing(x, g), all=crossings(x, g), gains=dict(zip(map(str, x), g)),
                bootstrap=crossing_ci(x, groups, min(args.boot, 2000), rng),
                predicted=predicted(pred, "measured mixture", base))
        for b in bins:
            b["gain"] = {base: scene_auc(v) for base, v in b["gain"].items()}
            out_bins.append(b)
        summary["bins"]["bins"] = out_bins

    # ---- semi-synthetic (Fig. 2b-d)
    if args.semisynth and args.semisynth.exists():
        ss = json.loads(args.semisynth.read_text())
        ss_scenes = list(ss["scenes"])
        for kind, by_w in ss["features"].items():
            rows_k = {}
            for w_str, feat in by_w.items():
                tim = timing("focal_", "ss", feat, ss_scenes, C.FOCAL, "tm")
                B = budget(tim, C.FOCAL_REF)
                rows = {s: load(R / f"focal_{s}-graph-mr-ss-{feat}.json") for s in ss_scenes}
                vals = {}
                for key, label, _ in C.FOCAL:
                    curs = {s: curves_from(rows[s], label) for s in ss_scenes}
                    rd, _ = read_at(tim, key, B, curs.values())
                    if rd is not None:
                        vals[key] = {s: matched_values(c, rd) for s, c in curs.items()}
                rows_k[float(w_str)] = dict(budget=B, vals=vals)
            out = dict(levels={}, crossovers={})
            for w, d in sorted(rows_k.items()):
                out["levels"][str(w)] = dict(budget=d["budget"], auc={k: scene_auc({s: np.array(list(v.values()))
                                                                                     for s, v in per_s.items()})
                                                                      for k, per_s in d["vals"].items()})
            for base in C.BASELINES:
                ws, groups = [], []
                for w, d in sorted(rows_k.items()):
                    if C.OURS in d["vals"] and base in d["vals"]:
                        gr = {}
                        for s, o in d["vals"][C.OURS].items():
                            x = d["vals"][base].get(s, {})
                            g = np.array([o[t] - x[t] for t in o if t in x])
                            if len(g):
                                gr[s] = g
                        if gr:
                            ws.append(w)
                            groups.append(gr)
                if groups:
                    out["crossovers"][f"vs_{base}"] = dict(
                        gains={str(w): scene_auc(g) for w, g in zip(ws, groups)},
                        measured=crossing(ws, [scene_auc(g) for g in groups]),
                        all=crossings(ws, [scene_auc(g) for g in groups]),
                        bootstrap=crossing_ci(ws, groups, min(args.boot, 2000), rng),
                        predicted=predicted(pred, SS_KINDS.get(kind, kind), base))
            summary["semisynth"][kind] = out

    # ---- calibrated (Table 3): sift_low and semi-synthetic whole-track at w = 0.25
    feat = man["sets"].get("sift_low", {}).get("feature")
    if feat:
        tim = timing("", "sift_time", man["sets"]["sift_time"]["feature"], set_scenes("sift_time"), C.CALIB, "tmc",
                     C.CALIB_MID)
        B = budget(tim, C.CALIB_REF)
        auc = {}
        for key, label, _ in C.CALIB:
            curs = {s: curves_from(load(R / f"{s}-graph{C.CALIB_MID}-mrc-sift_low-{key}-{feat}.json"), label)
                    for s in set_scenes("sift_low")}
            rd, _ = read_at(tim, key, B, curs.values())
            if rd is not None:
                auc[key] = scene_auc({s: np.array(list(matched_values(c, rd).values())) for s, c in curs.items()})
        summary["calibrated"]["sift_low"] = dict(budget=B, auc=auc)
    if args.semisynth and args.semisynth.exists():
        ss = json.loads(args.semisynth.read_text())
        feat = ss["features"].get("whole", {}).get("0.25")
        if feat:
            tim = timing("", "ss", feat, list(ss["scenes"]), C.CALIB, "tmc", C.CALIB_MID)
            B = budget(tim, C.CALIB_REF)
            auc = {}
            for key, label, _ in C.CALIB:
                curs = {s: curves_from(load(R / f"{s}-graph{C.CALIB_MID}-mrc-ss-{feat}.json"), label)
                        for s in ss["scenes"]}
                rd, _ = read_at(tim, key, B, curs.values())
                if rd is not None:
                    auc[key] = scene_auc({s: np.array(list(matched_values(c, rd).values())) for s, c in curs.items()})
            summary["calibrated"]["whole_0.25"] = dict(budget=B, auc=auc)

    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    write_md(summary, md, args.out)
    figure(summary, args.out)
    print("\n".join(md))


def fmt(v, d=2):
    return "-" if v is None else f"{v:.{d}f}"


def write_md(s, md, out):
    names = {k: n for k, _, n in C.FOCAL}
    md += [f"Budgets (mean single-core ms of {C.FOCAL_REF} at default settings): " +
           ", ".join(f"{k} {fmt(v)}" for k, v in s["budgets"].items()), ""]
    md += ["| Method | SIFT, w < %.1f | SP+LG |" % C.W_MAX, "|---|---|---|"]
    for k, _, n in C.FOCAL:
        md.append(f"| {n} | {fmt(s['auc'].get('sift_low', {}).get(k))} | {fmt(s['auc'].get('splg', {}).get(k))} |")
    md.append("")
    if s["primary"]:
        md.append(f"Primary test, {names[C.OURS]} minus each baseline on the guarded SIFT triplets with w < {C.W_MAX}:")
        for base in C.BASELINES:
            r = s["primary"].get(base)
            if r and not r["triplets"]:
                md.append(f"- vs {names[base]}: no paired triplets")
            elif r:
                md.append(f"- vs {names[base]}: {fmt(r['estimate'])} AUC@10, 95% CI [{fmt(r['ci95'][0])}, "
                          f"{fmt(r['ci95'][1])}] (scene-stratified [{fmt(r['ci95_stratified'][0])}, "
                          f"{fmt(r['ci95_stratified'][1])}]), one-sided p = {r['p_one_sided']:.4g}, "
                          f"{r['triplets']} triplets in {r['scenes']} scenes")
        if "intersection_union_p" in s["primary"]:
            md.append(f"- intersection-union p = {s['primary']['intersection_union_p']:.4g}: "
                      f"{'superior' if s['primary']['superior_at_0.05'] else 'not shown superior'} at 0.05")
        md.append("")
    if s["bins"].get("bins"):
        md += ["Real triplets by inlier ratio (Fig. 2a):", "",
               "| w | triplets | SP+LG share | " + " | ".join(names[k] for k, _, _ in C.FOCAL) + " |",
               "|---" * (3 + len(C.FOCAL)) + "|"]
        for b in s["bins"]["bins"]:
            md.append(f"| {b['lo']:.1f}-{b['hi']:.1f} | {b['triplets']} | {fmt(b['share_splg'])} | " +
                      " | ".join(fmt(b["auc"].get(k)) for k, _, _ in C.FOCAL) + " |")
        for base in C.BASELINES:
            c = s["bins"].get(f"crossover_vs_{base}", {})
            md.append(f"- crossover vs {names[base]}: measured {fmt(c.get('measured'), 3)}, bootstrap "
                      f"{c.get('bootstrap')}, predicted {c.get('predicted')}")
        md.append("")
    for kind, d in s["semisynth"].items():
        md.append(f"Semi-synthetic, {SS_KINDS.get(kind, kind)} outliers (Fig. 2):")
        for w, lv in d["levels"].items():
            md.append(f"- w = {w}: " + ", ".join(f"{names[k]} {fmt(v)}" for k, v in lv["auc"].items()))
        for name, c in d["crossovers"].items():
            md.append(f"- crossover {name}: gains {c['gains']}, measured {fmt(c['measured'], 3)}, "
                      f"bootstrap {c['bootstrap']}, predicted {c['predicted']}")
        md.append("")
    for name, d in s["calibrated"].items():
        md.append(f"Calibrated, {name} (budget {fmt(d['budget'])} ms): " +
                  ", ".join(f"{n} {fmt(d['auc'].get(k))}" for k, _, n in C.CALIB))
    (out / "matched.md").write_text("\n".join(md) + "\n")


def figure(s, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = {k: n for k, _, n in C.FOCAL}
    show = ["6p", "seq", "M", C.OURS, "O"]
    fig, ax = plt.subplots(1, 5, figsize=(21, 3.6))
    for set_name, ls in (("sift", "-"), ("splg", "--")):     # (e) AUC@10 against mean single-core time
        for i, k in enumerate(show):
            c = s.get("curves", {}).get(set_name, {}).get(k)
            if not c:
                continue
            line = ax[4].plot(c["ms"], c["auc"], ls=ls, marker=".", color=f"C{i}",
                              label=f"{names[k]}, {'SIFT w < %.1f' % C.W_MAX if set_name == 'sift' else 'SP+LG'}")
            if c["default_ms"] and c["default_auc_timing_subset"] is not None:
                ax[4].plot([c["default_ms"]], [c["default_auc_timing_subset"]], "s", color=line[0].get_color())
        if s["budgets"].get(set_name):
            ax[4].axvline(s["budgets"][set_name], color="gray", lw=0.7, ls=ls)
    ax[4].set_xscale("log")
    ax[4].set_title("(e) AUC@10 vs runtime (squares: defaults)")
    ax[4].legend(fontsize=5)
    if s["bins"].get("bins"):
        bins = s["bins"]["bins"]
        x = [b["mean_w"] for b in bins]
        for k in show:
            ax[0].plot(x, [b["auc"].get(k) for b in bins], "o-", label=names[k],
                       ls=":" if k == "O" else "-")
        for base in C.BASELINES:
            p = (s["bins"].get(f"crossover_vs_{base}", {}).get("predicted") or {}).get("w") or []
            for w in p:
                ax[0].axvline(w, color="k", lw=0.7, ls="--")
        ax[0].set_title("(a) real triplets by inlier ratio")
    for i, kind in enumerate(("whole", "view3", "mixture")):
        d = s["semisynth"].get(kind)
        if not d:
            continue
        ws = sorted(float(w) for w in d["levels"])
        for k in show:
            ax[i + 1].plot(ws, [d["levels"][str(w)]["auc"].get(k) for w in ws], "o-", label=names[k],
                           ls=":" if k == "O" else "-")
        if kind == "mixture" and "single" in s["semisynth"]:
            dd = s["semisynth"]["single"]
            ax[i + 1].plot(ws, [dd["levels"].get(str(w), {}).get("auc", {}).get(C.OURS) for w in ws], "k--",
                           label=f"{names[C.OURS]}, single-view")
        for c in d["crossovers"].values():
            for w in (c.get("predicted") or {}).get("w") or []:
                ax[i + 1].axvline(w, color="k", lw=0.7, ls="--")
        ax[i + 1].set_title(f"({'bcd'[i]}) {SS_KINDS[kind]} outliers")
    for a in ax[:4]:
        a.set_xlabel("inlier ratio w")
        a.set_ylabel("AUC@10 at matched runtime")
    ax[4].set_xlabel("mean single-core time per triplet (ms)")
    ax[4].set_ylabel("AUC@10")
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig2.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
