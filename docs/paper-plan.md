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
- Paper polish: DONE this pass — Fig.1 butterfly datapath (ASCII), fold7
  parallel-reduction pseudocode in Sec 4.2, and a positioning table vs
  CFNTT / Compact-FALCON in Sec 7 (both Barrett + full ROM; neither of our
  optimizations present).
- Paper builds: DONE — docs/paper/Makefile (pandoc -> PDF via xelatex, clean,
  no missing glyphs) + build README; CI generates the LaTeX skeleton on every
  push.  Citekeys are readable markers -> \cite{} at venue conversion.
- Sec 5 verification-summary table (Table 1) added.
- Editorial QA pass: reconciled the fold7-redesign numbers everywhere
  (ROM LUT 214->192 / -11%->-20% was stale in the prose + evaluation.md
  table after the parallel-reduction fold7); fixed 3 stale section refs
  (future-work was §8 pre-Related-Work-insertion, now §9); FF %s re-checked
  (mult -27%, core -14%, ROM -20% all consistent with the scripts).
- FSM reconstruction: partial progress — traced the datapath, fixed the
  write latency (8->10, pipe[9]) to remove X-corruption; result now
  well-defined but not yet cycle-accurate (twiddle/network alignment).
  Whole-core AREA unaffected (elaborates); streaming sim still passes.
  Full cycle-accuracy remains future work (needed only for timed run/Fmax).
- Dedicated Related Work section (Sec 8) added to the paper body,
  consolidating docs/related-work.md: NTT accelerators / conflict-free
  memory, modular reduction, twiddle storage, verified PQC hardware — with
  the honest positioning of each contribution.
- §2 Background prose (NTT/CFNTT paragraph): DONE.
- Bibliography: DONE (docs/paper/references.bib; paper References section
  uses citekeys). A few paywalled page-numbers marked [verify at camera-ready].
- Compact-FALCON diff: DONE — FULL TEXT read (PDF at docs/refs/, gitignored):
  it has NO twiddle compression (search-summary error), stores full FP64
  twiddle ROMs + Barrett NTT reduction, xc7a100t @134MHz.  Neither of our
  contributions overlaps it; strengthens novelty (latest Falcon-NTT still
  full-ROM + Barrett).
- Whole-core AREA: DONE (proposed/fpga_cost_core.sh): DSP 3->1, FF -14%,
  LUT +5%, BRAM unchanged.
- Post-route Fmax: DONE without Vivado (openXC7 nextpnr-xilinx on xc7a100t,
  proposed/pnr/fmax.sh): multiplier Fmax-NEUTRAL (K-RED ~230 vs Barrett
  ~233 MHz -> 3->1 DSP for free); butterfly ~122 vs ~164 MHz (-26%, partly
  the cost of the #7 correctness fix). Honest DSP/memory-for-Fmax tradeoff
  now in paper Sec 7/9 + abstract.
- Whole-core Fmax: DONE (proposed/pnr/fmax_core.sh): ~137 vs ~136 MHz -1%
  -- the butterfly's -26% DILUTES to ~1% at the core (memory/network/FSM
  dominate).  So the shipped core gets 3->1 DSP + bug fix + -50% twiddle
  bits at ~1% Fmax cost.  Remaining: cycle-accurate FSM for a functional
  timed run + optional Vivado confirmation.
- PDF render QA: fixed the positioning table overflowing the page (11->7
  cols; the 3 rightmost columns were silently clipped off-page), and cleared
  stale "Fmax needs Vivado/future work" lines in Sec 7 that contradicted the
  measured Fmax paragraph.  Full PDF builds clean (9pp, xelatex).
- KEY INFRA FINDING: Vivado is NOT required for routed Fmax — openXC7
  toolchain-nix (pin tag 0.8.2) gives it fully in nix.
- Dockerfile + CITATION.cff + docs/artifact.md: DONE; Zenodo DOI = at release.
- FPGA-primitive cost table (open flow, proposed/fpga_cost.sh): DONE; corrected
  the ROM claim (−79% was generic gates; FPGA distributed-ROM is −11% LUT /
  −50% bits) and the DSP-for-LUT tradeoff, honestly, in evaluation.md + paper §7.
- Vivado-on-NixOS setup guide (docs/vivado-nixos.md): DONE; PnR run still TODO.
- Open-flow FPGA-primitive + logic-depth (ltp) numbers: DONE (proposed/fpga_cost.sh).
  Depth analysis DROVE an fold7 redesign (3 chained subs -> parallel compare +
  1 sub; LTP 31->26, area down, DSP-free), fully re-verified.
- Bibliography + Compact-FALCON diff: DONE (docs/paper/references.bib).
- Venue: see docs/venue-assessment.md. Honest current level = workshop/
  preprint; best-fit submittable-now target = FMCAD Applications / DATE
  verification (lead with the verify->bug->redesign story). TCHES needs the
  Vivado-PnR upgrade + SOTA comparison first.
