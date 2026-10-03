#!/usr/bin/env python3
# ============================================================================
# cosim_sweep.py — Phase 3 sweep-level cosimulation: hw/l2/wpms_l2_top.v (Core
# RH031p + Formation + sequencer, running a score) against the sweep oracle
# sweep_sim.py (through sweep_dump.py; the golden files are not edited).
#
#   python3 cosim_sweep.py [--score r1d|r1b] [--samples N] [--seeds 2026,7,42]
#                          [--nmax 2048] [--tmin 2083] [--out DIR] [--report FILE]
#                          [--directed] [--rtl DIR]
#
# For every sample of the oracle run: the testbench waits until the sequencer is
# idle, writes through the input-switch port whatever the oracle's writer changed
# (inbox slots, RT.OUT, COMMIT masks and armed bits, the staged sweep word and
# its armed bit), then gives the strobe. Compared, packet by packet: the block
# and the eight-word bundle L1 latches, N (bins with bin_valid), and that K runs
# 0 .. N-1 with no hole; per Stay: the stay_value pin at the Stay's execute
# clock (N for a packet, 0 for housekeeping — C4-F16, W-F22). Measured: T_wake,
# g between packet Stays, BCP and its copy, the sweep length (strobe -> the first
# clock back in a SLEEP wait) against the sample period T_min.
#
# The strobe is given when the previous sweep is over (plus 0-3 clocks), not on a
# 48 kHz grid: the Core only waits in SLEEP meanwhile, so nothing observable
# depends on the idle time; the real-time question — does every sweep fit in
# T_min? — is answered per sweep by its measured length.
#
# --directed adds hand-made cases: the packet floor (N_MIN lowered to 16 for the
# measurement only) and one injected error of each kind EW2..EW6 (L1 silenced at
# once; the Core reaches the trap word and halts).
# Evidence class: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF Phase 3).
# 002 2026-10-03       Claude Code   Chg : the simulator's ERROR lines count with its warnings (the
#                                          Formation's own checks, RH005/RH006, print ERROR).
# ============================================================================
import argparse, json, os, random, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
L2 = os.path.join(HW, "l2")
PROFILE = os.path.normpath(os.path.join(HW, "..", ".."))
WS = os.environ.get("WS", os.path.normpath(os.path.join(PROFILE, "..")))
IMEM = os.path.join(WS, "PTSG-Core", "03_Sample_Implementations", "ai_friendly_vendor_wrappers", "ptsg_imem", "ptsg_imem.v")
ORACLE = os.path.join(WS, "FPGA_Spectrum_Engine_OpenPrompt", "04_Verification", "oracle", "wpms_layer1_oracle.py")
sys.path.insert(0, HERE)
import score_as as SA

ERRN = {4: "E4", 5: "E5", 8: "E8", 18: "EW2", 19: "EW3", 20: "EW4", 21: "EW5", 22: "EW6"}
SCORES = {"r1d": "wpms_r1d.score", "r1b": "wpms_r1b.score"}


# ---------------------------------------------------------------- build & run
def assemble(score_path, outdir, tag):
    words, info = SA.assemble(score_path)
    base = os.path.join(outdir, tag)
    open(base + ".hex", "w").write(SA.to_hex(words, info, os.path.basename(score_path)))
    return base + ".hex", info


RTL = [L2]                                                   # directories searched for the RTL (mutant runs first)


def rtl(name):
    for d in RTL:
        if os.path.exists(os.path.join(d, name)): return os.path.join(d, name)
    raise FileNotFoundError(name)


