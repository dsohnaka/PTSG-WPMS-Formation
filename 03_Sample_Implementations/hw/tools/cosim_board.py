#!/usr/bin/env python3
# ============================================================================
# cosim_board.py — Phase 6 board-level RTL-SIM: the DE10-nano top
# (hw/de10_nano/DE10_Nano_wpms_top.v) with its PLLs and ISSP instances in
# their SIM branches, on the board-level bench (hw/de10_nano/sim/
# DE10_Nano_wpms_tb.v: the three oscillators, KEY/SW, an ADV7513 on the I2C
# bus, an I2S receiver, the video timing check). The host's steps are those
# the Tcl plays on the board (hw/tools/host/wpms_phase6_steps.py), driven
# through the ISSP bit protocol. The tap bus is dumped as SignalTap holds it
# and measured by phase6_evidence.py, the same code that will read the
# SignalTap exports: what this run observes is what the silicon must show.
#
#   python3 cosim_board.py --case CASE|all [--budget 50|100|both] [--out DIR]
#                          [--evidence DIR] [--jobs N]
#
# Cases (SILICON_BRIEF Phase 6 evidence items in brackets):
#   origin    reset; the ROM's test origin (block 0, N = NMAX): full load  [2, 3, 4, 5]
#   first_go  the origin, then one GO: a C-major triad on blocks 1-3       [1, 7, 8]
#   full8     one GO: eight blocks, the full mask, sum of N = NMAX         [1, 2, 3, 4, 5, 7]
#   ew6       LE0 = -1 written by the host                                 [6]
#   ew2 ew3 ew4 ew5   the injection images of gen_inject_scores.py, reset  [6]
#   pcm       first_go held for 1,100 sweeps, no VCD: the PCM from the
#             bench's B lines, its spectrum beside the model's             [8]
# The expected values are the brief's bounds, in EXPECT below, written before
# any run. Each run's observations go to DIR/<case>_<budget>.json: these are
# the RTL-SIM values each SignalTap capture is compared with. Each run is also
# cut as the bring-up recipe's SignalTap capture of that case (TRIGGERS:
# trigger, depth 4,096, position, storage qualifier), written in the layout of
# a SignalTap export (DIR/expected_<case>_<budget>.vcd.gz), read back and
# measured by phase6_evidence.py: the silicon path, dry-run on RTL-SIM data.
# Evidence class: RTL-SIM (Icarus Verilog -g2012). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "host"))
import cosim_sweep as CS                 # noqa: E402  (paths of the Core's imem and the oracle)
import phase6_evidence as EV             # noqa: E402
import wpms_phase6_steps as P6           # noqa: E402  (outside WPMS: the host's steps)

HW = CS.HW
DE = os.path.join(HW, "de10_nano")
BUDGETS = {50: dict(nmax=1008, tmin=1041), 100: dict(nmax=2048, tmin=2083)}

# ---- expected, from the brief (Phase 6 evidence items), before any run ------------------------------
EXPECT = dict(
    strobe_interval="each interval T_min or T_min + 1 (f_sys / 48 kHz: 1,041.7 or 2,083.3 clocks)",
    g=0,                    # item 1: no clock between the packets of a sweep
    t_wake_max=4,           # item 2: strobe -> first packet_start <= 4 (nominal 2)
    floor_max=32,           # item 3: the packet window + 2 <= N_MIN = 32
    bcp_max=10,             # item 4: the BCP word -> inbox_taken, full take-set, <= 10
    length_max="T_min",     # item 5: a full-load sweep, housekeeping included, fits in T_min
    error="the right code; no packet, no bin, every bank zero after it; the Core halts",   # item 6
    bundles="every bundle at packet_start equal to the model",                            # item 7
    pcm="every bank equal to the model; the spectrum the model's",                        # item 8
)
CASES = {
    "origin":   dict(score="r1d", error=None, items=[2, 3, 4, 5]),
    "first_go": dict(score="r1d", error=None, items=[1, 7, 8]),
    "full8":    dict(score="r1d", error=None, items=[1, 2, 3, 4, 5, 7]),
    "ew6":      dict(score="r1d", error="EW6", items=[6]),
    "ew2":      dict(score="ew2", error="EW2", items=[6]),
    "ew3":      dict(score="ew3", error="EW3", items=[6]),
    "ew4":      dict(score="ew4", error="EW4", items=[6]),
    "ew5":      dict(score="ew5", error="EW5", items=[6]),
    "pcm":      dict(score="r1d", error=None, items=[8]),
}
PCM_SWEEPS = 1100


