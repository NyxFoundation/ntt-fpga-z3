# ntt-fpga-z3

[![verify](https://github.com/NyxFoundation/ntt-fpga-z3/actions/workflows/verify.yml/badge.svg)](https://github.com/NyxFoundation/ntt-fpga-z3/actions/workflows/verify.yml)

Formal verification (z3/SMT + Yosys/SymbiYosys) of the **CFNTT** radix-2 NTT
accelerator reference implementation —
[xiang-rc/cfntt_ref](https://github.com/xiang-rc/cfntt_ref), the artifact of
*"CFNTT: Scalable Radix-2/4 NTT Multiplication Architecture with an Efficient
Conflict-free Memory Mapping Scheme"* (Chen et al., IACR TCHES 2022(1):94–126,
[DOI 10.46586/tches.v2022.i1.94-126](https://doi.org/10.46586/tches.v2022.i1.94-126)).

The released Verilog is modeled **bit-exactly** (wire widths, truncations,
mux/operand order taken from the RTL, not from the paper) and proved
equivalent to the mod-q arithmetic with z3 over the *full* input domains.
Ground truth — including both twiddle tables — is read at runtime from the
pinned `cfntt_ref` submodule; nothing is transcribed by hand.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) — every script carries PEP 723
inline metadata, so `uv run` provisions Python + z3 automatically:

```sh
git clone --recurse-submodules https://github.com/NyxFoundation/ntt-fpga-z3.git
cd ntt-fpga-z3

uv run verify_radix2.py       # the z3 verification    -> "VERIFIED"
uv run bug_intt_halving.py    # the finding            -> "BUG REPRODUCED + FIX VALIDATED"
uv run mutation_test.py       # non-vacuity harness    -> "ALL MUTATIONS DETECTED"

# RTL-level suite (SymbiYosys + LEC + structural audits):
nix shell nixpkgs#yosys nixpkgs#sby nixpkgs#yices --command yosys/run_all.sh
```

`DEEP_VERIFY=1 uv run verify_radix2.py` additionally runs the full-basis
N=1024 round-trip. (No uv? `pip install z3-solver` and run with `python`.)

## What is verified (`verify_radix2.py`)

| # | Check | Method |
|---|-------|--------|
| A | `modular_add.v` == (x+y) mod q | z3, exact gate model, full 14-bit domain |
| B | `modular_substraction.v` == (x−y) mod q | z3, exact gate model, full domain |
| C | `modular_half.v` == x·2⁻¹ mod q | z3, exact gate model, full domain |
| D1 | `modular_mul.v` == a·b mod q | z3, **exact RTL datapath**: pre-truncated Barrett `t=((z>>13)·0x5553)>>15`, 15-bit remainder truncation, one conditional subtraction — proves the 29-bit wire never drops a bit, `t·q ≤ z`, `z−t·q < 2q`, output reduced, for every z ≤ (q−1)² |
| D2 | same datapath in plain ints | edge pairs + 20k-sample cross-check vs (a·b) mod q |
| E | `conflict_free_memory_map.v` | z3: (bank, offset) bijective; distinct banks at every power-of-two stride |
| F | `address_generator.v` | z3, exact case-statement model: no 10-bit overflow, `addr0[p]=0`, `addr1 = addr0 \| (1<<p)`, banks differ, (k,i)→addr0 injective — every stage enumerates each butterfly pair exactly once |
| G | `tf_address_generator.v` | z3: both modes read `ROM[model_r − 1]`, always inside the 1023-deep ROM |
| H | twiddle ROMs, **all 2047 entries** | derived ψ^bitrev(i) == model `w_rom` (1024/1024) == RTL `tf_ROM.v` (1023/1023) |
| I | `compact_bf.v` routing | z3: NTT/INTT mux selection and operand order (INTT subtracts `v−u`) |
| J | INTT∘NTT = identity | full basis, N ∈ {8, 16, 64} (linear ⇒ all inputs) |
| K | negacyclic convolution theorem | all basis pairs, N ∈ {8, 16} (bilinear ⇒ all inputs) |
| — | production N=1024 round-trip | on the real source table; full basis behind `DEEP_VERIFY=1` |

All checks pass — the arithmetic units, the conflict-free addressing scheme,
the ROM contents, and the reference algorithm itself are correct. z3
`unknown` is never accepted as a pass; every bit-vector obligation is
bit-blasted to a decidable form.

`mutation_test.py` guards against vacuous proofs: it injects four realistic
bugs into the RTL model (wrong Barrett constant, swapped INTT subtraction
operands, one corrupted ROM entry, wrong address stride) and asserts each
mutant is killed with a concrete counterexample.

## The finding (`bug_intt_halving.py`)

**The released radix-2 INTT butterfly is missing the per-stage halving; the
radix-2 INTT output is scaled by 2¹⁰ mod q.**

| Artifact | per-stage ×½ |
|---|---|
| Paper (Sec 3.2/3.3, Eq. 23, Alg. 3) | ✔ folded into every INTT stage |
| `model_code/poly_mult_radix_2.py` | ✔ `op21` in every `DIF_RN_INTT` stage |
| Radix-4 RTL (`PE0.v:48-49`, `PE1.v:46-47`, `PE2.v:56/74`, `PE3.v:66-67`) | ✔ `modular_half` instantiated |
| **Radix-2 RTL (`compact_bf.v`)** | ✘ none — `modular_half.v` is shipped but instantiated nowhere in `hardware_code_radix-2/`; no N⁻¹ correction in `top_poly_mul.v`; no compensation in the twiddle ROM (check H) |

`bug_intt_halving.py` drives the bit-exact integer models of the released
datapaths through the full N=1024 transform, reading twiddles from the real
`tf_ROM.v` contents at the real `tf_address_generator.v` addresses, and shows
`INTT(NTT(x)) == 2^10 · x (mod q)` **exactly**, on every vector tried. The
released `tb_top.v` contains no self-check, so simulation does not catch it.

The same script validates the fix: mirroring `PE0.v`, route the `sel=1`
outputs of `compact_bf.v` through `modular_half`
(`bf_lower ← modular_half(add_out)`, `bf_upper ← modular_half(mult_out)`).
Both are combinational, so cycle counts are unchanged; with the patched
butterfly, `INTT(NTT(x)) == x`.

Reported upstream:
[xiang-rc/cfntt_ref#7](https://github.com/xiang-rc/cfntt_ref/issues/7).

## Yosys / SymbiYosys suite (`yosys/`)

The z3 suite proves the datapath on hand-built models; [`yosys/`](yosys/)
covers the remaining hardware-FV categories **directly on the RTL** (no
transcription), all green locally and in CI:

- **Pipeline timing** through the real `DFF`/`shift_4` chains: `modular_mul`
  == (a·b) mod q at latency 4 (BMC + k-induction), `compact_bf` == the
  DIT/DIF butterfly at latency 6 in both modes — verified COMPOSITIONALLY
  (leaf units proven equivalent to behavioural models in `fv_units` /
  `fv_modular_mul`, then abstracted, assume-guarantee style, so the
  butterfly obligations close in seconds).
- **Reset & power-up X**: outputs clear under reset from any state; per
  operating mode the butterfly is a feed-forward pipeline (register graph
  acyclic, input→output register path == 6, proven over the JSON netlist)
  so power-up X cannot persist.
- **LEC**: `equiv_opt -assert synth` per module (RTL vs gate netlist).
- **AGU / bank map re-proven on the RTL** (closing the z3 transcription
  gap), **CDC** (single clock domain, vacuously N/A), **parameterisation**
  (width sound; q/N hardcoded — documented), **constant-time addressing**
  (the AGU modules carry no data inputs).
- Control-FSM items are **blocked by the release** (`fsm.v` is empty) — the
  audit records the fact and will FAIL (demanding harness extension) if
  fsm.v ever appears upstream.

See [`yosys/README.md`](yosys/README.md) for the full 8-item coverage table
and the BMC-completeness argument.

## Proposed improvement (`proposed/`) — CFNTT-KRED

A formally verified redesign found by iterating view → implement → verify
over the reference: q = 3·2¹²+1 is a Proth prime, so the Barrett multiplier's
two constant multipliers can be replaced by shift-add K-RED folds — **3 → 1
hardware multipliers per butterfly**, −21% cells on the multiplier, −10% on
the butterfly, **with the issue-#7 INTT halving fix fused in** (the INTT
twiddle is derived from the same 9⁻¹-scaled ROM word by one `modular_half`).
Same ports, delay fabric and latencies as the reference.  Proofs: z3
full-domain reduction proof, SymbiYosys RTL pipeline + butterfly proofs,
bit-exact end-to-end polynomial multiplication, mutation probes.

A second, **visually-discovered** invention lives there too: the psi-fold
twiddle ROM (`w_rom[512+j] = 7·w_rom[j]` from the bit-reversed layout; ×7
is shift-sub) stores half the words and is proven equivalent to the shipped
`tf_ROM.v` for every address — **−79% cells** measured.  See
[`proposed/README.md`](proposed/README.md).

## Scope

- Control-FSM sequencing, the temporal half of memory-hazard freedom, and
  protocol compliance are **blocked by the release itself**:
  `hardware_code_radix-2/fsm.v` is empty (see
  [cfntt_ref#4](https://github.com/xiang-rc/cfntt_ref/issues/4)); the audit
  records this instead of skipping silently.
- The radix-4 tree is not covered (only its `modular_half` usage is cited).

## Layout

```
verify_radix2.py      the z3 verification (exact gate models + basis checks)
bug_intt_halving.py   the INTT halving finding: reproduction + fix validation
mutation_test.py      non-vacuity harness (4 injected bugs, all must be killed)
yosys/                RTL-level suite: SymbiYosys harnesses, LEC, audits
proposed/kred/        invention 1: CFNTT-KRED 1-multiplier, bug-fixed butterfly
proposed/rom-fold/    invention 2: psi-fold twiddle ROM (visually discovered)
cfntt_ref/            git submodule -> xiang-rc/cfntt_ref @ 8373a66 (ground truth)
```

## License

The verification code is MIT-licensed. The `cfntt_ref` submodule is the
upstream authors' work under its own license.
