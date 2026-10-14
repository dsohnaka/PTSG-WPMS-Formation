#!/usr/bin/env python3
# ============================================================================
# test_gui_bridge.py — OUTSIDE WPMS: checks of the host GUI's bridge and
# controller without Quartus, in the style of ../check_host_tcl.py: the bridge
# (wpms_bridge.tcl) runs under a plain tclsh against ../issp_standin.tcl
# (stand-ins of the Quartus ISSP commands, answering with the bit protocol of
# hw/switch/wpms_host_bridge.v), and is driven over TCP.
#
# V1 — the bridge (GUI brief §5):
#   ping     PING reads ID and CONFIG;
#   wr       W and R: one transaction each, the read-back and <us> in the reply;
#   refuse   a refused write answers rej 1;
#   batch    B n: n replies and END; stopped at a refusal (the rest SKIP, never
#            executed); a batch without refusal executes every line;
#   errors   unknown commands and bad lines answer ERR; the bridge serves on;
#   issp     an ISSP error (no acknowledge) answers ERR and the next read is
#            answered correctly (the toggles were set back to the acknowledges);
#   clients  a client lost without QUIT, a second client refused while one is
#            served, QUIT: the next client is accepted, the session opened once;
#   bind     the listening socket is 127.0.0.1 (and refuses a non-loopback
#            address of this host, where one exists);
#   shutdown SHUTDOWN answers BYE, closes the session (wpms_close) and exits.
#   mutants  nine broken copies of wpms_bridge.tcl, each must fail a case.
# V2 — the controller headless (wpms_ctl.py) against the bridge, with a FREEZE
# MODEL added to this test's own copy of the stand-in (the procs are redefined
# in the driver; issp_standin.tcl is not edited): writes to an armed or fired
# item (its INBOX slots, RTOUT, COMMIT; SWEEP / SWEEP_COMMIT) are refused until
# APPLIED_SEQ reaches its GO, a GO is checked as the switch checks it (P <= 8,
# no block twice, N in [32, NMAX], sum of N <= NMAX), REJECT[0] counts the
# refusals; the state starts as the ROM's test origin leaves it (block 0,
# N = NMAX, sweep [0]):
#   storm    hundreds of random knob moves on four blocks, the sender stepping
#            between them: no refusal (REJECT[0] 0), sent = desired at the end,
#            every block served, every GO applied before the next one is sent;
#   thread   the same with the sender thread and a hand moving knobs on six
#            blocks for 3 s;
#   fair     one knob moved at every step, another block changed once: it is
#            served within the next two GOs (round-robin);
#   origin   the test origin in the middle: applied, the controller resyncs;
#   teeth    a controller that does not wait for the apply is refused by the
#            freeze model (the check has teeth).
# The step logs of storm and thread are saved for cosim_gui_replay.py (V3),
# which checks freezing against the switch RTL itself.
#
#   python3 test_gui_bridge.py [--tclsh tclsh8.6] [--report FILE] [--logs DIR]
#   exit 0: all pass · 1: a case fails or a mutant survives · 2: no tclsh found
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-14       Claude Code   Add : First version (GUI_BRIEF_WPMS_Host_Control_2026-10-14 §5 V1, V2).
# ============================================================================
import argparse, os, random, re, shutil, socket, subprocess, sys, tempfile, threading, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import wpms_ctl as C                     # noqa: E402

ID, CONFIG = 0x57504D53, 0x0003F081

# the test's own additions to the stand-in (driver only; issp_standin.tcl is not edited)
HOOKS = r"""
# the session's opening and closing, visible on stdout
rename start_insystem_source_probe t_start_orig
proc start_insystem_source_probe {args} { puts "STANDIN start"; flush stdout; t_start_orig {*}$args }
rename end_insystem_source_probe t_end_orig
proc end_insystem_source_probe {} { puts "STANDIN end"; flush stdout; t_end_orig }
# a transaction on word 0xFFE is never acknowledged (an ISSP error)
rename write_source_data t_wsd_orig
proc write_source_data {args} {
    scan [standin::opt $args value] %lx n
    if {(($n >> 32) & 0xFFF) == 0xFFE} { set ::standin::dead 1 }
    set r [t_wsd_orig {*}$args]
    set ::standin::dead 0
    return $r
}
"""

