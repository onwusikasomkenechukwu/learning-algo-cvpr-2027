"""Print requirements from a lock file with environment markers resolved for a target Python.

pip download --python-version still evaluates markers against the host interpreter,
so build_wheelhouse.sh resolves them per target version with this script first.
Usage: python scripts/resolve_markers.py 3.14 requirements.lock
"""
import sys

from pip._vendor.packaging.requirements import Requirement

version, lock = sys.argv[1], sys.argv[2]
env = {"python_version": version, "python_full_version": version + ".0"}
for line in open(lock):
    line = line.split("#")[0].strip()
    if not line:
        continue
    req = Requirement(line)
    if req.marker is None or req.marker.evaluate(env):
        print(f"{req.name}{req.specifier}")
