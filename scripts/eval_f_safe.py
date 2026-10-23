"""Run threeview's eval_f.py (or eval.py, with EVAL_SCRIPT=eval.py) unchanged, but with a worker pool that
survives crashes inside poselib.

On abl-dell the PoseLib fork dies with general protection faults on some Great Court / St Mary's triplets
(kernel log 2026-10-23). eval_f.py's multiprocessing.Pool then waits forever for the dead worker's result.
This wrapper loads eval_f.py from the current folder (the threeview checkout), replaces its Pool with
SafePool and calls its eval(parse_args()) with the same command line.

SafePool.imap hands each worker one task at a time over its own pipe, so when a worker dies the task it held
is known. That task is retried once in a fresh worker; if it crashes again it is
  - pickled to $EVALF_CRASH_DIR/item_<index>.pkl and logged to $EVALF_CRASH_DIR/crashes.jsonl
    (experiment, image names, match count, exit code) for scripts/poselib_crash_repro.py, and
  - returned as a failed estimate: a copy of a finished result of the same experiment with every '*_err'
    value set to NaN (the tables count NaN as 180 degrees) and 'crashed': True, so positions still pair
    between experiments and the results file is written.
A Python exception in a task is handled the same way (Pool would have aborted the whole run).

  cd third_party/threeview && EVALF_CRASH_DIR=/tmp/crashes python ../../scripts/eval_f_safe.py -nw 94 FEATURE SCENE_DIR
"""
import copy
import importlib.util
import json
import math
import multiprocessing as mp
import os
import pickle
import sys
import time
import traceback
from multiprocessing.connection import wait
from pathlib import Path


def _worker(conn, func):
    while True:
        msg = conn.recv()
        if msg is None:
            return
        i, item = msg
        try:
            conn.send(("ok", i, func(item)))
        except Exception:
            conn.send(("err", i, traceback.format_exc()))


def describe(item):
    """Experiment label, image names and match count found in an eval_f.py task tuple (best effort)."""
    out = dict(experiment=None, strings=[], n_points=None)
    items = item if isinstance(item, (tuple, list)) else [item]
    for x in items:
        if isinstance(x, str):
            if out["experiment"] is None and ("p3v" in x or "p(" in x or "6p" in x):
                out["experiment"] = x
            else:
                out["strings"].append(x)
        elif hasattr(x, "shape") and out["n_points"] is None and len(getattr(x, "shape", ())) == 2:
            out["n_points"] = int(x.shape[0])
    return out


