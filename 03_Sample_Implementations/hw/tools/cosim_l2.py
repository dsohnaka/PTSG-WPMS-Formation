#!/usr/bin/env python3
# ============================================================================
# cosim_l2.py — Phase 2 cosimulation: hw/l2/wpms_formation.v against the golden
# model pfasm_tools_w.Machine (imported, never edited), one instruction per clock.
#
#   python3 cosim_l2.py [--random N] [--seed S] [--jobs J] [--out DIR] [--only g1,g2]
#                       [--report FILE] [--rtl DIR]
#
# Case groups (SILICON_BRIEF_2026-09-27 Phase 2):
#   packet    wpms_packet.pfasm in packet windows, several CUR blocks per case
#   hk        wpms_housekeeping.pfasm (BCP) in HK with random take-sets and sweep items
#   fwd       BCP followed at once by reads and writes of slots still being copied
#   exp       exp_maclaurin_w.pfasm in HK, x = -0.50 .. +0.50 step 0.05 (21 values)
#   neg       the 13 cases of negative_tests.py, on the hardware
#   e4        encodings the assembler never emits (hardware-only E4)
#   prefetch  the prefetch port: N window [N_MIN, NMAX] (EW2) and the bundle order
#   timing    directed cases traced clock by clock (the report's clock table)
#   random    random contract sequences: BCP mid-program, strobes, idle gaps, taps
#   late      directed cases for what SD-22 step 2 changed (Formation RH006): the
#             instruction right behind an overflowing MUL/MAC (squashed), a prefetch's
#             EW2 in a MUL's X clock (with and without its E8), a read right after BCP
#             of a slot it made pending, a strobe in the clock BCP is issued
#
# EXPECTED VALUES come from the model, run one instruction at a time. The model
# records errors and continues; the hardware halts at the first one. So for an
# erroring case the expected scene is the model's state just before the erroring
# instruction, with that error's code and the instruction's index (and nothing of
# what follows executes). Validator-level E4 (the removed rows RTW CMT PSH POP WSV
# and STA ADRS) comes from T.validate; encodings with no .pfasm form expect E4 by
# decode_map.json's must-be-zero rule. The model keeps no LoopVal/JumpVal; they
# are expected per Map v0.3 §3 (WLV: LoopVal <- Accm[11:0], WJV: JumpVal <- Accm[11:0]).
# Evidence class of every result printed here: RTL-SIM (Icarus Verilog).
# License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
# 002 2026-10-03       Claude Code   Chg : the simulator's ERROR lines count with its warnings (the
#                                          Formation's own checks, RH005/RH006, print ERROR).
# 003 2026-10-03       Claude Code   Add : group late (SD-22 step 2), generated after every other group
#                                          (their seed stream and cases are unchanged); step J, an issue
#                                          with a strobe in the same clock (wpms_formation_tb.v RH003).
# ============================================================================
import argparse, json, math, os, random, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True                              # keep the golden tools directory clean
HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
S3 = os.path.normpath(os.path.join(HW, ".."))                # 03_Sample_Implementations
TOOLS = os.path.join(S3, "tools")
LISTS = os.path.join(S3, "instruction_lists")
L2 = os.path.join(HW, "l2")
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)
import pfasm_tools_w as T                                    # golden model (never edited)
import sweep_sim as SS                                       # golden sequencer pieces: strobe, prefetch, rand_block
import pfasm_as as A                                         # the assembler (decode_map.json)

ISA = json.load(open(os.path.join(TOOLS, "isa_table_w.json")))
DM = A.DM
ERR = {k: v["code"] for k, v in DM["error_codes"].items()}
ERR_NAME = {v: k for k, v in ERR.items()}
M32 = (1 << 32) - 1


def u32(v): return v & M32
def bits_of(s): return sum(1 << b for b in s)


# ============================================================================
#  The model side: the golden Machine plus the hardware's halt semantics
# ============================================================================
def clone_machine(mc):
    """Copy of a Machine (lists, nested lists and sets copied; scalars shared)."""
    c = T.Machine.__new__(T.Machine)
    for k, v in mc.__dict__.items():
        if isinstance(v, list): v = [r[:] if isinstance(r, list) else r for r in v]
        elif isinstance(v, set): v = set(v)
        setattr(c, k, v)
    return c


class Model:
    def __init__(self, store, inbox, regs):
        mc = T.Machine()
        mc.store = [T.s32(v) for v in store]
        mc.inbox = [[T.s32(v) for v in row] for row in inbox]
        for i in (13, 14):
            for row in mc.inbox: row[i] = 0                  # not stored (Map v0.3 §4: +D reads 0, +E is RTOUT)
        mc.accm, mc.temp = T.s32(regs["accm"]), T.s32(regs["temp"])
        mc.adrs, mc.shv, mc.sweep_a = regs["adrs"], regs["shv"], regs["sweep_a"]
        self.mc = mc
        self.phase, self.cur, self.q = "HK", 0, 0
        self.quartet = dict(K=0, I=0, SN=0, SSS=0)
        self.loopval = self.jumpval = 0
        self.err = None                                      # (code, index, sn) of the first error
        self.ireq = 0
        self.n = 0                                           # index of the next issued instruction

    halted = property(lambda self: self.err is not None)

    def clone(self):
        c = Model.__new__(Model)
        c.__dict__ = dict(self.__dict__)
        c.mc = clone_machine(self.mc)
        c.quartet = dict(self.quartet)
        return c

    # ---- steps ------------------------------------------------------------
    def switch(self, a, d):                                  # the input switch (Map v0.3 §4; customer Ch.5 §5.6.2)
        mc = self.mc
        if a < 0x80: mc.inbox[a >> 4][a & 15] = T.s32(d) if (a & 15) not in (13, 14) else 0
        elif a < 0x88: mc.rtout_staged[a & 7] = d & 0xFFFF
        elif a < 0x90: mc.commit[a & 7] = d & 0x1FFFF; mc.armed[a & 7] = bool((d >> 30) & 1)
        elif a == 0x90: mc.sweep_staged = d & 0xFFFFFFF
        elif a == 0x91: mc.sweep_armed = bool((d >> 30) & 1)

    def strobe(self):
        SS.Sequencer(self.mc, None, None).strobe()           # the golden take-set latch

    def ctx(self, pkt, cur, q, k, i, sn, sss):
        self.phase, self.cur, self.q = ("PKT" if pkt else "HK"), cur, q
        self.quartet = dict(K=k, I=i, SN=sn, SSS=sss)

    def error(self, name, idx):
        self.err = (ERR[name], idx, self.quartet["SN"]); self.ireq = 1

    def issue(self, item):
        """One instruction. Returns the error name it raised (None if it committed)."""
        idx = self.n; self.n += 1
        if self.halted: return None
        if item.get("raw"):                                  # no .pfasm form: E4 by the must-be-zero rule
            self.error("E4", idx); return "E4"
        v = T.validate([item], ISA)
        if any("E4" in e for e in v):
            self.error("E4", idx); return "E4"
        if v: raise RuntimeError(f"validator: {v}")          # E1/E2/literal: never generated here
        mc = self.mc; snap = clone_machine(mc)
        mc.q = self.q
        e0 = len(mc.errors)
        mc.run([item], self.phase, cur=self.cur, quartet=self.quartet)
        if len(mc.errors) > e0:
            name = mc.errors[e0].split()[0]
            self.mc = snap                                   # hardware: the violator commits nothing
            self.error(name, idx); return name
        if item["mn"] == "WLV": self.loopval = u32(mc.accm) & 0xFFF
        if item["mn"] == "WJV": self.jumpval = u32(mc.accm) & 0xFFF
        return None

    def prefetch(self, b):
        mc = self.mc
        want = (u32(mc.store[b * 16]),) + SS.bundle_of(mc.store[b * 16:b * 16 + 16])
        if not self.halted:
            sq = SS.Sequencer(mc, None, None); sq.prefetch(b)  # the golden EW2 check
            if sq.errors: self.error("EW2", -1)
        return want

    def ack(self):
        self.ireq = 0

    def scene(self):
        mc = self.mc
        e = self.err or (0, -1, 0)
        return dict(flag=int(self.err is not None), code=e[0], idx=e[1], sn=e[2],
                    accm=u32(mc.accm), temp=u32(mc.temp), adrs=mc.adrs & 0x3FF, shv=mc.shv & 31,
                    sweep_a=mc.sweep_a, copied=bits_of(mc.copied), take=bits_of(mc.take),
                    swcop=int(mc.sweep_copied), taken=int(mc.inbox_taken),
                    loopval=self.loopval, jumpval=self.jumpval, ireq=self.ireq, busy=0,
                    store=[u32(v) for v in mc.store])


