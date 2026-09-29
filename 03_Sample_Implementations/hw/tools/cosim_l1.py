#!/usr/bin/env python3
# ============================================================================
# cosim_l1.py — Phase 4 cosimulation of the L1 pipeline against the customer's
# oracle (golden: l1_phase, l1_amplitude, exp2_q131, step_toward) and the
# published model of the parts the oracle does not model (hw/tools/l1_model.py:
# sin core, product, accumulators, output stage).
#
#   python3 cosim_l1.py units  [--n 1000000] [--seed 1]     sin core and exp2 unit
#   python3 cosim_l1.py module [--sweeps 400] [--seed 1]    wpms_l1_module + output
#                                                           stage, bin by bin and
#                                                           sample by sample
#   python3 cosim_l1.py mgfade                               MG 0 -> -60 dB, soft mute
#                                                           to the floor, exact zero
#   common: --out DIR (build), --rtl DIR (a directory whose .v files replace
#           hw/l1's — used by the mutants), --report FILE
#
# Evidence class of every comparison: RTL-SIM (Icarus Verilog -g2012).
# License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF Phase 4).
# ============================================================================
import argparse, math, os, random, shutil, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import l1_model as M                      # noqa: E402
O = M.O
HW = os.path.normpath(os.path.join(HERE, ".."))
L1 = os.path.join(HW, "l1")
Q30 = 1 << 30


def rtl_file(name, rtl):
    if rtl and os.path.exists(os.path.join(rtl, name)):
        return os.path.join(rtl, name)
    return os.path.join(L1, name)


