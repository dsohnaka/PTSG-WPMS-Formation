#!/usr/bin/env python3
# ============================================================================
# wpms_ctl.py — OUTSIDE WPMS: a stand-in for the Layer 4 controller. The
# controller behind wpms_gui.py, with no Tk in it (headless tests, scripts):
#   * Bridge: the client of wpms_bridge.tcl (TCP, 127.0.0.1, one line per
#     command: W / R / B / PING / QUIT / SHUTDOWN);
#   * the model of the GUI's state: per block b = 0..7 its knobs (centre,
#     spacing, level, glide, envelope width, N, route), the play order, the
#     master gain, rate and G_CTRL — as DESIRED and as SENT;
#   * the conversions, imported from ../wpms_music.py (om, q26, gaussian,
#     note_block, sweep_word, stage; the formulas already checked in RTL-SIM):
#     integers only cross the wall (C3-D1);
#   * the COALESCING LAW (GUI brief §4): knobs write only the desired state
#     (latest value wins); one sender sends the difference of ONE item at a
#     time (its changed slots, then COMMIT with that mask and go-now) and only
#     when no GO of this controller is pending; a GO is pending until
#     APPLIED_SEQ reaches it; items with differences are served round-robin;
#     the master gain needs no GO and is sent directly, latest value wins;
#     before sending, the GO check of the switch (P <= 8, no block twice,
#     N in [32, NMAX], sum of N <= NMAX) is made here on the state the switch
#     holds, so that a GO the switch would refuse is never sent;
#   * the STEP LOG: every transaction appended as a step of wpms_music.py's
#     format — ("W", addr, data, note), ("Q", addr, note), ("APPLY", note) when
#     a GO is seen applied — with its time and its reply; saved as JSON for
#     cosim_gui_replay.py (the same steps through the switch RTL).
#
#   python3 wpms_ctl.py [--port 50707] ping | status
#   python3 wpms_ctl.py [--port 50707] storm [--moves 400] [--seed 1] [--blocks 0,1,2,3] [--log F.json]
#   python3 wpms_ctl.py [--port 50707] measure [--n 1000] [--seconds 60] [--csv F.csv] [--log F.json]
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-14       Claude Code   Add : First version (GUI_BRIEF_WPMS_Host_Control_2026-10-14 §2-§4).
# 002 2026-10-14       Claude Code   Chg : measure sets up four playing blocks itself (brief §7: "four blocks"),
#                                          prints the histogram and the APPLIED_SEQ polls per GO.
# ============================================================================
import argparse, json, math, os, random, socket, sys, threading, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import wpms_music as MU                  # noqa: E402  (the conversions, unchanged)

FS = MU.FS
M32 = 0xFFFFFFFF
DB_PER_LOG2 = 20 * math.log10(2)          # 6.0206 dB per log2 unit: q26(-8) = -48.16 dB
N_MIN = 32
MG_FLOOR = -(1 << 31)                     # -32 in Q6.26 (Ch.4 §4.4.5): the Panic target
ENV = (1 << 3) | (1 << 4) | (1 << 15)     # LAD1, LAD2, LS0 (envelope width); PH*, LP untouched
GROUPS = (("pitch", MU.PITCH), ("level", MU.LEVEL), ("env", ENV))
FULL = MU.RESEED | MU.RT_BIT
# the map (customer Ch.5 §5.6, module 0)
A_ID, A_CONFIG, A_GO, A_GO_SEQ, A_APPLIED, A_APPLIED_SAMPLE = 0x000, 0x002, 0x008, 0x009, 0x00A, 0x00B
A_MG_TARGET, A_MG_RATE, A_MG, A_G_CTRL, A_CLIP, A_ORIGIN, A_REJECT0 = 0x010, 0x011, 0x012, 0x013, 0x016, 0x01C, 0x030
A_SWEEP, A_SWEEP_COMMIT = 0x290, 0x291
STATUS = ((A_GO_SEQ, "GO_SEQ"), (A_APPLIED, "APPLIED_SEQ"), (A_APPLIED_SAMPLE, "APPLIED_SAMPLE"),
          (A_REJECT0, "REJECT0"), (A_CLIP, "CLIP"), (A_MG, "MG"))
STATUS_PERIOD = 0.25                      # s, status poll when idle (and at most once between knob GOs)
PENDING_TIMEOUT = 3.0                     # s, a GO not applied by then is an error (a reset, a lost GO)


def s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


def seq_reached(applied, seq):
    """APPLIED_SEQ has reached GO number seq (32-bit counters, wrap-safe)."""
    return ((applied - seq) & M32) < (1 << 31)


