#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Emit the Kyber K-RED reducer RTL from kred_gen and verify it under
iverilog (edge + random product pairs).  Regenerates the checked-in
modular_mul_kred_kyber.v and fails if it drifts."""
import importlib.util, os, subprocess, sys, random

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("kg", os.path.join(HERE, "kred_gen.py"))
kg = importlib.util.module_from_spec(spec); spec.loader.exec_module(kg)

Q, PSI, N = 3329, 17, 256
plan = kg.plan_kred(Q)
rtl_path = os.path.join(HERE, "modular_mul_kred_kyber.v")
gen = kg.emit_rtl("Kyber", plan)
old = open(rtl_path).read() if os.path.exists(rtl_path) else ""
open(rtl_path, "w").write(gen)
if old and old != gen:
    print("FAIL: generated Kyber RTL drifted from checked-in copy"); sys.exit(1)

rng = random.Random(0)
edges = [0, 1, 2, Q - 1]
pairs = [(a, b) for a in edges for b in edges] + \
        [(rng.randrange(Q), rng.randrange(Q)) for _ in range(60000)]
open(os.path.join(HERE, "ky_a.hex"), "w").write("\n".join("%03x" % a for a, _ in pairs) + "\n")
open(os.path.join(HERE, "ky_b.hex"), "w").write("\n".join("%03x" % b for _, b in pairs) + "\n")

sim = os.path.join(HERE, "sim_ky")
subprocess.run(["iverilog", "-g2005", "-o", sim,
                os.path.join(HERE, "tb_kyber.v"), rtl_path], check=True)
r = subprocess.run(["vvp", sim], cwd=HERE, capture_output=True, text=True)
if "KYBER_RTL_PASS" in r.stdout:
    print("generated Kyber RTL: iverilog sweep PASS (%d pairs)" % len(pairs))
    print("KRED-GEN-CHECK PASS"); sys.exit(0)
print("FAIL:\n" + r.stdout[-500:]); sys.exit(1)
