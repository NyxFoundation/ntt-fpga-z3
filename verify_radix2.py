#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "z3-solver",
# ]
# ///
"""
Formal verification of the CFNTT Radix-2 NTT multiplication accelerator
(Chen et al., IACR TCHES 2022(1):94-126; reference repo xiang-rc/cfntt_ref).

Ground truth = the pinned `cfntt_ref` submodule (radix-2 tree; radix-4 is
OUT OF SCOPE for this check):
  * cfntt_ref/model_code/poly_mult_radix_2.py   (q=12289, kesai=7, DIT/DIF, op21)
  * cfntt_ref/hardware_code_radix-2/modular_add.v          -> check (A)
  * cfntt_ref/hardware_code_radix-2/modular_substraction.v -> check (B)
  * cfntt_ref/hardware_code_radix-2/modular_half.v         -> check (C)
      (implements the model's op21; note: NOT instantiated anywhere in the
       radix-2 RTL tree — the RTL INTT butterfly omits the per-stage halving)
  * cfntt_ref/hardware_code_radix-2/modular_mul.v          -> checks (D1),(D2)
  * cfntt_ref/hardware_code_radix-2/conflict_free_memory_map.v -> (E1),(E2)
  * cfntt_ref/hardware_code_radix-2/address_generator.v    -> check (F)
  * cfntt_ref/hardware_code_radix-2/tf_address_generator.v -> check (G)
  * cfntt_ref/hardware_code_radix-2/tf_ROM.v               -> check (H)
  * cfntt_ref/hardware_code_radix-2/compact_bf.v           -> check (I)

Everything below is modeled on those real functions/parameters; the two
twiddle tables are extracted from the submodule's files at runtime.

TIER 1 — size-independent, proven at FULL bit width / over the FULL domain:
  (A) modular_add.v   == (x+y) mod q      z3 / QF_BV, exact gate model    [src]
  (B) modular_substraction.v == (x-y) mod q  z3, exact gate model
      ({b,d}=x-y; q_mux=b?M:0; {c,z}=d+q_mux)                             [src]
  (C) modular_half.v  == x * 2^-1 mod q   z3 / QF_BV, exact gate model
      (= the model's op21)                                                [src]
  (D1) modular_mul.v  == (a*b) mod q      z3, EXACT RTL datapath:
       t = ((z>>13) * 15'h5553) >> 15  (pre-truncated Barrett, NOT the
       textbook t=(z*mu)>>28), remainder truncated to 15 bits, ONE
       conditional subtraction.  We prove, for every z <= (q-1)^2:
         - the 29-bit mul2 wire never drops a product bit,
         - t*q <= z              (no 28-bit underflow),
         - z - t*q < 2q          (15-bit truncation lossless AND one
                                  conditional subtraction suffices),
         - the bit-exact output mux == the corrected remainder, < q.
       With r = z - t*q exact and the output = r or r-q, output == z mod q.
       All obligations multiply by CONSTANTS only (z is a free 28-bit
       variable covering every product a*b with a,b < q), so z3 is fast.  [src]
  (D2) the same datapath, bit-exact in plain ints, cross-checked against
       (a*b) mod q on edge pairs + a deterministic random sample          [src]
  (E1) conflict-free memory map: (bank,offset) bijective on 10 bits       [src]
  (E2) for EVERY power-of-two stride 2^p the two butterfly operands
       land in DIFFERENT banks (pure parity-map property)                 [src]
  (F) address_generator.v, EXACT case-statement model, per stage p:
       under the FSM ranges k < 2^(9-p), i < 2^p:
         addr0 = ((k<<1)<<p)+i does not overflow 10 bits,
         addr0[p] == 0,  addr1(case) == addr0 | (1<<p),
         banks(addr0) != banks(addr1),  and (k,i) -> addr0 is INJECTIVE
       (so each stage enumerates every butterfly pair exactly once).      [src]
  (G) tf_address_generator.v, EXACT case constants, per stage p:
       NTT  address = k + (2^(9-p) - 1)  = (model DIT r-index 2^(9-p)+k) - 1
       INTT address = (2^(10-p)-2) - k   = (model DIF r-index 2^(10-p)-1-k) - 1
       both in ROM range [0,1023); i.e. the RTL reads ROM[model_r - 1].   [src]
  (H) twiddle ROM grounding, ALL entries:
       derived psi^bitrev(i,10) (psi=kesai=7) == model w_rom (1024/1024)
       RTL tf_ROM.v case table  == model w_rom[1..1023]  (1023/1023,
       confirming the -1 offset proven in (G); w_rom[0]=1 is unused).     [src]
  (I) compact_bf.v routing, exact mux/operand-order model (DFF delays
       abstracted to identity — pipeline alignment is the FSM's business),
       with the multiplier output as a free m < q (justified by (D1)):
         sel=0 (NTT):  out = (add(u,m), sub(u,m)), mult fed (v, w)
                       => (u + v*w, u - v*w)  == the model DIT butterfly
         sel=1 (INTT): out = (add(u,v), m),   mult fed (sub(v,u), w)
                       => (u + v, (v-u)*w)    == the model DIF butterfly
                          WITHOUT op21: the released radix-2 RTL performs
                          no per-stage halving (modular_half.v is not
                          instantiated) — documented divergence, see NOTE. [src]

TIER 2 — whole-system equivalence at the SMALLEST structure-preserving sizes,
using the source's EXACT DIT_NR_NTT / DIF_RN_INTT / op21 with a negacyclic
twiddle table psi^bitrev derived from the source root (psi = 7^(2048/2N)):
  (J) INVERTIBILITY  INTT(NTT(e_i)) == e_i on the FULL basis, N in {8,16,64}
      -> proves INTT o NTT = identity for ALL inputs (linear map).
  (K) CONVOLUTION    INTT(NTT(e_i) (.) NTT(e_j)) == negacyclic_conv(e_i,e_j)
      on all basis PAIRS, N in {8,16} -> proves the transform diagonalises
      negacyclic convolution (bilinear, hence for all inputs).

Production-size (N=1024) grounding: round-trip on the REAL source negacyclic
table (checked entry-for-entry in (H)) over a deterministic O(N log N) vector
set.  DEEP_VERIFY=1 additionally runs the FULL-basis N=1024 round-trip.

Prints exactly "VERIFIED" / exit 0 iff every required check passes, else
"FAIL: <reason + counterexample>" / exit 1.
"""