# ============================================================================
#  Cases
# ============================================================================
def ins(mn, op=None, allow_removed=False):
    return dict(word=A.encode(mn, op, allow_removed), mn=mn, op=op, band="BG", ln=0)


def raw(word, why):
    return dict(word=word, raw=True, mn="(raw)", op=why, band="BG", ln=0)


def prog_text(text, allow_removed=False):
    f = tempfile.NamedTemporaryFile("w", suffix=".pfasm", delete=False)
    f.write(text); f.close()
    try:
        return A.assemble(T.parse(f.name), allow_removed)
    finally:
        os.unlink(f.name)


def prog_file(name):
    return A.assemble_file(os.path.join(LISTS, name))


class Case:
    def __init__(self, group, name):
        self.group, self.name = group, name
        self.store = [0] * 128
        self.inbox = [[0] * 16 for _ in range(8)]
        self.regs = dict(accm=0, temp=0, adrs=0, shv=0, sweep_a=0)
        self.steps = []
        self.post = None                   # optional extra check: f(case, hw_records, exp_records) -> [problems]
        self.gen = None                    # generator-side model (random group)
        self.want_err = None               # sanity: the error the case is written to provoke
        self.note = ""

    def start_model(self):
        self.gen = Model(self.store, self.inbox, self.regs)
        return self.gen

    def _step(self, st):
        self.steps.append(st)
        m = self.gen
        if m is None: return None
        k = st[0]
        if k == "X": m.switch(st[1], st[2])
        elif k == "S": m.strobe()
        elif k == "Q": m.ctx(*st[1:])
        elif k == "I": return m.issue(st[1])
        elif k == "J": m.strobe(); return m.issue(st[1])
        elif k == "P": m.prefetch(st[1])
        elif k == "K": m.ack()
        return None

    def sw(self, a, d): self._step(("X", a, d))
    def strobe(self): self._step(("S",))
    def ctx(self, pkt=0, cur=0, q=0, k=0, i=0, sn=0, sss=0): self._step(("Q", pkt, cur, q, k, i, sn, sss))
    def ins(self, item): return self._step(("I", item))
    def ins_strobe(self, item): return self._step(("J", item))  # issued in the strobe's clock: after it
    def prog(self, items, gap=None):
        for n, it in enumerate(items):
            if gap and n:
                g = gap()
                if g: self.idle(g)
            self.ins(it)
    def idle(self, n): self._step(("N", n))
    def prefetch(self, b): self._step(("P", b))
    def wait(self): self._step(("W",))
    def ack(self): self._step(("N", 1)); self._step(("K",))      # the Core acknowledges an insertion it has seen
    def trace(self, on): self._step(("V", on))
    def dump(self): self._step(("W",)); self._step(("D",))


def expect(case):
    m = Model(case.store, case.inbox, case.regs)
    out = []
    for st in case.steps:
        k = st[0]
        if k == "X": m.switch(st[1], st[2])
        elif k == "S": m.strobe()
        elif k == "Q": m.ctx(*st[1:])
        elif k == "I": m.issue(st[1])
        elif k == "J": m.strobe(); m.issue(st[1])
        elif k == "P": out.append(("F", m.prefetch(st[1])))
        elif k == "K": m.ack()
        elif k == "D": out.append(("D", m.scene()))
    return out, m


def taps(rng):
    return dict(k=rng.randrange(1 << 12), i=rng.randrange(1 << 16), sn=rng.randrange(1 << 12), sss=rng.randrange(1 << 12))


def rand_val(rng):
    bits = rng.choice([0, 1, 3, 5, 8, 12, 16, 20, 24, 28, 30, 31, 32])
    v = rng.randrange(1 << bits) if bits else 0
    return T.s32(-v if rng.random() < 0.5 else v)


def rand_sweep(rng, Nof, kind="valid"):
    if kind == "invalid_P":
        return rng.randrange(9, 16) | (rng.getrandbits(24) << 4)
    if kind == "dup":
        P = rng.randrange(2, 9); order = rng.sample(range(8), P - 1); order.insert(rng.randrange(P), rng.choice(order))
        return T.make_sweep(order)
    P = rng.randrange(0, 9); order = rng.sample(range(8), P)
    if kind == "valid":
        while order and sum(Nof(b) for b in order) > T.NMAX: order.pop()
    return T.make_sweep(order)


# ---- packet: wpms_packet in packet windows over several CUR blocks ------------
def gen_packet(rng, n):
    pkt = prog_file("wpms_packet.pfasm")
    cases = []
    for c in range(n):
        case = Case("packet", f"packet-{c}")
        for b in range(8):
            case.store[b * 16:b * 16 + 16] = SS.rand_block(rng, rng.randrange(T.N_MIN, 513))
        case.regs.update(accm=rand_val(rng), temp=rand_val(rng), adrs=rng.randrange(0x200), shv=rng.randrange(32))
        P = rng.randrange(1, 9); order = rng.sample(range(8), P)
        for _ in range(rng.randrange(1, 4)):                  # 1..3 sweeps
            for q, b in enumerate(order):
                case.ctx(pkt=1, cur=b, q=q, **taps(rng))
                case.prog(pkt)                               # back to back, one per clock
                if rng.random() < 0.5: case.idle(rng.randrange(1, 5))
        case.note = f"order {order}"
        case.dump()
        cases.append(case)
    return cases


# ---- hk: wpms_housekeeping (BCP) with random take-sets and sweep items --------
PRESET_MASKS = list(SS.PRESETS.values())