FREEZE = r"""
# ---- the freeze model (V2): the switch's stage / arm / GO / apply rules for port 0 ------------------
namespace eval fz {
    variable nmax 1008
    variable frozen [dict create]
    variable n_st [lrepeat 8 0]; variable nv_st [lrepeat 8 0]
    variable n_fu [lrepeat 8 0]; variable nv_fu [lrepeat 8 0]
    variable sw_st 0; variable sw_fu 0
    variable cmask [lrepeat 8 0]
}
proc fz::inrange {d} { return [expr {$d < 0x80000000 && $d >= 32 && $d <= $::fz::nmax}] }
proc fz::check {items nowb nowmask} {
    set n $::fz::n_fu; set nv $::fz::nv_fu
    foreach b $items {
        if {$b < 8} {
            set m [expr {$b == $nowb ? $nowmask : [lindex $::fz::cmask $b]}]
            if {$m & 1} { lset n $b [lindex $::fz::n_st $b]; lset nv $b [lindex $::fz::nv_st $b] }
        }
    }
    set sw [expr {8 in $items ? $::fz::sw_st : $::fz::sw_fu}]
    set P [expr {$sw & 15}]
    set bad [expr {$P > 8}]
    set seen {}; set tot 0
    for {set q 0} {$q < min($P, 8)} {incr q} {
        set b [expr {($sw >> (4 + 3 * $q)) & 7}]
        if {$b in $seen || ![lindex $nv $b]} { set bad 1 }
        lappend seen $b
        incr tot [lindex $n $b]
    }
    if {$tot > $::fz::nmax} { set bad 1 }
    return [list $bad $n $nv $sw]
}
proc fz::fire {items n nv sw} {
    incr ::standin::go_seq; set ::standin::polls 0
    foreach it $items { dict set ::fz::frozen $it $::standin::go_seq }
    set ::fz::n_fu $n; set ::fz::nv_fu $nv; set ::fz::sw_fu $sw
}
proc fz::refuse {} {
    dict set ::standin::mem 48 [expr {[standin::rd 48] + 1}]
    return 1
}
proc fz::armed {} {
    set a {}
    dict for {it s} $::fz::frozen { if {$s eq "armed"} { lappend a $it } }
    return $a
}
proc fz::write {addr data} {
    set fzn [dict keys $::fz::frozen]
    if {$addr == 0x008} {
        if {$data & 3} {
            set items [fz::armed]
            lassign [fz::check $items -1 0] bad n nv sw
            if {$bad} { foreach it $items { dict unset ::fz::frozen $it }; return [fz::refuse] }
            fz::fire $items $n $nv $sw
        }
        return 0
    }
    if {$addr == 0x01C} {
        # the ROM's test origin (port 3): block 0 with N = NMAX, sweep [0], MG_TARGET 0, GO_ALL
        if {($data & 1) && !(0 in $fzn) && !(8 in $fzn)} {
            dict set ::standin::mem [expr {0x200}] $::fz::nmax
            lset ::fz::n_st 0 $::fz::nmax; lset ::fz::nv_st 0 1
            lset ::fz::cmask 0 [expr {0x19FFF}]
            set ::fz::sw_st 1; dict set ::standin::mem [expr {0x290}] 1
            dict set ::standin::mem 16 0
            lassign [fz::check {0 8} -1 0] bad n nv sw
            if {!$bad} { fz::fire {0 8} $n $nv $sw }
        }
        return 0
    }
    if {$addr >= 0x200 && $addr < 0x280} {
        set b [expr {($addr - 0x200) >> 4}]; set i [expr {$addr & 15}]
        if {$i == 13 || $i == 14 || $b in $fzn} { return [fz::refuse] }
        dict set ::standin::mem $addr $data
        if {$i == 0} { lset ::fz::n_st $b [expr {$data & 0xFFF}]; lset ::fz::nv_st $b [fz::inrange $data] }
        return 0
    }
    if {$addr >= 0x280 && $addr < 0x288} {
        if {($addr & 7) in $fzn} { return [fz::refuse] }
        dict set ::standin::mem $addr [expr {$data & 0xFFFF}]
        return 0
    }
    if {$addr >= 0x288 && $addr < 0x290} {
        set b [expr {$addr & 7}]
        if {$b in $fzn} { return [fz::refuse] }
        if {($data >> 31) & 1} {
            lassign [fz::check [list $b] $b [expr {$data & 0x1FFFF}]] bad n nv sw
            if {$bad} { return [fz::refuse] }
            lset ::fz::cmask $b [expr {$data & 0x1FFFF}]
            fz::fire [list $b] $n $nv $sw
        } else {
            lset ::fz::cmask $b [expr {$data & 0x1FFFF}]
            if {($data >> 30) & 1} { dict set ::fz::frozen $b armed }
        }
        dict set ::standin::mem $addr [expr {$data & 0x1FFFF}]
        return 0
    }
    if {$addr == 0x290} {
        if {8 in $fzn} { return [fz::refuse] }
        set ::fz::sw_st [expr {$data & 0xFFFFFFF}]
        dict set ::standin::mem $addr $::fz::sw_st
        return 0
    }
    if {$addr == 0x291} {
        if {8 in $fzn} { return [fz::refuse] }
        if {($data >> 31) & 1} {
            lassign [fz::check {8} -1 0] bad n nv sw
            if {$bad} { return [fz::refuse] }
            fz::fire {8} $n $nv $sw
        } elseif {($data >> 30) & 1} { dict set ::fz::frozen 8 armed }
        return 0
    }
    dict set ::standin::mem $addr $data
    return 0
}
proc standin::do_write {addr data} {
    lappend ::standin::log [format "W %03X %08X" $addr $data]
    set rej [fz::write $addr $data]
    return [list $rej [standin::rd $addr]]
}
proc standin::do_read {addr} {
    lappend ::standin::log [format "R %03X" $addr]
    if {$addr == 10 && $::standin::applied_seq != $::standin::go_seq} {
        if {[incr ::standin::polls] >= 2} { set ::standin::applied_seq $::standin::go_seq }
    }
    dict for {it s} $::fz::frozen {
        if {$s ne "armed" && $s <= $::standin::applied_seq} { dict unset ::fz::frozen $it }
    }
    return [standin::rd $addr]
}
# the state the ROM's test origin leaves: block 0 with N = NMAX playing alone
dict set ::standin::mem [expr {0x200}] $::fz::nmax
dict set ::standin::mem [expr {0x290}] 1
lset ::fz::n_st 0 $::fz::nmax; lset ::fz::nv_st 0 1; lset ::fz::n_fu 0 $::fz::nmax; lset ::fz::nv_fu 0 1
set ::fz::sw_st 1; set ::fz::sw_fu 1
dict set ::standin::mem 48 0
"""

