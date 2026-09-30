#!/usr/bin/env python3
# ============================================================================
# cosim_switch.py — Phase 5 cosimulation of hw/switch/wpms_system.v: the input
# switch, the ISSP host bridge and the Phase 4 synthesizer on the real 48 kHz
# grid, driven by the deterministic controller of wpms_system_tb.v through the
# same source bits the ISSP drives on the board (architect's ruling 2026-09-30).
#
#   python3 cosim_switch.py --case origin|music|reject|timing|bridge|random
#                           [--budget 50|100] [--seed S] [--samples N]
#                           [--out DIR] [--report FILE] [--rtl DIR]
#
# Checked, every run:
#   * the switch: every transaction the RTL executed is replayed through
#     switch_model.py (Ch.5's semantics, written from the text): each answer
#     (rdata, refused or not), each write presented to the Formation's inbox
#     port (clock, address, data), the apply steps, APPLIED_SEQ/SAMPLE, REJECT;
#   * the host path: each command of the controller became exactly one write
#     (+ its read-back) or one read on port 0 with the same fields, and its
#     probe returned that transaction's answer; KEY[0] presses became GO_ALLs;
#     nothing else reached port 0 (no replay after a reset with toggles set);
#     port 3 played the ROM's list after each reset, KEY[1] and TEST_ORIGIN;
#   * the sound: every bundle latched and every output sample, against
#     sweep_sim.Reference (the customer's semantics, unchanged) fed with the
#     takes the model predicts, and l1_model over the customer's oracle, with
#     the knobs the model predicts at each strobe;
#   * Ch.5 §5.4.3: GO -> first sweep playing it <= 2 sample periods;
#     exactly-once and one-sample landing follow from the bundle comparison.
# Evidence class: RTL-SIM (Icarus Verilog -g2012). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# ============================================================================
import argparse, math, os, random, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "host"))
import l1_model as M                     # noqa: E402
import cosim_sweep as CS                 # noqa: E402
import switch_model as SM                # noqa: E402
import gen_switch_rom as GR              # noqa: E402
import wpms_music as MU                  # noqa: E402  (outside WPMS: the host script's steps)
O = M.O
HW = CS.HW
L1D, L2D, SWD = os.path.join(HW, "l1"), CS.L2, os.path.join(HW, "switch")
GOLD = os.path.normpath(os.path.join(HW, "..", "tools"))
sys.path.insert(0, GOLD)
import sweep_sim as SS                   # noqa: E402  (golden, unchanged)

BUDGETS = {50: dict(nmax=1008, tmin=1041, half=10.0), 100: dict(nmax=2048, tmin=2083, half=5.0)}
RTLDIRS = []
DEB = 16                                  # KEY debounce in the bench (clocks)
RESEED_RT = 0x9FFF | 1 << 16
ARM, GONOW = 1 << 30, 1 << 31


def src(name, d):
    for x in RTLDIRS:
        if os.path.exists(os.path.join(x, name)):
            return os.path.join(x, name)
    return os.path.join(d, name)


def rom_list(budget, extra):
    L = [(a, d & 0xFFFFFFFF) for a, d, _ in GR.rom_list(BUDGETS[budget]["nmax"])]
    if extra:                                      # a TEST_ORIGIN write before the GO_ALL (an ISMCE-edited ROM)
        L.insert(len(L) - 1, (0x01C, 1))
    return L


def build(out, budget, extra=False):
    b = BUDGETS[budget]
    hexf, _ = CS.assemble(os.path.join(L2D, "scores", "wpms_r1d.score"), out, "wpms_r1d")
    rom = os.path.join(SWD, f"wpms_rom_origin_{b['nmax']}.hex")
    if extra:
        rom = os.path.join(out, "rom_test.hex")
        L = rom_list(budget, True)
        open(rom, "w").write("".join(f"{a << 32 | d:011X}\n" for a, d in L) + f"{0xFFF << 32:011X}\n" * (256 - len(L)))
    exe = os.path.join(out, "system.vvp")
    inc = [f"-I{RTLDIRS[0]}"] if RTLDIRS else []
    files = [src(f, SWD) for f in ("wpms_system_tb.v", "wpms_system.v", "wpms_switch.v", "wpms_host_bridge.v",
                                   "wpms_issp.v", "wpms_rom.v", "wpms_key_pulse.v")]
    files += [src(f, L1D) for f in ("wpms_synth_top.v", "wpms_l1_module.v", "wpms_l1_sin.v", "wpms_l1_exp2.v",
                                    "wpms_output_stage.v", "wpms_strobe_sync.v", "wpms_i2s_master.v")]
    files += [src(f, L2D) for f in ("wpms_l2_top.v", "wpms_formation.v", "wpms_sequencer.v")]
    files += [os.path.join(HW, "core", "ptsg_core_rh031p.v"), CS.IMEM]
    cmd = ["iverilog", "-g2012", *inc, f"-I{L1D}", f"-I{L2D}", "-o", exe, "-s", "wpms_system_tb",
           f"-Pwpms_system_tb.SCORE=\"{hexf}\"", f"-Pwpms_system_tb.EXP2_HEX=\"{src('wpms_exp2_table.hex', L1D)}\"",
           f"-Pwpms_system_tb.ROM_HEX=\"{rom}\"", f"-Pwpms_system_tb.NMAX={b['nmax']}",
           f"-Pwpms_system_tb.DEB={DEB}", f"-Pwpms_system_tb.SYS_HALF={b['half']}", *files]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines()
           if l.strip() and "sensitive to all" not in l and "coerced to inout" not in l]
    if r.returncode or bad:
        raise SystemExit("compile failed:\n" + "\n".join(bad[:30]))
    return exe


