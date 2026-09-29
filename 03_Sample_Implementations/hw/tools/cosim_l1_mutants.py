#!/usr/bin/env python3
# ============================================================================
# cosim_l1_mutants.py — does the Phase 4 cosimulation bite? Each mutant is one
# deliberate defect in a scratch copy of an hw/l1 file (the files themselves are
# never touched); the test named with it runs against the copy and must FAIL.
# A mutant that passes is reported as SURVIVED.
#
#   python3 cosim_l1_mutants.py [--out DIR]
#
# Tests: units (cosim_l1.py units, 20,000 inputs), module (cosim_l1.py module,
# 60 sweeps), mgfade is not used (slow); grid (cosim_synth.py grid, test origin,
# 100 MHz budget: the I2S wire, the capture, the latency).
# Evidence class: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF Phase 4).
# ============================================================================
import argparse, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
L1 = os.path.normpath(os.path.join(HERE, "..", "l1"))

# (id, file, the defect, text, replacement, test)
MUTANTS = [
    ("X1", "wpms_l1_exp2.v", "exp2 table read one entry off",
     "t0   <= rom[L[29:22]];", "t0   <= rom[L[29:22] + 8'd1];", "units"),
    ("X2", "wpms_l1_exp2.v", "exp2 underflow clamp at <= instead of <",
     "und0 <= (L < -(54'sd31 <<< 30));", "und0 <= (L <= -(54'sd31 <<< 30));", "units"),
    ("X3", "wpms_l1_exp2.v", "exp2 polynomial without its second-order term",
     "p3 <= 31'h4000_0000 + q1_2 + c2q2[41:30];", "p3 <= 31'h4000_0000 + q1_2;", "units"),
    ("X4", "wpms_l1_exp2.v", "exp2 final shift one too far",
     "a <= pos4 ? 32'h7FFF_FFFF : und4 ? 32'd0 : (m >> sh4);",
     "a <= pos4 ? 32'h7FFF_FFFF : und4 ? 32'd0 : (m >> (sh4 + 5'd1));", "units"),
    ("S1", "wpms_l1_sin.v", "reflection by two's complement instead of bit inversion (Ch.2 §2.3.3 wording)",
     "xi_e <= phase[30] ? ~phase[29:0] : phase[29:0];", "xi_e <= phase[30] ? (30'd0 - phase[29:0]) : phase[29:0];",
     "units"),
    ("S2", "wpms_l1_sin.v", "Horner stage 3 scaled one bit wrong",
     "S3  <= SIN_C2 - p3a[51:SIN_SH3];", "S3  <= SIN_C2 - p3a[51:SIN_SH3+1];", "units"),
    ("S3", "wpms_l1_sin.v", "the sign of Q3/Q4 lost",
     "sin_out <= s_fa ? -$signed(v) : $signed(v);", "sin_out <= $signed(v);", "units"),
    ("E1", "wpms_l1_module.v", "phase engine: the second difference never added",
     "ph1 <= phi;           phi <= phi + d;          d <= d + pc;",
     "ph1 <= phi;           phi <= phi + d;          d <= d;", "module"),
    ("E2", "wpms_l1_module.v", "LAD2 zero-extended instead of sign-extended",
     "wire signed [53:0] w_c   = {{22{b_lad2[31]}}, b_lad2};", "wire signed [53:0] w_c   = {22'd0, b_lad2};", "module"),
    ("E3", "wpms_l1_module.v", "master gain not added to the level (Ch.4 §4.4.1)",
     "+ {{18{mg[31]}}, mg, 4'd0};", ";", "module"),
    ("E4", "wpms_l1_module.v", "product truncated by floor instead of toward zero",
     "p19 <= prod18[73] ? -((-prod18) >>> 8) : (prod18 >>> 8);", "p19 <= prod18 >>> 8;", "module"),
    ("E5", "wpms_l1_module.v", "RT.OUT routing swapped (L <- bit 1)",
     "wire signed [74:0] add_l = (add && rt19[0]) ? p75 : 75'sd0;",
     "wire signed [74:0] add_l = (add && rt19[1]) ? p75 : 75'sd0;", "module"),
    ("E6", "wpms_l1_module.v", "a product in the strobe clock left out of the closing sample",
     "acc_l_closed <= mute ? 75'sd0 : acc_l + add_l;", "acc_l_closed <= mute ? 75'sd0 : acc_l;", "module"),
    ("E7", "wpms_l1_module.v", "amplitude delay one clock short (a paired with the next bin's sin)",
     "wire [31:0] a17   = a_dly[D_SIN-D_EXP2-1];", "wire [31:0] a17   = a_dly[D_SIN-D_EXP2-2];", "module"),
    ("E8", "wpms_l1_module.v", "accumulation not stopped by the error flag (ruling 2026-09-28)",
     "wire               add   = v19 && !mute;", "wire               add   = v19;", "module"),
    ("N1", "wpms_l1_module.v", "the inspector captures the bin after the selected one",
     "if (v1 && pos1 == insp_pos) begin", "if (v1 && pos1 == insp_pos + 12'd1) begin", "module"),
    ("O1", "wpms_output_stage.v", "rounding replaced by truncation",
     "wire signed [SW-1:0] half = $signed({{(SW-1){1'b0}}, 1'b1}) <<< (39 + g2);",
     "wire signed [SW-1:0] half = 0;", "module"),
    ("O2", "wpms_output_stage.v", "saturation replaced by wrap",
     "wire signed [23:0] sl = (rnd_l > PMAX) ? 24'sh7FFFFF : (rnd_l < PMIN) ? 24'sh800000 : rnd_l[23:0];",
     "wire signed [23:0] sl = rnd_l[23:0];", "module"),
    ("O3", "wpms_output_stage.v", "MG jumps to its target (no slew)",
     "mg    <= mg_n[31:0];", "mg    <= tgt;", "module"),
    ("O4", "wpms_output_stage.v", "soft mute zeroes at once, not at the floor (C4-D6)",
     "zero1 <= err_mute || (soft_mute && mg == MG_FLOOR);", "zero1 <= err_mute || soft_mute;", "module"),
    ("I1", "wpms_i2s_master.v", "left-justified instead of I2S (no one-SCLK delay)",
     "if (j >= 6'd1 && j <= 6'd24)       bit_of = l[6'd24 - j];",
     "if (j <= 6'd23)                    bit_of = l[6'd23 - j];", "grid"),
    ("I2", "wpms_i2s_master.v", "the strobe at F_m (no Delta_pre)",
     "if (nxt == 8'd252) strobe_tgl <= ~strobe_tgl;", "if (nxt == 8'd0) strobe_tgl <= ~strobe_tgl;", "grid"),
    ("Y1", "wpms_strobe_sync.v", "a two-clock strobe (edge detector on two stages)",
     "assign strobe = (s2 ^ s3) && !rst;", "assign strobe = ((s1 ^ s2) || (s2 ^ s3)) && !rst;", "grid"),
]