# (name, [(text in wpms_bridge.tcl, replacement)]): one defect each
MUTANTS = [
    ("reply before the transaction (the previous answer)",
     [("    variable done 0\n", "    variable done 0\n    variable last \"OK 00000000 0 0\"\n"),
      ("            puts $ch [lindex [bridge::one $line] 0]\n",
       "            puts $ch $::bridge::last\n            set ::bridge::last [lindex [bridge::one $line] 0]\n")]),
    ("batch not stopped at a refusal", [('if {$cls ne "ok"} { set stop 1 }', 'if {$cls eq "err"} { set stop 1 }')]),
    ("session re-opened per client", [("    set ::bridge::client $ch\n", "    set ::bridge::client $ch\n    catch {wpms_close}\n    wpms_open\n")]),
    ("port bound to 0.0.0.0", [("socket -server bridge::accept -myaddr 127.0.0.1 $::bridge::port",
                                "socket -server bridge::accept $::bridge::port")]),
    ("no resync after an ISSP error", [("proc bridge::resync {} {\n", "proc bridge::resync {} {\n    return\n")]),
    ("SHUTDOWN without wpms_close", [("close $srv\nwpms_close\n", "close $srv\n")]),
    ("QUIT closes the session", [("            bridge::drop $ch quit\n",
                                  "            bridge::drop $ch quit\n            wpms_close\n")]),
    ("a lost client not forgotten", [('    if {$::bridge::client eq $ch} { set ::bridge::client "" }\n', "")]),
    ("an ISSP error not caught", [("        if {[catch {wpms_read $addr} r]} {\n            bridge::resync\n"
                                   "            return [list \"ERR [bridge::errtext $r]\" err]\n        }\n",
                                   "        set r [wpms_read $addr]\n")]),
]