def build(outdir, hexfile, nmax, n_min, tag):
    exe = os.path.join(outdir, f"l2tb_{tag}.vvp")
    cmd = ["iverilog", "-g2012", "-I", RTL[0], "-I", L2, f"-Pwpms_l2_tb.SCORE=\"{hexfile}\"", f"-Pwpms_l2_tb.NMAX={nmax}",
           f"-Pwpms_l2_tb.N_MIN={n_min}", "-o", exe,
           os.path.join(L2, "wpms_l2_tb.v"), rtl("wpms_l2_top.v"), os.path.join(HW, "core", "ptsg_core_rh031p.v"),
           IMEM, rtl("wpms_formation.v"), rtl("wpms_sequencer.v")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines()
           if l.strip() and "sensitive to all" not in l and "coerced to inout" not in l]
    if r.returncode or bad:
        print("\n".join(bad[:30])); sys.exit(2)
    return exe


def run(exe, outdir, tag, stim):
    sp, rp = os.path.join(outdir, f"stim_{tag}.txt"), os.path.join(outdir, f"res_{tag}.txt")
    open(sp, "w").write(stim)
    r = subprocess.run(["vvp", "-n", exe, f"+stim={sp}", f"+out={rp}"], capture_output=True, text=True)
    warn = [l for l in (r.stdout + r.stderr).splitlines() if "WARNING" in l or "ERROR" in l]
    return parse(rp), warn


def parse(path):
    ev = []
    for line in open(path):
        f = line.split()
        if not f: continue
        k = f[0]
        if k == "L": ev.append(("L", int(f[1]), int(f[2]), [int(x, 16) for x in f[3:11]]))
        elif k == "P": ev.append(("P", int(f[1]), int(f[2]), int(f[3])))
        elif k == "A": ev.append(("A", int(f[1]), int(f[2]), int(f[3], 16), int(f[4])))
        elif k == "V": ev.append(("V", int(f[1]), int(f[2], 16), int(f[3])))
        elif k == "B": ev.append(("B", int(f[1]), int(f[2], 16)))
        elif k == "F": ev.append(("F", int(f[1]), int(f[2]), int(f[3], 16)))
        elif k in ("H", "Q"): ev.append((k, int(f[1]), int(f[2], 16)))
        else: ev.append((k, int(f[1])))                  # S D U C M T
    return ev


# ---------------------------------------------------------------- stimulus
SWITCH0 = dict(inbox=[[0] * 16 for _ in range(8)], commit=[0] * 8, armed=[False] * 8, rtout=[0] * 8,
               sweep_staged=0, sweep_armed=False)


def switch_writes(old, new):
    """Input-switch writes that turn the hardware's switch side from old into new
    (data first, the arming last, as the writer does it)."""
    w = []
    for b in range(8):
        for i in range(16):
            if i in (13, 14): continue
            if new["inbox"][b][i] != old["inbox"][b][i]: w.append((b * 16 + i, new["inbox"][b][i]))
        if new["rtout"][b] != old["rtout"][b]: w.append((0x80 + b, new["rtout"][b]))
    for b in range(8):
        if new["commit"][b] != old["commit"][b] or new["armed"][b] != old["armed"][b]:
            w.append((0x88 + b, new["commit"][b] | (int(new["armed"][b]) << 30)))
    if new["sweep_staged"] != old["sweep_staged"]: w.append((0x90, new["sweep_staged"]))
    if new["sweep_armed"] != old["sweep_armed"]: w.append((0x91, int(new["sweep_armed"]) << 30))
    return w


def stim_from_dump(dump, rng):
    L = ["R 4"]
    sh = json.loads(json.dumps(SWITCH0))
    for s in dump["samples"]:
        L.append("W")
        for a, d in switch_writes(sh, s["switch"]): L.append(f"X {a:x} {d & 0xFFFFFFFF:x}")
        sh = s["switch"]
        g = rng.randrange(4)
        if g: L.append(f"N {g:x}")
        L.append("S")
    L += ["W", "N 10", "E"]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- analysis
def per_sweep(ev):
    """Split events at the strobes: [(strobe_cyc, [events up to the next strobe])]."""
    out, cur = [], None
    for e in ev:
        if e[0] == "S":
            cur = (e[1], []); out.append(cur)
        elif cur is not None:
            cur[1].append(e)
    return out