def fill_go(case, rng, Nstore, sweep_kind, nmax_bias=False):
    """Inbox contents (initial), COMMIT/RTOUT writes, a sweep item; no strobe."""
    inN = []
    for b in range(8):
        N = rng.randrange(T.N_MIN, 1100 if nmax_bias else 257)
        vals = SS.rand_block(rng, N)
        case.inbox[b] = vals; inN.append(N)
    masks = {}
    for b in range(8):
        if rng.random() < 0.7:
            mask = rng.choice(PRESET_MASKS + [rng.randrange(1 << 17), 0x1FFFF, 0x1FFFF])
            armed = rng.random() < 0.75
            case.sw(0x88 + b, mask | (armed << 30) | (rng.getrandbits(1) << 20))   # bit 20: ignored by the port
            if armed: masks[b] = mask
        if rng.random() < 0.6: case.sw(0x80 + b, rng.randrange(1 << 16))
    Nof = lambda b: inN[b] if (b in masks and masks[b] & 1) else Nstore[b]
    if sweep_kind != "none":
        w = rand_sweep(rng, Nof, "valid" if sweep_kind == "valid" else sweep_kind)
        case.sw(0x90, w)
        case.sw(0x91, (rng.random() < 0.85) << 30)
    return Nof


def gen_hk(rng, n):
    hk = prog_file("wpms_housekeeping.pfasm")
    cases = []
    kinds = ["valid"] * 5 + ["none", "invalid_P", "dup", "over", "backstop"]
    for c in range(n):
        kind = kinds[c % len(kinds)]
        case = Case("hk", f"hk-{c}-{kind}")
        Nstore = [rng.randrange(T.N_MIN, 257) for _ in range(8)]
        for b in range(8):
            case.store[b * 16:b * 16 + 16] = SS.rand_block(rng, Nstore[b])
        order = rng.sample(range(8), rng.randrange(0, 9))
        while sum(Nstore[b] for b in order) > T.NMAX: order.pop()
        case.regs.update(sweep_a=T.make_sweep(order), accm=rand_val(rng), temp=rand_val(rng), shv=rng.randrange(32))
        Nof = fill_go(case, rng, Nstore, "valid" if kind in ("over", "backstop") else kind,
                      nmax_bias=kind in ("over", "backstop"))
        if kind == "over":                                   # a sweep item whose post-copy sum N > NMAX
            ords = sorted(range(8), key=Nof, reverse=True); o = []
            for b in ords:
                o.append(b)
                if sum(Nof(x) for x in o) > T.NMAX: break
            case.sw(0x90, T.make_sweep(o)); case.sw(0x91, 1 << 30)
        if kind == "backstop":                               # no item; the new N push the sweep in effect over NMAX
            case.sw(0x91, 0)
            o = sorted(range(8), key=Nof, reverse=True)
            case.regs["sweep_a"] = T.make_sweep(o)
            case.store[0::16] = [T.N_MIN] * 8                # the sweep in effect fits before the copy
        case.strobe()
        case.ctx(pkt=0, **taps(rng))
        case.prog(hk)
        if rng.random() < 0.3: case.prog(hk)                 # a second BCP: nothing new to copy
        case.dump()
        case.note = kind
        cases.append(case)
    return cases


# ---- fwd: reads and writes of slots whose copy is still landing ---------------
def gen_fwd(rng, n):
    cases = []
    for c in range(n):
        case = Case("fwd", f"fwd-{c}")
        for b in range(8):
            case.store[b * 16:b * 16 + 16] = SS.rand_block(rng, rng.randrange(T.N_MIN, 257))
        for b in range(8):
            case.inbox[b] = SS.rand_block(rng, rng.randrange(T.N_MIN, 257))
        taken = sorted(rng.sample(range(8), rng.randrange(1, 9)))
        for b in taken:
            case.sw(0x88 + b, rng.choice([0x1FFFF, 0x1FFFF, PRESET_MASKS[0], rng.randrange(1 << 17)]) | (1 << 30))
            case.sw(0x80 + b, rng.randrange(1 << 16))
        case.sw(0x91, 0)
        case.strobe()
        case.ctx(pkt=0, **taps(rng))
        case.ins(ins("BCP"))
        # right behind BCP: reads of the last-copied blocks, writes into pending slots,
        # read-back of what was just written, and moves of copied words to other slots
        late = taken[::-1]
        for k in range(rng.randrange(4, 14)):
            b = rng.choice(late[:3]); s = rng.randrange(16)
            r = rng.random()
            if r < 0.35:
                case.ins(ins("SAD", hex(b * 16 + s))); case.ins(ins("LDM"))
                case.ins(ins("SAD", hex(rng.randrange(8) * 16 + rng.randrange(16)))); case.ins(ins("STM"))
            elif r < 0.6:
                case.ins(ins("LDA", f"#{rng.randrange(-32768, 32768)}"))
                case.ins(ins("SAD", hex(b * 16 + s))); case.ins(ins("STM"))
            elif r < 0.8:
                case.ins(ins("SAD", hex(b * 16 + s))); case.ins(ins("LDA", "@PPM")); case.ins(ins("ADD", "@PPM"))
                case.ins(ins("STA", "@PPM"))
            else:
                case.ins(ins("SAD", hex(0x110 + b))); case.ins(ins("LDM"))    # COMMIT view: take/copied bits
            if rng.random() < 0.2: case.idle(1)
        case.dump()
        case.note = f"taken {taken}"
        cases.append(case)
    return cases


# ---- exp: the master's first program on the profile --------------------------
EXP_Q = 28


def exp_fix(v): return int(round(v * (1 << EXP_Q)))


def gen_exp(rng):
    prog = prog_file("exp_maclaurin_w.pfasm")
    coef = [exp_fix(1 / math.factorial(n)) for n in range(9, -1, -1)]
    cases = []
    for i in range(-10, 11):
        x = i * 0.05
        case = Case("exp", f"exp-x{x:+.2f}")
        case.store[:11] = [exp_fix(x)] + coef
        case.ctx(pkt=0, **taps(rng))
        case.prog(prog)
        case.dump()
        case.x = x
        cases.append(case)
    return cases