import os
import re
import sys
import random

try:
    from z3 import (
        BitVec, BitVecVal, Concat, Extract, ZeroExt, LShR, URem, UGE, ULE,
        ULT, If, And, Or, Not, Then, unsat, sat,
    )
except Exception as exc:  # z3 is allowed and required
    print("FAIL: z3 unavailable (%r)" % (exc,))
    sys.exit(1)

Q = 12289          # 14-bit NTT-friendly prime, q = 3*2^12 + 1              [src]
KESAI = 7          # negacyclic 2N-th root psi used by the reference        [src]
Q0 = 0x5553        # modular_mul.v parameter q0 = 15'h5553 = 21843          [src]

# Ground truth is read AT RUNTIME from the pinned cfntt_ref submodule — the
# tables are never transcribed by hand:
#   SRC_W_ROM  = model_code/poly_mult_radix_2.py  w_rom   (1024 entries)
#   RTL_TF_ROM = hardware_code_radix-2/tf_ROM.v case table (1023 entries)
_REPO = os.path.dirname(os.path.abspath(__file__))
_CFNTT = os.path.join(_REPO, "cfntt_ref")


def _load_ground_truth():
    model = os.path.join(_CFNTT, "model_code", "poly_mult_radix_2.py")
    rom_v = os.path.join(_CFNTT, "hardware_code_radix-2", "tf_ROM.v")
    if not (os.path.exists(model) and os.path.exists(rom_v)):
        print("FAIL: cfntt_ref submodule missing — run "
              "`git submodule update --init` first")
        sys.exit(1)
    with open(model) as fh:
        m = re.search(r"w_rom\s*=\s*\[([\d,\s]+)\]", fh.read())
    w_rom = [int(x) for x in m.group(1).split(",")]
    with open(rom_v) as fh:
        entries = {int(a): int(v) for a, v in
                   re.findall(r"10'd(\d+):\s*Q\s*<=\s*14'd(\d+);", fh.read())}
    tf_rom = [entries[a] for a in sorted(entries)]
    if sorted(entries) != list(range(len(entries))):
        print("FAIL: tf_ROM.v case table has address gaps")
        sys.exit(1)
    return w_rom, tf_rom


SRC_W_ROM, RTL_TF_ROM = _load_ground_truth()


# ---------------------------------------------------------------------------
# z3 helper: a property is PROVEN when the negation is UNSAT.  We bit-blast so
# every pure bit-vector obligation is decidable (never accept 'unknown').
# ---------------------------------------------------------------------------
def _qfbv_solver():
    return Then('simplify', 'bit-blast', 'smt').solver()