def simulate(exe, out, stim, vcd=None):
    sp, rp = os.path.join(out, "stim.txt"), os.path.join(out, "res.txt")
    open(sp, "w").write("\n".join(stim) + "\n")
    args = ["vvp", "-n", exe, f"+stim={sp}", f"+out={rp}"] + ([f"+vcd={vcd}"] if vcd else [])
    r = subprocess.run(args, capture_output=True, text=True)
    warn = [l for l in (r.stdout + r.stderr).splitlines() if "WARNING" in l or "ERROR" in l]
    return parse(rp), warn


def s24(v):
    return v - (1 << 24) if v >> 23 else v


def parse(path):
    ev = []
    for line in open(path):
        f = line.split()
        if not f:
            continue
        k = f[0]
        if k == "X": ev.append(("X", int(f[1]), int(f[2]), int(f[3]), int(f[4], 16), int(f[5], 16),
                                int(f[6], 16), int(f[7]), int(f[8], 16)))
        elif k == "U": ev.append(("U", int(f[1]), int(f[2]), int(f[3], 16)))
        elif k == "I": ev.append(("I", int(f[1]), int(f[2], 16), int(f[3], 16), int(f[4]), int(f[5])))
        elif k == "C": ev.append(("C", int(f[1]), SM.s32(int(f[2], 16)), SM.s32(int(f[3], 16)), int(f[4]),
                                  int(f[5]), int(f[6]), int(f[7])))
        elif k == "W": ev.append(("W", int(f[1]), int(f[2], 16), int(f[3], 16), int(f[4], 16), int(f[5])))
        elif k == "Q": ev.append(("Q", int(f[1]), int(f[2], 16), int(f[3], 16)))
        elif k == "K": ev.append(("K", int(f[1]), int(f[2])))
        elif k == "O": ev.append(("O", int(f[1]), s24(int(f[2], 16)), s24(int(f[3], 16)), int(f[4]),
                                  M.s32(int(f[5], 16)), int(f[6]), int(f[7])))
        elif k == "L": ev.append(("L", int(f[1]), int(f[2]), [int(x, 16) for x in f[3:11]]))
        elif k == "P": ev.append(("P", int(f[1]), int(f[2]), int(f[3])))
        elif k == "F": ev.append(("F", int(f[1]), int(f[2]), int(f[3], 16)))
        elif k == "H": ev.append(("H", int(f[1]), int(f[2], 16)))
        elif k == "Y": ev.append(("Y", *[int(x) for x in f[1:6]]))
        else: ev.append((k, int(f[1])))                          # S B R T
    return ev


# ---------------------------------------------------------------------------
# stimulus helpers (writer side: integers only)
# ---------------------------------------------------------------------------
def W(a, d): return f"W {a:x} {d & 0xFFFFFFFF:x}"
def Q(a): return f"Q {a:x}"


def stage(b, v, rt=3, mask=RESEED_RT, arm=True, now=False):
    L = [W(0x200 + 16 * b + i, v[i]) for i in range(16) if i not in (13, 14) and (mask >> i) & 1]
    if mask >> 16 & 1:
        L.append(W(0x280 + b, rt))
    L.append(W(0x288 + b, mask | (ARM if arm else 0) | (GONOW if now else 0)))
    return L


def sweep_word(order, P=None):
    w = len(order) if P is None else P
    for k, b in enumerate(order):
        w |= b << (4 + 3 * k)
    return w


def rand_block(rng, N):
    v = SS.rand_block(rng, N)                     # the sweep oracle's own random block (golden)
    return [x & 0xFFFFFFFF for x in v]


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
def case_origin(b, rng, n):
    L = ["R 8", "G 3"]
    L += [Q(a) for a in (0x000, 0x001, 0x002, 0x003, 0x009, 0x00A, 0x00B, 0x00C, 0x00D, 0x010, 0x011, 0x020,
                         0x030, 0x033, 0x292)]
    L += [Q(0x200 + i) for i in range(16)] + [Q(0x280), Q(0x288), Q(0x290), Q(0x291)]
    L += [f"G {max(1, n - 5):x}", "E"]
    return L


