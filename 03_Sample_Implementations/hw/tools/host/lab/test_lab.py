#!/usr/bin/env python3
# ============================================================================
# test_lab.py — OUTSIDE WPMS: checks of WPMS Lab (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §6).
#   V-L2  (--v2) the Lab controller headless against the bridge, the stand-ins and the
#         GUI test's freeze model: a preset load from the origin, a phase knob
#         pending until Seed, 500 random Lab moves; 0 refusals; the step log
#         (--logs) is what V-L3 replays with ../gui/cosim_gui_replay.py.
#   V-L1  lab_shapes.py against the customer's oracle (wpms_layer1_oracle.py) and
#         the GUI's gaussian(): the Schroeder identity, phases, lobe offset,
#         crest factors, the window at the centre bit for bit, the window
#         against l1_amplitude, Lab defaults = the GUI's slots, round trips,
#         the band indicator, the headroom estimate. Evidence class ORACLE.
#
#   python3 test_lab.py [--v2] [--logs DIR] [--report FILE]
#   exit 0: every case passes · 1: a case fails
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-19       Claude Code   Add : V-L1 and V-L2 (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §6).
# ============================================================================
import argparse, json, math, os, random, sys
from fractions import Fraction

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)
import lab_shapes as LS                  # noqa: E402
import wpms_music as MU                  # noqa: E402  (the GUI's gaussian(), unchanged)
import l1_model                          # noqa: E402  (loads the customer's oracle)
O = l1_model.O
C_FULL = LS.C.FULL

M32 = 1 << 32


