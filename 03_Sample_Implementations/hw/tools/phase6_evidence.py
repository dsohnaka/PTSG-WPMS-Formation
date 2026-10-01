#!/usr/bin/env python3
# ============================================================================
# phase6_evidence.py — the Layer 4 evidence of SILICON_BRIEF Phase 6 from a
# capture of the board top's tap bus (hw/de10_nano/DE10_Nano_wpms_top.v:
# tap_ctl, tap_dat): a SignalTap export (File > Export > VCD; bits one by one)
# or the board-level bench's VCD (vectors). The same code reads both, so the
# numbers RTL-SIM predicts are computed exactly as the silicon ones will be.
#
#   python3 phase6_evidence.py CAPTURE.vcd[.gz] [--budget 50|100] [--log HOST.log]
#                              [--score wpms_r1d.score] [--json OUT.json] [--bench RESULTS]
#
# Measured, per sweep of the capture (one tap sample = one clk_sys clock; the
# taps are one clock late, all alike, so every difference is exact):
#   g        clocks between the last bin of a packet and the first of the next
#   T_wake   strobe -> first packet_start
#   window   the packet's Stay Set -> the clock the Core reaches its Stay word
#            (the window's 25 words, ProgEnd, the queued Jump); floor = window + 2
#   BCP      the housekeeping window's BCP word -> inbox_taken rising
#   sweep    strobe -> seq_idle rising (asleep, the next bundle staged), with
#            the sweep's sum of bins (full load: sum = NMAX)
#   errors   error_flag (code), packets and bins after it, every bank written
#            after it (L1 silent: all zero), the Core's halt
#   bundles  every bundle at packet_start against the model (with --log)
#   PCM      every bank written against the model (up to an error), and the
#            spectrum of the captured PCM beside the model's (with --log)
# A capture taken with the storage qualifier tap_ctl[100] (packet_start |
# bank_we) holds events, not clocks: it is recognized by that bit being set in
# (nearly) every sample, and only the bundles, the PCM and the error code are
# measured from it. The bench's results file can stand in for the PCM of a long
# run (--bench RESULTS: its "B cycle n L R" lines, one per bank written).
# The model: hw/tools/switch_model.py replays the host's writes (and the ROM's
# list after each reset) into takes; sweep_sim.Reference (golden, unchanged)
# plays them; l1_model.py over the customer's oracle makes the samples. Each
# GO lands at the sample the switch reported (APPLIED_SAMPLE, read back by the
# host after the GO); the ROM's GO after a reset lands at sample 2.
# Host log lines understood: the bench's ("W cyc aaa dddddddd rrrrrrrr j",
# "Q cyc aaa rrrrrrrr", "R cyc") and wpms_issp_host.tcl's ("W aaa dddddddd ->
# rrrrrrrr [REFUSED]", "R aaa -> rrrrrrrr", "applied GO g at sweep s"; a line
# "RESET" added by hand where the board was reset).
# Evidence class: whatever the capture is (RTL-SIM for the bench, SILICON for
# SignalTap). License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, gzip, json, math, os, re, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
HW = os.path.normpath(os.path.join(HERE, ".."))
GOLD = os.path.normpath(os.path.join(HW, "..", "tools"))

BUDGETS = {50: dict(nmax=1008, tmin=1041), 100: dict(nmax=2048, tmin=2083)}
ERRN = {4: "E4", 5: "E5", 8: "E8", 18: "EW2", 19: "EW3", 20: "EW4", 21: "EW5", 22: "EW6"}
F = dict(strobe=(0, 1), pstart=(1, 1), bin=(2, 1), taken=(3, 1), err=(4, 1), halt=(5, 1), idle=(6, 1),
         bank=(7, 1), code=(8, 5), k=(13, 12), state=(25, 12), q=(37, 3), sweep=(40, 28), n=(68, 32),
         qual=(100, 1))
QUAL = 1 << 100


def fld(v, name):
    lo, w = F[name]
    return (v >> lo) & ((1 << w) - 1)


