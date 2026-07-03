# Evaluation (Phase 3–4)

## §sim — system-level RTL simulation (DONE)

`proposed/fullcore/run_stream.py` drives the **real invented RTL**
(`compact_bf_v2` + `modular_mul_kred` + `tf_rom_fold`) through a full N=1024
NTT and INTT under iverilog. Result: on every tested vector, the RTL
`NTT(x)` equals the reference `DIT_NR_NTT` on the real twiddle table, and
`INTT(NTT(x)) == x` **exactly** — the issue-#7 halving fix and the
9⁻¹-scaled folded ROM compose into a correct transform at the system level,
not merely per butterfly.

This closes the gap the module proofs leave: fv_bf_v2 proves the butterfly
== spec for every input; `run_stream.py` shows the specced modules,
sequenced by a controller and fed by the folded ROM, realize the whole
transform on real gates (iverilog).

Caveat (honest): cfntt_ref's *exact* banked-memory schedule is not
reproduced — the released `fsm.v` is empty (upstream #4). A reconstructed
FSM (`fsm_recon.v`) driving the banked datapath is included but not yet
cycle-accurate; it is future work and off the critical path, since the
inventions are drop-in with identical latency. See
`proposed/fullcore/README.md`.

## §synth — synthesis cost (DONE, generic; PnR pending)

All numbers from `yosys` generic synthesis (`synth -flatten -noabc`),
reproducible via `proposed/kred/cost_report.ys` and the ROM comparison. Cell
counts are technology-independent gate counts, not LUTs.

| Block | reference | proposed | Δ |
|---|---|---|---|
| modular multiplier | `modular_mul.v` 2176 cells, 101 FF, **3 mults** | `modular_mul_kred.v` 1724 cells, 74 FF, **1 mult** | −21% cells, −27% FF, −67% mults |
| butterfly | `compact_bf.v` 2820 cells, 297 FF, 3 mults | `compact_bf_v2.v` 2549 cells, 270 FF, 1 mult | −10% cells (**and INTT-correct**) |
| twiddle ROM | `tf_ROM.v` 7828 cells, 14322 stored bits | `tf_rom_fold.v` 1611 cells, 7168 stored bits | −79% cells, −50% bits |

These are technology-independent gate counts and are directionally useful,
but they *overstate the FPGA benefit for the ROM* (which maps to distributed
LUT-RAM, not gates). The FPGA-primitive numbers below are the ones the paper
relies on; read them, not the generic counts, for the ROM.

### FPGA primitives (open flow: `yosys synth_xilinx`, xc7 target)

The generic gate counts overstate the FPGA story in two honest ways —
resolved by mapping to real 7-series primitives. Per module, flattened
(reproduce: `nix shell nixpkgs#yosys --command proposed/fpga_cost.sh`):

| module | LUT | FF | **DSP48** | CARRY4 |
|---|---|---|---|---|
| `modular_mul` (Barrett) | 29 | 101 | **3** | 8 |
| `modular_mul_kred` | 83 | 74 | **1** | 14 |
| `compact_bf` (ref) | 158 | 297 | **3** | 24 |
| `compact_bf_v2` | 231 | 270 | **1** | 46 |
| `tf_ROM` | 241 | 14 | 0 | 0 |
| `tf_rom_fold` | 214 | 15 | 0 | 23 |

Honest reading (this is why per-FPGA numbers matter):

1. **DSP 3 → 1 holds on real primitives** — the headline. −67% DSP per
   butterfly, −27% FF on the multiplier. For NTT accelerators, which are
   almost always **DSP-bound** (many parallel butterflies, DSP is the
   scarce resource), this is the win that matters, and it scales ×d.
2. **K-RED trades DSPs for LUT/carry logic** — the multiplier's LUTs go
   29 → 83, the butterfly's 158 → 231. The shift-add folds are LUT+CARRY4.
   So on a *LUT-bound* design the trade could be neutral-to-negative; on the
   usual DSP-bound design it is a clear win. We report both directions
   rather than only the favourable one.
3. **The ROM's −79% was generic gates, not FPGA.** Mapped to primitives the
   ROM stays in distributed LUT-RAM (yosys does not infer BRAM for
   1023×14 here), so `tf_rom_fold` is only **−11% LUT** (241 → 214), with
   fold7 adding CARRY4. The real, defensible ROM claim is the **−50% stored
   bits**, which converts to a BRAM saving only when the table is large
   enough to be BRAM-mapped (bigger N, or a forced `ram_style="block"`);
   at Falcon's N=1024 as distributed ROM the LUT win is modest. We correct
   the paper accordingly.

### Timing proxy: logic depth (open flow, no PnR needed)

Fmax needs PnR, but yosys' longest-topological-path (`ltp`) gives a
technology-mapped **logic-depth** proxy that already answers the paper's two
timing questions. Per module (post-`synth_xilinx`, LUT/carry levels):

| module | LTP (logic levels) |
|---|---|
| `modular_mul` (Barrett) | 17 |
| `modular_mul_kred` | 21 |
| `tf_ROM` | 7 |
| `tf_rom_fold` | 26 |

- **K-RED vs Barrett (21 vs 17):** the K-RED fold adder chains add ~4 levels
  of logic. But `modular_mul`'s DSP48 counts as ~1 level in this proxy while
  hiding a full multiply, so the comparison understates Barrett; both units
  are latency-4 pipelined, so the *per-stage* path is what sets Fmax, and the
  K-RED stages are short adder chains. Directionally comparable; confirm with
  PnR.
- **fold7 on the ROM path (26 vs 7):** the derived-half read path is
  materially deeper than a plain ROM lookup — the ψ-fold's real cost is
  **combinational depth on the upper-half read**, not area. This is the
  honest risk for the ROM change. We already acted on it (below).

**Depth-driven redesign of fold7 (an RSI step from this very analysis).** The
first fold7 used three *chained* conditional subtractions (−4q, −2q, −q),
LTP 31. Recognizing `7x ∈ [0, 7q)`, we replaced them with six **parallel**
constant comparators that select `m·q` from precomputed multiples and a
**single** subtraction — LTP 31 → 26, LUT 214 → 192, CARRY4 23 → 18, still
DSP-free, and re-verified end-to-end (z3 `VERIFIED`, the shipped-ROM
equivalence miter, the full-transform sim, and the mutation sweep all pass on
the new datapath). A *pipelined* fold7 (one extra register) would remove the
depth from the ROM read entirely at +1 latency; we keep the combinational
version to preserve the drop-in 1-cycle ROM interface, and flag the
depth/latency trade for PnR.

### Vivado PnR (still TODO for Fmax + BRAM inference)

The open flow gives LUT/FF/DSP/CARRY but not **Fmax** and won't infer BRAM
the way Vivado does. Vivado numbers on the CFNTT part (Artix-7), v1 vs v2,
remain the camera-ready item — to (a) confirm fold7 closes timing on the ROM
path, (b) check the K-RED carry chains don't lengthen the critical path vs
Barrett, (c) get the BRAM story right for a BRAM-mapped ROM. Setup for
Vivado-on-NixOS is in `docs/vivado-nixos.md`. Whole-core numbers still need
the FSM reconstruction (§sim caveat).

## Reproducibility

Every number above regenerates from the public repo:
- `proposed/run_all.sh` — all module proofs + audits + mutation sweep
- `proposed/fullcore/run_stream.py` — the system-level simulation
- `proposed/kred/cost_report.ys` — the synthesis cost report
CI (`.github/workflows/verify.yml`) runs the proof/audit/sim suite on every push.
