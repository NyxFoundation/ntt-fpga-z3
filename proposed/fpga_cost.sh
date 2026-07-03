#!/usr/bin/env bash
# FPGA-primitive cost of the reference vs proposed modules, via the open
# flow (yosys synth_xilinx, 7-series).  Reproduces the LUT/FF/DSP/CARRY table
# in docs/evaluation.md.  Needs yosys in PATH:
#   nix shell nixpkgs#yosys --command proposed/fpga_cost.sh
set -euo pipefail
cd "$(dirname "$0")/.."
RTL=cfntt_ref/hardware_code_radix-2

declare -A F
F[modular_mul]="$RTL/modular_mul.v $RTL/common_lib.v"
F[modular_mul_kred]="proposed/kred/modular_mul_kred.v"
F[compact_bf]="$RTL/compact_bf.v $RTL/modular_mul.v $RTL/modular_add.v $RTL/modular_substraction.v $RTL/common_lib.v"
F[compact_bf_v2]="proposed/kred/compact_bf_v2.v proposed/kred/modular_mul_kred.v $RTL/modular_add.v $RTL/modular_substraction.v $RTL/modular_half.v $RTL/common_lib.v"
F[tf_ROM]="$RTL/tf_ROM.v"
F[tf_rom_fold]="proposed/rom-fold/tf_rom_fold.v"

printf "%-18s %5s %5s %4s %6s %5s\n" module LUT FF DSP CARRY4 LTP
for top in modular_mul modular_mul_kred compact_bf compact_bf_v2 tf_ROM tf_rom_fold; do
  reads=""
  for f in ${F[$top]}; do reads="$reads read_verilog $f;"; done
  tmp=$(mktemp)
  yosys -p "$reads synth_xilinx -flatten -top $top; tee -o $tmp stat; ltp" >/dev/null 2>/dev/null || true
  ltp=$(yosys -p "$reads synth_xilinx -flatten -top $top; ltp" 2>/dev/null | grep -oiE "length=[0-9]+" | grep -oE "[0-9]+" | tail -1)
  awk -v T="$top" '
    /Number of cells/ {lut=0;ff=0;dsp=0;carry=0}
    /^ *[0-9]+ +LUT[1-6]/ {lut+=$1}
    /^ *[0-9]+ +FD(CE|RE|PE|SE)/ {ff+=$1}
    /^ *[0-9]+ +DSP48E1/ {dsp+=$1}
    /^ *[0-9]+ +CARRY4/ {carry+=$1}
    END {printf "%-18s %5d %5d %4d %6d %5s\n", T, lut, ff, dsp, carry, L}
  ' L="$ltp" "$tmp"
  rm -f "$tmp"
done
