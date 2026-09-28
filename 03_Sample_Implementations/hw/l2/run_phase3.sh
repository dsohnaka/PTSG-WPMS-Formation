#!/usr/bin/env bash
# ============================================================================
#  run_phase3.sh — Phase 3 of SILICON_BRIEF_2026-09-27: sequencer and
#  integration (Core RH031p + Formation + sweep sequencer, running a score).
#  Reproduces every Phase 3 result (evidence class RTL-SIM, Icarus Verilog
#  -g2012) and exits non-zero if any expectation fails.
#  License: MIT (Layer 3).
# ----------------------------------------------------------------------------
#  1. Regression: the Phase 2 recipe (datapath cosimulation, mutants, score
#     round trip) on the current RTL.
#  2. The scores assemble to the committed images; the housekeeping dispatch
#     program is CLEAN for the validator and computes TAIL_BASE + 16 P.
#  3. The L2 top compiles clean.
#  4. R2 probe (Hook A): queued Base Set + Loop — gap-free, literal count only.
#  5. Sweep-level cosimulation against sweep_sim.py (via sweep_dump.py):
#       R1 dispatch form, 100 MHz budget (NMAX 2048, T_min 2083), seeds 2026, 7, 42
#       R1 dispatch form,  50 MHz budget (NMAX 1024, T_min 1041), seeds 2026, 7, 42
#       R1 branch form,   100 MHz budget, seed 2026
#     each with the directed cases (packet floor; EW2..EW6 injected: L1
#     silenced at once, the Core halted at the trap word);
#       R1 branch form,    50 MHz budget — informative: it does not fit.
#  6. The sweep-level mutants: every defect caught.
#  Usage: hw/l2/run_phase3.sh [EVIDENCE_DIR]
#         SAMPLES=<n> (default 12000 per seed); BUILD=<dir> (default hw/l2/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-28       Claude Code   Add : First version (Phase 3).
# ============================================================================
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
HW=$(cd "$HERE/.." && pwd)
S3=$(cd "$HW/.." && pwd)
TOOLS=$HW/tools
GOLD=$S3/tools
WS=${WS:-$(cd "$S3/../.." && pwd)}
IMEM=$WS/PTSG-Core/03_Sample_Implementations/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
BUILD=${BUILD:-$HERE/build}
SAMPLES=${SAMPLES:-12000}
EVID=${1:-}
LOGS=$BUILD/logs3; mkdir -p "$LOGS"
: > "$LOGS/run_phase3.txt"
FAIL=0
say()   { printf '%s\n' "$*" | tee -a "$LOGS/run_phase3.txt"; }
check() { if [ "$1" -eq 0 ]; then say "  [PASS] $2"; else say "  [FAIL] $2"; FAIL=1; fi; }

say "run_phase3: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $( (iverilog -V 2>&1 || true) | sed -n 1p ); $(python3 -V 2>&1); $SAMPLES samples per seed"

# ---- 1. Phase 2 regression --------------------------------------------------------
BUILD=$BUILD/phase2 "$HERE/run_phase2.sh" > "$LOGS/phase2_regression.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/phase2_regression.log")"
check $r "Phase 2 regression (datapath cosimulation, mutants, score round trip) on the current RTL"

# ---- 2. scores and the dispatch program ---------------------------------------------
mkdir -p "$BUILD/scores3"; r=0
for s in wpms_r1d wpms_r1b; do
    python3 "$TOOLS/score_as.py" "$HERE/scores/$s.score" -o "$BUILD/scores3/$s" >> "$LOGS/score_as3.log" 2>&1 || r=1
    for e in hex mif; do cmp -s "$BUILD/scores3/$s.$e" "$HERE/scores/$s.$e" || { say "    $s.$e differs from the committed image"; r=1; }; done
