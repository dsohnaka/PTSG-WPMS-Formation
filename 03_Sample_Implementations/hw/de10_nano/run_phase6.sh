#!/usr/bin/env bash
# ============================================================================
#  run_phase6.sh — SILICON_BRIEF_2026-09-27 Phase 6: everything that can be
#  shown before the board, and the expected values the board must reproduce.
#  License: MIT (Layer 3). Evidence class of every result: RTL-SIM (Icarus
#  Verilog -g2012), except the checks marked "stand-in" (a plain tclsh or
#  Icarus standing in for Quartus: they prove the files, not the device).
#
#   1. Regression (REGRESSION=1, default): the Phase 5 recipe, which runs
#      Phase 4's, 3's and 2's — on wpms_system RH002 (the tap ports).
#   2. The injection images (gen_inject_scores.py --check): EW2-EW5 as score
#      images for the In-System Memory Content Editor.
#   3. The host scripts (check_host_tcl.py, tclsh): the Phase 5 cases and the
#      six Phase 6 scripts (first_go, full8, ew6 at NMAX 1,008 and 2,048).
#   4. The Quartus project (make_quartus_project.py --check): the .qpf, the
#      two revisions, the .sdc under tclsh stand-ins; the project's Verilog
#      elaborated with the INTEL branches and stand-in primitives.
#   5. Compile the board-level bench, iverilog -Wall: nothing from de10_nano.
#   6. The board-level cosimulation (cosim_board.py), both budgets: origin,
#      first_go, full8, ew6, ew2-ew5, pcm — the brief's eight evidence items
#      checked against their bounds and the models; each cut as its SignalTap
#      capture and read back (the expected captures, expected_*.vcd.gz).
#   7. The resource ledger's parser (resource_ledger.py --selftest).
#  Usage: hw/de10_nano/run_phase6.sh [EVIDENCE_DIR]
#         REGRESSION=0 skips step 1; BUILD=<dir> (default hw/de10_nano/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-10-01       Claude Code   Add : First version (Phase 6).
# ============================================================================
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
HW=$(cd "$HERE/.." && pwd)
TOOLS=$HW/tools
WS=${WS:-$(cd "$HW/../../.." && pwd)}
BUILD=${BUILD:-$HERE/build}
REGRESSION=${REGRESSION:-1}
EVID=${1:-}
LOGS=$BUILD/logs6; mkdir -p "$LOGS"
: > "$LOGS/run_phase6.txt"
FAIL=0
say()   { printf '%s\n' "$*" | tee -a "$LOGS/run_phase6.txt"; }
check() { if [ "$1" -eq 0 ]; then say "  [PASS] $2"; else say "  [FAIL] $2"; FAIL=1; fi; }

say "run_phase6: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $(iverilog -V 2>&1 | head -1); Python $(python3 -c 'import sys; print(sys.version.split()[0])')"

# ---- 1. regression -----------------------------------------------------------------------------------
if [ "$REGRESSION" = 1 ]; then
    BUILD=$BUILD/phase5 "$HW/switch/run_phase5.sh" > "$LOGS/phase5_regression.log" 2>&1; r=$?
    say "  $(tail -1 "$BUILD/phase5/logs5/run_phase5.txt")"
    say "  $(tail -1 "$BUILD/phase5/phase4/logs4/run_phase4.txt")"
    say "  $(grep 'run_phase3:' "$BUILD/phase5/phase4/phase3/logs3/run_phase3.txt" | tail -1)"
    say "  $(grep 'run_phase2:' "$BUILD/phase5/phase4/phase3/phase2/logs/run_phase2.txt" | tail -1)"
    check $r "regression: Phases 2-5 on wpms_system RH002"
fi

# ---- 2. injection images -----------------------------------------------------------------------------
python3 "$TOOLS/gen_inject_scores.py" --check > "$LOGS/gen_inject_scores.log" 2>&1; r=$?
check $r "injection images wpms_r1d_ew{2,3,4,5_1008,5_2048}.{score,pfasm,hex,mif} regenerate identically"

# ---- 3. host scripts ---------------------------------------------------------------------------------
if command -v tclsh8.6 > /dev/null 2>&1 || command -v tclsh > /dev/null 2>&1; then
    python3 "$TOOLS/host/check_host_tcl.py" --report "$LOGS/check_host_tcl.txt" > /dev/null 2>&1; r=$?
    say "  $(grep '^  phase6' "$LOGS/check_host_tcl.txt")"
    say "  $(tail -1 "$LOGS/check_host_tcl.txt")"
    check $r "the host scripts under tclsh against the ISSP stand-ins (stand-in): each sends exactly its steps"