# ---------------------------------------------------------------------------------------------------
# VCD: the tap registers, one sample per clk_sys rising edge (or per period without a clock)
# ---------------------------------------------------------------------------------------------------
def read_vcd(path, clock="clk_sys", period_ps=None):
    """(ctl, dat): tap_ctl per sample, tap_dat where packet_start or bank_we. A sample is taken at
    each rising edge of the clock signal when the VCD has one (the bench; a SignalTap export that
    lists its acquisition clock, two time stamps per sample), else one per period of the time
    stamps (period_ps, or the smallest step). Samples taken while a tap bit is still X (the
    export's first time stamp) are dropped."""
    op = gzip.open if path.endswith(".gz") else open
    targets = {}                                  # id -> [(base, lo, width)]
    clock_ids = set()
    with op(path, "rt", errors="replace") as f:
        for line in f:
            if line.startswith("$var"):
                t = line.split()
                width, vid, ref = int(t[2]), t[3], t[4].lstrip("\\")
                rng = t[5] if len(t) > 6 and t[5].startswith("[") else None
                base = re.split(r"[|.]", ref)[-1]
                m = re.match(r"^(.*)\[(\d+)\]$", base)
                lo = 0
                if m:
                    base, lo = m.group(1), int(m.group(2))
                elif rng:
                    mm = re.match(r"\[(\d+):(\d+)\]", rng)
                    if mm:
                        lo = min(int(mm.group(1)), int(mm.group(2)))
                if base in ("tap_ctl", "tap_dat"):
                    targets.setdefault(vid, []).append((base, lo, width))
                if base == clock or base.endswith(clock):
                    clock_ids.add(vid)
            elif line.startswith("$enddefinitions"):
                break
        if not targets:
            raise SystemExit(f"{path}: no tap_ctl / tap_dat in the VCD")
        val = {"tap_ctl": 0, "tap_dat": 0}
        unknown = set()                           # tap ids whose value is X/Z now
        clk, clk_prev, rises = 0, 0, 0
        ctl, dat = [], {}
        times = []
        now = None

        def setbits(vid, bits):
            if vid not in targets:
                return
            if any(ch in "xXzZ" for ch in bits):
                unknown.add(vid)
            else:
                unknown.discard(vid)
            for base, lo, w in targets[vid]:
                b = bits[-w:].rjust(w, "0").replace("x", "0").replace("z", "0").replace("X", "0").replace("Z", "0")
                v = int(b, 2)
                mask = ((1 << w) - 1) << lo
                val[base] = (val[base] & ~mask) | (v << lo)

        def close(t):
            nonlocal clk_prev, rises
            if clock_ids and clk_prev == 0 and clk == 1:
                rises += 1
                if not unknown:
                    c = val["tap_ctl"]
                    if c & 0x82:                                   # packet_start or bank_we: keep the data
                        dat[len(ctl)] = val["tap_dat"]
                    ctl.append(c)
            clk_prev = clk
            if (not clock_ids or rises < 2) and not unknown:
                times.append((t, val["tap_ctl"], val["tap_dat"]))

        for line in f:
            if not line or line[0] in "$\n":
                continue
            ch = line[0]
            if ch == "#":
                t = int(line[1:])
                if now is not None:
                    close(now)
                now = t
            elif ch in "bB":
                bits, vid = line[1:].split()
                setbits(vid, bits)
                if vid in clock_ids:
                    clk = int(bits[-1]) if bits[-1] in "01" else 0
            elif ch in "01xXzZ":
                vid = line[1:].strip()
                setbits(vid, ch)
                if vid in clock_ids:
                    clk = 1 if ch == "1" else 0
        if now is not None:
            close(now)
    if rises < 2:                                                  # no usable clock: one sample per period
        ctl, dat = [], {}
        if len(times) < 2:
            raise SystemExit("too few samples")
        qualified = sum(1 for _, c, _ in times if c & QUAL) >= 0.9 * len(times)
        per = period_ps or min(b[0] - a[0] for a, b in zip(times, times[1:]) if b[0] > a[0])
        for (t, c, d), nxt in zip(times, times[1:] + [None]):
            # a qualified capture stores events: an unchanged value is not a second event
            reps = 1 if (nxt is None or qualified) else max(1, round((nxt[0] - t) / per))
            for _ in range(reps):
                if c & 0x82:
                    dat[len(ctl)] = d
                ctl.append(c)
    return ctl, dat


