# Build the paper. Markdown is the source of truth (paper.md).
#
# The canonical PDF is the two-column IEEEtran build (ieee/build.sh):
#   nix shell nixpkgs#pandoc nixpkgs#texliveFull --command make
# A quick single-column serif draft is also available:
#   nix shell nixpkgs#pandoc nixpkgs#texliveSmall --command make draft.pdf
PANDOC ?= pandoc
FLAGS  = --from gfm+raw_attribute --pdf-engine=xelatex -V geometry:margin=1in -V linkcolor:blue -V mainfont="DejaVu Serif" -V monofont="DejaVu Sans Mono" -H tikz-header.tex
# citekeys in the prose are readable markers ([cfntt], ...) resolving to
# references.bib; convert to \cite{} in the venue LaTeX class at submission.

paper.pdf: paper.md references.bib ieee/preamble.tex ieee/build.sh ieee/fix_longtables.py
	bash ieee/build.sh
	cp ieee/paper_ieee.pdf paper.pdf

draft.pdf: paper.md references.bib
	$(PANDOC) $(FLAGS) paper.md -o draft.pdf

paper.tex: paper.md references.bib
	$(PANDOC) $(FLAGS) --standalone paper.md -o paper.tex

clean:
	rm -f paper.pdf draft.pdf paper.tex

.PHONY: clean
