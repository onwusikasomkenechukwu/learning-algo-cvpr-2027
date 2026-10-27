"""Check the correct-root tool against a full solve (student instructions v5, Task 2.3 step 7 and Task 2.4 step 5).

Full solve: every root of the 4p3vf system at a generic complex parameter pA, found by monodromy and saved by
  python src/check_fourp3vf.py --only monodromy --instances 1 --save --out <dir>      (-> <dir>/monodromy_0.npz)
is tracked to the sample's observed coordinates along a straight line with a random complex gamma (one gamma per
sample, the gamma trick), which reaches every isolated root of the target with probability one.

Per sample: the correct-root tool of src/homotopy_proto.py (five complex paths from the ground truth at
noise-free coordinates) gives ok / ambiguous / not_real; the full solve gives the endpoints that finish, the
distinct ones, the real ones and those passing the acceptance checks (residual, omega > 0, focal range, positive
depths, class (+,+)). Checks: the tool's root is one of the full-solve roots; and it is the accepted real root
with the smallest pose error to the ground truth (if not, a different exact root lies closer to the truth).
The number of accepted real roots is the number of wrong roots of the right class a tracker could end at.

  python src/full_solve_check.py --start <dir>/monodromy_0.npz --mode random --n 50 --noise 1 --out results/full_solve/random
  python src/full_solve_check.py --start <dir>/monodromy_0.npz --mode triplets --scene <triplets>/KingsCollege \
      --nvm <cambridge>/KingsCollege/reconstruction.nvm --n 50 --out results/full_solve/KingsCollege
"""
import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import fourp3vf as M
from homotopy_proto import S, check_endpoint, correct_root, parameter_homotopy, practical, track

_start = {}


def _init(path):
    d = np.load(path)
    _start.update(pA=d["pA"], sols=d["sols"])


def full_solve(x, rng):
    gamma = np.exp(2j * np.pi * rng.uniform())
    H = parameter_homotopy(_start["pA"], x.astype(complex), gamma)
    ends, failed = [], 0
    for z0 in _start["sols"]:
        r = track(H, z0.astype(complex))
        if r["ok"] and np.isfinite(r["z"]).all():
            ends.append(r["z"])
        else:
            failed += 1
    distinct = []
    for z in ends:
        if all(np.linalg.norm(z - w) > 1e-6 * (1 + np.linalg.norm(w)) for w in distinct):
            distinct.append(z)
    real = [z.real for z in distinct if np.abs(z.imag).max() <= S["ref_real"] * (1 + np.linalg.norm(z))]
    return dict(n_start=len(_start["sols"]), finished=len(ends), failed=failed, distinct=len(distinct)), real


def check(job):
    inst, seed = job
    rng = np.random.default_rng(seed)
    t0 = time.time()
    ref = correct_root(inst, rng)
    counts, real = full_solve(inst["x"], rng)
    acc = [z for z in real if check_endpoint(z, inst["x"])[0]]
    row = dict(names=inst.get("names"), noise_px=inst.get("noise_px"), ref=ref["status"], **counts,
               real=len(real), accepted_real=len(acc))
    if ref["status"] == "ok":
        zc = ref["z"]
        d = [np.linalg.norm(z - zc) / (1 + np.linalg.norm(zc)) for z in real]
        row["tool_in_full_solve"] = bool(d and min(d) <= S["match_tol"])
        row["tool_dist_to_nearest"] = float(min(d)) if d else None
        errs = []
        for z in acc:
            p, rerr, ferr = practical(z, inst["x"], inst)
            errs.append((rerr if rerr is not None else np.inf) + 100 * (ferr if ferr is not None else np.inf))
        if acc:
            best = acc[int(np.argmin(errs))]
            row["tool_is_closest_accepted"] = bool(np.linalg.norm(best - zc) <= S["match_tol"] * (1 + np.linalg.norm(zc)))
            row["tool_accepted"] = bool(check_endpoint(zc, inst["x"])[0])
    row["seconds"] = time.time() - t0
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="monodromy_<i>.npz from check_fourp3vf.py --save")
    ap.add_argument("--mode", choices=["random", "triplets"], default="random")
    ap.add_argument("--scene")
    ap.add_argument("--nvm")
    ap.add_argument("--feature", default="triplets-features_superpoint_800_2048-LG")
    ap.add_argument("--theta", type=float, default=2.0)
    ap.add_argument("--noise", type=float, default=1.0, help="--mode random: pixel noise at 800 px")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--nproc", type=int, default=1)
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = np.random.default_rng(args.rng)
    scene = M.TripletScene(args.scene, args.feature, args.theta, 0, 1, nvm=args.nvm) if args.mode == "triplets" else None
    jobs = []
    for k in range(args.n):
        try:
            inst = scene.instance(rng, "real", 1.0) if scene else M.random_instance(rng, args.noise, 1.0)
        except StopIteration:
            break
        jobs.append((inst, args.rng * 100003 + k))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Pool(args.nproc, initializer=_init, initargs=(args.start,)) as pool, open(f"{out}.jsonl", "w") as fh:
        rows = []
        for row in pool.imap(check, jobs):
            rows.append(row)
            fh.write(json.dumps(row, default=float) + "\n")
            fh.flush()
    ok = [r for r in rows if r["ref"] == "ok"]

    def share(key, rs):
        v = [r[key] for r in rs if r.get(key) is not None]
        return (float(np.mean(v)), len(v)) if v else (None, 0)

    summ = dict(args=vars(args), samples=len(rows), ref={s: sum(r["ref"] == s for r in rows) for s in
                                                         ("ok", "ambiguous", "not_real")},
                start_roots=rows[0]["n_start"] if rows else None,
                finished_median=float(np.median([r["finished"] for r in rows])) if rows else None,
                distinct_median=float(np.median([r["distinct"] for r in rows])) if rows else None,
                real_median=float(np.median([r["real"] for r in rows])) if rows else None,
                accepted_real_median=float(np.median([r["accepted_real"] for r in rows])) if rows else None,
                tool_in_full_solve=share("tool_in_full_solve", ok),
                tool_is_closest_accepted=share("tool_is_closest_accepted", ok),
                tool_accepted=share("tool_accepted", ok),
                seconds_median=float(np.median([r["seconds"] for r in rows])) if rows else None)
    Path(f"{out}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, default=float))


if __name__ == "__main__":
    main()