def write_signaltap_vcd(ctl, dat, path, period_ps=20000, with_clock=True):
    """ctl/dat written in the layout of a SignalTap export (QUARTUS_VCD_EXPORT 1.0: 1 ps, every bit
    its own variable, X at time 0; with_clock: the acquisition clock listed, two time stamps per
    sample). For a dry run of the silicon path on RTL-SIM data; tap_dat is held between the
    samples that carry it."""
    ids = []

    def ident(k):
        s_ = ""
        k += 1
        while k:
            k, r = divmod(k - 1, 94)
            s_ = chr(33 + r) + s_
        return s_

    names = (["clk_sys"] if with_clock else []) + [f"tap_ctl[{i}]" for i in range(100, -1, -1)] + \
            [f"tap_dat[{i}]" for i in range(303, -1, -1)]
    ids = {n: ident(k) for k, n in enumerate(names)}
    L = ["$comment", " written by hw/tools/phase6_evidence.py in the layout of a SignalTap export", "$end",
         "$version", " QUARTUS_VCD_EXPORT 1.0 ", "$end", "$timescale", "  1 ps", "$end",
         "$scope module DE10_Nano_wpms_top $end"]
    L += [f"$var reg 1 {ids[n]} {n} $end" for n in names]
    L += ["$upscope $end", "$enddefinitions $end", "#0", "$dumpvars"] + [f"X{ids[n]}" for n in names] + ["$end"]
    prev = {}
    d_cur = 0
    half = period_ps // 2
    for k, c in enumerate(ctl):
        if k in dat:
            d_cur = dat[k]
        t0 = (2 * k + 1) * half if with_clock else (k + 1) * period_ps
        L.append(f"#{t0}")
        if with_clock:
            L.append(f"1{ids['clk_sys']}")
        for i in range(101):
            v = (c >> i) & 1
            if prev.get(("c", i)) != v:
                L.append(f"{v}{ids[f'tap_ctl[{i}]']}")
                prev[("c", i)] = v
        for i in range(304):
            v = (d_cur >> i) & 1
            if prev.get(("d", i)) != v:
                L.append(f"{v}{ids[f'tap_dat[{i}]']}")
                prev[("d", i)] = v
        if with_clock:
            L.append(f"#{t0 + half}")
            L.append(f"0{ids['clk_sys']}")
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "wt") as f:
        f.write("\n".join(L) + "\n")


def is_qualified(ctl):
    return bool(ctl) and sum(1 for c in ctl if c & QUAL) >= 0.9 * len(ctl)


# ---------------------------------------------------------------------------------------------------
# the score: where the Core's words are (labels, each position's Stay word)
# ---------------------------------------------------------------------------------------------------
def score_map(score_path):
    import score_as as SA
    words, info = SA.assemble(score_path)
    lab = info["labels"]
    stay_of = {}
    by_addr = {a: c for a, w, c in words}
    for name, a in lab.items():
        if name.startswith("POS"):
            for x in range(a + 1, a + 64):
                c = by_addr.get(x, "")
                if re.search(r"\bStay\b", c) and "StaySet" not in c:
                    stay_of[a] = x
                    break
    return lab, stay_of


# ---------------------------------------------------------------------------------------------------
# the measurements
# ---------------------------------------------------------------------------------------------------
def measure_qualified(ctl, dat):
    """A storage-qualified capture: one sample per packet_start or bank_we."""
    res = dict(samples=len(ctl), strobes=None, sweeps=[], errors=[], packets=[], qualified=True,
               strobe_interval=[])
    for i, c in enumerate(ctl):
        if c & 2:
            sw, q = fld(c, "sweep"), fld(c, "q")
            res["packets"].append(dict(start=i, bins=None, k_ok=True, last=None, window=None, q=q, n=fld(c, "n"),
                                       block=(sw >> (4 + 3 * q)) & 7, P=sw & 15))
    res["errors"] = errors_of(ctl, dat, qualified=True)
    return res


