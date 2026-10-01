#!/usr/bin/env python3
# ============================================================================
# cosim_synth.py — Phase 4 system-level cosimulation of hw/l1/wpms_synth_top.v
# (Core RH031p + Formation + sequencer + L1 + output stage + strobe sync + I2S).
#
#   python3 cosim_synth.py oracle --budget 50|100 [--samples N] [--seeds a,b,c]
#       The sweep oracle's GO traffic (sweep_sim.py via sweep_dump.py, unchanged),
#       strobe given by the bench after each sweep and the L1 pipeline are over
#       (as Phase 3). Checked: every latched bundle, N, K, stay_value (the Phase
#       3 checks, reused), and every output sample (bank L, R, clip, MG) against
#       hw/tools/l1_model.py computed from the ORACLE's bundles over the
#       customer's oracle; each sweep's length and SWEEP_CLOCKS against T_min.
#   python3 cosim_synth.py grid --budget 50|100 --case origin|origin_literal|gauss|glide|full8
#       The real 48 kHz grid: the strobe from the I2S master through the
#       synchronizer. The page is modelled by sweep_sim.Reference (the customer's
#       semantics, unchanged). Checked: every output sample against the model,
#       the I2S wire decoded against the words the master captured and those
#       against the bank, the strobe interval, the latency to the wire, the
#       customer's end-to-end numbers (test-origin peak, 927 audible bins).
#   common: --out DIR, --report FILE, --rtl DIR (files there replace hw/l1's and
#           hw/l2's: mutant runs)
#
# Evidence class: RTL-SIM (Icarus Verilog -g2012). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF Phase 4).
# 002 2026-09-30       Claude Code   Fix : reference_packets took N after the Reference had applied the
#                                          strobe's GO: a GO changing N of a block that plays in that very
#                                          sweep would have been modelled with the new N (latent: no Phase 4
#                                          case changes N of a playing block; found by Phase 5's random case).
# ============================================================================
import argparse, json, math, os, random, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import l1_model as M                     # noqa: E402
import cosim_sweep as CS                 # noqa: E402  (Phase 3: stimulus and bundle analysis)
O = M.O
HW = CS.HW
L1D = os.path.join(HW, "l1")
L2D = CS.L2
GOLD = os.path.normpath(os.path.join(HW, "..", "tools"))
sys.path.insert(0, GOLD)
import pfasm_tools_w as T                # noqa: E402  (golden, unchanged)
import sweep_sim as SS                   # noqa: E402  (golden, unchanged)

BUDGETS = {50: dict(nmax=1008, tmin=1041, half=10.0), 100: dict(nmax=2048, tmin=2083, half=5.0)}
RTLDIRS = []
MCLK_NS = 1e3 / 12.288
RESEED_RT = 0x9FFF | 1 << 16


def src(name, d):
    for x in RTLDIRS:
        if os.path.exists(os.path.join(x, name)):
            return os.path.join(x, name)
    return os.path.join(d, name)


def build(out, budget, tag, n_min=32):
    b = BUDGETS[budget]
    hexf, _ = CS.assemble(os.path.join(L2D, "scores", "wpms_r1d.score"), out, "wpms_r1d")
    exe = os.path.join(out, f"synth_{tag}.vvp")
    inc = [f"-I{RTLDIRS[0]}"] if RTLDIRS else []
    cmd = ["iverilog", "-g2012", *inc, f"-I{L1D}", f"-I{L2D}", "-o", exe, "-s", "wpms_synth_tb",
           f"-Pwpms_synth_tb.SCORE=\"{hexf}\"", f"-Pwpms_synth_tb.EXP2_HEX=\"{src('wpms_exp2_table.hex', L1D)}\"",
           f"-Pwpms_synth_tb.NMAX={b['nmax']}", f"-Pwpms_synth_tb.N_MIN={n_min}", f"-Pwpms_synth_tb.SYS_HALF={b['half']}",
           os.path.join(L1D, "wpms_synth_tb.v"), src("wpms_synth_top.v", L1D), src("wpms_l1_module.v", L1D),
           src("wpms_l1_sin.v", L1D), src("wpms_l1_exp2.v", L1D), src("wpms_output_stage.v", L1D),
           src("wpms_strobe_sync.v", L1D), src("wpms_i2s_master.v", L1D), src("wpms_l2_top.v", L2D),
           src("wpms_formation.v", L2D), src("wpms_sequencer.v", L2D),
           os.path.join(HW, "core", "ptsg_core_rh031p.v"), CS.IMEM]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines()
           if l.strip() and "sensitive to all" not in l and "coerced to inout" not in l]
    if r.returncode or bad:
        raise SystemExit("compile failed:\n" + "\n".join(bad[:30]))
    return exe


