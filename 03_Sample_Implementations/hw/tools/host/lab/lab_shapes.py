#!/usr/bin/env python3
# ============================================================================
# lab_shapes.py — OUTSIDE WPMS: a stand-in for the Layer 4 controller.
# The conversions of WPMS Lab (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §3):
# musical and physical knobs -> the 32-bit slot words of one block. Pure
# functions, no I/O. Integers only cross the wall (C3-D1).
#
# The slot semantics, as the customer's oracle realizes them
# (wpms_layer1_oracle.py: l1_phase, l1_amplitude; Ch.3 §3.4.2, §3.5):
#   frequency word of bin k  OM0 + k*OMD1 + C(k,2)*OMD2           (mod 2^32)
#   phase of bin k           PH0 + k*PHD1 + C(k,2)*PHD2           (mod 2^32)
#   log2 window of bin k     LS0 + k*LAD1 + C(k,2)*LAD2           (Q12.20, Q8.24, Q2.30)
#   level                    2^(LP + MG + window), clamped per bin to [0, 1)
# with C(k,2) = k(k-1)/2 (forward differences). Hence:
#   chirp c [Hz]             OMD2 = round(c * 2^32 / Fs)
#   lobe offset tau [s]      PHD1 = -tau * df [cycles/bin]: the bins line up at t = tau
#   Schroeder                PHD1 = 1/(2N), PHD2 = 1/N [cycles]: phase k^2/(2N)
#   window S_k = S_p - a (k - k_c)^2 [log2]:
#                            LAD2 = -2a, LAD1 = a (2 k_c - 1), LS0 = S_p - a k_c^2
#   The GUI's gaussian() (the oracle's gaussian_slots, consistent form) is this
#   window with a = gamma / ln 2, k_c = N/2 (its apex) and S_p = 0, a taken from the
#   ROUNDED LAD2. The Lab's peak position p maps to k_c = p * N, so p = 0.5 is
#   the GUI's window bit for bit.
# Lab is an own-risk tool (the architect, 2026-10-19): the indicators here
# (band, headroom, 32-bit range) inform; nothing here refuses.
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-19       Claude Code   Add : First version (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §3).
# ============================================================================
import math
import os
import sys
from fractions import Fraction

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "gui")))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import wpms_ctl as C                     # noqa: E402  (the GUI's controller: read and import only)

FS = C.FS
M32 = 1 << 32
LN2 = math.log(2)
DB = C.DB_PER_LOG2                       # 6.0206 dB per log2 unit
I32_MIN, I32_MAX = -(1 << 31), (1 << 31) - 1
PHASE_SLOTS = (6, 7, 8)                  # PH0, PHD1, PHD2: [S], sent only in a full re-seed


def u32(x):
    return int(x) % M32


def s32(v):
    return C.s32(v)


def clamp32(x):
    """A signed slot value clamped to 32 bits; returns (value, clamped?)."""
    x = int(x)
    return max(I32_MIN, min(I32_MAX, x)), not I32_MIN <= x <= I32_MAX


# ---- frequency: the chirp (OMD2) -------------------------------------------------------------------
def omd2_word(c_hz):
    """Spacing drift per bin c [Hz] -> OMD2 (two's complement)."""
    return u32(round(c_hz * M32 / FS))


def omd2_hz(word):
    return s32(word) * FS / M32


def chirp_drift_hz(c_hz, N):
    """Change of the bin spacing across the packet: spacing(N-2) - spacing(0) = (N-2) c."""
    return (N - 2) * c_hz