# ---- conversions (writer side of the wall: integers only cross) --------------------------------
def db_word(db):
    """dB -> Q6.26 log2 units, as MG_TARGET and LPT take them (q26(dB / 6.0206)); <= 0, floor -32."""
    return max(MG_FLOOR, min(0, MU.q26(db / DB_PER_LOG2)))


def rate_word(db_per_s):
    """dB/s -> Q6.26 log2 units per sample, as MG_RATE and LE0 take them (60 dB/s -> 13,933)."""
    return max(1, MU.q26(db_per_s / DB_PER_LOG2 / FS))


def gamma_max(N):
    """The widest gamma whose LAD2, LAD1 and LS0 still fit in 32 bits for this N (gaussian())."""
    c = min(2.0, 256.0 / max(1, N - 1), 16384.0 / (N * N))   # c = 2 gamma / ln 2, |LADx|, |LS0| < 2^31
    return 0.999 * c * math.log(2) / 2


DEFAULT_F = (261.6256, 329.6276, 391.9954, 523.2511, 659.2551, 783.9909, 1046.502, 130.8128)


def default_params(b, nmax=1008):
    return dict(f=DEFAULT_F[b], df=1 / 16, level=-6.0, glide=60.0, gamma=3e-4,
                N=max(N_MIN, min(120, nmax // 8)), route=3)


def block_slots(p):
    """The 16 slots of a block from its knobs (note_block's formulas; LE0 from the glide rate)."""
    v = MU.note_block(p["f"], int(p["N"]), p["df"], A0=10 ** (p["level"] / 20), gamma=p["gamma"])
    v[0x5] = rate_word(p["glide"])
    return v


def params_problem(p, nmax):
    if not (N_MIN <= int(p["N"]) <= nmax):
        return f"N = {p['N']} outside [{N_MIN}, {nmax}]"
    if not (0 <= p["gamma"] <= gamma_max(int(p["N"]))):
        return f"envelope width gamma = {p['gamma']:.3g} outside [0, {gamma_max(int(p['N'])):.3g}] for N = {p['N']}"
    if p["glide"] <= 0:
        return "glide rate must be > 0 dB/s (LE0 = 0 freezes the level; LE0 < 0 is EW6)"
    if p["df"] <= 0 or p["f"] <= 0:
        return "centre and spacing must be > 0 Hz"
    v = block_slots(p)
    big = [i for i in range(16) if not -(1 << 31) <= v[i] < (1 << 32)]
    if big:
        return f"slots {big} do not fit in 32 bits"
    return None


def band_of(p):
    """(lowest, highest) bin frequency in Hz."""
    lo = p["f"] - p["df"] * (int(p["N"]) - 1) / 2
    return lo, lo + p["df"] * (int(p["N"]) - 1)


def sweep_order_of(w):
    P = w & 15
    return [(w >> (4 + 3 * k)) & 7 for k in range(min(P, 8))], P


# ---- the bridge client -------------------------------------------------------------------------
class BridgeError(Exception):
    """The connection to the bridge is lost or the bridge answered out of protocol."""


class IsspError(Exception):
    """The bridge answered ERR: an ISSP error (no acknowledge, a Tcl error); the bridge serves on."""


class Bridge:
    """One TCP connection to wpms_bridge.tcl. Replies are parsed; ERR raises only where noted."""

    def __init__(self, host="127.0.0.1", port=50707, timeout=10.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = self.f = None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.f = self.sock.makefile("rw", encoding="ascii", newline="\n")
        return self

    def close(self):
        for x in (self.f, self.sock):
            try:
                x and x.close()
            except OSError:
                pass
        self.sock = self.f = None

    def _send(self, lines):
        if not self.f:
            raise BridgeError("not connected")
        try:
            self.f.write("".join(l + "\n" for l in lines))
            self.f.flush()
        except OSError as e:
            raise BridgeError(f"connection lost: {e}")

    def _line(self):
        try:
            l = self.f.readline()
        except OSError as e:
            raise BridgeError(f"connection lost: {e}")
        if not l:
            raise BridgeError("connection closed by the bridge")
        return l.strip()

    @staticmethod
    def parse(kind, line):
        """('OK', rdata, rej, us) for W, ('OK', rdata, 0, us) for R, ('SKIP',) or ('ERR', text)."""
        f = line.split()
        if f and f[0] == "OK":
            try:
                if kind == "W" and len(f) == 4:
                    return ("OK", int(f[1], 16), int(f[2]), int(f[3]))
                if kind == "R" and len(f) == 3:
                    return ("OK", int(f[1], 16), 0, int(f[2]))
            except ValueError:
                pass
            return ("ERR", f"unparsed reply: {line}")
        if f and f[0] == "SKIP":
            return ("SKIP",)
        return ("ERR", line[4:] if line.startswith("ERR ") else f"unexpected reply: {line}")

    def write(self, addr, data):
        self._send([f"W {addr & 0xFFF:03X} {data & M32:08X}"])
        return self.parse("W", self._line())

    def read(self, addr):
        self._send([f"R {addr & 0xFFF:03X}"])
        return self.parse("R", self._line())

    def batch(self, ops):
        """ops: [('W', a, d) | ('R', a)] -> ([reply per op], END us). One TCP round trip."""
        lines = [f"W {o[1] & 0xFFF:03X} {o[2] & M32:08X}" if o[0] == "W" else f"R {o[1] & 0xFFF:03X}" for o in ops]
        self._send([f"B {len(lines)}"] + lines)
        R = [self.parse(o[0], self._line()) for o in ops]
        end = self._line()
        if not end.startswith("END "):
            raise BridgeError(f"no END after a batch: {end}")
        return R, int(end.split()[1])

    def ping(self):
        self._send(["PING"])
        l = self._line()
        f = l.split()
        if len(f) != 4 or f[:2] != ["OK", "WPMS"]:
            raise BridgeError(f"PING: {l}")
        return int(f[2], 16), int(f[3], 16)

    def quit(self, shutdown=False):
        try:
            self._send(["SHUTDOWN" if shutdown else "QUIT"])
            return self._line()
        finally:
            self.close()


# ---- the controller ------------------------------------------------------------------------------
class Controller:
    """The GUI's state as desired and as sent, the coalescing sender and the step log.
    Knob setters may be called from any thread; step() / the sender thread do the transactions."""

    def __init__(self, host="127.0.0.1", port=50707):
        self.host, self.port = host, port
        self.lock = threading.RLock()
        self.bridge = None
        self.state = "disconnected"
        self.nmax, self.id, self.config = 1008, 0, 0
        self.t0 = time.monotonic()
        # desired
        self.params = [default_params(b) for b in range(8)]
        self.touched = [False] * 8               # a knob of the block moved since its state was unknown
        self.force_seed = [False] * 8
        self.play = []                           # the desired sweep order
        self.mg_target, self.mg_rate, self.g_ctrl = 0, MU.MG_RATE_DEFAULT, 0
        self.oneshots = []                       # ("origin",)
        # sent (what the switch holds after the GOs this controller saw applied)
        self.sent_slots = [None] * 8             # list of 16 or None (unknown)
        self.sent_rt = [None] * 8
        self.sent_N = [None] * 8                 # N as the switch's GO check knows it (None: unknown)
        self.sent_play = None
        self.sent_mg_target = self.sent_mg_rate = self.sent_g_ctrl = None
        # the sender
        self.rr = 0
        self.pending = None                      # (seq, item, t_sent, note)
        self.status_due_ok = True                # a status poll may run before the next knob GO
        self.last_status = 0.0
        self.hold_until = 0.0
        self.status = {}
        # records
        self.log = []                            # {"t_us", "step", "reply"}
        self.times = []                          # us of every transaction (bridge-measured)
        self.go_lat = []                         # s from a COMMIT go-now sent to its apply seen
        self.counts = dict(gos=0, master=0, refused=0, errors=0, skipped=0, status=0)
        self.errors = []
        self.origin_state = None                 # what connect() read (for the replay)
        self.version = 0                         # bumped when desired state changes from outside the GUI
        self._thread = None
        self._stop = threading.Event()

    # ---- the step log --------------------------------------------------------------------------------
    def _t(self):
        return int((time.monotonic() - self.t0) * 1e6)

    def _rec(self, step, reply=None):
        self.log.append(dict(t_us=self._t(), step=list(step), reply=list(reply) if reply else None))

    def save_log(self, path):
        with self.lock:
            doc = dict(format="wpms_ctl step log 1", note="OUTSIDE WPMS: steps of wpms_music.py's format",
                       bridge=f"{self.host}:{self.port}", id=self.id, config=self.config, nmax=self.nmax,
                       origin=self.origin_state, counts=self.counts,
                       steps=[e["step"] for e in self.log], t_us=[e["t_us"] for e in self.log],
                       replies=[e["reply"] for e in self.log])
        with open(path, "w") as f:
            json.dump(doc, f, indent=0)
        return len(doc["steps"])

    def save_times_csv(self, path):
        with open(path, "w") as f:
            f.write("k,us\n")
            for k, us in enumerate(self.times):
                f.write(f"{k},{us}\n")

    def time_stats(self):
        t = self.times
        if not t:
            return dict(n=0, last=None, mean=None, max=None, min=None)
        return dict(n=len(t), last=t[-1], mean=sum(t) / len(t), max=max(t), min=min(t))

    # ---- transactions (all logged) -------------------------------------------------------------------
    def _note_err(self, text):
        self.counts["errors"] += 1
        self.errors.append(text)
        del self.errors[:-50]

    def _ops(self, ops):
        """ops: [(step tuple)] of W / Q steps -> replies; one batch (one round trip). Stops at a refusal."""
        req = [("W", s[1], s[2]) if s[0] == "W" else ("R", s[1]) for s in ops]
        if len(req) == 1:
            r = [self.bridge.write(req[0][1], req[0][2]) if req[0][0] == "W" else self.bridge.read(req[0][1])]
        else:
            r, _ = self.bridge.batch(req)
        for s, x in zip(ops, r):
            if x[0] == "SKIP":
                self.counts["skipped"] += 1
                continue
            self._rec(s, x)
            if x[0] == "OK":
                self.times.append(x[3])
                if s[0] == "W" and x[2]:
                    self.counts["refused"] += 1
                    self._note_err(f"REFUSED: W {s[1]:03X} {s[2] & M32:08X} ({s[3]})")
            else:
                self._note_err(f"ERR at {s[0]} {s[1]:03X}: {x[1]}")
        return r

    def _read(self, addr, note):
        x = self._ops([("Q", addr, note)])[0]
        if x[0] != "OK":
            raise IsspError(f"read {addr:03X}: {x[1] if len(x) > 1 else x[0]}")
        return x[1]

    # ---- connect / resync ----------------------------------------------------------------------------
    def connect(self):
        self.bridge = Bridge(self.host, self.port).connect()
        self.id, self.config = self.bridge.ping()
        if self.id != 0x5750_4D53:
            raise BridgeError(f"ID {self.id:08X} is not WPMS")
        self.nmax = (self.config >> 8) & 0xFFFF            # CONFIG = {8'd0, NMAX[15:0], blocks, M}
        self.params = [default_params(b, self.nmax) for b in range(8)]
        self._rec(("Q", A_ID, "ID = WPMS (PING)"), ("OK", self.id, 0, 0))
        self._rec(("Q", A_CONFIG, "CONFIG (PING)"), ("OK", self.config, 0, 0))
        self._resync("connect")
        st = self._status()
        if st.get("GO_SEQ") != st.get("APPLIED_SEQ"):
            self.pending = (st["GO_SEQ"], None, time.monotonic(), "a GO found pending at connect")
        self.state = "connected"
        return self

    def _resync(self, why):
        """Read what the switch holds — the sweep word, N of the listed blocks, the master knobs — and
        take it as both sent and desired (after connect, the test origin, or a GO not applied)."""
        w = self._read(A_SWEEP, f"SWEEP ({why})")
        order, P = sweep_order_of(w)
        N = {b: self._read(0x200 + 16 * b, f"INBOX[{b}][0] N ({why})") & 0xFFF for b in order}
        mgt = s32(self._read(A_MG_TARGET, f"MG_TARGET ({why})"))
        mgr = s32(self._read(A_MG_RATE, f"MG_RATE ({why})"))
        gc = self._read(A_G_CTRL, f"G_CTRL ({why})") & 31
        with self.lock:
            self.sent_play, self.play = list(order), list(order)
            self.sent_slots, self.sent_rt, self.sent_N = [None] * 8, [None] * 8, [None] * 8
            self.touched, self.force_seed = [False] * 8, [False] * 8
            for b, n in N.items():
                self.sent_N[b] = n
                self.params[b]["N"] = n
            self.sent_mg_target, self.sent_mg_rate, self.sent_g_ctrl = mgt, mgr, gc
            self.mg_target, self.mg_rate, self.g_ctrl = mgt, mgr, gc
            if self.origin_state is None:
                self.origin_state = dict(sweep=w, N={str(b): n for b, n in N.items()},
                                         mg_target=mgt, mg_rate=mgr, g_ctrl=gc)
            self.version += 1

    def close(self, shutdown=False):
        self.stop()
        if self.bridge:
            try:
                self.bridge.quit(shutdown)
            except (BridgeError, OSError):
                pass
        self.bridge = None
        self.state = "disconnected"

    # ---- knobs: desired state only (latest value wins) ----------------------------------------------
    def desired_problem(self, params=None, play=None):
        """Why a desired state would be refused (the GUI says it before the switch has to), or None."""
        params = params or self.params
        play = self.play if play is None else play
        for b in play:
            pr = params_problem(params[b], self.nmax)
            if pr:
                return f"block {b}: {pr}"
        if len(play) > 8 or len(set(play)) != len(play):
            return "a block twice in the play order, or more than 8"
        tot = sum(int(params[b]["N"]) for b in play)
        if tot > self.nmax:
            return f"sum of N of the playing blocks {tot} > NMAX {self.nmax}"
        return None

    def set_block(self, b, **kw):
        """Change knobs of block b (f, df, level, glide, gamma, N, route). Returns None or why not."""
        with self.lock:
            p = dict(self.params[b])
            p.update(kw)
            pr = params_problem(p, self.nmax)
            if pr is None:
                P = list(self.params)
                P[b] = p
                pr = self.desired_problem(P)
            if pr:
                return pr
            self.params[b] = p
            self.touched[b] = True
            return None

    def set_play(self, b, on):
        """Tick / untick block b; the order is the order of ticking. Returns None or why not."""
        with self.lock:
            play = [x for x in self.play if x != b] + ([b] if on else [])
            pr = self.desired_problem(play=play)
            if pr:
                return pr
            if on and self.sent_N[b] is None:
                self.touched[b] = True               # never seeded: seed it before it joins the sweep
            self.play = play
            return None

    def seed(self, b):
        with self.lock:
            pr = params_problem(self.params[b], self.nmax)
            if pr:
                return pr
            self.touched[b] = self.force_seed[b] = True
            return None

    def set_master_db(self, db):
        with self.lock:
            self.mg_target = db_word(db)

    def panic(self):
        with self.lock:
            self.mg_target = MG_FLOOR

    def set_mg_rate(self, db_per_s):
        with self.lock:
            self.mg_rate = rate_word(db_per_s)

    def set_g(self, g, override=True):
        with self.lock:
            self.g_ctrl = (0x10 | (int(g) & 15)) if override else 0

    def test_origin(self):
        with self.lock:
            self.oneshots.append(("origin",))

    # ---- the difference of one item ------------------------------------------------------------------
    def _block_mask(self, b):
        if not self.touched[b] and self.sent_slots[b] is None:
            return 0
        v = block_slots(self.params[b])
        rt = int(self.params[b]["route"]) & 3
        if self.sent_slots[b] is None or self.force_seed[b] or v[0] != self.sent_slots[b][0]:
            return FULL
        m = 0
        for _, g in GROUPS:
            if any(v[i] != self.sent_slots[b][i] for i in range(16) if g >> i & 1):
                m |= g
        if rt != self.sent_rt[b]:
            m |= MU.RT_BIT
        return m

    def _go_ok(self, item, m=0):
        """The switch's GO check (PR-1, PR-2, §5.4.4) on the state it holds after this GO."""
        N = list(self.sent_N)
        order = self.sent_play or []
        if item == 8:
            order = self.play
        elif m & 1:
            N[item] = int(self.params[item]["N"])
        if len(order) > 8 or len(set(order)) != len(order):
            return False
        if any(N[b] is None or not N_MIN <= N[b] <= self.nmax for b in order):
            return False
        return sum(N[b] for b in order) <= self.nmax

    def pending_items(self):
        with self.lock:
            its = [b for b in range(8) if self._block_mask(b)]
            if self.sent_play is not None and self.play != self.sent_play:
                its.append(8)
            return its

    def busy(self):
        with self.lock:
            return bool(self.pending or self.oneshots or self.pending_items() or self._master_diff())

    def _master_diff(self):
        d = []
        if self.mg_target != self.sent_mg_target:
            d.append((A_MG_TARGET, self.mg_target, "MG_TARGET"))
        if self.mg_rate != self.sent_mg_rate:
            d.append((A_MG_RATE, self.mg_rate, "MG_RATE"))
        if self.g_ctrl != self.sent_g_ctrl:
            d.append((A_G_CTRL, self.g_ctrl, "G_CTRL"))
        return d

    # ---- the sender: one unit of work per call (no lock held during a transaction) -----------------
    def _status(self):
        r = self._ops([("Q", a, f"status {n}") for a, n in STATUS])
        st = {n: x[1] for (a, n), x in zip(STATUS, r) if x[0] == "OK"}
        self.status = st
        self.last_status = time.monotonic()
        self.counts["status"] += 1
        if "APPLIED_SEQ" in st:
            self._check_applied(st["APPLIED_SEQ"])
        return st

    def _check_applied(self, applied):
        if self.pending and seq_reached(applied, self.pending[0]):
            seq, item, t1, note = self.pending
            self.pending = None
            self.go_lat.append(time.monotonic() - t1)
            self._rec(("APPLY", f"GO {seq} applied ({note})"))
            if item == "origin":
                self._resync("after the test origin")

    def step(self):
        """One unit of work: a master write, a status poll, an APPLIED_SEQ poll, a one-shot action or
        one item's GO. Returns True if a transaction was made. Call from one thread only."""
        now = time.monotonic()
        # 1. the master knobs: no GO, latest value wins
        with self.lock:
            md = self._master_diff()
        if md:
            r = self._ops([("W", a, d & M32, n) for a, d, n in md])
            with self.lock:
                for (a, d, n), x in zip(md, r):
                    if x[0] == "OK" and not x[2]:
                        if a == A_MG_TARGET: self.sent_mg_target = d
                        elif a == A_MG_RATE: self.sent_mg_rate = d
                        else: self.sent_g_ctrl = d
                        self.counts["master"] += 1
                    elif x[0] == "OK" and d == {A_MG_TARGET: self.mg_target, A_MG_RATE: self.mg_rate}.get(a, self.g_ctrl):
                        # refused: the knob goes back to what the switch holds (not written again and again)
                        if a == A_MG_TARGET: self.mg_target = self.sent_mg_target
                        elif a == A_MG_RATE: self.mg_rate = self.sent_mg_rate
                        else: self.g_ctrl = self.sent_g_ctrl
            return True
        # 2. the status: every 250 ms; at most one poll between knob GOs
        with self.lock:
            knob = self._knob_work()
        if now - self.last_status >= STATUS_PERIOD and (self.status_due_ok or not knob):
            self._status()
            self.status_due_ok = False
            return True
        # 3. a GO of this controller pending: poll APPLIED_SEQ
        if self.pending:
            if now - self.pending[2] > PENDING_TIMEOUT:
                seq, item, _, note = self.pending
                self._note_err(f"GO {seq} ({note}) not applied in {PENDING_TIMEOUT} s")
                self.pending = None
                self._resync("a GO not applied")
                return True
            self._check_applied(self._read(A_APPLIED, "APPLIED_SEQ poll"))
            return True
        # 4. one-shot actions (no GO of ours pending)
        with self.lock:
            what = self.oneshots.pop(0) if self.oneshots else None
        if what:
            if what[0] == "origin":
                g0 = self._read(A_GO_SEQ, "GO_SEQ before the test origin")
                x = self._ops([("W", A_ORIGIN, 1, "TEST_ORIGIN")])[0]
                if x[0] == "OK" and not x[2]:
                    # the ROM plays its list, ending in GO_ALL: GO g0 + 1
                    self.pending = ((g0 + 1) & M32, "origin", time.monotonic(), "test origin")
            return True
        # 5. one item's difference, round-robin, if the switch would accept its GO
        if now < self.hold_until:
            return False
        with self.lock:
            pick = None
            for it in sorted(self.pending_items(), key=lambda i: (i - self.rr) % 9):
                m = self._block_mask(it) if it < 8 else 0
                if self._go_ok(it, m):
                    pick = (it, m)
                    break
        if pick is None:
            return False              # nothing differs, or nothing can go yet
        self._send_item(*pick)
        self.rr = (pick[0] + 1) % 9
        self.status_due_ok = True
        return True

    def _knob_work(self):
        return bool(self.pending_items()) and not self.pending

    def _send_item(self, it, m):
        with self.lock:                                   # a snapshot of the desired state
            if it == 8:
                play = list(self.play)
                steps = [("W", A_SWEEP, MU.sweep_word(play), f"SWEEP {play}"),
                         ("W", A_SWEEP_COMMIT, MU.GONOW, "SWEEP_COMMIT go-now")]
                note = f"sweep {play}"
            else:
                v = block_slots(self.params[it])
                rt = int(self.params[it]["route"]) & 3
                kind = ("seed" if m == FULL else
                        "+".join(n for n, g in GROUPS if m & g) + ("+route" if m & MU.RT_BIT else ""))
                note = f"block {it} {kind.strip('+')}"
                steps = MU.stage(it, v, rt=rt, mask=m, arm=False, note=note)
                steps[-1] = ("W", 0x288 + it, m | MU.GONOW, f"{note} COMMIT[{it}] go-now")
        steps.append(("Q", A_GO_SEQ, "GO_SEQ of this GO"))
        r = self._ops(steps)
        t1 = time.monotonic()
        fired = len(r) == len(steps) and all(x[0] == "OK" and not x[2] for x in r[:-1])
        if not fired:
            # nothing fired (stopped at the refusal or error): the switch still holds the sent state;
            # wait a little before trying again (a refusal is a defect of this controller)
            with self.lock:
                if it < 8:
                    self.force_seed[it] = True
            self.hold_until = t1 + 0.5
            return
        seq = r[-1][1] if r[-1][0] == "OK" else self._read(A_GO_SEQ, "GO_SEQ of this GO (again)")
        self.counts["gos"] += 1
        self.pending = (seq, it, t1, note)
        with self.lock:
            if it == 8:
                self.sent_play = play
            else:
                if self.sent_slots[it] is None or m == FULL:
                    self.sent_slots[it] = list(v)
                else:
                    for i in range(16):
                        if m >> i & 1:
                            self.sent_slots[it][i] = v[i]
                if m & MU.RT_BIT:
                    self.sent_rt[it] = rt
                if m & 1:
                    self.sent_N[it] = v[0]
                self.force_seed[it] = False

    # ---- running ---------------------------------------------------------------------------------------
    def run_until_idle(self, timeout=60.0):
        """Step until nothing differs and no GO is pending (headless use). True if idle in time."""
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            if not self.step() and not self.busy():
                return True
        return False

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="wpms_ctl sender", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                if not self.step():
                    time.sleep(0.002)
            except IsspError as e:
                with self.lock:
                    self._note_err(f"ISSP: {e}")
                time.sleep(0.1)
            except (BridgeError, OSError) as e:
                with self.lock:
                    self.state = f"lost: {e}"
                    self._note_err(str(e))
                return


# ---- command line: scripted use and the board's measurements ---------------------------------------
def storm(ctl, moves, rng, blocks, settle=True, dt=0.0):
    """Random knob moves on several blocks, as fast as a script can (desired state only)."""
    nmax = ctl.nmax
    for k in range(moves):
        b = rng.choice(blocks)
        r = rng.random()
        if r < 0.35:
            ctl.set_block(b, level=rng.uniform(-40, -3))
        elif r < 0.6:
            ctl.set_block(b, f=rng.uniform(150, 2000))
        elif r < 0.7:
            ctl.set_block(b, df=2 ** rng.uniform(-6, 0))
        elif r < 0.78:
            ctl.set_block(b, gamma=rng.uniform(1e-5, min(1e-3, gamma_max(ctl.params[b]["N"]))))
        elif r < 0.83:
            ctl.set_block(b, glide=rng.choice([20, 60, 200, 1000]))
        elif r < 0.88:
            ctl.set_block(b, route=rng.choice([1, 2, 3]))
        elif r < 0.93:
            ctl.set_block(b, N=rng.randrange(N_MIN, max(N_MIN + 1, nmax // len(blocks) + 1)))
        elif r < 0.97:
            ctl.set_play(b, b not in ctl.play)
        else:
            ctl.set_master_db(rng.uniform(-30, 0))
        if dt:
            time.sleep(dt)
        else:
            ctl.step()                          # a hand never outruns the sender by more than this
    if settle:
        return ctl.run_until_idle(120)
    return True


def main():
    ap = argparse.ArgumentParser(description="wpms_ctl: the controller of the WPMS host GUI (OUTSIDE WPMS)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=50707)
    ap.add_argument("cmd", choices=("ping", "status", "storm", "measure"))
    ap.add_argument("--moves", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--blocks", default="0,1,2,3")
    ap.add_argument("--n", type=int, default=1000, help="measure: single transactions timed")
    ap.add_argument("--seconds", type=float, default=60.0, help="measure: knob storm duration")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--shutdown", action="store_true", help="stop the bridge at the end")
    a = ap.parse_args()
    ctl = Controller(a.host, a.port).connect()
    print(f"wpms_ctl: ID {ctl.id:08X}, CONFIG {ctl.config:08X} (NMAX {ctl.nmax}); sweep {ctl.sent_play}, "
          f"N {[ctl.sent_N[b] for b in ctl.sent_play]}")
    try:
        if a.cmd == "status":
            for k, v in ctl._status().items():
                print(f"  {k:15s} {v:08X}")
        elif a.cmd == "storm":
            blocks = [int(x) for x in a.blocks.split(",")]
            rej0 = ctl._status()["REJECT0"]
            ok = storm(ctl, a.moves, random.Random(a.seed), blocks)
            rej1 = ctl._status()["REJECT0"]
            print(f"wpms_ctl storm: {a.moves} moves on blocks {blocks}: {ctl.counts['gos']} GOs, idle {ok}, "
                  f"REJECT0 {rej0} -> {rej1}, refused {ctl.counts['refused']}, errors {ctl.counts['errors']}")
        elif a.cmd == "measure":
            measure(ctl, a)
    finally:
        if a.log:
            print(f"wpms_ctl: {ctl.save_log(a.log)} steps -> {a.log}")
        ctl.close(shutdown=a.shutdown)


def histogram(t_us, edges_ms=(1, 2, 5, 10, 20, 30, 50, 100)):
    """[(label, count)] of transaction times in ms."""
    rows, lo = [], 0
    for hi in list(edges_ms) + [None]:
        n = sum(1 for x in t_us if lo * 1000 <= x < (hi * 1000 if hi else float("inf")))
        rows.append((f"{lo} … {hi} ms" if hi else f">= {lo} ms", n))
        lo = hi
    return rows


def measure(ctl, a):
    """GUI brief §7: one ISSP transaction (mean/max over n), master-gain and block-level update rates,
    REJECT[0] before and after a knob storm on four blocks (set up here: blocks 0-3, N = 240 each, -6 dB)."""
    t = []
    for k in range(a.n):
        x = ctl._ops([("Q", A_ID, "timing: ID")])[0]
        if x[0] == "OK":
            t.append(x[3])
    t.sort()
    print(f"  M1 ISSP read of ID x{len(t)}: mean {sum(t) / len(t) / 1000:.2f} ms, median {t[len(t) // 2] / 1000:.2f}, "
          f"p99 {t[int(len(t) * 0.99)] / 1000:.2f}, max {t[-1] / 1000:.2f} ms (bridge-measured)")
    for lab, n in histogram(t):
        print(f"     {lab:>14s}  {n}")
    # M2: the master gain, as fast as the sender goes (no GO)
    t0 = time.monotonic()
    n0 = ctl.counts["master"]
    while time.monotonic() - t0 < min(10.0, a.seconds):
        ctl.set_master_db(-random.uniform(0, 12))
        ctl.step()
    dt = time.monotonic() - t0
    ctl.set_master_db(0)
    ctl.run_until_idle(10)
    print(f"  M2 master gain: {ctl.counts['master'] - n0} updates in {dt:.1f} s = {(ctl.counts['master'] - n0) / dt:.1f} /s")
    # four blocks playing: block 0 shrinks first, then 1-3 join (the controller finds the order)
    blocks = [0, 1, 2, 3]
    for b in blocks:
        why = ctl.set_block(b, N=240, level=-6.0)
        if why:
            print(f"  setup block {b}: {why}")
    for b in blocks:
        why = ctl.set_play(b, True)
        if why:
            print(f"  setup play {b}: {why}")
    ctl.run_until_idle(60)
    print(f"  four blocks: play {ctl.play}, switch {ctl.sent_play}")
    # M3: block levels on four blocks for a.seconds
    rej0 = ctl._status()["REJECT0"]
    g0, l0, p0 = ctl.counts["gos"], len(ctl.go_lat), sum(1 for e in ctl.log if e["step"][-1] == "APPLIED_SEQ poll")
    rng = random.Random(a.seed)
    t0 = time.monotonic()
    while time.monotonic() - t0 < a.seconds:
        ctl.set_block(rng.choice(blocks), level=rng.uniform(-30, -6))
        ctl.step()
    ctl.run_until_idle(30)
    dt = time.monotonic() - t0
    rej1 = ctl._status()["REJECT0"]
    ng = ctl.counts["gos"] - g0
    polls = sum(1 for e in ctl.log if e["step"][-1] == "APPLIED_SEQ poll") - p0
    lat = sorted(ctl.go_lat[l0:]) or [0]
    print(f"  M3 block level on {blocks}: {ng} GOs in {dt:.1f} s = {ng / dt:.1f} /s; APPLIED_SEQ polls per GO "
          f"{polls / max(1, ng):.2f}; GO -> apply seen: median {lat[len(lat) // 2] * 1000:.1f} ms, "
          f"max {lat[-1] * 1000:.1f} ms")
    print(f"  M4 REJECT0 {rej0} -> {rej1} (unchanged expected); refused {ctl.counts['refused']}, "
          f"errors {ctl.counts['errors']}")
    st = ctl.time_stats()
    print(f"  all transactions: n {st['n']}, mean {st['mean'] / 1000:.2f} ms, max {st['max'] / 1000:.2f} ms")
    for lab, n in histogram(ctl.times):
        print(f"     {lab:>14s}  {n}")
    if a.csv:
        ctl.save_times_csv(a.csv)
        print(f"  times -> {a.csv}")

if __name__ == "__main__":
    main()
