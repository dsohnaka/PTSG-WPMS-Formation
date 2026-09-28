#!/usr/bin/env python3
# ============================================================================
# sweep_dump.py — the brief's "--dump mode of sweep_sim.py", done WITHOUT
# editing the golden model: sweep_sim.py is imported and run unchanged (its own
# main(), its own GO traffic and checks); its Sequencer class is replaced, for
# the run, by a subclass that only RECORDS:
#   * at every strobe, the input-switch side of the machine as the writer left
#     it for that sample — inbox contents, COMMIT masks and armed bits, staged
#     RT.OUT, staged sweep word and its armed bit;
#   * for every packet the sweep plays, the block, the eight-word bundle L1
#     latches (as the oracle computes it) and N (the block's slot 0, which no
#     window writes and which is what the sequencer prefetched).
# The oracle's own verdict (L1 bundle mismatches vs the reference written from
# the customer's semantics, machine/sequencer errors) is kept with the dump.
#
#   python3 sweep_dump.py OUT.json [--oracle wpms_layer1_oracle.py] [--samples N]
#                         [--seed S] [--nmax 2048]
#
# --nmax other than 2048 overrides the profile constant NMAX of the golden
# modules for this run only (the 50 MHz target, ruling 2026-09-28); the files
# are not touched. License: MIT (Layer 3). Evidence class: ORACLE.
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF Phase 3).
# ============================================================================
import argparse, contextlib, io, json, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, TOOLS)
import pfasm_tools_w as T
import sweep_sim as SS


class Recorder(SS.Sequencer):
    """The golden Sequencer, unchanged in behaviour; it only writes things down."""
    last = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.samples = []
        Recorder.last = self

    def strobe(self):
        mc = self.mc
        self.samples.append(dict(
            switch=dict(inbox=[[T.s32(v) & 0xFFFFFFFF for v in row] for row in mc.inbox],
                        commit=[int(c) & 0x1FFFF for c in mc.commit], armed=[bool(x) for x in mc.armed],
                        rtout=[int(r) & 0xFFFF for r in mc.rtout_staged],
                        sweep_staged=int(mc.sweep_staged), sweep_armed=bool(mc.sweep_armed)),
            N=[mc.store[b * 16] for b in range(T.BLOCKS)], packets=[]))
        super().strobe()

    def sweep(self):
        obs = super().sweep()
        rec = self.samples[-1]
        rec["packets"] = [dict(block=b, bundle=list(bun), N=rec["N"][b]) for b, bun in obs]
        return obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--oracle", default="")
    ap.add_argument("--samples", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--nmax", type=int, default=T.NMAX)
    a = ap.parse_args()
    if a.nmax != T.NMAX:
        T.NMAX = a.nmax                         # run-time override; pfasm_tools_w.Machine reads it as a global
    SS.Sequencer = Recorder                     # sweep_sim.main() builds its sequencer by this name
    cwd = os.getcwd()
    os.chdir(TOOLS)                             # sweep_sim.main() opens its files relative to tools/
    out = io.StringIO()
    code = 0
    try:
        sys.argv = ["sweep_sim.py", a.oracle or "-", str(a.samples), str(a.seed)]
        with contextlib.redirect_stdout(out):
            SS.main()
    except SystemExit as e:
        code = e.code or 0
    finally:
        os.chdir(cwd)
    rec = Recorder.last
    text = out.getvalue()
    dump = dict(provenance=dict(tool="sweep_sim.py (unchanged) via sweep_dump.py", seed=a.seed, samples=a.samples,
                                nmax=T.NMAX, n_min=T.N_MIN, oracle=os.path.basename(a.oracle) if a.oracle else "local CR5-L1",
                                oracle_exit=code, oracle_output=text.strip().splitlines()),
                samples=rec.samples)
    json.dump(dump, open(a.out, "w"))
    npk = sum(len(s["packets"]) for s in rec.samples)
    full = sum(1 for s in rec.samples if sum(p["N"] for p in s["packets"]) == T.NMAX)
    print(text.rstrip())
    print(f"sweep_dump: {len(rec.samples)} samples, {npk} packets ({full} full-load sweeps, NMAX {T.NMAX}) -> {a.out}; "
          f"oracle exit {code}")
    sys.exit(code)


if __name__ == "__main__":
    main()