def prove_unsat(name, constraints):
    s = _qfbv_solver()
    s.add(*constraints)
    r = s.check()
    if r == unsat:
        return True, ""
    if r == sat:
        return False, "%s: z3 found a violating model %s" % (name, s.model())
    return False, "%s: z3 returned 'unknown' (encoding not decided)" % name


# ---------------------------------------------------------------------------
# Exact gate models of the two combinational modular units, reused by the
# compact_bf routing check (I).  14-bit in, 14-bit out.
# ---------------------------------------------------------------------------
def zadd_gate(x, y):
    """modular_add.v: {c,s}=x+y; {b,d}=s-M; sel=~((~c)&b); z=sel?d:s   [src]"""
    M15 = BitVecVal(Q, 15)
    sum15 = ZeroExt(1, x) + ZeroExt(1, y)          # {c,s}
    c = Extract(14, 14, sum15)
    s = Extract(13, 0, sum15)
    diff = ZeroExt(1, s) - M15                      # {b,d} = s - M
    b = Extract(14, 14, diff)
    d = Extract(13, 0, diff)
    sel = ~((~c) & b)
    return If(sel == BitVecVal(1, 1), d, s)


def zsub_gate(x, y):
    """modular_substraction.v: {b,d}=x-y; q=b?M:0; {c,z}=d+q (carry c dropped)
    — the correction constant is MUXED, exactly as in the RTL.           [src]"""
    diff15 = ZeroExt(1, x) - ZeroExt(1, y)
    b = Extract(14, 14, diff15)                     # borrow (1 => x < y)
    d = Extract(13, 0, diff15)
    qmux = If(b == BitVecVal(1, 1), BitVecVal(Q, 14), BitVecVal(0, 14))
    return Extract(13, 0, ZeroExt(1, d) + ZeroExt(1, qmux))


# ===========================================================================
# TIER 1 (A) modular_add.v — exact gate model, prove == (x+y) mod q
# ===========================================================================
def check_modular_add():
    x = BitVec('x', 14)
    y = BitVec('y', 14)
    sum15 = ZeroExt(1, x) + ZeroExt(1, y)
    gold = If(UGE(sum15, BitVecVal(Q, 15)),
              Extract(13, 0, sum15 - BitVecVal(Q, 15)), Extract(13, 0, sum15))
    pre = And(ULT(x, BitVecVal(Q, 14)), ULT(y, BitVecVal(Q, 14)))
    return prove_unsat("modular_add", [pre, zadd_gate(x, y) != gold])


# ===========================================================================
# TIER 1 (B) modular_substraction.v — exact gate model, prove == (x-y) mod q
# ===========================================================================
def check_modular_sub():
    x = BitVec('x', 14)
    y = BitVec('y', 14)
    # golden: (x - y + q) mod q on a wider unsigned word (no Int/BV mixing)
    gold = URem(ZeroExt(2, x) - ZeroExt(2, y) + BitVecVal(Q, 16), BitVecVal(Q, 16))
    pre = And(ULT(x, BitVecVal(Q, 14)), ULT(y, BitVecVal(Q, 14)))
    return prove_unsat("modular_sub", [pre, ZeroExt(2, zsub_gate(x, y)) != gold])


# ===========================================================================
# TIER 1 (C) modular_half.v / op21 — exact gate model, prove == x * 2^-1 mod q
#   x_sh = x>>1 ; {c,s} = x_sh + (M+1)/2 ; y = x[0] ? s : x_sh
#   (2^-1 mod q == (q+1)/2 == 6145.)  This is the model's op21; note the
#   module is NOT instantiated in the radix-2 RTL datapath (see check I).
# ===========================================================================
def check_modular_half():
    INV2 = (Q + 1) // 2                             # 6145
    a = BitVec('a', 14)
    xsh = LShR(a, 1)                                # a >> 1
    s = Extract(13, 0, ZeroExt(1, xsh) + BitVecVal(INV2, 15))
    y = If(Extract(0, 0, a) == BitVecVal(1, 1), s, xsh)
    gold = URem(ZeroExt(18, a) * BitVecVal(INV2, 32), BitVecVal(Q, 32))
    pre = ULT(a, BitVecVal(Q, 14))
    return prove_unsat("modular_half", [pre, ZeroExt(18, y) != gold])


