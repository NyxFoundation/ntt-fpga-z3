# Post-route Fmax — open flow (no Vivado)

Real routed Fmax for the reference vs proposed multiplier and butterfly on
**Artix-7 xc7a100t**, using **openXC7's `nextpnr-xilinx`** — no Vivado, no
multi-GB AMD download.

## Tools (pin the working openXC7 tag — HEAD's flake is broken)

```sh
nix build github:openXC7/toolchain-nix/0.8.2#packages.x86_64-linux.nextpnr-xilinx
nix build github:openXC7/toolchain-nix/0.8.2#packages.x86_64-linux.nextpnr-xilinx-chipdb.artix7
export NP=<result-nextpnr>/bin/nextpnr-xilinx
export CHIPDB=<result-chipdb>/xc7a100tcsg324.bin
export YOSYS="nix shell nixpkgs#yosys --command yosys"
proposed/pnr/fmax.sh
```

(HEAD of openXC7 currently fails to evaluate — `nextpnr-xilinx` missing from
its nixpkgs binding; the tag `0.8.2` has a self-consistent `flake.lock` and
builds. The chipdb builds all 7-series parts from prjxray-db (~10-20 min,
heavy pypy pass) — worth caching.)

## Method

Each module is **register-wrapped** (`wrap.py`): every DUT input is driven
from an internal shift register and every output is registered then
XOR-reduced, so the only I/O is `clk` + `serial_in` + `serial_out`. This
(a) makes the timed path a true register-to-register critical path, and
(b) avoids the wide-module I/O-placement failures nextpnr hits when 40-80
ports must be pinned. Reported = best of 3 placer seeds.

## Result (see ../../docs/evaluation.md for the honest reading)

| module | Fmax (xc7a100t) |
|---|---|
| `modular_mul` (Barrett, 3 DSP) | ~233 MHz |
| `modular_mul_kred` (K-RED, 1 DSP) | ~230 MHz |
| `compact_bf` (reference, INTT-buggy) | ~164 MHz |
| `compact_bf_v2` (K-RED, INTT-correct) | ~122 MHz |

K-RED is **Fmax-neutral at the multiplier** (3→1 DSP for free), and the
butterfly trades ~26% clock for the DSP/memory savings (partly the cost of
*correctness* — the reference omits the §3 halving). A pipelined K-RED/fold
recovers most of it at +1 latency.

## Files
| File | Role |
|---|---|
| `fmax.sh` | the reproducible Fmax comparison (median of 3 seeds) |
| `wrap.py` | register-wrapper generator (reduces a module to clk + 2 pins) |
