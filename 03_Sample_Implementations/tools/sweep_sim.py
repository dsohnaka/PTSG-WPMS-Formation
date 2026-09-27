#!/usr/bin/env python3
# ============================================================================
# sweep_sim.py — sweep-level oracle for the WPMS choreography (Deliverables 2, 3)
#
# Runs the real L2 window programs (wpms_packet.pfasm, wpms_housekeeping.pfasm)
# on the profile machine (pfasm_tools_w.Machine) under a model of the sweep
# sequencer, with random GO traffic (retunes, re-seeds, level glides, sweep
# changes, pauses), and compares what L1 latches at every packet start against
# a reference written from the customer's semantics (WPMS Ch.3 §3.4.3, Ch.5
# §5.3-5.4). The level-glide law is taken from the customer's own oracle
# (wpms_layer1_oracle.py: step_toward) when its path is given.
#
#   python3 sweep_sim.py [path/to/wpms_layer1_oracle.py] [samples] [seed]
# License: MIT (Layer 3). Illustrative — evidence class ORACLE, not silicon.
# ============================================================================
import json, random, sys, importlib.util
import pfasm_tools_w as T

M32 = 1 << 32
S = dict(N=0x0, TAG=0x1, LP=0x2, LAD1=0x3, LAD2=0x4, LE0=0x5, PH0=0x6, PHD1=0x7, PHD2=0x8,
         LPT=0x9, OM0=0xA, OMD1=0xB, OMD2=0xC, RT=0xE, LS0=0xF)
PRESETS = {"RETUNE": 0x9E3B | 1 << 16, "RESEED": 0x9FFF | 1 << 16, "LEVEL": 0x0220,
           "PITCH": 0x1C00, "PHASE_RESET": 0x01C0}
T_WAKE, CTRL, T_HK_CTRL = 2, 4, 3      # Core-side clocks (nominal; Core-owned, measured in Layer 4)

def load_step_toward(path):
    if path:
        spec = importlib.util.spec_from_file_location("cust", path); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return m.step_toward, "customer oracle"
    return (lambda LP, LPT, LE0: LP + max(-LE0, min(LE0, LPT - LP))), "local copy of CR5-L1"

def u(v): return v % M32
def bundle_of(slots): return tuple(u(slots[i]) for i in T.BUNDLE_SLOTS)

class Sequencer:
    def __init__(self, mc, pkt, hk):
        self.mc, self.pkt, self.hk = mc, pkt, hk
        self.bun_s = self.stay_s = None
        self.errors, self.max_sweep, self.max_bcp = [], 0, 0
    def prefetch(self, b):
        N = self.mc.store[b * 16]
        if not (T.N_MIN <= N <= T.NMAX): self.errors.append(f"EW2 N={N} in block {b}")
        self.bun_s, self.stay_s = bundle_of(self.mc.store[b * 16:b * 16 + 16]), N
    def strobe(self):                                   # take-set latched on the synchronized strobe
        mc = self.mc
        mc.take = {b for b in range(T.BLOCKS) if mc.armed[b]}
        mc.take_sweep, mc.copied, mc.sweep_copied, mc.inbox_taken = mc.sweep_armed, set(), False, False
    def sweep(self):
        mc = self.mc; w = mc.sweep_a; P = T.sweep_P(w); order = T.sweep_order(w)[:P]
        obs, clocks = [], T_WAKE
        for q, b in enumerate(order):
            live = bundle_of(mc.store[b * 16:b * 16 + 16])
            if self.bun_s != live: self.errors.append(f"stale bundle for block {b}")
            obs.append((b, self.bun_s)); N = self.stay_s   # L1 latches; Core reads stay_value = N
            if q + 1 < P: self.prefetch(order[q + 1])      # worst case: before this window writes
            mc.q = q
            L = mc.run(self.pkt, 'PKT', cur=b)
            if L + CTRL > N: self.errors.append(f"window overrun: L={L} N={N}")
            clocks += N
        mc.q = 0
        bcp = mc.run(self.hk, 'HK'); self.max_bcp = max(self.max_bcp, bcp)
        w2 = mc.sweep_a
        if T.sweep_P(w2): self.prefetch(T.sweep_order(w2)[0])
        clocks += bcp + T_HK_CTRL + 1                    # +1: first-bundle prefetch (slot-parallel)
        self.max_sweep = max(self.max_sweep, clocks)
        if clocks > 2083: self.errors.append(f"sweep overrun: {clocks} clocks")
        return obs