# ===========================================================================
# TIER 1 (D1) modular_mul.v — EXACT RTL Barrett datapath, all z <= (q-1)^2.
#
# The RTL is NOT the textbook Barrett t=(z*mu)>>28: it pre-truncates
# (z_shift = z>>13 BEFORE multiplying by q0=15'h5553), truncates the
# remainder to 15 bits (sub[14:0]) and does ONE conditional subtraction.
# The margin is tight (the quotient estimate loses up to ~z*2.1e-5 + 1),
# so r < 2q is a real proof obligation, not a textbook fact.
#
# z is a FREE 28-bit variable with z <= (q-1)^2, which covers every product
# a*b with a,b < q while keeping every obligation a CONSTANT multiplication
# (no symbolic 14x14 multiplier to bit-blast).  DFFs are pure pipeline delay.
# ===========================================================================
def check_modular_mul_rtl():
    z = BitVec('z', 28)
    q28 = BitVecVal(Q, 28)
    pre = ULE(z, BitVecVal((Q - 1) * (Q - 1), 28))

    # wire [14:0] z_shift = z >> 13   (28->15: lossless for ANY 28-bit z)
    z_shift = Extract(14, 0, LShR(z, 13))
    # wire [28:0] mul2 = z_shift * q0 — the full product needs 30 bits, the
    # wire keeps 29.  Obligation 1: bit 29 of the true product is 0 under pre
    # (WITHOUT the pre this genuinely truncates — reduced inputs are required).
    prod30 = ZeroExt(15, z_shift) * BitVecVal(Q0, 30)
    ob_mul2_fits = Extract(29, 29, prod30) == BitVecVal(0, 1)
    mul2 = Extract(28, 0, prod30)                   # the 29-bit wire value
    # wire [13:0] mul2_shift = mul2 >> 15   (29->14: exact)
    t = Extract(13, 0, LShR(mul2, 15))              # quotient estimate
    # wire [27:0] mul3 = mul2_shift * q      (14x14 -> 28: exact)
    mul3 = ZeroExt(14, t) * q28
    # Obligation 2: no underflow in sub = z - mul3, i.e. t*q <= z.
    ob_no_underflow = ULE(mul3, z)
    sub = z - mul3                                  # = r, exact given ob 2
    # Obligation 3: r < 2q  (=> sub[14:0] lossless AND one cond. sub enough)
    ob_lt_2q = ULT(sub, BitVecVal(2 * Q, 28))
    # Bit-exact output stage:
    #   sub_low = sub[14:0] ; {sign,sub_correct} = sub_low - q ;
    #   P_d = sign ? sub_low[13:0] : sub_correct
    sub_low = Extract(14, 0, sub)
    diff15 = sub_low - BitVecVal(Q, 15)
    sign = Extract(14, 14, diff15)
    sub_correct = Extract(13, 0, diff15)
    P_d = If(sign == BitVecVal(1, 1), Extract(13, 0, sub_low), sub_correct)
    # Obligation 4: the output equals the corrected remainder and is reduced.
    # With r = z - t*q exact (ob 2) and output = r or r-q (ob 4), output is
    # congruent to z mod q; with output < q it IS z mod q.
    gold = If(ULT(sub, q28), sub, sub - q28)
    ob_output = And(ZeroExt(14, P_d) == gold, ULT(gold, q28))

    bad = Not(And(ob_mul2_fits, ob_no_underflow, ob_lt_2q, ob_output))
    return prove_unsat("modular_mul_rtl", [pre, bad])


# ===========================================================================
# TIER 1 (D2) modular_mul.v — the same datapath bit-exact in plain ints,
# cross-checked against (a*b) mod q (grounds the z3 transcription itself).
# ===========================================================================
def _mul_rtl_int(a, b):
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


def check_modular_mul_concrete():
    edges = [0, 1, 2, 3, 6144, 6145, Q - 2, Q - 1]
    pairs = [(a, b) for a in edges for b in edges]
    rng = random.Random(1)
    pairs += [(rng.randrange(Q), rng.randrange(Q)) for _ in range(20000)]
    for a, b in pairs:
        got = _mul_rtl_int(a, b)
        want = (a * b) % Q
        if got != want:
            return False, ("modular_mul concrete: rtl(%d,%d)=%d != %d"
                           % (a, b, got, want))
    return True, ""


# ===========================================================================
# TIER 1 (E) conflict-free memory map  (conflict_free_memory_map.v):
#            bank = parity of the 10-bit address, offset = address >> 1.
# ===========================================================================
def _parity10(a):
    p = Extract(0, 0, a)
    for i in range(1, 10):
        p = p ^ Extract(i, i, a)
    return p                                        # BV1 = bank number


def check_cfmap_bijection():
    # (bank, offset) is injective over the full 10-bit address space.
    a = BitVec('a', 10)
    b = BitVec('b', 10)
    same_bank = _parity10(a) == _parity10(b)
    same_off = Extract(9, 1, a) == Extract(9, 1, b)        # addr >> 1
    return prove_unsat("cfmap_bijection", [a != b, same_bank, same_off])


