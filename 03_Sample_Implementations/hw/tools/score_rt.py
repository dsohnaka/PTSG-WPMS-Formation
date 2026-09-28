#!/usr/bin/env python3
# ============================================================================
# score_rt.py — round trip of score_as.py through the Core copy
# (hw/core/ptsg_core_rh031p.v): does the Core decode what the assembler encodes?
#
#   python3 score_rt.py [--out DIR]
#
# Runs hw/l2/scores/d3_sketch_r1_fixture.score (the literal Deliverable 3 §3
# sketch, R1 — a fixture, NOT the Phase 3 score) on the Core with hw/l2/score_rt_tb.v:
#   RT-1  P = 0, three strobes   (empty sweeps: the reset state, CR5-R1)
#   RT-2  P = 2, two strobes     (the NONEMPTY check right after SLEEP)
#   RT-3  P = 2, a variant with "NOP CSEL=NONEMPTY" in front of the NONEMPTY
#         Branch (built here from the fixture; not committed as a score)
# Checks (must hold, else exit 1): every external-operation issue carries exactly
# the assembled word at the issuing state_number; every Formation word of a window
# is issued once per pass, in order; Stay Set -> Stay-timeup of HK = T_HK.
# Observations (reported with their expectation, never "fixed"): SD-05 (a) the
# second empty sweep waits in S_PUSH, (b) a queued Branch not taken resumes at
# Branch + 1; SD-14 the NONEMPTY Branch reads the lane of the word before it.
# Evidence class: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
# ============================================================================
import argparse, os, re, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_as as S

HW = os.path.normpath(os.path.join(HERE, ".."))
L2 = os.path.join(HW, "l2")
PROFILE = os.path.normpath(os.path.join(HW, "..", ".."))
WS = os.environ.get("WS", os.path.normpath(os.path.join(PROFILE, "..")))
IMEM = os.path.join(WS, "PTSG-Core", "03_Sample_Implementations", "ai_friendly_vendor_wrappers", "ptsg_imem", "ptsg_imem.v")
CORE = os.path.join(HW, "core", "ptsg_core_rh031p.v")
FIXTURE = os.path.join(L2, "scores", "d3_sketch_r1_fixture.score")


def build_image(score, out):
    words, info = S.assemble(score)
    open(out + ".hex", "w").write(S.to_hex(words, info, os.path.basename(score)))
    open(out + ".mif", "w").write(S.to_mif(words, info, os.path.basename(score)))
    return {a: w for a, w, _ in words}, info, {a: c for a, w, c in words}


def run(img, info, outdir, tag, P, clocks, strobe):
    exe = os.path.join(outdir, f"rt_{tag}.vvp")
    r = subprocess.run(["iverilog", "-g2012", f"-Pscore_rt_tb.HEX=\"{img}.hex\"", "-o", exe, CORE, IMEM,
                        os.path.join(L2, "score_rt_tb.v")], capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and "sensitive to all" not in l]
    if r.returncode or bad: print("\n".join(bad)); sys.exit(2)
    log = os.path.join(outdir, f"rt_{tag}.txt")
    pk = [f"+pkt{q}={info['labels'][f'PKT{q}']:x}" for q in range(8)]
    subprocess.run(["vvp", "-n", exe, f"+out={log}", f"+P={P}", f"+clocks={clocks}", f"+strobe={strobe}"] + pk,
                   capture_output=True, text=True)
    ev = []
    for line in open(log):
        f = line.split()
        if f[0] == "S": ev.append(("S", int(f[1]), int(f[2], 16), int(f[3], 16), int(f[4])))
        elif f[0] == "O": ev.append(("O", int(f[1]), int(f[2], 16), int(f[3], 16)))
        elif f[0] in ("H", "Z"): ev.append((f[0], int(f[1]), int(f[2], 16)))
        elif f[0] == "E": ev.append(("E", int(f[1]), int(f[2], 16), int(f[3])))
    return ev


