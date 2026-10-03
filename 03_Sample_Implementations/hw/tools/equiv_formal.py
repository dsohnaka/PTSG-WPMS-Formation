#!/usr/bin/env python3
# ============================================================================
# equiv_formal.py — SD-22 step 1, proved: the logic RH005 / RH002 restructured
# computes what it computed before, for every input (SAT, Yosys).
#
#   1. the switch's GO check (wpms_switch RH002 against RH001): go_bad and
#      go_sum, for every sweep word, every N and every validity, NMAX 1,008
#      and 2,048;
#   2. the Formation's EW5 functions (RH005 against RH004): the sum of N over
#      the sweep word (tree against chain) and the repeat check (pairwise
#      against the running mask), for every word and every eight N;
#   3. the Formation's split enables (RH005): for every state and every input,
#      the enable each op's registers use (x_ok_split, the simulation check)
#      equals RH004's single commit, x_go && x_err == 0. The multiplier's and
#      the shifter's overflow flags and EW5 are cut into free inputs (the
#      claim then holds for any value they take).
# The old logic is taken from a git commit (e3d4985, the first fit's RTL) and
# the new from the working files; 1 and 2 are cut out of the sources between
# fixed markers, so the proof is about the text that is built. Since step 2
# these markers are gone from the working files: run step 1 against the step-1
# commit, --step 1 --new 8815e35.
#
# SD-22 step 2 (--step 2, the default; old logic from 8815e35):
#   4. the switch's GO path (RH003 against RH002), NMAX 1,008 and 2,048: where
#      the switch uses it (a GO, a go-now of a block or of the sweep word), the
#      items fired, the N and validity the GO leaves and the sweep word are
#      equal, for every request and every state; and the check of that state
#      (P, PR-1, PR-2, the sum of N against NMAX) gives the same verdict for
#      every sweep word, every N and every validity;
#   5. the Formation RH006, the whole module, from ANY state (no reset, every
#      register and memory word free): one clock later, the operand read ahead
#      equals the direct read whenever an instruction executes, and the late E8
#      equals the overflow seen in X; in every state, the idle test equals
#      RH005's and the split enables equal the commit. The EW5 lookahead in four
#      claims: one clock later the terms it reduced are the direct terms (when an
#      instruction executes) and its registers hold csa9 of them and the bound;
#      the direct sum is the tree of those terms; and, for any eight
#      sign-extended terms, csa9's two words add up to the tree minus NMAX + 1
#      (NMAX 1,008 and 2,048) — together, the reduced sum equals the direct sum
#      minus NMAX + 1 (chk_ew5, which simulation checks in every clock). The
#      claims are the module's chk_* wires (simulation section). The multiplier's
#      results are cut free (the claims hold for any value they take).
# Step 2's sums are carry-save adders against adder trees, a known hard case
# for the SAT solver inside Yosys; Yosys builds each problem and writes it as
# CNF (sat -dump_cnf), and CaDiCaL 1.9.5 (python-sat) solves it: UNSAT is the
# proof. Three negative controls show the flow finds a counterexample when there
# is one: the switch's check with the bound off by one, the Formation's pre-read
# with the BCP term removed (mutant M26) and its EW5 lookahead blind to a strobe
# (M27): each must come back SAT.
#
#   python3 equiv_formal.py [--step 1|2] [--ref COMMIT] [--new COMMIT] [--yosys yowasp-yosys] [--out DIR]
#
# Evidence class: formal (SAT, Yosys `sat -prove`). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SD-22 step 1).
# 002 2026-10-03       Claude Code   Add : SD-22 step 2 (checks 4 and 5, two negative controls); --step, --new;
#                                          the CNF solved by CaDiCaL (python-sat) when it is installed.
# ============================================================================
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
L2, SW = os.path.join(HW, "l2"), os.path.join(HW, "switch")
REF = {1: "e3d4985", 2: "8815e35"}