def errors_of(ctl, dat, qualified=False):
    """Each rise of error_flag: its code, and what follows it (L1 silent: no packet, no bin, banks zero)."""
    out = []
    for i in range(len(ctl)):
        if (ctl[i] >> 4) & 1 and (i == 0 or not (ctl[i - 1] >> 4) & 1):
            if i == 0 and not qualified:
                continue                                           # flag already up when the capture began
            after_p = sum(1 for x in range(i, len(ctl)) if ctl[x] & 2)
            after_b = None if qualified else sum(1 for x in range(i, len(ctl)) if (ctl[x] >> 2) & 1)
            banks = [x for x in range(i, len(ctl)) if (ctl[x] >> 7) & 1]
            loud = [x for x in banks if (dat.get(x, 0) >> 256) & 0xFFFFFFFFFFFF]
            h = next((x for x in range(i, len(ctl)) if (ctl[x] >> 5) & 1), None)
            out.append(dict(at=i, n=fld(ctl[i], "n"), code=ERRN.get(fld(ctl[i], "code"), fld(ctl[i], "code")),
                            packets_after=after_p, bins_after=after_b, banks_after=len(banks),
                            banks_after_nonzero=len(loud),
                            halt_after=None if qualified else ((h - i) if h is not None else None),
                            halted=any((ctl[x] >> 5) & 1 for x in range(i, len(ctl)))))
    return out


def measure(ctl, dat, budget, score_path):
    """A continuous capture (one sample per clock). Sweeps run strobe to strobe; the stretch after
    the last strobe is measured as a partial sweep (packets, g, T_wake, windows; no length, no sum).
    BCP is found wherever the capture holds it, strobe or not: a capture triggered on the full
    take-set (P becoming 8) holds its BCP in the pre-trigger samples."""
    if is_qualified(ctl):
        return measure_qualified(ctl, dat)
    lab, stay_of = score_map(score_path)
    hk_bcp = lab["HK"] + 1
    S = [i for i, c in enumerate(ctl) if c & 1]
    res = dict(samples=len(ctl), strobes=len(S), sweeps=[], errors=[], packets=[])
    res["strobe_interval"] = sorted(set(b2 - a for a, b2 in zip(S, S[1:])))
    # BCP: the clock the Core enters the BCP word -> inbox_taken rising
    bcps = []
    for i in range(1, len(ctl)):
        if fld(ctl[i], "state") == hk_bcp and fld(ctl[i - 1], "state") != hk_bcp:
            tk = next((x for x in range(i, min(len(ctl), i + 64))
                       if (ctl[x] >> 3) & 1 and not (ctl[x - 1] >> 3) & 1), None)
            bcps.append((i, (tk - i) if tk is not None else None))
    res["bcp_events"] = bcps
    # the full take-set: the BCP that made P = 8 (SWEEP.a lands at BCP)
    p8 = next((i for i in range(1, len(ctl))
               if fld(ctl[i], "sweep") & 15 == 8 and fld(ctl[i - 1], "sweep") & 15 != 8), None)
    res["bcp_full_take"] = next((dt for i, dt in reversed(bcps) if i <= p8), None) if p8 is not None else None
    for j, s0 in enumerate(S):
        complete = j + 1 < len(S)
        s1 = S[j + 1] if complete else len(ctl)
        sw = dict(strobe=s0, n=None, packets=[], complete=complete)
        p_idx = [i for i in range(s0 + 1, s1) if ctl[i] & 2]
        for qi, p in enumerate(p_idx):
            end = p_idx[qi + 1] if qi + 1 < len(p_idx) else s1
            bins, kok, i = 0, True, p
            while i < end and (ctl[i] >> 2) & 1:
                if fld(ctl[i], "k") != bins:
                    kok = False
                bins += 1
                i += 1
            last_bin = p + bins - 1
            ss = p - 1
            pos = fld(ctl[ss], "state") if ss >= 0 else None
            w = None
            if pos in stay_of:
                stay = stay_of[pos]
                for x in range(ss, end):
                    if fld(ctl[x], "state") == stay:
                        w = x - ss
                        break
            sweepw = fld(ctl[p], "sweep")
            q = fld(ctl[p], "q")
            pk = dict(start=p, bins=bins, k_ok=kok, last=last_bin, window=w, q=q, n=fld(ctl[p], "n"),
                      block=(sweepw >> (4 + 3 * q)) & 7, P=sweepw & 15)
            sw["packets"].append(pk)
            res["packets"].append(pk)
        if p_idx:
            sw["n"] = fld(ctl[p_idx[0]], "n")
            sw["t_wake"] = p_idx[0] - s0
            sw["g"] = [sw["packets"][k + 1]["start"] - sw["packets"][k]["last"] - 1 for k in range(len(p_idx) - 1)]
        sw["sum_bins"] = sum(pk["bins"] for pk in sw["packets"]) if complete else None
        sw["bcp"] = next((dt for i, dt in bcps if s0 <= i < s1), None)
        idle = next((i for i in range(s0 + 1, s1) if (ctl[i] >> 6) & 1 and not (ctl[i - 1] >> 6) & 1), None)
        sw["length"] = (idle - s0) if (idle is not None and complete) else None
        res["sweeps"].append(sw)
    res["errors"] = errors_of(ctl, dat)
    return res


