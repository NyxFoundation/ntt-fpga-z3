#!/usr/bin/env bash
# Build a two-column IEEE-conference PDF (IEEEtran) from the single-source
# paper.md.  IEEEtran is the format for DATE / ICCAD / DAC / ASP-DAC (the
# hardware venues in docs/venue-assessment.md), so this is a venue-neutral
# submission skeleton.  Run from docs/paper/ via nix (pandoc + texliveFull).
#
# pandoc emits longtable, which fails in two-column mode; we post-process each
# longtable into a both-column-spanning table*+tabular.  Wide verbatim (Fig.1,
# code) is shrunk to fit the 3.5in column; Fig.1 remains a candidate for a
# proper vector redraw at camera-ready.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

pandoc --from gfm+raw_attribute --to latex -s \
  -V documentclass=IEEEtran -V classoption=conference \
  -H "$here/preamble.tex" \
  "$here/../paper.md" -o "$here/paper_ieee.tex"

python3 "$here/fix_longtables.py" "$here/paper_ieee.tex"

# image paths in paper.md are relative to docs/paper/; we compile one level
# deeper, so point them one directory further up
sed -i 's|{\.\./assets/|{../../assets/|g' "$here/paper_ieee.tex"

# proper IEEE author block (pandoc emits \author{} as plain text)
sed -i 's|\\author{Masato Kamba (Nyx Foundation)}|\\author{\\IEEEauthorblockN{Masato Kamba}\\IEEEauthorblockA{Nyx Foundation}}|' "$here/paper_ieee.tex"

cd "$here"
xelatex -interaction=nonstopmode paper_ieee.tex >build.log 2>&1 || true
xelatex -interaction=nonstopmode paper_ieee.tex >build.log 2>&1 || true
echo "=== errors ==="; grep -E "^! " build.log | head -6 || echo none
echo "=== overfull >30pt ==="; grep -oE "Overfull \\\\hbox \([0-9]+" build.log | sort -rn | head -5 || echo none
grep -oE "Output written.*\([0-9]+ pages?" build.log | head -1