def score_files(name, nmax):
    if name == "r1d":
        return os.path.join(HW, "l2", "scores", "wpms_r1d.hex"), os.path.join(HW, "l2", "scores", "wpms_r1d.score")
    tag = f"{name}_{nmax}" if name == "ew5" else name
    return (os.path.join(DE, "inject", f"wpms_r1d_{tag}.hex"), os.path.join(DE, "inject", f"wpms_r1d_{tag}.score"))


def build(out, budget, score):
    b = BUDGETS[budget]
    hexf, _ = score_files(score, b["nmax"])
    exe = os.path.join(out, f"board_{budget}_{score}.vvp")
    files = [os.path.join(DE, "sim", "DE10_Nano_wpms_tb.v"), os.path.join(DE, "sim", "wpms_pll_sim.v"),
             os.path.join(DE, "DE10_Nano_wpms_top.v"), os.path.join(DE, "wpms_pll.v")]
    files += [os.path.join(HW, "switch", f) for f in ("wpms_system.v", "wpms_switch.v", "wpms_host_bridge.v",
                                                      "wpms_issp.v", "wpms_rom.v", "wpms_key_pulse.v")]
    files += [os.path.join(HW, "l1", f) for f in ("wpms_synth_top.v", "wpms_l1_module.v", "wpms_l1_sin.v",
                                                  "wpms_l1_exp2.v", "wpms_output_stage.v", "wpms_strobe_sync.v",
                                                  "wpms_i2s_master.v", "wpms_video_720p.v", "wpms_adv7513_cfg.v")]
    files += [os.path.join(HW, "l2", f) for f in ("wpms_l2_top.v", "wpms_formation.v", "wpms_sequencer.v")]
    files += [os.path.join(HW, "core", "ptsg_core_rh031p.v"), CS.IMEM]
    tb = "DE10_Nano_wpms_tb"
    cmd = ["iverilog", "-g2012", "-Wall", "-I", os.path.join(HW, "l1"), "-I", os.path.join(HW, "l2"),
           "-o", exe, "-s", tb, f"-P{tb}.SYS_MHZ={budget}", f"-P{tb}.SCORE_HEX=\"{hexf}\"",
           f"-P{tb}.EXP2_HEX=\"{os.path.join(HW, 'l1', 'wpms_exp2_table.hex')}\"",
           f"-P{tb}.ROM_HEX=\"{os.path.join(HW, 'switch', 'wpms_rom_origin_%d.hex' % b['nmax'])}\"", *files]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines()
           if l.strip() and "sensitive to all" not in l and "coerced to inout" not in l
           and "timescale for" not in l and "inherited timescale" not in l]
    if r.returncode or bad:
        raise SystemExit("compile failed:\n" + "\n".join(bad[:30]))
    return exe


def stimulus(case, nmax):
    # every run lasts 64 strobes or more: the ADV7513 table (1 MHz I2C in the bench) is written by then
    if case == "origin":
        return ["V 1", "G 40", "Q 9", "Q a", "Q b", "Q 299", "Q 18"]
    if case in ("ew2", "ew3", "ew4", "ew5"):
        return ["V 1", "G 6", "Q 9", "Q a", "Q b", "G 3a"]
    if case == "pcm":
        return ["G 3"] + P6.to_stim(P6.first_go(nmax)) + [f"G {PCM_SWEEPS:x}"]
    st = ["V 1", "G 3"] + P6.to_stim(P6.CASES[case](nmax))
    return st + (["G 30"] if case == "ew6" else [])


# The SignalTap captures of the bring-up recipe (hw/de10_nano/README.md), cut from the bench's VCD:
# (trigger, storage-qualified). Depth 4,096 and SignalTap's "pre trigger position" (12 % of the
# samples before the trigger), as the recipe sets them.
DEPTH, PRE = 4096, 0.12
TRIGGERS = {
    "origin":   ("C1: the first packet_start after reset", False),
    "full8":    ("C2: P becoming 8 (the full take-set lands)", False),
    "first_go": ("C3: P becoming 3 (the triad's sweep), qualified by packet_start | bank_we", True),
    "ew6": ("C4: error_flag rising", False),
    "ew2": ("C5: error_flag rising", False), "ew3": ("C5: error_flag rising", False),
    "ew4": ("C5: error_flag rising", False), "ew5": ("C5: error_flag rising", False),
}