else
    say "  host scripts skipped: no tclsh"
fi

# ---- 4. Quartus project ------------------------------------------------------------------------------
python3 "$HERE/make_quartus_project.py" --out "$BUILD/quartus" --check > "$LOGS/make_quartus_project.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/make_quartus_project.log")"
check $r "Quartus project: pins = the golden top's, files present, SDC groups and HDMI clock (stand-in), INTEL elaboration"

# ---- 5. compile ----------------------------------------------------------------------------------------
IMEM=$WS/PTSG-Core/03_Sample_Implementations/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
iverilog -g2012 -Wall -I "$HW/l1" -I "$HW/l2" -o "$BUILD/board_wall.vvp" -s DE10_Nano_wpms_tb \
    "$HERE"/sim/DE10_Nano_wpms_tb.v "$HERE"/sim/wpms_pll_sim.v "$HERE"/DE10_Nano_wpms_top.v "$HERE"/wpms_pll.v \
    "$HW"/switch/wpms_system.v "$HW"/switch/wpms_switch.v "$HW"/switch/wpms_host_bridge.v "$HW"/switch/wpms_issp.v \
    "$HW"/switch/wpms_rom.v "$HW"/switch/wpms_key_pulse.v \
    "$HW"/l1/wpms_synth_top.v "$HW"/l1/wpms_l1_module.v "$HW"/l1/wpms_l1_sin.v "$HW"/l1/wpms_l1_exp2.v \
    "$HW"/l1/wpms_output_stage.v "$HW"/l1/wpms_strobe_sync.v "$HW"/l1/wpms_i2s_master.v \
    "$HW"/l1/wpms_video_720p.v "$HW"/l1/wpms_adv7513_cfg.v \
    "$HW"/l2/wpms_l2_top.v "$HW"/l2/wpms_formation.v "$HW"/l2/wpms_sequencer.v "$HW"/core/ptsg_core_rh031p.v "$IMEM" \
    > "$LOGS/compile6.log" 2>&1; r=$?
own=$(grep -c "de10_nano/" "$LOGS/compile6.log")
say "  iverilog -Wall: $(wc -l < "$LOGS/compile6.log") lines, $own from hw/de10_nano"
[ $r -eq 0 ] && [ "$own" -eq 0 ]; check $? "board top + bench compile; nothing to say about hw/de10_nano"

# ---- 6. board-level cosimulation ------------------------------------------------------------------------
python3 "$TOOLS/cosim_board.py" --budget both --case all --out "$BUILD/cosim" --evidence "$BUILD/expected" \
    > "$LOGS/cosim_board.txt" 2>&1; r=$?
grep -E '^\[' "$LOGS/cosim_board.txt" | while read -r l; do say "  $l"; done
say "  $(tail -1 "$LOGS/cosim_board.txt")"
check $r "cosim_board: the eight evidence items within the brief's bounds, bit-exact with the models, both budgets"

# ---- 7. resource ledger parser ------------------------------------------------------------------------------
python3 "$TOOLS/resource_ledger.py" --selftest > "$LOGS/resource_ledger_selftest.log" 2>&1; r=$?
check $r "resource_ledger.py reads the Fitter's 'Resource Utilization by Entity' table (self-test)"

if [ "$FAIL" -eq 0 ]; then say "run_phase6: ALL PHASE 6 CHECKS PASSED (RTL-SIM; the board is next)"; else say "run_phase6: SOME CHECKS FAILED"; fi
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs" "$EVID/expected"
    for f in run_phase6.txt gen_inject_scores.log check_host_tcl.txt make_quartus_project.log compile6.log \
             cosim_board.txt resource_ledger_selftest.log; do
        [ -f "$LOGS/$f" ] && sed "s#$WS/#<workspace>/#g" "$LOGS/$f" > "$EVID/logs/$f"
    done
    for f in "$BUILD"/expected/*.json; do
        sed "s#$WS/#<workspace>/#g" "$f" > "$EVID/expected/$(basename "$f")"
    done
    cp "$BUILD"/expected/expected_*.vcd.gz "$EVID/expected/" 2>/dev/null
    if [ "$REGRESSION" = 1 ]; then
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase5/logs5/run_phase5.txt" > "$EVID/logs/phase5_regression.txt"
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase5/phase4/logs4/run_phase4.txt" > "$EVID/logs/phase4_regression.txt"
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase5/phase4/phase3/logs3/run_phase3.txt" > "$EVID/logs/phase3_regression.txt"
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase5/phase4/phase3/phase2/logs/run_phase2.txt" > "$EVID/logs/phase2_regression.txt"
    fi
fi
exit $FAIL