def simulate(exe, out, tag, stim, forced):
    sp, rp = os.path.join(out, f"stim_{tag}.txt"), os.path.join(out, f"res_{tag}.txt")
    open(sp, "w").write(stim)
    args = ["vvp", "-n", exe, f"+stim={sp}", f"+out={rp}"] + (["+forcestrobe"] if forced else [])
    r = subprocess.run(args, capture_output=True, text=True)
    warn = [l for l in (r.stdout + r.stderr).splitlines() if "WARNING" in l or "ERROR" in l]
    return parse(rp), warn


def parse(path):
    ev = []
    for line in open(path):
        f = line.split()
        if not f:
            continue
        k = f[0]
        if k == "L": ev.append(("L", int(f[1]), int(f[2]), [int(x, 16) for x in f[3:11]]))
        elif k == "P": ev.append(("P", int(f[1]), int(f[2]), int(f[3])))
        elif k == "A": ev.append(("A", int(f[1]), int(f[2]), int(f[3], 16), int(f[4])))
        elif k == "V": ev.append(("V", int(f[1]), int(f[2], 16), int(f[3])))
        elif k == "B": ev.append(("B", int(f[1]), int(f[2], 16)))
        elif k == "F": ev.append(("F", int(f[1]), int(f[2]), int(f[3], 16)))
        elif k in ("H", "Q"): ev.append((k, int(f[1]), int(f[2], 16)))
        elif k == "O": ev.append(("O", int(f[1]), s24(int(f[2], 16)), s24(int(f[3], 16)), int(f[4]),
                                  M.s32(int(f[5], 16)), int(f[6]), int(f[7])))
        elif k == "Z": ev.append(("Z", int(f[1]), int(f[2]), int(f[3])))
        elif k == "I": ev.append(("I", float(f[1])))
        elif k == "J": ev.append(("J", float(f[1]), int(f[2]), s24(int(f[3], 16)), s24(int(f[4], 16)),
                                  s24(int(f[5], 16)), s24(int(f[6], 16))))
        elif k == "Y": ev.append(("Y", *[int(x) for x in f[1:6]]))
        else: ev.append((k, int(f[1])))                 # S D U C M T
    return ev


def s24(v):
    return v - (1 << 24) if v >> 23 else v


def ctrl_lines(g, g_ctrl=0, mgt=0, mgr=M.MG_RATE_DEFAULT, soft=0):
    return [f"D {g:x} {g_ctrl:x}", f"M {mgt & 0xFFFFFFFF:x} {mgr & 0xFFFFFFFF:x} {soft:x}"]


def model_banks(samples_packets, g, g_ctrl=0, mgt=0, mgr=M.MG_RATE_DEFAULT, errors_from=None):
    """samples_packets[i] = [(bundle, N), ...] played in sweep i (started by strobe i).
    Returns the expected O events for strobes 0 .. len (strobe i closes sweep i-1)."""
    out = M.Output(g=(g_ctrl & 15) if g_ctrl & 16 else 4 * g, mg_target=mgt, mg_rate=mgr)
    exp = []
    mg_open = None
    for i in range(len(samples_packets) + 1):
        if i == 0:
            al = ar = 0
        else:
            al, ar = M.sweep_acc(samples_packets[i - 1], mg_open)
        mg_closed = out.mg
        err = errors_from is not None and i >= errors_from
        bank = out.strobe(al, ar, mg_closed, error=err)
        exp.append((bank[0], bank[1], out.clip[0] | out.clip[1] << 1, out.mg))
        mg_open = out.mg
    return exp


def _model_worker(args):
    return model_banks(*args)


