#!/usr/bin/env python3
# ============================================================================
# l1_model.py — the bit-level model of the WPMS L1 pipeline and output path
# that hw/l1/ implements (SILICON_BRIEF_2026-09-27 Phase 4). One module per
# instance, as the customer's Ch.3 draws it.
#
# WHERE EACH PART COMES FROM
#   * GOLDEN (the customer's oracle, imported and run unchanged):
#       exp2_q131, l1_amplitude (Ch.3 §3.5.4 + Ch.4 §4.4.1 MG), l1_phase
#       (§3.4.2), step_toward (Ch.4 §4.4.1 MG slew; Ch.5 §5.3.2), gaussian_slots.
#   * PUBLISHED HERE (Layer 3, the realization's own definition — the customer's
#     oracle has no model of these; Ch.2 fixes their structure and error
#     budget, not their bits):
#       sin_q040      the Maclaurin core (Ch.2 v1.1): 11th order, Horner, two
#                     clocks per stage, 27-bit signed operands, truncation
#                     toward zero, Q0.40 out. Realization: the Horner variable
#                     is U = u^2 with u the in-quadrant phase in CYCLES, the
#                     2*pi powers are absorbed into the coefficients
#                     c_j = (2*pi)^(2j+1)/(2j+1)! (Ch.2 §2.9 "folded" Arena
#                     row: x' is never materialized — the final multiply is
#                     u * S1, S1 carrying c_0 = 2*pi), and each stage has its
#                     own power-of-two scale (Ch.2 §2.5.1 "pre-scaled") so that
#                     every operand keeps 25-26 significant bits. Seven
#                     multipliers (C2-D10). Max |error| vs sin(2*pi*phi): see
#                     selftest (2^-24.0, the 11th-order truncation itself).
#       product_q163  Q1.31 x Q0.40 -> Q1.71, truncated toward zero to Q1.63
#                     (Ch.3 §3.6.1, Ch.2 v1.1 §2.4.2, C2-D11's policy).
#       accumulators  Q12.63 per channel, gated by RT.OUT bits 0 (L), 1 (R),
#                     closed on the strobe (Ch.3 §3.6.2-3.6.3, C3-D8, C3-D9).
#       output stage  Sum of modules; out = saturate(round(acc * 2^-G)) in
#                     Q1.23, round = add half then floor; sticky clip flags;
#                     MG slewed by step_toward on every strobe, the new value
#                     used by the sweep that strobe starts; soft mute drives the
#                     MG target to the floor (-32) and a sweep played at the
#                     floor while muted outputs exact zero (Ch.4 §4.4, C4-D4..D6);
#                     an L2 error silences the output (ruling 2026-09-28).
#
#   python3 l1_model.py            # self-test: sin core budget, phase path vs
#                                  # the oracle, table/constant provenance
# License: MIT (Layer 3). Evidence class of what it prints: ORACLE.
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF Phase 4).
# ============================================================================
import math, os, random, sys

sys.dont_write_bytecode = True           # never leave __pycache__ beside a golden model
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.environ.get("WS") or os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
ORACLE_DIR = os.path.join(WS, "FPGA_Spectrum_Engine_OpenPrompt", "04_Verification", "oracle")
sys.path.insert(0, ORACLE_DIR)
import wpms_layer1_oracle as O            # noqa: E402  (golden, unchanged)

M32 = 1 << 32


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >> 31 else v


def tz(v, sh):
    """Truncate v / 2^sh toward zero (C2-D11)."""
    return v >> sh if v >= 0 else -((-v) >> sh)