done
say "  $(tr '\n' ';' < "$LOGS/score_as3.log" | sed 's#/[^ ;]*/##g')"
check $r "score_as.py: wpms_r1d and wpms_r1b equal the committed .hex/.mif"
( cd "$GOLD" && python3 -c "
import json, pfasm_tools_w as T
isa = json.load(open('isa_table_w.json'))
p = T.parse('$HERE/programs/wpms_housekeeping_dispatch.pfasm')
v = T.validate(p, isa)
got = []
for P in range(9):
    mc = T.Machine(); mc.store[0::16] = [64] * 8
    mc.sweep_staged = T.make_sweep(list(range(P))); mc.sweep_armed = mc.take_sweep = True; mc.q = 0
    mc.run(p, 'HK'); got.append(mc.accm)
ok = not v and got == [0x300 + 16 * P for P in range(9)]
print('validate', v or 'CLEAN', '; JumpVal for P = 0..8:', ' '.join('0x%03X' % g for g in got))
raise SystemExit(0 if ok else 1)
" ) > "$LOGS/dispatch_program.log" 2>&1; r=$?
say "  $(cat "$LOGS/dispatch_program.log")"
check $r "wpms_housekeeping_dispatch.pfasm: CLEAN; the model computes TAIL_BASE + 16 P (ORACLE)"

# ---- 3. compile -----------------------------------------------------------------------
iverilog -g2012 -Wall -I "$HERE" -o "$BUILD/l2tb_check.vvp" -s wpms_l2_tb "$HERE/wpms_l2_tb.v" "$HERE/wpms_l2_top.v" \
    "$HW/core/ptsg_core_rh031p.v" "$IMEM" "$HERE/wpms_formation.v" "$HERE/wpms_sequencer.v" > "$LOGS/compile3.log" 2>&1; r=$?
other=$(grep -v "sensitive to all\|coerced to inout\|timescale\|time unit\|time precision\|Affected design\|declared here" "$LOGS/compile3.log" | grep -c . || true)
say "  iverilog -Wall: $(grep -c "sensitive to all" "$LOGS/compile3.log") '@* sensitive' notes, $(grep -c "coerced to inout" "$LOGS/compile3.log") tri0-port note(s), $other other lines"
[ "$r" -eq 0 ] && [ "$other" -eq 0 ]; check $? "wpms_l2_top + Core copy + Formation + sequencer + testbench compile"

# ---- 4. R2 probe ----------------------------------------------------------------------------
python3 "$TOOLS/r2_probe.py" --out "$BUILD/r2_probe" > "$LOGS/r2_probe.log" 2>&1; r=$?
sed -n '2,3p' "$LOGS/r2_probe.log" | tee -a "$LOGS/run_phase3.txt"
check $r "R2 probe: queued Base Set + Loop re-enters gap-free with a literal count; no data-driven count (SD-04)"

# ---- 5. sweep-level cosimulation -----------------------------------------------------------
run_cs() {   # name, args...
    local name=$1; shift
    python3 "$TOOLS/cosim_sweep.py" "$@" --out "$BUILD/cosim_sweep" --report "$LOGS/$name.txt" > "$LOGS/$name.log" 2>&1
    local r=$?
    grep -E "^  (total|T_wake|g |housekeeping|sweep length|floor)" "$LOGS/$name.txt" | sed "s/^/  [$name] /" | tee -a "$LOGS/run_phase3.txt"
    return $r
}
run_cs cs_r1d_100 --score r1d --samples "$SAMPLES" --seeds 2026,7,42 --nmax 2048 --tmin 2083 --directed; r=$?
check $r "R1 dispatch form, 100 MHz budget: every bundle, N, K sequence and stay_value as the oracle; errors silence L1"
run_cs cs_r1d_50 --score r1d --samples "$SAMPLES" --seeds 2026,7,42 --nmax 1024 --tmin 1041 --directed; r=$?
check $r "R1 dispatch form, 50 MHz budget (NMAX 1024, T_min 1041): as above, every sweep fits"
run_cs cs_r1b_100 --score r1b --samples "$SAMPLES" --seeds 2026 --nmax 2048 --tmin 2083 --directed; r=$?
check $r "R1 branch form, 100 MHz budget: as above (T_wake 3, g 1)"
run_cs cs_r1b_50 --score r1b --samples 3000 --seeds 2026 --nmax 1024 --tmin 1041 --allow-overrun; r=$?
say "  [cs_r1b_50] $(grep -o 'sweeps longer than T_min: [0-9]*' "$LOGS/cs_r1b_50.txt") (informative: the branch form does not fit 50 MHz at NMAX 1024)"
check $r "R1 branch form, 50 MHz budget: bundles as the oracle (overruns reported, not failed)"

# ---- 6. sweep-level mutants ---------------------------------------------------------------------
python3 "$TOOLS/cosim_sweep_mutants.py" --out "$BUILD/sweep_mutants" > "$LOGS/cosim_sweep_mutants.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/cosim_sweep_mutants.log")"
check $r "cosim_sweep_mutants.py: every deliberate defect in the sequencer / Formation is caught"

if [ "$FAIL" -eq 0 ]; then say "run_phase3: ALL PHASE 3 CHECKS PASSED"; else say "run_phase3: SOME CHECKS FAILED"; fi
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs"
    for f in run_phase3.txt score_as3.log dispatch_program.log compile3.log r2_probe.log cosim_sweep_mutants.log \
             cs_r1d_100.txt cs_r1d_50.txt cs_r1b_100.txt cs_r1b_50.txt; do
        [ -f "$LOGS/$f" ] && cp "$LOGS/$f" "$EVID/logs/"
    done
    cp "$BUILD/phase2/logs/run_phase2.txt" "$EVID/logs/phase2_regression.txt" 2>/dev/null
fi
exit $FAIL