def compare_banks(obs, exp, label):
    probs = []
    if len(obs) != len(exp):
        probs.append(f"{label}: {len(obs)} samples written, {len(exp)} expected")
    bad = 0
    for i, (o, e) in enumerate(zip(obs, exp)):
        got = (o[2], o[3], o[4], o[5])
        if got != e:
            bad += 1
            if bad <= 5:
                probs.append(f"{label}: sample {i - 1} (strobe {i}): RTL L {o[2]} R {o[3]} clip {o[4]} MG {o[5]} / "
                             f"model L {e[0]} R {e[1]} clip {e[2]} MG {e[3]}")
    if bad > 5:
        probs.append(f"{label}: {bad} samples differ in all")
    return probs, bad


# ---------------------------------------------------------------------------
# mode A: the sweep oracle's GO traffic
# ---------------------------------------------------------------------------
def oracle_seed(args):
    seed, budget, samples, out, rtl, g, g_ctrl, mgt = args
    RTLDIRS[:] = rtl
    b = BUDGETS[budget]
    dp = os.path.join(out, f"dump_{seed}.json")
    subprocess.run([sys.executable, os.path.join(HERE, "sweep_dump.py"), dp, "--oracle", CS.ORACLE,
                    "--samples", str(samples), "--seed", str(seed), "--nmax", str(b["nmax"])],
                   capture_output=True, text=True)
    dump = json.load(open(dp))
    rng = random.Random(seed)
    L = ["R 4"] + ctrl_lines(g, g_ctrl, mgt)
    sh = json.loads(json.dumps(CS.SWITCH0))
    for s in dump["samples"]:
        L.append("W")
        for a, d in CS.switch_writes(sh, s["switch"]):
            L.append(f"X {a:x} {d & 0xFFFFFFFF:x}")
        sh = s["switch"]
        n = rng.randrange(4)
        if n:
            L.append(f"N {n:x}")
        L.append("S")
    L += ["W", "S", "W", "N 10", "E"]                  # the last strobe closes the last sweep
    exe = os.path.join(out, "synth_oracle.vvp")
    ev, warn = simulate(exe, out, f"s{seed}", "\n".join(L) + "\n", forced=True)
    # the Phase 3 checks (bundles, N, K, the pin, timing): the last strobe closes only
    evA = [e for e in ev if e[0] != "S"] and ev
    strobes = [e for e in ev if e[0] == "S"]
    trimmed = ev[:ev.index(strobes[-1])] if strobes else ev
    probs, st = CS.analyse(dump, trimmed, b["tmin"], b["nmax"])
    probs += [f"simulator: {w}" for w in warn]
    # the output samples
    packets = [[(p["bundle"], p["N"]) for p in s["packets"]] for s in dump["samples"]]
    exp = model_banks(packets, g, g_ctrl, mgt)
    obs = [e for e in ev if e[0] == "O"]
    p2, bad = compare_banks(obs, exp, f"seed {seed}")
    probs += p2
    sc = [o[6] for o in obs]
    y = [e for e in ev if e[0] == "Y"]
    over = y[0][5] if y else None
    if over:
        probs.append(f"seed {seed}: overrun flag set")
    late = [x for x in sc if x > b["tmin"] - 1]
    if late:
        probs.append(f"seed {seed}: {len(late)} sweeps with the last product at or after T_min")
    nz = sum(1 for o in obs if o[2] or o[3])
    clipped = sum(1 for o in obs if abs(o[2]) == (1 << 23) - 1 or o[2] == -(1 << 23) or abs(o[3]) == (1 << 23) - 1
                  or o[3] == -(1 << 23))
    ol = [l for l in dump["provenance"]["oracle_output"] if "mismatches" in l]
    return dict(seed=seed, probs=probs, st=st, nsamples=len(obs), bad=bad, sc_max=max(sc) if sc else 0,
                nonzero=nz, clipped=clipped, oracle=ol[0].strip() if ol else "?", g=g, g_ctrl=g_ctrl, mgt=mgt,
                mg_end=obs[-1][5] if obs else None)


