# Paper plan — status tracker

Goal: a submission-ready manuscript on the verified CFNTT improvements
(CFNTT-KRED butterfly + psi-fold twiddle ROM), the verification methodology,
and the upstream bug find. Working target venue: TCHES (fallback: FMCAD
case study). Every phase lands in docs/ as it completes.

| # | Phase | Output | Status |
|---|-------|--------|--------|
| 1 | Related-work sweep (novelty check: K-RED in hardware, twiddle generation/compression, verified NTT hardware, Falcon q=12289 accelerators) | `docs/related-work.md` | DONE (deep-read TODOs listed inside) |
| 2 | Novelty assessment; adjust claims | claims section in `docs/related-work.md` | DONE (C1-C3 adjusted) |
| 3 | FSM reconstruction + full-core RTL simulation (verilator) vs golden polymult | `proposed/fullcore/` + `docs/evaluation.md` §sim | IN PROGRESS |
| 4 | Synthesis numbers (yosys synth_xilinx open flow; PnR if toolchain available) | `docs/evaluation.md` §synth | pending |
| 5 | Generalization: parameterized generator (Proth-prime q → KRED constants + folded ROM + auto-proofs; Kyber q=3329 as second instance) | `proposed/generator/` + `docs/generalization.md` | pending |
| 6 | Formal lemma write-ups (psi-fold lemma, K-RED bounds) | `docs/lemmas.md` | pending |
| 7 | Manuscript draft (abstract → intro → background → design → verification → evaluation → related → conclusion) | `docs/paper/paper.md` | pending |

Ground rules: honest novelty framing (K-RED is Longa–Naehrig 2016 known art;
the verified hardware fusion + psi-fold + bug-find + methodology are the
claims to defend); every number in the paper must be reproducible from this
repo's CI or scripts.