# ---------------------------------------------------------------------------------------------------
# the model: host log -> takes -> Reference -> bundles and samples
# ---------------------------------------------------------------------------------------------------
GO_ADDRS = (0x008,)


def parse_log(path):
    """[(kind, ...)]: ('reset',), ('w', addr, data, rej), ('q', addr, rdata) in log order."""
    steps = []
    if not path:
        return steps
    for line in open(path):
        s = line.strip()
        m = re.match(r"^W (\d+) ([0-9a-fA-F]{3}) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) (\d)$", s)
        if m:
            steps.append(("w", int(m.group(2), 16), int(m.group(3), 16), int(m.group(5))))
            continue
        m = re.match(r"^Q (\d+) ([0-9a-fA-F]{3}) ([0-9a-fA-F]{8})$", s)
        if m:
            steps.append(("q", int(m.group(2), 16), int(m.group(3), 16)))
            continue
        m = re.match(r"^W ([0-9a-fA-F]{3}) ([0-9a-fA-F]{8}) -> ([0-9a-fA-F]{8})( REFUSED)?", s)
        if m:
            steps.append(("w", int(m.group(1), 16), int(m.group(2), 16), 1 if m.group(4) else 0))
            continue
        m = re.match(r"^R ([0-9a-fA-F]{3}) -> ([0-9a-fA-F]{8})", s)
        if m:
            steps.append(("q", int(m.group(1), 16), int(m.group(2), 16)))
            continue
        m = re.match(r"^applied GO (\d+) at sweep (\d+)", s)
        if m:
            steps.append(("applied", int(m.group(1)), int(m.group(2))))
            continue
        if re.match(r"^R \d+$", s) or s == "RESET":
            steps.append(("reset",))
    return steps


def takes_from_log(nmax, steps):
    """Replay the writes through switch_model (ROM after each reset); {strobe k: snaps} for the last reset.
    Each GO's strobe = APPLIED_SAMPLE - 1, the sample read back for its GO_SEQ."""
    import switch_model as SM
    import gen_switch_rom as GR
    rom = [(a, d & 0xFFFFFFFF) for a, d, _ in GR.rom_list(nmax)]
    # GO_SEQ -> APPLIED_SAMPLE pairs read back (Q 009 / Q 00A / Q 00B after a wait)
    applied, last_go, last_ap = {}, None, None
    segs = [[]]
    for st in steps:
        if st[0] == "reset":
            segs.append([])
        segs[-1].append(st)
    seg = segs[-1]
    for st in seg:
        if st[0] == "applied": applied[st[1]] = st[2]
        if st[0] == "q" and st[1] == 0x009: last_go = st[2]
        if st[0] == "q" and st[1] == 0x00A: last_ap = st[2]
        if st[0] == "q" and st[1] == 0x00B and last_go is not None and last_ap == last_go:
            applied[last_go] = st[2]
    applied.setdefault(1, 2)                                           # the ROM's GO after reset (CR5-R1)
    sw = SM.Switch(nmax)
    takes, problems = {}, []
    c = [100]

    def ex(port, a, d):
        before = sw.go_seq
        rd, rj = sw.exec(c[0], port, 1, a, d)
        sw.presented(c[0] + 1)
        c[0] += 4
        if sw.go_seq != before:
            k = applied.get(sw.go_seq)
            if k is None:
                problems.append(f"GO {sw.go_seq}: no APPLIED_SAMPLE read back for it; not modelled")
                k = 10 ** 9 + sw.go_seq
            else:
                k -= 1
            sw.strobe(c[0], k)
            sw.taken(c[0] + 1)
            sw.apply(c[0] + 3)
            sw.presented(c[0] + 4)
            c[0] += 8
            takes[k] = sw.takes[-1][1]
        return rj

    for a, d in rom:
        ex(3, a, d)
    for st in seg:
        if st[0] == "w":
            _, a, d, rej = st
            if a == 0x01C and d & 1 and not rej:
                for a2, d2 in rom:
                    ex(3, a2, d2)
                continue
            rj = ex(0, a, d)
            if rj != rej:
                problems.append(f"write {a:03X} {d:08X}: refused {rej} on the board, {rj} in the model")
    return takes, problems


