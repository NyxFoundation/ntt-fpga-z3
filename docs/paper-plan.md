# Paper plan — status tracker

Goal: a submission-ready manuscript on the verified CFNTT improvements
(CFNTT-KRED butterfly + psi-fold twiddle ROM), the verification methodology,
and the upstream bug find. Working target venue: TCHES (fallback: FMCAD
case study). Every phase lands in docs/ as it completes.

| # | Phase | Output | Status |
|---|-------|--------|--------|
| 1 | Related-work sweep (novelty check: K-RED in hardware, twiddle generation/compression, verified NTT hardware, Falcon q=12289 accelerators) | `docs/related-work.md` | DONE (deep-read TODOs listed inside) |
| 2 | Novelty assessment; adjust claims | claims section in `docs/related-work.md` | DONE (C1-C3 adjusted) |
| 3 | FSM reconstruction + full-core RTL simulation (verilator) vs golden polymult | `proposed/fullcore/` + `docs/evaluation.md` §sim | DONE (stream sim PASS; banked-FSM recon = future work) |
| 4 | Synthesis numbers (yosys synth_xilinx open flow; PnR if toolchain available) | `docs/evaluation.md` §synth | DONE generic; PnR = TODO |
| 5 | Generalization: parameterized generator (Proth-prime q → KRED constants + folded ROM + auto-proofs; Kyber q=3329 as second instance) | `proposed/generator/` + `docs/generalization.md` | DONE (Falcon+Kyber, Kyber exhaustive + RTL) |
| 6 | Formal lemma write-ups (psi-fold lemma, K-RED bounds) | `docs/lemmas.md` | DONE (4 lemmas, numerically re-checked) |
| 7 | Manuscript draft (abstract → intro → background → design → verification → evaluation → related → conclusion) | `docs/paper/paper.md` | DONE (full draft; section TODOs + refs inline) |

Ground rules: honest novelty framing (K-RED is Longa–Naehrig 2016 known art;
the verified hardware fusion + psi-fold + bug-find + methodology are the
claims to defend); every number in the paper must be reproducible from this
repo's CI or scripts.


## Remaining before submission (post-draft)
- §2 Background prose (NTT/CFNTT paragraph): DONE.
- Bibliography: DONE (docs/paper/references.bib; paper References section
  uses citekeys). A few paywalled page-numbers marked [verify at camera-ready].
- Compact-FALCON diff: DONE at abstract level (complex-FFT compression vs
  our integer bit-reversed psi-fold); exact mechanism [verify] if PDF obtained.
- Whole-core PnR (needs the FSM reconstruction finished) for reviewer-grade
  LUT/FF/DSP/BRAM/Fmax; per-module PnR can go in now.
- Dockerfile + CITATION.cff + docs/artifact.md: DONE; Zenodo DOI = at release.
- FPGA-primitive cost table (open flow, proposed/fpga_cost.sh): DONE; corrected
  the ROM claim (−79% was generic gates; FPGA distributed-ROM is −11% LUT /
  −50% bits) and the DSP-for-LUT tradeoff, honestly, in evaluation.md + paper §7.
- Vivado-on-NixOS setup guide (docs/vivado-nixos.md): DONE; PnR run still TODO.
- Open-flow FPGA-primitive + logic-depth (ltp) numbers: DONE (proposed/fpga_cost.sh).
  Depth analysis DROVE an fold7 redesign (3 chained subs -> parallel compare +
  1 sub; LTP 31->26, area down, DSP-free), fully re-verified.
- Bibliography + Compact-FALCON diff: DONE (docs/paper/references.bib).
- Decide venue split (TCHES full paper vs FMCAD methodology case study).
