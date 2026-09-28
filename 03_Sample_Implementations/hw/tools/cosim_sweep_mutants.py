#!/usr/bin/env python3
# ============================================================================
# cosim_sweep_mutants.py — does the Phase 3 sweep-level cosimulation bite? Each
# mutant is one deliberate defect in a scratch copy of wpms_sequencer.v or
# wpms_formation.v (the files themselves are never touched); cosim_sweep.py runs
# against the copy (200 samples of seed 2026 plus the directed cases) and must
# FAIL. A mutant that passes is reported as SURVIVED.
#
#   python3 cosim_sweep_mutants.py [--out DIR]
#
# Evidence class: RTL-SIM (Icarus Verilog). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF Phase 3).
# ============================================================================
import argparse, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
L2 = os.path.normpath(os.path.join(HERE, "..", "l2"))

# (id, file, the defect, text, replacement, score)
MUTANTS = [
    ("S1", "wpms_sequencer.v", "prefetch the packet's own block instead of the next one",
     "pf_block <= order_of(sweep_a, q_r);      // q_r already counts this packet",
     "pf_block <= order_of(sweep_a, q_r - 4'd1);", "r1d"),
    ("S2", "wpms_sequencer.v", "stay_value follows StayVal.s (no second stage, W-F22)",
     "assign stay_value = stayval_p;", "assign stay_value = stayval_s;", "r1d"),
    ("S3", "wpms_sequencer.v", "K on the L1 face not delayed with the timing signals (SD-11)",
     "assign l1_k            = k_prev;", "assign l1_k            = stay_counter;", "r1d"),
    ("S4", "wpms_sequencer.v", "MORE lane off by one",
     "L_MORE:     condition = (q_r < P);", "L_MORE:     condition = (q_r <= P);", "r1b"),
    ("S5", "wpms_sequencer.v", "q not 0 in housekeeping (the dispatch reads the status view)",
     "assign seq_q      = pkt_now ? q_r : hk_now ? 4'd0 : (pkt_r ? qplay_r : 4'd0);",
     "assign seq_q      = pkt_now ? q_r : hk_now ? q_r : (pkt_r ? qplay_r : q_r);", "r1d"),
    ("S6", "wpms_sequencer.v", "the first bundle is prefetched before BCP's copy has landed",
     "end else if (hk_wait && inbox_taken) begin", "end else if (hk_wait) begin", "r1d"),
    ("S7", "wpms_sequencer.v", "L1 not silenced on error",
     "assign l1_bin_valid    = ts_pkt && !l1_mute;", "assign l1_bin_valid    = ts_pkt;", "r1d"),
    ("S8", "wpms_sequencer.v", "StayVal.p not cleared at the housekeeping Stay Set",
     "stayval_p <= 12'd0;                      // housekeeping: the literal applies",
     "stayval_p <= stayval_p;", "r1d"),
    ("S9", "wpms_sequencer.v", "NONEMPTY lane inverted",
     "L_NONEMPTY: condition = (P != 4'd0);", "L_NONEMPTY: condition = (P == 4'd0);", "r1b"),
    ("S10", "wpms_formation.v", "insert_req held through insert_ack (the Phase 3 fix undone)",
     "assign insert_req    = insert_req_r && !insert_ack;", "assign insert_req    = insert_req_r;", "r1d"),
    ("S11", "wpms_sequencer.v", "the Stay Set is taken from K alone (TS_PKT ignored: HK counted as a packet)",
     "wire        pkt_now = det && ts_pkt;", "wire        pkt_now = det;", "r1d"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(L2, "build", "sweep_mutants"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows, ok = [], True
    for mid, fname, what, old, new, score in MUTANTS:
        src = open(os.path.join(L2, fname)).read()
        n = src.count(old)
        if n != 1:
            rows.append((mid, what, f"STALE ({n})", "")); ok = False; continue
        d = os.path.join(a.out, mid); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, fname), "w").write(src.replace(old, new))
        rep = os.path.join(d, "summary.txt")
        r = subprocess.run([sys.executable, os.path.join(HERE, "cosim_sweep.py"), "--score", score, "--samples", "200",
                            "--seeds", "2026", "--directed", "--rtl", d, "--out", os.path.join(d, "run"), "--report", rep],
                           capture_output=True, text=True)
        text = open(rep).read() if os.path.exists(rep) else (r.stdout + r.stderr)
        first = next((l.strip()[5:] for l in text.splitlines() if l.strip().startswith("FAIL ")), "")
        killed = r.returncode != 0
        if not killed: ok = False
        rows.append((mid, what, "KILLED" if killed else "SURVIVED", first[:110]))
    print("cosim_sweep_mutants: one defect per scratch copy of the L2 RTL — evidence class RTL-SIM")
    for mid, what, verdict, first in rows:
        print(f"  {mid:4s} {verdict:9s} {what}  ->  {first}")
    print(f"cosim_sweep_mutants: {sum(r[2] == 'KILLED' for r in rows)}/{len(rows)} mutants killed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
