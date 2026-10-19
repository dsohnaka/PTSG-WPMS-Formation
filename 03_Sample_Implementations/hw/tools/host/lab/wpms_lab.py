#!/usr/bin/env python3
# ============================================================================
# wpms_lab.py — OUTSIDE WPMS: a stand-in for the Layer 4 controller.
# WPMS Lab, the sound-design panel (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §3),
# Tkinter only. It is the GUI's panel (../gui/wpms_gui.py, imported, not
# copied: Master with PANIC, Status with CLIP, the step log) with Lab's block
# tabs and the Lab controller (wpms_lab_ctl.py):
#   Chirp      c [Hz per bin] -> OMD2 (PITCH, phase-continuous); the drift (N-2) c
#   Phase      preset (Zero, Schroeder, Half-Schroeder, Custom), PH0 [cycles],
#              lobe offset tau [s] (PHD1 = -tau df), curvature PHD2 [cycles/bin^2];
#              [S]: nothing is sent until "Seed phases" (shown as pending seed)
#   Window     Gaussian: peak position p (k_c = p N; 0.5 = the GUI's window), width
#              (the gamma row, no limit), peak offset [dB]; Raw: start [dB], slope
#              [dB/bin], curvature [dB/bin^2] (> 0: inverted)  -> LAD1, LAD2, LS0 (ENV)
#   Slots      the 16 words of the block, desired and sent (hex, signed decimal)
#   Indicators the band (0 ... Fs/2), the worst-case peak of the playing set
#              (red above -1 dBFS), 32-bit clamps: shown, never a refusal (own
#              risk, ruling 2026-10-19). Refused only: what the switch or the
#              Formation would stop on (N range, sum of N > NMAX, glide < 0).
#   Presets    Load / Save (JSON, presets/).
# The bridge serves one client: close the GUI before connecting the Lab.
#
#   python wpms_lab.py [--port 50707] [--connect] [--preset presets/dirichlet_scale.json]
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-19       Claude Code   Add : First version (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §3).
# ============================================================================
import argparse, json, math, os, sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "gui")))
import lab_shapes as LS                  # noqa: E402
import wpms_lab_ctl as LC                # noqa: E402
import wpms_gui as G                     # noqa: E402  (the GUI's panel: read and import only)

C = LS.C
SLOT_NAMES = ["N", "TAG", "LP", "LAD1", "LAD2", "LE0", "PH0", "PHD1", "PHD2", "LPT", "OM0", "OMD1", "OMD2",
              "-", "-", "LS0"]
RED, ORANGE, GREY = "#b00000", "#b06000", "#555"


class NumRow:
    """A linear slider with an entry: the slider covers a useful range, the entry takes any value."""

    def __init__(self, parent, row, label, lo, hi, fmt, on_change, unit="", length=190):
        self.lo, self.hi, self.fmt, self.on_change = lo, hi, fmt, on_change
        self.quiet = False
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(4, 6))
        self.var = tk.DoubleVar()
        self.scale = ttk.Scale(parent, orient="horizontal", from_=lo, to=hi, length=length, variable=self.var,
                               command=self._moved)
        self.scale.grid(row=row, column=1, sticky="ew", pady=1)
        self.evar = tk.StringVar()
        e = ttk.Entry(parent, textvariable=self.evar, width=11)
        e.grid(row=row, column=2, sticky="w", padx=4)
        e.bind("<Return>", self._entered)
        self.unit = ttk.Label(parent, text=unit, foreground=GREY)
        self.unit.grid(row=row, column=3, sticky="w")

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.scale.configure(from_=lo, to=hi)

    def set(self, x):
        self.quiet = True
        self.var.set(min(max(x, min(self.lo, self.hi)), max(self.lo, self.hi)))
        self.quiet = False
        self.evar.set(self.fmt(x))

    def _moved(self, _=None):
        if self.quiet:
            return
        x = self.var.get()
        self.evar.set(self.fmt(x))
        self.on_change(x)

    def _entered(self, _=None):
        try:
            x = float(self.evar.get())
        except ValueError:
            return
        self.quiet = True
        self.var.set(min(max(x, min(self.lo, self.hi)), max(self.lo, self.hi)))
        self.quiet = False
        self.on_change(x)