def analyse(dump, ev, tmin, nmax):
    probs, sweeps = [], per_sweep(ev)
    exp = dump["samples"]
    if len(sweeps) != len(exp):
        probs.append(f"{len(sweeps)} strobes seen, {len(exp)} samples in the dump")
    st = dict(packets=0, bins=0, sweeps=0, full=0, wake=[], g=[], sweep_len=[], full_len=[], hk=[], bcp_copy=[],
              pin_pkt_bad=0, pin_hk_bad=0, stays=0)
    for n, ((s_cyc, es), want) in enumerate(zip(sweeps, exp)):
        lat = [e for e in es if e[0] == "L"]
        pkt = [e for e in es if e[0] == "P"]
        got = [(e[2], e[3]) for e in lat]
        wantp = [(p["block"], p["bundle"]) for p in want["packets"]]
        if got != wantp:
            i = next((k for k in range(min(len(got), len(wantp))) if got[k] != wantp[k]), min(len(got), len(wantp)))
            probs.append(f"sample {n}: packet {i}: got {got[i] if i < len(got) else '-'} want {wantp[i] if i < len(wantp) else '-'}"
                         f" ({len(got)} latched, {len(wantp)} expected)")
        nb = [e[2] for e in pkt]
        if nb != [p["N"] for p in want["packets"]]:
            probs.append(f"sample {n}: bins per packet {nb} want {[p['N'] for p in want['packets']]}")
        if any(e[3] != 1 for e in pkt):
            probs.append(f"sample {n}: K did not run 0..N-1 in a packet")
        for k in ("M", "T", "F", "H", "Q"):
            for e in es:
                if e[0] == k: probs.append(f"sample {n}: unexpected event {e}")
        # Stay Sets (A: logged one clock after the Stay Set) and the pin at each Stay (V)
        ss = [(e[1] - 1, e[2]) for e in es if e[0] == "A"]
        pk_ss = [c for c, kind in ss if kind == 1]
        hk_ss = [c for c, kind in ss if kind == 0]
        stays = [e for e in es if e[0] == "V"]
        st["stays"] += len(stays)
        Ns = [p["N"] for p in want["packets"]]
        for j, e in enumerate(stays):
            if j < len(Ns):
                if e[3] != Ns[j]: st["pin_pkt_bad"] += 1
            elif e[3] != 0: st["pin_hk_bad"] += 1
        if pk_ss: st["wake"].append(pk_ss[0] - s_cyc)
        for j in range(len(pk_ss)):
            nxt = pk_ss[j + 1] if j + 1 < len(pk_ss) else (hk_ss[0] if hk_ss else None)
            if nxt is not None and j < len(Ns): st["g"].append(nxt - pk_ss[j] - Ns[j])
        u = [e[1] for e in es if e[0] == "U"]
        if u:
            ln = u[0] - s_cyc
            st["sweep_len"].append(ln)
            if sum(Ns) == nmax: st["full_len"].append(ln); st["full"] += 1
            if ln > tmin: probs.append(f"sample {n}: sweep of {ln} clocks > T_min {tmin}")
            if hk_ss: st["hk"].append(u[0] - hk_ss[0])
        b = [e[1] for e in es if e[0] == "B"]
        c = [e[1] for e in es if e[0] == "C"]
        if b and c: st["bcp_copy"].append(c[0] - b[0])
        st["packets"] += len(lat); st["bins"] += sum(nb); st["sweeps"] += 1
    if st["pin_pkt_bad"]: probs.append(f"stay_value at {st['pin_pkt_bad']} packet Stays differed from N")
    if st["pin_hk_bad"]: probs.append(f"stay_value non-zero at {st['pin_hk_bad']} housekeeping Stays")
    return probs, st


def rng_str(v):
    return f"{min(v)}..{max(v)}" if v else "-"


