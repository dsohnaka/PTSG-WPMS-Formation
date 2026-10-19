#!/usr/bin/env python3
# ============================================================================
# wpms_lab_ctl.py — OUTSIDE WPMS: a stand-in for the Layer 4 controller.
# The controller of WPMS Lab (LAB_BRIEF_WPMS_Sound_Design_2026-10-19), no Tk.
# Built on the GUI's controller (../gui/wpms_ctl.py, imported, not copied): the
# bridge client, the coalescing law, the switch's GO check and the step log
# are the GUI's, unchanged; this subclass overrides
#   * slots_of(b)  — the seam of brief §2.2 (ruling 2026-10-19): a block's 16
#                    slots come from lab_shapes.lab_slots() (chirp, phases,
#                    window) instead of the GUI's block_slots();
#   * the checks of a desired state — Lab is an own-risk tool (ruling
#                    2026-10-19): no gamma limit, no band or headroom refusal
#                    (indicators only); kept: N in [32, NMAX], the sum of N of
#                    the playing blocks <= NMAX, P <= 8 (the switch's own GO
#                    check) and LE0 >= 0 (LE0 < 0 is EW6: the Formation stops
#                    until a reset — refused, ruling 2026-10-19);
#   * the phase slots PH0, PHD1, PHD2 are [S]: moving their knobs sends nothing;
#                    Seed sends a full re-seed carrying them ("pending seed");
#   * presets (brief §3.5): versioned JSON with the knobs and the resolved slots;
#                    a load is desired state only (full re-seeds and the sweep
#                    word go through the normal sender).
# One bridge serves one client: the GUI and the Lab cannot be connected at once.
#
#   python3 wpms_lab_ctl.py [--port 50707] ping | load PRESET.json [--log F.json]
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-19       Claude Code   Add : First version (LAB_BRIEF_WPMS_Sound_Design_2026-10-19 §2-§4).
# ============================================================================
import argparse, json, os, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab_shapes as LS                  # noqa: E402
C = LS.C                                 # ../gui/wpms_ctl.py (read and import only)

A_G_EFF = 0x014
PHASE_KEYS = ("ph0", "phd1", "phd2", "phase_preset")
KNOB_KEYS = ("f", "df", "level", "glide", "gamma", "N", "route") + tuple(LS.LAB_DEFAULTS)
ONE_CLIENT = "the bridge serves one client at a time: close or disconnect the GUI (or another Lab) first"