# ---- neg: negative_tests.py N1..N13 on the hardware ----------------------------
def gen_neg(rng):
    PKT = open(os.path.join(LISTS, "wpms_packet.pfasm")).read()
    cases = []

    def blk(case, b=0, N=64, LE0=100):
        case.store[b * 16] = N; case.store[b * 16 + 5] = LE0

    c = Case("neg", "N1 direct store write in a packet window"); blk(c); c.want_err = "EW4"
    c.ctx(pkt=1, cur=0, sn=0x101); c.prog(prog_text(".bg\n SAD 0x006\n LDM\n SAD 0x00A\n ADD @PPM\n SAD 0x006\n STM\n")); c.dump(); cases.append(c)
    c = Case("neg", "N2 BCP in a packet window"); blk(c); c.want_err = "EW4"
    c.ctx(pkt=1, cur=0, sn=0x102); c.prog(prog_text(".bg\n BCP\n")); c.dump(); cases.append(c)
    c = Case("neg", "N3 CUR write in HK"); blk(c); c.want_err = "EW4"
    c.ctx(pkt=0, sn=0x103); c.prog(prog_text(".bg\n SAD 0x106\n STM\n")); c.dump(); cases.append(c)
    c = Case("neg", "N4 STM into the inbox"); blk(c); c.want_err = "EW3"
    c.ctx(pkt=0, sn=0x104); c.prog(prog_text(".bg\n SAD 0x082\n STM\n")); c.dump(); cases.append(c)
    c = Case("neg", "N5 STP with LE0 < 0"); blk(c, LE0=-1); c.want_err = "EW6"
    c.ctx(pkt=1, cur=0, sn=0x105); c.prog(prog_text(PKT)); c.dump(); cases.append(c)
    c = Case("neg", "N6 sweep word repeats a block"); c.store[0] = c.store[16] = 64; c.want_err = "EW5"
    c.sw(0x90, T.make_sweep([0, 1, 0])); c.sw(0x91, 1 << 30); c.strobe()
    c.ctx(pkt=0, sn=0x106); c.prog(prog_text(".bg\n BCP\n")); c.dump(); cases.append(c)
    c = Case("neg", "N7 sweep sum N > NMAX"); c.store[0] = c.store[16] = 1100; c.want_err = "EW5"
    c.sw(0x90, T.make_sweep([0, 1])); c.sw(0x91, 1 << 30); c.strobe()
    c.ctx(pkt=0, sn=0x107); c.prog(prog_text(".bg\n BCP\n")); c.dump(); cases.append(c)
    for name, text in (("N8 CMT (no page pair)", ".q\n CMT\n"), ("N9 WSV (sequencer owns stay_value)", ".bg\n WSV\n"),
                       ("N10 PSH (no data stack)", ".bg\n PSH\n"), ("N11 STA ADRS (W-F1)", ".bg\n STA ADRS\n")):
        c = Case("neg", name); blk(c); c.want_err = "E4"
        c.ctx(pkt=0, sn=0x108)
        c.prog(prog_text(".bg\n LDA #77\n STA TEMP\n") + prog_text(text, allow_removed=True) + prog_text(".bg\n LDA #5\n"))
        c.dump(); cases.append(c)
    # N12: the mutant window (PH0 advanced twice), exactly negative_tests.py's edit
    mut = PKT.replace("        LDM                     ; A = PHD1",
                      "        SAD     0x106\n        LDM\n        SAD     0x10A\n        ADD     @PPM\n        SAD     0x106\n"
                      "        STM\n        SAD     0x107\n        LDM                     ; A = PHD1")
    assert mut != PKT
    for k in range(3):
        c = Case("neg", f"N12 mutant window (PH0 advanced twice) caught #{k}")
        for b in range(8): c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, rng.randrange(T.N_MIN, 513))
        cur = rng.randrange(8)
        c.ctx(pkt=1, cur=cur, **taps(rng)); c.prog(prog_text(mut)); c.dump()
        good = Case("neg", "reference"); good.store = list(c.store); good.ctx(pkt=1, cur=cur); good.prog(prog_text(PKT)); good.dump()
        ref = expect(good)[0][-1][1]

        def post(case, hw, exp, ref=ref, cur=cur):
            got = hw[-1][1]["store"]
            if got == ref["store"]:
                return ["N12: the mutant's scene equals the correct window's: the comparison would not bite"]
            diff = [f"slot 0x{a & 15:X} of block {a >> 4}" for a in range(128) if got[a] != ref["store"][a]]
            case.note = f"mutant differs from the correct window at {', '.join(diff)} (cur {cur})"
            return []
        c.post = post
        cases.append(c)
    c = Case("neg", "N13 block N = 16 < N_MIN at prefetch"); c.store[0] = 16; c.want_err = "EW2"
    c.ctx(pkt=0, sn=0x10D); c.prefetch(0); c.ins(ins("LDA", "#9")); c.dump(); cases.append(c)
    return cases


# ---- e4: encodings with no .pfasm form ---------------------------------------
def gen_e4(rng):
    cases = []
    legal = {(s["mode"], s["subop"]): (mn, s["kind"]) for mn, s in DM["instructions"].items()}
    removed = {(s["mode"], s["subop"]): mn for mn, s in DM["removed_rows_E4"].items()}
    words = []
    for mode in range(16):
        for subop in range(16):
            if (mode, subop) in legal: continue
            what = f"removed row {removed[(mode, subop)]}" if (mode, subop) in removed else \
                   ("mode 0 (never issued by the Core)" if mode == 0 else
                    f"mode {mode} unassigned" if mode >= 5 else f"sub-op {mode}.{subop} unassigned")
            words.append((A.word(mode, subop, rng.randrange(16) if rng.random() < 0.5 else 0,
                                 rng.randrange(1 << 16) if rng.random() < 0.5 else 0), f"{mode}.{subop} {what}"))
    for (mode, subop), (mn, kind) in sorted(legal.items()):
        if kind == "none":
            words.append((A.word(mode, subop, rng.randrange(1, 16), 0), f"{mn}: register-ID field not 0"))
            words.append((A.word(mode, subop, 0, rng.randrange(1, 1 << 16)), f"{mn}: immediate field not 0"))
            words.append((A.word(mode, subop, 0, 0x8000), f"{mn}: immediate bit 15 set"))
        elif kind == "src":
            for rid in range(7, 16):
                words.append((A.word(mode, subop, rid, 0), f"{mn}: source ID {rid} reserved"))
            for rid in range(1, 7):
                words.append((A.word(mode, subop, rid, rng.randrange(1, 1 << 16)), f"{mn}: source ID {rid} with immediate not 0"))
        elif kind == "dst":
            for rid in range(2, 16):
                words.append((A.word(mode, subop, rid, 0), f"{mn}: destination ID {rid} " + ("(ADRS, W-F1)" if rid == 6 else "reserved/unimplemented")))
            for rid in (0, 1):
                words.append((A.word(mode, subop, rid, rng.randrange(1, 1 << 16)), f"{mn}: destination {rid} with immediate not 0"))
        elif kind == "lit9":
            words.append((A.word(mode, subop, rng.randrange(1, 16), 0x005), f"{mn}: register-ID field not 0"))
            for bit in range(9, 16):
                words.append((A.word(mode, subop, 0, (1 << bit) | rng.randrange(0x200)), f"{mn}: literal bit {bit} set"))
        elif kind == "shift":
            words.append((A.word(mode, subop, rng.randrange(1, 16), 3), f"{mn}: register-ID field not 0"))
    for w, why in words:
        c = Case("e4", f"E4 0x{w:08X} {why}"); c.want_err = "E4"
        c.store[:16] = SS.rand_block(rng, 64)
        c.ctx(pkt=rng.getrandbits(1), cur=rng.randrange(8), **taps(rng))
        c.prog([ins("LDA", f"#{rng.randrange(-32768, 32768)}"), ins("STA", "TEMP"), ins("SAD", "0x005"),
                raw(w, why), ins("LDA", "#1"), ins("SAD", "0x000"), ins("WSH")])
        c.dump(); cases.append(c)
    # the boundary on the legal side: every field at its extreme, accepted
    c = Case("e4", "legal extremes accepted")
    c.ctx(pkt=0, **taps(rng))
    c.prog([ins("SAD", "0x1FF"), ins("LDA", "#-32768"), ins("SFT", "32767"), ins("SFT", "-1"), ins("LDA", "#32767"),
            ins("SFT", "15"), ins("LDA", "#0"), ins("SFT", "-32768"), ins("SAD", "0x000"), ins("LDA", "SSS"), ins("ADD", "SN"),
            ins("ADD", "I"), ins("ADD", "K"), ins("STA", "TEMP")])
    c.dump(); cases.append(c)
    return cases


