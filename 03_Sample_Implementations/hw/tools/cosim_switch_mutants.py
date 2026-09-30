#!/usr/bin/env python3
# ============================================================================
# cosim_switch_mutants.py — does the Phase 5 cosimulation bite? Each mutant is
# one deliberate defect in a scratch copy of a file of hw/switch (or of the
# Formation's RH004); the scenario named with it runs against the copy and must
# FAIL. A mutant that passes is reported as SURVIVED.
#
#   python3 cosim_switch_mutants.py [--out DIR]
#
# Evidence class: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# ============================================================================
import argparse, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
DIRS = {"switch": os.path.join(HW, "switch"), "l2": os.path.join(HW, "l2")}

# (id, dir, file, the defect, text, replacement, scenario)
MUTANTS = [
    ("W1", "switch", "wpms_switch.v", "a GO's hand-over carries only its own items (earlier fired items dropped)",
     "ibx_wdata <= {23'd0, fired | go_items};", "ibx_wdata <= {23'd0, go_items};", "random"),
    ("W2", "switch", "wpms_switch.v", "GO_ALL fires only the issuing port's items",
     "if (x_go)        go_items = x_d[1] ? arm : (arm & (x_p3 ? arm_p3 : ~arm_p3));",
     "if (x_go)        go_items = (arm & (x_p3 ? arm_p3 : ~arm_p3));", "random"),
    ("W3", "switch", "wpms_switch.v", "inbox slots writable while their block is armed (no freeze)",
     "if (!x_slot_ok || frozen[xb]) rej_now = 1'b1;", "if (!x_slot_ok) rej_now = 1'b1;", "reject"),
    ("W4", "switch", "wpms_switch.v", "the sum of N checked against NMAX + 64",
     "if (go_sum > NMAX) go_bad = 1'b1;", "if (go_sum > NMAX + 64) go_bad = 1'b1;", "reject"),
    ("W5", "switch", "wpms_switch.v", "PR-1 not checked (a block twice in the sweep word)",
     "if (seen[blk] || !nv_nx[blk]) go_bad = 1'b1;", "if (!nv_nx[blk]) go_bad = 1'b1;", "reject"),
    ("W6", "switch", "wpms_switch.v", "PR-2 range closed below NMAX (N = NMAX refused)",
     "wire         x_inrange = ($signed(x_d) >= N_MIN) && ($signed(x_d) <= NMAX);",
     "wire         x_inrange = ($signed(x_d) >= N_MIN) && ($signed(x_d) < NMAX);", "origin"),
    ("W7", "switch", "wpms_switch.v", "APPLIED_SAMPLE one sweep early",
     "applied_sample <= n_take + 32'd1;", "applied_sample <= n_take;", "reject"),
    ("W8", "switch", "wpms_switch.v", "the apply step clears every fired item, not the take's",
     "fired   <= fired & ~ft;", "fired   <= 9'd0;", "random"),
    ("W9", "switch", "wpms_switch.v", "the take mirror ignores a write presented in the strobe clock",
     "ft <= fa_nx;  ft_seq <= fa_seq_nx;  ft_open <= 1'b1;", "ft <= fa;  ft_seq <= fa_seq;  ft_open <= 1'b1;", "timing"),
    ("W10", "l2", "wpms_formation.v", "the Formation's take ignores an arm write in the strobe clock (RH004 undone)",
     "take <= armed_nx; take_sweep <= sweep_armed_nx;", "take <= armed; take_sweep <= sweep_armed;", "timing"),
    ("W11", "switch", "wpms_system.v", "the bridge takes the fields as soon as it sees the toggle (no settling)",
     "parameter integer HOST_SETTLE  = 4", "parameter integer HOST_SETTLE  = 0", "bridge"),
    ("W12", "switch", "wpms_host_bridge.v", "a design reset forgets the editor's toggles (stale replay)",
     "wack <= wt;  rack <= rt;  rej_r <= 1'b0;  rdata_r <= 32'd0;",
     "wack <= 1'b0;  rack <= 1'b0;  rej_r <= 1'b0;  rdata_r <= 32'd0;", "bridge"),
    ("W13", "switch", "wpms_switch.v", "the ROM's end marker not recognised",
     "if (rom_q[43:32] == 12'hFFF) rom_st <= R_IDLE;", "if (rom_q[43:32] == 12'hFFE) rom_st <= R_IDLE;", "origin"),
    ("W14", "switch", "wpms_switch.v", "go-now forwards the mask without the arm bit (never handed over)",
     "ibx_wdata <= {1'b0, 1'b1, 13'd0, x_d[16:0]};", "ibx_wdata <= {15'd0, x_d[16:0]};", "reject"),
    ("W15", "switch", "wpms_switch.v", "RTOUT forwarded to the neighbouring block",
     "ibx_addr <= {5'b10000, xb};", "ibx_addr <= {5'b10000, xb ^ 3'd1};", "music"),
    ("W16", "switch", "wpms_switch.v", "a refused GO leaves its items armed",
     "if (go_bad) begin rej_now = 1'b1; arm <= arm & ~go_items; end",
     "if (go_bad) begin rej_now = 1'b1; end", "reject"),
    ("W17", "switch", "wpms_switch.v", "an empty take never publishes APPLIED",
     "if (ft_seq != applied_seq) begin", "if (ft != 9'd0 && ft_seq != applied_seq) begin", "random"),
    ("W18", "switch", "wpms_switch.v", "INBOX reads one slot off",
     "shadow_q <= shadow[xo[6:0]];", "shadow_q <= shadow[{xo[6:4], xo[3:0] ^ 4'd1}];", "origin"),
    ("W19", "switch", "wpms_switch.v", "COMMIT reads 'armed' only before the GO (fired items read unarmed)",
     "else if (x_commit)      rd_v = {1'b0, frozen[xb], 13'd0, cmask_v[17*xb +: 17]};",
     "else if (x_commit)      rd_v = {1'b0, arm[xb], 13'd0, cmask_v[17*xb +: 17]};", "random"),
    ("W20", "switch", "wpms_switch.v", "the take never carries its GO_SEQ (APPLIED_SEQ stuck)",
     "wire [31:0]  fa_seq_nx = (ibx_we && ibx_hand) ? ibx_seq : fa_seq;",
     "wire [31:0]  fa_seq_nx = fa_seq;", "random"),
    ("W21", "switch", "wpms_switch.v", "MG_RATE written into MG_TARGET",
     "8'h11: mg_rate   <= x_d;", "8'h11: mg_target <= x_d;", "random"),
    ("W22", "switch", "wpms_switch.v", "the ROM may restart itself (TEST_ORIGIN from port 3 accepted)",
     "8'h1C: if (x_p3) rej_now = 1'b1;", "8'h1C: if (1'b0) rej_now = 1'b1;", "origin+rom"),
]


