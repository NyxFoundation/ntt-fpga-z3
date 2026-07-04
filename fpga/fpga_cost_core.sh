#!/usr/bin/env bash
# Whole-core FPGA-primitive cost: the reference top_poly_mul vs the proposed
# top_poly_mul_v2 (compact_bf_v2 + modular_mul_kred + tf_rom_fold), via the
# open flow (yosys synth_xilinx, 7-series).  Reproduces the whole-core table
# in docs/evaluation.md.  Needs yosys in PATH:
#   nix shell nixpkgs#yosys --command fpga/fpga_cost_core.sh
#
# Notes:
#  * The released fsm.v is empty (upstream #4), so we link the reconstructed
#    fullcore/fsm_recon.v to let the core ELABORATE.  This affects synthesis
#    (area) only; it is not the cycle-accurate schedule (see fullcore/README).
#  * top_poly_mul's only output is done_flag, so synthesis dead-code-eliminates
#    the entire datapath (banks/mult/ROM never reach a port).  We set `keep`
#    on the datapath leaf modules so the area is measured, matching the
#    (* DONT_TOUCH *) intent of the released RTL.
set -euo pipefail
cd "$(dirname "$0")/.."
RTL=cfntt_ref/hardware_code_radix-2
FC=verification/fullcore
common="$RTL/address_generator.v $RTL/conflict_free_memory_map.v $RTL/arbiter.v \
  $RTL/network_bank_in.v $RTL/network_bf_in.v $RTL/network_bf_out.v \
  $RTL/data_bank.v $RTL/tf_address_generator.v $RTL/modular_add.v \
  $RTL/modular_substraction.v $RTL/modular_half.v $RTL/common_lib.v"
keep="setattr -mod -set keep 1 data_bank;
  setattr -mod -set keep 1 modular_mul; setattr -mod -set keep 1 modular_mul_kred;
  setattr -mod -set keep 1 tf_ROM; setattr -mod -set keep 1 tf_rom_fold;"

measure() { # top, extra-files, outfile
  yosys -p "read_verilog $FC/fsm_recon.v $common $2; hierarchy -top $1; $keep \
    synth_xilinx -top $1; tee -o $3 stat" >/dev/null 2>&1
}
measure top_poly_mul    "$RTL/top_poly_mul.v $RTL/compact_bf.v $RTL/modular_mul.v $RTL/tf_ROM.v" /tmp/core_ref.txt
measure top_poly_mul_v2 "$FC/top_poly_mul_v2.v kred-butterfly/compact_bf_v2.v kred-butterfly/modular_mul_kred.v psi-fold-rom/tf_rom_fold.v" /tmp/core_v2.txt

printf "%-14s %6s %6s %5s %7s %7s\n" core LUT FF DSP48 RAMB18 CARRY4
for pair in "reference:/tmp/core_ref.txt" "proposed:/tmp/core_v2.txt"; do
  name=${pair%%:*}; f=${pair#*:}
  python3 - "$name" "$f" <<'PY'
import re,sys
name,f=sys.argv[1],sys.argv[2]
b=open(f).read(); b=b[b.rfind("=== design hierarchy ==="):]
sm=lambda p: sum(int(n) for n,_ in re.findall(r"^\s*(\d+)\s+("+p+r")\b", b, re.M))
print("%-14s %6d %6d %5d %7d %7d" % (name, sm(r"LUT[1-6]"), sm(r"FD\w+"),
      sm("DSP48E1"), sm(r"RAMB\w+"), sm("CARRY4")))
PY
done
