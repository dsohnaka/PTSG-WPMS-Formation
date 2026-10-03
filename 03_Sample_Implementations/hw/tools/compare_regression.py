#!/usr/bin/env python3
# ============================================================================
# compare_regression.py — a rerun of run_phase6.sh (Phases 2-6) against a
# recorded run: do the logs, the board runs' JSON and the expected captures
# repeat? Lines carrying the date, a duration or a path are normalised, the
# JSON's simulator run time is ignored and the VCDs are compared byte for
# byte ($date aside); every other difference is listed for the reader to
# explain. (SD-22: a restructure must repeat the record of 2026-10-01.)
#
#   python3 compare_regression.py --build BUILD_DIR --record EVIDENCE_DIR
#
# BUILD_DIR is run_phase6.sh's BUILD (REGRESSION=1); EVIDENCE_DIR a folder
# written by run_phase6.sh EVIDENCE_DIR (logs/, expected/).
# Evidence class: RTL-SIM (a comparison of RTL-SIM records). License: MIT.
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SD-22 step 1).
# ============================================================================
import argparse, difflib, gzip, json, os, re, sys

PAIRS = [("phase5/phase4/phase3/phase2/logs/run_phase2.txt", "logs/phase2_regression.txt"),
         ("phase5/phase4/phase3/logs3/run_phase3.txt", "logs/phase3_regression.txt"),
         ("phase5/phase4/logs4/run_phase4.txt", "logs/phase4_regression.txt"),
         ("phase5/logs5/run_phase5.txt", "logs/phase5_regression.txt"),
         ("logs6/run_phase6.txt", "logs/run_phase6.txt"),
         ("logs6/cosim_board.txt", "logs/cosim_board.txt"),
         ("logs6/check_host_tcl.txt", "logs/check_host_tcl.txt"),
         ("logs6/gen_inject_scores.log", "logs/gen_inject_scores.log"),
         ("logs6/make_quartus_project.log", "logs/make_quartus_project.log"),
         ("logs6/compile6.log", "logs/compile6.log")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--record", required=True)
    ap.add_argument("--workspace", default=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                          "..", "..", "..", "..")) + "/")
    a = ap.parse_args()
    build = os.path.abspath(a.build) + "/"

    def norm(text):
        text = text.replace(build, "<build>/").replace(a.workspace, "<workspace>/")
        out = []
        for l in text.splitlines():
            l = re.sub(r"\d{4}-\d\d-\d\dT[\d:]+Z", "<date>", l)
            l = re.sub(r"\b\d+(\.\d+)? s\b", "<t> s", l)
            l = re.sub(r"<workspace>/\S*/build/quartus", "<build>/quartus", l)
            out.append(l)
        return out

    total = 0
    for new, old in PAIRS:
        p, q = os.path.join(a.record, old), os.path.join(a.build, new)
        if not os.path.exists(p) or not os.path.exists(q):
            print(f"== {old}: missing ({'record' if not os.path.exists(p) else 'rerun'})"); total += 1; continue
        d = [l for l in difflib.unified_diff(norm(open(p).read()), norm(open(q).read()), lineterm="", n=0)
             if not l.startswith(("---", "+++", "@@"))]
        total += len(d)
        print(f"== {old}: {'identical' if not d else str(len(d)) + ' differing lines'}")
        for l in d:
            print("   " + l[:220])
    ej, nj = os.path.join(a.record, "expected"), os.path.join(a.build, "expected")
    names = sorted(os.listdir(ej))
    same = 0
    for f in names:
        p, q = os.path.join(ej, f), os.path.join(nj, f)
        if not os.path.exists(q):
            print(f"   missing in the rerun: {f}"); continue
        if f.endswith(".json"):
            x = json.loads(open(p).read())
            y = json.loads(open(q).read().replace(a.workspace, "<workspace>/"))
            for j in (x, y):
                j.get("observed", {}).pop("sim_seconds", None)       # the simulator's wall-clock time
            ok = x == y
        else:
            strip = lambda b: re.sub(rb"\$date.*?\$end", b"", b, flags=re.S)
            ok = strip(gzip.open(p).read()) == strip(gzip.open(q).read())
        same += ok
        if not ok:
            print(f"   DIFFERS: {f}")
    print(f"== expected/: {same} of {len(names)} identical (the JSON by value, the simulator's run time aside; "
          f"the VCD byte for byte, $date aside)")
    print(f"compare_regression: {'IDENTICAL' if total == 0 and same == len(names) else 'differences listed above'}")


if __name__ == "__main__":
    main()