def check_cfmap_conflict_free():
    # For EVERY power-of-two stride 2^p: an address with bit p = 0 and its
    # partner (bit p = 1) land in DIFFERENT banks (pure parity property).
    for p in range(10):
        a = BitVec('a_%d' % p, 10)
        mask = BitVecVal(1 << p, 10)
        op0 = a & ~mask
        op1 = op0 | mask
        ok, msg = prove_unsat(
            "cfmap_stride_2^%d" % p,
            [_parity10(op0) == _parity10(op1)],      # same bank -> must be UNSAT
        )
        if not ok:
            return False, msg
    return True, ""


# ===========================================================================
# TIER 1 (F) address_generator.v — EXACT case-statement model.
#   addr0 = ((k<<1)<<p) + i ;  addr1 = {addr0[9:p+1], 1'b1, addr0[p-1:0]}
# Under the FSM ranges (k < 2^(9-p) butterfly groups, i < 2^p within a
# group — the model's k / j loop bounds), prove per stage p:
#   no 10-bit overflow;  addr0[p] == 0;  addr1 == addr0 | (1<<p);
#   banks differ;  and (k,i) -> addr0 is injective.
# ===========================================================================
def _addr1_case(addr0, p):
    one = BitVecVal(1, 1)
    if p == 0:
        return Concat(Extract(9, 1, addr0), one)
    if p == 9:
        return Concat(one, Extract(8, 0, addr0))
    return Concat(Extract(9, p + 1, addr0), one, Extract(p - 1, 0, addr0))


def check_address_generator():
    for p in range(10):
        k = BitVec('k_%d' % p, 20)
        i = BitVec('i_%d' % p, 20)
        pre = And(ULT(k, BitVecVal(1 << (9 - p), 20)),
                  ULT(i, BitVecVal(1 << p, 20)))
        wide = (k << (p + 1)) + i                    # exact at 20 bits
        addr0 = Extract(9, 0, wide)
        addr1 = _addr1_case(addr0, p)
        props = And(
            ULT(wide, BitVecVal(1024, 20)),          # fits the 10-bit wire
            Extract(p, p, addr0) == BitVecVal(0, 1),  # operand-0 bit p is 0
            addr1 == (addr0 | BitVecVal(1 << p, 10)),  # partner at stride 2^p
            _parity10(addr0) != _parity10(addr1),    # different banks
        )
        ok, msg = prove_unsat("address_generator p=%d" % p, [pre, Not(props)])
        if not ok:
            return False, msg
        # injectivity: two (k,i) with the same addr0 must be the same pair,
        # so each stage enumerates every butterfly pair exactly once
        # (512 pairs onto the 512 addresses with bit p = 0).
        k2 = BitVec('k2_%d' % p, 20)
        i2 = BitVec('i2_%d' % p, 20)
        pre2 = And(ULT(k2, BitVecVal(1 << (9 - p), 20)),
                   ULT(i2, BitVecVal(1 << p, 20)))
        wide2 = (k2 << (p + 1)) + i2
        ok, msg = prove_unsat(
            "address_generator injective p=%d" % p,
            [pre, pre2, wide == wide2, Or(k != k2, i != i2)],
        )
        if not ok:
            return False, msg
    return True, ""


# ===========================================================================
# TIER 1 (G) tf_address_generator.v — EXACT case constants, per stage p.
# The model's DIT r-counter starts at 1 and increments; its DIF r-counter
# starts at len(w_rom)-1 = 1023 and decrements.  Stage p (J = 2^p) does
# 2^(9-p) reads, so:
#   model DIT k-th read:  r = 2^(9-p) + k      (k = 0 .. 2^(9-p)-1)
#   model DIF k-th read:  r = 2^(10-p) - 1 - k
# The RTL case table is  NTT: k + (2^(9-p)-1),  INTT: (2^(10-p)-2) - k
# (p=9 INTT is literally `k`, i.e. 0 for the single read) — exactly
# model_r - 1 in both modes, always inside the 1023-deep ROM.
# ===========================================================================
def check_tf_addressing():
    ntt_const = {9: 0, 8: 1, 7: 3, 6: 7, 5: 15, 4: 31,
                 3: 63, 2: 127, 1: 255, 0: 511}      # RTL: k + const   [src]
    intt_const = {8: 2, 7: 6, 6: 14, 5: 30, 4: 62,
                  3: 126, 2: 254, 1: 510, 0: 1022}   # RTL: const - k   [src]
    for p in range(10):
        k = BitVec('k_%d' % p, 20)
        pre = ULT(k, BitVecVal(1 << (9 - p), 20))
        ntt = k + BitVecVal(ntt_const[p], 20)
        model_dit_r = BitVecVal(1 << (9 - p), 20) + k
        if p == 9:
            intt = k                                 # case p=9: reg_1 = k [src]
        else:
            intt = BitVecVal(intt_const[p], 20) - k
        model_dif_r = BitVecVal((1 << (10 - p)) - 1, 20) - k
        props = And(
            ntt == model_dit_r - BitVecVal(1, 20),   # ROM[model_r - 1]
            intt == model_dif_r - BitVecVal(1, 20),
            ULT(ntt, BitVecVal(1023, 20)),           # inside the 1023-deep ROM
            ULT(intt, BitVecVal(1023, 20)),
        )
        ok, msg = prove_unsat("tf_address p=%d" % p, [pre, Not(props)])
        if not ok:
            return False, msg
    return True, ""


