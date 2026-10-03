#!/usr/bin/env python3
# ============================================================================
# gate_depth.py — how deep is the logic in front of each register? A reading
# of the netlist for timing work (SD-22), not a timing analysis.
#
# Each module is synthesized by Yosys to generic gates (synth -flatten -noabc:
# AND, OR, XOR, MUX, NOT ... one level each; the multiplier becomes gates too)
# and, for every register, the longest chain of gates in front of its inputs
# is counted. Registers are grouped by name (bit and word indices folded).
# The previous revision (from a git commit) and the working file are read the
# same way, so the two columns compare like with like.
#
#   python3 gate_depth.py [--ref COMMIT] [--lut] [--top N] [--out DIR]
#
# --lut maps the gates into 6-input LUTs first (Yosys's ABC, abc -lut 6) and
# counts LUT levels: nearer what the Fitter places, though an adder or the
# multiplier, which Quartus puts in carry chains and DSP blocks, comes out as
# deep LUT chains here.
#
# A gate level is not a nanosecond: a DSP block, a carry chain and a long
# route are each worth very different numbers of levels. The Quartus timing
# report is the measure; this says where the long chains end.
# Evidence class: ESTIMATE (Yosys, not Quartus). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SD-22 step 1).
# 002 2026-10-03       Claude Code   Add : --lut, the depth in 6-input LUTs (SD-22 step 2).
# ============================================================================
import argparse, json, os, re, shutil, subprocess, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
REF_COMMIT = "e3d4985"
# (module, its file, the files it needs beside it)
MODULES = [("wpms_formation", "l2/wpms_formation.v", ["l2/wpms_decode.vh"]),
           ("wpms_switch", "switch/wpms_switch.v", ["switch/wpms_rom.v", "switch/wpms_rom_origin_1008.hex"])]


def git_show(commit, rel):
    r = subprocess.run(["git", "-C", HW, "show", f"{commit}:./{rel}"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git show {commit}:{rel}: {r.stderr.strip()}")
    return r.stdout


def synth(yosys, d, top, vfiles, lut=False):
    """Generic gates (or 6-input LUTs), flattened; the netlist as JSON (yowasp's sandbox sees the run
    directory only)."""
    script = (f"read_verilog -sv -DSYNTHESIS {' '.join(vfiles)}; synth -top {top} -flatten -noabc; "
              f"{'abc -lut 6; ' if lut else ''}opt_clean; write_json {top}.json")
    r = subprocess.run([yosys, "-q", "-p", script], capture_output=True, text=True, cwd=d)
    if r.returncode:
        raise SystemExit(f"yosys failed in {d}:\n{r.stdout}{r.stderr}")
    return os.path.join(d, f"{top}.json")


def depth_by_register(path, top, lut=False):
    m = json.load(open(path))["modules"][top]
    cells = m["cells"]
    name = {}                                   # bit -> its name (a visible one first)
    for n, nn in m["netnames"].items():
        hid = nn.get("hide_name", 0)
        for b in nn["bits"]:
            if not isinstance(b, str) and (b not in name or (name[b][1] and not hid)):
                name[b] = (n, hid)
    driver, seq = {}, []
    for cn, c in cells.items():
        t = c["type"]
        is_seq = "DFF" in t or "DLATCH" in t or t.startswith("$_SR")
        if is_seq:
            seq.append(cn)
        for p, d in c["port_directions"].items():
            if d == "output":
                for b in c["connections"][p]:
                    if not isinstance(b, str):
                        driver[b] = (cn, is_seq)
    depth = {}

    def dep(b0):                                # iterative longest path to bit b0
        stack = [b0]
        while stack:
            b = stack[-1]
            if isinstance(b, str) or b in depth:
                stack.pop(); continue
            if b not in driver or driver[b][1]:
                depth[b] = 0; stack.pop(); continue
            c = cells[driver[b][0]]
            ins = [ib for p, d in c["port_directions"].items() if d == "input" for ib in c["connections"][p]
                   if not isinstance(ib, str)]
            todo = [ib for ib in ins if ib not in depth]
            if todo:
                stack.extend(todo); continue
            w = (1 if c["type"] == "$lut" else 0) if lut else 1      # --lut: LUT levels only
            depth[b] = w + max([depth[ib] for ib in ins], default=0)
            stack.pop()
        return depth.get(b0, 0) if not isinstance(b0, str) else 0

    groups, count = defaultdict(int), defaultdict(int)
    for cn in seq:
        c = cells[cn]
        q = [b for p, d in c["port_directions"].items() if d == "output" for b in c["connections"][p]]
        nm = name.get(q[0], ("?", 1))[0] if q and not isinstance(q[0], str) else "?"
        g = re.sub(r"\[\d+\]", "[]", nm)
        g = re.sub(r"^\$fsm\$oldstate\\", "", g)
        g = re.sub(r"\$auto\$.*", "(unnamed)", g)
        mx = max([dep(ib) for p, d in c["port_directions"].items() if d == "input" and p not in ("C", "CLK")
                  for ib in c["connections"][p]], default=0)
        groups[g] = max(groups[g], mx)
        count[g] += 1
    return groups, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=REF_COMMIT)
    ap.add_argument("--top", type=int, default=24, help="rows per module")
    ap.add_argument("--lut", action="store_true", help="count 6-input LUT levels (abc -lut 6) instead of gates")
    ap.add_argument("--yosys", default=shutil.which("yosys") or "yowasp-yosys")
    ap.add_argument("--out", default=os.path.join(HW, "l2", "build", "gate_depth"))
    a = ap.parse_args()
    unit = "6-input LUT levels (abc -lut 6)" if a.lut else "gate levels"
    print(f"gate_depth: {unit} in front of each register group — previous revision (commit {a.ref}) "
          f"against the working file; {a.yosys} synth -flatten -noabc — evidence class ESTIMATE")
    for top, rel, extra in MODULES:
        cols = []
        for tag in ("old", "new"):
            d = os.path.join(a.out, top, tag)
            os.makedirs(d, exist_ok=True)
            files = []
            for r in [rel] + extra:
                text = git_show(a.ref, r) if tag == "old" else open(os.path.join(HW, r)).read()
                open(os.path.join(d, os.path.basename(r)), "w").write(text)
                if r.endswith(".v"):
                    files.append(os.path.basename(r))
            cols.append(depth_by_register(synth(a.yosys, d, top, files, a.lut), top, a.lut))
        (old, n_old), (new, n_new) = cols
        keys = sorted(set(old) | set(new), key=lambda k: (-max(old.get(k, 0), new.get(k, 0)), k))
        print(f"\n{top}: longest {max(old.values())} -> {max(new.values())} {'LUT ' if a.lut else ''}levels")
        print(f"  {'register group':44s} {'bits':>6s} {'old':>5s} {'new':>5s}")
        for k in keys[:a.top]:
            print(f"  {k[:44]:44s} {n_new.get(k, n_old.get(k, 0)):6d} {old.get(k, '-')!s:>5s} {new.get(k, '-')!s:>5s}")


if __name__ == "__main__":
    main()
