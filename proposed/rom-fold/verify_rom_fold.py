#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "z3-solver",
# ]
# ///
"""
z3 proof of the fold7 datapath (tf_rom_fold.v) at EXACT RTL widths, over the
FULL domain x < q:

    t0 = (x<<3) - x                    17-bit, == 7x exactly (no wrap)
    t1 = t0 >= 4q ? t0 - 4q : t0
    t2 = t1 >= 2q ? t1 - 2q : t1
    t3 = t2 >=  q ? t2 -  q : t2

Obligations (divider-free — subtracted amounts are explicit multiples of q):
  (1) t0 == 7x as integers (the shift-sub never wraps 17 bits for x < q)
  (2) 7x == t3 + q*(4*s1 + 2*s2 + s3)  where s_i are the mux conditions
      — so t3 ≡ 7x (mod q) by construction, machine-checked
  (3) t3 < q — fully reduced
Together: t3 == 7x mod q for every x < q.

Prints "VERIFIED" / exit 0 iff all obligations are proven (negation UNSAT).
"""

import sys

try:
    from z3 import BitVec, BitVecVal, If, UGE, ULT, And, Not, Then, unsat, sat
except Exception as exc:
    print("FAIL: z3 unavailable (%r)" % (exc,))
    sys.exit(1)

Q = 12289


def prove(name, constraints):
    s = Then('simplify', 'bit-blast', 'smt').solver()
    s.add(*constraints)
    r = s.check()
    if r == unsat:
        return True, ""
    if r == sat:
        return False, "%s: violating model %s" % (name, s.model())
    return False, "%s: z3 returned 'unknown'" % name


def main():
    W = 20
    x = BitVec('x', W)
    q = BitVecVal(Q, W)
    pre = ULT(x, q)

    t0 = (x << 3) - x
    s1 = UGE(t0, BitVecVal(4 * Q, W))
    t1 = If(s1, t0 - BitVecVal(4 * Q, W), t0)
    s2 = UGE(t1, BitVecVal(2 * Q, W))
    t2 = If(s2, t1 - BitVecVal(2 * Q, W), t1)
    s3 = UGE(t2, q)
    t3 = If(s3, t2 - q, t2)

    subtracted = (If(s1, BitVecVal(4, W), BitVecVal(0, W))
                  + If(s2, BitVecVal(2, W), BitVecVal(0, W))
                  + If(s3, BitVecVal(1, W), BitVecVal(0, W))) * q

    checks = [
        ("fold7: t0 == 7x, fits 17 bits (no wrap)",
         [pre, Not(And(t0 == BitVecVal(7, W) * x,
                       ULT(t0, BitVecVal(1 << 17, W))))]),
        ("fold7 congruence: 7x == t3 + q*(4s1+2s2+s3)",
         [pre, BitVecVal(7, W) * x != t3 + subtracted]),
        ("fold7 reduced: t3 < q",
         [pre, Not(ULT(t3, q))]),
    ]
    for name, cons in checks:
        ok, msg = prove(name, cons)
        if not ok:
            print("FAIL: %s" % msg)
            sys.exit(1)
        sys.stderr.write("ok  %s\n" % name)

    print("VERIFIED")
    sys.exit(0)


if __name__ == "__main__":
    main()
