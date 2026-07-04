# Artifact appendix

Everything in the paper is reproducible from this repository. The claims and
the scripts that regenerate them:

| Paper claim | Reproduce with |
|---|---|
| K-RED reducer == 9·A·B mod q, full domain | `uv run kred-butterfly/verify_kred.py` |
| Butterfly (both modes), ROM ≡ shipped, reset, latency | `run_all.sh` (SymbiYosys + audits + mutation sweep) |
| Full transform: NTT == ref, INTT(NTT(x)) == x (and the bug on the ref core) | `uv run verification/fullcore/run_stream.py` |
| Generalization: Kyber exhaustive + generated RTL | `uv run generator/kred_gen.py && uv run generator/gen_check.py` |
| Synthesis cost numbers | `yosys kred-butterfly/cost_report.ys` (+ the ROM stat in `docs/evaluation.md`) |
| Upstream bug (issue #7) reproduced | `uv run bug_intt_halving.py` |

## One-command reproduction

Native (Nix):

```sh
git clone --recurse-submodules https://github.com/NyxFoundation/FoldNTT
cd ntt-fpga-z3
nix shell nixpkgs#yosys nixpkgs#sby nixpkgs#yices nixpkgs#iverilog nixpkgs#uv \
  --command bash -lc 'run_all.sh \
    && uv run verification/fullcore/run_stream.py \
    && uv run generator/kred_gen.py \
    && uv run generator/gen_check.py'
```

Containerized (no Nix on the host):

```sh
docker build -t ntt-fpga-z3 .
docker run --rm ntt-fpga-z3
```

## Pinned versions (for the camera-ready / Zenodo deposit)

- this repository: commit `a962577` (update on deposit)
- `cfntt_ref` submodule (ground truth): `8373a66`
- toolchain: `yosys`, `sby`, `yices`, `iverilog`, `z3`, `uv` from
  `nixpkgs/nixos-unstable` (pin `NIXPKGS_REV` in the Dockerfile for a
  byte-reproducible image at deposit time).

The container image is self-tested: its build warms z3 and its default
`CMD` runs the whole proof/audit/sim suite; `run_stream.py`,
`kred_gen.py`, `gen_check.py` and `rom_fold_math.py` were confirmed passing
inside it. A runtime entrypoint resolves libstdc++ from the Nix store so the
pip-provided z3 wheel loads.

## Zenodo (TODO at submission)

Create a Zenodo record from the GitHub release (Zenodo↔GitHub integration),
which mints a DOI for the exact tagged commit; add the DOI badge here and to
the paper's Reproducibility section. `CITATION.cff` provides the metadata.

## Integrity check (2026-07-03)

Full reproducibility chain re-run green, and every FPGA number in the paper
verified equal to the live script output:

- z3 / math: `verify_radix2.py` VERIFIED; `kred_math`, `verify_kred`,
  `rom_fold_math`, `verify_rom_fold`, `kred_gen` all PASS/VALIDATED.
- RTL: `fv_kred.sby` (rst) PASS, `fv_rom_fold.sby` (bmc) PASS.
- Simulation: `run_stream.py` STREAM SIM PASS; `gen_check.py` (Kyber RTL)
  PASS; `gen_rom_fold.py` regenerates IN SYNC.
- Cost: `fpga_cost.sh` / `fpga_cost_core.sh` outputs match paper §7 exactly
  (modular_mul 29/101/3, kred 83/74/1; tf_ROM 241, fold 192; whole core
  ref 784/582/3/2, proposed 824/502/1/2).

The paper is internally consistent and fully reproducible from this repo.