class SafePool:
    retries = 1

    def __init__(self, processes=None, *args, **kwargs):
        self.n = processes or os.cpu_count()
        self.crash_dir = Path(os.environ.get("EVALF_CRASH_DIR", "crashes"))
        # fork as eval_f.py's Pool does on Linux; EVALF_MP_CONTEXT=spawn for testing where fork is missing
        self.ctx = mp.get_context(os.environ.get("EVALF_MP_CONTEXT", "fork"))

    def _start(self, func):
        parent, child = self.ctx.Pipe()
        p = self.ctx.Process(target=_worker, args=(child, func), daemon=True)
        p.start()
        child.close()
        return dict(proc=p, conn=parent, task=None)

    def imap(self, func, iterable, chunksize=1):
        items = iter(iterable)
        results, failed, tries, pending = {}, {}, {}, []
        workers = [self._start(func) for _ in range(self.n)]
        exhausted = False
        total = 0

        def next_task():
            nonlocal exhausted, total
            if pending:
                return pending.pop()
            if exhausted:
                return None
            try:
                item = next(items)
            except StopIteration:
                exhausted = True
                return None
            total += 1
            return total - 1, item

        def feed(w):
            t = next_task()
            w["task"] = t
            if t is not None:
                try:
                    w["conn"].send(t)
                except (BrokenPipeError, OSError):   # the worker died meanwhile: its sentinel reports it
                    pass
            return t is not None

        busy = [w for w in workers if feed(w)]
        idle = [w for w in workers if w["task"] is None]
        while busy:
            ready = wait([w["conn"] for w in busy] + [w["proc"].sentinel for w in busy], timeout=30)
            for w in list(busy):
                msg = None
                if w["conn"] in ready:
                    try:
                        msg = w["conn"].recv()
                    except (EOFError, OSError):
                        msg = None
                if msg is not None:
                    kind, i, payload = msg
                    if kind == "ok":
                        results[i] = payload
                    else:
                        self._failed(failed, w["task"], f"python exception:\n{payload}")
                    if not feed(w):
                        busy.remove(w)
                        idle.append(w)
                    continue
                if w["proc"].sentinel in ready or not w["proc"].is_alive():
                    w["proc"].join(1)
                    code = w["proc"].exitcode
                    i, item = w["task"]
                    tries[i] = tries.get(i, 0) + 1
                    print(f"[eval_f_safe] worker died (exit {code}) on task {i}, try {tries[i]}: "
                          f"{describe(item)}", file=sys.stderr, flush=True)
                    if tries[i] <= self.retries:
                        pending.append((i, item))
                    else:
                        self._failed(failed, (i, item), f"worker crashed, exit code {code}")
                    busy.remove(w)
                    nw = self._start(func)
                    workers.append(nw)
                    if feed(nw):
                        busy.append(nw)
                    else:
                        idle.append(nw)
                    # an idle worker can take a requeued task
                    while pending and idle:
                        iw = idle.pop()
                        if feed(iw):
                            busy.append(iw)
                        else:
                            idle.append(iw)
                            break
        for w in workers:
            if w["proc"].is_alive():
                try:
                    w["conn"].send(None)
                except (BrokenPipeError, OSError):
                    pass
        for w in workers:
            w["proc"].join(5)
        self._fill(results, failed)
        if failed:
            print(f"[eval_f_safe] {len(failed)} of {total} tasks failed (see {self.crash_dir}/crashes.jsonl)",
                  file=sys.stderr, flush=True)
        for i in range(total):
            if i in results:
                yield results[i]

    def _failed(self, failed, task, why):
        i, item = task
        self.crash_dir.mkdir(parents=True, exist_ok=True)
        path = self.crash_dir / f"item_{i}.pkl"
        try:
            with open(path, "wb") as fh:
                pickle.dump(item, fh)
        except Exception as e:                       # unpicklable: still log it
            path = f"not saved: {e!r}"
        rec = dict(index=i, why=why.splitlines()[-1][:300], item=str(path), time=time.strftime("%F %T"),
                   **describe(item))
        with open(self.crash_dir / "crashes.jsonl", "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        failed[i] = rec

    @staticmethod
    def _fill(results, failed):
        """Failed tasks become failed estimates of their experiment (NaN errors = 180 degrees in the tables)."""
        template = {}
        for r in results.values():
            if isinstance(r, dict) and "experiment" in r:
                template.setdefault(r["experiment"], r)
        for i, rec in failed.items():
            t = template.get(rec["experiment"])
            if t is None:
                print(f"[eval_f_safe] no finished result of {rec['experiment']!r} to copy; task {i} dropped",
                      file=sys.stderr)
                continue
            r = copy.deepcopy(t)
            for k in r:
                if k.endswith("_err"):
                    r[k] = math.nan
            r["crashed"] = True
            for k, name in zip(("img1", "img2", "img3"), rec["strings"]):   # eval_f.py task: img1, img2, img3
                if k in r:
                    r[k] = name
            results[i] = r

    def close(self):
        pass

    def join(self):
        pass

    def terminate(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def load_eval_f(threeview=".", script=None):
    """Load threeview's eval_f.py (or $EVAL_SCRIPT, e.g. eval.py: same structure) as a module."""
    script = script or os.environ.get("EVAL_SCRIPT", "eval_f.py")
    tv = Path(threeview).resolve()
    sys.path.insert(0, str(tv))
    name = Path(script).stem
    spec = importlib.util.spec_from_file_location(name, tv / script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                           # pickling of module-level functions by name
    spec.loader.exec_module(mod)
    return mod


def main():
    mod = load_eval_f(".")
    mod.Pool = SafePool
    sys.argv = [os.environ.get("EVAL_SCRIPT", "eval_f.py")] + sys.argv[1:]
    mod.eval(mod.parse_args())


if __name__ == "__main__":
    main()
