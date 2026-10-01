#!/usr/bin/env python3
# ============================================================================
# check_host_tcl.py — OUTSIDE WPMS: runs the host scripts under a plain tclsh
# against issp_standin.tcl (stand-ins for the Quartus Prime ISSP commands,
# answering with the protocol of hw/switch/wpms_host_bridge.v) and checks:
#   demo    the transactions wpms_music_demo.tcl makes are exactly the steps of
#           wpms_music.py — the list RTL-SIM plays (cosim_switch.py --case
#           music): each W one write with its fields, each Q one read, each
#           APPLY a read of GO_SEQ, polls of APPLIED_SEQ until equal, a read of
#           APPLIED_SAMPLE; and the file on disk is what wpms_music.py writes;
#   stress  the same with late acknowledges (3 probe reads), answers in lower
#           case without leading zeros, and a source left by an earlier session
#           with both toggles set;
#   refuse  a refused write is reported (REFUSED, return 1) and the script goes on;
#   dead    no acknowledge: wpms_write fails with an error instead of hanging;
#   status  wpms_status reads its eleven words;
#   phase6  each Phase 6 script (wpms_phase6_<case>_<nmax>.tcl: first_go,
#           full8, ew6 at NMAX 1,008 and 2,048) makes exactly the transactions
#           of its steps in wpms_phase6_steps.py — the steps cosim_board.py
#           plays in RTL-SIM — its one GO is applied, and the file on disk is
#           what wpms_phase6_steps.py writes;
#   mutants eight broken copies of wpms_issp_host.tcl, each of which must fail
#           at least one of the cases above.
# This checks the scripts, not Quartus and not the RTL: the command names and
# arguments are Quartus Prime's ::quartus::insystem_source_probe package as the
# stand-ins model it; Phase 6 runs the scripts on the board.
#
#   python3 check_host_tcl.py [--tclsh tclsh8.6] [--report FILE]
#   exit 0: all pass · 1: a case fails or a mutant survives · 2: no tclsh found
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# 002 2026-10-01       Claude Code   Add : the phase6 case (the Phase 6 scripts; SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, os, re, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wpms_music as MU                  # noqa: E402
import wpms_phase6_steps as P6           # noqa: E402

P6_FILES = tuple(P6.tcl_name(n, m) for m in (1008, 2048) for n in P6.CASES)
FILES = ("issp_standin.tcl", "wpms_issp_host.tcl", "wpms_music_demo.tcl") + P6_FILES
STATUS_WORDS = ["009", "00A", "00B", "012", "014", "016", "018", "030", "033", "292", "298"]

# (name, text in wpms_issp_host.tcl, replacement): one defect each
MUTANTS = [
    ("no wait for the acknowledge", "if {($st & 3) == ($c & 3)}", "if 1"),
    ("only WR_ACK compared", "if {($st & 3) == ($c & 3)}", "if {($st & 1) == ($c & 1)}"),
    ("the probe not padded", "set p [wpms_pad [read_probe_data -instance_index $::wpms::host -value_in_hex] 9]",
     "set p [read_probe_data -instance_index $::wpms::host -value_in_hex]"),
    ("the first device of the chain (the HPS)", 'if {$dev_name eq ""} { set dev_name [lindex $devs end] }',
     "set dev_name [lindex $devs 0]"),
    ("REJ ignored", "return [list $rd [expr {($st >> 2) & 1}]]", "return [list $rd 0]"),
    ("the source's state not read at open",
     "set ::wpms::src [wpms_pad [read_source_data -instance_index $::wpms::host -value_in_hex] 12]",
     "set ::wpms::src 000000000000"),
    ("an 8-bit address", "[expr {$addr & 0xFFF}]", "[expr {$addr & 0xFF}]"),
    ("no poll of APPLIED_SEQ", "while {[wpms_read 0x00A] != $go}", "while {0}"),
]


def tcl(p):
    return "{" + p.replace("\\", "/") + "}"


def run(tclsh, d, body):
    """One tclsh run in the script directory d: the stand-ins, then `body`.
    Returns (rc, stdout, stderr, transactions)."""
    with tempfile.TemporaryDirectory() as t:
        log = os.path.join(t, "standin.log")
        drv = os.path.join(t, "drive.tcl")
        with open(drv, "w") as f:
            f.write("\n".join([f"source {tcl(os.path.join(d, 'issp_standin.tcl'))}",
                               f"set ::standin::logfile {tcl(log)}"] + body) + "\n")
        p = subprocess.run([tclsh, drv], capture_output=True, text=True, timeout=300)
        tx = [x for x in open(log).read().split("\n") if x] if os.path.exists(log) else []
    return p.returncode, p.stdout, p.stderr, tx


