"""Build an offline apt repository of Ubuntu .debs for machines without internet.

Resolves the full Depends/Pre-Depends closure (no Recommends) of seed packages against the
Ubuntu archive indexes, downloads the .debs, and writes a flat-repo Packages index, so the
target installs with apt's normal resolver (which never downgrades and skips what is installed):

  echo "deb [trusted=yes] file:$PWD/apt-bundle ./" | sudo tee /etc/apt/sources.list.d/offline.list
  sudo apt update -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/offline.list -o Dir::Etc::sourceparts=-
  sudo apt install --no-install-recommends <seeds>

Packages from a source can be pinned to an older version fetched from Launchpad (--pin), which is
needed when prebuilt kernel modules require an exact driver version that the mirror no longer has.

Usage:
  python scripts/build_apt_bundle.py plan     --seeds-file seeds.txt [--pin SRC=VERSION ...]
  python scripts/build_apt_bundle.py download --seeds-file seeds.txt [--pin ...] --out <dir>
Seeds file: one package per line; "# group: name" lines start a size group in the plan.
"""
import argparse
import hashlib
import json
import lzma
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

MIRROR = "http://archive.ubuntu.com/ubuntu"  # replaced by --snapshot
SUITES = ("resolute", "resolute-updates", "resolute-security")
COMPONENTS = ("main", "restricted", "universe", "multiverse")


# ---------- Debian version comparison (dpkg semantics) ----------
def _order(c):
    if c.isdigit():
        return 0
    if c.isalpha():
        return ord(c)
    return 0 if c == "" else (-1 if c == "~" else ord(c) + 256)


def _cmp_part(a, b):
    while a or b:
        na = re.match(r"^[^\d]*", a).group(); nb = re.match(r"^[^\d]*", b).group()
        a, b = a[len(na):], b[len(nb):]
        for i in range(max(len(na), len(nb))):
            ca = _order(na[i]) if i < len(na) else 0
            cb = _order(nb[i]) if i < len(nb) else 0
            if ca != cb:
                return ca - cb
        da = re.match(r"^\d*", a).group(); db = re.match(r"^\d*", b).group()
        a, b = a[len(da):], b[len(db):]
        if int(da or 0) != int(db or 0):
            return int(da or 0) - int(db or 0)
    return 0


def vercmp(a, b):
    def split(v):
        e, _, r = v.partition(":") if ":" in v else ("0", "", v)
        up, _, rev = r.rpartition("-") if "-" in r else (r, "", "0")
        return int(e), up, rev
    ea, ua, ra = split(a); eb, ub, rb = split(b)
    return (ea - eb) or _cmp_part(ua, ub) or _cmp_part(ra, rb)


def satisfies(ver, op, want):
    c = vercmp(ver, want)
    return {"=": c == 0, ">=": c >= 0, "<=": c <= 0, ">>": c > 0, "<<": c < 0}[op]


# ---------- index ----------
def load_index(cache, mirror):
    cache.mkdir(parents=True, exist_ok=True)
    pk, prov = defaultdict(list), defaultdict(list)
    for s in SUITES:
        for c in COMPONENTS:
            f = cache / f"{s}__{c}.xz"
            if not f.exists():
                urllib.request.urlretrieve(f"{mirror}/dists/{s}/{c}/binary-amd64/Packages.xz", f)
            for block in lzma.open(f, "rt", encoding="utf-8").read().split("\n\n"):
                d, key = {}, None
                for line in block.splitlines():
                    if line.startswith(" ") and key:
                        d[key] += "\n" + line
                    elif ":" in line:
                        key, v = line.split(":", 1); d[key] = v.strip()
                if "Package" not in d:
                    continue
                d["_raw"] = block.strip()
                pk[d["Package"]].append(d)
                for p in filter(None, (x.strip() for x in d.get("Provides", "").split(","))):
                    m = re.match(r"([^\s(]+)\s*(?:\(=\s*([^)]+)\))?", p)
                    prov[m.group(1)].append((d, m.group(2)))
    return pk, prov


