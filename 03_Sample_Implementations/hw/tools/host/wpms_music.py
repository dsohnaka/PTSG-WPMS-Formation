#!/usr/bin/env python3
# ============================================================================
# wpms_music.py — OUTSIDE WPMS. A stand-in for the Layer 4 controller: a few
# musical GOs for the Phase 6 video, written once and played two ways:
#   * on silicon: a Tcl script for quartus_stp that drives the ISSP instance
#     HOST (wpms_issp_host.tcl), writing the switch's map (customer Ch.5 §5.6);
#   * in simulation: the same steps as commands for the deterministic
#     controller of hw/switch/wpms_system_tb.v (hw/tools/cosim_switch.py
#     --case music checks every sample of it against the models).
# It converts Hz and dB to the page's integers here, on the writer's side of
# the wall (C3-D1): nothing but integers crosses.
#
#   python3 wpms_music.py [--nmax 1008] [--out wpms_music_demo.tcl]
#
# Steps: ("W", addr, data, note) write · ("Q", addr, note) read ·
#        ("APPLY", note) wait until the last GO is applied (silicon: poll
#        APPLIED_SEQ = GO_SEQ; simulation: 3 strobes, Ch.5 §5.4.3's bound + 1) ·
#        ("SOUND", ms, note) let it play (simulation: a few strobes).
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5; host path ISSP, ruling 2026-09-30).
# ============================================================================
import argparse, math, os, sys

FS, M32 = 48_000, 1 << 32
LN2 = math.log(2)
RESEED, PITCH, LEVEL, RT_BIT, ARM, GONOW = 0x9FFF, 0x1C00, 0x0220, 1 << 16, 1 << 30, 1 << 31
MG_RATE_DEFAULT = 13_933                     # 60 dB/s (Ch.4 §4.4.1)


def q26(x):
    return round(x * 2 ** 26)


def om(f_hz):
    return round(f_hz * M32 / FS) % M32


def gaussian(N, gamma, A0):
    """Ch.1 §1.4's Gaussian as slots (the customer's oracle's gaussian_slots, consistent form)."""
    LP = round(math.log2(A0) * 2 ** 26)
    LAD2 = round(-2 * gamma / LN2 * 2 ** 30)
    c = LAD2 / 2 ** 30
    LAD1 = round((-c * (N - 1) / 2) * 2 ** 24)
    LS0 = round(c * N * N / 8 * 2 ** 20)
    return LS0, LAD1, LAD2, LP


def note_block(f_hz, N=240, df_hz=1 / 16, A0=0.97, gamma=3e-4):
    """A packet centred near f_hz: N bins df_hz apart under a Gaussian envelope."""
    ls0, lad1, lad2, lp = gaussian(N, gamma, A0)
    v = [0] * 16
    v[0x0] = N
    v[0x2] = v[0x9] = lp                      # LP, LPT
    v[0x3], v[0x4], v[0xF] = lad1, lad2, ls0
    v[0xA] = om(f_hz - df_hz * (N - 1) / 2)   # OM0: bin 0
    v[0xB] = round(df_hz * M32 / FS)          # OMD1
    return v


def sweep_word(order):
    w = len(order)
    for k, b in enumerate(order):
        w |= b << (4 + 3 * k)
    return w


def stage(b, v, rt=3, mask=RESEED | RT_BIT, arm=True, note=""):
    s = [("W", 0x200 + 16 * b + i, v[i] & 0xFFFFFFFF, f"{note} INBOX[{b}][{i:X}]") for i in range(16)
         if i not in (13, 14) and (mask >> i) & 1]
    if mask & RT_BIT:
        s.append(("W", 0x280 + b, rt, f"{note} RTOUT[{b}]"))
    s.append(("W", 0x288 + b, mask | (ARM if arm else 0), f"{note} COMMIT[{b}]"))
    return s