def case_music(b, rng, n):
    L = ["R 8", "G 4"] + MU.to_stim(MU.demo(b["nmax"]), sound_strobes=6) + ["G 4", "E"]
    return L


def case_reject(b, rng, n):
    """Refusals (Ch.5 §5.4.2 frozen-while-armed; PR-1, PR-2, §5.4.4 sum of N; the
    choices of §4.4 for read-only and unmapped words), then legal GOs: nothing
    refused may reach the page. Block 0 (the test origin) fills NMAX on its own
    at 50 MHz, so the sweeps here list blocks 1 and 2 only."""
    nmax = b["nmax"]
    v1, v2 = rand_block(rng, 64), rand_block(rng, 64)
    for v in (v1, v2):
        v[0x5] = 0                                # LE0 >= 0 (PR-3: the writer's duty)
    L = ["R 8", "G 3"]
    # 1. frozen: after arming, the block and its RTOUT/COMMIT refuse writes; so does the armed sweep word
    L += stage(1, v1) + [W(0x211, 7), W(0x21A, 1), W(0x281, 1), W(0x289, RESEED_RT | ARM), W(0x290, sweep_word([1])),
                         W(0x291, ARM), W(0x290, 0x11), W(0x291, ARM)]
    L += [W(0x008, 1), "G 3", Q(0x00A), Q(0x030)]
    # 2. PR-2: a listed block's N out of [N_MIN, NMAX]; each GO refused, its items disarmed
    for bad_n in (31, nmax + 1, 0, 0x80000020):
        vb = list(v2); vb[0] = bad_n & 0xFFFFFFFF
        L += stage(2, vb) + [W(0x290, sweep_word([1, 2])), W(0x291, ARM), W(0x008, 1), Q(0x288 + 2), Q(0x291)]
    # 3. the sum of N above NMAX, each block in range
    va, vb = list(v1), list(v2)
    va[0] = vb[0] = nmax // 2 + 16
    L += stage(1, va) + stage(2, vb) + [W(0x290, sweep_word([1, 2])), W(0x291, ARM), W(0x008, 2), Q(0x030)]
    # 4. PR-1 (a block twice), P = 9, and a block whose N was never written
    L += [W(0x290, sweep_word([1, 1])), W(0x291, ARM | GONOW)]
    L += [W(0x290, sweep_word([1, 2, 3, 4, 5, 6, 7, 0], P=9)), W(0x291, GONOW)]
    L += [W(0x290, sweep_word([3])), W(0x291, GONOW)]
    # 5. read-only, reserved and unmapped words
    L += [W(a, 0x1234) for a in (0x000, 0x009, 0x00A, 0x012, 0x018, 0x041, 0x100, 0x20D, 0x20E, 0x292, 0x298,
                                 0x2A0, 0x300, 0xFFF)]
    # 6. legal GOs after all that: block 2 with a good N, then sweep [1, 2] (block 1 keeps its page N)
    vg = list(v2); vg[0] = 96
    L += stage(2, vg) + [W(0x290, sweep_word([1, 2])), W(0x291, ARM), W(0x008, 1), "G 3",
                         Q(0x030), Q(0x033), Q(0x009), Q(0x00A), Q(0x292), W(0x030, 0xFFFFFFFF), Q(0x030)]
    # 7. go-now on one block (LEVEL) while the others play
    vl = list(vg); vl[0x5], vl[0x9] = 1 << 20, -(4 << 26)
    L += [W(0x205, vl[0x5]), W(0x209, vl[0x9] & 0xFFFFFFFF), W(0x28A, 0x0220 | GONOW), "G 3", Q(0x00A), Q(0x00B)]
    L += [f"G {max(1, n - 30):x}", "E"]
    return L


def case_timing(b, rng, n):
    """GO hand-overs around the strobe: the controller starts a GO k clocks after a
    strobe for k across the end of the period, so that the hand-over is presented
    before, in and after a strobe clock; multi-item GOs check the one-sample landing."""
    T = b["tmin"]
    L = ["R 8", "G 3", "P 0"]
    blocks = {bk: rand_block(rng, 48) for bk in range(1, 5)}
    for v in blocks.values():
        v[0x5] = 0
    for bk, v in blocks.items():
        L += stage(bk, v)
    L += [W(0x290, sweep_word([1, 2, 3, 4])), W(0x291, ARM), W(0x008, 1), "G 3"]   # block 0 alone fills NMAX at 50 MHz
    ks = list(range(T - 22, T - 2)) * 3            # the strobe interval alternates (1041/1042, 2083/2084)
    for it, k in enumerate(ks):
        items = [1 + (it % 4), 1 + ((it + 1) % 4)]
        for bk in items:
            v = list(blocks[bk]); v[0xA] = rng.randrange(1 << 32); v[0xB] = rng.randrange(1 << 20)
            L += [W(0x200 + 16 * bk + 0xA, v[0xA]), W(0x200 + 16 * bk + 0xB, v[0xB]), W(0x288 + bk, 0x1C00 | ARM)]
        L += [f"A {k:x}", W(0x008, 1), "G 3"]
    L += [f"G {max(1, n - 3 * len(ks) - 8):x}", "E"]
    return L


