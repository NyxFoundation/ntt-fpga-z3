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

    t = (x<<3) - x                     17-bit, == 7x exactly (no wrap)
    m = floor(7x/q) in 0..6            six constant comparators (parallel)
    r = t - m*q                        single subtraction

Obligations (divider-free — m*q is an explicit multiple of q):
  (1) t == 7x as integers (the shift-sub never wraps 17 bits for x < q)
  (2) the comparator ladder computes m = floor(t/q), i.e. m*q <= t < (m+1)*q
  (3) r == t - m*q < q  — fully reduced
Together: r ≡ 7x (mod q) and r < q, so r == 7x mod q for every x < q.

Prints "VERIFIED" / exit 0 iff all obligations are proven (negation UNSAT).
"""

import sys

try:
    from z3 import BitVec, BitVecVal, If, UGE, ULE, ULT, And, Not, Then, unsat, sat
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

    t = (x << 3) - x
    # m = priority ladder (6q down to q); matches the RTL conditional chain
    mq = If(UGE(t, BitVecVal(6 * Q, W)), BitVecVal(6 * Q, W),
          If(UGE(t, BitVecVal(5 * Q, W)), BitVecVal(5 * Q, W),
           If(UGE(t, BitVecVal(4 * Q, W)), BitVecVal(4 * Q, W),
            If(UGE(t, BitVecVal(3 * Q, W)), BitVecVal(3 * Q, W),
             If(UGE(t, BitVecVal(2 * Q, W)), BitVecVal(2 * Q, W),
              If(UGE(t, q), q, BitVecVal(0, W)))))))
    r = t - mq

    checks = [
        ("fold7: t == 7x, fits 17 bits (no wrap)",
         [pre, Not(And(t == BitVecVal(7, W) * x,
                       ULT(t, BitVecVal(1 << 17, W))))]),
        ("fold7: mq == floor(t/q)*q, i.e. mq <= t < mq+q",
         [pre, Not(And(ULE(mq, t), ULT(t, mq + q)))]),
        ("fold7 reduced: r == t - mq < q",
         [pre, Not(And(r == t - mq, ULT(r, q)))]),
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