# ===========================================================================
# TIER 1 (H) twiddle ROM grounding — ALL entries of BOTH source tables.
#   derived[i] = psi^bitrev(i,10) mod q (psi = kesai = 7)
#   == model w_rom entry-for-entry (1024), and the RTL tf_ROM.v case table
#   == w_rom[1..1023] entry-for-entry (the -1 offset proven in (G);
#   w_rom[0] = 1 is the unused identity entry).
# ===========================================================================
def check_twiddle_roms():
    if len(SRC_W_ROM) != 1024 or len(RTL_TF_ROM) != 1023:
        return False, ("rom tables: bad lengths %d/%d"
                       % (len(SRC_W_ROM), len(RTL_TF_ROM)))
    if SRC_W_ROM[0] != 1:
        return False, "rom tables: w_rom[0] = %d != 1" % SRC_W_ROM[0]
    for i in range(1024):
        d = pow(KESAI, bitrev(i, 10), Q)
        if d != SRC_W_ROM[i]:
            return False, ("rom tables: derived psi^bitrev w_rom[%d]=%d "
                           "!= source %d" % (i, d, SRC_W_ROM[i]))
    for a in range(1023):
        if RTL_TF_ROM[a] != SRC_W_ROM[a + 1]:
            return False, ("rom tables: RTL tf_ROM[%d]=%d != w_rom[%d]=%d"
                           % (a, RTL_TF_ROM[a], a + 1, SRC_W_ROM[a + 1]))
    return True, ""


# ===========================================================================
# TIER 1 (I) compact_bf.v routing — exact mux/operand-order dataflow model.
# DFF / shift_4 delays are pipeline alignment only and abstracted to
# identity; the multiplier output is a FREE m < q (its value is pinned to
# (A*B) mod q by check D1).  Proves, at the gate level of zadd/zsub:
#   sel=0 (NTT):  (bf_lower, bf_upper) = (add(u,m), sub(u,m)), mult <- (v, w)
#                 with m = v*w mod q  =>  (u + v*w, u - v*w)  = model DIT bf
#   sel=1 (INTT): (bf_lower, bf_upper) = (add(u,v), m), mult <- (sub(v,u), w)
#                 with m = (v-u)*w mod q  =>  (u + v, (v-u)*w) = model DIF bf
#                 WITHOUT op21 halving (modular_half.v is not instantiated
#                 in the radix-2 RTL) — documented divergence, see NOTE.
# The sel=1 subtraction operand order (v-u, NOT u-v) matches the model's
# op21(t - u) * w.
# ===========================================================================
def check_compact_bf_routing():
    u = BitVec('u', 14)
    v = BitVec('v', 14)
    m = BitVec('m', 14)                              # mult_out, free (see D1)
    sel = BitVec('sel', 1)
    zero = BitVecVal(0, 1)
    # netlist (delays -> identity): mux_out1 = u (both branches are u)
    sub_op1 = If(sel == zero, u, v)                  # mux_out1 / mux_out5
    sub_op2 = If(sel == zero, m, u)
    sub_out = zsub_gate(sub_op1, sub_op2)
    add_out = zadd_gate(u, If(sel == zero, m, v))    # mux_out2
    bf_lower = add_out                               # (q1 vs q5 delay only)
    bf_upper = If(sel == zero, sub_out, m)
    mult_a = If(sel == zero, v, sub_out)             # mux_out3
    pre = And(ULT(u, BitVecVal(Q, 14)), ULT(v, BitVecVal(Q, 14)),
              ULT(m, BitVecVal(Q, 14)))
    ntt_props = And(bf_lower == zadd_gate(u, m),
                    bf_upper == zsub_gate(u, m),
                    mult_a == v)
    intt_props = And(bf_lower == zadd_gate(u, v),
                     bf_upper == m,
                     mult_a == zsub_gate(v, u))      # (v-u), operand order!
    bad = Or(And(sel == zero, Not(ntt_props)),
             And(sel == BitVecVal(1, 1), Not(intt_props)))
    ok, msg = prove_unsat("compact_bf_routing", [pre, bad])
    if ok:
        sys.stderr.write(
            "NOTE compact_bf.v INTT mode computes (u+v, (v-u)*w) with NO "
            "per-stage op21 halving\n     (modular_half.v is defined but "
            "instantiated nowhere in the radix-2 RTL); the\n     model's "
            "DIF_RN_INTT applies op21 every stage — a real model-vs-RTL "
            "scaling divergence\n     in the released source, flagged here, "
            "not hidden.\n")
    return ok, msg


