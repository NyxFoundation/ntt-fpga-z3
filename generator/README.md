# Parameterized generator: the inventions as a method

`kred_gen.py` turns the two Falcon-specific inventions into a construction
that instantiates for any Proth NTT prime `q = k·2^m + 1`. This lifts the
paper from two tricks for q = 12289 to a verified method, demonstrated on
Falcon and Kyber.

## What it generates, per prime

1. **K-RED reduction schedule.** Because `k·2^m ≡ −1 (mod q)`, a value split
   at bit m folds by `k·lo − hi` (plus a q-multiple offset to stay
   non-negative). The generator computes:
   - the number of folds `F` to reduce a full product (< q²) to < 2q,
   - each fold's offset (as a multiple of q) and wire width,
   - the spurious factor `k^F` and its inverse `(k^F)^{-1}` to fold into the
     twiddle ROM (the transform's precomputed multiplier constants),
   - `k·x` as a shift-add sum (k's set bits): Falcon k=3 → 1 adder,
     Kyber k=13 → 2 adders.
   It then emits synthesizable RTL (the register-level hardware source
   code: `modular_mul_kred_<prime>.v`) and a
   bit-exact model, validated over the whole product domain.

2. **ψ-fold ROM plan.** If ψ (the 2N-th root) is shift-friendly, the
   bit-reversed table's upper half is `ψ·(lower half)`, so store half and
   derive with a ψ-multiply gate (recursively −75%).

## Validated instances

| prime | q = k·2^m+1 | K-RED | ψ-fold |
|---|---|---|---|
| **Falcon** (FN-DSA) | 12289 = 3·2¹²+1 | 2 folds, factor 9, k·x = 1 adder, 1 cond-sub | ψ=7 = x<<{0,1,2}, store N/2 (N/4) |
| **Kyber** (ML-KEM) | 3329 = 13·2⁸+1 | 2 folds, factor 169, k·x = 2 adders, 1 cond-sub | ψ=17 = x<<{0,4}, store N/2 (N/4) |

Correctness evidence (`kred_gen.py`, CI):
- Kyber K-RED reducer: exhaustive over all z < q² (≈ 1.1×10⁷).
- Falcon K-RED reducer: edges + 2M samples (the full 28-bit domain is
  covered by the hand-written unit's z3 (an automated theorem prover)
  proof in `../kred/verify_kred.py`).
- The generated Kyber RTL (`modular_mul_kred_kyber.v`) passes an
  iverilog sweep (`tb_kyber.v`, 60k edge+random pairs) computing
  `169·A·B mod q` at the emitted latency.

The generator finds a tighter Falcon schedule than the hand-written RTL
(4q vs 6q first-fold offset); both are valid, and the hand-written unit is
one conservative instance.

## Run

```sh
uv run kred_gen.py                                   # plans + KRED-GEN VALIDATED
nix shell nixpkgs#iverilog --command uv run gen_check.py   # emit + iverilog-check Kyber RTL
```

## Scope

- The generator proves the reduction datapath and the ψ-fold relation
  per prime. Wiring a generated unit into a full accelerator (banks, FSM —
  the control state machine) is per-design integration, not automated here.
- ψ-fold requires a shift-friendly ψ; both Falcon and Kyber have one, but a
  general q may not (the generator flags it and falls back to a small
  constant-multiply, still cheaper than storing the half).
