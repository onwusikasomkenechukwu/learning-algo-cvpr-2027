"""Task 2.8 steps 5-6 (student instructions v5): predicted crossover inlier ratios from the cost model of draft v4
Sec. 5, written to a dated predictions file before any low-inlier run.

Model (draft Eqs. 3-4). With a = fraction of tracks correct in views 1-2 and b = fraction of those correct in
view 3 (w = ab), the probability that a sample succeeds is
  6pt+P3P     q_6 = a^6 b^3 s_6
  4p3vf(M)    q_M = a^4 b^3 s_M                      (seeds only)
  ours        q_O = a^4 b^3 [s_M + b (1 - s_M) s_E]   (seeds plus endpoints)
  sequential  stage 1 needs 1 / (a^6 s_seq1) samples and stage 2 1 / (b^3 s_seq2) (measured stage rates; s_6 and 1
              when they are missing)
  refit       4p3vf(M) with the two-view refit: q_R = a^4 b^3 s_R
and the expected time to a first good hypothesis is T_m = t_m / q_m, with t_m = c_m + h_m N c_s the time per
sample (solve plus scoring). t_m comes from eval_f.py runs in C++ on the tuning scene: mean runtime / mean
iterations of '6p3v', '4p3v(M)' and '6p3v + SEQ' (per iteration of either stage). Ours adds the tracking time per
sample (--track-ms; by default the Python prototype's median, an upper bound for C++).

Outlier types map w to (a, b): whole-track (wrong in all views): a = w, b = 1; view-3: a = 1, b = w;
single-view, each view equally often: a = 1 - 2(1 - w)/3, b = w/a; measured mixture (scripts/outlier_stats.py on
the tuning scene's SIFT triplets, 'other' counted as whole-track): a = 1 - (1 - w)(p_whole + p_view1 + p_view2).
A crossover is an inlier ratio where T_ours / T_baseline crosses 1; some pairs have none (against 4p3vf(M) with
whole-track outliers the ratio does not depend on w), and that is written down too.

  python scripts/crossovers.py --success results/task28/success.json --outliers results/task28/summary.json \
      --results third_party/threeview/results --scene courtyard --out results/task28/predictions
"""
import argparse
import datetime
import json
from pathlib import Path

import numpy as np

SP = "triplets-features_superpoint_800_2048-LG"


def _rows(results_dir, scene, feature, experiment, tag=""):
    p = Path(results_dir) / f"focal_{scene}{tag}-{feature}.json"
    if not p.exists():
        return []
    return [r for r in json.loads(p.read_text()) if r["experiment"] == experiment and not r.get("crashed")]


def per_sample_ms(results_dir, scene, feature, experiment, tag=""):
    rows = _rows(results_dir, scene, feature, experiment, tag)
    it = np.mean([r["info"]["iterations"] for r in rows]) if rows else 0
    return float(np.mean([r["info"]["runtime"] for r in rows]) / it) if it else None


def scoring_cost(results_dir, scene, feature, h):
    """Least-squares fit of the time per RANSAC iteration of '6p3v' against the number of matches N over the
    scene's triplets: t = c + slope N. Each iteration scores h hypotheses on N matches, so the scoring cost per
    hypothesis and match is slope / h (an estimate: local optimization runs fold into both terms)."""
    rows = [r for r in _rows(results_dir, scene, feature, "6p3v")
            if r["info"].get("iterations") and r["info"].get("inlier_ratio")]
    if len(rows) < 10 or not h:
        return None
    n = np.array([r["info"]["num_inliers"] / r["info"]["inlier_ratio"] for r in rows])
    t = np.array([r["info"]["runtime"] / r["info"]["iterations"] for r in rows])
    slope, icpt = np.polyfit(n, t, 1)
    return dict(triplets=len(rows), per_iteration_ms_at_N0=float(icpt), ms_per_match=float(slope),
                ms_per_hypothesis_and_match=float(slope / h), median_matches=float(np.median(n)))


def ab(kind, w, mix=None):
    if kind == "whole-track":
        return w, np.ones_like(w)
    if kind == "view-3":
        return np.ones_like(w), w
    if kind == "single-view":
        a = 1 - 2 * (1 - w) / 3
    else:                                      # measured mixture
        wrong12 = mix["whole"] + mix["other"] + mix["view1"] + mix["view2"]
        a = 1 - (1 - w) * wrong12
    return a, w / a