# ---------------------------------------------------------------- directed cases
RESEED = 0x9FFF | 1 << 16


def make_block(rng, N, le0=None):
    q26 = 1 << 26
    v = [0] * 16
    v[0] = N; v[1] = rng.randrange(1 << 16); v[2] = rng.randrange(-32 * q26, 0) & 0xFFFFFFFF
    v[9] = rng.randrange(-32 * q26, 0) & 0xFFFFFFFF; v[5] = (13933 if le0 is None else le0) & 0xFFFFFFFF
    for i in (3, 4, 6, 7, 8, 10, 11, 12, 15): v[i] = rng.getrandbits(32)
    return v


def go_lines(blocks, sweep_order, mask=RESEED, arm_sweep=True):
    L = []
    for b, vals in blocks.items():
        for i in range(16):
            if i not in (13, 14): L.append(f"X {b * 16 + i:x} {vals[i] & 0xFFFFFFFF:x}")
        L.append(f"X {0x80 + b:x} 1")
        L.append(f"X {0x88 + b:x} {mask | 1 << 30:x}")
    if sweep_order is not None:
        w = len(sweep_order)
        for k, b in enumerate(sweep_order): w |= b << (4 + 3 * k)
        L.append(f"X 90 {w:x}")
        L.append(f"X 91 {int(arm_sweep) << 30:x}")
    return L


def unarm(blocks, sweep=True):
    L = [f"X {0x88 + b:x} {RESEED:x}" for b in blocks]
    if sweep: L.append("X 91 0")
    return L