# ---------------------------------------------------------------------------
# The Maclaurin core (Ch.2 v1.1) — published realization
# ---------------------------------------------------------------------------
SIN_U_DROP = 4                       # u = xi' >> 4 : 26 bits, units 2^-28 cycle
SIN_U_UNITS = 28
SIN_UU_DROP = 26                     # U = u*u >> 26 : 26 bits, units 2^-30
SIN_UU_UNITS = 2 * SIN_U_UNITS - SIN_UU_DROP
SIN_E = {1: 23, 2: 20, 3: 19, 4: 19, 5: 20}   # scale 2^e of S_j (S1 outermost)
SIN_F5 = 22                          # scale of c5 (the innermost coefficient)
_TP = 2 * math.pi
# c_j = (2 pi)^(2j+1) / (2j+1)!  as integers at their stage's scale (fixed here; the
# RTL constants are generated from these numbers by gen_l1_tables.py)
SIN_C = [round(_TP ** 1 / 1 * 2 ** SIN_E[1]),             # c0 = 2 pi          (scale 2^23)
         round(_TP ** 3 / 6 * 2 ** SIN_E[2]),             # c1 = (2 pi)^3/3!   (2^20)
         round(_TP ** 5 / 120 * 2 ** SIN_E[3]),           # c2 = (2 pi)^5/5!   (2^19)
         round(_TP ** 7 / 5040 * 2 ** SIN_E[4]),          # c3 = (2 pi)^7/7!   (2^19)
         round(_TP ** 9 / 362880 * 2 ** SIN_E[5]),        # c4 = (2 pi)^9/9!   (2^20)
         round(_TP ** 11 / 39916800 * 2 ** SIN_F5)]       # c5 = (2 pi)^11/11! (2^22)
assert SIN_C == [52707179, 43349917, 42784653, 40215962, 44101737, 63311520], SIN_C
# right shifts that bring each product to the next stage's scale
SIN_SH = {5: SIN_UU_UNITS + SIN_F5 - SIN_E[5],          # U*c5  -> S5 scale : 32
          4: SIN_UU_UNITS + SIN_E[5] - SIN_E[4],        # U*S5  -> S4 scale : 31
          3: SIN_UU_UNITS + SIN_E[4] - SIN_E[3],        # U*S4  -> S3 scale : 30
          2: SIN_UU_UNITS + SIN_E[3] - SIN_E[2],        # U*S3  -> S2 scale : 29
          1: SIN_UU_UNITS + SIN_E[2] - SIN_E[1],        # U*S2  -> S1 scale : 27
          0: SIN_U_UNITS + SIN_E[1] - 40}               # u*S1  -> Q0.40    : 11


def sin_trace(phase):
    """All intermediate values of the core for one phase (Q0.32 cycles)."""
    phase &= 0xFFFFFFFF
    quad = phase >> 30
    xi = phase & ((1 << 30) - 1)
    if quad & 1:                                   # Q2, Q4: 0.25 - xi, as bit inversion (Ch.2 §2.3.3)
        xi = ((1 << 30) - 1) - xi
    u = xi >> SIN_U_DROP
    U = (u * u) >> SIN_UU_DROP
    c = SIN_C
    S5 = c[4] - tz(U * c[5], SIN_SH[5])
    S4 = c[3] - tz(U * S5, SIN_SH[4])
    S3 = c[2] - tz(U * S4, SIN_SH[3])
    S2 = c[1] - tz(U * S3, SIN_SH[2])
    S1 = c[0] - tz(U * S2, SIN_SH[1])
    v = tz(u * S1, SIN_SH[0])
    out = -v if quad & 2 else v
    return dict(quad=quad, xi=xi, u=u, U=U, S5=S5, S4=S4, S3=S3, S2=S2, S1=S1, v=v, sin=out)


def sin_q040(phase):
    """sin(2 pi phase) as Q0.40 signed (41 bits)."""
    return sin_trace(phase)["sin"]


# ---------------------------------------------------------------------------
# Per bin and per packet
# ---------------------------------------------------------------------------
def product_q163(a, s):
    """a (Q1.31, >= 0) x sin (Q0.40) -> Q1.71 -> Q1.63, toward zero."""
    return tz(a * s, 8)


BUNDLE_NAMES = ("PH0", "PHD1", "PHD2", "LP", "LS0", "LAD1", "LAD2", "RT")   # sweep_sim/Register Map order


