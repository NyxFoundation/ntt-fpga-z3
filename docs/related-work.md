# Related work & novelty assessment (Phase 1–2)

Status: first sweep complete (2026-07-03). Verdicts below drive the paper's
claims; deep-reads marked TODO must be finished before submission.

## 1. K-RED / Proth-prime reduction in hardware — **KNOWN ART, claim narrowed**

Shift-add K-RED-style reduction units are established in Kyber (q = 3329,
also Proth) NTT accelerators:

- Pipelined conflict-free Kyber NTT accelerators use shift-add modular
  reduction eliminating integer multipliers
  ([PLOS One 2025](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0333301),
  [preprint](https://www.preprints.org/manuscript/202504.2368)).
- "Optimized FPGA Architecture for Modular Reduction in NTT"
  ([eprint 2024/1890](https://eprint.iacr.org/2024/1890.pdf)) defines
  *Proth-l* primes and multiplication-free **K-RED-Shift** variants.
- Kyber modular polynomial multipliers with K-RED
  ([IEEE](https://ieeexplore.ieee.org/document/9996868/)).
- EMINEM (mixed-radix NTT for Falcon/Dilithium/HAWK,
  [ACM TRETS](https://dl.acm.org/doi/10.1145/3771287)) uses
  shift-and-add-based Barrett.

**Adjusted claim C1**: not "K-RED in hardware" but — the first *formally
verified*, *drop-in* K-RED retrofit of a published conflict-free NTT
accelerator (CFNTT, the Falcon prime q = 12289), in which the 9⁻¹ twiddle
scaling and the op21-on-ROM derivation additionally **fix a real bug in the
released artifact** (upstream issue #7: missing per-stage INTT halving),
with machine-checked equivalence down to the shipped ROM contents.
Cost result (3→1 DSP per butterfly, −21%/−10% cells) is a *retrofit*
result, positioned against CFNTT itself rather than against the Kyber SOTA.

## 2. Twiddle-factor storage reduction — **KNOWN GENRE, mechanism distinct**

- **Half-Memory TFG** ([Electronics 13(16):3128, 2024](https://www.mdpi.com/2079-9292/13/16/3128)):
  stores half the table and derives the rest via the **negation symmetry**
  `W^(n/2) ≡ −1 (mod q)` — i.e. `W^(k+n/2) = −W^k`, a subtraction.
- On-the-fly serial/parallel TFGs (same paper; also
  [FALCON-based TFG](https://www.researchgate.net/publication/379486985)
  — per-butterfly generation units built around a **modular multiplier** +
  BRAM for base constants; and
  [eprint 2025/1407](https://eprint.iacr.org/2025/1407) — a design tool
  with generic on-the-fly generation).
- "Compact FALCON FFT/NTT Accelerator"
  ([ResearchGate](https://www.researchgate.net/publication/393120423))
  mentions "twiddle factor compression" — **TODO: obtain and diff** (the
  one potentially-close prior work).

**Why the ψ-fold is not the Half-Memory TFG**: CFNTT-class in-place
accelerators store the *negacyclic* table in *bit-reversed* order,
`w_rom[i] = ψ^bitrev(i)` with ψ the 2N-th root. Its exponents range over
[0, N) — **no two entries differ by N in the exponent, so the negation
symmetry `ψ^(k+N) = −ψ^k` never applies inside the table.** The
bit-reversed layout instead maps *address*-halving to multiplication by ψ
(`w_rom[N/2+j] = ψ·w_rom[j]`), and for shift-friendly ψ (Falcon's ψ = 7:
`7x = (x<<3) − x`) the derivation is **multiplier-free** — unlike the
on-the-fly TFGs above. It recurses (ψ² = 49, fold7²), and the RTL is proven
pointwise-equivalent to the *shipped* ROM rather than re-derived from the
spec.

**Adjusted claim C2**: a storage-halving (recursively -75%) twiddle
derivation for **bit-reversed negacyclic tables where negation symmetry is
structurally unavailable**, multiplier-free for shift-friendly ψ, verified
equivalent to the shipped ROM at every address; −79% cells measured on the
CFNTT ROM.

## 3. Formal verification of PQC/NTT hardware — **active, but different axis**

The 2026 wave of machine-checked PQC-hardware verification targets
**masking / side-channel composition**, not functional correctness of the
arithmetic against a mathematical specification:

- Structural dependency analysis for masked NTT hardware (Adams Bridge
  ML-DSA/ML-KEM, 1.17M cells) — [arXiv:2604.15249](https://arxiv.org/abs/2604.15249)
- Machine-checked arithmetic-masking composition — [arXiv:2604.20793](https://arxiv.org/pdf/2604.20793),
  [arXiv:2604.25878](https://arxiv.org/pdf/2604.25878), [arXiv:2604.18717](https://arxiv.org/pdf/2604.18717)
- Masked Barrett reduction leakage bounds — [arXiv:2604.24670](https://arxiv.org/pdf/2604.24670)

**Claim C3** (methodology, complements rather than competes): end-to-end
*functional* verification of a published accelerator artifact — exact-width
gate models, divider-free congruence encodings (URem goldens diverge in
SMT; restate as nonnegative linear identities), compositional
assume-guarantee via leaf-unit equivalences, BMC-completeness for
time-local properties from unconstrained initial state, and
mutation-tested non-vacuity — which **found a real bug** (upstream #4/#7
artifacts) in a peer-reviewed accelerator's released RTL. All checks are
CI-reproducible from the public repo.

## 4. Provenance angle (discussion section only)

The ψ-fold was found by an LLM agent *visually reviewing a 3D model* of the
architecture inside a view → implement → verify loop. No prior art found
combining agentic RSI + visual floorplan review + machine-checked hardware
invention; however this claim belongs to a different venue (MLCAD/agents),
and in the TCHES/FMCAD paper it is one honest paragraph of "how this was
found", with the full derivation history public on the gallery timeline.

## Verdict for the paper

| Claim | Novelty risk | Mitigation |
|---|---|---|
| C1 verified K-RED retrofit + bug fix | low-medium (K-RED HW known) | position as verified retrofit + artifact bug find, not as new reduction |
| C2 ψ-fold for bit-reversed negacyclic ROMs | low (mechanism distinct from negation/OTF-multiplier art) | **must** diff the Compact-FALCON compression (TODO) |
| C3 FV methodology + real bug | low (masking-dominated field) | emphasize reproducibility + upstream issues |

Remaining TODOs before submission: obtain Compact FALCON FFT/NTT paper;
skim EMINEM for its Barrett variant details; cite Longa–Naehrig 2016 and
CFNTT (TCHES 2022) precisely; check hacspec/Jasmin verified *software* NTT
line of work for the related-work section.