def signaltap_cut(case, ctl, dat):
    """(ctl, dat) as SignalTap holds them for the case's trigger, or None (no trigger in the run)."""
    what, qual = TRIGGERS[case]
    if qual:
        idx = [i for i, c in enumerate(ctl) if c & EV.QUAL]
        ctl, dat = [ctl[i] for i in idx], {k: dat[i] for k, i in enumerate(idx) if i in dat}
    if case == "origin":
        hit = lambda i: ctl[i] & 2                                              # noqa: E731
    elif case in ("full8", "first_go"):
        P = 8 if case == "full8" else 3
        hit = lambda i: EV.fld(ctl[i], "sweep") & 15 == P and EV.fld(ctl[i - 1], "sweep") & 15 != P   # noqa: E731
    else:
        hit = lambda i: (ctl[i] >> 4) & 1 and not (ctl[i - 1] >> 4) & 1        # noqa: E731
    t = next((i for i in range(1, len(ctl)) if hit(i)), None)
    if t is None:
        return None
    a = max(0, t - int(DEPTH * PRE))
    c2 = ctl[a:a + DEPTH]
    return c2, {i - a: v for i, v in dat.items() if a <= i < a + DEPTH}, what, qual


def dry_run(case, budget, d, ctl, dat, steps, score_src):
    """The silicon path on this run's data: the cut written as a SignalTap export, read back by
    phase6_evidence.py, measured and compared with the model, as the board's capture will be."""
    cut = signaltap_cut(case, ctl, dat)
    if cut is None:
        return dict(trigger=TRIGGERS[case][0], found=False)
    c2, d2, what, qual = cut
    vp = os.path.join(d, "expected_signaltap.vcd.gz")
    EV.write_signaltap_vcd(c2, d2, vp, period_ps=20000 if budget == 50 else 10000, with_clock=not qual)
    c3, d3 = EV.read_vcd(vp)
    r3 = EV.measure(c3, d3, budget, score_src)
    e3 = EV.evaluate(r3, c3, d3, budget, steps)
    keep = ("qualified", "g", "t_wake", "window", "floor", "bcp", "bcp_full_take", "full_load_length",
            "bundles", "pcm", "model_from")
    out = {k: e3.get(k) for k in keep}
    out.update(trigger=what, found=True, samples=len(c3), same_samples=(c3 == c2 and d3 == d2),
               errors=[dict(code=e["code"], packets_after=e["packets_after"], bins_after=e["bins_after"],
                            banks_after_nonzero=e["banks_after_nonzero"], halted=e["halted"]) for e in e3["errors"]],
               file=vp)
    return out


def late_capture(budget, ctl, dat, steps, score_src):
    """A capture taken long after reset, as on the board (the GO lands seconds after the reset): the
    run cut from the first sweep that plays the host's GO on, measured with the model started from
    that GO alone (phase6_evidence.py, start_mode "go")."""
    takes, _ = EV.takes_from_log(BUDGETS[budget]["nmax"], steps)
    k0 = max(takes) if takes else None
    if not k0 or k0 < 2:
        return None
    i0 = next((i for i, c in enumerate(ctl) if EV.fld(c, "n") >= k0 + 1), None)
    if i0 is None:
        return None
    c2, d2 = ctl[i0:], {i - i0: v for i, v in dat.items() if i >= i0}
    r2 = EV.measure(c2, d2, budget, score_src)
    e2 = EV.evaluate(r2, c2, d2, budget, steps, start_mode="go")
    return dict(go_strobe=k0, model_from=e2.get("model_from"), bundles=e2.get("bundles"), pcm=e2.get("pcm"),
                problems=e2.get("model_problems"))