def phases(ph0, phd1, phd2, n):
    """Phase of bins 0..n-1 by the recurrence of Ch.3 §3.4.2 (= O.l1_phase for every k)."""
    out, phi, d = [], ph0 % M32, phd1 % M32
    for _ in range(n):
        out.append(phi)
        phi = (phi + d) % M32
        d = (d + phd2) % M32
    return out


def packet(bundle, n, mg=0):
    """One packet on L1: bundle = 8 words (u32, oracle order), n bins, MG (Q6.26).
    Returns per-bin lists and the routing bits."""
    ph0, phd1, phd2, lp, ls0, lad1, lad2, rt = bundle
    ph = phases(ph0, phd1, phd2, n)
    amp = O.l1_amplitude(s32(ls0), s32(lad1), s32(lad2), s32(lp), n, MG=mg)   # golden
    sn = [sin_q040(p) for p in ph]
    pr = [product_q163(a, s) for a, s in zip(amp, sn)]
    return dict(phase=ph, a=amp, sin=sn, prod=pr, rt=rt & 3,
                L=lambda k: (s32(lp) << 4) + (mg << 4) + (s32(ls0) << 10) + k * (s32(lad1) << 6)
                + (k * (k - 1) // 2) * s32(lad2))            # log2 amplitude of bin k (Q.30), closed form


# ---------------------------------------------------------------------------
# Output stage (Ch.4 §4.4)
# ---------------------------------------------------------------------------
MG_FLOOR = -(32 << 26)                 # -32 in Q6.26 = -2^31 (Ch.4 §4.4.5)
MG_RATE_DEFAULT = 13933                # 60 dB/s (Ch.4 §4.4.1, CH4-MG)
G_OF_DIP = (0, 4, 8, 12)               # DIP[1:0] (Ch.1 §1.8, C4-D5)
PCM_MAX, PCM_MIN = (1 << 23) - 1, -(1 << 23)


def pcm_of(acc, g):
    """saturate(round(acc * 2^-G)) : acc Q13.63 (any width) -> Q1.23; returns (value, clipped)."""
    y = (acc + (1 << (39 + g))) >> (40 + g)
    if y > PCM_MAX:
        return PCM_MAX, True
    if y < PCM_MIN:
        return PCM_MIN, True
    return y, False


class Output:
    """The output stage and the per-module accumulators, sample by sample."""

    def __init__(self, g=12, mg_target=0, mg_rate=MG_RATE_DEFAULT):
        self.g = g
        self.mg = 0                     # reset value
        self.mg_target = mg_target
        self.mg_rate = mg_rate
        self.soft_mute = False
        self.clip = [False, False]
        self.bank = (0, 0)

    def strobe(self, acc_l, acc_r, mg_of_closed_sweep, error=False):
        """Close the finished sweep into the bank, then step MG for the sweep that starts."""
        if error or (self.soft_mute and mg_of_closed_sweep == MG_FLOOR):
            self.bank = (0, 0)
        else:
            l, cl = pcm_of(acc_l, self.g)
            r, cr = pcm_of(acc_r, self.g)
            self.clip = [self.clip[0] or cl, self.clip[1] or cr]
            self.bank = (l, r)
        tgt = MG_FLOOR if self.soft_mute else min(self.mg_target, 0)
        self.mg = O.step_toward(self.mg, tgt, max(self.mg_rate, 0))     # golden
        return self.bank


def sweep_acc(packets, mg):
    """Accumulators of one sweep: packets = [(bundle, n)]; returns (acc_l, acc_r)."""
    al = ar = 0
    for bun, n in packets:
        p = packet(bun, n, mg)
        s = sum(p["prod"])
        if p["rt"] & 1:
            al += s
        if p["rt"] & 2:
            ar += s
    return al, ar


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def selftest(exhaustive=True):
    ok = True
    print("l1_model self-test — evidence class ORACLE")
    print(f"  golden: {os.path.relpath(os.path.join(ORACLE_DIR, 'wpms_layer1_oracle.py'), WS)} (imported unchanged)")
    print(f"  sin constants c0..c5 = {SIN_C}; stage shifts {SIN_SH}")
    # 1. sin core: every u of one quadrant (exhaustive, numpy), both ends of its 16 phases
    worst, wph, top = 0.0, 0, 0
    try:
        import numpy as np
    except ImportError:
        np = None
    if exhaustive and np is not None:
        c = [np.int64(x) for x in SIN_C]
        for base in range(0, 1 << 26, 1 << 22):
            u = np.arange(base, base + (1 << 22), dtype=np.int64)
            U = (u * u) >> SIN_UU_DROP
            S5 = c[4] - ((U * c[5]) >> SIN_SH[5])
            S4 = c[3] - ((U * S5) >> SIN_SH[4])
            S3 = c[2] - ((U * S4) >> SIN_SH[3])
            S2 = c[1] - ((U * S3) >> SIN_SH[2])
            S1 = c[0] - ((U * S2) >> SIN_SH[1])
            v = (u * S1) >> SIN_SH[0]
            top = max(top, int(v.max()))
            val = v.astype(np.float64) / 2.0 ** 40
            for off in (0, (1 << SIN_U_DROP) - 1):          # the 16 phases that share this u
                xi = (u << SIN_U_DROP) + off
                ref = np.sin(2 * np.pi * xi.astype(np.float64) / 2.0 ** 32)
                e = np.abs(val - ref)
                i = int(e.argmax())
                if e[i] > worst:
                    worst, wph = float(e[i]), int(xi[i])
        how = "exhaustive over u (2^26 values, both ends of each u's 16 phases)"
    else:
        rnd = random.Random(1)
        for _ in range(200000):
            ph = rnd.randrange(1 << 30)
            e = abs(sin_q040(ph) / 2 ** 40 - math.sin(2 * math.pi * ph / 2 ** 32))
            if e > worst:
                worst, wph = e, ph
        top = max(sin_trace(ph)["v"] for ph in range(0, 1 << 30, 1 << 12))
        how = "200,000 random phases (numpy absent)"
    fits = top <= (1 << 40) - 1
    ok &= worst <= 2 ** -23.9 and fits
    print(f"  sin_q040: max |err| vs sin(2 pi phi) = {worst:.3e} = 2^{math.log2(worst):.2f} at phase 0x{wph:08X}; "
          f"max output {top} <= 2^40-1: {fits}  [{how}]")
    print(f"    (Ch.2 §2.8.2 aggregate budget ~1.3e-7; 24-bit DAC LSB 2^-23 = 1.19e-7; the 11th-order "
          f"truncation alone at pi/2 is {(math.pi / 2) ** 13 / math.factorial(13):.2e})")
    # symmetry: Q2/Q4 by reflection, Q3/Q4 by negation
    sym = all(sin_q040(p + (2 << 30)) == -sin_q040(p) for p in range(0, 1 << 30, (1 << 30) // 997))
    ok &= sym
    print(f"  sin_q040: sin(phi + 1/2) = -sin(phi) on 998 phases: {sym}")
    # 2. phase path vs the golden l1_phase
    rnd = random.Random(2)
    bad = 0
    for _ in range(300):
        p0, p1, p2 = (rnd.randrange(M32) for _ in range(3))
        n = rnd.randrange(1, 2049)
        seq = phases(p0, p1, p2, n)
        for k in {0, 1, n - 1, rnd.randrange(n), rnd.randrange(n)}:
            bad += seq[k] != O.l1_phase(p0, p1, p2, k)
    ok &= bad == 0
    print(f"  phases(): equal to the oracle's l1_phase at 5 bins of each of 300 random packets: mismatches {bad}")
    # 3. the exp2 table and constants the RTL uses are the oracle's
    print(f"  exp2 table: 256 x {max(O._T).bit_length()} bits (oracle _T), C1 = {O._C1}, C2 = {O._C2}")
    print(f"l1_model: {'self-test PASS' if ok else 'self-test FAIL'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest("--quick" not in sys.argv) else 1)