def demo(nmax=1008):
    """The Phase 6 demo: a triad, a retune, a decay, a bass, a fade, the test origin again."""
    C5, E5, G5, F5, A5, C6, C3 = 523.2511, 659.2551, 783.9909, 698.4565, 880.0, 1046.502, 130.8128
    N = 240 if nmax >= 1008 else 120
    S = [("Q", 0x000, "ID = WPMS"), ("Q", 0x002, "CONFIG"), ("Q", 0x00A, "APPLIED_SEQ (the ROM's GO)"),
         ("W", 0x013, 0x18, "G_CTRL: override, G = 8"),
         ("W", 0x011, MG_RATE_DEFAULT, "MG_RATE 60 dB/s"), ("W", 0x010, 0, "MG_TARGET 0 dB")]
    blocks = {1: note_block(C5, N), 2: note_block(E5, N), 3: note_block(G5, N)}
    for b, v in blocks.items():
        S += stage(b, v, rt=(1, 3, 2)[b - 1], note=f"triad {b}")
    S += [("W", 0x290, sweep_word([1, 2, 3]), "SWEEP [1, 2, 3]"), ("W", 0x291, ARM, "SWEEP_COMMIT arm"),
          ("W", 0x008, 1, "GO"), ("APPLY", "C major"), ("SOUND", 1500, "C major")]
    # retune to F major: phase-continuous (PITCH = OM0, OMD1, OMD2)
    for b, f in ((1, F5), (2, A5), (3, C6)):
        v = note_block(f, N)
        S += stage(b, v, mask=PITCH, note=f"retune {b}")
    S += [("W", 0x008, 1, "GO"), ("APPLY", "F major"), ("SOUND", 1500, "F major")]
    # a decay on the top note: LEVEL (LE0 rate, LPT target), go-now
    v = note_block(C6, N)
    v[0x5], v[0x9] = q26(2 / FS), q26(-12)          # 2 log2 units per second, towards -72 dB
    S += stage(3, v, mask=LEVEL, arm=False, note="decay 3")[:-1]
    S += [("W", 0x28B, LEVEL | GONOW, "COMMIT[3] LEVEL go-now"), ("APPLY", "decay"), ("SOUND", 1500, "decay")]
    # a bass under it: block 4, sweep [1, 2, 3, 4] (4 x N <= NMAX), GO_ALL
    S += stage(4, note_block(C3 * 2, N, A0=0.97), rt=3, note="bass 4")
    S += [("W", 0x290, sweep_word([1, 2, 3, 4]), "SWEEP [1, 2, 3, 4]"), ("W", 0x291, ARM, "SWEEP_COMMIT arm"),
          ("W", 0x008, 2, "GO_ALL"), ("APPLY", "bass"), ("SOUND", 1500, "with bass")]
    # fade out, then the test origin again (the ROM also sets MG_TARGET = 0: it fades back in)
    S += [("W", 0x010, q26(-8) & 0xFFFFFFFF, "MG_TARGET -48 dB"), ("SOUND", 1000, "fade"),
          ("W", 0x01C, 1, "TEST_ORIGIN"), ("APPLY", "test origin"), ("SOUND", 1500, "test origin"),
          ("Q", 0x009, "GO_SEQ"), ("Q", 0x00A, "APPLIED_SEQ"), ("Q", 0x00B, "APPLIED_SAMPLE"),
          ("Q", 0x030, "REJECT[0] (0 expected)")]
    return S


# ---- the two players ------------------------------------------------------------------------------
def to_stim(steps, sound_strobes=6):
    """Commands for wpms_system_tb.v (the deterministic controller)."""
    L = []
    for st in steps:
        if st[0] == "W": L.append(f"W {st[1]:x} {st[2] & 0xFFFFFFFF:x}")
        elif st[0] == "Q": L.append(f"Q {st[1]:x}")
        elif st[0] == "APPLY": L.append("G 3")
        elif st[0] == "SOUND": L.append(f"G {max(1, min(sound_strobes, round(st[1] * FS / 1000))):x}")
    return L


def to_tcl(steps, name="demo"):
    L = [f"# wpms_music_{name}.tcl — generated by hw/tools/host/wpms_music.py. OUTSIDE WPMS: a stand-in for",
         "# the Layer 4 controller. Run on the PC with the DE10-nano attached and the Phase 6 image loaded:",
         f"#   quartus_stp -t wpms_music_{name}.tcl",
         "source [file join [file dirname [info script]] wpms_issp_host.tcl]",
         "wpms_open"]
    for st in steps:
        if st[0] == "W":
            L.append(f"wpms_w 0x{st[1]:03X} 0x{st[2] & 0xFFFFFFFF:08X} {{{st[3]}}}")
        elif st[0] == "Q":
            L.append(f"wpms_q 0x{st[1]:03X} {{{st[2]}}}")
        elif st[0] == "APPLY":
            L.append(f"wpms_wait_applied {{{st[1]}}}")
        elif st[0] == "SOUND":
            L.append(f"after {st[1]} ;# {st[2]}")
    L += ["wpms_close", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nmax", type=int, default=1008)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "wpms_music_demo.tcl"))
    a = ap.parse_args()
    open(a.out, "w").write(to_tcl(demo(a.nmax)))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
