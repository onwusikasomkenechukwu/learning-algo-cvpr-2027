"""Replay one eval_f.py task that crashed inside poselib (saved by scripts/eval_f_safe.py) in isolation, to
find where and why it crashes.

Prints what the task holds (experiment, image names, array shapes, non-finite or duplicate points), then runs
eval_f.eval_experiment on it with faulthandler on, so a fault prints the Python stack. With --gdb it re-runs
itself under gdb in batch mode and prints the native backtrace (the poselib function that faults).

  cd third_party/threeview
  python ../../scripts/poselib_crash_repro.py --gdb $CRASH_DIR/item_123.pkl
"""
import argparse
import faulthandler
import os
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_f_safe import describe, load_eval_f  # noqa: E402


def inspect(item):
    print("task:", describe(item))
    items = item if isinstance(item, (tuple, list)) else [item]
    for k, x in enumerate(items):
        if isinstance(x, np.ndarray):
            line = f"  [{k}] array {x.shape} {x.dtype}"
            if x.dtype.kind == "f":
                line += f", non-finite {int((~np.isfinite(x)).sum())}"
                if x.ndim == 2 and len(x):
                    line += f", duplicate rows {len(x) - len(np.unique(x, axis=0))}"
                    line += f", min {np.nanmin(x, axis=0).round(2).tolist()} max {np.nanmax(x, axis=0).round(2).tolist()}"
            print(line)
        elif isinstance(x, dict):
            print(f"  [{k}] dict keys {sorted(map(str, x))[:12]}")
        else:
            print(f"  [{k}] {type(x).__name__}: {str(x)[:120]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item", help="item_<index>.pkl written by eval_f_safe.py")
    ap.add_argument("--threeview", default=".", help="threeview checkout (eval_f.py, res/)")
    ap.add_argument("--gdb", action="store_true", help="re-run under gdb and print the native backtrace")
    args = ap.parse_args()
    if args.gdb:
        gdb = shutil.which("gdb")
        if gdb is None:
            sys.exit("gdb not found (sudo apt install gdb), run without --gdb for the Python stack only")
        cmd = [gdb, "-batch", "-ex", "set pagination off", "-ex", "run", "-ex", "bt 25",
               "-ex", "info sharedlibrary poselib", "--args", sys.executable, "-X", "faulthandler",
               os.path.abspath(__file__), "--threeview", args.threeview, args.item]
        sys.exit(subprocess.call(cmd))
    faulthandler.enable()
    with open(args.item, "rb") as fh:
        item = pickle.load(fh)
    inspect(item)
    mod = load_eval_f(args.threeview)
    print("running eval_f.eval_experiment ...", flush=True)
    r = mod.eval_experiment(item)
    print("finished without a crash this time:", {k: v for k, v in r.items() if k.endswith("_err")}
          if isinstance(r, dict) else type(r))


if __name__ == "__main__":
    main()
