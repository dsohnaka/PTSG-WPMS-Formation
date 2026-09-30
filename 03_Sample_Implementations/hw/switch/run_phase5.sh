#!/usr/bin/env bash
# ============================================================================
#  run_phase5.sh — SILICON_BRIEF_2026-09-27 Phase 5: the minimal input switch
#  (customer Ch.5), with the ISSP host path of the ruling of 2026-09-30.
#  License: MIT (Layer 3). Evidence class of every result: RTL-SIM (Icarus
#  Verilog -g2012) unless marked ESTIMATE (yosys) or ORACLE.
#
#   1. Regression (REGRESSION=1, default): the Phase 4 recipe, which runs Phase
#      3's, which runs Phase 2's — on the Formation's RH004 (the arm vector,
#      the strobe-clock take) and the ADV7513 table's RH002.
#   2. The ROM images (gen_switch_rom.py --check): the test origin of Ch.3
#      §3.10 / Ch.5 §5.8, N = 1,008 (50 MHz, ruling SD-17 (a)) and 2,048.
#   3. Compile: wpms_system + its bench, iverilog -Wall: no line from hw/switch.
#   4. The system cosimulation (cosim_switch.py), 50 and 100 MHz budgets:
#      origin, music (the host script's own steps), reject, timing, bridge;
#      random traffic (seeds 1-3 at 50 MHz, 4 at 100); the test ROM image.
#   4b. The host scripts (hw/tools/host/check_host_tcl.py, if tclsh is
#      installed): wpms_issp_host.tcl and wpms_music_demo.tcl under tclsh
#      against stand-ins of the Quartus ISSP commands (not Quartus, not RTL).
#   5. Mutants (cosim_switch_mutants.py): each must be killed.
#   6. Resources (yowasp-yosys, if installed): ESTIMATE per entity.
#   7. A VCD of a short run for the evidence (reset, ROM, a host GO).
#  Usage: hw/switch/run_phase5.sh [EVIDENCE_DIR]
#         REGRESSION=0 skips step 1; SAMPLES (Phase 4's oracle runs, default
#         3000); BUILD=<dir> (default hw/switch/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-30       Claude Code   Add : First version (Phase 5).
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
LOGS=$BUILD/logs5; mkdir -p "$LOGS"
: > "$LOGS/run_phase5.txt"
FAIL=0
say()   { printf '%s\n' "$*" | tee -a "$LOGS/run_phase5.txt"; }
check() { if [ "$1" -eq 0 ]; then say "  [PASS] $2"; else say "  [FAIL] $2"; FAIL=1; fi; }

say "run_phase5: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $(iverilog -V 2>&1 | head -1); Python $(python3 -c 'import sys; print(sys.version.split()[0])')"

# ---- 1. regression -----------------------------------------------------------------------------------
if [ "$REGRESSION" = 1 ]; then
    BUILD=$BUILD/phase4 "$HW/l1/run_phase4.sh" > "$LOGS/phase4_regression.log" 2>&1; r=$?
    say "  $(tail -1 "$BUILD/phase4/logs4/run_phase4.txt")"
    say "  $(grep 'run_phase3:' "$BUILD/phase4/phase3/logs3/run_phase3.txt" | tail -1)"
    say "  $(grep 'run_phase2:' "$BUILD/phase4/phase3/phase2/logs/run_phase2.txt" | tail -1)"
    check $r "regression: Phases 2, 3 and 4 on the Formation's RH004 and the ADV7513 table's RH002"
fi

# ---- 2. ROM images -------------------------------------------------------------------------------------
python3 "$TOOLS/gen_switch_rom.py" --check > "$LOGS/gen_switch_rom.log" 2>&1; r=$?
check $r "ROM images wpms_rom_origin_{1008,2048}.{hex,mif} regenerate identically (Ch.3 §3.10, Ch.5 §5.8)"