def git_show(commit, rel):
    r = subprocess.run(["git", "-C", HW, "show", f"{commit}:./{rel}"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git show {commit}:{rel}: {r.stderr.strip()}")
    return r.stdout


def between(text, start, end, what):
    i = text.find(start)
    if i < 0 or text.count(start) != 1:
        raise SystemExit(f"marker not found once ({what}): {start!r}")
    j = text.index(end, i) + len(end)
    return text[i:j]


def go_miter(old, new):
    end = "        if (go_sum > NMAX) go_bad = 1'b1;\n    end\n"
    mod = lambda name, blk: (f"module {name} (sw_nx, n_nx_v, nv_nx, go_bad, go_sum);\n"
                             "    parameter integer NMAX = 1008;\n"
                             "    input [27:0] sw_nx; input [95:0] n_nx_v; input [7:0] nv_nx;\n"
                             "    output go_bad; output [14:0] go_sum;\n" + blk + "endmodule\n")
    return (mod("go_old", between(old, "    reg         go_bad;", end, "switch RH001")) +
            mod("go_new", between(new, "    reg         go_bad;", end, "switch, working file")) + """
module go_miter #(parameter integer NMAX = 1008) (input [27:0] sw_nx, input [95:0] n_nx_v, input [7:0] nv_nx, output eq);
    wire b0, b1; wire [14:0] s0, s1;
    go_old #(.NMAX(NMAX)) u0 (sw_nx, n_nx_v, nv_nx, b0, s0);
    go_new #(.NMAX(NMAX)) u1 (sw_nx, n_nx_v, nv_nx, b1, s1);
    assign eq = (b0 == b1) && (s0 == s1);
endmodule
""")


def ew_miter(old, new):
    def funcs(text, what):
        blk = between(text, "    function signed [35:0] sum_n;", "    wire [255:0] n_all", what)
        return blk[:blk.rindex("    wire [255:0] n_all")]
    mod = lambda name, f: (f"module {name} (input [27:0] w, input [255:0] n_all, output [35:0] s, output inv);\n" + f +
                           "    assign s = sum_n(w, n_all);\n    assign inv = sweep_invalid(w);\nendmodule\n")
    return (mod("ew_old", funcs(old, "Formation RH004")) + mod("ew_new", funcs(new, "Formation, working file")) + """
module ew_miter (input [27:0] w, input [255:0] n_all, output eq_s, output eq_inv);
    wire [35:0] s0, s1; wire i0, i1;
    ew_old u0 (w, n_all, s0, i0);
    ew_new u1 (w, n_all, s1, i1);
    assign eq_s = (s0 == s1);
    assign eq_inv = (i0 == i1);
endmodule
""")


def go_ctx_miter(old, new):
    """The switch's GO path, from EXEC's fields and the state to what the switch uses."""
    start = "    wire         x_glob   = (x_a[11:8] == 4'h0);\n"
    head = ("    parameter integer NMAX = 1008;\n    parameter integer N_MIN = 32;\n"
            "    input [11:0] x_a; input [31:0] x_d; input x_we, x_p3; input [8:0] arm, arm_p3, fired;\n"
            "    input [135:0] cmask_v; input [95:0] n_st_v, n_fu_v; input [7:0] nv_st, nv_fu;\n"
            "    input [27:0] sw_st, sw_fu;\n"
            "    output [8:0] o_items; output [95:0] o_n_nx; output [7:0] o_nv_nx; output [27:0] o_sw_nx; output o_bad;\n"
            "    wire [8:0] frozen = arm | fired;\n")
    ports = "x_a, x_d, x_we, x_p3, arm, arm_p3, fired, cmask_v, n_st_v, nv_st, n_fu_v, nv_fu, sw_st, sw_fu, o_items, o_n_nx, o_nv_nx, o_sw_nx, o_bad"
    outs = ("    assign o_items = go_items; assign o_n_nx = n_nx_v; assign o_nv_nx = nv_nx;\n"
            "    assign o_sw_nx = sw_nx; assign o_bad = go_bad;\n")
    blk_old = between(old, start, "        if (go_sum > NMAX) go_bad = 1'b1;\n    end\n", "switch RH002")
    blk_new = between(new, start, "    wire        go_bad = go_pr || !go_low[15];", "switch, the new text")
    blk_new += new[new.index(blk_new) + len(blk_new):].split("\n", 1)[0] + "\n"
    return (f"module go_ctx_old ({ports}, o_ctx);\n" + head + "    output o_ctx;\n" + blk_old + outs +
            "    assign o_ctx = x_go || x_nowb || x_nows;\nendmodule\n" +
            f"module go_ctx_new ({ports});\n" + head + blk_new + outs + "endmodule\n" + """
module go_ctx_miter #(parameter integer NMAX = 1008) (
    input [11:0] x_a, input [31:0] x_d, input x_we, x_p3, input [8:0] arm, arm_p3, fired, input [135:0] cmask_v,
    input [95:0] n_st_v, n_fu_v, input [7:0] nv_st, nv_fu, input [27:0] sw_st, sw_fu, output eq);
    wire [8:0] i0, i1; wire [95:0] n0, n1; wire [7:0] v0, v1; wire [27:0] w0, w1; wire b0, b1, ctx;
    go_ctx_old #(.NMAX(NMAX)) u0 (.x_a(x_a), .x_d(x_d), .x_we(x_we), .x_p3(x_p3), .arm(arm), .arm_p3(arm_p3),
        .fired(fired), .cmask_v(cmask_v), .n_st_v(n_st_v), .nv_st(nv_st), .n_fu_v(n_fu_v), .nv_fu(nv_fu),
        .sw_st(sw_st), .sw_fu(sw_fu), .o_items(i0), .o_n_nx(n0), .o_nv_nx(v0), .o_sw_nx(w0), .o_bad(b0), .o_ctx(ctx));
    go_ctx_new #(.NMAX(NMAX)) u1 (.x_a(x_a), .x_d(x_d), .x_we(x_we), .x_p3(x_p3), .arm(arm), .arm_p3(arm_p3),
        .fired(fired), .cmask_v(cmask_v), .n_st_v(n_st_v), .nv_st(nv_st), .n_fu_v(n_fu_v), .nv_fu(nv_fu),
        .sw_st(sw_st), .sw_fu(sw_fu), .o_items(i1), .o_n_nx(n1), .o_nv_nx(v1), .o_sw_nx(w1), .o_bad(b1));
    assign eq = !ctx || (i0 == i1 && n0 == n1 && v0 == v1 && w0 == w1 && b0 == b1);
endmodule
""")


def go_chk_miter(old, new, bound_off=False):
    """The switch's check of the state a GO leaves: (sw_nx, n_nx_v, nv_nx) -> go_bad."""
    head = ("    parameter integer NMAX = 1008;\n"
            "    input [27:0] sw_nx; input [95:0] n_nx_v; input [7:0] nv_nx; output o_bad;\n")
    blk_old = between(old, "    reg         go_bad;", "        if (go_sum > NMAX) go_bad = 1'b1;\n    end\n", "switch RH002")
    blk_new = between(new, "    localparam [15:0] NEG_NMAX1", "    wire        go_bad = go_pr || !go_low[15];", "switch, the new text")
    blk_new += new[new.index(blk_new) + len(blk_new):].split("\n", 1)[0] + "\n"
    if bound_off:                                             # the negative control: the bound off by one
        blk_new = blk_new.replace("-(NMAX + 1);", "-(NMAX + 2);")
    return ("module go_chk_old (sw_nx, n_nx_v, nv_nx, o_bad);\n" + head + blk_old + "    assign o_bad = go_bad;\nendmodule\n" +
            "module go_chk_new (sw_nx, n_nx_v, nv_nx, o_bad);\n" + head + blk_new + "    assign o_bad = go_bad;\nendmodule\n" + """
module go_chk_miter #(parameter integer NMAX = 1008) (input [27:0] sw_nx, input [95:0] n_nx_v, input [7:0] nv_nx, output eq);
    wire b0, b1;
    go_chk_old #(.NMAX(NMAX)) u0 (.sw_nx(sw_nx), .n_nx_v(n_nx_v), .nv_nx(nv_nx), .o_bad(b0));
    go_chk_new #(.NMAX(NMAX)) u1 (.sw_nx(sw_nx), .n_nx_v(n_nx_v), .nv_nx(nv_nx), .o_bad(b1));
    assign eq = (b0 == b1);
endmodule
""")


def ew_arith_miter(new):
    """csa9's two words against the tree of sum_n, for any eight sign-extended terms (the working text)."""
    funcs = "".join(between(new, start, "    endfunction\n", what) for start, what in (
        ("    function signed [35:0] sum_n;", "sum_n"), ("    function [71:0] csa;", "csa"),
        ("    function [71:0] csa9;", "csa9")))
    return ("module ew_arith #(parameter integer NMAX = 2048) (input [255:0] n, output eq);\n"
            "    localparam [35:0] NEG_NMAX1 = -(NMAX + 1);\n" + funcs +
            "    localparam [27:0] W8 = {3'd7, 3'd6, 3'd5, 3'd4, 3'd3, 3'd2, 3'd1, 3'd0, 4'd8};   // P = 8, blocks 0..7\n"
            "    reg [323:0] t;\n    integer k;\n"
            "    always @* begin\n"
            "        for (k = 0; k < 8; k = k + 1) t[36*k +: 36] = {{4{n[32*k + 31]}}, n[32*k +: 32]};\n"
            "        t[288 +: 36] = NEG_NMAX1;\n    end\n"
            "    wire [71:0] r = csa9(t);\n"
            "    assign eq = (r[71:36] + r[35:0] == sum_n(W8, n) - (NMAX + 1));\nendmodule\n")


def cadical():
    try:
        from pysat.solvers import Solver
        from pysat.formula import CNF
        return Solver, CNF
    except ImportError:
        return None


def prove_cnf(yosys, script, log, cwd, want_unsat=True):
    """Yosys builds the problem (the script ends in a sat call) and writes its CNF; CaDiCaL solves it."""
    import time
    cnf = os.path.splitext(os.path.basename(log))[0] + ".cnf"
    p = subprocess.Popen([yosys, "-p", f"{script} -dump_cnf {cnf}"], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, cwd=cwd)
    text, size = [], None
    for line in p.stdout:
        text.append(line)
        m = re.search(r"Solving problem with (\d+) variables and (\d+) clauses", line)
        if m:                                                 # the CNF is written: Yosys's own solver not needed
            size = (int(m.group(1)), int(m.group(2))); p.kill(); break
    p.wait()
    if size is None:
        open(log, "w").write("".join(text))
        return False, "Yosys did not reach the SAT problem"
    Solver, CNF = cadical()
    f = CNF(from_file=os.path.join(cwd, cnf))
    t0 = time.time()
    with Solver(name="cadical195", bootstrap_with=f.clauses) as s:
        sat = s.solve()
    dt = time.time() - t0
    os.unlink(os.path.join(cwd, cnf))
    verdict = "SAT (a counterexample exists)" if sat else "UNSAT (no counterexample: proved)"
    open(log, "w").write("".join(text) + f"\nCaDiCaL 1.9.5 (python-sat): {verdict} in {dt:.1f} s\n")
    return (not sat) if want_unsat else sat, f"{size[0]:,} variables, {size[1]:,} clauses; CaDiCaL {dt:.0f} s"


def prove(yosys, script, log, cwd):
    r = subprocess.run([yosys, "-p", script], capture_output=True, text=True, cwd=cwd)
    open(log, "w").write(r.stdout + r.stderr)
    m = re.search(r"Solving problem with (\d+) variables and (\d+) clauses", r.stdout)
    ok = r.returncode == 0 and "SAT proof finished - no model found: SUCCESS!" in r.stdout
    size = f"{int(m.group(1)):,} variables, {int(m.group(2)):,} clauses" if m else "no SAT problem"
    return ok, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, choices=(1, 2), default=2)
    ap.add_argument("--ref", default=None, help="the old revisions' commit (step 1: e3d4985, step 2: 8815e35)")
    ap.add_argument("--new", default=None, help="the new revisions' commit (default: the working files)")
    ap.add_argument("--yosys", default=shutil.which("yosys") or "yowasp-yosys")
    ap.add_argument("--out", default=os.path.join(HW, "l2", "build", "equiv_formal"))
    a = ap.parse_args()
    ref = a.ref or REF[a.step]
    os.makedirs(a.out, exist_ok=True)
    new_text = lambda rel: git_show(a.new, rel) if a.new else open(os.path.join(HW, rel)).read()
    sw_old, sw_new = git_show(ref, "switch/wpms_switch.v"), new_text("switch/wpms_switch.v")
    f_old, f_new = git_show(ref, "l2/wpms_formation.v"), new_text("l2/wpms_formation.v")
    flow = "proc; flatten; opt -fast"
    # the Formation as a whole, read from the run directory (yowasp's sandbox sees it)
    open(os.path.join(a.out, "wpms_formation.v"), "w").write(f_new)
    open(os.path.join(a.out, "wpms_decode.vh"), "w").write(new_text("l2/wpms_decode.vh"))
    whole = lambda cut: ("read_verilog -nosynthesis wpms_formation.v; hierarchy -top wpms_formation; proc; "
                         "expose w:x_ok_split w:x_commit w:chk_pre w:chk_e8 w:chk_idle w:chk_tm w:chk_csa w:chk_tree; "
                         "delete t:$print; "
                         f"expose -cut {cut}; memory; opt -fast; async2sync; dffunmap; ")
    if a.step == 1:
        go_v, ew_v = "go_miter.v", "ew_miter.v"
        open(os.path.join(a.out, go_v), "w").write(go_miter(sw_old, sw_new))
        open(os.path.join(a.out, ew_v), "w").write(ew_miter(f_old, f_new))
        checks = [(f"switch GO check (go_bad, go_sum), NMAX {n}", "go_" + str(n),
                   f"read_verilog {go_v}; chparam -set NMAX {n} go_miter; hierarchy -top go_miter; {flow}; "
                   "sat -prove eq 1 -verify") for n in (1008, 2048)]
        checks += [("Formation EW5: the sum of N (tree against chain)", "ew_sum",
                    f"read_verilog {ew_v}; hierarchy -top ew_miter; {flow}; sat -prove eq_s 1 -verify"),
                   ("Formation EW5: the repeat check (pairwise against running mask)", "ew_inv",
                    f"read_verilog {ew_v}; hierarchy -top ew_miter; {flow}; sat -prove eq_inv 1 -verify"),
                   ("Formation: split enables = RH004's commit, every state and input", "split",
                    "read_verilog -nosynthesis wpms_formation.v; "
                    "hierarchy -top wpms_formation; proc; expose w:x_ok_split w:x_commit; delete t:$print; "
                    "expose -cut w:mul_ovf w:mac_ovf w:sft_ovf w:ew5; memory; opt -fast; async2sync; dffunmap; "
                    "select -assert-count 1 w:x_ok_split; sat -seq 1 -prove x_ok_split x_commit -verify")]
    else:
        gc_v, gk_v, gx_v = "go_ctx_miter.v", "go_chk_miter.v", "go_chk_off.v"
        open(os.path.join(a.out, gc_v), "w").write(go_ctx_miter(sw_old, sw_new))
        open(os.path.join(a.out, gk_v), "w").write(go_chk_miter(sw_old, sw_new))
        open(os.path.join(a.out, gx_v), "w").write(go_chk_miter(sw_old, sw_new, bound_off=True))
        checks = [(f"switch GO path, where it is used: items, N, validity, sweep word (RH003 = RH002), NMAX {n}",
                   "goctx_" + str(n),
                   f"read_verilog {gc_v}; chparam -set NMAX {n} go_ctx_miter; hierarchy -top go_ctx_miter; {flow}; "
                   "sat -prove eq 1") for n in (1008, 2048)]
        checks += [(f"switch GO check of that state: P, PR-1, PR-2, sum of N (carry-save = tree), NMAX {n}",
                    "gochk_" + str(n),
                    f"read_verilog {gk_v}; chparam -set NMAX {n} go_chk_miter; hierarchy -top go_chk_miter; {flow}; "
                    "sat -prove eq 1") for n in (1008, 2048)]
        controls = [("negative control: the switch's check with the bound off by one (must be SAT)", "ctl_gochk",
                     f"read_verilog {gx_v}; chparam -set NMAX 1008 go_chk_miter; hierarchy -top go_chk_miter; {flow}; "
                     "sat -prove eq 1")]
        two = "sat -seq 2 -prove-skip 1 -prove"                    # step 1 free, the claim at step 2
        checks += [("Formation: the operand read ahead = the direct read, one clock from any state", "pre",
                    whole("w:mul_r w:mac_r") + f"{two} chk_pre 1"),
                   ("Formation: the late E8 = the overflow seen in X, one clock from any state", "e8",
                    whole("w:mul_r w:mac_r") + f"{two} chk_e8 1"),
                   ("Formation EW5 (1/4): the terms reduced last clock = the direct terms, one clock from any state",
                    "ew5_tm", whole("w:mul_r w:mac_r") + f"{two} chk_tm 1"),
                   ("Formation EW5 (2/4): the registers hold csa9 of those terms and the bound, one clock from any state",
                    "ew5_csa", whole("w:mul_r w:mac_r") + f"{two} chk_csa 1"),
                   ("Formation EW5 (3/4): the direct sum = the tree of the direct terms, every state", "ew5_tree",
                    whole("w:mul_r w:mac_r") + "sat -seq 1 -prove chk_tree 1")]
        open(os.path.join(a.out, "ew_arith.v"), "w").write(ew_arith_miter(f_new))
        checks += [(f"Formation EW5 (4/4): csa9's two words = the tree - (NMAX + 1), any eight terms, NMAX {n}",
                    f"ew5_arith_{n}", f"read_verilog ew_arith.v; chparam -set NMAX {n} ew_arith; hierarchy -top ew_arith; "
                    f"{flow}; sat -prove eq 1") for n in (1008, 2048)]
        checks += [
                   ("Formation: the idle test (BCP's commit last) = RH005's, every state and input", "idle",
                    whole("w:mul_r w:mac_r") + "sat -seq 1 -prove chk_idle 1"),
                   ("Formation: split enables = the commit (with the squash), every state and input", "split",
                    whole("w:mul_ovf w:mac_ovf w:sft_ovf w:ew5 w:w_e8") + "sat -seq 1 -prove x_ok_split x_commit")]
        m26 = "                        || (sx_bcp && new_list[a_block_sx] && msA_n[s_sx]);"
        assert f_new.count(m26) == 1, "the pre-read's BCP term (negative control) not found"
        open(os.path.join(a.out, "wpms_formation_m26.v"), "w").write(f_new.replace(m26, "                        || 1'b0;"))
        controls.append(("negative control: the pre-read without BCP's new pending slots, M26 (must be SAT)", "ctl_pre",
                         whole("w:mul_r w:mac_r").replace("wpms_formation.v", "wpms_formation_m26.v")
                         + "sat -seq 2 -prove-skip 1 -prove chk_pre 1"))
        m27 = "        if (seq_strobe) begin                                   // after execute, as below"
        assert f_new.count(m27) == 1, "the lookahead's strobe term (negative control) not found"
        open(os.path.join(a.out, "wpms_formation_m27.v"), "w").write(
            f_new.replace(m27, "        if (1'b0) begin                                   // after execute, as below"))
        controls.append(("negative control: the EW5 lookahead blind to a strobe, M27 (must be SAT)", "ctl_tm",
                         whole("w:mul_r w:mac_r").replace("wpms_formation.v", "wpms_formation_m27.v")
                         + "sat -seq 2 -prove-skip 1 -prove chk_tm 1"))
    print(f"equiv_formal: SD-22 step {a.step}; old logic from commit {ref}, new from "
          f"{'commit ' + a.new if a.new else 'the working files'}; {a.yosys} — evidence class formal (SAT)")
    ok = True
    use_cnf = a.step == 2 and cadical() is not None
    if a.step == 2 and not use_cnf:
        print("  (python-sat not installed: Yosys's own solver, which may not finish the sums; pip install python-sat)")
    for what, tag, script in checks:
        log = os.path.join(a.out, f"{tag}.log")
        good, size = (prove_cnf(a.yosys, script, log, a.out) if use_cnf else
                      prove(a.yosys, script if a.step == 1 else script + " -verify", log, a.out))
        ok &= good
        print(f"  [{'PROVED' if good else 'FAILED'}] {what}  ({size})")
    for what, tag, script in (controls if a.step == 2 and use_cnf else []):
        found, size = prove_cnf(a.yosys, script, os.path.join(a.out, f"{tag}.log"), a.out, want_unsat=False)
        ok &= found
        print(f"  [{'COUNTEREXAMPLE FOUND' if found else 'MISSED'}] {what}  ({size})")
    print(f"equiv_formal: {'PASS — every check proved' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
