#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
The proposed CFNTT-KRED butterfly — bit-exact reference model and end-to-end
validation against the negacyclic-convolution golden.

Idea (see ../README / proposed/README.md):
  * q = 12289 = 3*2^12 + 1 is a Proth prime, so 3*2^12 == -1 (mod q) and a
    product can be reduced MULTIPLIER-FREE by two K-RED folds
    (Longa & Naehrig 2016 use this in software for the same q; the reference
    RTL instead spends TWO extra hardware multipliers on Barrett).
  * The unit returns 9ab mod q; the spurious factor 9 is folded into the
    twiddle ROM (store W = 9^-1 * w), so every butterfly multiply is EXACT.
  * INTT twiddles are derived from the SAME ROM by one op21 (x2^-1) on the
    ROM output: 9*(t-u)*(op21(W)) == ((t-u)*w)/2 — which simultaneously
    FUSES the per-stage halving of the multiply path, fixing upstream
    issue #7 at zero extra multiplier cost.  The add path uses one op21
    gate (shift+add), as the paper always intended.
  * PWM (both operands are data) double-passes the same unit with the
    stored constant 81^-1: 9*(9xy)*81^-1 == xy.

Validates, bit-exactly in plain ints:
  - kred9(c) == 9c mod q on edges + a dense random sample (the FULL-domain
    proof is z3, in verify_kred.py)
  - INTT(NTT(x)) == x on the REAL tf_ROM.v contents (9^-1-scaled)
  - INTT(PWM(NTT(a),NTT(b))) == negacyclic(a,b)

Prints "PROPOSAL MATH VALIDATED" and exits 0 iff everything matches.
"""

import os
import re
import sys
import random

Q = 12289
INV9 = pow(9, -1, Q)      # 2731
INV81 = pow(81, -1, Q)    # 11227
N, LOGN = 1024, 10

_REPO = os.path.dirname(os.path.abspath(__file__))


def kred9(c):
    """r ≡ 9c (mod q), 0 <= r < q, for any 0 <= c < 2^28 — shifts/adds only."""
    c0, c1 = c & 0xFFF, c >> 12
    d = 3 * c0 + 6 * Q - c1              # ≡ 3c ; 0 < d < 2^17   (z3-proven)
    d0, d1 = d & 0xFFF, d >> 12
    e = 3 * d0 + Q - d1                  # ≡ 9c ; 0 < e < 2q     (z3-proven)
    return e - Q if e >= Q else e


def mult_kred(a, b):
    """The proposed unit: ONE integer multiplier + kred9. Returns 9ab mod q."""
    return kred9(a * b)


def op21(a):
    return (a >> 1) if a % 2 == 0 else (a >> 1) + (Q + 1) // 2


def load_w_rom():
    rom_v = os.path.join(_REPO, "..", "..", "cfntt_ref",
                         "hardware_code_radix-2", "tf_ROM.v")
    if not os.path.exists(rom_v):
        print("FAIL: cfntt_ref submodule missing")
        sys.exit(1)
    with open(rom_v) as fh:
        entries = {int(a): int(v) for a, v in
                   re.findall(r"10'd(\d+):\s*Q\s*<=\s*14'd(\d+);", fh.read())}
    tf = [entries[a] for a in sorted(entries)]
    return [(INV9 * w) % Q for w in [1] + tf]      # the PROPOSED ROM contents


W_ROM = load_w_rom()


def ntt_bf(u, v, W):
    t = mult_kred(v, W)                  # == v*w exactly (W = 9^-1 w)
    return (u + t) % Q, (u - t) % Q


def intt_bf(u, v, W):
    # halving on the mult path fused into op21(W); add path via op21 gate
    return op21((u + v) % Q), mult_kred((v - u) % Q, op21(W))


def ntt(a):
    a = a[:]
    r = 1
    for p in range(LOGN - 1, -1, -1):
        J = 1 << p
        for k in range(N // (2 * J)):
            W = W_ROM[r]
            r += 1
            for j in range(J):
                lo, hi = k * 2 * J + j, k * 2 * J + j + J
                a[lo], a[hi] = ntt_bf(a[lo], a[hi], W)
    return a


def intt(a):
    a = a[:]
    r = len(W_ROM) - 1
    for i in range(LOGN):
        J = 1 << i
        for k in range(N // (2 * J)):
            W = W_ROM[r]
            r -= 1
            for j in range(J):
                lo, hi = k * 2 * J + j, k * 2 * J + j + J
                a[lo], a[hi] = intt_bf(a[lo], a[hi], W)
    return a


def pwm(x, y):
    return [mult_kred(mult_kred(a, b), INV81) for a, b in zip(x, y)]


def negacyclic(a, b):
    c = [0] * N
    for i in range(N):
        ai = a[i]
        if ai:
            for j in range(N):
                k = i + j
                v = ai * b[j]
                if k >= N:
                    k -= N
                    v = -v
                c[k] = (c[k] + v) % Q
    return c


def main():
    rng = random.Random(0)

    edges = [0, 1, 0xFFF, 0x1000, Q - 1, Q, 2 * Q, (Q - 1) ** 2,
             (1 << 28) - 1, 1 << 27, (1 << 16) - 1]
    for c in edges + [rng.randrange(1 << 28) for _ in range(500_000)]:
        if kred9(c) != (9 * c) % Q:
            print("FAIL: kred9(%d) wrong" % c)
            sys.exit(1)

    vecs = [[1] + [0] * (N - 1), [i % Q for i in range(N)]] + \
           [[rng.randrange(Q) for _ in range(N)] for _ in range(4)]
    for x in vecs:
        if intt(ntt(x)) != x:
            print("FAIL: roundtrip broken")
            sys.exit(1)

    for _ in range(2):
        a = [rng.randrange(Q) for _ in range(N)]
        b = [0] * N
        for _ in range(8):
            b[rng.randrange(N)] = rng.randrange(Q)
        if intt(pwm(ntt(a), ntt(b))) != negacyclic(a, b):
            print("FAIL: polymult broken")
            sys.exit(1)

    print("kred9 edges+500k OK; INTT(NTT(x))==x; polymult==negacyclic")
    print("PROPOSAL MATH VALIDATED")
    sys.exit(0)


if __name__ == "__main__":
    main()
