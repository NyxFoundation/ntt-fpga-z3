# IEEE two-column build (submission skeleton)

Builds a two-column **IEEEtran** conference PDF from the single-source
`../paper.md`. IEEEtran is the format for DATE / ICCAD / DAC / ASP-DAC (the
hardware venues in `../../venue-assessment.md`), so this is a venue-neutral
starting point for the hardware-paper route.

```sh
# from docs/paper/ , with nix (pandoc + texliveFull):
nix shell nixpkgs#pandoc nixpkgs#texliveFull --command bash ieee/build.sh
# -> ieee/paper_ieee.pdf
```

## What works

Title, abstract, two-column body, section structure, references, Greek
letters and most inline symbols, and **all four data tables** (auto-converted
from pandoc `longtable` to both-column-spanning `table*` by `fix_longtables.py`
— longtable fails in two-column mode). Page 1 is submission-quality.

**Fig.1 is now a TikZ vector figure** (embedded in `../paper.md` as a
`{=latex}` raw block via `gfm+raw_attribute`, a both-column-spanning
`figure*` with `\resizebox`, so it renders in *both* the single-column and
two-column builds). The datapath, the shaded changed blocks, and both
adder/subtractor inputs all render cleanly in two columns.

The two-column build now compiles with **no LaTeX errors and no overfull
boxes**: the equation-dense prose (§2/§3) was converted from inline Unicode
super/subscripts to proper LaTeX math (`$\log_2 N$`, `$2^{-1}$`,
`$\mathrm{INTT}(\mathrm{NTT}(x))=2^{10}x$`), which fixed the last overflow
and improved typography in **both** builds.

Remaining before a specific venue's camera-ready: swap the readable citekey
markers (`[cfntt]`, …) for `\cite{}` against `references.bib`, and apply the
chosen venue's exact class/options (page limit, copyright block). These are
mechanical and venue-specific.

## Files
| File | Role |
|---|---|
| `build.sh` | pandoc → IEEEtran → post-process → xelatex |
| `preamble.tex` | IEEEtran tweaks: mono font for Fig.1, Unicode→LaTeX maps |
| `fix_longtables.py` | longtable → two-column-spanning `table*` |
