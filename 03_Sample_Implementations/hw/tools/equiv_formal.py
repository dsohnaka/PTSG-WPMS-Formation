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
# The old logic is taken from a git commit (default e3d4985, the first fit's
# RTL) and the new from the working files; 1 and 2 are cut out of the sources
# between fixed markers, so the proof is about the text that is built.
#
#   python3 equiv_formal.py [--ref COMMIT] [--yosys yowasp-yosys] [--out DIR]
#
# Evidence class: formal (SAT, Yosys `sat -prove`). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SD-22 step 1).
# ============================================================================
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
L2, SW = os.path.join(HW, "l2"), os.path.join(HW, "switch")
REF_COMMIT = "e3d4985"


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


def prove(yosys, script, log, cwd):
    r = subprocess.run([yosys, "-p", script], capture_output=True, text=True, cwd=cwd)
    open(log, "w").write(r.stdout + r.stderr)
    m = re.search(r"Solving problem with (\d+) variables and (\d+) clauses", r.stdout)
    ok = r.returncode == 0 and "SAT proof finished - no model found: SUCCESS!" in r.stdout
    size = f"{int(m.group(1)):,} variables, {int(m.group(2)):,} clauses" if m else "no SAT problem"
    return ok, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=REF_COMMIT)
    ap.add_argument("--yosys", default=shutil.which("yosys") or "yowasp-yosys")
    ap.add_argument("--out", default=os.path.join(HW, "l2", "build", "equiv_formal"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sw_old, sw_new = git_show(a.ref, "switch/wpms_switch.v"), open(os.path.join(SW, "wpms_switch.v")).read()
    f_old, f_new = git_show(a.ref, "l2/wpms_formation.v"), open(os.path.join(L2, "wpms_formation.v")).read()
    go_v, ew_v = "go_miter.v", "ew_miter.v"           # read from the run directory (yowasp's sandbox sees it)
    open(os.path.join(a.out, go_v), "w").write(go_miter(sw_old, sw_new))
    open(os.path.join(a.out, ew_v), "w").write(ew_miter(f_old, f_new))
    flow = "proc; flatten; opt -fast"
    checks = [(f"switch GO check (go_bad, go_sum), NMAX {n}", "go_" + str(n),
               f"read_verilog {go_v}; chparam -set NMAX {n} go_miter; hierarchy -top go_miter; {flow}; "
               "sat -prove eq 1 -verify") for n in (1008, 2048)]
    checks += [("Formation EW5: the sum of N (tree against chain)", "ew_sum",
                f"read_verilog {ew_v}; hierarchy -top ew_miter; {flow}; sat -prove eq_s 1 -verify"),
               ("Formation EW5: the repeat check (pairwise against running mask)", "ew_inv",
                f"read_verilog {ew_v}; hierarchy -top ew_miter; {flow}; sat -prove eq_inv 1 -verify"),
               ("Formation: split enables = RH004's commit, every state and input", "split",
                f"read_verilog -nosynthesis -I {L2} {os.path.join(L2, 'wpms_formation.v')}; "
                "hierarchy -top wpms_formation; proc; expose w:x_ok_split w:x_commit; delete t:$print; "
                "expose -cut w:mul_ovf w:mac_ovf w:sft_ovf w:ew5; memory; opt -fast; async2sync; dffunmap; "
                "select -assert-count 1 w:x_ok_split; sat -seq 1 -prove x_ok_split x_commit -verify")]
    print(f"equiv_formal: old logic from commit {a.ref}, new from the working files; {a.yosys} — evidence class formal (SAT)")
    ok = True
    for what, tag, script in checks:
        good, size = prove(a.yosys, script, os.path.join(a.out, f"{tag}.log"), a.out)
        ok &= good
        print(f"  [{'PROVED' if good else 'FAILED'}] {what}  ({size})")
    print(f"equiv_formal: {'PASS — every check proved' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