def case_bridge(b, rng, n):
    L = ["R 8", "G 2"]
    for sk in (1, 2, 3, 0):
        L += [f"S {sk:x}"] + [W(0x040, rng.randrange(1 << 16)), Q(0x040), W(0x011, rng.randrange(1 << 20)), Q(0x011)]
    L += ["P 0"] + [Q(0x000), Q(0x001), W(0x013, 0x0C), Q(0x013), W(0x013, 0)] + ["P 4"]
    # a design reset with the editor's toggles set: nothing may be replayed
    L += ["X 10 1", "G 3", Q(0x009), "X 10 2", "G 3", Q(0x00A), "X 10 3", "G 3", W(0x015, 0), Q(0x015)]
    # KEY[0] (GO_ALL) and KEY[1] (the test origin again)
    v = rand_block(rng, 128); v[0x5] = 0
    L += stage(2, v) + [W(0x290, sweep_word([2])), W(0x291, ARM), "K 0", "G 3", Q(0x00A), Q(0x292), Q(0x030),
                        "K 1", "G 3", Q(0x292)]
    L += [f"G {max(1, n - 20):x}", "E"]
    return L


def case_random(b, rng, n):
    """Anything a writer may do, in any order: the switch must answer as the model
    and the page must play as the Reference. Writers keep LE0 >= 0 (PR-3)."""
    nmax = b["nmax"]
    L = ["R 8", "G 2", "P 2"]
    strobes = 2
    while strobes < n - 4:
        r = rng.random()
        if r < 0.28:
            bk, i = rng.randrange(8), rng.randrange(16)
            if i == 0:
                d = rng.choice([rng.randrange(32, nmax // 2 + 1), rng.randrange(32, 129), rng.randrange(0, 64),
                                rng.randrange(nmax - 16, nmax + 16), rng.randrange(1 << 32)])
            elif i == 5:
                d = rng.choice([0, 13933, rng.randrange(0, 1 << 24)])
            else:
                d = rng.randrange(1 << 32)
            L.append(W(0x200 + 16 * bk + i, d))
        elif r < 0.33:
            L.append(W(0x280 + rng.randrange(8), rng.randrange(4)))
        elif r < 0.45:
            m = rng.choice([RESEED_RT, 0x9E3B | 1 << 16, 0x0220, 0x1C00, 0x01C0, rng.randrange(1 << 17)])
            L.append(W(0x288 + rng.randrange(8), m | rng.choice([0, ARM, ARM, ARM, GONOW])))
        elif r < 0.52:
            P = rng.choice([0, 1, 2, 3, 4, 8, 9, rng.randrange(16)])
            order = [rng.randrange(8) for _ in range(8)]
            if rng.random() < 0.6:
                order = rng.sample(range(8), 8)
            L.append(W(0x290, sweep_word(order, P=P)))
        elif r < 0.58:
            L.append(W(0x291, rng.choice([ARM, ARM, GONOW, 0])))
        elif r < 0.68:
            L.append(W(0x008, rng.choice([1, 2, 2, 3, 0])))
        elif r < 0.84:
            L.append(Q(rng.choice([0x000, 0x002, 0x009, 0x00A, 0x00B, 0x00C, 0x00D, 0x010, 0x011, 0x012, 0x013, 0x014,
                                   0x015, 0x016, 0x018,
                                   0x019, 0x020, 0x030, 0x040, 0x041, 0x042, 0x043, 0x292, 0x298, 0x299,
                                   0x200 + rng.randrange(128), 0x280 + rng.randrange(8), 0x288 + rng.randrange(8),
                                   0x290, 0x291, rng.randrange(1 << 12)])))
        elif r < 0.90:
            a = rng.choice([0x010, 0x011, 0x013, 0x015, 0x016, 0x019, 0x020, 0x030, 0x040, 0x299, rng.randrange(1 << 12)])
            d = {0x010: -rng.randrange(0, 8 << 26), 0x011: rng.choice([13933, 1 << 22, rng.randrange(1 << 20)]),
                 0x013: rng.randrange(32), 0x015: rng.randrange(2)}.get(a, rng.randrange(1 << 32))
            if a == 0x01C:
                d = 0
            L.append(W(a, d))
        elif r < 0.93:
            L.append(f"S {rng.choice([0, 0, 1, 2, 3]):x}")
        elif r < 0.95:
            L.append(f"K {rng.choice([0, 0, 1]):x}")
        else:
            g = rng.randrange(1, 4)
            L.append(f"G {g:x}")
            strobes += g
        if rng.random() < 0.12:
            L.append(f"N {rng.randrange(1, 800):x}")
            strobes += 0.4
    L += ["G 4", "E"]
    return L


def case_evidence(b, rng, n):
    """A short run for the VCD of the evidence: reset, the ROM's test origin, one block
    staged and fired by the host through the ISSP bit protocol, its hand-over and take."""
    v = MU.note_block(440.0, 64)
    L = ["R 8", "G 2"] + stage(1, v, rt=3) + [W(0x290, sweep_word([1])), W(0x291, ARM), W(0x008, 1),
                                               Q(0x009), "G 3", Q(0x00A), Q(0x00B), "G 1", "E"]
    return L


CASES = dict(origin=case_origin, music=case_music, reject=case_reject, timing=case_timing, bridge=case_bridge,
             random=case_random, evidence=case_evidence)


# ---------------------------------------------------------------------------
# checking
# ---------------------------------------------------------------------------
def check(ev, budget, case, extra=False):
    b = BUDGETS[budget]
    T = b["tmin"]
    probs, rep = [], []
    rom = rom_list(budget, extra)
    sw = SM.Switch(b["nmax"])
    X = [e for e in ev if e[0] == "X"]
    I = [e for e in ev if e[0] == "I"]
    S = [e[1] for e in ev if e[0] == "S"]
    R = [e[1] for e in ev if e[0] == "R"]
    Bv = [e[1] for e in ev if e[0] == "B"]
    Uv = [e for e in ev if e[0] == "U"]
    C = {e[1]: e for e in ev if e[0] == "C"}
    for e in ev:
        if e[0] == "T":
            probs.append(f"the bench timed out at clock {e[1]}")
        if e[0] == "F":
            probs.append(f"Formation error {CS.ERRN.get(e[2], e[2])} at clock {e[1]}")

    # ---- replay: events in clock order; within a clock EXEC, strobe, then presented writes -------
    by = {}
    for e in X: by.setdefault(e[1], []).append(("X", e))
    for e in Uv: by.setdefault(e[1], []).append(("U", e))
    for c in S: by.setdefault(c, []).append(("S", c))
    for c in Bv: by.setdefault(c, []).append(("B", c))
    for c in R: by.setdefault(c, []).append(("R", c))
    order = {"R": 0, "B": 1, "X": 2, "U": 2, "S": 3}
    sidx = {c: i for i, c in enumerate(S)}
    ctl_at = {}                                  # strobe cycle -> knobs the model holds then
    xbad = 0
    applied_reads = []
    cycles = sorted(by)
    for c in cycles:
        # writes presented in earlier clocks
        for p in sorted(k for k in list(sw.pend) if k < c):
            sw.presented(p)
        items = sorted(by[c], key=lambda t: order[t[0]])
        if any(t[0] == "S" for t in items):
            ctl_at[c] = (sw.mg_target, sw.mg_rate, sw.g_ctrl, sw.mute)
        for kind, e in items:
            if kind == "S":                          # the strobe takes this clock's presented write too
                sw.presented(c)
            if kind == "R":
                sw.reset()
            elif kind == "B":
                sw.taken(c)
            elif kind == "X":
                _, xc, port, we, a, d, rd, rj, live = e
                exp_rd, exp_rj = sw.exec(xc, port, we, a, d)
                if we:
                    exp_rd = 0
                elif exp_rd is None:
                    exp_rd = live
                if (rd, rj) != (exp_rd, exp_rj):
                    xbad += 1
                    if xbad <= 6:
                        probs.append(f"transaction at {xc} port {port} {'W' if we else 'R'} {a:03X} {d:08X}: RTL "
                                     f"{rd:08X} rej {rj} / model {exp_rd:08X} rej {exp_rj}")
                if not we and a in (0x00A, 0x00B):
                    applied_reads.append((xc, a, rd))
            elif kind == "U":
                sw.apply(c)
            elif kind == "S":
                sw.strobe(c, sidx[c])
        sw.presented(c)
    for p in sorted(sw.pend):
        sw.presented(p)
    if xbad > 6:
        probs.append(f"{xbad} transactions answered differently in all")
    probs += sw.problems[:10]
    rep.append(f"  switch: {len(X)} transactions ({sum(1 for e in X if e[2] == 0)} port 0, "
               f"{sum(1 for e in X if e[2] == 3)} port 3; {sum(e[7] for e in X)} refused), {len(Uv)} apply steps, "
               f"{len(S)} strobes: answers equal to switch_model's: {len(X) - xbad}/{len(X)}")

    # ---- the writes presented to the Formation's inbox port ------------------------------------------
    got = [(e[1], e[2], e[3]) for e in I]
    want = [(cyc, a, d) for cyc, a, d, _ in sw.ibx]
    if got != want:
        k = next((i for i, (g, w) in enumerate(zip(got, want)) if g != w), min(len(got), len(want)))
        probs.append(f"inbox-port writes differ from the model's at #{k}: RTL {got[k] if k < len(got) else None} / "
                     f"model {want[k] if k < len(want) else None} ({len(got)} vs {len(want)})")
    hand = [(e[1], e[5]) for e in I if e[4]]
    want_h = [(cyc, seq) for cyc, a, d, seq in sw.ibx if seq is not None]
    if hand != want_h:
        probs.append("hand-over side band (GO_SEQ carried) differs from the model's")
    rep.append(f"  inbox port: {len(got)} writes presented (clock, address, data) equal to the model's: {got == want}; "
               f"hand-overs {len(want_h)}")

    # ---- apply steps: 2 clocks after inbox_taken rose, before the next strobe ------------------------
    lag = []
    for u in Uv:
        prior = [bc for bc in Bv if bc < u[1]]
        if prior:
            lag.append(u[1] - prior[-1])
    if lag and (min(lag) < 2 or max(lag) > 4):
        probs.append(f"apply step {min(lag)}..{max(lag)} clocks after inbox_taken rose (2..4 expected)")
    margin = []
    for u in Uv:
        nxt = [s_ for s_ in S if s_ > u[1]]
        if nxt and u[2]:
            margin.append(nxt[0] - (u[1] + 1))
    if margin and min(margin) < 1:
        probs.append(f"an apply write landed {min(margin)} clocks before a strobe")
    if lag:
        rep.append(f"  apply step: {min(lag)}..{max(lag)} clocks after inbox_taken rose; its write lands "
                   f"{min(margin) if margin else '-'} clocks or more before the next strobe")

    # ---- the host path: commands vs port-0 transactions ---------------------------------------------
    cmdev = [e for e in ev if e[0] in ("W", "Q", "K") and not (e[0] == "K" and e[2] == 1)]
    p0 = [e for e in X if e[2] == 0]
    i = 0
    hbad = 0
    for e in cmdev:
        if e[0] == "W":
            if i + 1 >= len(p0) or not (p0[i][3] == 1 and p0[i][4] == e[2] and p0[i][5] == e[3]) or \
                    not (p0[i + 1][3] == 0 and p0[i + 1][4] == e[2]) or (e[4], e[5]) != (p0[i + 1][6], p0[i][7]):
                hbad += 1
                if hbad <= 3:
                    probs.append(f"host write {e[2]:03X} {e[3]:08X} (probe {e[4]:08X} rej {e[5]}) does not match port 0 "
                                 f"{p0[i:i + 2]}")
            i += 2
        elif e[0] == "Q":
            if i >= len(p0) or not (p0[i][3] == 0 and p0[i][4] == e[2]) or e[3] != p0[i][6]:
                hbad += 1
                if hbad <= 3:
                    probs.append(f"host read {e[2]:03X} (probe {e[3]:08X}) does not match port 0 {p0[i:i + 1]}")
            i += 1
        else:                                                      # KEY[0]: a GO_ALL on port 0
            if i >= len(p0) or (p0[i][3], p0[i][4], p0[i][5]) != (1, 0x008, 2):
                hbad += 1
                probs.append(f"KEY[0] at {e[1]} did not become a GO_ALL on port 0")
            i += 1
    if i != len(p0):
        probs.append(f"port 0 saw {len(p0) - i} transactions no command asked for")
    rep.append(f"  host path: {len([e for e in cmdev if e[0] == 'W'])} writes, {len([e for e in cmdev if e[0] == 'Q'])} "
               f"reads, {len([e for e in cmdev if e[0] == 'K'])} KEY[0] presses -> {len(p0)} port-0 transactions, "
               f"{'all' if not hbad else 'NOT all'} as commanded; probe answers equal: {hbad == 0}")

    # ---- the ROM on port 3 ----------------------------------------------------------------------------
    p3 = [e for e in X if e[2] == 3]
    runs, j = 0, 0
    while j < len(p3):
        seq = [(e[4], e[5]) for e in p3[j:j + len(rom)]]
        if seq != rom:
            probs.append(f"port 3 at {p3[j][1]}: not the ROM's list")
            break
        runs += 1
        j += len(rom)
    starts = len(R) + len([e for e in ev if e[0] == "K" and e[2] == 1]) + len(sw.rom_starts)
    rep.append(f"  ROM (port 3): {runs} complete plays of its {len(rom)} writes (resets {len(R)}, KEY[1] "
               f"{len([e for e in ev if e[0] == 'K' and e[2] == 1])}, TEST_ORIGIN {len(sw.rom_starts)}); refused: "
               f"{sum(e[7] for e in p3)}")
    if runs != starts:
        probs.append(f"the ROM played {runs} times, {starts} starts")

    # ---- knobs at each strobe -------------------------------------------------------------------------
    kbad = 0
    for c, (mgt, mgr, gc, mu) in ctl_at.items():
        e = C.get(c)
        if e is None or (e[2], e[3], e[4], e[5]) != (mgt, mgr, gc, mu):
            kbad += 1
            if kbad <= 3:
                probs.append(f"knobs at strobe {c}: RTL {e[2:6] if e else None} / model {(mgt, mgr, gc, mu)}")

    # ---- the sound: Reference pages from the model's takes, l1_model over the oracle ----------------
    step, _ = SS.load_step_toward(CS.ORACLE)
    takes = {sid: snaps for sid, snaps in sw.takes}
    segs = []
    bounds = R + [10 ** 18]
    for k in range(len(R)):
        segs.append([c for c in S if bounds[k] < c < bounds[k + 1]])
    ref = SS.Reference(step)
    L_ev = [e for e in ev if e[0] == "L"]
    O_ev = [e for e in ev if e[0] == "O"]
    nb = nbun = sbad = bbad = 0
    clr = sorted((cyc + 1, bits) for cyc, what, bits in sw.clears if what == "clip")   # pulse clock, bits
    for si, seg in enumerate(segs):
        ref.sweep = 0                                             # CR5-R1; blocks keep their values
        out = M.Output(g=12)
        mg_open = None
        pk = []
        prev3 = R[si]
        for k, c in enumerate(seg):
            g = SM.go_dict(takes.get(sidx[c], {}))
            n_played = [ref.blk[bk][0] for bk in range(8)]        # N as this sweep plays it (the GO lands after)
            obs = ref.sample(g)
            pk.append([(list(bun), n_played[bk]) for bk, bun in obs])
        for k, c in enumerate(seg):
            # bundles latched in sweep k
            nxt = seg[k + 1] if k + 1 < len(seg) else None
            lat = [e[3] for e in L_ev if e[1] > c and (nxt is None or e[1] <= nxt)]
            if nxt is not None:
                want_b = [bun for bun, _ in pk[k]]
                nbun += len(want_b)
                if lat != want_b:
                    bbad += 1
                    if bbad <= 3:
                        probs.append(f"sweep at strobe {c}: {len(lat)} bundles latched, not the Reference's {len(want_b)}")
            # the bank this strobe writes (it closes sweep k - 1)
            e = C.get(c)
            geff, soft = (e[6], e[7]) if e else (12, 0)
            mgt, mgr = ctl_at.get(c, (0, 13933, 0, 0))[:2]
            out.g, out.soft_mute, out.mg_target, out.mg_rate = geff, bool(soft), mgt, mgr
            al, ar = (0, 0) if k == 0 else M.sweep_acc(pk[k - 1], mg_open)
            for p_, bits in clr:                                  # CLIP write-1-to-clear pulses up to S+3
                if prev3 < p_ <= c + 3:
                    out.clip = [out.clip[0] and not bits & 1, out.clip[1] and not bits & 2]
            prev3 = c + 3
            mg_closed = out.mg
            bank = out.strobe(al, ar, mg_closed)
            want = (bank[0], bank[1], out.clip[0] | out.clip[1] << 1, out.mg)
            mg_open = out.mg
            o = [x for x in O_ev if c < x[1] <= c + 8]
            nb += 1
            if not o or (o[0][2], o[0][3], o[0][4], o[0][5]) != want:
                sbad += 1
                if sbad <= 5:
                    probs.append(f"sample closed at strobe {c}: RTL {o[0][2:6] if o else None} / model {want}")
    rep.append(f"  sound: {nbun} bundles in closed sweeps and {nb} output samples compared with sweep_sim.Reference "
               f"-> l1_model (customer's oracle): {nbun and bbad == 0} / {nb - sbad} of {nb} samples equal")
    # which takes could be heard: a block of the take plays in the sweep after it
    heard = tot = 0
    for sid, snaps in sw.takes:
        blks = {it for it in snaps if it != 8}
        if not snaps:
            continue
        tot += 1
        nxt = [e for e in L_ev if sid + 1 < len(S) and S[sid + 1] < e[1] <= (S[sid + 2] if sid + 2 < len(S) else 10 ** 18)]
        if blks & {e[2] for e in nxt} or 8 in snaps:
            heard += 1
    rep.append(f"  takes with items: {tot}; heard (a block of the take plays in the next sweep, or the sweep word "
               f"changes): {heard}")
    if case == "timing" and heard < tot:
        probs.append(f"the timing case let {tot - heard} takes go unheard")
    if sbad > 5:
        probs.append(f"{sbad} samples differ in all")

    # ---- Ch.5 §5.4.3: GO -> first sweep playing it -------------------------------------------------
    # a GO accepted (EXEC) in clock e is handed over in e + 1 and taken by the first strobe at or
    # after e + 1 (RH004); the sweep that plays it starts at the strobe after that. Counted in
    # strobes after the acceptance, that is the second at the latest.
    fire_at = {s_: cyc - 1 for cyc, a, d, s_ in sw.ibx if s_ is not None}
    lat_c, lat_n = [], []
    for s_, ex in fire_at.items():
        after = [c for c in S if c > ex]
        if len(after) >= 2:
            took = next(c for c in after if c >= ex + 1)
            play = after[after.index(took) + 1]
            lat_c.append(play - ex)
            lat_n.append(after.index(play) + 1)
    if lat_c:
        per = 1e6 / 48 / (b["half"] * 2)            # the true sample period in clk_sys clocks
        rep.append(f"  GO -> first sweep playing it: {min(lat_c)} .. {max(lat_c)} clocks = {min(lat_c) / per:.4f} .. "
                   f"{max(lat_c) / per:.4f} periods, from strobe {min(lat_n)} .. {max(lat_n)} after the GO, over "
                   f"{len(lat_c)} GOs (Ch.5 §5.4.3: <= 2)")
        if max(lat_n) > 2:
            probs.append(f"a GO played from strobe {max(lat_n)} after its acceptance")
    # hand-over positions relative to the strobe (timing case)
    pos = []
    for s_, ex in fire_at.items():
        land = ex + 1
        near = min(S, key=lambda c: abs(c - land)) if S else None
        if near is not None:
            pos.append(land - near)
    close = sorted(set(p for p in pos if -3 <= p <= 3))
    rep.append(f"  hand-overs presented at strobe offsets (clocks, -3..+3 seen): {close}")
    if case == "timing" and not {-1, 0, 1} <= set(close):
        probs.append(f"the timing case did not place hand-overs at -1, 0 and +1 ({close})")
    if case == "origin":
        pcm = [abs(o[2]) for o in O_ev]
        pk_ = max(pcm) if pcm else 0
        db = 20 * math.log10(pk_ / 2 ** 23) if pk_ else float("-inf")
        rep.append(f"  test origin from the ROM (N = {b['nmax']}), G = 12: PCM peak {pk_} = {db:.2f} dBFS over {len(O_ev)} "
                   f"samples (phase4_l1.md: -12.44 dBFS for N = 1,008, -6.29 for N = 2,048)")
    y = [e for e in ev if e[0] == "Y"]
    if y:
        _, iv, mn, mx, scm, ov = y[0]
        rep.append(f"  strobe interval {mn}..{mx} clocks; SWEEP_CLOCKS_MAX {scm} (T_min {T}); overrun {ov}")
        if ov:
            probs.append("L1 overrun")
    return probs, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=list(CASES))
    ap.add_argument("--budget", type=int, default=50, choices=(50, 100))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(SWD, "build", "cosim"))
    ap.add_argument("--report", default=None)
    ap.add_argument("--rtl", default=None)
    ap.add_argument("--vcd", default=None)
    ap.add_argument("--rom-extra", action="store_true", help="a test ROM image with a TEST_ORIGIN write")
    a = ap.parse_args()
    if a.rtl:
        RTLDIRS.insert(0, a.rtl)
    b = BUDGETS[a.budget]
    n = a.samples or dict(origin=120, music=0, reject=60, timing=0, bridge=50, random=300, evidence=0)[a.case]
    out = os.path.join(a.out, f"{a.case}_{a.budget}_{a.seed}")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    rng = random.Random(a.seed)
    exe = build(out, a.budget, a.rom_extra)
    stim = CASES[a.case](b, rng, n)
    ev, warn = simulate(exe, out, stim, a.vcd)
    probs, rep = check(ev, a.budget, a.case, a.rom_extra)
    probs = [f"simulator: {w}" for w in warn[:5]] + probs
    head = (f"cosim_switch {a.case} (seed {a.seed}): wpms_system on the 48 kHz grid, host path by the deterministic "
            f"controller through the ISSP bit protocol — evidence class RTL-SIM; NMAX {b['nmax']}, T_min {b['tmin']} "
            f"({a.budget} MHz budget)")
    lines = [head] + rep + [f"  FAIL {p}" for p in probs[:25]]
    lines.append(f"cosim_switch {a.case}: {'PASS' if not probs else 'FAIL'} ({time.time() - t0:.0f} s)")
    text = "\n".join(lines)
    print(text)
    if a.report:
        open(a.report, "w").write(text + "\n")
    sys.exit(0 if not probs else 1)


if __name__ == "__main__":
    main()