def check_issues(ev, mem, notes, tag):
    bad = [(c, st, w) for k, c, st, w in [e for e in ev if e[0] == "O"] if mem.get(st) != w]
    for c, st, w in bad[:5]:
        notes.append(f"{tag}: clock {c}: state 0x{st:03X} issued {w:08X}, image holds {mem.get(st, 0):08X}")
    return len([e for e in ev if e[0] == "O"]), not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(L2, "build", "score_rt"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    L, fails = [], []
    p = L.append
    mem, info, com = build_image(FIXTURE, os.path.join(a.out, "d3_sketch_r1_fixture"))
    lab = info["labels"]
    p("score_rt: score_as.py images through the Core copy (ptsg_core_rh031p.v, IMEM_DEPTH 4096, PRESCALE 1,")
    p("          stay_value 0, stack_ack 0) — evidence class RTL-SIM")
    p(f"  fixture: {os.path.relpath(FIXTURE, PROFILE)} -> {info['size']} words + trap at 0x{info['trap']:03X}; "
      f"SLEEP 0x{lab['SLEEP']:03X}, PKT0 0x{lab['PKT0']:03X}, HK 0x{lab['HK']:03X}")

    # ---- RT-1: empty sweeps ------------------------------------------------------------
    ev = run(os.path.join(a.out, "d3_sketch_r1_fixture"), info, a.out, "1", 0, 500, 150)
    n, ok = check_issues(ev, mem, fails, "RT-1")
    walk = [(e[1], e[2]) for e in ev if e[0] == "S"]
    hk_in = [c for c, s in walk if s == lab["HK"]]
    jump = [c for c, s in walk if s == lab["HK"] + 4]
    push = [e for e in ev if e[0] == "H"]
    end = [e for e in ev if e[0] == "E"][0]
    thk = (jump[0] - hk_in[0]) if hk_in and jump else None
    if thk != 13: fails.append(f"RT-1: HK Stay Set -> Jump SLEEP took {thk} clocks, T_HK = 13 expected")
    p(f"  RT-1 P=0: {n} issue(s), each the image's word: {'yes' if ok else 'NO'} "
      f"(BCP 0x{mem[lab['HK'] + 1]:08X} at 0x{lab['HK'] + 1:03X}); HK Stay Set -> Jump SLEEP {thk} clocks (T_HK 13)")
    p(f"       expected (SD-05 a, by reading): the NONEMPTY Branch is taken on an empty sweep and auto-saves;")
    p(f"       the second taken Branch finds the holding register occupied and waits for stack_ack in S_PUSH.")
    p(f"       observed: HK entered at clock(s) {hk_in}; stack push request at "
      f"{[(c, f'0x{s:03X}') for _, c, s in push]}; at the end state 0x{end[2]:03X}, fsm {end[3]} "
      f"({'stalled' if push and end[2] == lab['SLEEP'] + 1 else 'running'})")

    # ---- RT-2: two packets, literal fixture ----------------------------------------------
    ev = run(os.path.join(a.out, "d3_sketch_r1_fixture"), info, a.out, "2", 2, 700, 300)
    n, ok2 = check_issues(ev, mem, fails, "RT-2")
    walk = [(e[1], e[2], e[3]) for e in ev if e[0] == "S"]
    after = [(c, s, ts) for c, s, ts in walk if s in (lab["SLEEP"] + 1, lab["HK"], lab["PKT0"])][:3]
    p(f"  RT-2 P=2: {n} issue(s), each the image's word: {'yes' if ok2 else 'NO'}")
    p(f"       expected (D3 §3-§4): P > 0 -> NONEMPTY true -> PKT0 (0x{lab['PKT0']:03X}).")
    p("       observed: " + ", ".join(f"clock {c} state 0x{s:03X} timing_signals 0x{ts:04X}" for c, s, ts in after)
      + " — the Branch at 0x002 is evaluated while timing_signals still hold the word before it"
        " (SLEEP, CSEL = STROBE, registered bus): SD-14")

    # ---- RT-3: variant with the lane word in front -------------------------------------
    src = open(FIXTURE).read()
    old = "        Branch  HK              CSEL=NONEMPTY   ; false (P = 0) -> HK"
    assert src.count(old) == 1
    var = os.path.join(a.out, "d3_sketch_r1_variant.score")
    open(var, "w").write(src.replace(old, "        NOP                     CSEL=NONEMPTY   ; score_rt.py variant: the lane word\n" + old))
    vmem, vinfo, _ = build_image(var, os.path.join(a.out, "d3_sketch_r1_variant"))
    vl = vinfo["labels"]
    ev = run(os.path.join(a.out, "d3_sketch_r1_variant"), vinfo, a.out, "3", 2, 700, 300)
    n, ok3 = check_issues(ev, vmem, fails, "RT-3")
    walk = [(e[1], e[2]) for e in ev if e[0] == "S"]
    ss = [c for c, s in walk if s in (vl["PKT0"], vl["PKT1"], vl["HK"])]
    pkt0 = [c for c, s in walk if s == vl["PKT0"]]
    pkt1 = [c for c, s in walk if s == vl["PKT1"]]
    hk = [c for c, s in walk if s == vl["HK"]]
    win = [e for e in ev if e[0] == "O" and vl["PKT0"] < e[2] < vl["PKT0"] + 26]
    wwords = [e[3] for e in win]
    exp_w = [vmem[vl["PKT0"] + 1 + k] for k in range(25)]
    inorder = wwords[:25] == exp_w
    if not inorder: fails.append("RT-3: the first packet window's 25 issues differ from the image")
    per0 = (pkt1[0] - pkt0[0]) if pkt0 and pkt1 else None
    per1 = (hk[0] - pkt1[0]) if pkt1 and hk else None
    p(f"  RT-3 P=2 (variant, NOP CSEL=NONEMPTY before the Branch): {n} issue(s), each the image's word: "
      f"{'yes' if ok3 else 'NO'}; window 0 issued in order: {'yes' if inorder else 'NO'}")
    p(f"       expected (SD-05 b, by reading): MORE true at PKT0's timeup -> queued Branch not taken -> resume at")
    p(f"       Branch + 1 = PKT0's own Stay, which runs again as a bare Stay N_MIN: PKT0 -> PKT1 = 2 x 32 = 64.")
    p(f"       observed: PKT0 Stay Set at clock {pkt0[:1]}, PKT1 at {pkt1[:1]}, HK at {hk[:1]}: "
      f"PKT0 -> PKT1 {per0} clocks, PKT1 -> HK {per1} clocks (MORE false: taken, auto-save)")
    ok_all = ok and ok2 and ok3 and inorder and not fails
    for f in fails: p("  FAIL " + f)
    p(f"score_rt: {'PASS' if ok_all else 'FAIL'} — the Core decodes the assembled words as encoded "
      f"(observations above are discrepancies, filed, not failures)")
    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    open(os.path.join(a.out, "summary.txt"), "w").write(text)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
