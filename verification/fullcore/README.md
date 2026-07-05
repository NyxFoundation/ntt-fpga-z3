# Full-core / system-level RTL evidence

The module-level proofs (`../../kred-butterfly/`, `../../psi-fold-rom/`) establish each invented
block correct for all inputs. This folder raises that to the transform level
under a real Verilog simulator.

## What runs (`run_stream.py` — CI)

`tb_stream.v` drives the invented RTL (the register-level hardware source
code: `compact_bf_v2` +
`modular_mul_kred` + `tf_rom_fold`) through a complete N=1024 DIT-NR NTT and
DIF-RN INTT under iverilog, one butterfly (the transform's small
multiply-and-add step) per cycle (pipelined; results
collected via an index delay line: butterflies within a stage touch
disjoint indices, so back-to-back issue has no RAW hazard, and the pipeline
is drained between stages). The whole folded ROM is pre-read into `wrom[]`
first, exercising `tf_rom_fold` across its full address range.

Checks, on multiple random vectors:

- `NTT(x)` == the reference `DIT_NR_NTT` on the real twiddle table, and
- `INTT(NTT(x)) == x` exactly, i.e. the issue-#7 halving fix works at
  the full-transform level, not just per butterfly.

```
nix shell nixpkgs#iverilog --command uv run run_stream.py   # -> STREAM SIM PASS
```

This is orthogonal to cfntt_ref's banked-memory schedule: the inventions are
drop-in (same ports, same latency), so a correct controller sequences them
into a correct transform regardless of the conflict-free memory mapping.

## Reconstructed banked FSM (`fsm_recon.v`, `tb_fullcore.v`): future work

The released `fsm.v` is empty (upstream issue #4), so the shipped
`top_poly_mul` cannot elaborate as-is. `fsm_recon.v` is a reconstructed
controller with the exact port list `top_poly_mul` instantiates, and
`top_poly_mul_v2.v` swaps in the invented modules. This drives the actual
banked datapath (two conflict-free banks, address generators,
`network_bf_in/out`), which additionally exercises the memory system.

Status: partially reconstructed. Progress so far, from cycle-accurate
tracing (`tb_debug` in git history):

- The datapath write latency is 10 cycles (read path 4 + butterfly 6),
  not 8. With `wen` fixed to `pipe[9]` the earlier X-corruption is gone
  (writes no longer fire before the pipeline fills); `fsm_recon.v` carries
  this fix.
- The result is now well-defined but still numerically wrong
  (`INTT(NTT(x))` does not return `2¹⁰·x`), so the schedule is not yet
  cycle-accurate: the remaining gap is the precise alignment of the twiddle
  (precomputed multiplier constant) address/ROM read and the two operand/output networks (`network_bf_in`,
  `network_bf_out`, whose `sel` is `shift_7`-delayed) relative to the bank
  read/write, across the per-`k`-group twiddle changes.

A faithful cycle-accurate reconstruction of the unreleased FSM (the
control state machine) is a
research task in its own right and remains future work. It is not on the
critical path for the inventions' correctness: the streaming harness above
establishes the full transform at the RTL level, the SymbiYosys proofs
establish each module, and the whole-core area synthesizes from this
elaborating (not-yet-timed) core (`../fpga_cost_core.sh`). What the finished
FSM would add is a timed whole-core run and, with Vivado, routed Fmax
(the highest clock frequency the routed design sustains).

## Files

| File | Role |
|---|---|
| `tb_stream.v`, `run_stream.py` | pipelined full-transform harness over the invented RTL (the working, CI-run evidence) |
| `fsm_recon.v` | reconstructed control FSM (port-compatible with `top_poly_mul`; schedule not yet cycle-exact) |
| `top_poly_mul_v2.v` | shipped top with `compact_bf_v2` + `tf_rom_fold` swapped in |
| `tb_fullcore.v` | banked-core testbench (NTT then INTT, bank dumps; pending the FSM reconstruction) |