RESEED_ALL = 0x9FFF                                    # every slot of a block (13, 14 are not slots)


def complete_take(snaps):
    """A take that fixes everything the next sweeps play: a sweep word, and every block it orders
    taken whole (RESEED and more). From it the model can start without the history before it."""
    sw = [sn[1] for sn in snaps.values() if sn[0] == "sweep"]
    if not sw:
        return False
    w = sw[0]
    order = [(w >> (4 + 3 * j)) & 7 for j in range(w & 15)]
    blocks = {it: sn for it, sn in snaps.items() if sn[0] != "sweep"}
    return all(b in blocks and (blocks[b][1] & RESEED_ALL) == RESEED_ALL for b in order)


def predict(nmax, takes, upto, g=12, start=None):
    """Bundles per sweep k (1-based) and the bank written at each strobe k (closing sweep k-1).
    start=None: from reset (every take replayed). start=k0: from the complete take of strobe k0
    alone (complete_take), for a capture long after reset: bundles from sweep k0 + 1, banks from
    strobe k0 + 2 (the first one closing a sweep the take made). MG stays at its reset value in
    both (no knob is written by the Phase 6 steps).
    The model stops at a sweep it cannot play (a block an error injection broke): what follows an
    error is checked as silence, not against the model."""
    import switch_model as SM
    import l1_model as M
    sys.path.insert(0, GOLD)
    import sweep_sim as SS
    import cosim_sweep as CS
    step, _ = SS.load_step_toward(CS.ORACLE)
    ref = SS.Reference(step)
    ref.sweep = 0
    out = M.Output(g=g)
    bundles, banks = {}, {}
    pk_prev, mg_open = None, None
    k_first = 1
    if start is not None:
        ref.sample(SM.go_dict(takes[start]))                 # P = 0: nothing plays; the take lands
        k_first = start + 1
    for k in range(k_first, upto + 1):
        try:
            gg = SM.go_dict(takes.get(k, {}))
            n_played = [ref.blk[bk][0] for bk in range(8)]
            obs = ref.sample(gg)
            pk = [(list(bun), n_played[bk]) for bk, bun in obs]
            # the bank written at strobe k closes sweep k - 1
            al, ar = (0, 0) if pk_prev is None else M.sweep_acc(pk_prev, mg_open)
            mg_closed = out.mg
            bank = out.strobe(al, ar, mg_closed)
        except Exception:                                    # noqa: BLE001 (the model's own limits)
            break
        bundles[k] = [(bk, list(bun)) for bk, bun in obs]
        mg_open = out.mg
        if start is None or k >= start + 2:
            banks[k] = (bank[0], bank[1])
        pk_prev = pk
    return bundles, banks


def s24(v):
    return v - (1 << 24) if v >> 23 else v