def times(a, b, p):
    T6 = p["t6"] / (a ** 6 * b ** 3 * p["s6"])
    TM = p["tM"] / (a ** 4 * b ** 3 * p["sM"])
    TO = p["tO"] / (a ** 4 * b ** 3 * (p["sM"] + b * (1 - p["sM"]) * p["sE"]))
    # sequential: measured stage success rates when available (stage 2 given a good stage 1), else s_6 and 1
    s1, s2 = p.get("s_seq1") or p["s6"], p.get("s_seq2") or 1.0
    Tseq = p["tseq"] * (1 / (a ** 6 * s1) + 1 / (b ** 3 * s2)) if p["tseq"] else np.full_like(a, np.nan)
    TR = p["tR"] / (a ** 4 * b ** 3 * p["sR"]) if p.get("tR") and p.get("sR") else np.full_like(a, np.nan)
    return dict(T6=T6, TM=TM, TO=TO, Tseq=Tseq, TR=TR)


def crossings(w, ratio):
    """Inlier ratios where ratio (T_ours / T_baseline) crosses 1, by linear interpolation in log space."""
    lr = np.log(ratio)
    out = []
    for i in np.flatnonzero(np.isfinite(lr[:-1]) & np.isfinite(lr[1:]) & (np.sign(lr[:-1]) != np.sign(lr[1:]))):
        out.append(float(w[i] - lr[i] * (w[i + 1] - w[i]) / (lr[i + 1] - lr[i])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--success", type=Path, required=True, help="scripts/success_rates.py output")
    ap.add_argument("--outliers", type=Path, help="scripts/outlier_stats.py summary.json (mixture)")
    ap.add_argument("--results", type=Path, help="eval_f.py results folder (per-sample C++ times)")
    ap.add_argument("--scene", default="courtyard")
    ap.add_argument("--feature", default=SP)
    ap.add_argument("--track-ms", type=float, help="tracking time per sample added to ours (default: prototype)")
    ap.add_argument("--rates", choices=["all", "ceiling"], default="all",
                    help="success rates over all samples, or over those where LO from the reference succeeds")
    ap.add_argument("--out", type=Path, required=True, help="output prefix (.json and .md)")
    args = ap.parse_args()

    sr = json.loads(args.success.read_text())
    src = sr if args.rates == "all" else dict(sr, **sr["given_ceiling"])
    p = dict(s6=src["s_6"], sM=src["s_M"], sE=src["s_E"] or 0.0, sR=src.get("s_R"), s_seq1=src.get("s_seq1"),
             s_seq2=src.get("s_seq2"))
    t6 = per_sample_ms(args.results, args.scene, args.feature, "6p3v") if args.results else None
    tM = per_sample_ms(args.results, args.scene, args.feature, "4p3v(M)") if args.results else None
    tseq = per_sample_ms(args.results, args.scene, args.feature, "6p3v + SEQ", "-seq") if args.results else None
    tR = per_sample_ms(args.results, args.scene, args.feature, "4p3v(M) + ENM", "-killA") if args.results else None
    track = args.track_ms if args.track_ms is not None else (sr["python_ms"]["track"] or 0.0)
    missing = [k for k, v in dict(t6=t6, tM=tM).items() if v is None]
    if missing:
        raise SystemExit(f"no eval_f.py per-sample time for {missing} on {args.scene} in {args.results}")
    p.update(t6=t6, tM=tM, tO=tM + track, tseq=tseq, tR=tR)
    score = scoring_cost(args.results, args.scene, args.feature, sr.get("h_6")) if args.results else None
    mix = None
    if args.outliers and args.outliers.exists():
        summ = json.loads(args.outliers.read_text())
        mix = next(iter(summ.values()))["mixture_tuning_sift"]
        if mix.get("whole") is None:
            mix = None
    kinds = ["whole-track", "view-3", "single-view"] + (["measured mixture"] if mix else [])
    w = np.linspace(0.02, 1.0, 491)
    pred = dict(date=datetime.date.today().isoformat(), inputs=p, rates=args.rates, track_ms=track,
                success_file=str(args.success), mixture=mix, scoring_cost=score, crossovers={})
    f3 = lambda v: "-" if v is None else f"{v:.3f}"
    f4 = lambda v: "not measured" if v is None else f"{v:.4f}"
    lines = [f"# Predicted crossovers, {pred['date']} (Task 2.8, written before any low-inlier run)", "",
             f"Inputs ({args.rates} samples of {args.success.name}; per-sample time c = eval_f.py runtime / RANSAC "
             f"iterations in C++ on {args.scene}):", "",
             "| method | s | c (ms per sample) | h (hypotheses per sample) |", "|---|---|---|---|",
             f"| 6pt+P3P | {f3(p['s6'])} | {f4(t6)} | {f3(sr.get('h_6'))} |",
             f"| 4p3vf(M) | {f3(p['sM'])} | {f4(tM)} | {f3(sr.get('h_M'))} |",
             f"| ours (seeds + endpoints) | s_E = {f3(p['sE'])} | {f4(p['tO'])} (tracking {track:.3f}) | "
             f"{f3(sr.get('h_E'))} endpoints |",
             f"| 4p3vf(M) + two-view refit | {f3(p['sR'])} | {f4(tR)} | {f3(sr.get('h_R'))} |",
             f"| sequential, stage 1 (6pt, views 1-2) | {f3(p['s_seq1'])} | {f4(tseq)} (both stages, per "
             f"iteration) | {f3(sr.get('h_seq1'))} |",
             f"| sequential, stage 2 (P3P, given stage 1) | {f3(p['s_seq2'])} | | {f3(sr.get('h_seq2'))} |", ""]
    if args.track_ms is None and not track:
        lines += ["No tracking time was measured (no sample tracked), so ours = 4p3vf(M) cost per sample.", ""]
    if score:
        lines += [f"Scoring cost: {score['ms_per_hypothesis_and_match'] * 1e6:.1f} ns per hypothesis and match "
                  f"(time per iteration of 6pt+P3P = {score['per_iteration_ms_at_N0']:.4f} ms + "
                  f"{score['ms_per_match'] * 1e6:.1f} ns x N over {score['triplets']} triplets, divided by h_6; "
                  f"median N = {score['median_matches']:.0f}).", ""]
    if mix:
        lines.append("Measured outlier mixture (" + ", ".join(f"{k} {v:.2f}" for k, v in mix.items()
                                                          if isinstance(v, float)) + ").")
        lines.append("")
    pairs = (("ours vs 6pt+P3P", "TO", "T6"), ("ours vs 4p3vf(M)", "TO", "TM"), ("ours vs sequential", "TO", "Tseq"),
             ("refit vs 6pt+P3P", "TR", "T6"), ("refit vs sequential", "TR", "Tseq"))
    lines += ["| Outlier type | " + " | ".join(n for n, _, _ in pairs) + " |", "|---" * (len(pairs) + 1) + "|"]
    for kind in kinds:
        a, b = ab(kind, w, mix)
        T = times(a, b, p)
        row = {}
        for name, num, den in pairs:
            ratio = T[num] / T[den]
            who = name.split(" vs ")[0]
            if not np.isfinite(ratio).any():
                row[name] = "not measured"
                continue
            c = crossings(w, ratio)
            if c:
                row[name] = ", ".join(f"w = {x:.3f}" for x in c) + \
                    f" ({who} faster {'below' if ratio[0] < 1 else 'above'})"
            else:
                row[name] = f"none: {who} {'faster' if np.nanmedian(ratio) < 1 else 'slower'} everywhere " \
                            f"(ratio {np.nanmin(ratio):.2f}-{np.nanmax(ratio):.2f})"
        pred["crossovers"][kind] = row
        lines.append(f"| {kind} | " + " | ".join(row[n] for n, _, _ in pairs) + " |")
    lines += ["", "w* by the closed form for whole-track outliers against 6pt+P3P (draft Sec. 5): "
              f"{np.sqrt((p['sM'] + (1 - p['sM']) * p['sE']) * t6 / (p['s6'] * p['tO'])):.3f} "
              "(no crossover in (0, 1] when it is >= 1)."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{args.out}.json").write_text(json.dumps(pred, indent=1))
    Path(f"{args.out}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
