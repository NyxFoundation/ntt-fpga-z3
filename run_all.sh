#!/usr/bin/env bash
# The complete verification suite for BOTH inventions.  Needs yosys, sby,
# yices-smt2, python3 and uv in PATH — e.g.:
#   nix shell nixpkgs#yosys nixpkgs#sby nixpkgs#yices --command ./run_all.sh
# MODE=quick skips the ~15-min fv_kred bmc+prove (the one hard SMT task) and
# the mutation sweep; everything else runs.
set -euo pipefail
cd "$(dirname "$0")"
MODE="${MODE:-all}"

run_sby() {
  local dir=$1 f=$2; shift 2
  for task in "$@"; do
    echo "== $dir/$f [$task]"
    (cd "$dir" && sby -f "$f" "$task" | tail -1)
  done
}

echo "==== math + z3 (bit-exact models, full-domain datapath proofs)"
uv run kred-butterfly/kred_math.py | tail -1
uv run kred-butterfly/verify_kred.py | tail -1
uv run psi-fold-rom/rom_fold_math.py | tail -1
uv run psi-fold-rom/verify_rom_fold.py | tail -1

echo "==== generated RTL in sync (tables never hand-transcribed)"
uv run psi-fold-rom/gen_rom_fold.py >/dev/null
git diff --exit-code psi-fold-rom/tf_rom_fold.v && echo "tf_rom_fold.v in sync"

echo "==== SymbiYosys: RTL proofs"
if [ "$MODE" != quick ]; then
  run_sby kred-butterfly fv_kred.sby bmc prove rst
else
  run_sby kred-butterfly fv_kred.sby rst
  echo "== kred-butterfly/fv_kred.sby [bmc,prove] SKIPPED (MODE=quick)"
fi
run_sby kred-butterfly fv_bf_v2_ntt.sby bmc
run_sby kred-butterfly fv_bf_v2_intt.sby bmc
run_sby kred-butterfly fv_reset_v2.sby bmc prove
run_sby psi-fold-rom fv_rom_fold.sby bmc
run_sby ntt-core fv_core.sby bmc prove

echo "==== structural audits (lint, feed-forward/latency, single clock)"
python3 verification/audit_v2.py

if [ "$MODE" != quick ]; then
  echo "==== RTL mutation sweep (proofs must FAIL on broken RTL)"
  verification/mutation_rtl.sh
fi

echo "ALL FoldNTT INVENTION CHECKS PASS"
