# psi-fold twiddle ROM: half the stored words, zero multipliers

Invention #2 of the loop, and the one found by visually reviewing the 3D
architecture model. After CFNTT-KRED shrank the arithmetic, the rendered
floorplan showed the 1023-word twiddle ROM (the precomputed constants
the transform multiplies by) as the largest block left,
next to two precedents: the K-RED fold stages (shift-add constant
multiplies are ~free) and the op21 gate on the ROM output (deriving a
twiddle variant from a stored word already pays once). This module applies
the same pattern to the ROM itself.

## The algorithm

### 1. The hidden symmetry of the bit-reversed table

CFNTT stores its negacyclic twiddles in bit-reversed order:

```
w_rom[i] = ψ^bitrev₁₀(i)   (mod q),    ψ = kesai = 7,  q = 12289
```

For an index in the upper half, `512 + j` (j < 512), bit 9 is set, and in
the bit-reversed exponent that bit lands at position 0:

```
bitrev₁₀(512 + j) = 2·bitrev₉(j) + 1 = bitrev₁₀(j) + 1
```

so the whole upper half is one ψ away from the lower half:

```
w_rom[512 + j] = ψ^(bitrev(j)+1) = 7 · w_rom[j]   (mod q)   for ALL j < 512
```

(verified against every entry of the shipped `tf_ROM.v`).

### 2. ×7 is free on a Proth prime

ψ = 7 makes the derivation a shift-and-subtract:

```
7x = (x << 3) − x          < 7q < 2¹⁷  for x < q
```

then reduced to `[0, q)` by six parallel constant comparators that
select the multiple `m·q` (from precomputed values) plus a single
subtraction: no multiplier, and a shallow critical path (chosen over
three chained subtractions after a logic-depth analysis: LTP 31 → 26).

### 3. The folded ROM

`tf_rom_fold.v` keeps `tf_ROM.v`'s exact interface and 1-cycle latency:

```
i = A + 1                            (address semantics of tf_ROM)
base  = ROM512[i mod 512]            512 stored words = 9⁻¹·w_rom[0..511]
Q_out = i ≥ 512 ? fold7(base) : base
```

The stored words are 9⁻¹-scaled because the unit composes with the
CFNTT-KRED butterfly (the small multiply-and-add step the transform
repeats; [`../kred/`](../kred/)). Constant scalings commute
with the fold, so the same trick works unscaled for the original design.

### 4. It recurses

Each halving level costs one more fold7 in the chain:

```
w[256 + j] = 49·w[j]  = fold7²    → 256-word ROM (−75% bits), ≤ 3 chained folds
w[128 + j] = 7⁴·w[j]  = fold7⁴    → …
```

The 512-word (1-level) point is the shipped RTL (the register-level
hardware source code); the 256-word variant is
validated end-to-end in `rom_fold_math.py`.

## Files

| File | Role |
|---|---|
| `gen_rom_fold.py` | generates `tf_rom_fold.v` mechanically from the shipped `tf_ROM.v`; no table is hand-transcribed (CI regenerates and diffs) |
| `tf_rom_fold.v` | the folded ROM RTL (generated; drop-in for `tf_ROM.v`) |
| `rom_fold_math.py` | fold relations at levels 1–3 against the real table; `fold7` exhaustive over the full domain; 9⁻¹ composition; e2e round-trips with 512- and 256-word ROMs |
| `verify_rom_fold.py` | z3, full domain, divider-free: `t0 == 7x` fits 17 bits; congruence `7x == t3 + q·(4s₁+2s₂+s₃)`; `t3 < q` |
| `fv_rom_fold.sv/.sby` | SymbiYosys miter with REN free: a load cycle gives `9·Q_new ≡ Q_ref (mod q)` at every legal address; an idle cycle (REN=0) holds both outputs; together full equivalence for every REN sequence, 1-cycle latency preserved |

**Corner cases.** `A = 1023` is the one input where the two ROMs differ
(the shipped ROM's case statement holds its previous word; the fold ROM
wraps its internal index). It is excluded by assumption, and that
assumption is itself proven elsewhere: `../verification/reference-fv/fv_agu.sby` shows
`tf_address_generator` keeps its address inside `[0, 1023)` in both modes.
`REN = 0` (idle) behaviour is proven identical, so equivalence survives
arbitrary stall patterns.

**Composition with the butterfly.** No extra harness is needed to verify
the ROM feeding `compact_bf_v2`: `fv_bf_v2_{ntt,intt}` prove the butterfly
correct for every w-input stream, which subsumes the streams this ROM
can produce; `fv_rom_fold` pins what those streams are. The audits in
`../audit_v2.py` add lint, per-mode feed-forward/latency and single-clock
checks; `../mutation_rtl.sh` shows a corrupted stored word or a wrong fold
shift is caught with a counterexample.

## Results

| | `tf_ROM.v` | `tf_rom_fold.v` |
|---|---|---|
| stored words | 1023 | **512** (−50%; 256 possible) |
| stored bits | 14322 | **7168** |
| cells (yosys generic synth, flattened) | 7828 | **1611 (−79%)** |
| extra logic | — | 1 fold7 gate (4 narrow adders) |
| interface / latency | 1-cycle registered | identical |

## Notes

- On-the-fly / compressed twiddle generation is a known family of
  techniques in FFT/NTT hardware. The contribution here is the specific
  bit-reversed half-fold via ψ with a Proth-prime shift-sub multiplier,
  composed with the 9⁻¹ K-RED scaling, and proven equivalent to the
  shipped ROM at every address rather than re-derived from the spec.
- The fold sits combinationally after the ROM register; it adds gate delay
  on the w path, which has two registers of slack in `compact_bf`. Timing
  closure is expected, but place-and-route (mapping the logic onto the
  chip's physical fabric) is out of scope here.