# ---- prefetch: N window and bundle order ---------------------------------------
def gen_prefetch(rng):
    cases = []
    for N in (16, 31, 32, 33, 64, 2047, 2048, 2049, 0, -1, -2048, 0x7FFFFFFF, -0x80000000):
        b = rng.randrange(8)
        c = Case("prefetch", f"prefetch N={N} block {b}")
        for k in range(8): c.store[k * 16:k * 16 + 16] = [rand_val(rng) for _ in range(16)]
        c.store[b * 16] = N
        c.want_err = "EW2" if not (T.N_MIN <= N <= T.NMAX) else None
        c.ctx(pkt=0, sn=0x200 + (N & 0xFF))
        c.prefetch(b); c.ins(ins("LDA", "#3")); c.dump(); cases.append(c)
    c = Case("prefetch", "prefetch after BCP has landed (bundle of the new block)")
    for b in range(8):
        c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, rng.randrange(T.N_MIN, 257))
        c.inbox[b] = SS.rand_block(rng, rng.randrange(T.N_MIN, 257))
        c.sw(0x88 + b, 0x1FFFF | (1 << 30)); c.sw(0x80 + b, rng.randrange(1 << 16))
    c.sw(0x90, T.make_sweep([3, 1, 4])); c.sw(0x91, 1 << 30); c.strobe()
    c.ctx(pkt=0); c.ins(ins("BCP")); c.wait()
    for b in range(8): c.prefetch(b)
    c.dump(); cases.append(c)
    return cases


# ---- timing: traced directed cases ---------------------------------------------
def gen_timing(rng):
    cases = []
    c = Case("timing", "T1 packet window back to back")
    for b in range(8): c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, 64)
    c.ctx(pkt=1, cur=5, q=2, **taps(rng)); c.trace(1); c.prog(prog_file("wpms_packet.pfasm")); c.idle(2); c.trace(0); c.dump()
    cases.append(c)
    for nb in (0, 1, 8):
        c = Case("timing", f"T2 BCP with {nb} taken block(s) and a sweep item")
        for b in range(8):
            c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, 128)
            c.inbox[b] = SS.rand_block(rng, 128)
        for b in range(nb): c.sw(0x88 + b, 0x1FFFF | (1 << 30))
        c.sw(0x90, T.make_sweep(list(range(8)))); c.sw(0x91, 1 << 30); c.strobe()
        c.ctx(pkt=0); c.trace(1); c.ins(ins("BCP")); c.idle(12); c.trace(0); c.dump(); cases.append(c)
    c = Case("timing", "T3 BCP then store traffic at once (copy paused, forwarding)")
    for b in range(8):
        c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, 128)
        c.inbox[b] = SS.rand_block(rng, 128)
        c.sw(0x88 + b, 0x1FFFF | (1 << 30))
    c.sw(0x91, 0); c.strobe()
    c.ctx(pkt=0); c.trace(1)
    c.prog([ins("BCP"), ins("SAD", "0x7F"), ins("LDM"), ins("SAD", "0x75"), ins("STM"), ins("STM"), ins("SAD", "0x3E"),
            ins("LDA", "@PPM"), ins("STA", "@PPM"), ins("STA", "TEMP")])
    c.idle(12); c.trace(0); c.dump(); cases.append(c)
    c = Case("timing", "T4 error halt: nothing after the violator executes"); c.want_err = "EW3"
    c.ctx(pkt=0, sn=0x44); c.trace(1)
    c.prog([ins("LDA", "#12"), ins("SAD", "0x0FF"), ins("STM"), ins("LDA", "#99"), ins("STA", "TEMP"), ins("WLV")])
    c.idle(2); c.ack(); c.idle(1); c.trace(0); c.dump(); cases.append(c)
    c = Case("timing", "T5 strobe in the clock BCP executes")
    for b in range(8):
        c.store[b * 16:b * 16 + 16] = SS.rand_block(rng, 128)
        c.inbox[b] = SS.rand_block(rng, 128)
        c.sw(0x88 + b, 0x0FFF | (1 << 30))
    c.strobe(); c.ctx(pkt=0); c.trace(1); c.ins(ins("BCP")); c.strobe(); c.idle(10); c.trace(0); c.dump(); cases.append(c)
    return cases


# ---- late: what SD-22 step 2 changed (Formation RH006) ----------------------------
def gen_late(rng):
    """Directed; draws nothing from rng, so the groups before it keep their cases."""
    cases = []
    big = 0x40000000                                           # its square leaves 32 bits: E8
    for mn, behind in (("MUL", "STA TEMP"), ("MAC", "STM")):
        c = Case("late", f"L1 {mn} @PPM overflows; {behind} right behind it is not executed"); c.want_err = "E8"
        c.store[0x10] = big; c.store[0x11] = big; c.store[0x12] = 5
        c.regs["temp"] = big if mn == "MAC" else 7
        c.ctx(pkt=0, sn=0x2A1)
        c.prog([ins("SAD", "0x10"), ins("LDA", "@PPM"), ins("SAD", "0x11"), ins(mn, "@PPM"),
                ins(*behind.split()), ins("SAD", "0x12"), ins("LDA", "@PPM")])
        c.idle(2); c.ack(); c.idle(1); c.dump(); cases.append(c)
    c = Case("late", "L2 a prefetch's EW2 in a MUL's X clock (the MUL fits): the MUL lands, then EW2")
    c.want_err = "EW2"
    c.store[0x10] = 3; c.store[0x11] = 5; c.store[0x20] = 16      # block 2: N = 16 < N_MIN
    c.ctx(pkt=0, sn=0x2A2)
    c.prog([ins("SAD", "0x10"), ins("LDA", "@PPM"), ins("SAD", "0x11"), ins("MUL", "@PPM")])
    c.prefetch(2); c.ins(ins("STA", "TEMP")); c.ins(ins("SAD", "0x05")); c.idle(2); c.ack(); c.idle(1); c.dump()
    cases.append(c)
    c = Case("late", "L3 a prefetch's EW2 in the X clock of an overflowing MUL: E8 first, as the model")
    c.want_err = "E8"
    c.store[0x10] = big; c.store[0x11] = big; c.store[0x20] = 16
    c.ctx(pkt=0, sn=0x2A3)
    c.prog([ins("SAD", "0x10"), ins("LDA", "@PPM"), ins("SAD", "0x11"), ins("MUL", "@PPM")])
    c.prefetch(2); c.ins(ins("STA", "TEMP")); c.idle(2); c.ack(); c.idle(1); c.dump(); cases.append(c)
    for b, slot in ((3, 5), (6, 14), (1, 0)):
        c = Case("late", f"L4 BCP, then at once a read of slot {slot} of block {b} it made pending")
        for k in range(8):
            c.store[k * 16:k * 16 + 16] = [64] + [0x1000 * k + i for i in range(1, 16)]
            c.inbox[k] = [96] + [0x7000 * (k + 1) + i for i in range(1, 16)]
            c.sw(0x80 + k, 0x4321 + k)                             # RTOUT
        c.sw(0x88 + b, 0x1FFFF | (1 << 30)); c.sw(0x91, 0); c.strobe()
        c.ctx(pkt=0, sn=0x2A4)
        c.prog([ins("SAD", f"0x{b * 16 + slot:03X}"), ins("BCP"), ins("LDA", "@PPM"), ins("STA", "TEMP"),
                ins("LDM"), ins("ADD", "@PPM")])                     # Temp keeps what the read right after BCP saw
        c.idle(2); c.dump(); cases.append(c)
    # L5: a strobe in BCP's issue clock; its take-set, not the one before it, decides EW5
    # (inbox N 1,100 for every block, store N 50; the sweep word lists blocks 0 and 1)
    for name, before, at, want in (
            ("it takes blocks 0, 1 and the sweep word (2 x 1,100 > NMAX): EW5", False, True, "EW5"),
            ("it takes nothing; the take before it (0, 1, the sweep word) would raise EW5", True, False, None)):
        c = Case("late", f"L5 strobe in the clock BCP is issued: {name}"); c.want_err = want
        for k in range(8):
            c.store[k * 16] = 50; c.inbox[k][0] = 1100
        c.sw(0x90, T.make_sweep([0, 1]))
        for k in (0, 1): c.sw(0x88 + k, 0x00001 | ((1 << 30) if before else 0))
        c.sw(0x91, (1 << 30) if before else 0); c.strobe()      # the take before
        for k in (0, 1): c.sw(0x88 + k, 0x00001 | ((1 << 30) if at else 0))
        c.sw(0x91, (1 << 30) if at else 0)
        c.ctx(pkt=0, sn=0x2A5); c.ins(ins("LDA", "#1")); c.ins_strobe(ins("BCP")); c.ins(ins("LDA", "#2"))
        c.idle(16); c.dump(); cases.append(c)
    return cases


