#!/usr/bin/env python3
# ============================================================================
# cosim_gui_replay.py — OUTSIDE WPMS: V3 of the host GUI (GUI brief §5). A
# step log recorded by wpms_ctl.py (a headless storm against the stand-ins, or
# a session on the board) is replayed through the switch RTL: the steps become
# commands of the deterministic controller of hw/switch/wpms_system_tb.v
# (wpms_music.to_stim, unchanged), and hw/tools/cosim_switch.py's own build,
# simulate and check functions (imported, not edited) compare every
# transaction with switch_model.py, every inbox write, the apply steps, the
# ROM, and every bundle and output sample with sweep_sim.Reference and
# l1_model over the customer's oracle — the checks of `cosim_switch.py --case
# music`. Added here:
#   * every write of the log is accepted by the RTL (no refusal on port 0):
#     the coalescing law of wpms_ctl.py never writes a frozen item;
#   * after each APPLY step (simulation: 3 strobes, Ch.5 §5.4.3's bound + 1)
#     APPLIED_SEQ equals GO_SEQ (two reads added after it): every GO applied;
#   * the GOs the RTL accepted from the host are the go-now COMMITs and
#     SWEEP_COMMITs of the log, one each.
# Pauses of the session longer than --gap ms become a few strobes of sound
# (to_stim's SOUND, at most --sound-strobes) so that the music is heard too.
# The replay starts from a reset (the ROM's test origin): a log whose session
# did not start there (its "origin" record) is reported as such.
#
#   python3 cosim_gui_replay.py LOG.json[.gz] [LOG2.json ...] [--out DIR] [--report FILE]
#                               [--gap 50] [--sound-strobes 2] [--max-steps N]
# Evidence class: RTL-SIM (Icarus Verilog -g2012). License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-14       Claude Code   Add : First version (GUI_BRIEF_WPMS_Host_Control_2026-10-14 §5 V3).
# ============================================================================
import argparse, gzip, json, os, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(TOOLS, "host"))
sys.path.insert(0, TOOLS)
import cosim_switch as CS                # noqa: E402  (build, simulate, check: unchanged)
import wpms_music as MU                  # noqa: E402  (to_stim: unchanged)

BUDGET_OF = {1008: 50, 2048: 100}


def load(path):
    doc = json.load(gzip.open(path, "rt") if path.endswith(".gz") else open(path))
    if doc.get("format") != "wpms_ctl step log 1":
        raise SystemExit(f"{path}: not a wpms_ctl step log")
    doc["steps"] = [tuple(s) for s in doc["steps"]]
    return doc


def is_go(s):
    """A GO this controller sent: COMMIT[b] or SWEEP_COMMIT with go-now."""
    return s[0] == "W" and (0x288 <= s[1] <= 0x28F or s[1] == 0x291) and (s[2] >> 31) & 1


def steps_for_sim(doc, gap_ms, max_steps):
    """The log's steps, with SOUND for long pauses and two reads after each APPLY (the check)."""
    S, prev = [], None
    steps, t_us = doc["steps"], doc.get("t_us") or [0] * len(doc["steps"])
    if max_steps:
        steps, t_us = steps[:max_steps], t_us[:max_steps]
    for s, t in zip(steps, t_us):
        if prev is not None and gap_ms and (t - prev) / 1000 > gap_ms:
            S.append(("SOUND", round((t - prev) / 1000), "pause of the session"))
        prev = t
        S.append(s)
        if s[0] == "APPLY":
            S += [("Q", 0x009, "check: GO_SEQ"), ("Q", 0x00A, "check: APPLIED_SEQ")]
    return S


