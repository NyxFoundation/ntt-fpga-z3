#!/usr/bin/env python3
"""
Reproduces the missing per-stage halving in the released radix-2 INTT
butterfly (cfntt_ref/hardware_code_radix-2/compact_bf.v), and validates the
PE0-style fix.

Background (see verify_radix2.py for the full formal verification):
  * The paper folds a *1/2 scale into EVERY INTT stage (CFNTT, TCHES 2022,
    Sec 3.2/3.3, Eq. 23, Algorithm 3), and the reference model
    (model_code/poly_mult_radix_2.py) applies op21 in every DIF_RN_INTT stage.
  * The radix-4 RTL instantiates modular_half accordingly (PE0.v:48-49,
    PE1.v:46-47, PE2.v:56/74, PE3.v:66-67).
  * The radix-2 RTL ships modular_half.v but instantiates it NOWHERE:
    compact_bf.v in INTT mode (sel=1) computes (u+v, (v-u)*w) with no
    halving, and there is no N^-1 correction in top_poly_mul.v or in the
    twiddle ROM (tf_ROM.v == w_rom[1..1023] entry-for-entry, proven in
    verify_radix2.py check H).

This script drives BIT-EXACT integer models of the released Verilog
datapaths (modular_add.v, modular_substraction.v, modular_mul.v,
modular_half.v — each proven equivalent to the mod-q arithmetic in
verify_radix2.py) through the full N=1024 INTT, reading twiddles from the
REAL tf_ROM.v contents at the REAL tf_address_generator.v addresses, and
shows:

  released butterfly:   INTT(NTT(x)) == 2^10 * x  (mod q)   for every x tried
  PE0-style patched:    INTT(NTT(x)) == x                   for every x tried

(The 2^10 factor is exact: the released INTT butterfly is linear and equals
2x the model butterfly on both outputs, so 10 stages compound to 2^10.)

Prints "BUG REPRODUCED + FIX VALIDATED" and exits 0 iff both hold exactly.
"""

import os
import re
import sys
import random

Q = 12289
Q0 = 0x5553          # modular_mul.v parameter q0 = 15'h5553
N = 1024
LOGN = 10

_REPO = os.path.dirname(os.path.abspath(__file__))
_CFNTT = os.path.join(_REPO, "cfntt_ref")


def _load_tf_rom():
    rom_v = os.path.join(_CFNTT, "hardware_code_radix-2", "tf_ROM.v")
    if not os.path.exists(rom_v):
        print("FAIL: cfntt_ref submodule missing — run "
              "`git submodule update --init` first")
        sys.exit(1)
    with open(rom_v) as fh:
        entries = {int(a): int(v) for a, v in
                   re.findall(r"10'd(\d+):\s*Q\s*<=\s*14'd(\d+);", fh.read())}
    return [entries[a] for a in sorted(entries)]


TF_ROM = _load_tf_rom()                       # the RTL's 1023-entry ROM


# ---------------------------------------------------------------------------
# Bit-exact integer models of the released Verilog datapaths (each proven
# == the corresponding mod-q operation in verify_radix2.py).
# ---------------------------------------------------------------------------
def add_rtl(x, y):
    """modular_add.v: {c,s}=x+y; {b,d}=s-M; sel=~((~c)&b); z=sel?d:s"""
    s15 = (x + y) & 0x7FFF
    c = (s15 >> 14) & 1
    s = s15 & 0x3FFF
    d15 = (s - Q) & 0x7FFF
    b = (d15 >> 14) & 1
    d = d15 & 0x3FFF
    sel = 1 - ((1 - c) & b)
    return d if sel == 1 else s


def sub_rtl(x, y):
    """modular_substraction.v: {b,d}=x-y; q=b?M:0; {c,z}=d+q"""
    d15 = (x - y) & 0x7FFF
    b = (d15 >> 14) & 1
    d = d15 & 0x3FFF
    return (d + (Q if b == 1 else 0)) & 0x3FFF


def mul_rtl(a, b):
    """modular_mul.v: pre-truncated Barrett, 15-bit remainder truncation,
    one conditional subtraction (exact wire widths)."""
    z = (a * b) & ((1 << 28) - 1)
    z_shift = (z >> 13) & 0x7FFF
    mul2 = (z_shift * Q0) & ((1 << 29) - 1)
    t = (mul2 >> 15) & 0x3FFF
    mul3 = (t * Q) & ((1 << 28) - 1)
    sub = (z - mul3) & ((1 << 28) - 1)
    sub_low = sub & 0x7FFF
    diff = (sub_low - Q) & 0x7FFF
    sign = (diff >> 14) & 1
    return (sub_low & 0x3FFF) if sign == 1 else (diff & 0x3FFF)


