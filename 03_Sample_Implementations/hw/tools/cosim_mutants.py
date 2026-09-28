#!/usr/bin/env python3
# ============================================================================
# cosim_mutants.py — does the Phase 2 cosimulation bite? Each mutant is one
# deliberate defect put into a scratch copy of hw/l2/wpms_formation.v (the file
# itself is never touched); cosim_l2.py is run against the copy and must FAIL.
# A mutant that passes is reported as SURVIVED: a hole in the suite, not a pass.
#
#   python3 cosim_mutants.py [--random N] [--out DIR]
#
# Evidence class of the results: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
# ============================================================================
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
L2 = os.path.normpath(os.path.join(HERE, "..", "l2"))

# (id, the defect, text in wpms_formation.v, replacement)
MUTANTS = [
    ("M1", "store reads ignore pending slots (no forwarding from the inbox)",
     "wire [31:0] store_a   = pm_a[a_slot] ? pend_a : st_rd_a[a_slot];",
     "wire [31:0] store_a   = st_rd_a[a_slot];"),
    ("M2", "a datapath write to a pending slot does not cancel its copy",
     "if (dp_st_we && a_block == bp[2:0])  pn[a_slot] = 1'b0;",
     "if (1'b0)  pn[a_slot] = 1'b0;"),
    ("M3", "ADD saturates on positive overflow instead of wrapping (W-F30)",
     "OP_ADD: accm <= accm + src;",
     "OP_ADD: accm <= (!accm[31] && !src[31] && ((accm + src) >> 31)) ? 32'h7FFFFFFF : accm + src;"),
    ("M4", "BCP in the strobe's clock wins over the strobe (execute after strobe)",
     "copied <= 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;\n            end",
     "copied <= bcp_commit ? (copied | new_list) : 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;\n            end"),
    ("M5", "must-be-zero immediate not checked for operand-less instructions",
     "K_NONE:  e4 = (x_rid != 4'd0) || (x_imm != 16'd0);",
     "K_NONE:  e4 = (x_rid != 4'd0);"),
    ("M6", "the CUR alias follows ADRS instead of order[q]",
     "wire [2:0] a_block = (region == R_CUR) ? x_cur : adrs[6:4];",
     "wire [2:0] a_block = adrs[6:4];"),
    ("M7", "MAC realigns with a logical shift",
     "wire signed [64:0] mac_sh = mac_pe >>> shv;",
     "wire signed [64:0] mac_sh = mac_pe >> shv;"),
    ("M8", "bundle order: LP and LS0 swapped on the prefetch port",
     "assign pf_lp   = st_rd_p[2];  assign pf_ls0  = st_rd_p[15];",
     "assign pf_lp   = st_rd_p[15];  assign pf_ls0  = st_rd_p[2];"),
    ("M9", "EW2 lower bound off by one (N = N_MIN rejected)",
     "(($signed(pf_n) < N_MIN)",
     "(($signed(pf_n) <= N_MIN)"),
    ("M10", "K read at execute instead of with the issue (F-F10 alignment)",
     "SRC_K:    src = {20'd0, x_k};",
     "SRC_K:    src = {20'd0, tap_k};"),
    ("M11", "the violating STM still writes the store",
     "wire dp_st_we = x_commit && ((op == OP_STM) || is_store_dst) &&",
     "wire dp_st_we = x_go && ((op == OP_STM) || is_store_dst) &&"),
    ("M12", "BCP checks the sweep's sum N on the pre-copy N",
     "n_post[bn] = pe[0] ? ib_n[bn] : st_n[bn];",
     "n_post[bn] = st_n[bn];"),
    ("M13", "STP reads its source before the EW6 check (E5 wins over EW6)",
     "OP_STP:  if (temp[31]) x_err = ERR_EW6;                      // checked before the read\n                     else if (uses_ppm_src && rd_e5) x_err = ERR_E5;",
     "OP_STP:  if (uses_ppm_src && rd_e5) x_err = ERR_E5;\n                     else if (temp[31]) x_err = ERR_EW6;"),
    ("M14", "inbox_taken rises at BCP's edge, before the copy has landed",
     "if ((taken_due || bcp_commit) && pm_idle_next) begin",
     "if (taken_due || bcp_commit) begin"),
    ("M15", "the copy engine does not pause for a datapath store write",
     "wire cp_go = cp_any && !dp_st_we;",
     "wire cp_go = cp_any;"),
    ("M16", "STA TEMP also writes the store (destination ID ignored)",
     "wire is_store_dst = (op == OP_STA) && (x_rid == DST_STORE);",
     "wire is_store_dst = (op == OP_STA);"),
    ("M17", "E8 not raised on a left SFT overflow (the model raises it: SD-13)",
     "OP_SFT:  if (sft_ovf) x_err = ERR_E8;",
     "OP_SFT:  x_err = 5'd0;"),
    ("M18", "status view: phase bit inverted",
     "R_STAT:   rd_val = {23'd0, !x_pkt, sweep_a[3:0], x_q};",
     "R_STAT:   rd_val = {23'd0, x_pkt, sweep_a[3:0], x_q};"),
    ("M19", "no backstop: sum N checked only when a sweep item is taken",
     "wire         ew5        = (do_sweep && sw_invalid) || (chk_sum > NMAX);",
     "wire         ew5        = (do_sweep && sw_invalid) || (do_sweep && chk_sum > NMAX);"),
    ("M20", "a repeated block in the sweep item is not refused",
     "if (seen[blk]) sweep_invalid = 1'b1;",
     "if (1'b0) sweep_invalid = 1'b1;"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=400)
    ap.add_argument("--out", default=os.path.join(L2, "build", "mutants"))
    a = ap.parse_args()
    src = open(os.path.join(L2, "wpms_formation.v")).read()
    os.makedirs(a.out, exist_ok=True)
    rows, ok = [], True
    for mid, what, old, new in MUTANTS:
        n = src.count(old)
        if n != 1:
            rows.append((mid, what, f"STALE (pattern found {n} times)", "")); ok = False; continue
        d = os.path.join(a.out, mid)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "wpms_formation.v"), "w").write(src.replace(old, new))
        shutil.copy(os.path.join(L2, "wpms_decode.vh"), d)
        rep = os.path.join(d, "summary.txt")
        r = subprocess.run([sys.executable, os.path.join(HERE, "cosim_l2.py"), "--random", str(a.random), "--rtl", d,
                            "--out", os.path.join(d, "run"), "--report", rep], capture_output=True, text=True)
        text = open(rep).read() if os.path.exists(rep) else r.stdout + r.stderr
        caught = []
        for line in text.splitlines():
            m = re.match(r"\s+(\w+)\s+(\d+)\s+(\d+)\s+\d+\s+\d+", line)
            if m and m.group(1) != "total" and int(m.group(3)) < int(m.group(2)):
                caught.append(f"{m.group(1)} {int(m.group(2)) - int(m.group(3))}")
        inv = re.search(r"invariant violations: (\d+)", text)
        if inv and int(inv.group(1)): caught.append(f"invariant/protocol {inv.group(1)}")
        killed = r.returncode != 0
        if not killed: ok = False
        rows.append((mid, what, "KILLED" if killed else "SURVIVED", ", ".join(caught) or ("build failed" if killed else "")))
    print("cosim_mutants: each mutant is one defect in a scratch copy of wpms_formation.v — evidence class RTL-SIM")
    print(f"  {'id':4s} {'verdict':9s} defect  ->  failing cases by group")
    for mid, what, verdict, caught in rows:
        print(f"  {mid:4s} {verdict:9s} {what}  ->  {caught}")
    print(f"cosim_mutants: {sum(r[2] == 'KILLED' for r in rows)}/{len(rows)} mutants killed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
