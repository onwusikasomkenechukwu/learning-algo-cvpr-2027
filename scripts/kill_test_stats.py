"""Statistics for both kill tests (student instructions v5 Tasks 1.9 / 2.2, draft v4 Sec. 6.2), written to
<out>.md and <out>.json. The decisions follow the pre-registered rules; the rest says how firm they are.

Kill test B (results/killB/<scene>_shard<i>.jsonl, src/homotopy_proto.py): one sample per triplet, continuation
and converged LM from the same seeds, paired binary outcome "reaches the correct root" (strict: samples whose
reference root is unambiguous). Rule: cont - LM >= +5 pp and exact McNemar p < 0.05.
  - per scene and pooled: rates, difference, discordant pairs, exact McNemar p, Newcombe's hybrid score
    interval for a paired difference (Newcombe 1998, method 10), one-sided exact p for "LM is better"
  - pooled intervals that respect the scenes: stratified bootstrap (samples resampled within each scene) and
    two-level bootstrap (scenes, then samples), both on the four paired-outcome counts of each scene
  - heterogeneity of the per-scene differences: Cochran's Q and I^2
  - whether the +5 pp target lies outside the 95 % intervals (a decisive fail rather than a point-estimate one)
  - sensitivity: 'practical' success on every seeded sample (no unambiguity filter); secondary comparisons of
    continuation with Newton homotopy and Newton, Holm-adjusted together with the primary one

Kill test A (eval_f.py results): AUC@10 per scene (error = max of mean rotation / mean translation error over
pairs 12 and 13, NaN = 180 deg, mean over thresholds 1..10 deg of the fraction below), scenes weighted equally.
One run per RANSAC seed: seed 0 = focal_<scene>-<feat>.json and focal_<scene>-killA-<feat>.json, seed k = the
same with tags s<k> and killA-s<k> (EVALF_SEED, scripts/patches/threeview_seed.py). Each triplet's score is
averaged over the seeds. Rule: 6p3v - best re-fitted ('+ ENM') variant >= 2.0 AUC@10.
  - the best variant is chosen on the same data, so every bootstrap replicate re-selects it (keeping the observed
    best fixed would understate how close the gap can come to 2.0); the fixed-best interval is shown too
  - stratified bootstrap (triplets within the five fixed scenes: the Cambridge benchmark as defined) and
    two-level bootstrap (scenes too; with five scenes it is coarse), and the share of replicates with gap >= 2
  - gap per scene, leaving one scene out, per seed (run-to-run spread), per variant, and the refit's own effect
    (each '+ ENM' variant against the same variant without it, seed 0)

  python scripts/kill_test_stats.py --killb results/killB/*.jsonl --results third_party/threeview/results \
      --out results/abl_dell/kill_test_stats
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, chi2

Z = 1.959963984540054
CAMBRIDGE = ["GreatCourt", "KingsCollege", "OldHospital", "ShopFacade", "StMarysChurch"]
TARGET_B, TARGET_A = 5.0, 2.0


# ---------------------------------------------------------------- kill test B

def paired_counts(rows, a, b, key):
    """[both, a only, b only, neither] for success `key` of methods a and b."""
    x = np.array([[bool(r[a][key]), bool(r[b][key])] for r in rows], bool).reshape(-1, 2)
    return np.array([np.sum(x[:, 0] & x[:, 1]), np.sum(x[:, 0] & ~x[:, 1]), np.sum(~x[:, 0] & x[:, 1]),
                     np.sum(~x[:, 0] & ~x[:, 1])], float)


def wilson(k, n):
    p, d = k / n, 1 + Z * Z / n
    c, h = (p + Z * Z / (2 * n)) / d, Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return c - h, c + h


def newcombe(c4):
    """95 % interval for p_a - p_b from paired counts (Newcombe 1998, method 10, continuity-corrected phi)."""
    a, b, c, d = c4
    n = c4.sum()
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    A = a * d - b * c
    if A > 0:
        A = max(A - n / 2, 0.0)
    phi = A / np.sqrt(den) if den > 0 else 0.0
    lo = (p1 - p2) - np.sqrt(max((p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2, 0))
    hi = (p1 - p2) + np.sqrt(max((u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2, 0))
    return lo, hi


def compare(c4):
    n, b, c = c4.sum(), int(c4[1]), int(c4[2])
    lo, hi = newcombe(c4)
    return dict(n=int(n), rate_a=(c4[0] + c4[1]) / n, rate_b=(c4[0] + c4[2]) / n, diff=(b - c) / n,
                ci=[lo, hi], a_only=b, b_only=c,
                p=binomtest(b, b + c, 0.5).pvalue if b + c else 1.0,
                p_b_better=binomtest(b, b + c, 0.5, alternative="less").pvalue if b + c else 1.0)


def boot_b(per_scene, B, rng):
    """Stratified and two-level bootstrap of the pooled difference (sum of (b - c) / sum of n)."""
    C = np.array(per_scene)                        # (S, 4)
    n, q = C.sum(1).astype(int), C / C.sum(1, keepdims=True)
    S = len(C)
    strat_num, strat_den = np.zeros(B), np.zeros(B)
    for s in range(S):
        m = rng.multinomial(n[s], q[s], size=B)
        strat_num += m[:, 1] - m[:, 2]
        strat_den += n[s]
    times = np.stack([np.bincount(row, minlength=S) for row in rng.integers(0, S, (B, S))])   # (B, S)
    two_num, two_den = np.zeros(B), np.zeros(B)
    for s in range(S):
        m = rng.multinomial(n[s] * times[:, s], q[s])
        two_num += m[:, 1] - m[:, 2]
        two_den += n[s] * times[:, s]
    return strat_num / strat_den, two_num / two_den


def heterogeneity(per_scene):
    d, w = [], []
    for c4 in per_scene:
        n, b, c = c4.sum(), c4[1], c4[2]
        var = (b + c - (b - c) ** 2 / n) / n ** 2
        if var > 0:
            d.append((b - c) / n)
            w.append(1 / var)
    d, w = np.array(d), np.array(w)
    if len(d) < 2:
        return None
    mean = np.sum(w * d) / np.sum(w)
    Q = float(np.sum(w * (d - mean) ** 2))
    df = len(d) - 1
    return dict(Q=Q, df=df, p=float(chi2.sf(Q, df)), I2=max(0.0, (Q - df) / Q) if Q > 0 else 0.0)


def holm(ps):
    order = np.argsort(ps)
    adj, run = np.empty(len(ps)), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def kill_b(paths, B, rng):
    by = {}
    paths = [q for p in map(Path, paths) for q in (sorted(p.glob("*.jsonl")) if p.is_dir() else [p])]
    for p in paths:
        scene = Path(p).name.split(".")[0].split("_shard")[0]
        by.setdefault(scene, []).extend(json.loads(l) for l in open(p) if l.strip())
    scenes = sorted(by)
    seeded = {s: [r for r in by[s] if r.get("n_seeds")] for s in scenes}
    strict = {s: [r for r in seeded[s] if r.get("ref") == "ok"] for s in scenes}
    res = dict(scenes=scenes, n_samples={s: len(by[s]) for s in scenes},
               n_seeded={s: len(seeded[s]) for s in scenes}, n_strict={s: len(strict[s]) for s in scenes})
    per = [paired_counts(strict[s], "cont", "lm", "strict") for s in scenes]
    res["per_scene"] = {s: compare(c) for s, c in zip(scenes, per)}
    pooled = compare(np.sum(per, 0))
    st, tl = boot_b(per, B, rng)
    pooled["ci_stratified"] = np.percentile(st, [2.5, 97.5]).tolist()
    pooled["ci_two_level"] = np.percentile(tl, [2.5, 97.5]).tolist()
    res["pooled"] = pooled
    res["heterogeneity"] = heterogeneity(per)
    res["scenes_lm_ahead"] = sum(res["per_scene"][s]["diff"] < 0 for s in scenes)
    res["decision"] = dict(diff_pp=100 * pooled["diff"], p=pooled["p"],
                           passes=bool(100 * pooled["diff"] >= TARGET_B and pooled["p"] < 0.05),
                           target_excluded=bool(100 * max(pooled["ci"][1], pooled["ci_stratified"][1],
                                                          pooled["ci_two_level"][1]) < TARGET_B))
    prac = compare(np.sum([paired_counts(seeded[s], "cont", "lm", "practical") for s in scenes], 0))
    res["practical_all_seeded"] = prac
    sec = {m: compare(np.sum([paired_counts(strict[s], "cont", m, "strict") for s in scenes], 0))
           for m in ("lm", "newton_hom", "newton")}
    for m, a in zip(sec, holm(np.array([sec[m]["p"] for m in sec]))):
        sec[m]["p_holm"] = float(a)
    res["cont_vs"] = sec
    return res


def report_b(r):
    pp = lambda x: f"{100 * x:+.1f}"
    L = ["## Kill test B: continuation vs converged LM (correct root, paired)", "",
         "| scene | samples | strict n | cont % | LM % | cont - LM (pp) | 95 % CI (Newcombe) | cont only / LM only "
         "| McNemar p |", "|---|---|---|---|---|---|---|---|---|"]
    for s in r["scenes"] + ["POOLED"]:
        c = r["pooled"] if s == "POOLED" else r["per_scene"][s]
        n = sum(r["n_samples"].values()) if s == "POOLED" else r["n_samples"][s]
        L.append(f"| {s} | {n} | {c['n']} | {100 * c['rate_a']:.1f} | {100 * c['rate_b']:.1f} | {pp(c['diff'])} | "
                 f"[{pp(c['ci'][0])}, {pp(c['ci'][1])}] | {c['a_only']} / {c['b_only']} | {c['p']:.2g} |")
    p, d, h = r["pooled"], r["decision"], r["heterogeneity"]
    L += ["", f"- Pooled cont - LM = {d['diff_pp']:+.1f} pp; 95 % CI Newcombe [{pp(p['ci'][0])}, {pp(p['ci'][1])}], "
              f"stratified bootstrap [{pp(p['ci_stratified'][0])}, {pp(p['ci_stratified'][1])}], two-level "
              f"bootstrap [{pp(p['ci_two_level'][0])}, {pp(p['ci_two_level'][1])}] pp.",
          f"- LM ahead in {r['scenes_lm_ahead']} of {len(r['scenes'])} scenes; one-sided exact p that LM is better: "
          f"{p['p_b_better']:.2g}.",
          f"- Heterogeneity across scenes: Q = {h['Q']:.2f} (df {h['df']}, p = {h['p']:.2g}), I^2 = {100 * h['I2']:.0f} %."
          if h else "- Heterogeneity: fewer than two scenes.",
          f"- The +{TARGET_B:.0f} pp target is {'outside' if d['target_excluded'] else 'INSIDE'} every 95 % interval"
          f"{' (decisive)' if d['target_excluded'] else ''}.",
          f"- Sensitivity, 'practical' success on all {r['practical_all_seeded']['n']} seeded samples: cont - LM = "
          f"{pp(r['practical_all_seeded']['diff'])} pp [{pp(r['practical_all_seeded']['ci'][0])}, "
          f"{pp(r['practical_all_seeded']['ci'][1])}], McNemar p = {r['practical_all_seeded']['p']:.2g}.",
          "- Continuation against each other method (strict, Holm over the three): " + "; ".join(
              f"{m} {pp(c['diff'])} pp [{pp(c['ci'][0])}, {pp(c['ci'][1])}], p_Holm = {c['p_holm']:.2g}"
              for m, c in r["cont_vs"].items()) + ".", "",
          f"KILL TEST B: cont - LM = {d['diff_pp']:+.1f} pp (needs >= +{TARGET_B:.0f}), McNemar p = {d['p']:.2g} -> "
          f"{'PASS' if d['passes'] else 'FAIL'}" + (" (target outside the 95 % intervals)" if d["target_excluded"]
                                                   and not d["passes"] else "")]
    return L


# ---------------------------------------------------------------- kill test A

def scores(rows):
    """{triplet: AUC@10 contribution in percent}, {triplet: crashed} for one experiment's rows."""
    out, crashed = {}, {}
    for r in rows:
        e = max(0.5 * (r["R_12_err"] + r["R_13_err"]), 0.5 * (r["t_12_err"] + r["t_13_err"]))
        e = 180.0 if np.isnan(e) else e
        k = (r["img1"], r["img2"], r["img3"])
        out[k] = 100.0 * np.mean(e < np.arange(1, 11))
        crashed[k] = bool(r.get("crashed"))
    return out, crashed


