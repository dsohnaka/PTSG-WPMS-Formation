#!/usr/bin/env python3
# ============================================================================
# switch_model.py — the input switch of customer Ch.5 §5.4-§5.8 as Phase 5
# builds it, at transaction level: written from the chapter's text and the
# choices of reports/phase5_switch.md §4.4, not from the RTL (hw/switch/). The
# cosimulation (cosim_switch.py) feeds it the transactions the RTL executed,
# the strobes and the apply steps, each with its clock, and compares every
# answer, every write the switch presents to the Formation's inbox port, and —
# through sweep_sim.Reference and l1_model — every bundle and every sample.
#
# CLOCK RULES the model keeps (the switch's contract, wpms_switch.v header):
#   * a transaction executes (EXEC) in one clock and is answered in the next;
#     the inbox write it makes is presented in the clock after EXEC;
#   * the Formation's armed flags change at the end of the clock a write is
#     presented in, and a strobe takes them including that clock's write (Map
#     v0.3 §7; Formation RH004): a GO is taken by the first strobe after its
#     EXEC clock;
#   * within one clock: EXEC, then the writes presented in that clock, then
#     the strobe (whose assignments win).
#
# Evidence class of what it checks: RTL-SIM (against Icarus). License: MIT.
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# ============================================================================
ID, VERSION = 0x5750_4D53, 0x0001_0000
MG_RATE_DEFAULT = 13_933
M32 = (1 << 32) - 1
# words the switch reads through from taps (compared with what the bench saw)
LIVE = {0x012, 0x014, 0x016, 0x018, 0x019, 0x041, 0x042, 0x043, 0x292, 0x298, 0x299}


def s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


