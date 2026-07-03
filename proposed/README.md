# Proposed improvements — two verified inventions

The output of the recursive **view → implement → verify** loop over the
reference design, one folder per invention:

| Folder | Invention | Trigger | Headline |
|---|---|---|---|
| [`kred/`](kred/) | **CFNTT-KRED butterfly** — K-RED shift-add reduction (q = 3·2¹²+1 is Proth, so 3·2¹² ≡ −1 mod q), factor 9 folded into 9⁻¹-scaled twiddles, op21-on-ROM fusion | source-grounded formal verification (Barrett spends 3 multipliers; issue #7) | multipliers/butterfly **3 → 1**, INTT bug **fixed inside the architecture** |
| [`rom-fold/`](rom-fold/) | **ψ-fold twiddle ROM** — `w_rom[512+j] = 7·w_rom[j]` from the bit-reversed layout; ×7 is shift-sub, so half the ROM is derived by a tiny fold7 gate | **visual review of the 3D model** (the ROM was the largest block left on the floorplan) | stored words **−50%** (recursively −75%), cells **−79%**, proven equal to the shipped ROM at every address |

Each folder is self-contained: the algorithm explained in its README, the
RTL, the bit-exact math model, the z3 full-domain proofs, the SymbiYosys
harnesses, and measured costs. The two compose: `compact_bf_v2` +
`modular_mul_kred` + `tf_rom_fold` replace `compact_bf` + `modular_mul` +
`tf_ROM` drop-in (same ports and latencies); the memory system, address
generators and conflict-free mapping are untouched.

Both inventions and their whole derivation history are visible step by step
on the gallery page of the `ntt-fpga` scene (visually-3d), including the
verification runs and the score trajectory.