def load_a(results, feat):
    """data[seed][scene][experiment] = (scores, crashed)."""
    data = {}
    for seed in range(10):
        tags = ("", "-killA") if seed == 0 else (f"-s{seed}", f"-killA-s{seed}")
        for s in CAMBRIDGE:
            for tag in tags:
                p = Path(results) / f"focal_{s}{tag}-{feat}.json"
                if not p.exists():
                    continue
                rows = json.loads(p.read_text())
                for exp in {r["experiment"] for r in rows}:
                    data.setdefault(seed, {}).setdefault(s, {})[exp] = scores(
                        [r for r in rows if r["experiment"] == exp])
    return data


def kill_a(results, feat, B, rng):
    data = load_a(results, feat)
    if 0 not in data:
        return None
    enm = sorted({e for sc in data[0].values() for e in sc if "+ ENM" in e})
    methods = ["6p3v"] + enm
    scenes = [s for s in CAMBRIDGE if all(m in data[0].get(s, {}) for m in methods)]
    seeds = [k for k in sorted(data) if all(m in data[k].get(s, {}) for s in scenes for m in methods)]
    if not scenes or not enm:
        return None
    keys = {s: sorted(set.intersection(*[set(data[k][s][m][0]) for k in seeds for m in methods])) for s in scenes}
    # (n_s, M) seed-averaged scores per scene, and per seed
    S = {s: np.array([[np.mean([data[k][s][m][0][t] for k in seeds]) for m in methods] for t in keys[s]])
         for s in scenes}
    per_seed = {k: {s: np.array([[data[k][s][m][0][t] for m in methods] for t in keys[s]]) for s in scenes}
                for k in seeds}
    crashed = {m: int(sum(data[k][s][m][1][t] for k in seeds for s in scenes for t in keys[s])) for m in methods}

    def gaps(mats):                     # gap of every ENM variant, pooled over scenes with equal weights
        auc = np.mean([m.mean(0) for m in mats], 0)
        return auc[0] - auc[1:], auc

    g, auc = gaps([S[s] for s in scenes])
    best = int(np.argmin(g))
    res = dict(scenes=scenes, seeds=seeds, n_triplets={s: len(keys[s]) for s in scenes}, crashed_rows=crashed,
               auc={m: float(a) for m, a in zip(methods, auc)}, gap={v: float(x) for v, x in zip(enm, g)},
               best=enm[best], gap_best=float(g[best]))
    # bootstrap: stratified (scenes fixed) and two-level (scenes resampled), the best variant re-selected each time
    sel_st, fix_st, sel_tl, all_st = [], [], [], []
    chunk = 100
    for _ in range(0, B, chunk):
        means = np.stack([S[s][rng.integers(0, len(S[s]), (chunk, len(S[s])))].mean(1) for s in scenes], 1)
        auc_b = means.mean(1)                                   # (chunk, M)
        gb = auc_b[:, :1] - auc_b[:, 1:]
        sel_st.append(gb.min(1)), fix_st.append(gb[:, best]), all_st.append(gb)
        pick = rng.integers(0, len(scenes), (chunk, len(scenes)))
        auc_t = means[np.arange(chunk)[:, None], pick].mean(1)
        sel_tl.append((auc_t[:, :1] - auc_t[:, 1:]).min(1))
    sel_st, fix_st, sel_tl, all_st = map(np.concatenate, (sel_st, fix_st, sel_tl, all_st))
    res.update(ci_selected_stratified=np.percentile(sel_st, [2.5, 97.5]).tolist(),
               ci_selected_two_level=np.percentile(sel_tl, [2.5, 97.5]).tolist(),
               ci_fixed_best_stratified=np.percentile(fix_st, [2.5, 97.5]).tolist(),
               share_gap_ge_target=dict(stratified=float(np.mean(sel_st >= TARGET_A)),
                                        two_level=float(np.mean(sel_tl >= TARGET_A))),
               ci_variant_stratified={v: np.percentile(all_st[:, i], [2.5, 97.5]).tolist()
                                      for i, v in enumerate(enm)})
    res["per_scene_gap_best"] = {s: float(S[s][:, 0].mean() - S[s][:, 1 + best].mean()) for s in scenes}
    res["leave_one_out"] = {s: dict(zip(("gap", "best"), (lambda gg: (float(gg.min()), enm[int(gg.argmin())]))(
        gaps([S[o] for o in scenes if o != s])[0]))) for s in scenes} if len(scenes) > 1 else {}
    res["per_seed"] = {k: dict(zip(("gap", "best"), (lambda gg: (float(gg.min()), enm[int(gg.argmin())]))(
        gaps([per_seed[k][s] for s in scenes])[0]))) for k in seeds}
    refit = {}
    for v in enm:                                                # seed 0: ENM variant vs the same without refit
        plain = v.replace(" + ENM", "")
        if not all(plain in data[0][s] for s in scenes):
            continue
        d = []
        for s in scenes:
            ks = [t for t in keys[s] if t in data[0][s][plain][0]]
            d.append(np.array([data[0][s][v][0][t] - data[0][s][plain][0][t] for t in ks]))
        eff = float(np.mean([x.mean() for x in d]))
        bs = np.mean([x[rng.integers(0, len(x), (2000, len(x)))].mean(1) for x in d], 0)
        refit[v] = dict(effect=eff, ci=np.percentile(bs, [2.5, 97.5]).tolist())
    res["refit_effect"] = refit
    res["decision"] = dict(gap=res["gap_best"], passes=bool(res["gap_best"] >= TARGET_A),
                           target_excluded=bool(max(res["ci_selected_stratified"][1], res["ci_selected_two_level"][1])
                                                < TARGET_A))
    return res