def replay(path, a):
    doc = load(path)
    nmax = doc["nmax"]
    if nmax not in BUDGET_OF:
        raise SystemExit(f"{path}: NMAX {nmax} is neither 1,008 nor 2,048")
    budget = BUDGET_OF[nmax]
    name = os.path.basename(path).split(".")[0]
    out = os.path.join(a.out, name)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    S = steps_for_sim(doc, a.gap, a.max_steps)
    stim = ["R 8", "G 4"] + MU.to_stim(S, sound_strobes=a.sound_strobes) + ["G 4", "E"]
    exe = CS.build(out, budget)
    ev, warn = CS.simulate(exe, out, stim)
    probs, rep = CS.check(ev, budget, "replay")
    probs = [f"simulator: {w}" for w in warn[:5]] + probs

    # the session's start against the ROM's test origin
    org = doc.get("origin") or {}
    at_origin = org.get("sweep") == 1 and org.get("N", {}).get("0") == nmax
    # every write of the log accepted by the RTL (port 0, a write: its EXEC)
    X = [e for e in ev if e[0] == "X"]
    ref0 = [e for e in X if e[2] == 0 and e[3] == 1 and e[7]]
    if ref0:
        probs.append(f"{len(ref0)} host writes refused by the RTL, the first {ref0[0][4]:03X} {ref0[0][5]:08X} "
                     f"at clock {ref0[0][1]}")
    # after each APPLY: APPLIED_SEQ = GO_SEQ
    Q = [e for e in ev if e[0] == "Q"]
    qi = iter(Q)
    pairs = []
    for s in S:
        if s[0] == "Q":
            q = next(qi, None)
            if s[2].startswith("check: GO_SEQ"):
                pairs.append([q[3] if q else None])
            elif s[2].startswith("check: APPLIED_SEQ") and pairs:
                pairs[-1].append(q[3] if q else None)
    late = [p for p in pairs if len(p) != 2 or p[0] is None or p[0] != p[1]]
    if late:
        probs.append(f"{len(late)} APPLY steps with APPLIED_SEQ != GO_SEQ after the bound, e.g. {late[0]}")
    # the GOs the RTL accepted from the host = the go-now steps of the log
    gos_log = sum(1 for s in S if is_go(s))
    gos_rtl = sum(1 for e in X if e[2] == 0 and e[3] == 1 and not e[7] and
                  (0x288 <= e[4] <= 0x28F or e[4] == 0x291) and (e[5] >> 31) & 1)
    if gos_log != gos_rtl:
        probs.append(f"the log has {gos_log} go-now GOs, the RTL accepted {gos_rtl}")
    nw = sum(1 for s in S if s[0] == "W")
    nq = sum(1 for s in S if s[0] == "Q")
    head = (f"cosim_gui_replay {name}: the step log of wpms_ctl.py through wpms_system (switch + ISSP bridge + "
            f"synthesizer), deterministic controller — evidence class RTL-SIM; NMAX {nmax} ({budget} MHz budget)")
    lines = [head,
             f"  log: {len(doc['steps'])} steps{f' (first {a.max_steps} replayed)' if a.max_steps else ''}; "
             f"{nw} writes, {nq} reads ({2 * len(pairs)} of them added checks), {len(pairs)} APPLY, "
             f"{sum(1 for s in S if s[0] == 'SOUND')} pauses > {a.gap} ms as sound; session started at the test "
             f"origin: {at_origin}{'' if at_origin else ' (origin record ' + json.dumps(org) + ')'}"]
    lines += rep
    lines.append(f"  host writes refused by the RTL: {len(ref0)} (0 expected); go-now GOs in the log {gos_log}, "
                 f"accepted by the RTL {gos_rtl}; APPLY steps with APPLIED_SEQ = GO_SEQ after the bound: "
                 f"{len(pairs) - len(late)}/{len(pairs)}")
    lines += [f"  FAIL {p}" for p in probs[:25]]
    lines.append(f"cosim_gui_replay {name}: {'PASS' if not probs else 'FAIL'} ({time.time() - t0:.0f} s)")
    return not probs, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--out", default=os.path.join(TOOLS, "..", "switch", "build", "gui_replay"))
    ap.add_argument("--report", default=None)
    ap.add_argument("--gap", type=float, default=50.0, help="pauses longer than this (ms) become sound")
    ap.add_argument("--sound-strobes", type=int, default=2)
    ap.add_argument("--max-steps", type=int, default=0)
    a = ap.parse_args()
    a.out = os.path.normpath(a.out)
    ok_all, text = True, []
    for p in a.logs:
        ok, lines = replay(p, a)
        ok_all &= ok
        text += lines
        print("\n".join(lines), flush=True)
    if a.report:
        open(a.report, "w").write("\n".join(text) + "\n")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