def run_one(case, budget, out, exe):
    b = BUDGETS[budget]
    d = os.path.join(out, f"{case}_{budget}")
    os.makedirs(d, exist_ok=True)
    sp, rp = os.path.join(d, "stim.txt"), os.path.join(d, "results.txt")
    vcd = None if case == "pcm" else os.path.join(d, "taps.vcd")
    open(sp, "w").write("\n".join(stimulus(case, b["nmax"])) + "\n")
    t0 = time.time()
    args = ["vvp", "-n", exe, f"+stim={sp}", f"+out={rp}"] + ([f"+vcd={vcd}"] if vcd else [])
    r = subprocess.run(args, capture_output=True, text=True)
    sim_s = time.time() - t0
    warn = [l for l in (r.stdout + r.stderr).splitlines() if "WARNING" in l or "ERROR" in l or "unknown command" in l]
    _, score_src = score_files(CASES[case]["score"], b["nmax"])
    steps = EV.parse_log(rp)
    if vcd:
        ctl, dat = EV.read_vcd(vcd)
        res = EV.measure(ctl, dat, budget, score_src)
        ev = EV.evaluate(res, ctl, dat, budget, steps)
        ev["samples"], ev["strobes"] = res["samples"], res["strobes"]
        ev["signaltap_dry_run"] = dry_run(case, budget, d, ctl, dat, steps, score_src)
        if case in ("first_go", "full8"):
            ev["late_capture"] = late_capture(budget, ctl, dat, steps, score_src)
    else:
        res = dict(qualified=True, packets=[], errors=[], sweeps=[], strobe_interval=[])
        ev = EV.evaluate(res, [], {}, budget, steps, bench=rp, max_pcm_sweeps=PCM_SWEEPS + 100)
        ev["qualified"] = None
    ev["bench"] = summary(rp)
    ev["sim_seconds"] = round(sim_s, 1)
    ev["simulator_warnings"] = warn[:5]
    return ev


def summary(rp):
    z = {}
    for line in open(rp):
        if line.startswith("Z "):
            for kv in line[2:].split():
                k, v = kv.split("=")
                z[k] = int(v, 16) if k.startswith("adv_0x") or k == "adv_N" else int(v)
        elif line.startswith("T "):
            z["host_timeouts"] = z.get("host_timeouts", 0) + 1
    return z