def run_one(m, out):
    mid, dk, fname, what, old, new, case = m
    srcf = os.path.join(DIRS[dk], fname)
    text = open(srcf).read()
    n = text.count(old)
    if n != 1:
        return (mid, what, f"STALE ({n})", "")
    d = os.path.join(out, mid)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, fname), "w").write(text.replace(old, new))
    rep = os.path.join(d, "summary.txt")
    extra = case.endswith("+rom")
    case = case.replace("+rom", "")
    cmd = [sys.executable, os.path.join(HERE, "cosim_switch.py"), "--case", case, "--budget", "50",
           "--rtl", d, "--out", os.path.join(d, "run"), "--report", rep] + (["--rom-extra"] if extra else [])
    if case == "random":
        cmd += ["--seed", "1"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    t = open(rep).read() if os.path.exists(rep) else (r.stdout + r.stderr)
    first = next((l.strip() for l in t.splitlines() if l.strip().startswith("FAIL ")), "")
    return (mid, what, "KILLED" if r.returncode != 0 else "SURVIVED", first[:140])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HW, "switch", "build", "mutants"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with ThreadPoolExecutor(min(6, os.cpu_count() or 1)) as ex:
        rows = list(ex.map(lambda m: run_one(m, a.out), MUTANTS))
    print("cosim_switch_mutants: one defect per scratch copy — evidence class RTL-SIM")
    for mid, what, verdict, first in rows:
        print(f"  {mid:3s} {verdict:9s} {what}  ->  {first}")
    k = sum(r[2] == "KILLED" for r in rows)
    print(f"cosim_switch_mutants: {k}/{len(rows)} mutants killed")
    sys.exit(0 if k == len(rows) else 1)


if __name__ == "__main__":
    main()