# ===========================================================================
# TIER 2 reference: the source's EXACT functions (poly_mult_radix_2.py),
# parameterised by q and the twiddle table.
# ===========================================================================
def op21(a, q):
    if a & 1 == 0:
        r = (a >> 1) % q
    else:
        r = ((a >> 1) + ((q + 1) >> 1)) % q
    return r


def DIT_NR_NTT(a, w_rom, q):
    n = len(a)
    log_n = n.bit_length() - 1
    r = 1
    for p in range(log_n - 1, -1, -1):
        J = 1 << p
        for k in range(n // (2 * J)):
            w = w_rom[r]
            r += 1
            for j in range(J):
                u = a[k * 2 * J + j] % q
                t = (a[k * 2 * J + j + J] * w) % q
                a[k * 2 * J + j] = (u + t) % q
                a[k * 2 * J + j + J] = (u - t) % q
    return a


def DIF_RN_INTT(a, w_rom, q):
    n = len(a)
    log_n = n.bit_length() - 1
    r = len(w_rom) - 1
    for i in range(log_n):
        J = 1 << i
        for k in range(n // (2 * J)):
            w = w_rom[r]
            r -= 1
            for j in range(J):
                u = a[k * 2 * J + j] % q
                t = a[k * 2 * J + j + J] % q
                a[k * 2 * J + j] = (op21(u + t, q)) % q
                a[k * 2 * J + j + J] = (op21(t - u, q) * w) % q
    return a


def pwm(x, y, q):
    return [(x[i] * y[i]) % q for i in range(len(x))]


def bitrev(x, bits):
    r = 0
    for _ in range(bits):
        r = (r << 1) | (x & 1)
        x >>= 1
    return r


def build_wrom(Ns, psi, q):
    """Negacyclic twiddle table in the source's bit-reversed layout:
       w_rom[i] = psi^bitrev(i, log2 Ns).  (== the source table at N=1024,
       proven entry-for-entry in check H.)"""
    logn = Ns.bit_length() - 1
    return [pow(psi, bitrev(i, logn), q) for i in range(Ns)]


def negacyclic_conv(a, b, q):
    """Independent golden: product in Z_q[x]/(x^N + 1)."""
    N = len(a)
    c = [0] * N
    for i in range(N):
        for j in range(N):
            k = i + j
            v = a[i] * b[j]
            if k >= N:
                k -= N
                v = -v
            c[k] = (c[k] + v) % q
    return c


def small_root(Ns, q):
    """psi = 7^(2048/(2*Ns)) is a primitive 2N-th root mod q (order(7)=2048)."""
    psi = pow(KESAI, 2048 // (2 * Ns), q)
    if pow(psi, Ns, q) != q - 1 or pow(psi, 2 * Ns, q) != 1:
        return None
    return psi


# ---- (J) invertibility on the FULL basis (proves INTT o NTT = id) ----------
def check_invertibility(Ns):
    q = Q
    psi = small_root(Ns, q)
    if psi is None:
        return False, "invertibility N=%d: 7 is not a primitive 2N-th root" % Ns
    w = build_wrom(Ns, psi, q)
    for idx in range(Ns):
        e = [0] * Ns
        e[idx] = 1
        spec = DIT_NR_NTT(e[:], w, q)
        back = DIF_RN_INTT(spec[:], w, q)
        if back != e:
            return False, ("invertibility N=%d: INTT(NTT(e_%d)) = %s != e_%d"
                           % (Ns, idx, back, idx))
    return True, ""


# ---- (K) convolution theorem on all basis pairs (proves diagonalisation) ---
def check_convolution(Ns):
    q = Q
    psi = small_root(Ns, q)
    if psi is None:
        return False, "convolution N=%d: 7 is not a primitive 2N-th root" % Ns
    w = build_wrom(Ns, psi, q)
    for i in range(Ns):
        ei = [0] * Ns
        ei[i] = 1
        fi = DIT_NR_NTT(ei[:], w, q)
        for j in range(Ns):
            ej = [0] * Ns
            ej[j] = 1
            fj = DIT_NR_NTT(ej[:], w, q)
            got = DIF_RN_INTT(pwm(fi, fj, q), w, q)
            gold = negacyclic_conv(ei, ej, q)
            if got != gold:
                return False, ("convolution N=%d: INTT(NTT(e_%d).NTT(e_%d)) = %s"
                               " != negacyclic %s" % (Ns, i, j, got, gold))
    return True, ""


# ---- production-size grounding: round-trip on the REAL source table --------
def check_production_roundtrip():
    q = Q
    N = 1024
    w = SRC_W_ROM                                   # checked in (H): == derived
    rng = random.Random(0)
    vecs = [
        [0] * N,                                     # zero
        [1] + [0] * (N - 1),                         # e_0
        [0] * (N - 1) + [1],                         # e_{N-1}
        [1] * N,                                     # all ones
        [i % q for i in range(N)],                   # ramp
    ]
    for _ in range(8):
        vecs.append([rng.randrange(q) for _ in range(N)])
    for vi, v in enumerate(vecs):
        back = DIF_RN_INTT(DIT_NR_NTT(v[:], w, q), w, q)
        ref = [c % q for c in v]
        if back != ref:
            return False, ("production roundtrip: INTT(NTT(v_%d)) != v_%d" % (vi, vi))
    return True, ""


# ---- DEEP_VERIFY=1: full-basis N=1024 round-trip (expensive, off by default)
def check_production_full_basis():
    q = Q
    N = 1024
    w = SRC_W_ROM
    for idx in range(N):
        e = [0] * N
        e[idx] = 1
        back = DIF_RN_INTT(DIT_NR_NTT(e[:], w, q), w, q)
        if back != e:
            return False, "full basis N=1024: INTT(NTT(e_%d)) != e_%d" % (idx, idx)
    return True, ""


# ===========================================================================
def main():
    checks = [
        ("modular_add.v == (x+y) mod q   [full 14-bit domain, z3]", check_modular_add),
        ("modular_substraction.v == (x-y) mod q [full domain, z3]", check_modular_sub),
        ("modular_half.v == x/2 mod q    [full 14-bit domain, z3]", check_modular_half),
        ("modular_mul.v == a*b mod q     [EXACT RTL datapath, z3]", check_modular_mul_rtl),
        ("modular_mul.v datapath, concrete ints  [edges + sample]", check_modular_mul_concrete),
        ("conflict-free map: (bank,offset) bijective         [z3]", check_cfmap_bijection),
        ("conflict-free map: distinct banks every stride     [z3]", check_cfmap_conflict_free),
        ("address_generator.v: exact case model, all stages  [z3]", check_address_generator),
        ("tf_address_generator.v == model r-counter - 1      [z3]", check_tf_addressing),
        ("twiddle ROMs: derived == w_rom == tf_ROM.v   [all 2047]", check_twiddle_roms),
        ("compact_bf.v routing: NTT/INTT mux + operand order [z3]", check_compact_bf_routing),
        ("INTT o NTT = identity          [full basis, N=8]", lambda: check_invertibility(8)),
        ("INTT o NTT = identity          [full basis, N=16]", lambda: check_invertibility(16)),
        ("INTT o NTT = identity          [full basis, N=64]", lambda: check_invertibility(64)),
        ("diagonalises negacyclic conv   [basis pairs, N=8]", lambda: check_convolution(8)),
        ("diagonalises negacyclic conv   [basis pairs, N=16]", lambda: check_convolution(16)),
        ("production round-trip on REAL source table [N=1024]", check_production_roundtrip),
    ]
    if os.environ.get("DEEP_VERIFY") == "1":
        checks.append(("full-basis round-trip [N=1024, DEEP_VERIFY]",
                       check_production_full_basis))
    for label, fn in checks:
        try:
            ok, msg = fn()
        except Exception as exc:
            print("FAIL: %s raised %r" % (label, exc))
            sys.exit(1)
        if not ok:
            print("FAIL: %s" % msg)
            sys.exit(1)
        sys.stderr.write("ok  %s\n" % label)
    print("VERIFIED")
    sys.exit(0)


if __name__ == "__main__":
    main()