def expected(steps):
    E = []
    for st in steps:
        if st[0] == "W":
            E.append(f"W {st[1]:03X} {st[2] & 0xFFFFFFFF:08X}")
        elif st[0] == "Q":
            E.append(f"R {st[1]:03X}")
        elif st[0] == "APPLY":
            E.append("APPLY")
        elif st[0] == "SOUND":
            E.append(f"S {st[1]}")
    return E


def match(E, T):
    """None if the transactions T are the steps E (APPLY = R 009, (R 00A)+, R 00B), else why not."""
    i = 0
    for k, e in enumerate(E):
        if e == "APPLY":
            if T[i:i + 1] != ["R 009"]:
                return f"step {k} (APPLY): {T[i:i + 1]} instead of R 009"
            i += 1
            n = 0
            while i < len(T) and T[i] == "R 00A":
                i, n = i + 1, n + 1
            if n == 0 or T[i:i + 1] != ["R 00B"]:
                return f"step {k} (APPLY): {n} polls of APPLIED_SEQ, then {T[i:i + 1]} instead of R 00B"
            i += 1
        else:
            if T[i:i + 1] != [e]:
                return f"step {k}: {T[i:i + 1]} instead of {e}"
            i += 1
    return None if i == len(T) else f"{len(T) - i} transactions more than the steps"


def case_demo(tclsh, d, name, knobs, E):
    rc, out, err, T = run(tclsh, d, knobs + [f"source {tcl(os.path.join(d, 'wpms_music_demo.tcl'))}"])
    why = []
    if rc != 0 or err.strip():
        why.append(f"tclsh exit {rc}: {err.strip()[:200]}")
    m = match(E, T)
    if m:
        why.append(m)
    if "REFUSED" in out:
        why.append("a write was refused")
    applied = re.findall(r"applied GO (\d+)", out)
    if applied != ["2", "3", "4", "5", "6"]:
        why.append(f"applied GOs {applied}, not 2..6")
    if not re.search(r"^R 009 -> 00000006", out, re.M) or not re.search(r"^R 00A -> 00000006", out, re.M):
        why.append("GO_SEQ / APPLIED_SEQ at the end not 6 / 6")
    nw = sum(1 for x in T if x.startswith("W "))
    nr = sum(1 for x in T if x.startswith("R "))
    text = (f"{nw} writes and {nr} reads, in the order of wpms_music.py's {len(E)} steps; "
            f"applied GOs {', '.join(applied)}")
    return name, not why, text + ("" if not why else "  <- " + "; ".join(why)), T


