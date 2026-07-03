#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "z3-solver",
# ]
# ///
"""
Formal verification of the proposed K-RED reduction datapath (kred9) for
q = 12289 = 3*2^12 + 1, at EXACT hardware widths, over the FULL input domain.

The unit reduces a 28-bit product c to 9c mod q using ONLY shifts and adds
(3x = (x<<1)+x; the offsets 6q and q are constants):

    c  = c1*2^12 + c0                    c < 2^28  (any product a*b, a,b < q)
    d  = 3*c0 + 6q - c1                  ≡ 3c (mod q)   [3*2^12 ≡ -1 (mod q)]
    e  = 3*d0 + q - d1                   ≡ 3d ≡ 9c (mod q),  d = d1*2^12 + d0
    r  = e - q if e >= q else e

Proof obligations, each for EVERY c < 2^28 (z3 / QF_BV, constant mults only):
  (1) no underflow / no overflow at the declared widths:
        0 < d < 2^17   (so d fits a 17-bit wire and the 6q offset suffices)
        0 < e < 2q     (so ONE conditional subtraction fully reduces)
  (2) r == (9c) mod q  and  r < q.

The correctness of using 9c-mod-q (instead of c mod q) in the butterfly is a
SEPARATE, pure-math fact validated end-to-end in kred_math/e2e: the ROM stores
9^-1-scaled twiddles, so 9*(v * 9^-1 w) == v*w exactly; the PWM double-pass
uses the stored constant 81^-1.

Prints "VERIFIED" / exit 0 iff every obligation is proven (negation UNSAT).
"""

import sys

try:
    from z3 import (
        BitVec, BitVecVal, Extract, ZeroExt, LShR, URem, ULT, ULE, UGE, If,
        And, Not, Then, unsat, sat,
    )
except Exception as exc:
    print("FAIL: z3 unavailable (%r)" % (exc,))
    sys.exit(1)

Q = 12289


def _solver():
    return Then('simplify', 'bit-blast', 'smt').solver()


def prove(name, constraints):
    s = _solver()
    s.add(*constraints)
    r = s.check()
    if r == unsat:
        return True, ""
    if r == sat:
        return False, "%s: violating model %s" % (name, s.model())
    return False, "%s: z3 returned 'unknown'" % name


def main():
    W = 32                                  # compute width (values < 2^28+eps)
    c = BitVec('c', W)
    q = BitVecVal(Q, W)
    pre = ULT(c, BitVecVal(1 << 28, W))     # full 28-bit domain

    c0 = c & BitVecVal(0xFFF, W)
    c1 = LShR(c, 12)                        # < 2^16
    d = BitVecVal(3, W) * c0 + BitVecVal(6 * Q, W) - c1
    d0 = d & BitVecVal(0xFFF, W)
    d1 = LShR(d, 12)
    e = BitVecVal(3, W) * d0 + q - d1
    r = If(UGE(e, q), e - q, e)

    # Congruence WITHOUT any divider: two nonnegative linear identities pin
    # d and e to 3c and 9c modulo q, then r < q finishes the proof.
    #   3c + 6q == d + c1*q      (since 3*2^12*c1 == (q-1)*c1)
    #   3d +  q == e + d1*q
    # so 9c == 3(3c) == 3d == e == r (mod q), and r < q  =>  r == 9c mod q.
    checks = [
        ("kred9 width: 0 < d < 2^17",
         [pre, Not(And(ULT(BitVecVal(0, W), d),
                       ULT(d, BitVecVal(1 << 17, W))))]),
        ("kred9 width: 0 < e < 2q (one cond. subtract suffices)",
         [pre, Not(And(ULT(BitVecVal(0, W), e),
                       ULT(e, BitVecVal(2 * Q, W))))]),
        ("kred9 congruence: 3c + 6q == d + c1*q",
         [pre, BitVecVal(3, W) * c + BitVecVal(6 * Q, W) != d + c1 * q]),
        ("kred9 congruence: 3d + q == e + d1*q",
         [pre, BitVecVal(3, W) * d + q != e + d1 * q]),
        ("kred9 output: r == e or e-q, exactly the reduced residue",
         [pre, Not(And(ULT(r, q),
                       If(UGE(e, q), r == e - q, r == e)))]),
    ]
    for name, cons in checks:
        ok, msg = prove(name, cons)
        if not ok:
            print("FAIL: %s" % msg)
            sys.exit(1)
        sys.stderr.write("ok  %s\n" % name)

    # sanity: the folded constants used by the architecture
    if (9 * pow(9, -1, Q)) % Q != 1 or (81 * pow(81, -1, Q)) % Q != 1:
        print("FAIL: inverse constants wrong")
        sys.exit(1)
    if (3 * (1 << 12)) % Q != Q - 1:
        print("FAIL: q is not 3*2^12+1 — K-RED inapplicable")
        sys.exit(1)
    sys.stderr.write("ok  folded constants (9^-1=2731, 81^-1=11227) verified\n")

    print("VERIFIED")
    sys.exit(0)


if __name__ == "__main__":
    main()
