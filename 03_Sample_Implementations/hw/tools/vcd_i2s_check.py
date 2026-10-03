#!/usr/bin/env python3
# ============================================================================
# vcd_i2s_check.py — what a SignalTap capture of the board's I2S pins says.
# Every audio sample on the wire is matched bit for bit against the L1 model
# playing the test origin (Ch.3 §3.10, the ROM's block); when the Core's
# timing_signals[0] (the packet's Stay) is in the capture too, the sweeps are
# measured against the audio frames.
#
# The capture's sample clock is clk_sys. HDMI_SCLK, HDMI_LRCLK and HDMI_I2S
# are decoded as Philips I2S (64 Fs; LRCLK low = left; the 24-bit word MSB
# first, one SCLK after the LRCLK edge). The test origin's samples depend on
# two unknowns: the sweeps since the GO, and G (DIP[1:0] x 4). The closed form
# of a sum of equally spaced partials finds both (a search over --hours of
# audio). The bit-exact model (l1_model.py) then computes the samples at that
# point, and they must equal the wire. The phases accumulate sweep by sweep in
# the Formation's store, so one wrong update anywhere since the GO would show.
#
#   python3 vcd_i2s_check.py CAPTURE.vcd[.gz] [--budget 50|100] [--hours H]
#
# Exit 0 when every decoded sample equals the model. Evidence class: SILICON
# (the capture), compared with the model. License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (Phase 6: the architect's ptsg_core_debug capture).
# ============================================================================
import argparse, gzip, math, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np                       # noqa: E402
import l1_model as M                     # noqa: E402
import gen_switch_rom as R               # noqa: E402

FS = 48000


def load_vcd(path):
    """The signals by their last name, sampled at each rising edge of the capture clock (clk_sys).
    SignalTap's export lists a sample's values at the time of its clock edge."""
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", newline=None) as f:
        lines = f.read().splitlines()
    ids, scope, body = {}, [], 0
    for body, line in enumerate(lines):
        p = line.split()
        if not p:
            continue
        if p[0] == "$scope":
            scope.append(p[2])
        elif p[0] == "$upscope":
            scope.pop()
        elif p[0] == "$var":
            ids[p[3]] = " ".join(p[4:-1])
        elif p[0] == "$enddefinitions":
            break
    clk = next((i for i, n in ids.items() if n == "clk_sys"), None)
    if clk is None:
        raise SystemExit("no clk_sys in the capture")
    events, t = [], 0
    for line in lines[body + 1:]:
        line = line.strip()
        if not line or line[0] == "$":
            continue
        if line[0] == "#":
            t = int(line[1:])
            continue
        v, i = line[1:].split() if line[0] in "bB" else (line[0], line[1:])
        events.append((t, i, v.lower()))
    state = {i: "x" for i in ids}
    cols = {n: [] for n in ids.values()}
    times, j = [], 0
    while j < len(events):
        t, rise = events[j][0], False
        while j < len(events) and events[j][0] == t:
            _, i, v = events[j]
            rise |= (i == clk and state[i] == "0" and v == "1")
            state[i] = v
            j += 1
        if rise:
            times.append(t)
            for i, n in ids.items():
                cols[n].append(state[i])
    period = (times[-1] - times[0]) / max(len(times) - 1, 1)
    return cols, period


def edges(x, a, b):
    return [k for k in range(1, len(x)) if x[k - 1] == a and x[k] == b]


def decode_i2s(cols):
    """[(frame index, left or None, right or None)] in order; frame = left then right."""
    sck, lr, sd = cols["HDMI_SCLK"], cols["HDMI_LRCLK"], cols["HDMI_I2S"]
    groups, ch, bits = [], None, []
    for k in edges(sck, "0", "1"):
        if k + 1 >= len(sd):
            break
        c, d = lr[k + 1], sd[k + 1]
        if c != ch:
            if ch is not None:
                groups.append((ch, bits))
            ch, bits = c, []
        bits.append(d)
    groups.append((ch, bits))
    frames, cur = [], None
    for c, b in groups:
        w = b[1:25]
        val = None
        if len(b) == 32 and all(x in "01" for x in w):
            val = int("".join(w), 2)
            val -= (1 << 24) if val & (1 << 23) else 0
        if c == "0":                                       # left opens a frame
            cur = [val, None]
            frames.append(cur)
        elif c == "1":
            if cur is None:                                # the capture began with a right word
                cur = [None, None]
                frames.append(cur)
            cur[1] = val
            cur = None
    return [(j, f[0], f[1]) for j, f in enumerate(frames) if f[0] is not None or f[1] is not None]