# ---- 3. compile ------------------------------------------------------------------------------------------
IMEM=$WS/PTSG-Core/03_Sample_Implementations/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
iverilog -g2012 -Wall -I "$HW/l1" -I "$HW/l2" -o "$BUILD/system_wall.vvp" -s wpms_system_tb \
    "$HERE"/wpms_system_tb.v "$HERE"/wpms_system.v "$HERE"/wpms_switch.v "$HERE"/wpms_host_bridge.v \
    "$HERE"/wpms_issp.v "$HERE"/wpms_rom.v "$HERE"/wpms_key_pulse.v \
    "$HW"/l1/wpms_synth_top.v "$HW"/l1/wpms_l1_module.v "$HW"/l1/wpms_l1_sin.v "$HW"/l1/wpms_l1_exp2.v \
    "$HW"/l1/wpms_output_stage.v "$HW"/l1/wpms_strobe_sync.v "$HW"/l1/wpms_i2s_master.v \
    "$HW"/l2/wpms_l2_top.v "$HW"/l2/wpms_formation.v "$HW"/l2/wpms_sequencer.v "$HW"/core/ptsg_core_rh031p.v "$IMEM" \
    > "$LOGS/compile5.log" 2>&1; r=$?
own=$(grep -c "hw/switch\|switch/wpms_" "$LOGS/compile5.log")
say "  iverilog -Wall: $(wc -l < "$LOGS/compile5.log") lines, $own from hw/switch"
[ $r -eq 0 ] && [ "$own" -eq 0 ]; check $? "wpms_system + bench compile; nothing to say about hw/switch"

# ---- 4. system cosimulation ------------------------------------------------------------------------------
: > "$LOGS/cosim_switch.txt"
runs=("origin 50 1" "music 50 1" "reject 50 1" "timing 50 1" "bridge 50 1" "random 50 1" "random 50 2" "random 50 3"
      "origin 100 1" "music 100 1" "reject 100 1" "timing 100 1" "bridge 100 1" "random 100 4")
pids=()
for spec in "${runs[@]}"; do
    set -- $spec
    python3 "$TOOLS/cosim_switch.py" --case "$1" --budget "$2" --seed "$3" --out "$BUILD/cosim" \
        --report "$LOGS/cosim_switch_$1_$2_$3.txt" > /dev/null 2>&1 &
    pids+=($!)
    if [ ${#pids[@]} -ge 4 ]; then wait "${pids[0]}"; pids=("${pids[@]:1}"); fi
done
wait
python3 "$TOOLS/cosim_switch.py" --case origin --budget 50 --rom-extra --out "$BUILD/cosim_rom" \
    --report "$LOGS/cosim_switch_origin_rom.txt" > /dev/null 2>&1
fails=0
for spec in "${runs[@]}" "origin_rom"; do
    set -- $spec
    f=$LOGS/cosim_switch_$1${2:+_$2}${3:+_$3}.txt
    cat "$f" >> "$LOGS/cosim_switch.txt" 2>/dev/null
    last=$(tail -1 "$f" 2>/dev/null)
    say "  [$spec] ${last#cosim_switch }"
    case "$last" in *PASS*) ;; *) fails=$((fails + 1)) ;; esac
done
[ $fails -eq 0 ]; check $? "cosim_switch: the switch, the host path, the ROM and the sound agree with the models in every run"

# ---- 4b. the host scripts (outside WPMS) ---------------------------------------------------------------
if command -v tclsh8.6 > /dev/null 2>&1 || command -v tclsh > /dev/null 2>&1; then
    python3 "$TOOLS/host/check_host_tcl.py" --report "$LOGS/check_host_tcl.txt" > /dev/null 2>&1; r=$?
    say "  $(tail -1 "$LOGS/check_host_tcl.txt")"
    check $r "the host scripts under tclsh against the ISSP stand-ins: the demo sends exactly its steps"
else
    say "  host scripts skipped: no tclsh"
fi