def directed(rng, score_hex, outdir, nmax, score):
    """Floor measurement and the five error injections. Returns report lines, problems."""
    lines, probs = [], []
    # ---- the packet floor: N = 28 .. 33 with N_MIN lowered to 16 (measurement only)
    exe = build(outdir, score_hex, nmax, 16, "floor")
    blocks = {b: make_block(rng, N) for b, N in zip(range(6), (28, 29, 30, 31, 32, 33))}
    L = ["R 4"] + go_lines(blocks, [0, 1, 2, 3, 4, 5]) + ["S", "W"] + unarm(blocks) + ["S", "W", "N 10", "E"]
    ev, warn = run(exe, outdir, "floor", "\n".join(L) + "\n")
    ss = [e[1] - 1 for e in ev if e[0] == "A" and e[2] == 1]
    hk = [e[1] - 1 for e in ev if e[0] == "A" and e[2] == 0]
    per = [b - a for a, b in zip(ss, ss[1:] + hk[-1:])]
    lines.append("  floor (N_MIN lowered to 16 for this case only): N = 28 29 30 31 32 33 -> Stay Set to next Stay Set "
                 + " ".join(map(str, per)))
    # ---- error injections
    exe = build(outdir, score_hex, nmax, 32, "err")
    base = {b: make_block(rng, 64) for b in range(8)}
    start = ["R 4"] + go_lines(base, [0, 1, 2]) + ["S", "W"] + unarm(base) + ["S", "W"]   # one empty, one 3-packet sweep
    cases = [
        ("EW6", "LE0 < 0 lands in block 1 (a listed block): its next packet window's STP",
         [f"X 15 ffffffff", f"X 89 {0x20 | 1 << 30:x}"], ["S", "W", "X 89 20", "S", "W"]),
        ("EW5", "a sweep item repeating block 2, taken at the strobe: BCP in housekeeping",
         ["X 90 " + f"{3 | 2 << 4 | 0 << 7 | 2 << 10:x}", "X 91 40000000"], ["S", "W"]),
        ("EW2", "block 0's N = 16 lands with the sweep [0]: the post-housekeeping prefetch",
         ["X 00 10", f"X 88 {1 | 1 << 30:x}", "X 90 " + f"{1 | 0 << 4:x}", "X 91 40000000"], ["S", "W", "S", "W"]),
    ]
    bad_windows = [
        ("EW4", "a window writing the store directly (negative_tests N1) as the packet window",
         ".bg\n SAD 0x006\n LDM\n SAD 0x00A\n ADD @PPM\n SAD 0x006\n STM\n"),
        ("EW3", "a window writing the inbox view (negative_tests N4) as the packet window",
         ".bg\n SAD 0x082\n STM\n"),
    ]
    results = []
    for code, what, writes, tail in cases:
        stim = start + writes + tail + ["N 3000", "E"]
        ev, warn = run(exe, outdir, f"err_{code}", "\n".join(stim) + "\n")
        results.append((code, what, ev, warn))
    src = open(os.path.join(L2, "scores", SCORES[score])).read()
    for code, what, prog in bad_windows:
        wp = os.path.join(outdir, f"bad_{code}.pfasm"); open(wp, "w").write(prog)
        sp = os.path.join(outdir, f"bad_{code}.score")
        open(sp, "w").write(src.replace(".window PKT wpms_packet.pfasm", f".window PKT {wp}")
                               .replace(".window HKD ../programs/", ".window HKD " + os.path.join(L2, "programs") + "/"))
        hexf, _ = assemble(sp, outdir, f"bad_{code}")
        exe2 = build(outdir, hexf, nmax, 32, f"bad_{code}")
        ev, warn = run(exe2, outdir, f"err_{code}", "\n".join(start + ["N 3000", "E"]) + "\n")
        results.append((code, what, ev, warn))
    for code, what, ev, warn in results:
        f = [e for e in ev if e[0] == "F"]
        h = [e for e in ev if e[0] == "H"]
        m = [e for e in ev if e[0] == "M"]
        q = [e for e in ev if e[0] == "Q"]
        after = [e for e in ev if e[0] in ("L",) and f and e[1] >= f[0][1]]
        # The Core's end: HALT at the trap word; in the lane form (r1b) an insertion taken after the
        # sweep's one taken Branch spills the holding register and waits in S_PUSH (no external stack).
        core_ok = (bool(h) and not q) or (score == "r1b" and bool(q) and not h)
        ok = bool(f) and ERRN.get(f[0][2]) == code and not m and not after and core_ok
        if not ok: probs.append(f"error case {code}: F {f[:1]} H {h[:1]} M {len(m)} latches after {len(after)} spill {len(q)}")
        end = (f"Core HALT at the trap 0x{h[0][2]:03X}, {h[0][1] - f[0][1]} clocks later" if f and h else
               f"Core waits in S_PUSH at 0x{q[0][2]:03X} (holding register taken by the sweep's Branch; no external stack)"
               if q else "Core end not reached")
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {code}: {what} -> error_flag {ERRN.get(f[0][2], '?') if f else 'none'}"
                     f"{' at clock ' + str(f[0][1]) if f else ''}; L1 muted from that clock (latches after: {len(after)}, "
                     f"bins while muted: {len(m)}); {end}")
    return lines, probs


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", default="r1d", choices=sorted(SCORES))
    ap.add_argument("--samples", type=int, default=12000)
    ap.add_argument("--seeds", default="2026,7,42")
    ap.add_argument("--nmax", type=int, default=2048)
    ap.add_argument("--tmin", type=int, default=2083)
    ap.add_argument("--out", default=os.path.join(L2, "build", "cosim_sweep"))
    ap.add_argument("--report", default="")
    ap.add_argument("--directed", action="store_true")
    ap.add_argument("--rtl", default="", help="directory searched first for wpms_*.v (mutant runs)")
    ap.add_argument("--allow-overrun", action="store_true", help="report sweeps longer than T_min, do not fail on them")
    a = ap.parse_args()
    if a.rtl: RTL.insert(0, a.rtl)
    tag = f"{a.score}_n{a.nmax}"
    out = os.path.join(a.out, tag); os.makedirs(out, exist_ok=True)
    t0 = time.time()
    hexf, info = assemble(os.path.join(L2, "scores", SCORES[a.score]), out, a.score)
    exe = build(out, hexf, a.nmax, 32, "main")
    seeds = [int(s) for s in a.seeds.split(",") if s]

    def one(seed):
        dp = os.path.join(out, f"dump_{seed}.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "sweep_dump.py"), dp, "--oracle", ORACLE,
                            "--samples", str(a.samples), "--seed", str(seed), "--nmax", str(a.nmax)],
                           capture_output=True, text=True)
        dump = json.load(open(dp))
        ev, warn = run(exe, out, f"s{seed}", stim_from_dump(dump, random.Random(seed)))
        probs, st = analyse(dump, ev, a.tmin, a.nmax)
        over = [x for x in probs if "> T_min" in x]
        st["overruns"] = len(over)
        if a.allow_overrun: probs = [x for x in probs if "> T_min" not in x]
        if dump["provenance"]["oracle_exit"] != 0: probs.append(f"the oracle itself failed (exit {dump['provenance']['oracle_exit']})")
        probs += [f"simulator: {w}" for w in warn]
        return seed, dump, probs, st, r.stdout.strip().splitlines()

    with ThreadPoolExecutor(len(seeds)) as ex:
        res = list(ex.map(one, seeds))
    L = []
    p = L.append
    p(f"cosim_sweep: wpms_l2_top ({SCORES[a.score]}) vs sweep_sim.py — evidence class RTL-SIM; NMAX {a.nmax}, T_min {a.tmin}")
    allp, tot = [], dict(packets=0, bins=0, sweeps=0, full=0, stays=0, overruns=0)
    agg = dict(wake=[], g=[], sweep_len=[], full_len=[], hk=[], bcp_copy=[])
    for seed, dump, probs, st, olines in res:
        ol = [l for l in olines if "mismatches" in l]
        p(f"  seed {seed}: {st['sweeps']} sweeps, {st['packets']} packets latched, {st['bins']} bins, "
          f"{st['full']} full-load sweeps; oracle: {ol[0].strip() if ol else '?'}; {'PASS' if not probs else 'FAIL'}")
        for k in tot: tot[k] += st[k]
        for k in agg: agg[k] += st[k]
        allp += [f"seed {seed}: {x}" for x in probs]
    p(f"  total: {tot['sweeps']} sweeps, {tot['packets']} packets, {tot['bins']} bins, {tot['full']} full-load sweeps, "
      f"{tot['stays']} Stays with the pin checked; sweeps longer than T_min: {tot['overruns']}")
    p(f"  T_wake (strobe clock -> first packet Stay Set): {rng_str(agg['wake'])} clocks; L1 packet_start one clock later")
    p(f"  g (Stay Set to next Stay Set minus N): {rng_str(agg['g'])}")
    p(f"  housekeeping Stay Set -> first SLEEP clock: {rng_str(agg['hk'])}; BCP commit -> copy landed: {rng_str(agg['bcp_copy'])} clocks")
    p(f"  sweep length (strobe -> first SLEEP clock): {rng_str(agg['sweep_len'])}; full-load sweeps: {rng_str(agg['full_len'])} "
      f"of T_min {a.tmin} ({a.tmin - max(agg['full_len']) if agg['full_len'] else '-'} spare at worst)")
    if a.directed:
        dl, dp = directed(random.Random(99), hexf, out, a.nmax, a.score)
        L += dl; allp += dp
    for x in allp[:30]: p("  FAIL " + x)
    if len(allp) > 30: p(f"  ... {len(allp)} problems in all")
    p(f"cosim_sweep: {'PASS' if not allp else 'FAIL'} ({time.time() - t0:.0f} s)")
    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    if a.report: open(a.report, "w").write(text)
    sys.exit(0 if not allp else 1)


if __name__ == "__main__":
    main()
