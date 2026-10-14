"""Recompute summary.json for a results folder from its per-scene CSVs.

Used after run_cluster.sh, where each node evaluated a subset of scenes and
wrote a partial summary. Usage: python scripts/merge_results.py results/test/poselib_th1_r0.8
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eval_relpose import summarize  # noqa: E402

for run_dir in map(Path, sys.argv[1:]):
    summary = {"scenes": {}}
    all_rows = []
    for path in sorted(run_dir.glob("*.csv")):
        with open(path) as f:
            rows = [{k: (v if k == "pair" else float(v)) for k, v in r.items()} for r in csv.DictReader(f)]
        summary["scenes"][path.stem] = summarize(rows)
        all_rows += rows
    summary["all"] = s = summarize(all_rows)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"{run_dir}: {len(summary['scenes'])} scenes, {s['pairs']} pairs, "
          f"mAA@10={s['mAA@10']:.4f} AUC@5/10/20={s['AUC@5']:.4f}/{s['AUC@10']:.4f}/{s['AUC@20']:.4f}")