# ---- 5. mutants --------------------------------------------------------------------------------------------
python3 "$TOOLS/cosim_switch_mutants.py" --out "$BUILD/mutants" > "$LOGS/cosim_switch_mutants.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/cosim_switch_mutants.log")"
check $r "every mutant of the switch, the bridge and RH004 is killed"

# ---- 6. resources --------------------------------------------------------------------------------------------
if command -v yowasp-yosys > /dev/null 2>&1; then
    mkdir -p "$BUILD/synth"; cp "$HERE"/wpms_switch.v "$HERE"/wpms_host_bridge.v "$HERE"/wpms_key_pulse.v \
        "$HERE"/wpms_rom.v "$HERE"/wpms_rom_origin_1008.hex "$BUILD/synth/"
    : > "$LOGS/yosys_stat.txt"
    for top in wpms_switch wpms_host_bridge wpms_key_pulse; do
        ( cd "$BUILD/synth" && yowasp-yosys -p "read_verilog -DSYNTHESIS wpms_switch.v wpms_host_bridge.v wpms_key_pulse.v wpms_rom.v; synth_intel_alm -family cyclonev -top $top -run begin:map_luts; abc -lut 6; opt -fast; clean; tee -o stat_$top.txt stat" > yosys_$top.log 2>&1 )
        line=$(grep -E '^\s+[0-9]+\s+(\$lut|MISTRAL_ALUT_ARITH|MISTRAL_FF|MISTRAL_MUL27X27|MISTRAL_MUL18X18|MISTRAL_M10K|\$mem.*)$' "$BUILD/synth/stat_$top.txt" | sort -u -k2 | awk '{printf "%s %s; ", $2, $1}')
        echo "$top: $line" >> "$LOGS/yosys_stat.txt"
        say "  ESTIMATE $top: $line"
    done
else
    say "  resource estimate skipped: yowasp-yosys not installed"
fi

# ---- 7. VCD -----------------------------------------------------------------------------------------------------
python3 "$TOOLS/cosim_switch.py" --case evidence --budget 50 --out "$BUILD/vcd" --vcd "$BUILD/vcd/phase5_host_go.vcd" \
    --report "$LOGS/cosim_switch_evidence.txt" > /dev/null 2>&1; r=$?
gzip -9 -f "$BUILD/vcd/phase5_host_go.vcd" 2>/dev/null
say "  $(tail -1 "$LOGS/cosim_switch_evidence.txt")"
check $r "evidence run (reset, the ROM, one host GO) with its VCD"

if [ "$FAIL" -eq 0 ]; then say "run_phase5: ALL PHASE 5 CHECKS PASSED"; else say "run_phase5: SOME CHECKS FAILED"; fi
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs"
    for f in run_phase5.txt gen_switch_rom.log compile5.log cosim_switch.txt cosim_switch_evidence.txt \
             check_host_tcl.txt cosim_switch_mutants.log yosys_stat.txt; do
        [ -f "$LOGS/$f" ] && sed "s#$WS/#<workspace>/#g" "$LOGS/$f" > "$EVID/logs/$f"
    done
    if [ "$REGRESSION" = 1 ]; then
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase4/logs4/run_phase4.txt" > "$EVID/logs/phase4_regression.txt"
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase4/phase3/logs3/run_phase3.txt" > "$EVID/logs/phase3_regression.txt"
        sed "s#$WS/#<workspace>/#g" "$BUILD/phase4/phase3/phase2/logs/run_phase2.txt" > "$EVID/logs/phase2_regression.txt"
        for f in adv7513_tb.log cosim_synth_grid.txt; do
            [ -f "$BUILD/phase4/logs4/$f" ] && sed "s#$WS/#<workspace>/#g" "$BUILD/phase4/logs4/$f" > "$EVID/logs/phase4_$f"
        done
    fi
    [ -f "$BUILD/vcd/phase5_host_go.vcd.gz" ] && cp "$BUILD/vcd/phase5_host_go.vcd.gz" "$EVID/"
fi
exit $FAIL
