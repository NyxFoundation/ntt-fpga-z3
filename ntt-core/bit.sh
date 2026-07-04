#!/usr/bin/env bash
# Build a Basys 3 (xc7a35tcpg236-1) bitstream for the NTT self-test with the
# FULLY OPEN, Vivado-free flow: yosys -> openXC7 nextpnr-xilinx -> FASM ->
# prjxray fasm2frames -> xc7frames2bit -> design.bit
#
# Run from the repo root (needs nix).  Output: ntt-core/build/design.bit
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=ntt-core/build; mkdir -p "$OUT"
XC=github:openXC7/toolchain-nix/0.8.2          # pinned working tag
PART=xc7a35tcpg236-1

echo "== resolving the open toolchain via nix =="
NPDIR=$(nix build "$XC#packages.x86_64-linux.nextpnr-xilinx" --no-link --print-out-paths)
CHDIR=$(nix build "$XC#packages.x86_64-linux.nextpnr-xilinx-chipdb.artix7" --no-link --print-out-paths)
PRJ=$(nix build "$XC#packages.x86_64-linux.prjxray" --no-link --print-out-paths)
FASM=$(nix build "$XC#packages.x86_64-linux.fasm" --no-link --print-out-paths)
NP="$NPDIR/bin/nextpnr-xilinx"
CHIPDB="$CHDIR/${PART%-*}.bin"
# prjxray-db (the fuzzed bit database) is a source dep of the chipdb build:
DB=$(nix eval --raw "$XC#packages.x86_64-linux.nextpnr-xilinx-chipdb.artix7.drvAttrs.src" 2>/dev/null || true)
[ -d "$DB/artix7/$PART" ] || DB=$(find /nix/store -maxdepth 2 -type d -path "*/artix7/$PART" 2>/dev/null | head -1 | xargs -r dirname | xargs -r dirname)

RTL="kred-butterfly/compact_bf_v2.v kred-butterfly/modular_mul_kred.v \
     psi-fold-rom/tf_rom_fold.v \
     cfntt_ref/hardware_code_radix-2/modular_add.v \
     cfntt_ref/hardware_code_radix-2/modular_substraction.v \
     cfntt_ref/hardware_code_radix-2/modular_half.v \
     cfntt_ref/hardware_code_radix-2/common_lib.v"

echo "== 1/4 yosys synth_xilinx =="
nix shell nixpkgs#yosys --command yosys -p \
  "read_verilog ntt-core/basys3_ntt_selftest.v ntt-core/ntt_core.v $RTL; \
   synth_xilinx -flatten -top basys3_ntt_selftest; delete t:\$scopeinfo; \
   write_json $OUT/design.json" >/dev/null

echo "== 2/4 nextpnr-xilinx place & route -> FASM =="
# no exit-code masking: a P&R failure aborts the flow immediately
"$NP" --chipdb "$CHIPDB" --xdc ntt-core/basys3.xdc --json "$OUT/design.json" \
      --fasm "$OUT/design.fasm" --write "$OUT/routed.json" \
      > "$OUT/nextpnr.log" 2>&1 \
  || { echo "nextpnr-xilinx FAILED:"; tail -30 "$OUT/nextpnr.log"; exit 1; }
grep -iE "Max frequency" "$OUT/nextpnr.log" || true
# timing gate: the core logic runs on clk/2 = 50 MHz, so EVERY reported clock
# must close at >= 50 MHz (and any explicit constraint FAIL aborts).
if grep -q "FAIL at" "$OUT/nextpnr.log"; then
  echo "TIMING GATE FAIL: a constrained clock missed its target"; exit 1
fi
FMIN=$(grep -oE "Max frequency for clock +'[^']+': +[0-9.]+" "$OUT/nextpnr.log" \
       | grep -oE '[0-9.]+$' | sort -n | head -1)
if [ -z "${FMIN:-}" ]; then
  echo "TIMING GATE FAIL: nextpnr reported no Fmax"; exit 1
fi
awk -v f="$FMIN" 'BEGIN {
  if (f+0 < 50.0) { print "TIMING GATE FAIL: min Fmax " f " MHz < 50 MHz"; exit 1 }
  print "timing gate OK: min Fmax " f " MHz >= 50 MHz (core clock)"
}'

echo "== 3/4 fasm2frames (prjxray db: $DB) =="
nix-shell -p "python311.withPackages(ps: with ps; \
    [textx antlr4-python3-runtime pyyaml numpy intervaltree simplejson])" \
  --run "PYTHONPATH=$FASM/lib/python3.11/site-packages:$PRJ/usr/share/python3 \
    python3 $PRJ/bin/fasm2frames --db-root $DB/artix7 --part $PART \
    $OUT/design.fasm > $OUT/design.frames"

echo "== 4/4 xc7frames2bit -> design.bit =="
"$PRJ/bin/xc7frames2bit" --frm_file "$OUT/design.frames" \
  --output_file "$OUT/design.bit" --part_name "$PART" \
  --part_file "$DB/artix7/$PART/part.yaml"

echo "== done =="; ls -la "$OUT/design.bit"; file "$OUT/design.bit"
echo "Load with:  openFPGALoader -b basys3 $OUT/design.bit   (or Vivado hw_manager)"
