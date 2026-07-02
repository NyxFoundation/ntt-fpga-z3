#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "z3-solver",
# ]
# ///
"""
Non-vacuity harness for verify_radix2.py: a formal check that passes on the
real RTL is only meaningful if it FAILS on a wrong one.

Each mutation below injects a realistic bug into a copy of verify_radix2.py's
RTL model (never into the golden/spec side) and asserts that the verification
catches it with a "FAIL" verdict and exit code 1:

  M1  wrong Barrett constant        q0 = 0x5553 -> 0x5552       (modular_mul.v)
  M2  swapped INTT sub operands     sub(v,u) -> sub(u,v)        (compact_bf.v)
  M3  one corrupted tf_ROM entry    RTL_TF_ROM[17] += 1         (tf_ROM.v)
  M4  wrong address stride          (k << (p+1)) -> (k << p)    (address_generator.v)

Prints "ALL MUTATIONS DETECTED" and exits 0 iff every mutant is killed.
"""

import os
import subprocess
import sys
import tempfile

_REPO = os.path.dirname(os.path.abspath(__file__))
_VERIFY = os.path.join(_REPO, "verify_radix2.py")

MUTATIONS = [
    (
        "M1 wrong Barrett constant (q0 = 0x5552)",
        "Q0 = 0x5553",
        "Q0 = 0x5552",
        "modular_mul_rtl",
    ),
    (
        "M2 swapped INTT subtraction operands (u-v instead of v-u)",
        "mult_a == zsub_gate(v, u))      # (v-u), operand order!",
        "mult_a == zsub_gate(u, v))",
        "compact_bf_routing",
    ),
    (
        "M3 one corrupted tf_ROM entry (RTL_TF_ROM[17] += 1)",
        "SRC_W_ROM, RTL_TF_ROM = _load_ground_truth()",
        "SRC_W_ROM, RTL_TF_ROM = _load_ground_truth()\n"
        "RTL_TF_ROM[17] = (RTL_TF_ROM[17] + 1) % Q",
        "rom tables",
    ),
    (
        "M4 wrong address-generator stride ((k<<p)+i instead of ((k<<1)<<p)+i)",
        "wide = (k << (p + 1)) + i",
        "wide = (k << p) + i",
        "address_generator",
    ),
]


def main():
    src = open(_VERIFY).read()
    failures = []
    for label, old, new, expect in MUTATIONS:
        if src.count(old) != 1:
            print("FAIL: harness: mutation target for %r occurs %d times"
                  % (label, src.count(old)))
            sys.exit(1)
        mutant = src.replace(old, new)
        # keep the mutant next to verify_radix2.py so the submodule resolves
        with tempfile.NamedTemporaryFile(
                "w", suffix=".py", dir=_REPO, delete=False) as fh:
            fh.write(mutant)
            path = fh.name
        try:
            r = subprocess.run([sys.executable, path],
                               capture_output=True, text=True, timeout=300)
        finally:
            os.unlink(path)
        killed = (r.returncode == 1 and "FAIL" in r.stdout
                  and expect in r.stdout)
        verdict = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(no output)"
        print("%s  %s\n    -> %s" % ("ok " if killed else "MISSED", label, verdict))
        if not killed:
            failures.append(label)
    if failures:
        print("FAIL: %d mutation(s) survived: %s" % (len(failures), failures))
        sys.exit(1)
    print("ALL MUTATIONS DETECTED")
    sys.exit(0)


if __name__ == "__main__":
    main()
