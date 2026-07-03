# CFNTT-KRED — a 1-multiplier, bug-fixed radix-2 NTT butterfly

Invention #1 of the view → implement → verify loop. A drop-in replacement
for cfntt_ref's modular multiplier and butterfly: **3 hardware multipliers
→ 1**, with the upstream INTT-halving bug
([cfntt_ref#7](https://github.com/xiang-rc/cfntt_ref/issues/7)) fixed inside
the architecture. Same ports, same delay fabric, same latencies
(multiplier 4 cycles, butterfly 6).

## The algorithm

### 1. Why Barrett is wasteful here

The reference `modular_mul.v` reduces the 28-bit product `z = a·b` with
Barrett reduction, which needs **two more hardware multipliers** besides
the unavoidable `a·b`:

```
t = ((z >> 13) · 21843) >> 15      ← multiplier #2 (quotient estimate)
r = z − t·q                        ← multiplier #3
```

But q = 12289 = **3·2¹² + 1** is a Proth prime, which gives the identity

```
3·2¹² ≡ −1  (mod q)
```

so any value can be reduced by *splitting at bit 12* instead of dividing —
the K-RED trick (Longa & Naehrig 2016, used in software for this q).

### 2. K-RED: reduction with shifts and adds only

Write the 28-bit product as `z = z₁·2¹² + z₀`. Then

```
3z = 3z₀ + 3·2¹²·z₁ ≡ 3z₀ − z₁   (mod q)
```

One fold trades a 28-bit value for a 17-bit one at the cost of a factor 3.
Two folds finish the job (all offsets are multiples of q, kept to stay
non-negative — no signed hardware):

```
d = 3·z[11:0] + 6q − z[27:12]      ≡ 3z (mod q),   0 < d < 2¹⁷
e = 3·d[11:0] +  q − d[16:12]      ≡ 9z (mod q),   0 < e < 2q
r = e ≥ q ? e − q : e              =  9z mod q
```

`3x = (x<<1) + x`, so the whole reduction is **shifts, adds and one
conditional subtraction** — `modular_mul_kred.v`, pipelined to the same
latency 4 as the original.

### 3. Folding the factor 9 away

The unit returns `9ab mod q`, not `ab mod q`. The factor disappears
architecturally, with **zero correction hardware** on the hot path:

| Path | Trick | Result |
|---|---|---|
| NTT butterfly | the twiddle ROM stores `W = 9⁻¹·w` (9⁻¹ = 2731) | `9·v·W = v·w` — **exact** |
| INTT butterfly | the INTT twiddle is `op21(W) = (2·9)⁻¹·w`, derived from the *same* ROM word by one `modular_half` gate | `9·(v−u)·op21(W) = ((v−u)·w)/2` — the per-stage **halving is fused in**, fixing issue #7 on the multiply path for free |
| INTT add path | one `modular_half` gate on `u+v` | `op21(u+v)` — the other half of the fix |
| PWM (both operands are data) | double-pass through the same unit with the stored constant 81⁻¹ = 11227 | `9·(9xy)·81⁻¹ = xy` — exact |

The ROM keeps the exact CFNTT layout and size; only its *contents* are
scaled. (The companion invention in [`../rom-fold/`](../rom-fold/) then
halves the ROM itself.)

## Files

| File | Role |
|---|---|
| `modular_mul_kred.v` | the K-RED multiplier RTL (drop-in for `modular_mul.v`) |
| `compact_bf_v2.v` | the butterfly RTL: KRED mult + op21-on-ROM INTT twiddle + halved add path |
| `kred_math.py` | bit-exact model; e2e `INTT(NTT(x))==x` and full negacyclic polymult vs golden, on the real (9⁻¹-scaled) `tf_ROM.v` contents |
| `verify_kred.py` | z3, FULL 28-bit domain, divider-free: width bounds + the linear congruence identities `3c+6q = d+c₁q`, `3d+q = e+d₁q` + reduced output |
| `fv_kred.sv/.sby` | SymbiYosys: RTL pipeline == the fold spec at latency 4 (BMC + k-induction) + reset; with the z3 proof this gives `P_out == 9AB mod q` |
| `fv_bf_v2.sv`, `fv_bf_v2_{ntt,intt}.sby` | compositional butterfly proofs (leaf units abstracted per `abstract_units_v2.v`, justified by `fv_kred` + `../../yosys/fv_units`) |
| `golden_v2.vh`, `abstract_units_v2.v` | golden operators / behavioural abstractions |
| `cost_report.ys/.txt` | yosys generic-synth cost comparison |

## Results

| Module | cells | FF bits | HW multipliers |
|---|---|---|---|
| `modular_mul.v` (reference, Barrett) | 2176 | 101 | **3** |
| `modular_mul_kred.v` | **1724 (−21%)** | **74 (−27%)** | **1** |
| `compact_bf.v` (reference — INTT-broken) | 2820 | 297 | 3 |
| `compact_bf_v2.v` (INTT-correct) | **2549 (−10%)** | 270 | **1** |

On FPGA the multipliers map to DSP blocks: **3 → 1 DSP per butterfly**,
scaling with the number of parallel butterflies.

## Honesty notes

- K-RED is known art (Longa & Naehrig, *Speeding up the NTT*, 2016 —
  software, same q). The contribution is the **verified hardware fusion
  into CFNTT**: single-ROM 9⁻¹ twiddles, the op21-on-ROM derivation that
  yields the INTT twiddle *and* the halving in one gate, the 81⁻¹ PWM
  double-pass, and end-to-end formal verification.
- PWM double-pass costs one extra pass over N coefficients per product
  (≈ +6% multiplier cycles for a full poly-mult).
- Timing: the folds are adder chains inside the same latency-4 envelope;
  place-and-route numbers are out of scope here.
