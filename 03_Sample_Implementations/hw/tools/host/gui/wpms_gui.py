#!/usr/bin/env python3
# ============================================================================
# wpms_gui.py — OUTSIDE WPMS: a stand-in for the Layer 4 controller. A Tkinter
# panel for turning WPMS's knobs on the DE10-nano from a PC (GUI brief §3):
#   Master   MG_TARGET in dB (0 ... -72), MG_RATE in dB/s, Panic (MG_TARGET to
#            the floor, -32 log2 units), Test origin (0x01C <- 1), G_CTRL
#            (override and G);
#   Block b  (a tab each, b = 0..7) Play (the sweep order is the order of
#            ticking), centre frequency and spacing (PITCH: phase-continuous),
#            level and glide rate (LEVEL: LPT, LE0 — the glide makes coarse
#            steps click-free), envelope width gamma (LAD1, LAD2, LS0), N, route
#            L / R (RTOUT), Seed (a full RESEED from the panel's values);
#            the sum of N of the ticked blocks against NMAX (read from CONFIG);
#   Status   GO_SEQ, APPLIED_SEQ, APPLIED_SAMPLE, REJECT[0], CLIP, MG, the
#            connection, the transaction times (last, mean, max);
#   Log      the step log as it grows; Save log (JSON, for cosim_gui_replay.py),
#            Save times (CSV).
# Every action goes through wpms_ctl.py (the desired state; its sender thread
# makes the transactions by the coalescing law). Tkinter only.
#
#   quartus_stp -t wpms_bridge.tcl            (one terminal; or: tclsh wpms_bridge.tcl --standin)
#   python wpms_gui.py [--port 50707] [--connect]
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-14       Claude Code   Add : First version (GUI_BRIEF_WPMS_Host_Control_2026-10-14 §3).
# ============================================================================
import argparse, math, os, sys, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wpms_ctl as C                     # noqa: E402

REFRESH_MS = 100
LOG_LINES = 1500


def fmt_hz(x):
    return f"{x:.4g} Hz" if x < 1 else f"{x:,.2f} Hz"


class Knob:
    """A labelled slider, linear or logarithmic, with its value as text."""

    def __init__(self, parent, row, label, lo, hi, log, fmt, on_change, length=330):
        self.log, self.fmt, self.on_change = log, fmt, on_change
        self.var = tk.DoubleVar()
        self.quiet = False
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(4, 6))
        self.scale = ttk.Scale(parent, orient="horizontal", length=length, variable=self.var, command=self._moved)
        self.scale.grid(row=row, column=1, sticky="ew", pady=1)
        self.text = ttk.Label(parent, width=24)
        self.text.grid(row=row, column=2, sticky="w", padx=4)
        self.set_range(lo, hi)

    def _f(self, x):
        return math.log10(x) if self.log else x

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, hi
        v = self.value() if self.var.get() else None
        self.scale.configure(from_=self._f(lo), to=self._f(hi))
        if v is not None:
            self.set(v)

    def value(self):
        v = self.var.get()
        return 10 ** v if self.log else v

    def set(self, x):
        x = min(max(x, min(self.lo, self.hi)), max(self.lo, self.hi))
        self.quiet = True
        self.var.set(self._f(x))
        self.quiet = False
        self.text.configure(text=self.fmt(x))

    def _moved(self, _=None):
        v = self.value()
        self.text.configure(text=self.fmt(v))
        if not self.quiet:
            self.on_change(v)