def cases(tclsh, d):
    """Every case against the scripts in directory d: a list of (name, ok, text)."""
    E = expected(MU.demo(1008))
    R = []
    n1, ok1, t1, T1 = case_demo(tclsh, d, "demo", [], E)
    n2, ok2, t2, T2 = case_demo(tclsh, d, "stress", ["set ::standin::delay 3", "set ::standin::ragged 1",
                                                    "set ::standin::src 0x3ABCDEADBEEF"], E)
    R += [(n1, ok1, t1), (n2, ok2 and T1 == T2, t2 + ("; the same transactions as without the stress"
                                                      if T1 == T2 else "  <- not the transactions of the demo case"))]

    host = os.path.join(d, "wpms_issp_host.tcl")
    rc, out, err, T = run(tclsh, d, ["set ::standin::refuse [list [expr {0x289}]]", f"source {tcl(host)}",
                                     "wpms_open", "puts \"RET [wpms_w 0x289 0x40019FFF {COMMIT[1]}]\"",
                                     "puts \"RET [wpms_w 0x010 0 {MG_TARGET}]\"", "wpms_close"])
    ok = bool(rc == 0 and not err.strip()
              and re.search(r"^W 289 40019FFF -> [0-9A-F]{8} REFUSED", out, re.M)
              and re.findall(r"^RET (\d)", out, re.M) == ["1", "0"] and T == ["W 289 40019FFF", "W 010 00000000"])
    R.append(("refuse", ok, "a refused write prints REFUSED and returns 1; the next write goes on"
              + ("" if ok else f"  <- rc {rc} {err.strip()[:200]} {T}")))

    rc, out, err, T = run(tclsh, d, ["set ::standin::dead 1", f"source {tcl(host)}", "set ::wpms::timeout_ms 200",
                                     "wpms_open", "if {[catch {wpms_write 0x010 5} e]} { puts \"ERR $e\" } "
                                     "else { puts NOERR }", "wpms_close"])
    ok = rc == 0 and not err.strip() and "ERR wpms: no acknowledge (addr 0x010)" in out
    R.append(("dead", ok, "no acknowledge -> the error 'wpms: no acknowledge (addr 0x010)', no hang"
              + ("" if ok else f"  <- rc {rc} {err.strip()[:200]} {out.strip()[-200:]}")))

    rc, out, err, T = run(tclsh, d, [f"source {tcl(host)}", "wpms_open", "wpms_status", "wpms_close"])
    ok = (rc == 0 and not err.strip() and T == [f"R {w}" for w in STATUS_WORDS]
          and len(re.findall(r"^  \S+ +[0-9A-F]{8}$", out, re.M)) == len(STATUS_WORDS))
    R.append(("status", ok, f"wpms_status reads its {len(STATUS_WORDS)} words"
              + ("" if ok else f"  <- rc {rc} {err.strip()[:200]} {T}")))

    why, nw, nr = [], 0, 0
    for nmax in (1008, 2048):
        for name in P6.CASES:
            fn = P6.tcl_name(name, nmax)
            rc, out, err, T = run(tclsh, d, [f"source {tcl(os.path.join(d, fn))}"])
            m = match(expected(P6.CASES[name](nmax)), T)
            applied = re.findall(r"applied GO (\d+)", out)
            if rc != 0 or err.strip():
                why.append(f"{fn}: tclsh exit {rc}: {err.strip()[:120]}")
            if m:
                why.append(f"{fn}: {m}")
            if applied != ["2"] or "REFUSED" in out:
                why.append(f"{fn}: applied GOs {applied}{', a write refused' if 'REFUSED' in out else ''}")
            nw += sum(1 for x in T if x.startswith("W "))
            nr += sum(1 for x in T if x.startswith("R "))
    R.append(("phase6", not why, f"{len(P6_FILES)} scripts: {nw} writes and {nr} reads, each script's in the "
              f"order of its wpms_phase6_steps.py steps; one GO each, applied"
              + ("" if not why else "  <- " + "; ".join(why[:3]))))
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tclsh", default=None)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    tclsh = a.tclsh or shutil.which("tclsh8.6") or shutil.which("tclsh")
    lines = []

    def say(s):
        lines.append(s)
        print(s, flush=True)

    def done(code):
        if a.report:
            with open(a.report, "w") as f:
                f.write("\n".join(lines) + "\n")
        return code

    if not tclsh:
        say("check_host_tcl: no tclsh found — skipped")
        return done(2)
    ver = subprocess.run([tclsh], input="puts [info patchlevel]\n", capture_output=True, text=True).stdout.strip()
    say(f"check_host_tcl: wpms_issp_host.tcl, wpms_music_demo.tcl and the Phase 6 scripts under tclsh {ver}, "
        "against issp_standin.tcl (a check of the scripts: not Quartus, not the RTL)")
    ok_all = True

    same = open(os.path.join(HERE, "wpms_music_demo.tcl")).read() == MU.to_tcl(MU.demo(1008))
    say(f"  {'file':7s} {'PASS' if same else 'FAIL'}: wpms_music_demo.tcl is what wpms_music.py writes (NMAX 1,008)")
    ok_all &= same
    stale = [P6.tcl_name(n, m) for m in (1008, 2048) for n in P6.CASES
             if not os.path.exists(os.path.join(HERE, P6.tcl_name(n, m)))
             or open(os.path.join(HERE, P6.tcl_name(n, m))).read() != P6.tcl_text(n, m)]
    say(f"  {'file':7s} {'PASS' if not stale else 'FAIL'}: the {len(P6_FILES)} Phase 6 scripts are what "
        f"wpms_phase6_steps.py writes" + (f"  <- {stale}" if stale else ""))
    ok_all &= not stale
    for name, ok, text in cases(tclsh, HERE):
        say(f"  {name:7s} {'PASS' if ok else 'FAIL'}: {text}")
        ok_all &= ok

    killed = 0
    with tempfile.TemporaryDirectory() as t:
        for k, (name, old, new) in enumerate(MUTANTS, 1):
            d = os.path.join(t, f"H{k}")
            os.mkdir(d)
            for f in FILES:
                shutil.copy(os.path.join(HERE, f), d)
            p = os.path.join(d, "wpms_issp_host.tcl")
            s = open(p).read()
            if s.count(old) != 1:
                say(f"  H{k:<5d} ERROR: the text to break is not found once ({name})")
                ok_all = False
                continue
            open(p, "w").write(s.replace(old, new))
            failed = [n for n, ok, _ in cases(tclsh, d) if not ok]
            killed += bool(failed)
            say(f"  H{k:<5d} {'KILLED' if failed else 'SURVIVED'}  {name}  ->  "
                f"{', '.join(failed) if failed else 'every case passes'}")
    say(f"  mutants {killed}/{len(MUTANTS)} broken copies of wpms_issp_host.tcl caught")
    ok_all &= killed == len(MUTANTS)

    say(f"check_host_tcl: {'PASS' if ok_all else 'FAIL'}")
    return done(0 if ok_all else 1)


if __name__ == "__main__":
    sys.exit(main())