def parse_rel(field):
    groups = []
    for grp in filter(None, (g.strip() for g in field.split(","))):
        alts = []
        for alt in grp.split("|"):
            m = re.match(r"\s*([^\s(:\[<]+)(?::\w+)?\s*(?:\(\s*([<>=]+)\s*([^)]+)\))?", alt)
            alts.append((m.group(1), m.group(2), (m.group(3) or "").strip() or None))
        groups.append(alts)
    return groups


class Resolver:
    def __init__(self, pk, prov, pins, assumed=()):
        self.pk, self.prov, self.pins = pk, prov, pins  # pins: {source: version}
        self.assumed = set(assumed)  # already on the target; never bundled
        self.chosen = {}

    def source(self, d):
        return d.get("Source", d["Package"]).split()[0]

    def candidates(self, name, op=None, want=None):
        out = []
        for d in self.pk.get(name, []):
            pinned = self.pins.get(self.source(d))
            if pinned:  # pinned sources: take the newest metadata but report the pinned version
                out.append(dict(d, Version=pinned, _pinned=True))
            elif op is None or satisfies(d["Version"], op, want):
                out.append(d)
        if op is None or not out:
            for d, pv in self.prov.get(name, []):
                if op is None or (pv and satisfies(pv, op, want)):
                    out.append(d)
        return list({(d["Package"], d["Version"]): d for d in out}.values())

    def best(self, name, op=None, want=None):
        cands = self.candidates(name, op, want)
        if not cands:
            return None
        for d in cands:  # already chosen wins
            if d["Package"] in self.chosen:
                return self.chosen[d["Package"]]
        real = [d for d in cands if d["Package"] == name] or cands
        top = real[0]
        for d in real[1:]:
            if vercmp(d["Version"], top["Version"]) > 0:
                top = d
        return top

    def add(self, name, why, missing):
        todo = [(name, None, None, why)]
        while todo:
            n, op, want, why = todo.pop()
            if n in self.assumed:
                continue
            d = self.best(n, op, want)
            if d is None:
                missing.append(f"{n} ({op} {want}) needed by {why}"); continue
            if d["Package"] in self.chosen:
                continue
            self.chosen[d["Package"]] = d
            for field in ("Pre-Depends", "Depends"):
                for alts in parse_rel(d.get(field, "")):
                    pick = None
                    for an, aop, aw in alts:
                        sibling = self.pk.get(an) and self.source(self.pk[an][0]) in self.pins
                        if d.get("_pinned") and sibling:
                            aop = aw = None  # sibling of a pinned source: versions move together
                        if self.best(an, aop, aw) is not None:
                            pick = (an, aop, aw); break
                    if pick is None:
                        missing.append(f"{alts} needed by {d['Package']}"); continue
                    todo.append((*pick, d["Package"]))


def launchpad_url(pkg, version):
    q = urllib.parse.urlencode({"ws.op": "getPublishedBinaries", "binary_name": pkg, "exact_match": "true",
                                "version": version,
                                "distro_arch_series": "https://api.launchpad.net/devel/ubuntu/resolute/amd64"})
    entries = json.load(urllib.request.urlopen(f"https://api.launchpad.net/devel/ubuntu/+archive/primary?{q}",
                                               timeout=60))["entries"]
    if not entries:
        raise RuntimeError(f"Launchpad has no {pkg} {version} for resolute/amd64")
    urls = json.load(urllib.request.urlopen(entries[0]["self_link"] + "?ws.op=binaryFileUrls", timeout=60))
    return next(u for u in urls if u.endswith(".deb"))