def check(case, budget, ev):
    """The brief's bounds (EXPECT) against what the run observed: [(item, text, ok)]."""
    b = BUDGETS[budget]
    c = CASES[case]
    R = []

    def add(item, text, ok):
        R.append((item, text, bool(ok)))

    z = ev["bench"]
    add(0, f"bench: I2S frames {z.get('i2s_frames')} decoded, mismatches {z.get('i2s_mismatch')}; host timeouts "
           f"{z.get('host_timeouts', 0)}; strobe interval {z.get('strobe_min')}..{z.get('strobe_max')}; overrun "
           f"{z.get('overrun')}", z.get("i2s_mismatch") == 0 and z.get("i2s_frames", 0) > 0
        and not z.get("host_timeouts") and z.get("overrun") == 0
        and b["tmin"] <= z.get("strobe_min", 0) <= z.get("strobe_max", 0) <= b["tmin"] + 1)
    add(0, f"bench: ADV7513 table done {z.get('adv_done')}, NACK {z.get('adv_nack')}; video: HS/VS/DE/TX_CLK "
           f"faults {z.get('hs_bad')}/{z.get('vs_bad')}/{z.get('de_bad')}/{z.get('tx_clk_phase_bad')}",
        z.get("adv_done") == 1 and z.get("adv_nack") == 0 and z.get("hs_bad") == 0 and z.get("vs_bad") == 0
        and z.get("de_bad") == 0 and z.get("tx_clk_phase_bad") == 0)
    add(0, f"simulator warnings: {len(ev['simulator_warnings'])}", not ev["simulator_warnings"])
    if case != "pcm":
        si = ev.get("strobe_interval") or []
        add(0, f"strobe intervals on the taps {si}", si and set(si) <= {b["tmin"], b["tmin"] + 1})
        add(0, f"K counts 0, 1, 2 ... in every packet: {ev.get('k_ok')}", ev.get("k_ok"))
        if 1 in c["items"]:
            add(1, f"g between the packets of a sweep: {ev.get('g')} (expected all {EXPECT['g']})",
                ev.get("g") == [0])
        if case not in ("ew2", "ew3", "ew4", "ew5", "ew6"):
            tw = ev.get("t_wake") or [99]
            add(2, f"T_wake {tw} clocks (expected <= {EXPECT['t_wake_max']}, nominal 2)", max(tw) <= EXPECT["t_wake_max"])
            fl = ev.get("floor") or [99]
            add(3, f"window {ev.get('window')} -> floor {fl} clocks (expected <= N_MIN {EXPECT['floor_max']})",
                max(fl) <= EXPECT["floor_max"])
            bc = ev.get("bcp") or [99, 99]
            add(4, f"BCP word -> inbox_taken {bc} clocks (expected <= {EXPECT['bcp_max']})", bc[1] <= EXPECT["bcp_max"])
            if case == "full8":
                bf = ev.get("bcp_full_take")
                add(4, f"BCP of the full take-set (8 blocks, full mask, sweep word): {bf} clocks (expected <= "
                       f"{EXPECT['bcp_max']})", bf is not None and bf <= EXPECT["bcp_max"])
            if 5 in c["items"]:
                fll = ev.get("full_load_length")
                add(5, f"full-load sweeps {ev.get('full_load_sweeps')} (sum of bins = {b['nmax']}): strobe -> asleep "
                       f"{fll} clocks (expected <= T_min {b['tmin']})",
                    ev.get("full_load_sweeps", 0) > 0 and fll and fll[1] <= b["tmin"])
            add(0, f"sweep length, longest of the run: {ev.get('sweep_length_max')} (<= {b['tmin']})",
                (ev.get("sweep_length_max") or 0) <= b["tmin"])
    errs = ev.get("errors") or []
    if c["error"] is None:
        add(6 if 6 in c["items"] else 0, f"errors: {[e['code'] for e in errs] or 'none'} (expected none)", not errs)
    else:
        e = errs[0] if errs else {}
        add(6, f"error_flag: {[x['code'] for x in errs]} (expected exactly one, {c['error']})",
            len(errs) == 1 and e.get("code") == c["error"])
        add(6, f"L1 silent after it: packets {e.get('packets_after')}, bins {e.get('bins_after')}, banks written "
               f"{e.get('banks_after')} of which non-zero {e.get('banks_after_nonzero')}",
            e.get("packets_after") == 0 and e.get("bins_after") == 0 and e.get("banks_after", 0) > 0
            and e.get("banks_after_nonzero") == 0)
        add(6, f"the Core halts {e.get('halt_after')} clocks after the flag", e.get("halted"))
    bu, pc = ev.get("bundles") or {}, ev.get("pcm") or {}
    if case != "pcm":
        add(7 if 7 in c["items"] else 0, f"bundles at packet_start equal to the model: {bu.get('equal')}/"
                                         f"{bu.get('compared')}", bu.get("compared", 0) > 0 and bu.get("equal") == bu.get("compared"))
    add(8 if 8 in c["items"] else 0, f"banks equal to the model: {pc.get('equal')}/{pc.get('compared')}"
                                     + (" (up to the error)" if c["error"] else ""),
        pc.get("compared", 0) > 0 and pc.get("equal") == pc.get("compared"))
    if case == "pcm":
        for ch in ("L", "R"):
            cpk, mpk = ev.get(f"spectrum_peaks_captured_{ch}"), ev.get(f"spectrum_peaks_model_{ch}")
            add(8, f"spectrum {ch} over {ev.get('spectrum_samples')} samples (Hz, dB): captured {cpk}, model {mpk}",
                cpk is not None and cpk == mpk)
        add(8, f"PCM peak after the GO {ev.get('pcm_peak_dbfs_last_go')} dBFS (the whole run, the origin's first "
               f"samples included: {ev.get('pcm_peak_dbfs')} dBFS)", ev.get("pcm_peak_dbfs_last_go") is not None)
    if ev.get("model_problems"):
        add(0, f"model: {ev['model_problems'][:3]}", False)
    lc = ev.get("late_capture")
    if case in ("first_go", "full8"):
        okl = bool(lc) and str(lc.get("model_from", "")).startswith("the complete take") and not lc.get("problems") \
            and lc["bundles"]["compared"] > 0 and lc["bundles"]["equal"] == lc["bundles"]["compared"] \
            and lc["pcm"]["compared"] > 0 and lc["pcm"]["equal"] == lc["pcm"]["compared"]
        add(7, f"a capture after the GO, the model started from the GO alone ({(lc or {}).get('model_from')}): "
               f"bundles {((lc or {}).get('bundles') or {}).get('equal')}/{((lc or {}).get('bundles') or {}).get('compared')}, "
               f"banks {((lc or {}).get('pcm') or {}).get('equal')}/{((lc or {}).get('pcm') or {}).get('compared')}", okl)
    dr = ev.get("signaltap_dry_run")
    if dr is not None:
        if not dr["found"]:
            add(0, f"SignalTap dry run: the trigger ({dr['trigger']}) never fired", False)
        else:
            sub = lambda a, b_: a is not None and b_ is not None and set(a) <= set(b_)          # noqa: E731
            ok = dr["same_samples"] and (dr["bundles"] or {}).get("equal") == (dr["bundles"] or {}).get("compared")
            ok = ok and (dr["pcm"] or {}).get("equal") == (dr["pcm"] or {}).get("compared")
            if not dr["qualified"]:
                ok = ok and sub(dr["t_wake"] or [], ev.get("t_wake") or []) and sub(dr["window"] or [], ev.get("window") or [])
                ok = ok and sub(dr["g"] or [], ev.get("g") or [])
            if case == "full8":
                ok = ok and dr["bcp_full_take"] == ev.get("bcp_full_take")
            if case in ("origin", "full8"):                    # item 5 from the capture alone
                ok = ok and bool(dr["full_load_length"]) and sub(dr["full_load_length"], ev.get("full_load_length") or [])
            if c["error"]:
                e = dr["errors"][0] if dr["errors"] else {}
                ok = ok and len(dr["errors"]) == 1 and e.get("code") == c["error"] and e.get("packets_after") == 0 \
                    and e.get("bins_after") == 0 and e.get("banks_after_nonzero") == 0 and e.get("halted")
            add(0, f"SignalTap dry run ({dr['trigger']}; {dr['samples']} samples"
                   f"{', storage-qualified' if dr['qualified'] else ''}): written as an export, read back "
                   f"{'unchanged' if dr['same_samples'] else 'CHANGED'}; bundles {dr['bundles']['equal']}/"
                   f"{dr['bundles']['compared']}, banks {dr['pcm']['equal']}/{dr['pcm']['compared']}"
                   + (f", BCP of the full take-set {dr['bcp_full_take']}" if case == 'full8' else "")
                   + (f", full-load sweep {dr['full_load_length']}" if case in ('origin', 'full8') else "")
                   + (f", {dr['errors'][0]['code'] if dr['errors'] else 'no error'}" if c['error'] else ""), ok)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="all", choices=["all"] + list(CASES))
    ap.add_argument("--budget", default="both", choices=["50", "100", "both"])
    ap.add_argument("--out", default=os.path.join(DE, "build", "cosim"))
    ap.add_argument("--evidence", default=None, help="directory for <case>_<budget>.json and the report")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    a = ap.parse_args()
    budgets = [50, 100] if a.budget == "both" else [int(a.budget)]
    cases = list(CASES) if a.case == "all" else [a.case]
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    exes = {}
    for bu in budgets:
        for cs in cases:
            key = (bu, CASES[cs]["score"])
            if key not in exes:
                exes[key] = build(a.out, bu, CASES[cs]["score"])
    jobs = [(cs, bu) for bu in budgets for cs in cases]
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futs = {j: pool.submit(run_one, j[0], j[1], a.out, exes[(j[1], CASES[j[0]]["score"])]) for j in jobs}
        results = {j: f.result() for j, f in futs.items()}
    lines = [f"cosim_board: the DE10-nano top on the board-level bench (PLLs and ISSP in their SIM branches) — "
             f"evidence class RTL-SIM",
             "expected (SILICON_BRIEF Phase 6, written before the runs): " + "; ".join(f"{k} {v}" for k, v in EXPECT.items())]
    fails = 0
    for (cs, bu), ev in results.items():
        R = check(cs, bu, ev)
        bad = [r for r in R if not r[2]]
        fails += len(bad)
        lines.append(f"[{cs} @ {bu} MHz budget, NMAX {BUDGETS[bu]['nmax']}, T_min {BUDGETS[bu]['tmin']}] "
                     f"{'PASS' if not bad else 'FAIL'}  ({ev['sim_seconds']} s simulated)")
        for item, text, ok in R:
            lines.append(f"  {'ok  ' if ok else 'FAIL'} {'item ' + str(item) if item else 'board '}: {text}")
        if a.evidence:
            os.makedirs(a.evidence, exist_ok=True)
            dr = ev.get("signaltap_dry_run") or {}
            if dr.get("file"):
                shutil.copyfile(dr["file"], os.path.join(a.evidence, f"expected_{cs}_{bu}.vcd.gz"))
                dr["file"] = f"expected_{cs}_{bu}.vcd.gz"
            json.dump(dict(case=cs, budget=bu, expected=EXPECT, observed=ev,
                           checks=[dict(item=i, text=t, ok=o) for i, t, o in R]),
                      open(os.path.join(a.evidence, f"{cs}_{bu}.json"), "w"), indent=1, default=str)
    lines.append(f"cosim_board: {'PASS' if not fails else 'FAIL'} ({len(results)} runs, {fails} failed checks, "
                 f"{time.time() - t0:.0f} s)")
    text = "\n".join(lines)
    print(text)
    if a.evidence:
        open(os.path.join(a.evidence, "cosim_board.txt"), "w").write(text + "\n")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
