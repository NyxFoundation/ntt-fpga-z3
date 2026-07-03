# Generalization (Phase 5)

The two Falcon inventions are not one-off tricks: both are instances of a
construction that applies to **any Proth NTT prime** `q = k·2^m + 1`. The
generator `proposed/generator/kred_gen.py` derives, verifies and emits them
per prime, demonstrated on **Falcon (q = 12289, FN-DSA)** and **Kyber
(q = 3329, ML-KEM)** — the two most important lattice PQC moduli.

## The two constructions, parameterized

### K-RED reduction (any Proth prime)

`k·2^m ≡ −1 (mod q)`, so splitting a value at bit m and folding by
`k·lo − hi` (with a q-multiple offset for non-negativity) multiplies the
represented residue by k while shrinking the magnitude. `F` folds reduce a
full product (< q²) to < 2q; the spurious factor `k^F` is folded into the
twiddle ROM as `(k^F)^{-1}`. `k·x` is shift-add (k's set bits).

| | Falcon | Kyber |
|---|---|---|
| q | 12289 = 3·2¹²+1 | 3329 = 13·2⁸+1 |
| folds F | 2 | 2 |
| spurious factor k^F | 9 → fold 9⁻¹=2731 | 169 → fold 169⁻¹=2285 |
| k·x | x<<{0,1} (1 adder) | x<<{0,2,3} (2 adders) |
| cond-subs | 1 | 1 |
| multipliers | **1** (just A·B) | **1** |

### ψ-fold twiddle ROM (any NTT prime with shift-friendly ψ)

The bit-reversed negacyclic table obeys `w_rom[N/2+j] = ψ·w_rom[j]`; if ψ is
shift-friendly, store half and derive the rest with a ψ-multiply gate
(recursively −75%).

| | Falcon | Kyber |
|---|---|---|
| ψ | 7 = x<<{0,1,2} | 17 = x<<{0,4} |
| store | N/2 (N/4 two-level) | N/2 (N/4) |

## Evidence

- **Kyber K-RED reducer, exhaustive**: `kred_gen.py` checks the fold
  schedule against `169·z mod q` for **all z < q² ≈ 1.1×10⁷**.
- **Falcon K-RED reducer**: edges + 2M samples (the full 28-bit domain is
  z3-proven for the hand-written unit in `../proposed/kred/verify_kred.py`).
- **Generated Kyber RTL** (`modular_mul_kred_kyber.v`, emitted by the
  generator): passes an iverilog sweep of 60k edge+random product pairs
  (`gen_check.py`) computing `169·A·B mod q` at the emitted latency.
- The generator finds a **tighter** Falcon schedule than the hand-written
  RTL (4q vs 6q first-fold offset) — both valid; the hand-written unit is
  one conservative instance, confirming the general construction subsumes it.

## Why this matters for the paper

It converts three separable contributions —
(a) verified K-RED retrofit + bug fix, (b) ψ-fold ROM, (c) the FV
methodology — from *Falcon-specific* to *a method with a working generator*,
with Kyber as an independent, exhaustively-checked second instance. That is
the difference between "we improved one accelerator" and "here is a verified
technique for the Proth-prime NTT family, plus a tool that instantiates it."

## Remaining (TODO)

- Emit the ψ-fold ROM RTL generically (currently emitted by hand for Falcon
  in `../rom-fold/gen_rom_fold.py`; the plan is computed for any prime).
- A generated SymbiYosys harness per prime (the Falcon harnesses are the
  template; the z3 congruence-identity encoding generalizes directly).
