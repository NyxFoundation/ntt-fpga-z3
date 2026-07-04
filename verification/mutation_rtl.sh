#!/usr/bin/env bash
# Non-vacuity harness for the FoldNTT invention RTL proofs: inject a realistic bug
# into each Verilog module and assert the corresponding SymbiYosys harness
# FAILS with a counterexample.  A proof that passes on the real RTL is only
# meaningful if it fails on a wrong one.
#
# Mutated runs go to throwaway workdirs under /tmp (sby -d), so the clean
# PASS workdirs and their status records are never clobbered.  A mutated run
# only counts as "detected" if sby reports an actual counterexample
# (DONE (FAIL...)); a crash or config error is a harness bug, not a kill.
set -u
cd "$(dirname "$0")/.."
fails=0
MUTDIR=$(mktemp -d /tmp/foldntt_mutation.XXXXXX)
trap 'rm -rf "$MUTDIR"' EXIT
n=0

mutate() { # file, sed-expr, harness-dir, sby-file, task, label
  local f=$1 expr=$2 dir=$3 sby=$4 task=$5 label=$6
  local wd log rc
  n=$((n+1)); wd="$MUTDIR/m$n"; log="$MUTDIR/m$n.log"
  cp "$f" "$f.orig"
  sed -i "$expr" "$f"
  if cmp -s "$f" "$f.orig"; then
    echo "HARNESS BUG: mutation did not apply — $label"; fails=$((fails+1))
    rm "$f.orig"; return
  fi
  (cd "$dir" && sby -f -d "$wd" "$sby" "$task") >"$log" 2>&1; rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "MISSED  $label (proof still passes on mutated RTL!)"; fails=$((fails+1))
  elif grep -q "DONE (FAIL" "$log"; then
    echo "ok      $label"
  else
    echo "HARNESS ERROR (rc=$rc, no counterexample) — $label"; fails=$((fails+1))
    tail -5 "$log"
  fi
  mv "$f.orig" "$f"
}

mutate kred-butterfly/modular_mul_kred.v "s/17'd73734/17'd73733/" \
  kred-butterfly fv_kred.sby bmc "M1 kred fold offset 6q-1        -> fv_kred FAILs"
mutate kred-butterfly/compact_bf_v2.v "s/assign add_sel = sel == 1'b0 ? add_out : add_half;/assign add_sel = add_out;/" \
  kred-butterfly fv_bf_v2_intt.sby bmc "M2 drop add-path halving        -> fv_bf_v2_intt FAILs"
mutate kred-butterfly/compact_bf_v2.v "s/assign mux_out4 = sel == 1'b0 ? w_q1 : w_half;/assign mux_out4 = sel == 1'b0 ? w_q1 : w_q2;/" \
  kred-butterfly fv_bf_v2_intt.sby bmc "M3 skip op21-on-ROM twiddle     -> fv_bf_v2_intt FAILs"
mutate psi-fold-rom/tf_rom_fold.v "s/9'd7: base <= 14'd3638;/9'd7: base <= 14'd3639;/;s/9'd7: base <= 14'd3637;/9'd7: base <= 14'd3638;/" \
  psi-fold-rom fv_rom_fold.sby bmc "M4 corrupt one stored ROM word  -> fv_rom_fold FAILs"
mutate psi-fold-rom/tf_rom_fold.v "s/{base, 3'b000}/{1'b0, base, 2'b00}/" \
  psi-fold-rom fv_rom_fold.sby bmc "M5 fold7 shift 3 -> 2 (3x not 7x) -> fv_rom_fold FAILs"
mutate kred-butterfly/compact_bf_v2.v "s/assign sub_op1 = sel == 1'b0 ? mux_out1 : mux_out5;/assign sub_op1 = sel == 1'b0 ? mux_out5 : mux_out5;/" \
  kred-butterfly fv_bf_v2_ntt.sby bmc "M6 NTT sub operand corruption   -> fv_bf_v2_ntt FAILs"
mutate kred-butterfly/abstract_units_v2.v "s/(x_add < M && y_add < M)/(1'b0)/" \
  kred-butterfly fv_bf_v2_ntt.sby bmc "M7 abstraction domain guard off -> fv_bf_v2_ntt FAILs (anyseq junk is live)"
mutate ntt-core/ntt_core.v "s/rr       <= mode ? 11'd1023 : 11'd1;/rr       <= mode ? 11'd1023 : 11'd0;/" \
  ntt-core fv_core.sby bmc "M8 FSM rr starts at 0 (ROM addr wraps to 1023) -> fv_core FAILs"

if [ "$fails" -eq 0 ]; then echo "ALL RTL MUTATIONS DETECTED"; else echo "MUTATION SWEEP FAILED ($fails)"; exit 1; fi