def bin_freqs(f_centre, df, c_hz, N):
    """f_k = f_0 + k df + C(k,2) c, with bin 0 where the GUI puts it (f_centre - df (N-1)/2)."""
    f0 = f_centre - df * (N - 1) / 2
    return [f0 + k * df + (k * (k - 1) // 2) * c_hz for k in range(N)]


def band(f_centre, df, c_hz, N):
    """(lowest, highest) bin frequency [Hz] (the quadratic's extremes included)."""
    fs = bin_freqs(f_centre, df, c_hz, N)
    return min(fs), max(fs)


def band_problem(f_centre, df, c_hz, N):
    """Why the band leaves [0, Fs/2), or None. An indicator only (Lab never refuses on it)."""
    lo, hi = band(f_centre, df, c_hz, N)
    if lo < 0:
        return f"lowest bin at {lo:,.2f} Hz < 0"
    if hi >= FS / 2:
        return f"highest bin at {hi:,.2f} Hz >= Fs/2 = {FS / 2:,.0f} Hz"
    return None


# ---- phase: PH0, PHD1, PHD2 ([S]: seeded only) ------------------------------------------------------
def cycles_word(x):
    """A phase quantity in cycles (any real) -> its 32-bit word."""
    return u32(round(Fraction(x) * M32)) if isinstance(x, Fraction) else u32(round(x * M32))


def word_cycles(w):
    return s32(w) / M32


def phd1_of_tau(tau_s, df_hz):
    """Lobe offset tau [s] -> PHD1 [cycles/bin] = -tau df (the bins line up at t = tau)."""
    return -tau_s * df_hz


def tau_of_phd1(phd1_cycles, df_hz):
    """PHD1 [cycles/bin] -> the first lobe time in [0, 1/df) [s]."""
    return (-phd1_cycles / df_hz) % (1.0 / df_hz)


PHASE_PRESETS = {"Zero": (0, 0), "Schroeder": (1, 1), "Half-Schroeder": (Fraction(1, 2), Fraction(1, 2))}


def phase_preset(name, N):
    """(PHD1, PHD2) in cycles: Zero (0, 0); Schroeder (1/(2N), 1/N); Half-Schroeder (1/(4N), 1/(2N))."""
    s1, s2 = PHASE_PRESETS[name]
    return Fraction(s1, 2 * N) if s1 else Fraction(0), Fraction(s2, N) if s2 else Fraction(0)


def bin_phase(k, ph0, phd1, phd2):
    """Phase word of bin k, closed form (the oracle's l1_phase by forward differences)."""
    return (ph0 + k * phd1 + (k * (k - 1) // 2) * phd2) % M32


# ---- window: LAD1, LAD2, LS0 -------------------------------------------------------------------------
def window_slots(N, a, k_c, s_p=0.0):
    """S_k = s_p - a (k - k_c)^2 [log2] -> (LS0 Q12.20, LAD1 Q8.24, LAD2 Q2.30), unclamped ints.
    a is taken back from the ROUNDED LAD2 (the oracle's consistent form), exact rational arithmetic."""
    lad2 = round(Fraction(-2) * Fraction(a) * (1 << 30))
    a_r = Fraction(-lad2, 1 << 31)
    k_c = Fraction(k_c)
    lad1 = round(a_r * (2 * k_c - 1) * (1 << 24))
    ls0 = round((Fraction(s_p) - a_r * k_c * k_c) * (1 << 20))
    return ls0, lad1, lad2


def window_gauss(N, gamma, pos=0.5, peak_db=0.0):
    """The GUI's Gaussian (a = gamma / ln 2) with its peak at k_c = pos * N and offset peak_db."""
    return window_slots(N, Fraction(gamma) / Fraction(LN2), Fraction(pos) * N, Fraction(peak_db) / Fraction(DB))


def window_raw(start_db, slope_db, curv_db):
    """Raw mode: S_0 [dB], first difference S_1 - S_0 [dB/bin], second difference [dB/bin^2]
    (curv > 0: an inverted window) -> (LS0, LAD1, LAD2)."""
    return (round(start_db / DB * (1 << 20)), round(slope_db / DB * (1 << 24)), round(curv_db / DB * (1 << 30)))


def window_db(k, ls0, lad1, lad2):
    """Window of bin k [dB], closed form."""
    return (s32(ls0) / 2 ** 20 + k * s32(lad1) / 2 ** 24 + (k * (k - 1) // 2) * s32(lad2) / 2 ** 30) * DB


def gamma_of_edge_db(N, edge_db):
    """The Gaussian width whose edge (k = 0, peak at N/2) lies edge_db below the peak."""
    return max(0.0, -edge_db / DB * LN2 / (N / 2) ** 2)


def edge_db_of_gamma(N, gamma):
    return -gamma / LN2 * (N / 2) ** 2 * DB


# ---- headroom: the worst-case peak (all bins in phase) ---------------------------------------------
def bin_amplitudes(slots, mg_q26=0):
    """Linear amplitude of each bin (float), as the L1 makes it: 2^(LP + MG + S_k), clamped to [0, 1)."""
    v = [s32(x) for x in slots]
    N = v[0] & 0xFFF
    lvl = (v[2] + min(0, mg_q26)) / 2 ** 26
    out = []
    for k in range(N):
        L = lvl + v[15] / 2 ** 20 + k * v[3] / 2 ** 24 + (k * (k - 1) // 2) * v[4] / 2 ** 30
        out.append(0.0 if L < -31 else min(1 - 2 ** -31, 2 ** L))
    return out


def peak_dbfs(blocks, g, mg_q26=0):
    """Worst-case output peak per channel [dBFS] of the playing blocks: every bin of every block in
    phase, summed per channel by RT.OUT (bit 0 L, bit 1 R), then x 2^-G (Ch.4 §4.4).
    blocks: [(slots16, rt)]. Returns (left, right); -inf for a silent channel."""
    acc = [0.0, 0.0]
    for slots, rt in blocks:
        s = sum(bin_amplitudes(slots, mg_q26))
        for ch in (0, 1):
            if rt >> ch & 1:
                acc[ch] += s
    return tuple(20 * math.log10(a * 2.0 ** -g) if a > 0 else float("-inf") for a in acc)


# ---- one block: the Lab's knobs -> 16 slots -------------------------------------------------------
LAB_DEFAULTS = dict(chirp=0.0, ph0=0.0, phd1=0.0, phd2=0.0, phase_preset="Zero",
                    win_mode="gauss", win_pos=0.5, win_peak_db=0.0,
                    win_start_db=0.0, win_slope_db=0.0, win_curv_db=0.0)


def lab_slots(p):
    """The 16 slots of a block from the GUI's knobs (f, df, level, glide, gamma, N, route) and the
    Lab's (chirp, phases, window). With the Lab's defaults this is the GUI's block_slots() exactly.
    Returns (slots, notes): notes lists the slots clamped to 32 bits."""
    q = dict(LAB_DEFAULTS)
    q.update(p)
    v = C.block_slots(q)
    N = int(q["N"])
    notes = []
    v[0xC] = omd2_word(q["chirp"])
    if q["win_mode"] == "raw":
        w = window_raw(q["win_start_db"], q["win_slope_db"], q["win_curv_db"])
    else:
        w = window_gauss(N, q["gamma"], q["win_pos"], q["win_peak_db"])
    for i, x in zip((0xF, 0x3, 0x4), w):
        v[i], cl = clamp32(x)
        if cl:
            notes.append(f"slot {i:X} clamped to 32 bits")
    v[6], v[7], v[8] = cycles_word(q["ph0"]), cycles_word(q["phd1"]), cycles_word(q["phd2"])
    return v, notes


def lab_indicators(p, nmax):
    """Indicators of one block (red in the panel; never a refusal)."""
    q = dict(LAB_DEFAULTS)
    q.update(p)
    out = []
    b = band_problem(q["f"], q["df"], q["chirp"], int(q["N"]))
    if b:
        out.append(b)
    _, notes = lab_slots(q)
    out += notes
    if not C.N_MIN <= int(q["N"]) <= nmax:
        out.append(f"N = {q['N']} outside [{C.N_MIN}, {nmax}] (the switch refuses such a GO)")
    return out