def spectrum_peaks(x, fs=48000.0, k=4, floor_db=-25.0):
    """The strongest local maxima of the Hann-windowed spectrum, zero-padded to a fine grid:
    [(Hz, dB re the strongest)], at most k, none below floor_db (the window's first side lobe
    is -31.5 dB), lowest frequency first."""
    try:
        import numpy as np
    except ImportError:
        return None
    if len(x) < 256:
        return None
    v = np.array(x, dtype=float)
    v = (v - v.mean()) * np.hanning(len(v))
    nfft = 1 << max(15, int(math.ceil(math.log2(len(v)))) + 2)
    X = np.abs(np.fft.rfft(v, nfft))
    if X.max() <= 0:
        return []
    db = 20 * np.log10(np.maximum(X, 1e-300) / X.max())
    loc = [i for i in range(1, len(X) - 1) if X[i] > X[i - 1] and X[i] >= X[i + 1] and db[i] >= floor_db]
    loc.sort(key=lambda i: -X[i])
    return [(round(i * fs / nfft, 1), round(float(db[i]), 1)) for i in sorted(loc[:k])]


def bench_banks(path):
    """The bench's B lines: [(cycle, n, L, R)], one per bank written."""
    out = []
    for line in open(path):
        m = re.match(r"^B (\d+) (\d+) ([0-9a-fA-F]{6}) ([0-9a-fA-F]{6})$", line.strip())
        if m:
            out.append((int(m.group(1)), int(m.group(2)), s24(int(m.group(3), 16)), s24(int(m.group(4), 16))))
    return out