# ---- random contract sequences ---------------------------------------------------
MN_W = dict(LDA=10, STA=6, ADD=8, SUB=6, MUL=5, MAC=5, SWP=4, SFT=5, SAD=16, LDM=12, STM=9, WLV=2, WJV=2, WSH=3, STP=4, BCP=2)
SRC_W = [("#", 4), ("@PPM", 7), ("TEMP", 3), ("K", 1), ("I", 1), ("SN", 1), ("SSS", 1)]
REGION_W = [((0x000, 0x07F), 38), ((0x080, 0x0FF), 10), ((0x100, 0x10F), 26), ((0x110, 0x117), 6),
            ((0x118, 0x119), 3), ((0x11A, 0x11A), 3), ((0x11B, 0x1FF), 2)]


def wchoice(rng, pairs):
    tot = sum(w for _, w in pairs); r = rng.random() * tot
    for v, w in pairs:
        r -= w
        if r < 0: return v
    return pairs[-1][0]


def rand_imm(rng):
    bits = rng.choice([0, 1, 3, 5, 8, 12, 15, 16])
    v = rng.randrange(1 << bits) if bits else 0
    return max(-32768, min(32767, -v if rng.random() < 0.5 else v))


def rand_instr(rng, pkt, focus):
    mnw = dict(MN_W)
    if pkt: mnw["BCP"] = 0.3
    if focus: mnw.update(SAD=30, LDM=18, STM=14)
    mn = wchoice(rng, list(mnw.items()))
    op = None
    if mn in ("LDA", "ADD", "SUB", "MUL", "MAC", "STP"):
        s = wchoice(rng, SRC_W)
        op = f"#{rand_imm(rng)}" if s == "#" else s
    elif mn == "STA":
        op = rng.choice(["TEMP", "@PPM"])
    elif mn == "SFT":
        op = str(rng.choice([rng.randrange(-4, 5), rng.randrange(-33, 34), rng.randrange(-32768, 32768)]))
    elif mn == "SAD":
        if focus and rng.random() < 0.7:
            b = rng.choice(focus); a = (0x100 if (pkt and rng.random() < 0.5) else b * 16) + rng.randrange(16)
        else:
            lo, hi = wchoice(rng, REGION_W); a = rng.randrange(lo, hi + 1)
        op = hex(a)
    return ins(mn, op)


P_ERR = 0.03


def gen_random(rng, n):
    cases = []
    for c in range(n):
        case = Case("random", f"rand-{c}")
        for a in range(128): case.store[a] = rand_val(rng)
        for b in range(8):
            if rng.random() < 0.8: case.store[b * 16] = rng.randrange(T.N_MIN, 257)
        if rng.random() < 0.7:
            for b in range(8): case.inbox[b] = [rand_val(rng) for _ in range(16)]
            for b in range(8):
                if rng.random() < 0.8: case.inbox[b][0] = rng.randrange(T.N_MIN, 257)
        Ns = [case.store[b * 16] for b in range(8)]
        case.regs.update(accm=rand_val(rng), temp=abs(rand_val(rng)) if rng.random() < 0.7 else rand_val(rng),
                         adrs=rng.randrange(0x200), shv=rng.randrange(32),
                         sweep_a=rand_sweep(rng, lambda b: Ns[b]) if rng.random() < 0.8 else 0)
        case.regs["temp"] = T.s32(case.regs["temp"])
        m = case.start_model()
        total = rng.randrange(1, 61)
        nseg = rng.choice([1, 1, 2, 3])
        left = total
        stop = False
        focus, focus_n = [], 0
        for seg in range(nseg):
            if stop: break
            pkt = rng.random() < 0.4
            if not pkt and rng.random() < 0.6:                # a GO in front of an HK segment
                case.wait()                                   # the switch touches RTOUT only after a copy landed
                for b in range(8):
                    if rng.random() < 0.5:
                        case.sw(0x88 + b, rng.choice(PRESET_MASKS + [rng.randrange(1 << 17)]) | ((rng.random() < 0.7) << 30))
                    if rng.random() < 0.3: case.sw(0x80 + b, rng.randrange(1 << 16))
                    if rng.random() < 0.1: case.sw(b * 16 + rng.randrange(16), rand_val(rng))
                if rng.random() < 0.6:
                    kind = rng.choice(["valid"] * 6 + ["invalid_P", "dup", "any"])
                    case.sw(0x90, rand_sweep(rng, lambda b: m.mc.store[b * 16], kind))
                    case.sw(0x91, (rng.random() < 0.7) << 30)
                case.strobe()
            t = taps(rng); cur, q = rng.randrange(8), rng.randrange(8)
            case.ctx(pkt=int(pkt), cur=cur, q=q, **t)
            seg_len = left if seg == nseg - 1 else rng.randrange(0, left + 1)
            left -= seg_len
            for k in range(seg_len):
                if rng.random() < 0.25:
                    t = taps(rng); case.ctx(pkt=int(pkt), cur=cur, q=q, **t)
                if rng.random() < 0.12: case.idle(rng.randrange(1, 5))
                if not pkt and rng.random() < 0.015: case.strobe()          # a strobe between two issues
                for attempt in range(8):
                    item = rand_instr(rng, pkt, focus if focus_n > 0 else None)
                    trial = m.clone()
                    e = trial.issue(item)
                    if e is None or rng.random() < P_ERR: break
                copied_before = set(m.mc.copied)
                e = case.ins(item)
                focus_n -= 1
                if item["mn"] == "BCP" and e is None:
                    new = sorted(m.mc.copied - copied_before)
                    if new: focus, focus_n = new, rng.randrange(3, 9)
                if e is not None:
                    for _ in range(rng.randrange(0, 4)): case.ins(rand_instr(rng, pkt, None))   # must not execute
                    stop = True; break
        if rng.random() < 0.1 and m.halted: case.ack()
        case.gen = None
        case.dump()
        cases.append(case)
    return cases