def cmd_oracle(a):
    b = BUDGETS[a.budget]
    out = os.path.join(a.out, f"oracle_{a.budget}")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    build(out, a.budget, "oracle")
    seeds = [int(s) for s in a.seeds.split(",") if s]
    # controls per seed: G 12; a G override; an MG glide toward -6 dB
    ctl = [(3, 0, 0), (3, 16 | 10, 0), (2, 0, -round(1.0 * 2 ** 26))]
    jobs = [(s, a.budget, a.samples, out, list(RTLDIRS)) + ctl[i % len(ctl)] for i, s in enumerate(seeds)]
    with ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1)) as ex:
        res = list(ex.map(oracle_seed, jobs))
    L = [f"cosim_synth oracle: wpms_synth_top vs sweep_sim.py (bundles) and l1_model over the customer's oracle "
         f"(samples) — evidence class RTL-SIM; NMAX {b['nmax']}, T_min {b['tmin']} ({a.budget} MHz budget)"]
    allp = []
    tot = dict(packets=0, bins=0, sweeps=0, full=0, samples=0)
    agg = dict(wake=[], g=[], sweep_len=[], full_len=[])
    scmax = 0
    for r in res:
        st = r["st"]
        L.append(f"  seed {r['seed']} (G {'override ' + str(r['g_ctrl'] & 15) if r['g_ctrl'] & 16 else 4 * r['g']}, "
                 f"MG target {r['mgt'] / 2 ** 26:+.2f} log2): {st['sweeps']} sweeps, {st['packets']} packets, {st['bins']} bins, "
                 f"{st['full']} full-load; {r['nsamples']} output samples, {r['bad']} differ from the model "
                 f"({r['nonzero']} non-zero, {r['clipped']} at full scale); SWEEP_CLOCKS max {r['sc_max']}; "
                 f"oracle: {r['oracle']}; {'PASS' if not r['probs'] else 'FAIL'}")
        for k in ("packets", "bins", "sweeps", "full"):
            tot[k] += st[k]
        tot["samples"] += r["nsamples"]
        for k in agg:
            agg[k] += st[k]
        scmax = max(scmax, r["sc_max"])
        allp += [f"seed {r['seed']}: {x}" for x in r["probs"]]
    L.append(f"  total: {tot['sweeps']} sweeps, {tot['packets']} packets, {tot['bins']} bins, {tot['full']} full-load; "
             f"{tot['samples']} output samples compared")
    L.append(f"  T_wake {CS.rng_str(agg['wake'])}; g {CS.rng_str(agg['g'])}; sweep length (strobe -> first SLEEP clock) "
             f"{CS.rng_str(agg['sweep_len'])}, full-load {CS.rng_str(agg['full_len'])} of T_min {b['tmin']}")
    L.append(f"  SWEEP_CLOCKS (strobe -> last product in the accumulator), worst: {scmax} of T_min {b['tmin']} "
             f"({b['tmin'] - 1 - scmax} spare)")
    for x in allp[:30]:
        L.append("  FAIL " + x)
    L.append(f"cosim_synth oracle: {'PASS' if not allp else 'FAIL'} ({time.time() - t0:.0f} s)")
    return not allp, L


# ---------------------------------------------------------------------------
# mode B: the real grid
# ---------------------------------------------------------------------------
def dirichlet_block(N):
    v = [0] * 16
    v[0] = N
    v[0xA] = 89_120_571                      # OM0 (Ch.3 §3.10)
    v[0xB] = 350                             # OMD1
    v[0x2] = -2_948_988                      # LP = log2 0.97 (Q6.26)
    v[0x9] = -2_948_988                      # LPT = LP (Ch.5 §5.8)
    return v


def gauss_block(N, consistent):
    v = dirichlet_block(N)
    ls0, lad1, lad2, lp = O.gaussian_slots(N, 1e-4, A0=0.97, consistent=consistent)
    v[0x2] = v[0x9] = lp
    v[0x3], v[0x4], v[0xF] = lad1, lad2, ls0
    return v


def block_writes(b, vals, rt=3, mask=RESEED_RT):
    L = [f"X {b * 16 + i:x} {vals[i] & 0xFFFFFFFF:x}" for i in range(16) if i not in (13, 14)]
    L.append(f"X {0x80 + b:x} {rt:x}")
    L.append(f"X {0x88 + b:x} {mask | 1 << 30:x}")
    return L


def sweep_writes(order):
    w = len(order)
    for k, b in enumerate(order):
        w |= b << (4 + 3 * k)
    return [f"X 90 {w:x}", "X 91 40000000"], w