class LabTab(G.BlockTab):
    """The GUI's block tab plus the Lab's chirp, phase and window panels, indicators and the slot view."""

    def __init__(self, app, nb, b):
        super().__init__(app, nb, b)
        f = self.frame
        for k in (self.kf, self.kdf, self.klv, self.kgl, self.kg):
            k.scale.configure(length=230)                # room for the slot view
        self.klv.set_range(-72, 12)                      # own risk: levels above 0 dB too
        self.hold = tk.BooleanVar()
        ttk.Checkbutton(f, text="hold (glide 0, LE0 = 0)", variable=self.hold, command=self._hold).grid(
            row=4, column=3, sticky="w")
        L = lambda key: (lambda v: self._lab(key, v))
        # ---- chirp
        self.kc = NumRow(f, 8, "Chirp c", -0.01, 0.01, lambda x: f"{x:.6g}", L("chirp"), "Hz per bin")
        self.drift = ttk.Label(f, foreground=GREY)
        self.drift.grid(row=9, column=0, columnspan=4, sticky="w", padx=4)
        # ---- phases [S]
        ph = ttk.LabelFrame(f, text="Phases (sent only by Seed phases)", padding=4)
        ph.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        top = ttk.Frame(ph)
        top.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(top, text="Preset").pack(side="left")
        self.ppreset = tk.StringVar(value="Zero")
        cb = ttk.Combobox(top, textvariable=self.ppreset, values=["Zero", "Schroeder", "Half-Schroeder", "Custom"],
                          width=15, state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._lab("phase_preset", self.ppreset.get()))
        ttk.Button(top, text="Seed phases", command=self._seed).pack(side="left", padx=8)
        self.pending = ttk.Label(top, foreground=ORANGE)
        self.pending.pack(side="left")
        self.kph0 = NumRow(ph, 1, "PH0", 0, 1, lambda x: f"{x:.6g}", L("ph0"), "cycles")
        self.ktau = NumRow(ph, 2, "Lobe offset τ", 0, 16, lambda x: f"{x:.6g}", self._tau, "s")
        self.kphd2 = NumRow(ph, 3, "Curvature PHD2", -0.05, 0.05, lambda x: f"{x:.6g}", L("phd2"), "cycles/bin²")
        # ---- window
        w = ttk.LabelFrame(f, text="Window (ENV: LAD1, LAD2, LS0) — width is the γ row above", padding=4)
        w.grid(row=11, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.wmode = tk.StringVar(value="gauss")
        mf = ttk.Frame(w)
        mf.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(mf, text="Gaussian", value="gauss", variable=self.wmode,
                        command=lambda: self._lab("win_mode", "gauss")).pack(side="left")
        ttk.Radiobutton(mf, text="Raw", value="raw", variable=self.wmode,
                        command=lambda: self._lab("win_mode", "raw")).pack(side="left", padx=8)
        self.edge = ttk.Label(mf, foreground=GREY)
        self.edge.pack(side="left", padx=8)
        self.kpos = NumRow(w, 1, "Peak position p", 0, 1, lambda x: f"{x:.4g}", L("win_pos"), "k_c = p·N")
        self.kpk = NumRow(w, 2, "Peak offset", -40, 12, lambda x: f"{x:.3g}", L("win_peak_db"), "dB")
        self.kst = NumRow(w, 3, "Raw: start", -60, 12, lambda x: f"{x:.4g}", L("win_start_db"), "dB at bin 0")
        self.ksl = NumRow(w, 4, "Raw: slope", -1, 1, lambda x: f"{x:.5g}", L("win_slope_db"), "dB/bin")
        self.kcu = NumRow(w, 5, "Raw: curvature", -0.05, 0.05, lambda x: f"{x:.5g}", L("win_curv_db"), "dB/bin²")
        # ---- indicators and the slot view
        self.ind = ttk.Label(f, foreground=RED, wraplength=640, justify="left")
        self.ind.grid(row=12, column=0, columnspan=4, sticky="w", pady=(4, 0))
        sv = ttk.LabelFrame(f, text="Slots: desired | sent", padding=2)
        sv.grid(row=0, column=4, rowspan=13, sticky="n", padx=(10, 0))
        self.slots = tk.Text(sv, width=44, height=19, font=("TkFixedFont", 8), relief="flat")
        self.slots.pack()

    # ---- controller -> widgets ---------------------------------------------------------------------------
    def load(self):
        super().load()
        ctl = self.app.ctl
        p = dict(LS.LAB_DEFAULTS)
        p.update(ctl.params[self.b])
        self.kg.set_range(1e-7, 1.0)                     # no gamma limit (own risk)
        self.kg.set(max(p["gamma"], 1e-7))
        self.kgl.set(max(p["glide"], 1))
        self.hold.set(p["glide"] <= 0)
        self.kc.set(p["chirp"])
        self.ppreset.set(p["phase_preset"])
        self.kph0.set(p["ph0"])
        df = p["df"] if p["df"] > 0 else 1 / 16
        self.ktau.set_range(0, 1 / df)
        self.ktau.set(LS.tau_of_phd1(p["phd1"], df) if df > 0 else 0)
        self.kphd2.set(p["phd2"])
        self.wmode.set(p["win_mode"])
        self.kpos.set(p["win_pos"]); self.kpk.set(p["win_peak_db"])
        self.kst.set(p["win_start_db"]); self.ksl.set(p["win_slope_db"]); self.kcu.set(p["win_curv_db"])
        self.show()

    def show(self):
        ctl = self.app.ctl
        p = dict(LS.LAB_DEFAULTS)
        p.update(ctl.params[self.b])
        N = int(p["N"])
        lo, hi = LS.band(p["f"], p["df"], p["chirp"], N)
        known = "switch state unknown (Seed or move a knob)" if ctl.sent_slots[self.b] is None else "in step"
        self.info.configure(text=f"bins {N}: {lo:,.2f} … {hi:,.2f} Hz   ·   {known}")
        self.order.configure(text=f"(#{ctl.play.index(self.b) + 1} in order)" if self.b in ctl.play else "")
        self.drift.configure(text=f"spacing {p['df']:.6g} → {p['df'] + LS.chirp_drift_hz(p['chirp'], N):.6g} Hz across "
                                  f"the packet (drift (N−2)·c = {LS.chirp_drift_hz(p['chirp'], N):+.6g} Hz)")
        if p["win_mode"] == "gauss":
            self.edge.configure(text=f"edges at {LS.edge_db_of_gamma(N, p['gamma']):.1f} dB (centred)")
        else:
            self.edge.configure(text="raw: S_k = start + k·slope + C(k,2)·curvature")
        self.ind.configure(text="   ".join(ctl.indicators(self.b)))
        self.refresh_slots()

    def refresh_slots(self):
        ctl = self.app.ctl
        v = ctl.slots_of(self.b)
        sent = ctl.sent_slots[self.b]
        lines = ["  slot desired   (signed)    sent"]
        for i in range(16):
            d = v[i] & 0xFFFFFFFF
            s = f"{sent[i] & 0xFFFFFFFF:08X}" if sent is not None else "   ?    "
            mark = " " if sent is None or not (v[i] - sent[i]) & 0xFFFFFFFF else "*"
            lines.append(f"{i:X} {SLOT_NAMES[i]:4s} {d:08X} {C.s32(d):>11d}{mark}{s}")
        self.slots.delete("1.0", "end")
        self.slots.insert("end", "\n".join(lines) + "\n* differs: the next GO sends it\n  (phases: Seed)")
        self.pending.configure(text="pending seed" if ctl.phase_pending(self.b) else "")

    # ---- widgets -> controller ---------------------------------------------------------------------------
    def _lab(self, key, v):
        if not self.app.ready():
            return
        kw = {key: v}
        if key in ("ph0", "phd2"):
            kw["phase_preset"] = "Custom"
        why = self.app.ctl.set_block(self.b, **kw)
        self.say(why)
        if why or key in ("phase_preset", "win_mode"):
            self.load()
        else:
            self.show()

    def _tau(self, tau):
        if self.app.ready():
            self.say(self.app.ctl.set_tau(self.b, tau))
            self.ppreset.set("Custom")
            self.show()

    def _hold(self):
        if self.app.ready():
            self.say(self.app.ctl.set_block(self.b, glide=0.0 if self.hold.get() else max(self.kgl.value(), 1)))
            self.show()

    def _n(self):
        if not self.app.ready():
            return
        try:
            n = int(self.nvar.get())
        except ValueError:
            self.load()
            return
        if n != int(self.app.ctl.params[self.b]["N"]):
            self.say(self.app.ctl.set_block(self.b, N=n))
            self.load()
            self.app.show_sweep()


class LabApp(G.App):
    def __init__(self, root, host, port):
        super().__init__(root, host, port)
        root.title("WPMS Lab — OUTSIDE WPMS (Layer 4 stand-in; sound design at your own risk)")
        for t in self.tabs:
            self.nb.forget(t.frame)
        self.tabs = [LabTab(self, self.nb, b) for b in range(8)]
        right = self.sweep.master
        bar = ttk.Frame(right)
        bar.pack(anchor="w", before=self.nb, fill="x")
        ttk.Button(bar, text="Load preset…", command=self.load_preset).pack(side="left")
        ttk.Button(bar, text="Save preset…", command=self.save_preset).pack(side="left", padx=4)
        self.head = ttk.Label(bar, font=("TkDefaultFont", 10, "bold"))
        self.head.pack(side="left", padx=12)

    def connect(self):
        if self.ctl:
            self.disconnect()
        try:
            self.ctl = LC.LabController(self.host.get(), int(self.port.get())).connect()
        except (OSError, C.BridgeError, C.IsspError, ValueError) as e:
            self.ctl = None
            messagebox.showerror("WPMS Lab", f"No connection to the bridge: {e}\n\nStart it first: "
                                             f"quartus_stp -t ../gui/wpms_bridge.tcl\n({LC.ONE_CLIENT})")
            return
        self.ctl.start()
        self.rej_at_connect = self.ctl.status.get("REJECT0")
        self.seen_version, self.log_shown = -1, 0
        self.logtext.delete("1.0", "end")

    def _refresh(self):
        super()._refresh()
        ctl = self.ctl
        if not ctl:
            self.head.configure(text="")
            return
        l, r = ctl.headroom()
        worst = max(l, r)
        txt = "silent" if worst == float("-inf") else f"{l:+.1f} / {r:+.1f} dBFS"
        self.head.configure(text=f"worst-case peak L / R (all bins in phase, G = {ctl.g_eff()}): {txt}",
                            foreground=RED if worst > -1 else "#006000")
        i = self.nb.index(self.nb.select())
        self.tabs[i].refresh_slots()

    def load_preset(self, path=None):
        if not self.ready():
            return
        path = path or filedialog.askopenfilename(initialdir=os.path.join(HERE, "presets"),
                                                  filetypes=[("Lab preset", "*.json")])
        if not path:
            return
        try:
            pr, notes = self.ctl.load_preset(path)
        except (OSError, ValueError, KeyError) as e:
            pr, notes = f"cannot read the preset: {e}", []
        if pr or notes:
            messagebox.showinfo("WPMS Lab", (f"Not loaded: {pr}\n\n" if pr else "Loaded.\n\n") + "\n".join(notes))

    def save_preset(self):
        if not self.ready():
            return
        path = filedialog.asksaveasfilename(initialdir=os.path.join(HERE, "presets"), defaultextension=".json",
                                            filetypes=[("Lab preset", "*.json")])
        if path:
            self.ctl.save_preset(path)


def main():
    ap = argparse.ArgumentParser(description="WPMS Lab (OUTSIDE WPMS)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=50707)
    ap.add_argument("--connect", action="store_true")
    ap.add_argument("--preset", default=None, help="a preset to load after connecting")
    a = ap.parse_args()
    root = tk.Tk()
    app = LabApp(root, a.host, a.port)
    if a.connect:
        def go():
            app.connect()
            if a.preset and app.ready():
                app.load_preset(a.preset)
        root.after(200, go)
    root.mainloop()


if __name__ == "__main__":
    main()