def origin(budget):
    n = 1008 if budget == 50 else 2048
    v = R.origin_block(n)
    lp = v[0x2] & 0xFFFFFFFF
    amp = M.O.l1_amplitude(0, 0, 0, M.s32(lp), 1, MG=0)[0] / 2.0 ** 31
    return n, v[0xA], v[0xB], lp, amp


def search(vals, n_bins, om0, omd1, amp, hours):
    """The sweep index of the first value and G that fit best (closed form)."""
    m32, L, best = 1 << 32, 4_000_000, (float("inf"), None, None)
    span = len(vals)
    v = np.array(vals, dtype=np.float64)
    for start in range(0, int(hours * 3600 * FS), L):
        n = np.arange(start, start + L + span - 1, dtype=np.int64)
        a = 2 * np.pi * ((n * om0) % m32) / m32
        b = 2 * np.pi * ((n * omd1) % m32) / m32
        s2 = np.sin(b / 2)
        small = np.abs(s2) < 1e-12
        d = np.where(small, n_bins, np.sin(n_bins * b / 2) / np.where(small, 1.0, s2))
        u = amp * np.sin(a + (n_bins - 1) * b / 2) * d
        for g in M.G_OF_DIP:
            p = np.clip(np.rint(u * 2.0 ** (23 - g)), M.PCM_MIN, M.PCM_MAX)
            err = np.zeros(L)
            for j in range(span):
                err += (p[j:j + L] - v[j]) ** 2
            i = int(np.argmin(err))
            if err[i] < best[0]:
                best = (float(err[i]), start + i, g)
    return math.sqrt(best[0] / span), best[1], best[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vcd")
    ap.add_argument("--budget", type=int, choices=(50, 100), default=50)
    ap.add_argument("--hours", type=float, default=2.0, help="how far after the GO to search")
    a = ap.parse_args()
    cols, period = load_vcd(a.vcd)
    ns = len(cols["clk_sys"])
    print(f"vcd_i2s_check: {os.path.basename(a.vcd)} — {ns} samples of clk_sys ({period / 1000:.3f} ns apart) "
          f"— evidence class SILICON, compared with the model")
    lr = cols.get("HDMI_LRCLK")
    fm = edges(lr, "1", "0")                                  # F_m: the left channel begins
    if "timing_signals[0]" in cols:
        pk = cols["timing_signals[0]"]
        up, dn = edges(pk, "0", "1"), edges(pk, "1", "0")
        lens = [next(d for d in dn if d > u) - u for u in up if any(d > u for d in dn)]
        per = [y - x for x, y in zip(up, up[1:])]
        ph = [f - max(u for u in up if u <= f) for f in fm if any(u <= f for u in up)]
        print(f"  Core: packet Stay (timing_signals[0] high) {sorted(set(lens))} clocks in {len(lens)} sweeps; "
              f"sweep period {per} (mean {sum(per) / max(len(per), 1):.3f}); "
              f"F_m minus the packet's start {sorted(set(ph))} clocks")
    frames = decode_i2s(cols)
    both = [(l, r) for _, l, r in frames if l is not None and r is not None]
    print(f"  I2S: {len(frames)} frames decoded ({len(both)} with both words); L == R in "
          f"{sum(l == r for l, r in both)} of {len(both)}")
    vals = [l if l is not None else r for _, l, r in frames]
    n_bins, om0, omd1, lp, amp = origin(a.budget)
    rms, n0, g = search(vals, n_bins, om0, omd1, amp, a.hours)
    print(f"  search (closed form, N = {n_bins}, {a.hours:g} h after the GO): best rms {rms:.1f} LSB at sweep "
          f"{n0} = {n0 / FS:.4f} s after the GO, G = {g} (DIP[1:0] = {g // 4:02b})")
    eq = 0
    for j, (_, l, r) in enumerate(frames):
        n = n0 + j
        bundle = ((n * om0) % M.M32, (n * omd1) % M.M32, 0, lp, 0, 0, 0, 3)
        al, ar = M.sweep_acc([(bundle, n_bins)], 0)
        ml, mr = M.pcm_of(al, g)[0], M.pcm_of(ar, g)[0]
        good = (l is None or l == ml) and (r is None or r == mr)
        eq += good
        print(f"    frame {j}: wire L {l} R {r}; model {ml} {mr}  {'equal' if good else 'DIFFERENT'}")
    ok = eq == len(frames)
    print(f"vcd_i2s_check: {'PASS' if ok else 'FAIL'} — {eq} of {len(frames)} frames equal the model bit for bit")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
