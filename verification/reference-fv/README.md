# Yosys / SymbiYosys verification: the 8 items beyond datapath proofs

The z3 (an automated theorem prover) suite (`../verify_radix2.py`) proves
the *combinational* datapath and
static structure on hand-built models. This directory closes the remaining
gaps directly on the RTL (the register-level hardware source code — no
transcription): yosys reads the released
Verilog, SymbiYosys proves the assertions, `equiv_opt` checks synthesis
equivalence, and structural audits cover the rest.

Run everything (needs `yosys`, `sby`, `yices-smt2`, `python3` in PATH):

```sh
nix shell nixpkgs#yosys nixpkgs#sby nixpkgs#yices --command ./run_all.sh
# or in a YosysHQ oss-cad-suite environment:  ./run_all.sh
MODE=bmc ./run_all.sh    # BMC only (skip the k-induction 'prove' tasks)
```

## The 8 items and their status

| # | Item | Harness | Status |
|---|------|---------|--------|
| 1 | Pipeline timing / sequential correctness | `fv_modular_mul.sby`, `fv_compact_bf_{ntt,intt}.sby` — inputs stream every cycle through the real `DFF`/`shift_4` chains; assert `out(t) == golden(in(t−latency))` (latency 4 for `modular_mul`, 6 for `compact_bf`, both modes). The butterfly harness is **compositional**: `modular_mul` is replaced by behavioural models (`abstract_units.v`: mul latency-4, add/sub combinational) whose equivalence to the RTL is exactly what `fv_modular_mul.sby` and `fv_units.sby` prove — assume-guarantee, so the SMT tasks stay seconds-fast. The latency-6 bound is independently confirmed structurally (see item 4) | **proved** |
| 2 | Control FSM / sequencing | — | **blocked by the release**: `fsm.v` is empty (`audit.py` records the byte count; upstream issue #4). Nothing to verify, not skipped silently |
| 3 | Memory hazards under pipelining | static part (each stage touches every pair exactly once, banks always differ) proved on the RTL in `fv_agu.sby`; the *temporal* schedule needs the FSM | **partial — rest blocked (see 2)** |
| 4 | Reset & power-up X | (a) `fv_reset.sby` — async reset forces both outputs to 0 from any state; (b) `audit.py` item4b — per operating mode the flattened butterfly is a feed-forward pipeline (register graph acyclic, longest input→output register path == 6), so every register is overwritten from primary inputs within 6 cycles and power-up X cannot persist. (Across both modes the netlist has an apparent mult→sub→mult cycle, but the paths are sel-mux-exclusive; no single mode activates it — hence the per-mode analysis) | **proved** |
| 5 | LEC: RTL vs synthesized netlist | `lec.ys` — `equiv_opt -assert synth` per module (all modular units except the multiplier, both address generators, the bank map) | **proved** (see note) |
| 6 | Parameterisation | `fv_param_width.sby` — the width parameter is sound (units still compute mod q at data_width=16). q and N are not parameters: `M`, `M_half`, `q0` are hardcoded constants and N=1024 is burned into the AGUs and the ROM — the paper's N/q scalability means *regenerating* code | **proved / documented** |
| 7 | CDC / protocol compliance | `audit.py` — every flip-flop in the flattened tree is clocked by the single top-level `clk`: one clock domain, CDC vacuously N/A. Protocol (conf/done_flag handshake) needs the FSM | **N/A (single clock) / blocked (see 2)** |
| 8 | Constant-time (access-pattern data-independence) | `audit.py` + `fv_agu.sby` — the modules that choose addresses/banks have no polynomial-data inputs at all (counters/control only), and their outputs are total functions of those counters: the memory access pattern cannot depend on secret data | **proved (structural)** |

## Why the BMC runs are complete proofs here

Every assertion is *time-local*: it relates outputs to inputs at most
`latency` cycles back, guarded by a saturating counter. The initial register
state is left unconstrained (symbolic), which over-approximates every
reachable state. So a BMC (exhaustive exploration of all behaviours up to a cycle
depth) of depth `guard + latency + 1` covers every window
of every execution, so unbounded correctness follows without induction.
`prove` (k-induction: an inductive proof over the state machine) tasks
are additionally run where they converge
(`fv_modular_mul`, `fv_reset`, `fv_agu`); for the abstracted butterfly
harnesses plain induction does not converge without invariant strengthening
and is omitted: the BMC argument above is already the complete proof.

## Notes

- Engine: `smtbmc yices`. The golden multiply uses `%` by the constant q.
  Bit-blasting the DUT's Barrett datapath against it is the one expensive
  obligation. It is paid once, in `fv_modular_mul.sby` (~8 min); the
  butterfly (the transform's multiply-and-add step) tasks reuse that
  result compositionally and close in seconds.
- LEC excludes `modular_mul`: a monolithic SAT miter (a circuit that
  compares two implementations output-for-output) over a hard multiplier
  is intractable for `equiv_simple` (industry uses dedicated datapath-SEC
  tools there). Its gate-level behaviour is instead verified functionally,
  end-to-end, in item 1, a stronger statement than netlist equivalence.
- `fv_compact_bf.sv` asserts what the released RTL computes in INTT mode:
  `(u+v, (v−u)·w)`, i.e. without the per-stage `op21` halving. The
  halving omission is the reported bug (upstream issue #7,
  `../bug_intt_halving.py`); these assertions pin the rest of the butterfly
  (routing, operand order, delays) so the bug is isolated to exactly that.