def run_one(m, out):
    mid, fname, what, old, new, test = m
    src = open(os.path.join(L1, fname)).read()
    n = src.count(old)
    if n != 1:
        return (mid, what, f"STALE ({n})", "")
    d = os.path.join(out, mid)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, fname), "w").write(src.replace(old, new))
    rep = os.path.join(d, "summary.txt")
    if test == "units":
        cmd = [sys.executable, os.path.join(HERE, "cosim_l1.py"), "units", "--n", "20000"]
    elif test == "module":
        cmd = [sys.executable, os.path.join(HERE, "cosim_l1.py"), "module", "--sweeps", "60"]
    else:
        cmd = [sys.executable, os.path.join(HERE, "cosim_synth.py"), "grid", "--budget", "100", "--case", "origin"]
    r = subprocess.run(cmd + ["--rtl", d, "--out", os.path.join(d, "run"), "--report", rep],
                       capture_output=True, text=True)
    text = open(rep).read() if os.path.exists(rep) else (r.stdout + r.stderr)
    lines = text.splitlines()
    first = next((l.strip() for l in lines if l.strip().startswith("FAIL ") or "MISMATCH" in l), "") or \
        next((l.strip() for l in lines if "FAIL" in l), "")
    return (mid, what, "KILLED" if r.returncode != 0 else "SURVIVED", first[:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(L1, "build", "l1_mutants"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with ThreadPoolExecutor(min(6, os.cpu_count() or 1)) as ex:
        rows = list(ex.map(lambda m: run_one(m, a.out), MUTANTS))
    print("cosim_l1_mutants: one defect per scratch copy of the L1 RTL — evidence class RTL-SIM")
    for mid, what, verdict, first in rows:
        print(f"  {mid:3s} {verdict:9s} {what}  ->  {first}")
    k = sum(r[2] == "KILLED" for r in rows)
    print(f"cosim_l1_mutants: {k}/{len(rows)} mutants killed")
    sys.exit(0 if k == len(rows) else 1)


if __name__ == "__main__":
    main()