# ============================================================================
#  Stimulus, simulation, results
# ============================================================================
def emit(cases, first_id):
    shadow = [[None] * 16 for _ in range(8)]
    out = []
    for n, case in enumerate(cases):
        cid = first_id + n
        case.cid = cid
        out.append(f"C {cid:x}")
        out.append("R")
        r = case.regs
        out.append(f"A {u32(r['accm']):x} {u32(r['temp']):x} {r['adrs']:x} {r['shv']:x} {r['sweep_a']:x}")
        for a in range(128): out.append(f"B {a:x} {u32(case.store[a]):x}")
        for b in range(8):
            for i in range(16):
                if i in (13, 14): continue
                v = u32(case.inbox[b][i])
                if shadow[b][i] != v:
                    out.append(f"X {b * 16 + i:x} {v:x}"); shadow[b][i] = v
        out.append("Q 0 0 0 0 0 0 0")
        for st in case.steps:
            k = st[0]
            if k == "X":
                out.append(f"X {st[1]:x} {u32(st[2]):x}")
                if st[1] < 0x80 and (st[1] & 15) not in (13, 14): shadow[st[1] >> 4][st[1] & 15] = u32(st[2])
            elif k == "Q": out.append("Q " + " ".join(f"{v:x}" for v in st[1:]))
            elif k in ("I", "J"): out.append(f"{k} {st[1]['word']:08x}")
            elif k in ("N", "P", "V"): out.append(f"{k} {st[1]:x}")
            else: out.append(k)
        out.append("E")
    return "\n".join(out) + "\n"


D_FIELDS = ["flag", "code", "idx", "sn", "accm", "temp", "adrs", "shv", "sweep_a", "copied", "take", "swcop",
            "taken", "loopval", "jumpval", "ireq", "busy"]
D_HEX = {"sn", "accm", "temp", "adrs", "shv", "sweep_a", "copied", "take", "loopval", "jumpval"}


def parse_results(path):
    res, trace = {}, {}
    lines = open(path).read().split("\n")
    i = 0
    while i < len(lines):
        f = lines[i].split()
        if not f: i += 1; continue
        if f[0] == "D":
            cid = int(f[1], 16)
            rec = {k: int(v, 16) if k in D_HEX else int(v) for k, v in zip(D_FIELDS, f[2:])}
            m = lines[i + 1].split()
            assert m[0] == "M", lines[i + 1][:40]
            rec["store"] = [int(x, 16) for x in m[1:]]
            res.setdefault(cid, []).append(("D", rec)); i += 2; continue
        if f[0] == "F":
            res.setdefault(int(f[1], 16), []).append(("F", tuple(int(x, 16) for x in f[3:])))
        elif f[0] == "T":
            trace.setdefault(int(f[1], 16), []).append(tuple(int(x) for x in f[2:]))
        i += 1
    return res, trace