def run(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(log, "w").write(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    return r


def compile_tb(top, files, out, rtl, extra=()):
    vvp = os.path.join(out, top + ".vvp")
    srcs = [rtl_file(f, rtl) for f in files]
    inc = [f"-I{rtl}"] if rtl else []
    r = run(["iverilog", "-g2012", "-Wall", *inc, f"-I{L1}", "-o", vvp, "-s", top, *extra, *srcs],
            os.path.join(out, top + ".compile.log"))
    if r.returncode != 0:
        raise SystemExit(f"compile failed: see {out}/{top}.compile.log\n{r.stderr[-2000:]}")
    return vvp


# ---------------------------------------------------------------------------
# units: sin core and exp2 unit, one input per clock
# ---------------------------------------------------------------------------
def unit_inputs(n, rnd):
    ph = []
    for q in range(4):                                   # quadrant edges and the u-truncation edges
        for d in (0, 1, 2, 15, 16, 17, (1 << 29), (1 << 30) - 17, (1 << 30) - 16, (1 << 30) - 2, (1 << 30) - 1):
            ph.append(q * Q30 + d)
    Ls = [0, -1, 1, -Q30, -Q30 - 1, -Q30 + 1, -31 * Q30, -31 * Q30 - 1, -31 * Q30 + 1, -30 * Q30,
          (1 << 53) - 1, -(1 << 53), -(1 << 52), 5 * Q30]
    for ip in range(-31, 0):                             # every integer part x every table entry x lo edges
        for hi in range(256):
            for lo in (0, 1, (1 << 21), (1 << 22) - 1):
                Ls.append(ip * Q30 + (hi << 22) + lo)
    while len(ph) < n:
        ph.append(rnd.randrange(1 << 32))
    k = len(Ls)
    while len(Ls) < n:
        r = rnd.random()
        if r < 0.8:
            Ls.append(rnd.randrange(-31 * Q30 - 1, 1))                   # the unclamped range
        elif r < 0.95:
            Ls.append(rnd.randrange(-40 * Q30, 8 * Q30))
        else:
            Ls.append(rnd.randrange(-(1 << 53), 1 << 53))
    return ph[:n], Ls[:n], k


def cmd_units(a):
    rnd = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    ph, Ls, ndir = unit_inputs(a.n, rnd)
    fin = os.path.join(a.out, "units_in.txt")
    with open(fin, "w") as f:
        for p, L in zip(ph, Ls):
            f.write(f"{p:08X} {L & ((1 << 54) - 1):014X}\n")
    vvp = compile_tb("wpms_l1_units_tb", ["wpms_l1_units_tb.v", "wpms_l1_sin.v", "wpms_l1_exp2.v"], a.out, a.rtl,
                     extra=[f"-Pwpms_l1_units_tb.EXP2_HEX=\"{rtl_file('wpms_exp2_table.hex', a.rtl)}\""])
    fout = os.path.join(a.out, "units_out.txt")
    r = run(["vvp", "-n", vvp, f"+in={fin}", f"+out={fout}", f"+n={len(ph)}"], os.path.join(a.out, "units_sim.log"))
    lines = open(fout).read().split() if os.path.exists(fout) else []
    bad_s = bad_a = 0
    first = []
    for i in range(len(ph)):
        if 2 * i + 1 >= len(lines):
            bad_s += 1; bad_a += 1
            continue
        s = int(lines[2 * i], 16)
        s = s - (1 << 41) if s >> 40 else s
        av = int(lines[2 * i + 1], 16)
        es, ea = M.sin_q040(ph[i]), O.exp2_q131(Ls[i])
        if s != es:
            bad_s += 1
            if len(first) < 5: first.append(f"sin phase=0x{ph[i]:08X}: RTL {s} model {es}")
        if av != ea:
            bad_a += 1
            if len(first) < 10: first.append(f"exp2 L={Ls[i]}: RTL {av} oracle {ea}")
    ok = bad_s == 0 and bad_a == 0 and len(lines) == 2 * len(ph)
    rep = [f"cosim_l1 units — evidence class RTL-SIM (Icarus), seed {a.seed}",
           f"  sin core  (wpms_l1_sin.v)  vs l1_model.sin_q040 : {len(ph)} phases ({4 * 11} directed edges): mismatches {bad_s}",
           f"  exp2 unit (wpms_l1_exp2.v) vs oracle exp2_q131  : {len(Ls)} L values ({ndir} directed: every integer part x "
           f"every table entry x 4 lo edges, and the clamps): mismatches {bad_a}"]
    rep += ["  FAIL " + x for x in first]
    rep.append(f"cosim_l1 units: {'PASS' if ok else 'FAIL'}")
    return ok, rep


# ---------------------------------------------------------------------------
# module: wpms_l1_module + wpms_output_stage
# ---------------------------------------------------------------------------
D_L1 = 19
INSP_POS = 7                                  # the inspector's bin position (Ch.5 0x040)


def rand_bundle(rnd, kind):
    """kind 'full': every slot at full range (the sweep oracle's rand_block style);
       'musical': a Gaussian-like shape and a level inside the clamps."""
    u = lambda: rnd.randrange(1 << 32)
    if kind == "full":
        b = [u() for _ in range(7)] + [rnd.randrange(1 << 16)]
    else:
        N = 2048
        g = rnd.choice([1e-6, 1e-5, 1e-4, 5e-4])
        ls0, lad1, lad2, lp = O.gaussian_slots(N, g, beta=rnd.uniform(-0.01, 0.01),
                                                A0=rnd.uniform(0.05, 0.99), consistent=rnd.random() < 0.5)
        lp = max(-(1 << 31), min((1 << 31) - 1, lp - rnd.randrange(0, 8 << 26)))
        b = [u(), u(), u(), lp & 0xFFFFFFFF, ls0 & 0xFFFFFFFF, lad1 & 0xFFFFFFFF, lad2 & 0xFFFFFFFF,
             rnd.randrange(1 << 16)]
    return b


def module_schedule(a, rnd):
    """A list of commands and, per sweep, what the model needs."""
    cmds, sweeps = [], []
    clk = 0                          # the clock the next command starts in
    ctrl = dict(dip_g=3, g_ctrl=0, soft=0, err=0, mgt=0, mgr=M.MG_RATE_DEFAULT)
    cmds.append(("C", dict(ctrl)))
    cmds.append(("I", 5)); clk += 5
    n_sw = a.sweeps
    for i in range(n_sw):
        # controls change between sweeps (before the strobe)
        if rnd.random() < 0.3:
            ctrl["dip_g"] = rnd.randrange(4)
        if rnd.random() < 0.1:
            ctrl["g_ctrl"] = rnd.choice([0, 16 | rnd.randrange(16)])
        if rnd.random() < 0.15:
            ctrl["mgt"] = rnd.choice([0, -(rnd.randrange(1 << 31)), -(1 << 31), rnd.randrange(1 << 20)])
        if rnd.random() < 0.1:
            ctrl["mgr"] = rnd.choice([M.MG_RATE_DEFAULT, 0, rnd.randrange(1 << 28), (1 << 31) + 5])
        if i == n_sw // 2:
            ctrl["soft"] = 1                                    # soft mute: MG to the floor, fast,
            ctrl["mgr"] = 1 << 28                               # so that the exact-zero rule is reached
        if i == n_sw // 2 + 40:
            ctrl["soft"] = 0
        if i == n_sw - 12:
            ctrl["err"] = 1                                     # the ruling's silence, to the end
        cmds.append(("C", dict(ctrl)))
        s_clk = clk
        cmds.append(("S", None)); clk += 1
        gap0 = rnd.choice([1, 1, 1, 2, 3, 4])                    # strobe -> first bin on the face
        cmds.append(("I", gap0)); clk += gap0
        P = rnd.choice([0, 1, 1, 2, 3, 4, 8])
        pk = []
        last_c0 = None
        for q in range(P):
            kind = "full" if rnd.random() < 0.5 else "musical"
            n = rnd.choice([1, 2, 3, rnd.randrange(1, 64), rnd.randrange(32, 300), rnd.randrange(1, 2049)])
            b = rand_bundle(rnd, kind)
            cmds.append(("P", (n, b)))
            pk.append(dict(n=n, bundle=b, c0=clk))
            clk += n
            last_c0 = clk - 1
            g = rnd.choice([0, 0, 0, 0, 1, 2])
            if g and q + 1 < P:
                cmds.append(("I", g)); clk += g
        # idle to the next strobe: the last bin's product (c0 + 19) must land no later
        # than the strobe clock (tail >= D_L1 - 1). Normally it lands before; now and
        # then exactly in the strobe clock (tail = D_L1 - 1: included in the closing
        # sample); once, one clock late (tail = D_L1 - 2: overrun, next sample).
        tail = rnd.choice([D_L1 + rnd.randrange(0, 40), D_L1 - 1, D_L1, D_L1 + 300])
        if i == n_sw - 20 and last_c0 is not None:
            tail = D_L1 - 2                                     # the deliberate overrun
        tail = max(tail, 1)
        cmds.append(("I", tail if last_c0 is not None else max(tail, 2))); clk += tail if last_c0 is not None else max(tail, 2)
        sweeps.append(dict(strobe=s_clk, ctrl=dict(ctrl), packets=pk))
    cmds.append(("C", dict(ctrl)))
    cmds.append(("S", None)); final_strobe = clk; clk += 1
    cmds.append(("I", 40)); clk += 40
    return cmds, sweeps, final_strobe


def module_expect(sweeps, final_strobe, start_g=12):
    """Model the RTL: per bin (in order) and per strobe."""
    bins = []                                # (phase, L-free a, sin, prod) per bin, and its c19 clock
    strobes = [s["strobe"] for s in sweeps] + [final_strobe]
    out = M.Output()
    mg_now = 0                               # MG after the step at the last strobe (= used by packets)
    # products by c19 clock
    events = []                              # (c19, prod, rt, sweep_index_of_c0)
    err_clock = None
    for si, sw in enumerate(sweeps):
        if sw["ctrl"]["err"] and err_clock is None:
            err_clock = sw["strobe"]         # the controls were set before this strobe (see schedule)
    # MG per sweep is determined by the output stage's steps; run strobe by strobe
    exp_banks = []
    acc = {}                                 # sample index -> [L, R]
    mgs = []
    prev_ctrl = sweeps[0]["ctrl"]
    # first pass: MG sequence (depends only on controls at each strobe)
    mg = 0
    mg_used = []
    for si, s in enumerate(strobes):
        c = sweeps[si]["ctrl"] if si < len(sweeps) else sweeps[-1]["ctrl"]
        tgt = M.MG_FLOOR if c["soft"] else min(M.s32(c["mgt"]), 0)
        rate = 0 if (c["mgr"] >> 31) else c["mgr"]
        mg_before = mg
        mg = O.step_toward(mg, tgt, rate)
        mg_used.append((mg_before, mg))      # (MG of the sweep closed here, MG of the sweep opened here)
    # bins
    insp = {}                                # sweep index -> (phase, L, a) of the bin at INSP_POS
    for si, sw in enumerate(sweeps):
        mg_sweep = mg_used[si][1]
        pos = 0
        for p in sw["packets"]:
            r = M.packet(p["bundle"], p["n"], mg_sweep)
            if pos <= INSP_POS < pos + p["n"]:
                k = INSP_POS - pos
                insp[si] = (r["phase"][k], r["L"](k), r["a"][k])
            pos += p["n"]
            for k in range(p["n"]):
                c0 = p["c0"] + k
                bins.append((r["phase"][k], r["a"][k], r["sin"][k], r["prod"][k]))
                events.append((c0 + D_L1, r["prod"][k], r["rt"], c0))
    # assign each product to the sample open at its c19 clock: interval (S_j, S_j+1]
    import bisect
    over = False
    lastc = {}
    samp_acc = [[0, 0] for _ in strobes]
    for c19, prod, rt, c0 in events:
        if err_clock is not None and c19 >= err_clock + 0:   # mute raised with the controls before err_clock
            pass
        j = bisect.bisect_left(strobes, c19) - 1         # strobes[j] < c19 <= strobes[j+1]
        i0 = bisect.bisect_left(strobes, c0) - 1         # the sample open at c0 (tag)
        if j != i0:
            over = True
        if err_clock is not None and c19 >= err_clock:
            continue                                     # muted: not accumulated
        if j + 1 < len(strobes):
            if rt & 1: samp_acc[j][0] += prod
            if rt & 2: samp_acc[j][1] += prod
            lastc[j] = min(c19 - strobes[j], 0xFFF)      # the RTL counter saturates
    # strobes 1.. close samples 0..; strobe 0 closes the empty sample before it
    for si in range(len(strobes)):
        c = sweeps[si]["ctrl"] if si < len(sweeps) else sweeps[-1]["ctrl"]
        out.g = (c["g_ctrl"] & 15) if (c["g_ctrl"] & 16) else 4 * c["dip_g"]
        out.soft_mute = bool(c["soft"])
        out.mg_target = M.s32(c["mgt"])
        out.mg_rate = c["mgr"] if not (c["mgr"] >> 31) else -1
        error = bool(c["err"])
        if si == 0:
            al = ar = 0
            sc = 0
        else:
            al, ar = samp_acc[si - 1]
            sc = lastc.get(si - 1, 0)
        mg_closed = mg_used[si][0]
        out.mg = mg_closed                               # the model steps it inside strobe()
        bank = out.strobe(al, ar, mg_closed, error=error)
        assert out.mg == mg_used[si][1]
        ins = insp.get(si - 1) if si else None
        exp_banks.append((bank[0], bank[1], out.clip[0] | (out.clip[1] << 1), out.mg, sc, ins))
    return bins, exp_banks, over


def mgfade_schedule(a):
    """Ch.4 §4.4.1/§4.4.5: MG 0 -> -60 dB at the default rate (CH4-MG: 1.0 s), then the
    soft mute to the floor (-32) and the exact zero there (C4-D6). One bin per sweep,
    LP = +16 (a clamped at 1 until MG < -16) at phase 1/4 (sin = 1), G = 0, so that the
    level stays visible to the floor (2^-16 of full scale = 128 LSB)."""
    target = -round(60 / M.O.DB_PER_LOG2 * 2 ** 26)
    cmds, sweeps = [], []
    clk = 0
    ctrl = dict(dip_g=0, g_ctrl=0, soft=0, err=0, mgt=target & 0xFFFFFFFF, mgr=M.MG_RATE_DEFAULT)
    cmds.append(("C", dict(ctrl))); cmds.append(("I", 5)); clk += 5
    b = [0x40000000, 0, 0, (16 << 26) & 0xFFFFFFFF, 0, 0, 0, 3]
    mg, n_fade, n_floor, i = 0, None, None, 0
    while True:
        if n_fade is not None and not ctrl["soft"]:
            ctrl["soft"] = 1
        cmds.append(("C", dict(ctrl)))
        s_clk = clk
        cmds.append(("S", None)); clk += 1
        cmds.append(("I", 1)); clk += 1
        cmds.append(("P", (1, b))); pk = [dict(n=1, bundle=b, c0=clk)]; clk += 1
        cmds.append(("I", D_L1)); clk += D_L1
        sweeps.append(dict(strobe=s_clk, ctrl=dict(ctrl), packets=pk))
        tgt = M.MG_FLOOR if ctrl["soft"] else M.s32(ctrl["mgt"])
        mg = O.step_toward(mg, tgt, ctrl["mgr"])
        i += 1
        if n_fade is None and mg == target:
            n_fade = i
        if n_floor is None and mg == M.MG_FLOOR:
            n_floor = i
        if n_floor is not None and i >= n_floor + 4:
            break
    cmds.append(("C", dict(ctrl))); cmds.append(("S", None)); final_strobe = clk; clk += 1
    cmds.append(("I", 40))
    return cmds, sweeps, final_strobe, n_fade, n_floor, target


def cmd_module(a):
    rnd = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    if a.what == "mgfade":
        cmds, sweeps, final_strobe, n_fade, n_floor, target = mgfade_schedule(a)
    else:
        cmds, sweeps, final_strobe = module_schedule(a, rnd)
    bins, banks, over = module_expect(sweeps, final_strobe)
    fcmd = os.path.join(a.out, "module_cmd.txt")
    with open(fcmd, "w") as f:
        for op, arg in cmds:
            if op == "C":
                f.write(f"C {arg['dip_g']} {arg['g_ctrl']:x} {arg['soft']} {arg['err']} "
                        f"{arg['mgt'] & 0xFFFFFFFF:08X} {arg['mgr'] & 0xFFFFFFFF:08X}\n")
            elif op == "S":
                f.write("S\n")
            elif op == "I":
                f.write(f"I {arg}\n")
            else:
                n, b = arg
                f.write(f"P {n} " + " ".join(f"{w & 0xFFFFFFFF:08X}" for w in b) + "\n")
        f.write("E\n")
    fbin = os.path.join(a.out, "module_bins_exp.txt")
    with open(fbin, "w") as f:
        for ph, av, s, pr in bins:
            f.write(f"{ph:08X} {av:08X} {s & ((1 << 41) - 1):011X} {pr & ((1 << 64) - 1):016X}\n")
    fbank = os.path.join(a.out, "module_banks_exp.txt")
    with open(fbank, "w") as f:
        for l, r, clip, mg, sc, ins in banks:
            iv, ip, iL, ia = (1, *ins) if ins else (0, 0, 0, 0)
            f.write(f"{l & 0xFFFFFF:06X} {r & 0xFFFFFF:06X} {clip:x} {mg & 0xFFFFFFFF:08X} {sc:03X} "
                    f"{iv:x} {ip:08X} {iL & ((1 << 54) - 1):014X} {ia:08X}\n")
    vvp = compile_tb("wpms_l1_tb", ["wpms_l1_tb.v", "wpms_l1_module.v", "wpms_l1_sin.v", "wpms_l1_exp2.v",
                                    "wpms_output_stage.v"], a.out, a.rtl,
                     extra=[f"-Pwpms_l1_tb.EXP2_HEX=\"{rtl_file('wpms_exp2_table.hex', a.rtl)}\""])
    log = os.path.join(a.out, "module_sim.log")
    r = run(["vvp", "-n", vvp, f"+cmd={fcmd}", f"+bins={fbin}", f"+banks={fbank}",
             f"+nbins={len(bins)}", f"+nbanks={len(banks)}", f"+overrun={int(over)}"], log)
    text = r.stdout
    summ = [l for l in text.splitlines() if l.startswith(("TB", "MISMATCH", "  "))]
    ok = r.returncode == 0 and "TB: PASS" in text
    if a.what == "mgfade":
        lv = [b[0] for b in banks]
        zero_at = next((k for k in range(1, len(lv)) if lv[k] == 0 and lv[k - 1] != 0), None)
        rep = [f"cosim_l1 mgfade — evidence class RTL-SIM (Icarus): MG slew and soft mute (Ch.4 §4.4.1, §4.4.5)",
               f"  MG 0 -> -60 dB (target {target}) at 13,933 per sample: reached at strobe {n_fade} = "
               f"{n_fade / 48000:.4f} s at 48 kHz (CH4-MG: 1.0 s); the RTL's MG equals the model's at every strobe",
               f"  soft mute: MG -> the floor (-32) reached at strobe {n_floor}; the last non-zero sample "
               f"{lv[zero_at - 1] if zero_at else '-'} LSB (a sweep played just above the floor), then exact zero from "
               f"sample {zero_at} (the first sweep played at the floor, C4-D6)",
               f"  {len(sweeps)} sweeps, {len(bins)} bins, {len(banks)} samples"]
        rep += ["  " + l for l in summ[:20]]
        ok = ok and n_fade is not None and abs(n_fade / 48000 - 1.0) < 0.01 and zero_at is not None
        rep.append(f"cosim_l1 mgfade: {'PASS' if ok else 'FAIL'}")
        return ok, rep
    npk = sum(len(s["packets"]) for s in sweeps)
    a0 = sum(1 for b in bins if b[1] == 0); a1 = sum(1 for b in bins if b[1] == (1 << 31) - 1)
    clipped = sum(1 for b in banks if b[2]); zero = sum(1 for b in banks if b[0] == 0 and b[1] == 0)
    rep = [f"cosim_l1 module — evidence class RTL-SIM (Icarus), seed {a.seed}",
           f"  {len(sweeps)} sweeps, {npk} packets, {len(bins)} bins (a = 0: {a0}; a clamped at 1: {a1}; "
           f"in between: {len(bins) - a0 - a1}); controls: G, G override, MG target/rate, soft mute, the error "
           f"silence; {len(banks)} samples ({zero} zero, {clipped} with the sticky clip set); one deliberate "
           f"overrun: {over}"]
    rep += ["  " + l for l in summ[:40]]
    rep.append(f"cosim_l1 module: {'PASS' if ok else 'FAIL'}")
    return ok, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["units", "module", "mgfade"])
    ap.add_argument("--n", type=int, default=1000000)
    ap.add_argument("--sweeps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(L1, "build", "cosim_l1"))
    ap.add_argument("--rtl", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    ok, rep = (cmd_units if a.what == "units" else cmd_module)(a)
    text = "\n".join(rep) + "\n"
    sys.stdout.write(text)
    if a.report:
        open(a.report, "w").write(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