def report_a(r, feat):
    f2 = lambda x: f"{x:+.2f}"
    ci = lambda c: f"[{f2(c[0])}, {f2(c[1])}]"
    missing = sorted(set(CAMBRIDGE) - set(r["scenes"]))
    L = ["## Kill test A: 6pt+P3P vs the best re-fitted mean-point variant (AUC@10)", "",
         f"{len(r['scenes'])}/5 Cambridge scenes" + (f" (MISSING {', '.join(missing)})" if missing else "") +
         f", {feat}, {len(r['seeds'])} run(s) (RANSAC seeds {', '.join(map(str, r['seeds']))}), triplets per scene "
         + ", ".join(f"{s} {n}" for s, n in r["n_triplets"].items()) + ". Rows from crashed tasks (counted as "
         "failures): " + (", ".join(f"{m} {c}" for m, c in r["crashed_rows"].items() if c) or "none") + ".", "",
         "| method | AUC@10 | gap to 6p3v | 95 % CI (stratified) |", "|---|---|---|---|",
         f"| 6p3v | {r['auc']['6p3v']:.2f} | | |"]
    for v in r["gap"]:
        L.append(f"| {v} | {r['auc'][v]:.2f} | {f2(r['gap'][v])} | {ci(r['ci_variant_stratified'][v])} |")
    d = r["decision"]
    L += ["", f"- Best re-fitted variant: {r['best']}; gap {f2(r['gap_best'])} AUC@10.",
          f"- 95 % CI with the best re-selected in each replicate: stratified {ci(r['ci_selected_stratified'])}, "
          f"two-level {ci(r['ci_selected_two_level'])}; keeping {r['best']} fixed: "
          f"{ci(r['ci_fixed_best_stratified'])}.",
          f"- Share of bootstrap replicates with gap >= {TARGET_A}: stratified "
          f"{100 * r['share_gap_ge_target']['stratified']:.1f} %, two-level {100 * r['share_gap_ge_target']['two_level']:.1f} %.",
          "- Gap per scene: " + ", ".join(f"{s} {f2(x)}" for s, x in r["per_scene_gap_best"].items()) + ".",
          "- Leaving one scene out: " + ", ".join(f"without {s} {f2(x['gap'])}" for s, x in r["leave_one_out"].items())
          + ".",
          "- Per run: " + ", ".join(f"seed {k} {f2(x['gap'])} ({x['best']})" for k, x in r["per_seed"].items()) + ".",
          "- Refit effect (re-fitted minus the same variant without the refit, seed 0): " + (", ".join(
              f"{v} {f2(x['effect'])} {ci(x['ci'])}" for v, x in r["refit_effect"].items()) or "no plain rows") + ".",
          "", f"KILL TEST A ({len(r['seeds'])} run(s)): 6p3v - best re-fitted = {f2(d['gap'])} AUC@10 (needs >= "
              f"+{TARGET_A}), 95 % CI {ci(r['ci_selected_stratified'])} -> {'PASS' if d['passes'] else 'FAIL'}"
              + (" (target outside the 95 % intervals)" if d["target_excluded"] and not d["passes"] else "")
              + (" (incomplete: not all scenes)" if missing else "")]
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--killb", nargs="*", default=[], help="kill test B shard files (.jsonl) or folders of them")
    ap.add_argument("--results", type=Path, help="eval_f.py results folder (kill test A)")
    ap.add_argument("--feat", default="triplets-features_superpoint_800_2048-LG")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True, help="output prefix (.md and .json)")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    out, lines = {}, ["# Kill test statistics", ""]
    if args.killb:
        out["kill_test_B"] = kill_b(args.killb, args.boot, rng)
        lines += report_b(out["kill_test_B"]) + [""]
    if args.results:
        a = kill_a(args.results, args.feat, args.boot, rng)
        if a is None:
            lines += ["## Kill test A", "", "No 6p3v and '+ ENM' results for the same scenes yet.", ""]
        else:
            out["kill_test_A"] = a
            lines += report_a(a, args.feat) + [""]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{args.out}.json").write_text(json.dumps(out, indent=1, default=float))
    Path(f"{args.out}.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
