#!/usr/bin/env python3
# ============================================================================
# test_lab.py — OUTSIDE WPMS: checks of WPMS Lab (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §6).
#   V-L1  lab_shapes.py against the customer's oracle (wpms_layer1_oracle.py) and
#         the GUI's gaussian(): the Schroeder identity, phases, lobe offset,
#         crest factors, the window at the centre bit for bit, the window
#         against l1_amplitude, Lab defaults = the GUI's slots, round trips,
#         the band indicator, the headroom estimate. Evidence class ORACLE.
#
#   python3 test_lab.py [--report FILE]
#   exit 0: every case passes · 1: a case fails
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-19       Claude Code   Add : V-L1 (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §6).
# ============================================================================
import argparse, math, os, random, sys
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    lines = ["test_lab: WPMS Lab against the customer's oracle (wpms_layer1_oracle.py) and the GUI's gaussian() — "
             "evidence class ORACLE", " V-L1 — lab_shapes.py"]
    ok_all = True
    for name, ok, text in v_l1():
        lines.append(f"  {name:6s} {'PASS' if ok else 'FAIL'}: {text}")
        ok_all &= ok
    lines.append(f"test_lab: {'PASS' if ok_all else 'FAIL'}")
    print("\n".join(lines))
    if a.report:
        open(a.report, "w").write("\n".join(lines) + "\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