def grid_case(case, budget):
    """Returns (stim lines, go_at: {strobe index: go dict}, n_samples, g, notes)."""
    b = BUDGETS[budget]
    N = b["nmax"] if case != "origin_literal" else 2048
    if case in ("origin", "origin_literal"):
        blocks = {0: dirichlet_block(N)}
        n = 120
    elif case == "gauss":
        blocks = {0: gauss_block(2048, False), 1: gauss_block(2048, True)}
        n = 8
    elif case == "full8":                     # the worst sweep: 8 packets, sum of N = NMAX exactly
        rnd = random.Random(8)
        blocks = {}
        for bk in range(8):
            v = dirichlet_block(b["nmax"] // 8)
            v[0xA] = rnd.randrange(1 << 32); v[0xB] = rnd.randrange(1 << 20); v[0xC] = rnd.randrange(1 << 12)
            v[0x6], v[0x7], v[0x8] = (rnd.randrange(1 << 32) for _ in range(3))
            ls0, lad1, lad2, lp = O.gaussian_slots(b["nmax"] // 8, 2e-4, A0=0.9, consistent=True)
            v[0x2] = v[0x9] = lp - (3 << 26); v[0x3], v[0x4], v[0xF] = lad1, lad2, ls0
            blocks[bk] = v
        n = 40
    else:                                     # glide: level glide + a pitch retune in flight
        v = dirichlet_block(min(N, 700))
        v[0x6], v[0x7], v[0x8] = 0x12345678, 1 << 20, 1 << 21          # Schroeder-like phase shape
        v[0x2] = -(6 << 26); v[0x9] = -(1 << 26); v[0x5] = 1 << 22       # LP -> LPT at LE0 per sample
        blocks = {0: v}
        n = 40
    L = ["R 4"] + ctrl_lines(3)
    go = {}
    order = list(range(8)) if case == "full8" else [0]
    rts = {bk: (1, 2, 3)[bk % 3] if case == "full8" else 3 for bk in blocks}
    for bk, vals in blocks.items():
        if case == "gauss" and bk == 1:
            continue
        L += block_writes(bk, vals, rt=rts[bk])
    sw, w = sweep_writes(order)
    L += sw
    go[0] = dict(blocks={bk: (RESEED_RT, list(vals), rts[bk]) for bk, vals in blocks.items()
                         if not (case == "gauss" and bk == 1)}, sweep=w)
    L += ["G 1", "K"] + [f"X {0x88 + bk:x} 0" for bk in go[0]["blocks"]] + ["X 91 0"]   # taken at strobe 0; disarm
    strobes = 1
    if case == "gauss":
        # the second Gaussian replaces the first after 3 sweeps (block 1, sweep [1])
        L += ["G 3", "K"] + block_writes(1, blocks[1])
        sw, w = sweep_writes([1])
        L += sw + ["G 1", "K", "X 89 0", "X 91 0"]
        go[4] = dict(blocks={1: (RESEED_RT, list(blocks[1]), 3)}, sweep=w)
        strobes = 5
    if case == "glide":
        # a pitch retune (+100 cents) armed in the window after BCP, taken by the next strobe
        L += ["G 9", "K", f"X a {round(89_120_571 * 2 ** (1 / 12)) & 0xFFFFFFFF:x}", f"X 88 {0x1C00 | 1 << 30:x}"]
        L += ["G 1", "K", "X 88 0"]
        vals = list(blocks[0]); vals[0xA] = round(89_120_571 * 2 ** (1 / 12))
        go[10] = dict(blocks={0: (0x1C00, vals, 3)}, sweep=None)
        strobes = 11
    L += [f"G {n - strobes:x}", "N 40", "E"]
    return L, go, n, 3


def reference_packets(go, n_strobes, step):
    """sweep_sim.Reference (the customer's semantics, unchanged): per sweep, the
    packets it plays [(bundle, N)]."""
    ref = SS.Reference(step)
    out = []
    for i in range(n_strobes):
        g = go.get(i)
        n_played = [ref.blk[b][0] for b in range(8)]          # N as this sweep plays it (RH002)
        obs = ref.sample(dict(blocks=g["blocks"], sweep=g["sweep"]) if g else None)
        out.append([(list(bun), n_played[b]) for b, bun in obs])
    return out


def cmd_grid(a):
    b = BUDGETS[a.budget]
    out = os.path.join(a.out, f"grid_{a.budget}_{a.case}")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    exe = build(out, a.budget, "grid")
    L, go, n, g = grid_case(a.case, a.budget)
    ev, warn = simulate(exe, out, a.case, "\n".join(L) + "\n", forced=False)
    probs = [f"simulator: {w}" for w in warn]
    step, _ = SS.load_step_toward(CS.ORACLE)
    strobes = [e for e in ev if e[0] == "S"]
    obs = [e for e in ev if e[0] == "O"]
    ns = len(strobes)
    rep = [f"cosim_synth grid/{a.case}: wpms_synth_top on the 48 kHz grid (I2S master -> synchronizer) — evidence "
           f"class RTL-SIM; NMAX {b['nmax']}, T_min {b['tmin']} ({a.budget} MHz budget); {ns} strobes"]
    f = [e for e in ev if e[0] == "F"]
    if a.case == "origin_literal":
        # the test origin as written (N = 2,048) against NMAX = 1,008: refused at prefetch
        # the sweep word lists a block with N = 2,048 > NMAX: BCP refuses it (EW5, sum of N > NMAX)
        # before any prefetch could (EW2); L1 silent at once; the Core halts at the trap
        ok_err = bool(f) and CS.ERRN.get(f[0][2]) == "EW5"
        after = [o for o in obs if o[1] > f[0][1] and (o[2] or o[3])] if f else obs
        h = [e for e in ev if e[0] == "H"]
        rep.append(f"  error_flag: {CS.ERRN.get(f[0][2], '?') if f else 'none'}"
                   f"{' at clock ' + str(f[0][1]) if f else ''}; non-zero samples after it: {len(after)}; "
                   f"Core HALT: {'at 0x%03X, %d clocks after the flag' % (h[0][2], h[0][1] - f[0][1]) if h and f else 'no'}")
        if not ok_err or after or not h:
            probs.append("the literal test origin was not refused with EW5, silence and the Core's HALT")
    else:
        if f:
            probs.append(f"unexpected Formation error {f[0]}")
        pk = reference_packets(go, ns, step)
        exp = model_banks(pk[:ns - 1], g)
        p2, bad = compare_banks(obs[:ns], exp[:ns], a.case)
        probs += p2
        rep.append(f"  output samples: {min(len(obs), ns)} compared with the model (sweep_sim.Reference pages -> "
                   f"l1_model), {bad} differ")
        # bundles latched vs the Reference's
        lat = [e for e in ev if e[0] == "L"]
        want = [bun for sw in pk[:ns - 1] for bun, _ in sw]            # every sweep that a strobe closed
        got = [e[3] for e in lat]
        same = got[:len(want)] == want
        if not same:
            probs.append(f"latched bundles differ from the Reference ({len(got)} latched, {len(want)} expected)")
        rep.append(f"  bundles latched in the {ns - 1} closed sweeps: {min(len(got), len(want))} of {len(want)}, "
                   f"equal to sweep_sim.Reference's: {same}")
    # the wire
    J = [e for e in ev if e[0] == "J"]
    wire_bad = sum(1 for j in J if (j[3], j[4]) != (j[5], j[6]))
    cdc_bad = 0
    for j in J:
        prior = [o for o in obs if o[1] < j[2]]
        want = (prior[-1][2], prior[-1][3]) if prior else (0, 0)
        if (j[5], j[6]) != want:
            cdc_bad += 1
    if wire_bad or cdc_bad:
        probs.append(f"I2S: {wire_bad} frames decoded differently from the words captured; {cdc_bad} captures "
                     f"differ from the bank")
    rep.append(f"  I2S wire: {len(J)} frames decoded by a receiver (SCLK rising edge, Philips); words equal to the "
               f"master's capture: {len(J) - wire_bad}/{len(J)}; captures equal to the bank written before F: "
               f"{len(J) - cdc_bad}/{len(J)}")
    # latency: strobe toggle S_m -> left MSB of sample m on the wire (F_{m+1} + 1 SCLK)
    I = [e[1] for e in ev if e[0] == "I"]
    Fs = [j[1] for j in J]
    lat_ns = []
    for i in range(len(I) - 1):
        nxt = [t for t in Fs if t > I[i + 1]]
        if nxt:
            lat_ns.append(nxt[0] + 4 * MCLK_NS - I[i])
    if lat_ns:
        lo, hi = min(lat_ns), max(lat_ns)
        rep.append(f"  latency S_m -> left MSB of that sweep's sample on the wire: {lo / 1000:.3f} .. {hi / 1000:.3f} us "
                   f"= {lo / (256 * MCLK_NS):.4f} periods (Ch.4 §4.8: 21.48 us = 1.031)")
        if abs(lo - 264 * MCLK_NS) > 1 or abs(hi - 264 * MCLK_NS) > 1:
            probs.append(f"latency {lo:.1f}..{hi:.1f} ns, expected {264 * MCLK_NS:.1f}")
    # the Core's side of the budget: strobe -> the first clock back in a SLEEP wait (U), per sweep
    U = [e[1] for e in ev if e[0] == "U"]
    lens = []
    for s_ in strobes:
        nxt = [u for u in U if u > s_[1]]
        if nxt:
            lens.append(nxt[0] - s_[1])
    if lens:
        rep.append(f"  Core sweep length (strobe -> first SLEEP clock): {min(lens)} .. {max(lens)} of T_min {b['tmin']}")
        if max(lens) > b["tmin"]:
            probs.append(f"a Core sweep of {max(lens)} clocks > T_min")
    y = [e for e in ev if e[0] == "Y"]
    if y:
        _, iv, mn, mx, scm, ov = y[0]
        want_iv = {50: (1041, 1042), 100: (2083, 2084)}[a.budget]
        rep.append(f"  strobe interval (clk_sys clocks): min {mn}, max {mx} (expected {want_iv[0]} / {want_iv[1]}); "
                   f"SWEEP_CLOCKS max {scm} (< T_min {b['tmin']}); overrun {ov}")
        if (mn, mx) != want_iv and not (mn in want_iv and mx in want_iv):
            probs.append(f"strobe interval {mn}..{mx}")
        if ov or scm > b["tmin"] - 1:
            probs.append(f"SWEEP_CLOCKS {scm} / overrun {ov}")
    # end-to-end numbers
    if a.case == "origin":
        pcm = [abs(o[2]) for o in obs]
        pk_ = max(pcm) if pcm else 0
        db = 20 * math.log10(pk_ / 2 ** 23) if pk_ else float("-inf")
        rep.append(f"  test origin (N = {BUDGETS[a.budget]['nmax']}), G = 12: PCM peak over {len(obs)} samples "
                   f"{pk_} = {db:.2f} dBFS (Ch.3 §3.6.4 / CH3-ORIGIN: -6.3 dBFS for N = 2,048)")
    if a.case == "gauss":
        Z = [e for e in ev if e[0] == "Z"]
        full = [z for z in Z if z[2] == 2048]
        nz = sorted(set(z[3] for z in full))
        rep.append(f"  sigma = 71 Gaussian, N = 2,048 (naive and consistent slots, CH3-E2E): bins with a != 0 per "
                   f"packet: {nz} over {len(full)} packets (customer: 927)")
        if nz != [927]:
            probs.append(f"audible bins {nz}, expected 927")
    for x in probs[:20]:
        rep.append("  FAIL " + x)
    rep.append(f"cosim_synth grid/{a.case}: {'PASS' if not probs else 'FAIL'} ({time.time() - t0:.0f} s)")
    return not probs, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["oracle", "grid"])
    ap.add_argument("--budget", type=int, default=50, choices=[50, 100])
    ap.add_argument("--samples", type=int, default=3000)
    ap.add_argument("--seeds", default="2026,7,42")
    ap.add_argument("--case", default="origin", choices=["origin", "origin_literal", "gauss", "glide", "full8"])
    ap.add_argument("--out", default=os.path.join(L1D, "build", "cosim_synth"))
    ap.add_argument("--report", default="")
    ap.add_argument("--rtl", default="")
    a = ap.parse_args()
    if a.rtl:
        RTLDIRS.insert(0, a.rtl)
    ok, rep = (cmd_oracle if a.what == "oracle" else cmd_grid)(a)
    text = "\n".join(rep) + "\n"
    sys.stdout.write(text)
    if a.report:
        open(a.report, "w").write(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