class Reference:                                        # the customer's semantics, written independently
    def __init__(self, step): self.blk = [[0] * 16 for _ in range(T.BLOCKS)]; self.sweep = 0; self.step = step
    def sample(self, go):
        P = T.sweep_P(self.sweep); order = T.sweep_order(self.sweep)[:P]; obs = []
        for b in order:
            s = self.blk[b]; obs.append((b, bundle_of(s)))
            s[S['PH0']] += s[S['OM0']]; s[S['PHD1']] += s[S['OMD1']]; s[S['PHD2']] += s[S['OMD2']]
            s[S['LP']] = self.step(s[S['LP']], s[S['LPT']], s[S['LE0']])
        if go:                                          # items taken at this strobe land for the next sweep
            for b, (mask, vals, rt) in go['blocks'].items():
                for i in range(16):
                    if i not in (13, 14) and (mask >> i) & 1: self.blk[b][i] = vals[i]
                if (mask >> 16) & 1: self.blk[b][S['RT']] = rt
            if go.get('sweep') is not None: self.sweep = go['sweep']
        return obs

def rand_block(rng, N):
    q26 = 1 << 26
    v = [0] * 16
    v[S['N']] = N; v[S['TAG']] = rng.randrange(1 << 16)
    v[S['LP']] = rng.randrange(-32 * q26, 0); v[S['LPT']] = rng.choice([-32 * q26, rng.randrange(-32 * q26, 0)])
    v[S['LE0']] = rng.choice([0, 13933, rng.randrange(0, q26 // 4)])
    for k in ('LAD1', 'LAD2', 'LS0'): v[S[k]] = rng.randrange(-(1 << 31), 1 << 31)
    for k in ('PH0', 'PHD1', 'PHD2', 'OM0', 'OMD1', 'OMD2'): v[S[k]] = T.s32(rng.randrange(M32))
    return v

def main():
    cust = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != '-' else None
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 12000
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 2026)
    step, src = load_step_toward(cust)
    isa = json.load(open("isa_table_w.json"))
    pkt, hk = T.parse("../instruction_lists/wpms_packet.pfasm"), T.parse("../instruction_lists/wpms_housekeeping.pfasm")
    assert not T.validate(pkt, isa) and not T.validate(hk, isa)
    mc = T.Machine(); sq = Sequencer(mc, pkt, hk); ref = Reference(step)
    stats = dict(go=0, reseed=0, retune=0, level=0, sweeps_changed=0, empty_sweeps=0, mismatches=0, played=0)
    pending = None
    for n in range(samples):
        # --- writer side (input switch): arm a GO now and then, only when nothing is frozen
        if pending is None and n and rng.random() < 0.02:             # full-load GO: sigma N = NMAX exactly
            P = rng.randrange(1, 9); order = rng.sample(range(T.BLOCKS), P)
            cuts = sorted(rng.sample(range(1, T.NMAX // T.N_MIN), P - 1)); parts = [b - a for a, b in zip([0] + cuts, cuts + [T.NMAX // T.N_MIN])]
            blocks = {}
            for b, k in zip(order, parts):
                vals = rand_block(rng, k * T.N_MIN); blocks[b] = (PRESETS["RESEED"], vals, rng.randrange(4))
                mc.inbox[b] = list(vals); mc.commit[b] = PRESETS["RESEED"]; mc.rtout_staged[b] = blocks[b][2]; mc.armed[b] = True
            sweep = T.make_sweep(order); mc.sweep_staged, mc.sweep_armed = sweep, True
            pending = dict(blocks=blocks, sweep=sweep); stats['go'] += 1; stats['reseed'] += P; stats['sweeps_changed'] += 1; stats['full'] = stats.get('full', 0) + 1
        if pending is None and (n == 0 or rng.random() < 0.06):
            blocks = {}
            nb = T.BLOCKS if n == 0 else rng.randrange(0, 4)
            for b in (range(T.BLOCKS) if n == 0 else rng.sample(range(T.BLOCKS), nb)):
                cur_N = mc.store[b * 16] or 64
                vals = rand_block(rng, cur_N if n else rng.randrange(T.N_MIN, 513))
                name = "RESEED" if n == 0 else rng.choice(list(PRESETS) + ["random"])
                mask = PRESETS[name] if name != "random" else rng.randrange(1 << 17)
                if n and rng.random() < 0.3 and (mask & 1):   # sometimes change N as well
                    vals[S['N']] = rng.randrange(T.N_MIN, 513)
                blocks[b] = (mask, vals, rng.randrange(4))
                stats['reseed'] += bool(mask & 0x01C4); stats['retune'] += bool(mask & 0x1C00); stats['level'] += bool(mask & 0x0220)
            sweep = None
            if n == 0 or rng.random() < 0.4:
                P = rng.randrange(0, 9); order = rng.sample(range(T.BLOCKS), P)
                # Sigma N of the listed blocks after this GO must fit (switch-side check, Ch.5 §5.4.4)
                Nof = lambda b: (blocks[b][1][S['N']] if b in blocks and blocks[b][0] & 1 else mc.store[b * 16])
                while order and sum(Nof(b) for b in order) > T.NMAX: order.pop()
                sweep = T.make_sweep(order); stats['sweeps_changed'] += 1
            # switch-side rule (Ch.5 §5.4.4): reject a GO whose sweep in effect would exceed NMAX
            eff = sweep if sweep is not None else mc.sweep_a
            Nnew = lambda b: (blocks[b][1][S['N']] if b in blocks and blocks[b][0] & 1 else mc.store[b * 16])
            if sum(Nnew(b) for b in T.sweep_order(eff)[:T.sweep_P(eff)]) > T.NMAX: blocks, sweep = {}, None
            if not blocks and sweep is None: continue_go = False
            else: continue_go = True
            for b, (mask, vals, rt) in (blocks.items() if continue_go else []):
                mc.inbox[b] = list(vals); mc.commit[b] = mask; mc.rtout_staged[b] = rt; mc.armed[b] = True
            if continue_go:
                if sweep is not None: mc.sweep_staged, mc.sweep_armed = sweep, True
                pending = dict(blocks=blocks, sweep=sweep); stats['go'] += 1
        # --- strobe: take-set latched; sweep runs; HK copies
        sq.strobe()
        go_now = pending if (mc.take or mc.take_sweep) else None
        got = sq.sweep(); want = ref.sample(go_now)
        stats['played'] += len(got); stats['empty_sweeps'] += (len(got) == 0)
        if got != want: stats['mismatches'] += 1
        if mc.inbox_taken and go_now:                      # switch: unfreeze, publish APPLIED
            for b in go_now['blocks']: mc.armed[b] = False
            mc.sweep_armed = False; pending = None
    errs = sorted(set(mc.errors + sq.errors))
    print(f"sweep_sim: {samples} samples, {stats['played']} packet plays, {stats['go']} GOs "
          f"(re-seed {stats['reseed']}, retune {stats['retune']}, level {stats['level']} items; {stats['sweeps_changed']} sweep words; "
          f"{stats['empty_sweeps']} empty sweeps, {stats.get('full', 0)} full-load GOs); glide law from {src}")
    print(f"  L1 bundle mismatches vs reference: {stats['mismatches']}   machine/sequencer errors: {errs or 'none'}")
    print(f"  per-packet window: {len(pkt)} instructions -> N_MIN = {len(pkt)} + {CTRL} = {len(pkt) + CTRL} (profile constant {T.N_MIN})")
    print(f"  BCP worst case: {sq.max_bcp} clocks;  worst sweep (Core nominals included): {sq.max_sweep} of 2083 clocks")
    sys.exit(1 if stats['mismatches'] or errs else 0)

if __name__ == "__main__":
    main()
