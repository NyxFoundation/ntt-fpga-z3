#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
The psi-fold twiddle ROM — bit-exact validation.

Found by VISUAL review of the 3D architecture model: after the K-RED
redesign shrank the arithmetic, the 1023-word twiddle ROM is the largest
block left on the logic floorplan, while the fold stages next to it show
that shift-add constant multiplies are nearly free, and the op21 gate on
the ROM output shows the "derive another twiddle from the same stored
word" pattern already paying off once.  Combining those observations:

  THEOREM (bit-reversed negacyclic layout, psi = kesai = 7):
      w_rom[512 + j] == 7 * w_rom[j]   (mod q)      for all j < 512
  and recursively per halving level (fold chains, still multiplier-free):
      w_rom[256 + j] == 49 * w_rom[j]  == fold7(fold7(.))   for j < 256
      w_rom[128 + j] == 7^4 * w_rom[j] == fold7 x4          for j < 128

  so the ROM stores HALF the words (or a quarter, ...) and derives the
  rest with fold7(x) = 7x mod q = (x<<3) - x + three conditional
  subtractions — shifts and adds only.  This composes with the KRED
  9^-1-scaled contents because constant scalings commute.

Validates against the REAL tf_ROM.v contents (submodule, never
transcribed): the fold relations at levels 1-3, fold7 exhaustively over
the full domain, the composition with 9^-1, and end-to-end
INTT(NTT(x)) == x with 512-word and 256-word ROMs.

Prints "ROM-FOLD MATH VALIDATED" and exits 0 iff everything matches.
"""

import os
import re
import sys
import random

Q = 12289
INV9 = pow(9, -1, Q)
N, LOGN = 1024, 10

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_w():
    rom_v = os.path.join(_HERE, "..", "..", "cfntt_ref",
                         "hardware_code_radix-2", "tf_ROM.v")
    if not os.path.exists(rom_v):
        print("FAIL: cfntt_ref submodule missing")
        sys.exit(1)
    with open(rom_v) as fh:
        entries = {int(a): int(v) for a, v in
                   re.findall(r"10'd(\d+):\s*Q\s*<=\s*14'd(\d+);", fh.read())}
    return [1] + [entries[a] for a in sorted(entries)]


W = load_w()


def fold7(x):
    t = (x << 3) - x
    if t >= 4 * Q:
        t -= 4 * Q
    if t >= 2 * Q:
        t -= 2 * Q
    if t >= Q:
        t -= Q
    return t


def kred9(c):
    c0, c1 = c & 0xFFF, c >> 12
    d = 3 * c0 + 6 * Q - c1
    d0, d1 = d & 0xFFF, d >> 12
    e = 3 * d0 + Q - d1
    return e - Q if e >= Q else e


def op21(a):
    return (a >> 1) if a % 2 == 0 else (a >> 1) + (Q + 1) // 2


def make_transforms(W_scaled):
    def ntt(a):
        a = a[:]
        r = 1
        for p in range(LOGN - 1, -1, -1):
            J = 1 << p
            for k in range(N // (2 * J)):
                Wv = W_scaled(r)
                r += 1
                for j in range(J):
                    lo, hi = k * 2 * J + j, k * 2 * J + j + J
                    t = kred9(a[hi] * Wv)
                    a[lo], a[hi] = (a[lo] + t) % Q, (a[lo] - t) % Q
        return a

    def intt(a):
        a = a[:]
        r = 1023
        for i in range(LOGN):
            J = 1 << i
            for k in range(N // (2 * J)):
                Wv = W_scaled(r)
                r -= 1
                for j in range(J):
                    lo, hi = k * 2 * J + j, k * 2 * J + j + J
                    u, v = a[lo], a[hi]
                    a[lo] = op21((u + v) % Q)
                    a[hi] = kred9(((v - u) % Q) * op21(Wv))
        return a

    return ntt, intt


def main():
    # fold relations, levels 1-3, ALL pairs, against the REAL table
    for level, half in ((1, 512), (2, 256), (3, 128)):
        mul = pow(7, 1 << (level - 1), Q)
        if not all(W[half + j] == (mul * W[j]) % Q for j in range(half)):
            print("FAIL: fold relation broken at level %d" % level)
            sys.exit(1)

    # fold7 == 7x mod q, EXHAUSTIVE over the full domain
    for x in range(Q):
        if fold7(x) != (7 * x) % Q:
            print("FAIL: fold7(%d) wrong" % x)
            sys.exit(1)

    # composition with the KRED 9^-1 scaling
    if not all((INV9 * W[512 + j]) % Q == fold7((INV9 * W[j]) % Q)
               for j in range(512)):
        print("FAIL: fold does not commute with 9^-1 scaling")
        sys.exit(1)

    # end-to-end round-trips with the halved and quartered ROMs
    ROM512 = [(INV9 * W[j]) % Q for j in range(512)]
    ROM256 = ROM512[:256]

    def w512(i):
        return ROM512[i] if i < 512 else fold7(ROM512[i - 512])

    def w256(i):
        # w[b9*512 + b8*256 + j] = 7^b9 * 49^b8 * w[j]
        # -> fold7 applied b9 + 2*b8 times on the stored word
        base = ROM256[i & 255]
        for _ in range((1 if i & 512 else 0) + (2 if i & 256 else 0)):
            base = fold7(base)
        return base

    rng = random.Random(0)
    for w_scaled in (w512, w256):
        ntt, intt = make_transforms(w_scaled)
        for _ in range(2):
            x = [rng.randrange(Q) for _ in range(N)]
            if intt(ntt(x)) != x:
                print("FAIL: roundtrip broken (%s)" % w_scaled.__name__)
                sys.exit(1)

    print("fold levels 1-3 vs REAL tf_ROM.v: OK; fold7 exhaustive: OK;")
    print("9^-1 composition: OK; e2e roundtrip with 512- and 256-word ROMs: OK")
    print("ROM bits: 14322 -> 7168 (-50%) or 3584 (-75%)")
    print("ROM-FOLD MATH VALIDATED")
    sys.exit(0)


if __name__ == "__main__":
    main()
