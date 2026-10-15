# board_stats.py — the numbers of reports/gui_board.md recomputed from the step logs and times (python3 board_stats.py)
import gzip, json, csv, statistics as st, sys
import os
E = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EDGES = (0.5, 1, 2, 5, 10, 20, 30)
def hist(us):
    rows, lo = [], 0
    for hi in list(EDGES) + [None]:
        n = sum(1 for x in us if lo * 1000 <= x < (hi * 1000 if hi else 1e18))
        rows.append((f"{lo} … {hi} ms" if hi else f"≥ {lo} ms", n)); lo = hi
    return rows
def desc(us, name):
    s = sorted(us); n = len(s)
    print(f"{name}: n {n}, mean {st.mean(s)/1000:.3f} ms, median {s[n//2]/1000:.3f}, p90 {s[int(n*.9)]/1000:.3f}, "
          f"p99 {s[int(n*.99)]/1000:.3f}, max {s[-1]/1000:.3f} ms, min {s[0]/1000:.3f}")
    for lab, c in hist(s): print(f"   {lab:>12s} {c:7d} {100*c/n:6.2f} %")
def load(f):
    d = json.load(gzip.open(f, "rt")); return d, d["steps"], d["t_us"], d["replies"]
def is_go(s): return s[0] == "W" and (0x288 <= s[1] <= 0x28F or s[1] == 0x291) and (s[2] >> 31) & 1

print("=== board_measure ===")
d, S, T, R = load(f"{E}/step_logs/board_measure.json.gz")
m1 = [r[3] for s, r in zip(S, R) if s[-1] == "timing: ID" and r and r[0] == "OK"]
assert all(r[1] == 0x57504D53 for s, r in zip(S, R) if s[-1] == "timing: ID")
desc(m1, "M1 ID reads")
mi = [i for i, s in enumerate(S) if s[0] == "W" and s[1] == 0x10]
print(f"M2 master writes {len(mi)}: t {T[mi[0]]/1e6:.3f} .. {T[mi[-1]]/1e6:.3f} s -> {(len(mi)-1)/((T[mi[-1]]-T[mi[0]])/1e6):.1f} /s")
# master write transaction times
desc([R[i][3] for i in mi], "   their write times")
# setup: sweep commits
sw = [(i, T[i]/1e6, S[i][3]) for i, s in enumerate(S) if s[0] == "W" and s[1] == 0x290]
print("SWEEP writes:", sw)
gos = [i for i, s in enumerate(S) if is_go(s)]
lev = [i for i in gos if "level" in S[i][3] and i > sw[-1][0]]
t0, t1 = T[lev[0]], T[lev[-1]]
print(f"M3 level GOs after setup {len(lev)}: {t0/1e6:.3f} .. {t1/1e6:.3f} s -> {(len(lev)-1)/((t1-t0)/1e6):.1f} /s; blocks",
      sorted(set(S[i][1] & 7 for i in lev)))
win = [i for i in range(lev[0], len(S)) if T[i] <= t1]
polls = sum(1 for i in win if S[i][-1] == "APPLIED_SEQ poll")
stat = sum(1 for i in win if S[i][-1] == "status GO_SEQ")
print(f"   APPLIED_SEQ polls {polls} -> per GO {polls/len(lev):.3f}; status polls in window {stat}")
# latency: R 009 record after the COMMIT -> APPLY record
lat = []; ap = [i for i, s in enumerate(S) if s[0] == "APPLY"]
import bisect
for i in lev:
    j = ap[bisect.bisect_left(ap, i)]
    lat.append(T[j] - T[i])
desc(lat, "   GO recorded -> APPLY recorded (one round trip + poll)")
# per GO total time: consecutive level GOs
dt = [T[b] - T[a] for a, b in zip(lev, lev[1:])]
desc(dt, "   interval between level GOs")
rj = [(T[i], R[i][1]) for i, s in enumerate(S) if s[0] == "Q" and s[1] == 0x30]
print(f"M4 REJECT0: {len(rj)} reads, first {rj[0][1]} at {rj[0][0]/1e6:.2f} s, last {rj[-1][1]} at {rj[-1][0]/1e6:.2f} s, max {max(v for _, v in rj)}")
print("refused", sum(1 for s, r in zip(S, R) if s[0]=="W" and r and r[2]), "errors", sum(1 for r in R if r and r[0] != "OK"))
print("CLIP nonzero", sum(1 for s, r in zip(S, R) if s[0]=="Q" and s[1]==0x16 and r[1]))
gseq = [r[1] for s, r in zip(S, R) if s[0]=="Q" and s[1]==9]; print("GO_SEQ first/last", gseq[0], gseq[-1])
allt = [int(r["us"]) for r in csv.DictReader(gzip.open(f"{E}/times/board_times.csv.gz", "rt"))]
desc(allt, "ALL transactions (board_times.csv)")
wr = [r[3] for s, r in zip(S, R) if s[0]=="W" and r]; rd = [r[3] for s, r in zip(S, R) if s[0]=="Q" and r and r[0]=="OK"]
desc(wr, "   writes"); desc(rd, "   reads")
print("duration", (T[-1]-T[0])/1e6)

print("\n=== GUI session ===")
d, S, T, R = load(f"{E}/step_logs/wpms_gui_20261015_195411.json.gz")
gos = [i for i, s in enumerate(S) if is_go(s)]
import collections
print("GOs", len(gos), collections.Counter(S[i][3].split(" COMMIT")[0] for i in gos))
print("duration", (T[-1]-T[0])/1e6, "s; GOs span", T[gos[0]]/1e6, T[gos[-1]]/1e6)
# busiest second
sec = collections.Counter(T[i]//1000000 for i in gos); print("busiest seconds", sec.most_common(5))
rj = [R[i][1] for i, s in enumerate(S) if s[0]=="Q" and s[1]==0x30]; print("REJECT0 max", max(rj), "reads", len(rj))
print("refused", sum(1 for s, r in zip(S, R) if s[0]=="W" and r and r[2]), "errors", sum(1 for r in R if r and r[0] != "OK"))
print("CLIP nonzero", sum(1 for s, r in zip(S, R) if s[0]=="Q" and s[1]==0x16 and r[1]))
mg = [(T[i]/1e6, R[i][1]) for i, s in enumerate(S) if s[0]=="Q" and s[1]==0x12]
pan = [T[i]/1e6 for i, s in enumerate(S) if s[0]=="W" and s[1]==0x10][0]
import math
def db(v): v = v - (1<<32) if v >> 31 else v; return v / 2**26 * 20*math.log10(2)
after = [(t - pan, round(db(v),1)) for t, v in mg if t >= pan]
print("PANIC at", pan, "MG after:", after[:30:2], "... last", after[-1])
allt = [int(r["us"]) for r in csv.DictReader(gzip.open(f"{E}/times/wpms_times_20261015_195429.csv.gz", "rt"))]
desc(allt, "ALL transactions (GUI times csv)")