def read_seeds(path):
    groups, cur = {}, "default"
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line.startswith("# group:"):
            cur = line.split(":", 1)[1].strip(); groups.setdefault(cur, [])
        elif line and not line.startswith("#"):
            groups.setdefault(cur, []).append(line)
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "download"])
    ap.add_argument("--seeds-file", required=True)
    ap.add_argument("--snapshot", help="resolve against snapshot.ubuntu.com at this time, e.g. 20260825T000000Z, "
                    "to match a machine that was last updated then (exact libc, kernel-module and driver versions)")
    ap.add_argument("--pin", action="append", default=[], help="SOURCE=VERSION (fetched from Launchpad)")
    ap.add_argument("--cache", default=str(Path(__file__).resolve().parent.parent / ".apt-index-cache"))
    ap.add_argument("--assume-installed", nargs="*", default=[], help="packages already on the target")
    ap.add_argument("--out")
    args = ap.parse_args()
    pins = dict(p.split("=", 1) for p in args.pin)
    mirror = f"https://snapshot.ubuntu.com/ubuntu/{args.snapshot}" if args.snapshot else MIRROR
    pk, prov = load_index(Path(args.cache) / (args.snapshot or "current"), mirror)
    groups = read_seeds(args.seeds_file)

    res, missing, group_of = Resolver(pk, prov, pins, args.assume_installed), [], {}
    for g, seeds in groups.items():
        before = set(res.chosen)
        for s in seeds:
            res.add(s, f"seed:{g}", missing)
        for n in set(res.chosen) - before:
            group_of[n] = g
    total = 0
    for g in groups:
        names = [n for n in res.chosen if group_of[n] == g]
        size = sum(int(res.chosen[n].get("Size", 0)) for n in names)
        total += size
        print(f"{g:28s} {len(names):4d} packages  {size / 1e6:8.1f} MB (pinned versions sized from newest metadata)")
    print(f"{'TOTAL':28s} {len(res.chosen):4d} packages  {total / 1e6:8.1f} MB")
    if missing:
        print("UNRESOLVED:", *sorted(set(missing))[:20], sep="\n  ")
    if args.cmd == "plan":
        return
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    index = []
    for n in sorted(res.chosen):
        d = res.chosen[n]
        if d.get("_pinned"):
            url = launchpad_url(n, d["Version"])
        else:
            url = f"{mirror}/{d['Filename']}"
        dest = out / url.rsplit("/", 1)[1]
        if not dest.exists():
            urllib.request.urlretrieve(url, dest)
        data = dest.read_bytes()
        if not d.get("_pinned") and hashlib.sha256(data).hexdigest() != d["SHA256"]:
            raise RuntimeError(f"sha256 mismatch for {dest.name}")
        index.append((d, dest, data))
        print(f"ok {dest.name}", flush=True)
    # Flat-repo Packages index built from each .deb's own control file (correct for pinned versions too).
    import io
    import tarfile
    stanzas = []
    for d, dest, data in index:
        control = deb_control(data)
        stanzas.append(control.rstrip("\n") + f"\nFilename: ./{dest.name}\nSize: {len(data)}\n"
                       f"SHA256: {hashlib.sha256(data).hexdigest()}\n")
    (out / "Packages").write_text("\n".join(stanzas))
    print(f"wrote {out / 'Packages'} ({len(stanzas)} packages)")


def deb_control(data):
    """Extract the control file text from a .deb (ar archive with control.tar.{xz,zst,gz})."""
    import io
    import tarfile
    pos = 8
    while pos < len(data):
        name = data[pos:pos + 16].decode().strip().rstrip("/")
        size = int(data[pos + 48:pos + 58].decode().strip())
        body = data[pos + 60:pos + 60 + size]
        pos += 60 + size + (size % 2)
        if name.startswith("control.tar"):
            if name.endswith(".zst"):  # Ubuntu's default; stdlib on Python >= 3.14, else pip zstandard
                try:
                    from compression import zstd
                    body = zstd.decompress(body)
                except ImportError:
                    import zstandard
                    body = zstandard.ZstdDecompressor().decompress(body, max_output_size=50_000_000)
                mode = "r:"
            else:
                mode = "r:*"
            with tarfile.open(fileobj=io.BytesIO(body), mode=mode) as t:
                for m in t.getmembers():
                    if m.name.lstrip("./") == "control":
                        return t.extractfile(m).read().decode()
    raise RuntimeError("no control file in .deb")


if __name__ == "__main__":
    sys.exit(main())
