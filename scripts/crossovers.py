"""Task 2.8 steps 5-6 (student instructions v5): predicted crossover inlier ratios from the cost model of draft v4
Sec. 5, written to a dated predictions file before any low-inlier run.

Model (draft Eqs. 3-4). With a = fraction of tracks correct in views 1-2 and b = fraction of those correct in
view 3 (w = ab), the probability that a sample succeeds is
  6pt+P3P     q_6 = a^6 b^3 s_6
  4p3vf(M)    q_M = a^4 b^3 s_M                      (seeds only)
  ours        q_O = a^4 b^3 [s_M + b (1 - s_M) s_E]   (seeds plus endpoints)
  sequential  stage 1 needs 1 / (a^6 s_6) samples and stage 2 1 / b^3 (P3P on clean points always succeeds)
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


def per_sample_ms(results_dir, scene, feature, experiment, tag=""):
    p = Path(results_dir) / f"focal_{scene}{tag}-{feature}.json"
    if not p.exists():
        return None
    rows = [r for r in json.loads(p.read_text()) if r["experiment"] == experiment and not r.get("crashed")]
    it = np.mean([r["info"]["iterations"] for r in rows]) if rows else 0
    return float(np.mean([r["info"]["runtime"] for r in rows]) / it) if it else None


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
    Tseq = p["tseq"] * (1 / (a ** 6 * p["s6"]) + 1 / b ** 3) if p["tseq"] else np.full_like(a, np.nan)
    return dict(T6=T6, TM=TM, TO=TO, Tseq=Tseq)


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
    p = dict(s6=src["s_6"], sM=src["s_M"], sE=src["s_E"] or 0.0)
    t6 = per_sample_ms(args.results, args.scene, args.feature, "6p3v") if args.results else None
    tM = per_sample_ms(args.results, args.scene, args.feature, "4p3v(M)") if args.results else None
    tseq = per_sample_ms(args.results, args.scene, args.feature, "6p3v + SEQ", "-seq") if args.results else None
    track = args.track_ms if args.track_ms is not None else (sr["python_ms"]["track"] or 0.0)
    missing = [k for k, v in dict(t6=t6, tM=tM).items() if v is None]
    if missing:
        raise SystemExit(f"no eval_f.py per-sample time for {missing} on {args.scene} in {args.results}")
    p.update(t6=t6, tM=tM, tO=tM + track, tseq=tseq)
    mix = None
    if args.outliers and args.outliers.exists():
        summ = json.loads(args.outliers.read_text())
        mix = next(iter(summ.values()))["mixture_tuning_sift"]
        if mix.get("whole") is None:
            mix = None
    kinds = ["whole-track", "view-3", "single-view"] + (["measured mixture"] if mix else [])
    w = np.linspace(0.02, 1.0, 491)
    pred = dict(date=datetime.date.today().isoformat(), inputs=p, rates=args.rates, track_ms=track,
                success_file=str(args.success), mixture=mix, crossovers={})
    lines = [f"# Predicted crossovers, {pred['date']} (Task 2.8, written before any low-inlier run)", "",
             f"Inputs: s_6 = {p['s6']:.3f}, s_M = {p['sM']:.3f}, s_E = {p['sE']:.3f} ({args.rates} samples, "
             f"{args.success.name}); per-sample ms: 6pt+P3P {t6:.4f}, 4p3vf(M) {tM:.4f}, ours {p['tO']:.4f} "
             f"(tracking {track:.3f}), sequential {tseq if tseq is None else round(tseq, 4)}."
             + (" No tracking time was measured (no sample tracked), so ours = 4p3vf(M) cost per sample."
                if args.track_ms is None and not track else ""), ""]
    if mix:
        lines.append("Measured outlier mixture (" + ", ".join(f"{k} {v:.2f}" for k, v in mix.items()
                                                          if isinstance(v, float)) + ").")
        lines.append("")
    lines += ["| Outlier type | vs 6pt+P3P | vs 4p3vf(M) | vs sequential |", "|---|---|---|---|"]
    for kind in kinds:
        a, b = ab(kind, w, mix)
        T = times(a, b, p)
        row = {}
        for name, key in (("6pt+P3P", "T6"), ("4p3vf(M)", "TM"), ("sequential", "Tseq")):
            ratio = T["TO"] / T[key]
            if not np.isfinite(ratio).any():
                row[name] = "not measured"
                continue
            c = crossings(w, ratio)
            if c:
                row[name] = ", ".join(f"w = {x:.3f}" for x in c) + \
                    f" (ours faster {'below' if ratio[0] < 1 else 'above'})"
            else:
                row[name] = f"none: ours {'faster' if np.nanmedian(ratio) < 1 else 'slower'} everywhere " \
                            f"(T_ours/T_base {np.nanmin(ratio):.2f}-{np.nanmax(ratio):.2f})"
        pred["crossovers"][kind] = row
        lines.append(f"| {kind} | {row['6pt+P3P']} | {row['4p3vf(M)']} | {row['sequential']} |")
    lines += ["", "w* by the closed form for whole-track outliers against 6pt+P3P (draft Sec. 5): "
              f"{np.sqrt((p['sM'] + (1 - p['sM']) * p['sE']) * t6 / (p['s6'] * p['tO'])):.3f} "
              "(no crossover in (0, 1] when it is >= 1)."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{args.out}.json").write_text(json.dumps(pred, indent=1))
    Path(f"{args.out}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