# ---------------------------------------------------------------------------------------------------
def evaluate(res, ctl, dat, budget, steps, bench=None, max_pcm_sweeps=4000, start_mode="auto"):
    """start_mode: "auto" (from reset when the capture is near it, else from the last complete GO before
    it), "reset", or "go" (from the last complete GO before the capture, wherever the capture is)."""
    b = BUDGETS[budget]
    out = dict(budget=budget, qualified=bool(res.get("qualified")))
    if not out["qualified"]:
        sw = [s for s in res["sweeps"] if s["packets"]]
        out["strobe_interval"] = res["strobe_interval"]
        out["sweeps_with_packets"] = len(sw)
        out["g"] = sorted(set(x for s in sw for x in s.get("g", [])))
        out["t_wake"] = sorted(set(s["t_wake"] for s in sw))
        out["window"] = sorted(set(p["window"] for p in res["packets"] if p["window"] is not None))
        out["floor"] = [w + 2 for w in out["window"]]
        out["k_ok"] = all(p["k_ok"] for p in res["packets"])
        bcp = [s["bcp"] for s in res["sweeps"] if s["bcp"] is not None]
        out["bcp"] = [min(bcp), max(bcp)] if bcp else None
        out["bcp_full_take"] = res.get("bcp_full_take")      # the BCP that made P = 8
        full = [s for s in res["sweeps"] if s["sum_bins"] == b["nmax"]]
        out["full_load_sweeps"] = len(full)
        fl = [s["length"] for s in full if s["length"]]
        out["full_load_length"] = [min(fl), max(fl)] if fl else None
        lens = [s["length"] for s in res["sweeps"] if s["length"]]
        out["sweep_length_max"] = max(lens) if lens else None
        out["packets"] = len(res["packets"])
    out["errors"] = res["errors"]
    err_at = res["errors"][0]["at"] if res["errors"] else None
    # ---- the PCM observed: banks in the capture, or the bench's B lines (with their order key)
    if bench:
        obs_banks = [(cyc, n, l, r) for cyc, n, l, r in bench_banks(bench)]
        err_key = None                                        # the bench's cycles are not the capture's samples
    else:
        obs_banks = []
        for i in sorted(dat):
            if (ctl[i] >> 7) & 1:
                d = dat[i]
                obs_banks.append((i, fld(ctl[i], "n"), s24((d >> 256) & 0xFFFFFF), s24((d >> 280) & 0xFFFFFF)))
        err_key = err_at
    # ---- against the model
    if steps is not None:
        takes, probs = takes_from_log(b["nmax"], steps)
        ns = sorted(set(p["n"] for p in res["packets"]))
        nb = sorted(set(n for _, n, _, _ in obs_banks))
        upto = max(ns + nb + [2])
        first = min(ns + nb) if (ns or nb) else 1
        start = None
        if start_mode == "go" or (start_mode == "auto" and upto > max_pcm_sweeps + 10):
            # long after reset: start from the last complete take before the capture
            k0 = max((k for k, sn in takes.items() if k < first and complete_take(sn)), default=None)
            if k0 is None or upto - k0 > max_pcm_sweeps + 10:
                probs.append(f"capture at sweeps {first}..{upto}: no complete GO within {max_pcm_sweeps} sweeps "
                             f"before it; take the capture soon after a reset or after a GO")
                upto = 0
            else:
                start = k0
        out["model_from"] = "reset" if start is None else f"the complete take of strobe {start}"
        bundles, banks = predict(b["nmax"], takes, upto, start=start) if upto else ({}, {})
        bb = bgood = 0
        first_bad = None
        for p in res["packets"]:
            if p["n"] not in bundles or (err_at is not None and p["start"] > err_at):
                continue
            want = dict(bundles[p["n"]])
            d = dat.get(p["start"])
            got = [(d >> (32 * w)) & 0xFFFFFFFF for w in range(8)] if d is not None else None
            exp = want.get(p["block"])
            bb += 1
            if got is not None and exp is not None and [x & 0xFFFFFFFF for x in exp] == got:
                bgood += 1
            elif first_bad is None:
                first_bad = dict(n=p["n"], q=p["q"], block=p["block"], got=got, want=exp)
        out["bundles"] = dict(compared=bb, equal=bgood, first_bad=first_bad)
        pc = pgood = 0
        pfirst = None
        cap, mod, capn = [], [], []                            # (L, R) pairs, and their strobe
        for key, n, l, r in obs_banks:
            if err_key is not None and key > err_key:
                continue                                      # after the error: silence, checked above
            if n in banks:
                pc += 1
                cap.append((l, r))
                mod.append(banks[n])
                capn.append(n)
                if banks[n] == (l, r):
                    pgood += 1
                elif pfirst is None:
                    pfirst = dict(n=n, got=(l, r), want=banks[n])
        out["pcm"] = dict(compared=pc, equal=pgood, first_bad=pfirst)
        out["model_problems"] = probs
        if cap:
            pk = max(max(abs(l), abs(r)) for l, r in cap)
            out["pcm_peak_dbfs"] = round(20 * math.log10(pk / 2 ** 23), 2) if pk else None
            if takes:                                          # the sound of the last GO alone
                k_last = max(takes)
                aft = [max(abs(l), abs(r)) for (l, r), n in zip(cap, capn) if n >= k_last + 2]
                pk2 = max(aft, default=0)
                out["pcm_peak_dbfs_last_go"] = round(20 * math.log10(pk2 / 2 ** 23), 2) if pk2 else None
            out["spectrum_samples"] = len(cap[-4096:])
            for ch, j in (("L", 0), ("R", 1)):
                out[f"spectrum_peaks_captured_{ch}"] = spectrum_peaks([v[j] for v in cap[-4096:]])
                out[f"spectrum_peaks_model_{ch}"] = spectrum_peaks([v[j] for v in mod[-4096:]])
    elif obs_banks:
        pcm = [(l, r) for key, _, l, r in obs_banks if err_key is None or key <= err_key]
        pk = max((max(abs(l), abs(r)) for l, r in pcm), default=0)
        out["pcm_peak_dbfs"] = round(20 * math.log10(pk / 2 ** 23), 2) if pk else None
        out["spectrum_samples"] = len(pcm[-4096:])
        for ch, j in (("L", 0), ("R", 1)):
            out[f"spectrum_peaks_captured_{ch}"] = spectrum_peaks([v[j] for v in pcm[-4096:]])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vcd")
    ap.add_argument("--budget", type=int, default=50, choices=(50, 100))
    ap.add_argument("--log", default=None, help="host log (bench results or the Tcl's printout)")
    ap.add_argument("--score", default=os.path.join(HW, "l2", "scores", "wpms_r1d.score"))
    ap.add_argument("--clock", default="clk_sys")
    ap.add_argument("--period-ps", type=int, default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--bench", default=None, help="the bench's results file: the PCM from its B lines")
    a = ap.parse_args()
    ctl, dat = read_vcd(a.vcd, a.clock, a.period_ps)
    res = measure(ctl, dat, a.budget, a.score)
    steps = parse_log(a.log) if a.log else None
    out = evaluate(res, ctl, dat, a.budget, steps, bench=a.bench)
    out["samples"] = res["samples"]
    out["strobes"] = res["strobes"]
    print(json.dumps(out, indent=1, default=str))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
