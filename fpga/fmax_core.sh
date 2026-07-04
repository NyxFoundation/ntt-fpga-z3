#!/usr/bin/env bash
# WHOLE-CORE post-route Fmax (open flow, NO Vivado) on Artix-7 xc7a100t:
# reference top_poly_mul vs proposed top_poly_mul_v2.  Static timing only
# needs the netlist, so the core is linked against the reconstructed
# fullcore/fsm_recon.v to elaborate (area/Fmax valid; not the cycle-accurate
# functional schedule).  keep on datapath leaf modules prevents DCE.  Best of
# 3 placer seeds.  Requires NP, CHIPDB (see fmax.sh / README).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); root=$(cd "$here/../.." && pwd)
: "${NP:?}" "${CHIPDB:?}"; YOSYS=${YOSYS:-yosys}
RTL="$root/cfntt_ref/hardware_code_radix-2"; FC="$root/verification/fullcore"
common="$RTL/address_generator.v $RTL/conflict_free_memory_map.v $RTL/arbiter.v $RTL/network_bank_in.v $RTL/network_bf_in.v $RTL/network_bf_out.v $RTL/data_bank.v $RTL/tf_address_generator.v $RTL/modular_add.v $RTL/modular_substraction.v $RTL/modular_half.v $RTL/common_lib.v"
keep="setattr -mod -set keep 1 data_bank; setattr -mod -set keep 1 modular_mul; setattr -mod -set keep 1 modular_mul_kred; setattr -mod -set keep 1 tf_ROM; setattr -mod -set keep 1 tf_rom_fold;"
core() { local top=$1; shift; local w=$(mktemp -d) best=0 f
  $YOSYS -p "read_verilog $FC/fsm_recon.v $common $*; hierarchy -top $top; $keep synth_xilinx -flatten -top $top; delete t:\$scopeinfo; write_json $w/d.json" >/dev/null 2>&1
  { echo "set_property IOSTANDARD LVCMOS33 [get_ports {clk}]";
    echo "set_property IOSTANDARD LVCMOS33 [get_ports {rst}]";
    for i in 0 1 2; do echo "set_property IOSTANDARD LVCMOS33 [get_ports {conf[$i]}]"; done
    for i in 0 1 2 3; do echo "set_property IOSTANDARD LVCMOS33 [get_ports {done_flag[$i]}]"; done
    echo "create_clock -period 2.0 -name clk [get_ports clk]"; } > "$w/c.xdc"
  for s in 1 2 3; do
    f=$("$NP" --chipdb "$CHIPDB" --seed $s --xdc "$w/c.xdc" --json "$w/d.json" 2>&1 \
        | grep -oE "Max frequency for clock.*: [0-9.]+ MHz" | grep -oE "[0-9.]+" | tail -1 || echo 0)
    awk -v a="$f" -v b="$best" 'BEGIN{exit !(a>b)}' && best=$f
  done
  printf "%-16s %6s MHz (best of 3 seeds)\n" "$top" "$best"; rm -rf "$w"
}
core top_poly_mul    "$RTL/top_poly_mul.v" "$RTL/compact_bf.v" "$RTL/modular_mul.v" "$RTL/tf_ROM.v"
core top_poly_mul_v2 "$FC/top_poly_mul_v2.v" "$root/kred-butterfly/compact_bf_v2.v" "$root/kred-butterfly/modular_mul_kred.v" "$root/psi-fold-rom/tf_rom_fold.v"