def half_rtl(x):
    """modular_half.v: x_sh=x>>1; {c,s}=x_sh+M_half; y=x[0]?s:x_sh"""
    x_sh = x >> 1
    s = (x_sh + 6145) & 0x3FFF
    return s if (x & 1) == 1 else x_sh


# ---------------------------------------------------------------------------
# The radix-2 INTT butterfly, two variants.
# ---------------------------------------------------------------------------
def bf_intt_released(u, v, w):
    """compact_bf.v, sel=1, AS RELEASED: (u+v, (v-u)*w) — no halving.
    (Routing and operand order proven against the netlist in
    verify_radix2.py check I.)"""
    return add_rtl(u, v), mul_rtl(sub_rtl(v, u), w)


def bf_intt_patched(u, v, w):
    """The PE0-style fix: modular_half on both sel=1 outputs (PE0.v:48-49
    applies half1 to the add path and half2 to the multiplier path).
    Both are combinational — no latency/cycle change."""
    return half_rtl(add_rtl(u, v)), half_rtl(mul_rtl(sub_rtl(v, u), w))


# ---------------------------------------------------------------------------
# Full DIF-RN INTT over the RTL dataflow: model loop structure with the
# REAL tf_ROM contents at the REAL tf_address_generator.v addresses
# (INTT mode address = (2^(10-p)-2) - k, proven == the model's r-counter - 1
# in verify_radix2.py check G).
# ---------------------------------------------------------------------------
def intt_hw(a, bf):
    a = a[:]
    for p in range(LOGN):                     # stage log-J = p
        J = 1 << p
        for k in range(N // (2 * J)):
            w = TF_ROM[((1 << (LOGN - p)) - 2) - k] if p != 9 else TF_ROM[k]
            for j in range(J):
                lo = k * 2 * J + j
                hi = lo + J
                a[lo], a[hi] = bf(a[lo], a[hi], w)
    return a


# ---------------------------------------------------------------------------
# Forward NTT: the reference model's DIT_NR_NTT with w_rom = [1] + tf_ROM
# (tf_ROM.v == w_rom[1..1023] is proven entry-for-entry in verify_radix2.py;
# the butterfly arithmetic equivalence to compact_bf.v sel=0 is check I).
# ---------------------------------------------------------------------------
def ntt(a):
    w_rom = [1] + TF_ROM
    a = a[:]
    r = 1
    for p in range(LOGN - 1, -1, -1):
        J = 1 << p
        for k in range(N // (2 * J)):
            w = w_rom[r]
            r += 1
            for j in range(J):
                lo = k * 2 * J + j
                hi = lo + J
                u = a[lo] % Q
                t = (a[hi] * w) % Q
                a[lo] = (u + t) % Q
                a[hi] = (u - t) % Q
    return a


def main():
    rng = random.Random(0)
    vecs = [
        [1] + [0] * (N - 1),                  # e_0
        [0] * (N - 1) + [1],                  # e_{N-1}
        [1] * N,                              # all ones
        [i % Q for i in range(N)],            # ramp
    ]
    for _ in range(6):
        vecs.append([rng.randrange(Q) for _ in range(N)])

    scale = pow(2, LOGN, Q)                   # 1024
    for vi, x in enumerate(vecs):
        y = ntt(x)
        got_released = intt_hw(y, bf_intt_released)
        want_scaled = [(scale * c) % Q for c in x]
        if got_released != want_scaled:
            print("FAIL: released butterfly on v_%d is NOT exactly 2^10-scaled "
                  "(unexpected — check the datapath models)" % vi)
            sys.exit(1)
        if got_released == [c % Q for c in x]:
            print("FAIL: released butterfly round-trips v_%d exactly — "
                  "no bug present?!" % vi)
            sys.exit(1)
        got_patched = intt_hw(y, bf_intt_patched)
        if got_patched != [c % Q for c in x]:
            print("FAIL: PE0-style patched butterfly does NOT round-trip v_%d" % vi)
            sys.exit(1)

    print("released radix-2 INTT butterfly: INTT(NTT(x)) == 2^10 * x (mod q) "
          "on all %d vectors   [BUG REPRODUCED]" % len(vecs))
    print("PE0-style patched butterfly:     INTT(NTT(x)) == x "
          "on all %d vectors                [FIX VALIDATED]" % len(vecs))
    print("BUG REPRODUCED + FIX VALIDATED")
    sys.exit(0)


if __name__ == "__main__":
    main()