def build(outdir, rtl=L2):
    exe = os.path.join(outdir, "wpms_formation_tb.vvp")
    cmd = ["iverilog", "-g2012", "-I", rtl, "-o", exe, os.path.join(rtl, "wpms_formation.v"), os.path.join(L2, "wpms_formation_tb.v")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    notes = [l for l in log.splitlines() if l.strip() and "sensitive to all" not in l]
    if r.returncode != 0 or notes:
        print("\n".join(log.splitlines()[:40])); sys.exit(2)
    return exe, log


def run_chunk(exe, outdir, k, text):
    stim = os.path.join(outdir, f"stim_{k}.txt"); out = os.path.join(outdir, f"results_{k}.txt")
    open(stim, "w").write(text)
    r = subprocess.run(["vvp", "-n", exe, f"+stim={stim}", f"+out={out}"], capture_output=True, text=True)
    return out, r.stdout + r.stderr


def compare(case, hw, exp):
    probs = []
    if len(hw) != len(exp):
        return [f"{len(hw)} result records, {len(exp)} expected"]
    for (hk, h), (ek, e) in zip(hw, exp):
        if hk != ek: probs.append(f"record kind {hk} vs {ek}"); continue
        if hk == "F":
            if h != e: probs.append("prefetch port: got " + " ".join(f"{v:08X}" for v in h) + " want " + " ".join(f"{v:08X}" for v in e))
            continue
        for f in D_FIELDS:
            if h[f] != e[f]: probs.append(f"{f}: got {h[f]:#x} want {e[f]:#x}")
        bad = [a for a in range(128) if h["store"][a] != e["store"][a]]
        for a in bad[:6]:
            probs.append(f"store[{a:#04x}] (block {a >> 4} slot {a & 15:X}): got {h['store'][a]:08X} want {e['store'][a]:08X}")
        if len(bad) > 6: probs.append(f"... {len(bad)} store words differ")
    return probs


def clock_table(case, tr):
    """From a traced case: per issued instruction the issue and X clocks; for BCP the copy."""
    rows = []
    issue = {t[2]: t[0] for t in tr if t[1] == 1 and t[2] >= 0}         # idx -> clock presented
    xcl = {t[4]: (t[0], t[5], t[6]) for t in tr if t[3] == 1 and t[4] >= 0}   # idx -> (clock, commit, err)
    items = [st[1] for st in case.steps if st[0] == "I"]
    for idx, it in enumerate(items):
        if idx not in issue: continue
        xc = xcl.get(idx)
        rows.append(dict(idx=idx, mn=f"{it['mn']} {it['op'] or ''}".strip(), issue=issue[idx],
                         x=xc[0] if xc else None, commit=xc[1] if xc else None, err=xc[2] if xc else None))
    copies = [(t[0], t[9]) for t in tr if t[8] == 1]                    # (clock, block) landing at that clock's edge
    taken_rise = next((t[0] for k, t in enumerate(tr) if t[10] == 1 and (k == 0 or tr[k - 1][10] == 0)), None)
    busy = [t[0] for t in tr if t[7] == 1]
    return rows, copies, taken_rise, busy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--jobs", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    ap.add_argument("--out", default=os.path.join(HW, "l2", "build", "cosim"))
    ap.add_argument("--only", default="")
    ap.add_argument("--report", default="", help="write the summary (text) here as well")
    ap.add_argument("--rtl", default=L2, help="directory holding the wpms_formation.v under test (mutant runs)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    rng = random.Random(a.seed)
    groups = [("packet", lambda: gen_packet(rng, 60)), ("hk", lambda: gen_hk(rng, 300)), ("fwd", lambda: gen_fwd(rng, 120)),
              ("exp", lambda: gen_exp(rng)), ("neg", lambda: gen_neg(rng)), ("e4", lambda: gen_e4(rng)),
              ("prefetch", lambda: gen_prefetch(rng)), ("timing", lambda: gen_timing(rng)),
              ("random", lambda: gen_random(rng, a.random)), ("late", lambda: gen_late(rng))]
    only = set(a.only.split(",")) if a.only else None
    cases = []
    for g, fn in groups:
        cs = fn()                                            # generate every group: the seed stream stays fixed
        if only is None or g in only: cases += cs
    t_gen = time.time() - t0
    exe, clog = build(a.out, a.rtl)
    J = max(1, min(a.jobs, len(cases)))
    chunks = [cases[k::J] for k in range(J)]
    texts, first = [], 0
    for ch in chunks:
        texts.append(emit(ch, first)); first += len(ch)
    t1 = time.time()
    with ThreadPoolExecutor(J) as ex:
        runs = list(ex.map(lambda kt: run_chunk(exe, a.out, kt[0], kt[1]), enumerate(texts)))
    t_sim = time.time() - t1
    res, trace = {}, {}
    simlog = []
    for out, log in runs:
        r, t = parse_results(out); res.update(r); trace.update(t); simlog.append(log)
    warnings = [l for log in simlog for l in log.splitlines() if "WARNING" in l or "INVARIANT" in l or "ERROR" in l]
    played = sum(int(l.split()[1]) for log in simlog for l in log.splitlines() if l.startswith("wpms_formation_tb:") and "cases played" in l)

    stats, fails, err_hist, n_ins = {}, [], {}, {}
    exp_err = {}
    timing = []
    for case in cases:
        exp, mfinal = expect(case)
        hw = res.get(case.cid, [])
        probs = compare(case, hw, exp)
        if case.want_err is not None or case.group in ("neg", "e4", "prefetch", "late"):
            got = ERR_NAME.get(exp[-1][1]["code"]) if exp and exp[-1][0] == "D" else None
            if got != case.want_err:
                probs.append(f"the model's first error is {got}, the case was written to provoke {case.want_err}")
        if case.post and not probs:
            probs += case.post(case, hw, exp)
        if case.group == "exp" and not probs:
            got = T.s32(hw[-1][1]["store"][11]) / (1 << EXP_Q)
            exp_err[case.x] = abs(got - math.exp(case.x))
        if case.group == "timing":
            timing.append((case, clock_table(case, trace.get(case.cid, []))))
        s = stats.setdefault(case.group, dict(cases=0, passed=0, issued=0, errors=0))
        s["cases"] += 1; s["passed"] += not probs
        s["issued"] += sum(1 for st in case.steps if st[0] == "I")
        d = exp[-1][1] if exp and exp[-1][0] == "D" else None
        if d and d["flag"]:
            s["errors"] += 1
            nm = ERR_NAME[d["code"]]; err_hist.setdefault(case.group, {}).setdefault(nm, 0)
            err_hist[case.group][nm] += 1
        for st in case.steps:
            if st[0] == "I" and not st[1].get("raw"):
                n_ins[st[1]["mn"]] = n_ins.get(st[1]["mn"], 0) + 1
        if probs: fails.append((case, probs))

    L = []
    p = L.append
    p(f"cosim_l2: hw/l2/wpms_formation.v vs pfasm_tools_w.Machine — evidence class RTL-SIM (Icarus Verilog)")
    p(f"  seed {a.seed}; {len(cases)} cases in {J} simulator runs ({played} played); generation {t_gen:.1f} s, simulation {t_sim:.1f} s")
    p(f"  {'group':9s} {'cases':>6s} {'pass':>6s} {'instr':>7s} {'err-cases':>9s}  first-error codes (expected = observed)")
    tot = dict(cases=0, passed=0, issued=0, errors=0)
    for g, _ in groups:
        if g not in stats: continue
        s = stats[g]
        for k in tot: tot[k] += s[k]
        eh = ", ".join(f"{k} {v}" for k, v in sorted(err_hist.get(g, {}).items()))
        p(f"  {g:9s} {s['cases']:6d} {s['passed']:6d} {s['issued']:7d} {s['errors']:9d}  {eh}")
    p(f"  {'total':9s} {tot['cases']:6d} {tot['passed']:6d} {tot['issued']:7d} {tot['errors']:9d}")
    p("  instructions issued by mnemonic: " + ", ".join(f"{k} {v}" for k, v in sorted(n_ins.items())))
    if exp_err:
        worst = max(exp_err.items(), key=lambda kv: kv[1])
        p(f"  exp_maclaurin_w on the hardware: max |err| over 21 x = {worst[1]:.2e} at x={worst[0]:+.2f} (model: 7.39e-09)")
    p(f"  simulator warnings (switch/prefetch protocol) and invariant violations: {len(warnings)}")
    for w in warnings[:5]: p("    " + w)
    for case, (rows, copies, taken, busy) in timing:
        p(f"  [trace] {case.name}")
        for r in rows:
            st = "commit" if r["commit"] else (f"ERROR {ERR_NAME.get(r['err'], r['err'])}" if r["err"] else "not executed (halted)")
            p(f"      #{r['idx']:<2d} {r['mn']:14s} issue clock {r['issue']:6d}   X clock {r['x'] if r['x'] is not None else '-':>6}   {st}")
        if copies: p(f"      copy lands: " + ", ".join(f"block {b} @ {c}" for c, b in copies))
        if taken is not None: p(f"      inbox_taken first seen high in clock {taken}")
        if busy: p(f"      bcp_busy high in clocks {busy[0]}..{busy[-1]} ({len(busy)} clocks)")
    for case, probs in fails[:25]:
        p(f"  FAIL {case.group}/{case.name}: " + "; ".join(probs[:8]))
    if len(fails) > 25: p(f"  ... {len(fails)} failing cases in all")
    for case in cases:
        if case.group == "neg":
            d = expect(case)[0][-1][1]
            p(f"  [{'PASS' if not any(c is case for c, _ in fails) else 'FAIL'}] {case.name:52s} -> "
              f"{ERR_NAME.get(d['code'], 'none') if d['flag'] else 'no error'}"
              f"{' at instruction ' + str(d['idx']) if d['flag'] and d['idx'] >= 0 else (' at prefetch' if d['flag'] else '')}"
              f"{'; ' + case.note if case.note else ''}")
    ok = not fails and played == len(cases) and not warnings
    p(f"cosim_l2: {'PASS' if ok else 'FAIL'} — {tot['passed']}/{tot['cases']} cases bit-identical to the model")
    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    if a.report: open(a.report, "w").write(text)
    open(os.path.join(a.out, "compile.log"), "w").write(clog)
    open(os.path.join(a.out, "vvp.log"), "w").write("\n".join(simlog))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
