# newcore: a minimal, verified own-FSM NTT/INTT accelerator

A self-contained single-butterfly (one multiply-and-add unit) NTT/INTT
core for Falcon (N=1024, q=12289), built from the verified blocks but
with its own control FSM (state machine). Unlike the reverse-engineered CFNTT FSM (`../verification/fullcore/`,
which elaborates but does not round-trip), this core round-trips by
construction: `INTT(NTT(x)) == x`.

Why a fresh core: the reproducibility gap in the retrofit was the unreleased
CFNTT control FSM. Owning the FSM removes that gap. Instead of a core that
only round-trips at the streaming/module level, this is a complete
accelerator that runs end-to-end and fits a hobbyist board.

## Design (deliberately simple)

- **`compact_bf_v2`**: the 1-multiplier K-RED butterfly (latency 6), reused
  and already SMT/SbY-verified (SMT: an automated theorem prover). Its INTT mode carries the per-stage `1/2`, so
  the transform round-trips to `x` (the released core's bug is absent).
- **`tf_rom_fold`**: the ψ-fold twiddle ROM (the transform's precomputed
  multiplier constants; stores half the words).
- **coefficient RAM**: one inlined dual-port BRAM (on-chip memory block)
  array (1024×14 → 1×RAMB18);
  host port for load/read while idle.
- **own FSM**: nested loops `p`(stage)/`k`(group)/`j`(butterfly), one
  butterfly at a time (sequential, so a single dual-port BRAM suffices and
  correctness is easy to see and verify). The schedule is
  simulation-validated on every CI run against the golden streaming harness
  `../verification/fullcore/tb_stream.v` and an independent Python golden;
  the FSM's control invariants are additionally proven by k-induction (an
  inductive proof over the state machine; see "FSM safety" under Status).

`start`+`mode` (0=NTT, 1=INTT) runs a transform on the RAM contents; `done`
pulses when finished.

## Status

- **Functional round-trip: PASS.** `tb_ntt_core.v` loads `x`, runs NTT then
  INTT back-to-back, and checks `INTT(NTT(x)) == x` for all 1024 coefficients
  under iverilog, on 4 vectors (deterministic ramp + seeded random).
- **NTT golden: PASS.** Every post-NTT memory dump equals an independent
  Python golden built from the reference `tf_ROM.v` table (a common-mode bug
  in the shared RTL leaves cannot pass this).
- **INTT golden: PASS.** For INTT-only vectors `y`,
  `ntt_golden(INTT_rtl(y)) == y`; by bijectivity the core's INTT is the exact
  inverse of the golden NTT, not merely of its own NTT.
- **NTT cross-validation: PASS.** The post-NTT memory is bit-identical to the
  golden streaming harness (`../verification/fullcore/tb_stream.v`) on the same
  input.
  All checks: `python3 ntt-core/run_check.py` (exit 0 iff all pass; every dump
  is deleted before and required after each simulation, and simulator exit
  codes are checked, so stale files can never pass).
- **FSM safety: PROVEN** (`fv_core.sby`, SymbiYosys k-induction, datapath
  stubbed). Under arbitrary host/start behaviour, in both modes: every
  issued twiddle-ROM address is ≤ 1022 (discharging `tf_rom_fold`'s proven
  domain for this FSM), the two RAM write ports never target the same
  address (`hi ≤ 1023`, no truncation aliasing), the `busy`/`done` protocol
  holds, and the twiddle counter follows the closed forms
  `rr = 2^(9-p)+k` (NTT) / `rr = 2^(10-p)-1-k` (INTT).  Non-vacuity: mutation
  M8 (`rr` mis-seeded) makes the proof fail.
- **Synthesis** (yosys `synth_xilinx`, Artix-7): 1 DSP48 (the FPGA's
  dedicated multiplier block), 1 RAMB18, ~186 FF, ~600 LUT (the FPGA's
  register and logic cells). Fits a Basys 3 (`xc7a35t`: 90 DSP / 50 BRAM / 20.8k
  LUT).

## Run

```sh
# from the repo root (the testbench dumps to ntt-core/nc_*.hex)
python3 ntt-core/run_check.py
```

## On-board demo (Basys 3): Vivado-free bitstream

`basys3_ntt_selftest.v` self-checks `INTT(NTT(x))==x` on-chip and shows the
verdict on the LEDs (led0=done, led1=PASS, led2=FAIL, led[15:6]=mismatch
count).  It runs the core on a /2 BUFG clock (50 MHz); post-route the core
clock closes at ~70–95 MHz (run-dependent), and `bit.sh` gates the build
on every reported clock closing ≥ 50 MHz.  Simulated PASS
(`tb_selftest.v`, with the `sim_prims.v` BUFG stub).

```sh
bash ntt-core/bit.sh          # yosys -> openXC7 nextpnr -> FASM -> prjxray -> .bit
# -> ntt-core/build/design.bit  (Xilinx BIT for xc7a35tcpg236-1, NO Vivado)
openFPGALoader -b basys3 ntt-core/build/design.bit
```

Verified reproducibly: the full flow (synth, place and route — mapping
the logic onto the chip's physical fabric — FASM, fasm2frames,
xc7frames2bit) produces a valid 2.19 MB bitstream (the file that
configures the FPGA).

## Next (optional)

1. Throughput: pipeline within a stage (2-bank conflict-free) for ~1
   butterfly/cycle.
2. A 7-segment PASS/FAIL display for a nicer demo.