def tcl(p):
    return "{" + p.replace("\\", "/") + "}"


class Run:
    """wpms_bridge.tcl under tclsh with the stand-ins (and the hooks), on a free port."""

    def __init__(self, tclsh, d, extra="", knobs=()):
        self.tmp = tempfile.mkdtemp(prefix="wpms_bridge_")
        self.log = os.path.join(self.tmp, "standin.log")
        drv = os.path.join(self.tmp, "drive.tcl")
        with open(drv, "w") as f:
            f.write("\n".join([f"source {tcl(os.path.join(d, 'issp_standin.tcl'))}",
                               f"set ::standin::logfile {tcl(self.log)}", HOOKS, extra, *knobs,
                               "set ::argv [list 0 --timeout 200]",
                               f"source {tcl(os.path.join(d, 'gui', 'wpms_bridge.tcl'))}"]) + "\n")
        self.p = subprocess.Popen([tclsh, drv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.out = []
        self.addr, self.port = None, None
        self._ready = threading.Event()
        threading.Thread(target=self._reader, daemon=True).start()
        self._ready.wait(10)

    def _reader(self):
        for line in self.p.stdout:
            self.out.append(line.rstrip("\n"))
            m = re.match(r"wpms_bridge: listening on (\S+):(\d+)", line)
            if m:
                self.addr, self.port = m.group(1), int(m.group(2))
                self._ready.set()
        self._ready.set()

    def text(self):
        return "\n".join(self.out)

    def starts(self):
        return sum(1 for l in self.out if l == "STANDIN start")

    def tx(self):
        """The stand-in's transactions (written by end_insystem_source_probe), read at finish()."""
        if os.path.exists(self.log):
            self.T = [x for x in open(self.log).read().split("\n") if x]
        return getattr(self, "T", None)

    def finish(self, timeout=5):
        try:
            return self.p.wait(timeout)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
            return None
        finally:
            self.tx()
            shutil.rmtree(self.tmp, ignore_errors=True)


class Cli:
    """A raw line client."""

    def __init__(self, port, timeout=5):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.f = self.s.makefile("rw", encoding="ascii", newline="\n")

    def send(self, *lines):
        self.f.write("".join(l + "\n" for l in lines))
        self.f.flush()

    def line(self):
        return self.f.readline().strip()

    def ask(self, line, n=1):
        self.send(line)
        return [self.line() for _ in range(n)]

    def close(self):
        for x in (self.f, self.s):
            try:
                x.close()
            except OSError:
                pass


def local_ip():
    """A non-loopback address of this host, or None (no packet is sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


# ---- V1 ------------------------------------------------------------------------------------------
def v1_cases(tclsh, d):
    """Every V1 case against the bridge in directory d (d/gui/wpms_bridge.tcl): [(name, ok, text)]."""
    R = []

    def rec(name, ok, text, why=""):
        R.append((name, bool(ok), text + ("" if ok else f"  <- {why}")))

    r = Run(tclsh, d, knobs=["set ::standin::refuse [list [expr {0x289}]]", "set ::standin::delay 2"])
    if r.port is None:
        r.finish()
        return [(n, False, "the bridge did not start: " + r.text()[-300:]) for n in
                ("ping", "wr", "refuse", "batch", "errors", "issp", "clients", "bind", "shutdown")]
    c = None
    try:
        c = Cli(r.port)
        a = c.ask("PING")[0]
        rec("ping", a == f"OK WPMS {ID:08X} {CONFIG:08X}", "PING -> OK WPMS <ID> <CONFIG>", a)

        w = c.ask("W 010 FFFFF000")[0]
        q = c.ask("R 10")[0]
        q2 = c.ask("R 002")[0]
        ok = (re.fullmatch(r"OK FFFFF000 0 \d+", w) and re.fullmatch(r"OK FFFFF000 \d+", q)
              and re.fullmatch(rf"OK {CONFIG:08X} \d+", q2))
        rec("wr", ok, "W -> OK <read-back> 0 <us>; R -> OK <word> <us> (also hex without leading zeros)", f"{w} | {q} | {q2}")

        x = c.ask("W 289 40019FFF")[0]
        y = c.ask("W 011 1234")[0]
        rec("refuse", re.fullmatch(r"OK [0-9A-F]{8} 1 \d+", x) and re.fullmatch(r"OK 00001234 0 \d+", y),
            "a refused write answers rej 1; the next write goes on", f"{x} | {y}")

        b = c.ask("B 4", 0)
        c.send("W 013 18", "W 289 40019FFF", "W 015 1", "R 000")
        b = [c.line() for _ in range(5)]
        b2 = c.ask("B 3", 0)
        c.send("W 040 5", "R 040", "R 000")
        b2 = [c.line() for _ in range(4)]
        ok = (re.fullmatch(r"OK 00000018 0 \d+", b[0]) and re.fullmatch(r"OK [0-9A-F]{8} 1 \d+", b[1])
              and b[2:4] == ["SKIP", "SKIP"] and re.fullmatch(r"END \d+", b[4])
              and re.fullmatch(r"OK 00000005 0 \d+", b2[0]) and re.fullmatch(r"OK 00000005 \d+", b2[1])
              and re.fullmatch(rf"OK {ID:08X} \d+", b2[2]) and re.fullmatch(r"END \d+", b2[3]))
        rec("batch", ok, "B 4 stopped at the refusal (2 SKIP), END; B 3 executes every line", f"{b} | {b2}")

        e = [c.ask(l)[0] for l in ("HELLO", "W 1234 5", "R", "B 0")]
        p = c.ask("PING")[0]
        rec("errors", all(x.startswith("ERR ") for x in e) and p.startswith("OK WPMS"),
            "unknown command, bad W, bad R, bad batch header -> ERR; the bridge serves on", f"{e} | {p}")

        q0 = c.ask("R 002")[0]
        z = c.ask("R FFE")[0]
        q1 = c.ask("R 000")[0]
        q2 = c.ask("W 011 77")[0]
        ok = (z.startswith("ERR wpms: no acknowledge") and re.fullmatch(rf"OK {ID:08X} \d+", q1)
              and re.fullmatch(r"OK 00000077 0 \d+", q2) and q0.startswith("OK"))
        rec("issp", ok, "no acknowledge -> ERR; then R 000 answers the ID and a write goes on", f"{z} | {q1} | {q2}")

        # a client lost without QUIT; a second one refused while one is served; QUIT; a new one
        c.s.close()
        c = None
        time.sleep(0.2)
        c1 = Cli(r.port)
        p1 = c1.ask("PING")[0]
        c2 = Cli(r.port)
        busy = c2.line()
        c2.close()
        bye = c1.ask("QUIT")[0]
        c1.close()
        time.sleep(0.1)
        c = Cli(r.port)
        p2 = c.ask("PING")[0]
        ok = (p1.startswith("OK WPMS") and busy.startswith("ERR busy") and bye == "BYE" and p2.startswith("OK WPMS")
              and r.starts() == 1 and "STANDIN end" not in r.out)
        rec("clients", ok, "a lost client and a QUIT: the next client is served; a second client gets ERR busy; "
            "the session opened once", f"{p1} | {busy} | {bye} | {p2} | starts {r.starts()}")

        ip = local_ip()
        ext = None
        if ip:
            try:
                s = socket.create_connection((ip, r.port), timeout=1)
                s.close()
                ext = "accepted"
            except OSError:
                ext = "refused"
        rec("bind", r.addr == "127.0.0.1" and ext != "accepted",
            f"listening on {r.addr}" + (f"; a connection to {ip} {ext}" if ip else "; no other address to try"),
            f"{r.addr} {ext}")

        s = c.ask("SHUTDOWN")[0]
        c.close()
        c = None
        rc = r.finish()
        T = r.tx() or []
        ok = (s == "BYE" and rc == 0 and "STANDIN end" in r.out and "W 015 00000001" not in T
              and "W 011 00000077" in T and "R 000" in T)
        rec("shutdown", ok, f"SHUTDOWN -> BYE, wpms_close, exit 0; the stand-in saw {len(T)} transactions, "
            "none of the skipped ones", f"{s} rc {rc} end {'STANDIN end' in r.out} {T[-6:]}")
    except (OSError, IndexError) as e:
        done = {n for n, _, _ in R}
        for n in ("ping", "wr", "refuse", "batch", "errors", "issp", "clients", "bind", "shutdown"):
            if n not in done:
                R.append((n, False, f"not reached: {type(e).__name__} {e}"))
    finally:
        if c:
            c.close()
        r.finish(2)
    return R


# ---- V2 ------------------------------------------------------------------------------------------
def commits(ctl):
    """Item of each GO sent, in order, from the step log (COMMIT[b] / SWEEP_COMMIT go-now)."""
    G = []
    for e in ctl.log:
        s = e["step"]
        if s[0] == "W" and (0x288 <= s[1] <= 0x28F or s[1] == 0x291) and s[2] >> 31:
            G.append(8 if s[1] == 0x291 else s[1] & 7)
    return G


def law_kept(ctl):
    """Every GO is applied (an APPLY step) before the next GO of this controller is sent."""
    open_go = False
    for e in ctl.log:
        s = e["step"]
        if s[0] == "W" and ((0x288 <= s[1] <= 0x28F or s[1] == 0x291) and s[2] >> 31 or s[1] == 0x01C):
            if open_go:
                return False
            open_go = True
        elif s[0] == "APPLY":
            open_go = False
    return True


def converged(ctl):
    bad = []
    for b in range(8):
        if ctl.sent_slots[b] is not None:
            v = C.block_slots(ctl.params[b])
            for _, g in C.GROUPS:
                for i in range(16):
                    if g >> i & 1 and v[i] != ctl.sent_slots[b][i]:
                        bad.append((b, i))
            if v[0] != ctl.sent_slots[b][0] or (ctl.params[b]["route"] & 3) != ctl.sent_rt[b]:
                bad.append((b, "N/route"))
    if ctl.play != ctl.sent_play:
        bad.append(("play", ctl.play, ctl.sent_play))
    if ctl.mg_target != ctl.sent_mg_target:
        bad.append("master")
    return bad


def v2_cases(tclsh, d, logs=None):
    R = []

    def v2run(name, body):
        r = Run(tclsh, d, extra=FREEZE)
        ctl = None
        try:
            if r.port is None:
                raise RuntimeError("the bridge did not start: " + r.text()[-300:])
            ctl = C.Controller(port=r.port).connect()
            ok, text = body(ctl)
            rej = ctl._status()["REJECT0"]
            ok = ok and rej == 0 and ctl.counts["refused"] == 0 and ctl.counts["errors"] == 0
            text += f"; REJECT0 {rej}, refused {ctl.counts['refused']}, errors {ctl.counts['errors']}"
            if logs and name in ("storm", "thread"):
                os.makedirs(logs, exist_ok=True)
                n = ctl.save_log(os.path.join(logs, f"v2_{name}.json"))
                text += f"; step log {n} steps -> v2_{name}.json"
            R.append((name, ok, text + ("" if ok else f"  <- {ctl.errors[:3]}")))
        except Exception as e:                               # noqa: BLE001  (a case fails, the run goes on)
            R.append((name, False, f"{type(e).__name__}: {e}"))
        finally:
            if ctl:
                ctl.close(shutdown=True)
            r.finish()

    def storm(ctl):
        blocks = [0, 1, 2, 3]
        idle = C.storm(ctl, 400, random.Random(1), blocks)
        G = commits(ctl)
        served = sorted(set(G) - {8})
        bad = converged(ctl)
        ok = idle and not bad and set(blocks) <= set(served) and law_kept(ctl)
        return ok, (f"400 moves on blocks {blocks}: {len(G)} GOs ({G.count(8)} sweep), blocks served {served}, "
                    f"final play {ctl.play}; sent = desired: {not bad}; each GO applied before the next: {law_kept(ctl)}")

    def thread(ctl):
        blocks = [0, 1, 2, 3, 4, 5]
        rng = random.Random(7)
        ctl.set_block(0, N=128)
        ctl.start()
        t_end = time.monotonic() + 3
        moves = 0
        while time.monotonic() < t_end:
            b = rng.choice(blocks)
            r = rng.random()
            if r < 0.5: ctl.set_block(b, level=rng.uniform(-40, -3))
            elif r < 0.8: ctl.set_block(b, f=rng.uniform(150, 2000))
            elif r < 0.9: ctl.set_play(b, b not in ctl.play)
            else: ctl.set_master_db(rng.uniform(-24, 0))
            moves += 1
            time.sleep(0.0005)
        t1 = time.monotonic() + 30
        while ctl.busy() and time.monotonic() < t1:
            time.sleep(0.01)
        ctl.stop()
        G = commits(ctl)
        served = sorted(set(G) - {8})
        bad = converged(ctl)
        ok = not ctl.busy() and not bad and set(blocks) <= set(served) and law_kept(ctl) and ctl.state == "connected"
        return ok, (f"{moves} moves in 3 s on blocks {blocks} with the sender thread: {len(G)} GOs, "
                    f"blocks served {served}; sent = desired: {not bad}; law kept: {law_kept(ctl)}")

    def fair(ctl):
        ctl.set_block(0, N=128)
        ctl.run_until_idle(10)
        for k in range(20):
            ctl.set_block(1, level=-6 - (k % 7))
            ctl.step()
        n0 = len(commits(ctl))
        ctl.set_block(2, f=700.0)
        for k in range(60):
            ctl.set_block(1, level=-6 - (k % 7))
            ctl.step()
        G = commits(ctl)[n0:]
        pos = G.index(2) if 2 in G else None
        ctl.run_until_idle(10)
        ok = pos is not None and pos <= 1
        return ok, f"block 1 moved at every step; block 2 changed once: served as GO #{pos} after its change (<= #1)"

    def origin(ctl):
        ctl.set_block(0, N=200)
        ctl.set_play(1, True)
        ctl.run_until_idle(10)
        before = list(ctl.sent_play)
        ctl.test_origin()
        ctl.run_until_idle(10)
        applied = any(e["step"][0] == "APPLY" and "test origin" in e["step"][1] for e in ctl.log)
        ok = applied and before == [0, 1] and ctl.play == [0] and ctl.sent_N[0] == ctl.nmax and law_kept(ctl)
        return ok, (f"sweep {before} -> test origin applied: {applied}; after it the controller holds sweep "
                    f"{ctl.play}, N0 = {ctl.sent_N[0]}")

    v2run("storm", storm)
    v2run("thread", thread)
    v2run("fair", fair)
    v2run("origin", origin)

    # teeth: a controller that sends the next GO without waiting for the apply must be refused
    class NoWait(C.Controller):
        def _send_item(self, it, m):
            super()._send_item(it, m)
            self.pending = None

    r = Run(tclsh, d, extra=FREEZE)
    try:
        ctl = NoWait(port=r.port).connect()
        C.storm(ctl, 200, random.Random(3), [0, 1, 2, 3], settle=False)
        rej = ctl._status()["REJECT0"]
        extra = ""
        if logs:
            os.makedirs(logs, exist_ok=True)
            extra = f"; step log {ctl.save_log(os.path.join(logs, 'v2_teeth.json'))} steps -> v2_teeth.json (V3 must fail it)"
        ctl.close(shutdown=True)
        R.append(("teeth", rej > 0, f"a controller that does not wait for APPLIED_SEQ: {rej} refusals "
                  "(the freeze model refuses it)" + extra))
    except Exception as e:                                   # noqa: BLE001
        R.append(("teeth", False, f"{type(e).__name__}: {e}"))
    finally:
        r.finish()
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tclsh", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--logs", default=None, help="directory for the V2 step logs (for cosim_gui_replay.py)")
    ap.add_argument("--no-mutants", action="store_true")
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
        say("test_gui_bridge: no tclsh found — skipped")
        return done(2)
    ver = subprocess.run([tclsh], input="puts [info patchlevel]\n", capture_output=True, text=True).stdout.strip()
    say(f"test_gui_bridge: wpms_bridge.tcl under tclsh {ver} against issp_standin.tcl, driven by wpms_ctl.py "
        "(a check of the bridge and the controller: not Quartus, not the RTL)")
    ok_all = True
    say(" V1 — the bridge")
    for name, ok, text in v1_cases(tclsh, HOST):
        say(f"  {name:8s} {'PASS' if ok else 'FAIL'}: {text}")
        ok_all &= ok
    say(" V2 — the controller headless, with the test's freeze model")
    for name, ok, text in v2_cases(tclsh, HOST, a.logs):
        say(f"  {name:8s} {'PASS' if ok else 'FAIL'}: {text}")
        ok_all &= ok

    if not a.no_mutants:
        killed = 0
        src = open(os.path.join(HERE, "wpms_bridge.tcl")).read()
        with tempfile.TemporaryDirectory() as t:
            for k, (name, edits) in enumerate(MUTANTS, 1):
                d = os.path.join(t, f"B{k}")
                os.makedirs(os.path.join(d, "gui"))
                for f in ("issp_standin.tcl", "wpms_issp_host.tcl"):
                    shutil.copy(os.path.join(HOST, f), d)
                s = src
                bad = [old for old, new in edits if s.count(old) != 1]
                if bad:
                    say(f"  B{k:<6d} ERROR: the text to break is not found once ({name})")
                    ok_all = False
                    continue
                for old, new in edits:
                    s = s.replace(old, new)
                open(os.path.join(d, "gui", "wpms_bridge.tcl"), "w").write(s)
                failed = [n for n, ok, _ in v1_cases(tclsh, d) if not ok]
                killed += bool(failed)
                say(f"  B{k:<6d} {'KILLED' if failed else 'SURVIVED'}  {name}  ->  "
                    f"{', '.join(failed) if failed else 'every case passes'}")
        say(f"  mutants {killed}/{len(MUTANTS)} broken copies of wpms_bridge.tcl caught")
        ok_all &= killed == len(MUTANTS)

    say(f"test_gui_bridge: {'PASS' if ok_all else 'FAIL'}")
    return done(0 if ok_all else 1)


if __name__ == "__main__":
    sys.exit(main())