class Switch:
    def __init__(self, nmax, n_min=32):
        self.nmax, self.n_min = nmax, n_min
        self.shadow = [0] * 128                    # INBOX as staged: memory, survives a design reset
        self.problems = []
        self.ibx = []                              # predicted inbox writes: (cycle presented, addr, data, seq)
        self.pend = {}                             # cycle presented -> [(addr, data, seq)]
        self.takes = []                            # (strobe index, {item: snapshot})
        self.rom_starts = []                       # EXEC cycles of TEST_ORIGIN writes (port 0)
        self.clears = []                           # (cycle, what, bits) of W-clear pulses
        self.swmax_clr = []
        self.landed = False                        # inbox_taken rose since the last strobe
        self.reset()

    # ---- reset: registers only (Ch.5 §5.8, CR5-R1) --------------------------------------------
    def reset(self):
        self.arm, self.arm_p3, self.fired = set(), set(), set()
        self.fa, self.ft, self.ft_open = set(), set(), False
        self.fa_seq = self.ft_seq = self.n_take = 0
        self.cmask, self.rtout, self.sw_st = [0] * 8, [0] * 8, 0
        self.n_st, self.nv_st = [0] * 8, [False] * 8
        self.n_fu, self.nv_fu, self.sw_fu = [0] * 8, [False] * 8, 0
        self.sample_n = self.sample_hi = 0
        self.owner0 = self.insp_mod = self.insp_pos = 0
        self.go_seq = self.applied_seq = self.applied_sample = 0
        self.reject = {0: 0, 3: 0}
        self.mg_target, self.mg_rate, self.g_ctrl, self.mute = 0, MG_RATE_DEFAULT, 0, 0
        self.fired_snap = {}                       # item -> what it carries (snapshot at fire)
        self.pend = {}
        self.landed = False

    def frozen(self):
        return self.arm | self.fired

    def in_range(self, v):
        return self.n_min <= s32(v) <= self.nmax

    # ---- the GO check (PR-1, PR-2, Ch.5 §5.4.4) -------------------------------------------------
    def check(self, items, now_b=None, now_mask=None):
        n, nv = list(self.n_fu), list(self.nv_fu)
        for b in range(8):
            if b in items:
                m = now_mask if b == now_b else self.cmask[b]
                if m & 1:
                    n[b], nv[b] = self.n_st[b], self.nv_st[b]
        sw = self.sw_st if 8 in items else self.sw_fu
        P = sw & 15
        bad = P > 8
        seen, total = set(), 0
        for q in range(min(P, 8)):
            blk = (sw >> (4 + 3 * q)) & 7
            if blk in seen or not nv[blk]:
                bad = True
            seen.add(blk)
            total += n[blk]
        if total > self.nmax:
            bad = True
        return bad, n, nv, sw

    def fire(self, cyc, items, n, nv, sw):
        for it in items:
            if it == 8:
                self.fired_snap[8] = ("sweep", self.sw_st)
            else:
                self.fired_snap[it] = ("block", self.cmask[it], list(self.shadow[16 * it:16 * it + 16]),
                                       self.rtout[it])
        self.fired |= items
        self.arm -= items
        self.n_fu, self.nv_fu, self.sw_fu = n, nv, sw
        self.go_seq += 1
        return self.go_seq

    def present(self, cyc, addr, data, seq=None):
        self.ibx.append((cyc + 1, addr, data & M32, seq))
        self.pend.setdefault(cyc + 1, []).append((addr, data & M32, seq))

    @staticmethod
    def vec(items):
        return sum(1 << i for i in items)

    # ---- one transaction (EXEC clock cyc); returns (expected rdata or None = a tap, expected rej)
    def exec(self, cyc, port, we, a, d):
        d &= M32
        fz = self.frozen()
        p3 = port == 3
        if not we:
            return self.read(a, port), 0
        rej = 0
        glob, mod, off = (a >> 8) == 0, (a >> 8) == 2, a & 0xFF
        if glob:
            if off == 0x08:
                if d & 3:
                    items = set(self.arm) if d & 2 else {i for i in self.arm if (i in self.arm_p3) == p3}
                    bad, n, nv, sw = self.check(items)
                    if bad:
                        rej = 1
                        self.arm -= items
                    else:
                        seq = self.fire(cyc, items, n, nv, sw)
                        self.present(cyc, 0x9F, self.vec(self.fired), seq)
            elif off == 0x10: self.mg_target = s32(d)
            elif off == 0x11: self.mg_rate = s32(d)
            elif off == 0x13: self.g_ctrl = d & 31
            elif off == 0x15: self.mute = d & 1
            elif off == 0x16: self.clears.append((cyc, "clip", d & 3))
            elif off == 0x19: self.clears.append((cyc, "minmax", 1))
            elif off == 0x1C:
                if p3:
                    rej = 1
                elif d & 1:
                    self.rom_starts.append(cyc)            # ignored by the RTL if the ROM is playing
            elif off == 0x20: self.owner0 = d & 0x3FFFF
            elif off == 0x30: self.reject[0] &= ~d & M32
            elif off in (0x31, 0x32): pass
            elif off == 0x33: self.reject[3] &= ~d & M32
            elif off == 0x40: self.insp_mod, self.insp_pos = d & 15, (d >> 4) & 0xFFF
            else: rej = 1
        elif mod:
            if off < 0x80:
                b, i = off >> 4, off & 15
                if i in (13, 14) or b in fz:
                    rej = 1
                else:
                    self.shadow[off] = d
                    self.present(cyc, off, d)
                    if i == 0:
                        self.n_st[b], self.nv_st[b] = d & 0xFFF, self.in_range(d)
            elif off >> 3 == 0x10:                                   # RTOUT
                b = off & 7
                if b in fz: rej = 1
                else:
                    self.rtout[b] = d & 0xFFFF
                    self.present(cyc, 0x80 | b, d & 0xFFFF)
            elif off >> 3 == 0x11:                                   # COMMIT
                b = off & 7
                if b in fz:
                    rej = 1
                elif d >> 31:                                        # go-now
                    bad, n, nv, sw = self.check({b}, now_b=b, now_mask=d & 0x1FFFF)
                    if bad:
                        rej = 1
                    else:
                        self.cmask[b] = d & 0x1FFFF
                        seq = self.fire(cyc, {b}, n, nv, sw)
                        self.present(cyc, 0x88 | b, (1 << 30) | (d & 0x1FFFF), seq)
                else:
                    self.cmask[b] = d & 0x1FFFF
                    self.present(cyc, 0x88 | b, d & 0x1FFFF)
                    if d >> 30 & 1:
                        self.arm.add(b)
                        (self.arm_p3.add if p3 else self.arm_p3.discard)(b)
            elif off == 0x90:
                if 8 in fz: rej = 1
                else:
                    self.sw_st = d & 0xFFFFFFF
                    self.present(cyc, 0x90, d & 0xFFFFFFF)
            elif off == 0x91:
                if 8 in fz:
                    rej = 1
                elif d >> 31:
                    bad, n, nv, sw = self.check({8})
                    if bad: rej = 1
                    else:
                        seq = self.fire(cyc, {8}, n, nv, sw)
                        self.present(cyc, 0x91, 1 << 30, seq)
                elif d >> 30 & 1:
                    self.arm.add(8)
                    (self.arm_p3.add if p3 else self.arm_p3.discard)(8)
            elif off == 0x99:
                self.swmax_clr.append(cyc)
            else:
                rej = 1
        else:
            rej = 1
        if rej:
            self.reject[3 if p3 else 0] = (self.reject[3 if p3 else 0] + 1) & M32
        return None, rej

    def read(self, a, port):
        glob, mod, off = (a >> 8) == 0, (a >> 8) == 2, a & 0xFF
        if a in LIVE:
            return None
        if glob:
            if off == 0x0C:
                self.sample_hi = (self.sample_n >> 32) & M32
            return {0x00: ID, 0x01: VERSION, 0x02: (self.nmax & 0xFFFF) << 8 | 8 << 4 | 1,
                    0x03: 3 if port == 3 else 0, 0x09: self.go_seq, 0x0A: self.applied_seq,
                    0x0B: self.applied_sample, 0x0C: self.sample_n & M32, 0x0D: self.sample_hi,
                    0x10: self.mg_target & M32, 0x11: self.mg_rate & M32, 0x13: self.g_ctrl,
                    0x15: self.mute, 0x20: self.owner0, 0x30: self.reject[0], 0x33: self.reject[3],
                    0x40: self.insp_pos << 4 | self.insp_mod}.get(off, 0)
        if mod:
            fz = self.frozen()
            if off < 0x80:
                return 0 if (off & 15) in (13, 14) else self.shadow[off]
            if off >> 3 == 0x10: return self.rtout[off & 7]
            if off >> 3 == 0x11: return (1 << 30 if (off & 7) in fz else 0) | self.cmask[off & 7]
            if off == 0x90: return self.sw_st
            if off == 0x91: return 1 << 30 if 8 in fz else 0
        return 0

    # ---- the strobe and the apply step ------------------------------------------------------------
    def taken(self, cyc):
        """inbox_taken rose: the Formation has copied the take (CR5-I3)."""
        self.landed = True

    def strobe(self, cyc, sidx):
        if self.ft_open and self.landed and (self.fa & self.ft):
            self.problems.append(f"strobe at {cyc}: items already copied are armed again ({sorted(self.fa & self.ft)})")
        if self.ft_open:
            self.problems.append(f"strobe at {cyc}: the take of the previous strobe was never applied")
        self.ft, self.ft_seq, self.ft_open = set(self.fa), self.fa_seq, True
        self.landed = False
        self.n_take = (self.sample_n + 1) & M32
        self.sample_n += 1
        snaps = {}
        for it in self.ft:
            if it in self.fired_snap:
                snaps[it] = self.fired_snap[it]
            else:
                self.problems.append(f"strobe at {cyc}: item {it} taken but never fired")
        self.takes.append((sidx, snaps))

    def apply(self, cyc):
        if not self.ft_open:
            return
        self.ft_open = False
        self.fired -= self.ft
        if self.ft:
            self.present(cyc, 0x9F, self.vec(self.fired))
        if self.ft_seq != self.applied_seq:
            self.applied_seq = self.ft_seq
            self.applied_sample = (self.n_take + 1) & M32

    def presented(self, cyc):
        """The writes presented in clock cyc change the Formation's flags (and the mirror) at its end."""
        for addr, data, seq in self.pend.pop(cyc, []):
            if addr >> 3 == 0x11:
                (self.fa.add if data >> 30 & 1 else self.fa.discard)(addr & 7)
            elif addr == 0x91:
                (self.fa.add if data >> 30 & 1 else self.fa.discard)(8)
            elif addr == 0x9F:
                self.fa = {i for i in range(9) if data >> i & 1}
            if seq is not None:
                self.fa_seq = seq


def go_dict(snaps):
    """sweep_sim.Reference's GO for one take: {'blocks': {b: (mask, vals, rt)}, 'sweep': w or None}."""
    blocks, sweep = {}, None
    for it, sn in snaps.items():
        if sn[0] == "sweep":
            sweep = sn[1]
        else:
            _, mask, vals, rt = sn
            blocks[it] = (mask, [s32(v) for v in vals], rt)
    return dict(blocks=blocks, sweep=sweep) if (blocks or sweep is not None) else None