class BlockTab:
    def __init__(self, app, nb, b):
        self.app, self.b = app, b
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text=f" Block {b} ")
        self.frame = f
        top = ttk.Frame(f)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        self.play = tk.BooleanVar()
        ttk.Checkbutton(top, text="Play", variable=self.play, command=self._play).pack(side="left")
        self.order = ttk.Label(top, width=14)
        self.order.pack(side="left", padx=6)
        ttk.Label(top, text="Route").pack(side="left", padx=(12, 2))
        self.rl, self.rr = tk.BooleanVar(), tk.BooleanVar()
        ttk.Checkbutton(top, text="L", variable=self.rl, command=self._route).pack(side="left")
        ttk.Checkbutton(top, text="R", variable=self.rr, command=self._route).pack(side="left")
        ttk.Label(top, text="N").pack(side="left", padx=(16, 2))
        self.nvar = tk.StringVar()
        self.nspin = ttk.Spinbox(top, from_=C.N_MIN, to=1008, increment=8, width=6, textvariable=self.nvar,
                                 command=self._n)
        self.nspin.pack(side="left")
        self.nspin.bind("<Return>", lambda e: self._n())
        self.nspin.bind("<FocusOut>", lambda e: self._n())
        ttk.Button(top, text="Seed", command=self._seed).pack(side="right")
        k = lambda key: (lambda v: self._knob(key, v))
        self.kf = Knob(f, 1, "Centre", 20, 20000, True, fmt_hz, k("f"))
        self.kdf = Knob(f, 2, "Spacing", 1 / 256, 64, True, lambda x: f"{x:.4g} Hz/bin", k("df"))
        self.klv = Knob(f, 3, "Level", -72, 0, False, lambda x: f"{x:.1f} dB", k("level"))
        self.kgl = Knob(f, 4, "Glide", 1, 10000, True, lambda x: f"{x:.3g} dB/s", k("glide"))
        self.kg = Knob(f, 5, "Width γ", 1e-6, 0.1, True,
                       lambda x: f"{x:.3g}  (±{1 / math.sqrt(x):.0f} bins at 1/e)" if x > 0 else "flat", k("gamma"))
        self.info = ttk.Label(f, foreground="#555")
        self.info.grid(row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.msg = ttk.Label(f, foreground="#b00000", wraplength=560)
        self.msg.grid(row=7, column=0, columnspan=3, sticky="w")
        f.columnconfigure(1, weight=1)

    # ---- from the controller to the widgets --------------------------------------------------------
    def load(self):
        ctl = self.app.ctl
        p = ctl.params[self.b]
        self.nspin.configure(to=ctl.nmax)
        self.kg.set_range(1e-6, C.gamma_max(int(p["N"])))
        self.kf.set(p["f"]); self.kdf.set(p["df"]); self.klv.set(p["level"]); self.kgl.set(p["glide"])
        self.kg.set(max(p["gamma"], 1e-6))
        self.nvar.set(str(int(p["N"])))
        self.rl.set(bool(p["route"] & 1)); self.rr.set(bool(p["route"] & 2))
        self.play.set(self.b in ctl.play)
        self.show()

    def show(self):
        ctl = self.app.ctl
        p = ctl.params[self.b]
        lo, hi = C.band_of(p)
        warn = "  — outside 0 … 24 kHz" if lo < 0 or hi > C.FS / 2 else ""
        known = "switch state unknown (Seed or move a knob)" if ctl.sent_slots[self.b] is None else "in step"
        self.info.configure(text=f"bins {int(p['N'])}: {lo:,.2f} … {hi:,.2f} Hz{warn}   ·   {known}")
        self.order.configure(text=f"(#{ctl.play.index(self.b) + 1} in order)" if self.b in ctl.play else "")

    def say(self, why):
        self.msg.configure(text=why or "")

    # ---- from the widgets to the controller --------------------------------------------------------
    def _knob(self, key, v):
        if not self.app.ready():
            return
        why = self.app.ctl.set_block(self.b, **{key: v})
        self.say(why)
        if why:
            self.load()
        else:
            self.show()

    def _route(self):
        if self.app.ready():
            self.say(self.app.ctl.set_block(self.b, route=int(self.rl.get()) | int(self.rr.get()) << 1))

    def _n(self):
        if not self.app.ready():
            return
        try:
            n = int(self.nvar.get())
        except ValueError:
            self.load()
            return
        ctl = self.app.ctl
        if n == int(ctl.params[self.b]["N"]):
            return
        g = min(ctl.params[self.b]["gamma"], C.gamma_max(n)) if n >= C.N_MIN else ctl.params[self.b]["gamma"]
        why = ctl.set_block(self.b, N=n, gamma=g)
        self.say(why)
        self.load()
        self.app.show_sweep()

    def _play(self):
        if not self.app.ready():
            self.play.set(not self.play.get())
            return
        why = self.app.ctl.set_play(self.b, self.play.get())
        self.say(why)
        if why:
            self.play.set(not self.play.get())
        self.app.show_sweep()

    def _seed(self):
        if self.app.ready():
            self.say(self.app.ctl.seed(self.b))


class App:
    def __init__(self, root, host, port):
        self.root, self.ctl = root, None
        self.host, self.port = tk.StringVar(value=host), tk.StringVar(value=str(port))
        self.seen_version, self.log_shown = -1, 0
        root.title("WPMS host control — OUTSIDE WPMS (Layer 4 stand-in)")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        style = ttk.Style()
        style.configure("Panic.TButton", foreground="#b00000")

        bar = ttk.Frame(root, padding=(6, 4))
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(bar, text="Bridge").pack(side="left")
        ttk.Entry(bar, textvariable=self.host, width=12).pack(side="left", padx=2)
        ttk.Entry(bar, textvariable=self.port, width=6).pack(side="left", padx=2)
        self.bconn = ttk.Button(bar, text="Connect", command=self.connect)
        self.bconn.pack(side="left", padx=4)
        ttk.Button(bar, text="Disconnect", command=self.disconnect).pack(side="left")
        ttk.Button(bar, text="Shut bridge down", command=lambda: self.disconnect(shutdown=True)).pack(side="left", padx=4)
        self.conn = ttk.Label(bar, text="disconnected", foreground="#b00000")
        self.conn.pack(side="left", padx=10)

        left = ttk.Frame(root, padding=4)
        left.grid(row=1, column=0, sticky="nsew")
        # ---- master
        m = ttk.LabelFrame(left, text="Master", padding=6)
        m.grid(row=0, column=0, sticky="ew")
        self.kmg = Knob(m, 0, "MG_TARGET", -72, 0, False, lambda x: f"{x:.1f} dB", self._mg, length=200)
        self.kmr = Knob(m, 1, "MG_RATE", 1, 1000, True, lambda x: f"{x:.3g} dB/s", self._mr, length=200)
        row = ttk.Frame(m)
        row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(row, text="PANIC", style="Panic.TButton", command=self._panic).pack(side="left")
        ttk.Button(row, text="Test origin", command=self._origin).pack(side="left", padx=6)
        ttk.Label(row, text="G").pack(side="left", padx=(10, 2))
        self.gover, self.gval = tk.BooleanVar(value=True), tk.StringVar(value="8")
        ttk.Checkbutton(row, text="override", variable=self.gover, command=self._g).pack(side="left")
        gs = ttk.Spinbox(row, from_=0, to=15, width=4, textvariable=self.gval, command=self._g)
        gs.pack(side="left", padx=2)
        gs.bind("<Return>", lambda e: self._g())
        self.mgnote = ttk.Label(m, foreground="#555")
        self.mgnote.grid(row=3, column=0, columnspan=3, sticky="w")
        # ---- status
        s = ttk.LabelFrame(left, text="Status", padding=6)
        s.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.st = {}
        names = ["GO_SEQ", "APPLIED_SEQ", "APPLIED_SAMPLE", "REJECT0", "CLIP", "MG", "sweep", "GOs / master",
                 "pending", "ISSP last", "ISSP mean / max", "errors"]
        for i, n in enumerate(names):
            ttk.Label(s, text=n).grid(row=i, column=0, sticky="w")
            self.st[n] = ttk.Label(s, width=34, font=("TkFixedFont", 9))
            self.st[n].grid(row=i, column=1, sticky="w")
        self.rej_at_connect = None

        # ---- blocks
        right = ttk.Frame(root, padding=4)
        right.grid(row=1, column=1, sticky="nsew")
        self.sweep = ttk.Label(right, font=("TkDefaultFont", 10, "bold"))
        self.sweep.pack(anchor="w")
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.tabs = [BlockTab(self, self.nb, b) for b in range(8)]

        # ---- log
        lg = ttk.LabelFrame(root, text="Step log", padding=4)
        lg.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        bar2 = ttk.Frame(lg)
        bar2.pack(fill="x")
        ttk.Button(bar2, text="Save log (JSON)", command=self.save_log).pack(side="left")
        ttk.Button(bar2, text="Save times (CSV)", command=self.save_times).pack(side="left", padx=4)
        self.follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="follow", variable=self.follow).pack(side="left", padx=8)
        self.show_polls = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="show status and APPLIED_SEQ polls", variable=self.show_polls).pack(side="left")
        ttk.Label(bar2, text="(the saved log has every transaction)", foreground="#555").pack(side="left", padx=6)
        self.logtext = tk.Text(lg, height=10, width=120, font=("TkFixedFont", 9), wrap="none")
        sb = ttk.Scrollbar(lg, command=self.logtext.yview)
        self.logtext.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.logtext.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)
        self.root.after(REFRESH_MS, self.refresh)

    # ---- connection ----------------------------------------------------------------------------------
    def ready(self):
        return self.ctl is not None and self.ctl.state == "connected"

    def connect(self):
        if self.ctl:
            self.disconnect()
        try:
            self.ctl = C.Controller(self.host.get(), int(self.port.get())).connect()
        except (OSError, C.BridgeError, C.IsspError, ValueError) as e:
            self.ctl = None
            messagebox.showerror("WPMS", f"No connection to the bridge: {e}\n\n"
                                         "Start it first: quartus_stp -t wpms_bridge.tcl")
            return
        self.ctl.start()
        self.rej_at_connect = self.ctl.status.get("REJECT0")
        self.seen_version, self.log_shown = -1, 0
        self.logtext.delete("1.0", "end")

    def disconnect(self, shutdown=False):
        if self.ctl:
            self.ctl.close(shutdown=shutdown)
        self.ctl = None

    def quit(self):
        self.disconnect()
        self.root.destroy()

    # ---- master --------------------------------------------------------------------------------------
    def _mg(self, db):
        if self.ready():
            self.ctl.set_master_db(db)
            self.mgnote.configure(text="")

    def _mr(self, r):
        if self.ready():
            self.ctl.set_mg_rate(r)

    def _panic(self):
        if self.ready():
            self.ctl.panic()
            self.kmg.set(-72)
            self.mgnote.configure(text="PANIC: MG_TARGET at the floor (-32 log2 = -192.7 dB); move the slider to undo")

    def _origin(self):
        if self.ready():
            self.ctl.test_origin()

    def _g(self):
        if not self.ready():
            return
        try:
            g = max(0, min(15, int(self.gval.get())))
        except ValueError:
            return
        self.ctl.set_g(g, self.gover.get())

    # ---- periodic --------------------------------------------------------------------------------------
    def load_all(self):
        ctl = self.ctl
        self.kmg.set(max(-72, C.s32(ctl.mg_target) / 2 ** 26 * C.DB_PER_LOG2))
        self.kmr.set(max(1, ctl.mg_rate / 2 ** 26 * C.FS * C.DB_PER_LOG2))
        self.gover.set(bool(ctl.g_ctrl & 0x10))
        self.gval.set(str(ctl.g_ctrl & 15 if ctl.g_ctrl & 0x10 else 8))
        for t in self.tabs:
            t.load()
        self.show_sweep()

    def show_sweep(self):
        ctl = self.ctl
        if not ctl:
            self.sweep.configure(text="")
            return
        tot = sum(int(ctl.params[b]["N"]) for b in ctl.play)
        self.sweep.configure(text=f"Play order {ctl.play}   ·   Σ N = {tot} / NMAX {ctl.nmax}   ·   "
                                  f"switch: {ctl.sent_play}")
        for t in self.tabs:
            self.nb.tab(t.frame, text=f" Block {t.b}{' ♪' if t.b in ctl.play else ''} ")
            t.show()

    def refresh(self):
        try:
            self._refresh()
        finally:
            self.root.after(REFRESH_MS, self.refresh)

    def _refresh(self):
        ctl = self.ctl
        if not ctl:
            self.conn.configure(text="disconnected", foreground="#b00000")
            return
        ok = ctl.state == "connected"
        self.conn.configure(text=f"{ctl.state} — {ctl.host}:{ctl.port}, ID {ctl.id:08X}, NMAX {ctl.nmax}",
                            foreground="#006000" if ok else "#b00000")
        if ctl.version != self.seen_version:
            self.seen_version = ctl.version
            self.load_all()
        st = ctl.status
        for n in ("GO_SEQ", "APPLIED_SEQ", "APPLIED_SAMPLE", "CLIP"):
            self.st[n].configure(text=f"{st[n]}" if n in st else "-")
        if "REJECT0" in st:
            new = st["REJECT0"] - (self.rej_at_connect or 0)
            self.st["REJECT0"].configure(text=f"{st['REJECT0']}  ({new:+d} since connect)",
                                         foreground="#b00000" if new else "#000")
        if "MG" in st:
            self.st["MG"].configure(text=f"{C.s32(st['MG']) / 2 ** 26 * C.DB_PER_LOG2:.1f} dB")
        self.st["sweep"].configure(text=f"{ctl.sent_play}")
        self.st["GOs / master"].configure(text=f"{ctl.counts['gos']} / {ctl.counts['master']}  "
                                               f"(refused {ctl.counts['refused']})")
        pend = ctl.pending_items()
        self.st["pending"].configure(text=(f"GO {ctl.pending[0]} ({ctl.pending[3]})" if ctl.pending else "no GO")
                                     + (f"; items {pend}" if pend else ""))
        ts = ctl.time_stats()
        if ts["n"]:
            self.st["ISSP last"].configure(text=f"{ts['last'] / 1000:.2f} ms  (n = {ts['n']})")
            self.st["ISSP mean / max"].configure(text=f"{ts['mean'] / 1000:.2f} / {ts['max'] / 1000:.2f} ms")
        self.st["errors"].configure(text=(f"{ctl.counts['errors']}: {ctl.errors[-1][:60]}" if ctl.errors else "0"),
                                    foreground="#b00000" if ctl.errors else "#000")
        # the log, as it grows (at most LOG_LINES kept on screen)
        n = len(ctl.log)
        if n > self.log_shown:
            first = max(self.log_shown, n - LOG_LINES)
            lines = []
            for e in ctl.log[first:n]:
                s, r = e["step"], e["reply"]
                if s[0] == "Q" and not self.show_polls.get() and (s[-1].startswith("status ")
                                                                   or s[-1] == "APPLIED_SEQ poll"):
                    continue
                if s[0] == "W":
                    t = f"W {s[1]:03X} {s[2] & C.M32:08X}"
                elif s[0] == "Q":
                    t = f"R {s[1]:03X}         "
                else:
                    t = f"{s[0]:<21s}"
                rr = ""
                if r and r[0] == "OK":
                    rr = f"-> {r[1]:08X}{' REFUSED' if s[0] == 'W' and r[2] else ''} {r[3] / 1000:6.2f} ms"
                elif r:
                    rr = f"-> {r[0]} {r[1] if len(r) > 1 else ''}"
                lines.append(f"{e['t_us'] / 1e6:10.3f}  {t}  {rr:<32s} {s[-1]}")
            if lines:
                self.logtext.insert("end", "\n".join(lines) + "\n")
            self.log_shown = n
            over = int(self.logtext.index("end-1c").split(".")[0]) - LOG_LINES
            if over > 0:
                self.logtext.delete("1.0", f"{over + 1}.0")
            if self.follow.get():
                self.logtext.see("end")

    # ---- files -------------------------------------------------------------------------------------------
    def save_log(self):
        if not self.ctl:
            return
        p = filedialog.asksaveasfilename(defaultextension=".json", initialfile=time.strftime("wpms_gui_%Y%m%d_%H%M%S.json"),
                                         filetypes=[("step log", "*.json")])
        if p:
            n = self.ctl.save_log(p)
            messagebox.showinfo("WPMS", f"{n} steps saved to {p}\n\nReplay: python cosim_gui_replay.py {os.path.basename(p)}")

    def save_times(self):
        if not self.ctl:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=time.strftime("wpms_times_%Y%m%d_%H%M%S.csv"),
                                         filetypes=[("CSV", "*.csv")])
        if p:
            self.ctl.save_times_csv(p)


def main():
    ap = argparse.ArgumentParser(description="WPMS host control GUI (OUTSIDE WPMS)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=50707)
    ap.add_argument("--connect", action="store_true", help="connect at start")
    a = ap.parse_args()
    root = tk.Tk()
    app = App(root, a.host, a.port)
    if a.connect:
        root.after(200, app.connect)
    root.mainloop()


if __name__ == "__main__":
    main()