class LabController(C.Controller):
    """The GUI's Controller with the Lab's slots, checks, phase seeding and presets."""

    def __init__(self, host="127.0.0.1", port=50707):
        super().__init__(host, port)
        self.g_dip = None                       # G from the DIP switches, read as G_EFF at connect

    # ---- connection ------------------------------------------------------------------------------------
    def connect(self):
        try:
            super().connect()
        except C.BridgeError as e:
            if "busy" in str(e):
                raise C.BridgeError(f"{e} — {ONE_CLIENT}")
            raise
        with self.lock:
            for p in self.params:
                for k, v in LS.LAB_DEFAULTS.items():
                    p.setdefault(k, v)
        g = self._read(A_G_EFF, "G_EFF (connect)") & 15
        self.g_dip = None if self.sent_g_ctrl & 0x10 else g
        return self

    # ---- the seam: a block's slots ----------------------------------------------------------------------
    def slots_of(self, b):
        return LS.lab_slots(self.params[b])[0]

    # ---- checks (own risk: only what the switch or the Formation would stop on) -------------------------
    def lab_problem(self, p):
        if not C.N_MIN <= int(p["N"]) <= self.nmax:
            return f"N = {p['N']} outside [{C.N_MIN}, {self.nmax}] (the switch refuses such a GO)"
        if p["glide"] < 0:
            return "glide < 0 would make LE0 < 0: the Formation's EW6 stops the sound until a reset (refused)"
        return None

    def desired_problem(self, params=None, play=None):
        params = params or self.params
        play = self.play if play is None else play
        for b in play:
            pr = self.lab_problem(params[b])
            if pr:
                return f"block {b}: {pr}"
        if len(play) > 8 or len(set(play)) != len(play):
            return "a block twice in the play order, or more than 8"
        tot = sum(int(params[b]["N"]) for b in play)
        if tot > self.nmax:
            return f"sum of N of the playing blocks {tot} > NMAX {self.nmax}"
        return None

    def set_block(self, b, **kw):
        """Any knob of block b (the GUI's and the Lab's). Phase knobs only change the desired phase
        words (sent by Seed). Returns None or why not."""
        with self.lock:
            p = dict(self.params[b])
            p.update(kw)
            if p.get("phase_preset", "Zero") in LS.PHASE_PRESETS and ("phase_preset" in kw or "N" in kw):
                d1, d2 = LS.phase_preset(p["phase_preset"], int(p["N"]))     # Schroeder follows N
                p["phd1"], p["phd2"] = float(d1), float(d2)
            p.pop("raw_slots", None)            # any knob moved: the slots follow the knobs again
            pr = self.lab_problem(p)
            if pr is None:
                P = list(self.params)
                P[b] = p
                pr = self.desired_problem(P)
            if pr:
                return pr
            self.params[b] = p
            if set(kw) - set(PHASE_KEYS):
                self.touched[b] = True
            return None

    def set_tau(self, b, tau_s):
        """Lobe offset tau [s] -> PHD1 = -tau * df (df as the switch holds it: OMD1 quantized)."""
        dfq = (LS.lab_slots(self.params[b])[0][0xB]) * LS.FS / LS.M32
        return self.set_block(b, phd1=LS.phd1_of_tau(tau_s, dfq), phase_preset="Custom")

    def seed(self, b):
        with self.lock:
            pr = self.lab_problem(self.params[b])
            if pr:
                return pr
            self.touched[b] = self.force_seed[b] = True
            return None

    def phase_pending(self, b):
        """The desired phase words differ from those sent (or nothing was sent yet): Seed needed."""
        with self.lock:
            sent = self.sent_slots[b]
            if sent is None:
                return True
            v = self.slots_of(b)
            return any((v[i] - sent[i]) & 0xFFFFFFFF for i in LS.PHASE_SLOTS)

    # ---- indicators ---------------------------------------------------------------------------------------
    def g_eff(self):
        if self.g_ctrl & 0x10:
            return self.g_ctrl & 15
        return 12 if self.g_dip is None else self.g_dip

    def headroom(self):
        """Worst-case output peak (L, R) [dBFS] of the desired playing set (an indicator, ORACLE-checked)."""
        with self.lock:
            blocks = [(self.slots_of(b), int(self.params[b]["route"]) & 3) for b in self.play]
            mg = C.s32(self.mg_target)
        return LS.peak_dbfs(blocks, self.g_eff(), mg)

    def indicators(self, b):
        with self.lock:
            return LS.lab_indicators(self.params[b], self.nmax)

    # ---- presets (brief §3.5) ------------------------------------------------------------------------------
    def to_preset(self, name=""):
        with self.lock:
            blocks = []
            for b in range(8):
                p = self.params[b]
                knobs = {k: p[k] for k in KNOB_KEYS if k in p}
                if p.get("raw_slots"):
                    knobs["raw_slots"] = list(p["raw_slots"])
                blocks.append(dict(b=b, knobs=knobs, slots=[C.s32(x) for x in self.slots_of(b)],
                                   rtout=int(p["route"]) & 3))
            return dict(version=1, name=name, nmax=self.nmax,
                        master=dict(mg_target=C.s32(self.mg_target), mg_rate=C.s32(self.mg_rate), g_ctrl=self.g_ctrl),
                        sweep=list(self.play), blocks=blocks)

    def save_preset(self, path, name=""):
        doc = self.to_preset(name or os.path.splitext(os.path.basename(path))[0])
        with open(path, "w") as f:
            json.dump(doc, f, indent=1)
        return doc

    def load_preset(self, doc):
        """Set the desired state from a preset (dict or path). Every block of the preset is re-seeded and the
        sweep word follows, through the normal sender. Returns (problem or None, notes)."""
        if isinstance(doc, str):
            doc = json.load(open(doc))
        if doc.get("version") != 1:
            return f"preset version {doc.get('version')} is not 1", []
        notes = []
        if doc.get("nmax") != self.nmax:
            notes.append(f"preset made for NMAX {doc.get('nmax')}, the switch has {self.nmax}")
        with self.lock:
            P = [dict(p) for p in self.params]
            for blk in doc["blocks"]:
                b = int(blk["b"])
                knobs = dict(LS.LAB_DEFAULTS)
                knobs.update(blk["knobs"])
                knobs.pop("raw_slots", None)
                knobs["route"] = int(blk.get("rtout", knobs.get("route", 3))) & 3
                stored = [C.s32(int(x)) for x in blk["slots"]]
                again = [C.s32(x) for x in LS.lab_slots(knobs)[0]]
                if again != stored:
                    diff = [f"{i:X}" for i in range(16) if again[i] != stored[i]]
                    notes.append(f"block {b}: slots {', '.join(diff)} recomputed differently; the stored slots are loaded")
                    knobs["raw_slots"] = stored
                P[b] = knobs
            play = [int(x) for x in doc.get("sweep", [])]
            pr = self.desired_problem(P, play)
            if pr:
                return pr, notes
            for blk in doc["blocks"]:
                b = int(blk["b"])
                self.params[b] = P[b]
                self.touched[b] = self.force_seed[b] = True
            self.play = play
            m = doc.get("master", {})
            if "mg_target" in m:
                self.mg_target = max(C.MG_FLOOR, min(0, int(m["mg_target"])))
            if "mg_rate" in m:
                self.mg_rate = int(m["mg_rate"])
            if "g_ctrl" in m:
                self.g_ctrl = int(m["g_ctrl"]) & 31
            self.version += 1
        return None, notes


def main():
    ap = argparse.ArgumentParser(description="wpms_lab_ctl: the controller of WPMS Lab (OUTSIDE WPMS)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=50707)
    ap.add_argument("cmd", choices=("ping", "load"))
    ap.add_argument("preset", nargs="?")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    ctl = LabController(a.host, a.port).connect()
    print(f"wpms_lab_ctl: ID {ctl.id:08X}, NMAX {ctl.nmax}, sweep {ctl.sent_play}, G {ctl.g_eff()}")
    try:
        if a.cmd == "load":
            pr, notes = ctl.load_preset(a.preset)
            for n in notes:
                print("  note:", n)
            if pr:
                print("  refused:", pr)
            else:
                ok = ctl.run_until_idle(60)
                print(f"  loaded: play {ctl.sent_play}, GOs {ctl.counts['gos']}, idle {ok}, "
                      f"REJECT0 {ctl._status()['REJECT0']}, headroom L/R {ctl.headroom()}")
    finally:
        if a.log:
            print(f"wpms_lab_ctl: {ctl.save_log(a.log)} steps -> {a.log}")
        ctl.close()


if __name__ == "__main__":
    main()
