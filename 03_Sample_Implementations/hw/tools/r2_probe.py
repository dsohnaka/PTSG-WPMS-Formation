#!/usr/bin/env python3
# ============================================================================
# r2_probe.py — Hook A of the 2026-09-27 trace: "Which Core primitive carries
# R2's conditional re-entry without a clock?" Probed on the Core copy
# (hw/core/ptsg_core_rh031p.v) with hw/l2/score_rt_tb.v; no Formation needed,
# the window words are issued and timed exactly as in the real score.
#
# One packet body closed by a QUEUED Base Set (Base := Stay Start State, i.e.
# the body's own Stay Set, C3-F25) and a QUEUED Loop:
#   R2-lit  Loop 3  — literal count: the body must play 3 times back to back
#           (gap-free re-entry at timeup), then continue past the Stay;
#   R2-ind  Loop 0  — the register-source form (target from the indirect-read
#           bus, purpose 01, i.e. LoopVal or the sequencer's P): does the Core
#           perform that read for a queued Loop, and when?
# Evidence class: RTL-SIM. License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF Phase 3).
# ============================================================================
import argparse, os, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_as as SA
import score_rt as RT

BODY = """.depth  1024
.trap   0x3FF
.window PKT wpms_packet.pfasm
        NOP
SLEEP:  Branch  0                               ; STROBE
BODY:   StaySet                 PKT
        Window  PKT
        ProgEnd
        BaseSet                                 ; queued: Base := Stay Start State (BODY)
        Loop    {count}                         ; queued Loop, target {count}
        Stay    32              PKT
HK:     StaySet
        ProgEnd
        Stay    13
        Jump    SLEEP
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RT.L2, "build", "r2_probe"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    L = ["r2_probe: queued Base Set + queued Loop on the Core copy (PRESCALE 1, stay_value 0) — evidence class RTL-SIM"]
    ok = True
    for tag, count in (("R2-lit", 3), ("R2-ind", 0)):
        sp = os.path.join(a.out, f"{tag}.score")
        open(sp, "w").write(BODY.format(count=count))
        words, info = SA.assemble(sp)
        base = os.path.join(a.out, tag)
        open(base + ".hex", "w").write(SA.to_hex(words, info, tag))
        info["labels"].update({f"PKT{q}": 0xFFF for q in range(8)})       # the toy lane mux is not used here
        ev = RT.run(base, info, a.out, tag, 0, 400, 150)
        body, hk = info["labels"]["BODY"], info["labels"]["HK"]
        walk = [(e[1], e[2]) for e in ev if e[0] == "S"]
        entries = [c for c, s in walk if s == body]
        hks = [c for c, s in walk if s == hk]
        ind = [line for line in open(os.path.join(a.out, f"rt_{tag}.txt")) if line.startswith("I ")]
        first = [c for c in entries if c < hks[0]] if hks else entries
        periods = [b - a for a, b in zip(first, first[1:] + hks[:1])]
        L.append(f"  {tag}: Loop {count}: body Stay Sets before housekeeping at clocks {first} -> periods {periods}; "
                 f"indirect reads requested: {len(ind)}")
        if tag == "R2-lit" and not (len(first) == 3 and all(p == 32 for p in periods)): ok = False
        if tag == "R2-ind" and not (len(first) == 1 and not ind): ok = False
    L.append("  reading: the queued Loop re-enters the whole window at timeup with no clock lost (C3-F25's self-loop),")
    L.append("  but its count is the literal D16-D31 only; Loop 0 is 'zero iterations' and no indirect read is made in")
    L.append("  the Q band (need_ind_loop excludes it; C4-V1). A data-driven R2 needs the Core to read a queued Loop's")
    L.append("  register-source target at scan time (INT-R1 on Loop) — a Core-office item, not done here.")
    L.append(f"r2_probe: {'as read (SD-04 confirmed)' if ok else 'NOT as read'}")
    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    open(os.path.join(a.out, "summary.txt"), "w").write(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