def v_l1():
    R = []

    def rec(name, ok, text):
        R.append((name, bool(ok), text))

    # L1.1 Schroeder identity, exact
    bad = 0
    for N in (32, 48, 240, 1008, 2048):
        p1, p2 = LS.phase_preset("Schroeder", N)
        for k in range(N):
            if k * p1 + (k * (k - 1) // 2) * p2 != Fraction(k * k, 2 * N):
                bad += 1
    rec("L1.1", bad == 0, f"Schroeder: k PHD1 + C(k,2) PHD2 = k^2/(2N) exactly, N in 32 ... 2048: {bad} exceptions")

    # L1.2 the oracle's Schroeder words at N = 2048
    p1, p2 = LS.phase_preset("Schroeder", 2048)
    w1, w2 = LS.cycles_word(p1), LS.cycles_word(p2)
    rec("L1.2", (w1, w2) == (1 << 20, 1 << 21), f"N = 2048: PHD1 = 0x{w1:X}, PHD2 = 0x{w2:X} (oracle: 2^20, 2^21)")

    # L1.3 closed-form bin phase vs the oracle's forward differences
    rnd = random.Random(1)
    bad = 0
    for _ in range(300):
        ph0, d1, d2 = (rnd.randrange(M32) for _ in range(3))
        k = rnd.randrange(2048)
        if LS.bin_phase(k, ph0, d1, d2) != O.l1_phase(ph0, d1, d2, k):
            bad += 1
    rec("L1.3", bad == 0, f"bin phase closed form = oracle l1_phase on 300 random words: {300 - bad}/300")

    import numpy as np
    # L1.4 lobe offset: the bins line up at t = tau
    worst = 0
    for N, df, tau in ((48, 1 / 16, 3.0), (240, 1 / 16, 11.5), (120, 0.25, 1.234), (48, 1.0, 0.4)):
        omd1 = round(df * M32 / LS.FS)
        dfq = omd1 * LS.FS / M32
        phd1 = LS.cycles_word(LS.phd1_of_tau(tau, dfq))
        n = np.arange(int(LS.FS / dfq))                       # one period, every sample
        k = np.arange(N)
        ph = (k * phd1 / M32)[:, None] + np.outer(k, n) * (omd1 / M32)
        env = np.abs(np.exp(2j * np.pi * ph).sum(0))
        t_pk = int(np.argmax(env))
        worst = max(worst, abs(t_pk - tau * LS.FS))
    rec("L1.4", worst <= 1, f"lobe offset tau: the packet peaks within {worst:.0f} sample(s) of tau (4 cases)")

    # L1.5 crest factor of one packet, N = 240
    def crest(N, name):
        p1, p2 = LS.phase_preset(name, N)
        k = np.arange(N)
        ph = 2 * np.pi * np.array([float(k_ * p1 + (k_ * (k_ - 1) // 2) * p2) for k_ in k])
        c = np.zeros(N * 16, complex)
        c[:N] = np.exp(1j * ph)
        env = np.abs(np.fft.ifft(c)) * N * 16
        return 20 * math.log10(env.max() / math.sqrt(N / 2))
    cz, ch, cs = crest(240, "Zero"), crest(240, "Half-Schroeder"), crest(240, "Schroeder")
    rec("L1.5", abs(cz - 10 * math.log10(480)) < 0.05 and 5 <= cs <= 7 and cs < ch < cz,
        f"crest N = 240: zero {cz:.2f} dB (10 log10 2N = {10 * math.log10(480):.2f}), Half-Schroeder {ch:.2f}, "
        f"Schroeder {cs:.2f} dB")

    # L1.6 the window at the centre vs gaussian(), bit for bit
    rnd = random.Random(6)
    cases = [(N, g) for N in (32, 33, 48, 120, 240, 1008, 2048) for g in (1e-6, 3e-4, 1e-3, 1e-2)]
    cases += [(rnd.randrange(32, 2049), 10 ** rnd.uniform(-6, -2)) for _ in range(200)]
    eq_half = eq_brief = lad2_eq = 0
    for N, g in cases:
        ls0, lad1, lad2, _ = MU.gaussian(N, g, 0.97)
        w = LS.window_gauss(N, g, 0.5, 0.0)
        wb = LS.window_slots(N, Fraction(g) / Fraction(LS.LN2), Fraction(N - 1, 2), 0)
        eq_half += w == (ls0, lad1, lad2)
        eq_brief += wb == (ls0, lad1, lad2)
        lad2_eq += wb[2] == lad2
    n = len(cases)
    rec("L1.6", eq_half == n and eq_brief < n and lad2_eq == n,
        f"window vs gaussian() on {n} (N, gamma): k_c = N/2 equal {eq_half}/{n}; k_c = (N-1)/2 (brief) "
        f"equal {eq_brief}/{n} (LAD2 equal {lad2_eq}/{n}; LAD1 and LS0 differ by half a bin)")

    # L1.7 the window's closed form vs the oracle's l1_amplitude
    rnd = random.Random(7)
    worst = 0.0
    for _ in range(40):
        N = rnd.randrange(32, 600)
        ls0, lad1, lad2 = LS.window_gauss(N, 10 ** rnd.uniform(-5, -2.5), rnd.random(), rnd.uniform(-20, 0))
        lp = round(math.log2(rnd.uniform(0.05, 0.9)) * 2 ** 26)
        a = O.l1_amplitude(ls0, lad1, lad2, lp, N)
        sl = [0] * 16
        sl[0], sl[2], sl[3], sl[4], sl[15] = N, lp, lad1, lad2, ls0
        f = LS.bin_amplitudes(sl)
        for k in range(N):
            if f[k] >= 2 ** -7:
                worst = max(worst, abs(a[k] / 2 ** 31 - f[k]) / f[k])
    rec("L1.7", worst <= 2 ** -23.9, f"window closed form vs oracle l1_amplitude (40 windows, bins >= 2^-7): "
        f"worst relative error 2^{math.log2(worst):.1f} (exp2 unit bound 2^-23.9)")

    # L1.8 Lab defaults = the GUI's slots
    rnd = random.Random(8)
    bad = 0
    for _ in range(300):
        p = dict(f=rnd.uniform(40, 8000), df=2 ** rnd.uniform(-8, 6), level=rnd.uniform(-72, 0),
                 glide=10 ** rnd.uniform(0, 4), gamma=10 ** rnd.uniform(-6, -3), N=rnd.randrange(32, 1009), route=3)
        if LS.lab_slots(p)[0] != LS.C.block_slots(p):
            bad += 1
    rec("L1.8", bad == 0, f"Lab defaults vs GUI block_slots(): {300 - bad}/300 blocks equal in all 16 slots")

    # L1.9 round trips
    rnd = random.Random(9)
    e_c = e_t = 0.0
    for _ in range(500):
        c = rnd.uniform(-0.5, 0.5)
        e_c = max(e_c, abs(LS.omd2_hz(LS.omd2_word(c)) - c))
        df = 2 ** rnd.uniform(-6, 2)
        tau = rnd.uniform(0, 1 / df)
        w = LS.cycles_word(LS.phd1_of_tau(tau, df))
        back = LS.tau_of_phd1(LS.word_cycles(w), df)
        e_t = max(e_t, min(abs(back - tau), 1 / df - abs(back - tau)) * df)   # in cycles
    rec("L1.9", e_c <= LS.FS / M32 and e_t <= 2 ** -32,
        f"OMD2 <-> c within {e_c:.2e} Hz (LSB {LS.FS / M32:.2e}); PHD1 <-> tau within {e_t:.1e} cycle (LSB 2.3e-10)")

    # L1.10 the band indicator
    ok = (LS.band_problem(1000, 1 / 16, 0.0, 240) is None
          and LS.band_problem(1000, 1 / 16, 2.0, 240) is not None          # last bin above 24 kHz
          and LS.band_problem(100, 1, 0.0, 400) is not None                 # first bin below 0
          and LS.band_problem(1000, 1, -0.01, 240) is None)
    rec("L1.10", ok, "band indicator: 0 ... Fs/2 flagged at both ends, quiet inside (shown, never a refusal)")

    # L1.11 headroom estimate vs the oracle (sum of l1_amplitude bins x 2^-G)
    rnd = random.Random(11)
    worst = 0.0
    for _ in range(60):
        blocks, acc = [], [0, 0]
        g = rnd.choice((0, 4, 8, 12))
        mg = -rnd.randrange(0, 4 << 26)
        for b in range(rnd.randrange(1, 5)):
            N = rnd.randrange(32, 300)
            ls0, lad1, lad2 = LS.window_gauss(N, 10 ** rnd.uniform(-6, -2), rnd.random(), rnd.uniform(-6, 6))
            lp = round(rnd.uniform(-8, 1) * 2 ** 26)
            sl = [0] * 16
            sl[0], sl[2], sl[3], sl[4], sl[15] = N, lp, lad1, lad2, ls0
            rt = rnd.choice((1, 2, 3))
            blocks.append((sl, rt))
            s = sum(O.l1_amplitude(ls0, lad1, lad2, lp, N, mg)) / 2 ** 31
            for ch in (0, 1):
                if rt >> ch & 1:
                    acc[ch] += s
        est = LS.peak_dbfs(blocks, g, mg)
        for ch in (0, 1):
            if acc[ch] > 0:
                worst = max(worst, abs(est[ch] - 20 * math.log10(acc[ch] * 2.0 ** -g)))
    rec("L1.11", worst <= 0.01, f"worst-case peak estimate vs oracle (60 cases, per-bin clamp included): "
        f"worst difference {worst:.2e} dB")
    return R


# ---- V-L2: the Lab controller headless, against the bridge + stand-ins + the GUI test's freeze model -----
def v_l2(log_dir=None):
    import shutil, time
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "gui")))
    import test_gui_bridge as TG          # the GUI's test harness (read and import only)
    import wpms_lab_ctl as LC
    R = []
    tclsh = shutil.which("tclsh8.6") or shutil.which("tclsh")
    if not tclsh:
        return [("L2", False, "no tclsh")]
    r = TG.Run(tclsh, TG.HOST, extra=TG.FREEZE)
    ctl = None
    try:
        ctl = LC.LabController(port=r.port).connect()
        presets = {n: json.load(open(os.path.join(HERE, "presets", n + ".json")))
                   for n in ("dirichlet_scale", "schroeder_pad", "chirp_bloom")}

        def gos(item=None, mask=None):
            out = []
            for e in ctl.log:
                s = e["step"]
                if s[0] == "W" and (0x288 <= s[1] <= 0x28F or s[1] == 0x291) and s[2] >> 31:
                    it = 8 if s[1] == 0x291 else s[1] & 7
                    if (item is None or it == item) and (mask is None or (s[2] & 0x1FFFF) == mask):
                        out.append(it)
            return out

        def converged():
            bad = []
            for b in range(8):
                sent = ctl.sent_slots[b]
                if sent is None:
                    continue
                v = ctl.slots_of(b)
                idx = [i for i in range(16) if i not in (1, 2, 13, 14)
                       and (i not in LS.PHASE_SLOTS or not ctl.phase_pending(b))]
                bad += [(b, i) for i in idx if (v[i] - sent[i]) & 0xFFFFFFFF]
            if ctl.play != ctl.sent_play:
                bad.append("play")
            return bad

        # L2.3 first: a preset load from the test origin (block 0, N = 1008)
        pr, notes = ctl.load_preset(presets["dirichlet_scale"])
        ctl.run_until_idle(60)
        full = gos(mask=C_FULL)
        ok3 = (pr is None and not notes and sorted(full) == list(range(8)) and gos(item=8) == [8]
               and ctl.sent_play == list(range(8))
               and all([x & 0xFFFFFFFF for x in ctl.sent_slots[b]] ==
                       [x & 0xFFFFFFFF for x in presets["dirichlet_scale"]["blocks"][b]["slots"]] for b in range(8)))
        R.append(("L2.3", ok3, f"Dirichlet scale from the origin: {len(full)} full re-seeds (blocks {sorted(full)}), "
                  f"{len(gos(item=8))} sweep GO; sent slots = the preset's stored slots: {ok3}; notes {notes}"))

        # L2.2 a phase knob without Seed sends nothing; Seed sends one full re-seed with the phase words
        n0 = len(ctl.log)
        ctl.set_block(5, phase_preset="Schroeder")
        ctl.run_until_idle(10)
        quiet = not any(e["step"][0] == "W" and e["step"][1] in range(0x250, 0x260) or
                        (e["step"][0] == "W" and e["step"][1] == 0x28D) for e in ctl.log[n0:])
        pend = ctl.phase_pending(5)
        g0 = len(gos(item=5, mask=C_FULL))
        ctl.seed(5)
        ctl.run_until_idle(10)
        seeded = len(gos(item=5, mask=C_FULL)) - g0
        d1, d2 = LS.phase_preset("Schroeder", 126)
        carried = (ctl.sent_slots[5][7] & 0xFFFFFFFF, ctl.sent_slots[5][8] & 0xFFFFFFFF) == \
            (LS.cycles_word(float(d1)), LS.cycles_word(float(d2)))
        R.append(("L2.2", quiet and pend and seeded == 1 and carried and not ctl.phase_pending(5),
                  f"phase preset on block 5: no transaction for it, pending seed {pend}; Seed: {seeded} full re-seed, "
                  f"PHD1/PHD2 = Schroeder words {carried}, pending after {ctl.phase_pending(5)}"))

        # L2.1 random Lab traffic, presets in between
        rng = random.Random(21)
        moves = 0
        for k in range(500):
            b = rng.randrange(8)
            r_ = rng.random()
            if r_ < 0.15: ctl.set_block(b, chirp=rng.uniform(-0.002, 0.002))
            elif r_ < 0.30: ctl.set_block(b, win_pos=rng.random(), gamma=10 ** rng.uniform(-6, -2.5))
            elif r_ < 0.38: ctl.set_block(b, win_mode="raw", win_start_db=rng.uniform(-40, 0),
                                          win_slope_db=rng.uniform(-0.5, 0.5), win_curv_db=rng.uniform(-0.01, 0.01))
            elif r_ < 0.42: ctl.set_block(b, win_mode="gauss", win_peak_db=rng.uniform(-12, 3))
            elif r_ < 0.50: ctl.set_block(b, phase_preset=rng.choice(["Zero", "Schroeder", "Half-Schroeder"]))
            elif r_ < 0.55: ctl.set_tau(b, rng.uniform(0, 16))
            elif r_ < 0.60: ctl.seed(b)
            elif r_ < 0.75: ctl.set_block(b, level=rng.uniform(-40, -6))
            elif r_ < 0.85: ctl.set_block(b, f=rng.uniform(150, 2000), df=2 ** rng.uniform(-5, 0))
            elif r_ < 0.90: ctl.set_block(b, N=rng.randrange(32, 200), glide=rng.choice([0, 60, 600]))
            elif r_ < 0.94: ctl.set_play(b, b not in ctl.play)
            elif r_ < 0.96: ctl.load_preset(presets[rng.choice(list(presets))])
            else: ctl.set_master_db(rng.uniform(-24, 0))
            moves += 1
            ctl.step()
        for b in range(8):
            if ctl.phase_pending(b) and ctl.sent_slots[b] is not None:
                ctl.seed(b)
        idle = ctl.run_until_idle(120)
        bad = converged()
        st = ctl._status()
        ok1 = (idle and not bad and st["REJECT0"] == 0 and ctl.counts["refused"] == 0 and ctl.counts["errors"] == 0
               and TG.law_kept(ctl))
        R.append(("L2.1", ok1, f"{moves} random Lab moves (chirp, window gauss/raw, phases, tau, Seed, level, pitch, N, "
                  f"play, presets): {ctl.counts['gos']} GOs; REJECT0 {st['REJECT0']}, refused {ctl.counts['refused']}, "
                  f"errors {ctl.counts['errors']}; sent = desired: {not bad}; each GO applied before the next: "
                  f"{TG.law_kept(ctl)}"))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            n = ctl.save_log(os.path.join(log_dir, "v_l2_lab.json"))
            R.append(("log", True, f"step log {n} steps -> v_l2_lab.json"))
    except Exception as e:                                    # noqa: BLE001
        R.append(("L2", False, f"{type(e).__name__}: {e}"))
    finally:
        if ctl:
            ctl.close(shutdown=True)
        r.finish()
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    ap.add_argument("--v2", action="store_true", help="also V-L2 (needs tclsh)")
    ap.add_argument("--logs", default=None, help="directory for the V-L2 step log (V-L3 replays it)")
    a = ap.parse_args()
    lines = ["test_lab: WPMS Lab against the customer's oracle (wpms_layer1_oracle.py) and the GUI's gaussian() — "
             "evidence class ORACLE", " V-L1 — lab_shapes.py"]
    ok_all = True
    for name, ok, text in v_l1():
        lines.append(f"  {name:6s} {'PASS' if ok else 'FAIL'}: {text}")
        ok_all &= ok
    if a.v2:
        lines.append(" V-L2 — the Lab controller headless (bridge under tclsh, stand-ins, the GUI test's freeze model)")
        for name, ok, text in v_l2(a.logs):
            lines.append(f"  {name:6s} {'PASS' if ok else 'FAIL'}: {text}")
            ok_all &= ok
    lines.append(f"test_lab: {'PASS' if ok_all else 'FAIL'}")
    print("\n".join(lines))
    if a.report:
        open(a.report, "w").write("\n".join(lines) + "\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
