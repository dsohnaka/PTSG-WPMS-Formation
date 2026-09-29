#!/usr/bin/env bash
# ============================================================================
#  run_phase4.sh — Phase 4 of SILICON_BRIEF_2026-09-27: the L1 pipeline and the
#  output path (customer Ch.2 v1.1, Ch.3, Ch.4), with the customer's oracle as
#  golden model. Reproduces every Phase 4 result (evidence class RTL-SIM,
#  Icarus Verilog -g2012; ORACLE for the model self-tests; ESTIMATE for the
#  resources) and exits non-zero if any expectation fails.
#  License: MIT (Layer 3).
# ----------------------------------------------------------------------------
#  1. Regression (REGRESSION=1, default): the Phase 3 recipe (which runs Phase 2's)
#     on the current RTL — the Formation and the L2 top changed (JumpVal power-up).
#  2. The customer's oracle, unchanged, with numpy (CH4-CREST really runs);
#     l1_model.py self-test (the sin core against sin(2 pi phi), exhaustive over u).
#  3. The generated numbers: wpms_exp2_table.hex/.mif and wpms_l1_consts.vh equal a
#     fresh generation from the oracle and the model.
#  4. Compile: every hw/l1 module and bench with -Wall.
#  5. Units: sin core and exp2 unit, 1,000,000 inputs (bit-exact).
#  6. Module: wpms_l1_module + output stage, bin by bin and sample by sample,
#     3 seeds x 400 sweeps; the MG fade (0 -> -60 dB) and the soft mute to the floor.
#  7. System on the 48 kHz grid (I2S master -> synchronizer): test origin, the
#     literal test origin at NMAX 1008 (refused), sigma = 71 Gaussian, level glide
#     with a pitch retune, full-load 8-packet sweep — 50 MHz and 100 MHz budgets.
#  8. System under the sweep oracle's GO traffic: 3 seeds x SAMPLES per budget.
#  9. Video carrier and ADV7513 configurator benches.
# 10. The L1 mutants: every deliberate defect caught.
# 11. (if yowasp-yosys is installed) the Cyclone V resource estimate per entity.
# 12. The SD-15 reproduction for the Core's office (hw/core/run_sd15.sh).
#  Usage: hw/l1/run_phase4.sh [EVIDENCE_DIR]
#         SAMPLES=<n> per seed (default 3000); REGRESSION=0 skips step 1;
#         BUILD=<dir> (default hw/l1/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-29       Claude Code   Add : First version (Phase 4).
# ============================================================================
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
HW=$(cd "$HERE/.." && pwd)
TOOLS=$HW/tools
WS=${WS:-$(cd "$HW/../../.." && pwd)}
ORACLE=$WS/FPGA_Spectrum_Engine_OpenPrompt/04_Verification/oracle/wpms_layer1_oracle.py
BUILD=${BUILD:-$HERE/build}
SAMPLES=${SAMPLES:-3000}
REGRESSION=${REGRESSION:-1}
EVID=${1:-}
LOGS=$BUILD/logs4; mkdir -p "$LOGS"
: > "$LOGS/run_phase4.txt"
FAIL=0
say()   { printf '%s\n' "$*" | tee -a "$LOGS/run_phase4.txt"; }
check() { if [ "$1" -eq 0 ]; then say "  [PASS] $2"; else say "  [FAIL] $2"; FAIL=1; fi; }

say "run_phase4: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $( (iverilog -V 2>&1 || true) | sed -n 1p ); $(python3 -V 2>&1); numpy $(python3 -c 'import numpy; print(numpy.__version__)' 2>/dev/null || echo absent); $SAMPLES samples per seed"

# ---- 1. regression ------------------------------------------------------------------------------
if [ "$REGRESSION" = 1 ]; then
    BUILD=$BUILD/phase3 "$HW/l2/run_phase3.sh" > "$LOGS/phase3_regression.log" 2>&1; r=$?
    say "  $(tail -1 "$LOGS/phase3_regression.log")"
    check $r "Phase 3 recipe (with Phase 2's) on the current RTL"
else
    say "  (regression skipped: REGRESSION=0)"
fi

# ---- 2. the oracle and the model ---------------------------------------------------------------
( cd "$(dirname "$ORACLE")" && python3 "$ORACLE" -v CH4-CREST CH3-EXP2 CH3-E2E CH4-MG > "$LOGS/oracle_selected.log" 2>&1; python3 "$ORACLE" > "$LOGS/oracle_all.log" 2>&1 ); r=$?
say "  customer oracle: $(tail -1 "$LOGS/oracle_all.log"); CH4-CREST: $(grep -c 'PASS  ' <(sed -n '/CH4-CREST/,/^\[/p' "$LOGS/oracle_selected.log")) sub-checks run"
check $r "wpms_layer1_oracle.py (unchanged): ALL PASS, CH4-CREST with numpy"
python3 "$TOOLS/l1_model.py" > "$LOGS/l1_model_selftest.log" 2>&1; r=$?
say "  $(grep 'sin_q040: max' "$LOGS/l1_model_selftest.log" | sed 's/^ *//')"
check $r "l1_model.py self-test: the sin core within 2^-23.9 of sin(2 pi phi) (exhaustive over u), phases = l1_phase (ORACLE)"

# ---- 3. generated numbers --------------------------------------------------------------------------
python3 "$TOOLS/gen_l1_tables.py" --check > "$LOGS/gen_l1_tables.log" 2>&1; r=$?
check $r "wpms_exp2_table.hex/.mif and wpms_l1_consts.vh equal a fresh generation (oracle _T/_C1/_C2; model constants)"

# ---- 4. compile -----------------------------------------------------------------------------------------
IMEM=$WS/PTSG-Core/03_Sample_Implementations/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
iverilog -g2012 -Wall -I "$HERE" -I "$HW/l2" -o "$BUILD/synth_check.vvp" -s wpms_synth_tb "$HERE/wpms_synth_tb.v" \
    "$HERE/wpms_synth_top.v" "$HERE/wpms_l1_module.v" "$HERE/wpms_l1_sin.v" "$HERE/wpms_l1_exp2.v" "$HERE/wpms_output_stage.v" \
    "$HERE/wpms_strobe_sync.v" "$HERE/wpms_i2s_master.v" "$HW/l2/wpms_l2_top.v" "$HW/l2/wpms_formation.v" \
    "$HW/l2/wpms_sequencer.v" "$HW/core/ptsg_core_rh031p.v" "$IMEM" > "$LOGS/compile4.log" 2>&1; r1=$?
iverilog -g2012 -Wall -o "$BUILD/outpath_check.vvp" "$HERE/wpms_video_720p.v" "$HERE/wpms_adv7513_cfg.v" >> "$LOGS/compile4.log" 2>&1; r2=$?
other=$(grep -v "sensitive to all\|coerced to inout\|timescale\|time unit\|time precision\|Affected design\|declared here" "$LOGS/compile4.log" | grep -c . || true)
say "  iverilog -Wall: $(grep -c 'sensitive to all' "$LOGS/compile4.log") '@* sensitive' notes (L2, as Phase 3), $(grep -c 'coerced to inout' "$LOGS/compile4.log") tri0-port note(s), $other other lines"
[ $r1 -eq 0 ] && [ $r2 -eq 0 ] && [ "$other" -eq 0 ]; check $? "wpms_synth_top (L2 + L1 + output path) and the output-path blocks compile"

# ---- 5. units ------------------------------------------------------------------------------------------
python3 "$TOOLS/cosim_l1.py" units --n 1000000 --out "$BUILD/cosim_l1" --report "$LOGS/cosim_l1_units.txt" > /dev/null 2>&1; r=$?
sed -n '2,3p' "$LOGS/cosim_l1_units.txt" | tee -a "$LOGS/run_phase4.txt"
check $r "sin core = l1_model.sin_q040 and exp2 unit = the oracle's exp2_q131, 1,000,000 inputs each"

# ---- 6. module -----------------------------------------------------------------------------------------
: > "$LOGS/cosim_l1_module.txt"; r=0
for s in 1 2 3; do
    python3 "$TOOLS/cosim_l1.py" module --sweeps 400 --seed $s --out "$BUILD/cosim_l1_m$s" --report "$BUILD/m$s.txt" > /dev/null 2>&1 || r=1
    cat "$BUILD/m$s.txt" >> "$LOGS/cosim_l1_module.txt"
    grep -E "^  (TB:|[0-9]+ sweeps)" "$BUILD/m$s.txt" | head -2 | sed "s/^/  [seed $s] /" | tee -a "$LOGS/run_phase4.txt"
done
check $r "wpms_l1_module + output stage: every bin (phase = l1_phase, a = l1_amplitude, sin, product) and every sample (bank, clip, MG, SWEEP_CLOCKS)"
python3 "$TOOLS/cosim_l1.py" mgfade --out "$BUILD/cosim_l1_mg" --report "$LOGS/cosim_l1_mgfade.txt" > /dev/null 2>&1; r=$?
sed -n '2,3p' "$LOGS/cosim_l1_mgfade.txt" | tee -a "$LOGS/run_phase4.txt"
check $r "MG 0 -> -60 dB in 1.0 s at 13,933 per sample (CH4-MG); soft mute to the floor, then exact zero (C4-D6)"

# ---- 7. system on the grid ----------------------------------------------------------------------------
: > "$LOGS/cosim_synth_grid.txt"; r=0
for c in "50 origin" "50 origin_literal" "50 glide" "50 full8" "100 origin" "100 gauss" "100 glide" "100 full8"; do
    set -- $c
    python3 "$TOOLS/cosim_synth.py" grid --budget $1 --case $2 --out "$BUILD/cosim_synth" --report "$BUILD/g_$1_$2.txt" > /dev/null 2>&1 || r=1
    cat "$BUILD/g_$1_$2.txt" >> "$LOGS/cosim_synth_grid.txt"
    say "  [grid $1 MHz $2] $(tail -1 "$BUILD/g_$1_$2.txt" | sed 's/^cosim_synth grid\/[a-z0-9_]*: //')"
done
grep -h -E "test origin \(N|sigma = 71|latency|strobe interval|error_flag:" "$LOGS/cosim_synth_grid.txt" | sort -u | sed 's/^/ /' | tee -a "$LOGS/run_phase4.txt"
set --
check $r "wpms_synth_top on the 48 kHz grid: samples = model, I2S wire = bank, latency 21.48 us, strobe 1041/1042 and 2083/2084, 927 audible bins, test-origin peak"

# ---- 8. system under the oracle's traffic --------------------------------------------------------
: > "$LOGS/cosim_synth_oracle.txt"; r=0
for b in 50 100; do
    python3 "$TOOLS/cosim_synth.py" oracle --budget $b --samples "$SAMPLES" --seeds 2026,7,42 --out "$BUILD/cosim_synth" \
        --report "$BUILD/o_$b.txt" > /dev/null 2>&1 || r=1
    cat "$BUILD/o_$b.txt" >> "$LOGS/cosim_synth_oracle.txt"
    grep -E "^  (total|SWEEP_CLOCKS|T_wake)" "$BUILD/o_$b.txt" | sed "s/^/  [oracle $b MHz] /" | tee -a "$LOGS/run_phase4.txt"
done
check $r "wpms_synth_top under sweep_sim's GO traffic: bundles as the oracle, every output sample as the model, SWEEP_CLOCKS < T_min"

# ---- 9. output-path benches -------------------------------------------------------------------------
iverilog -g2012 -o "$BUILD/video.vvp" -s wpms_video_tb "$HERE/wpms_video_tb.v" "$HERE/wpms_video_720p.v" 2> /dev/null && \
    vvp -n "$BUILD/video.vvp" > "$LOGS/video_tb.log" 2>&1; grep -q "video_tb: PASS" "$LOGS/video_tb.log"; r=$?
say "  $(grep 'clocks per frame' "$LOGS/video_tb.log")"
check $r "video carrier: 720p60 timing (VIC 4)"
iverilog -g2012 -o "$BUILD/adv.vvp" -s wpms_adv7513_tb "$HERE/wpms_adv7513_tb.v" "$HERE/wpms_adv7513_cfg.v" 2> /dev/null && \
    vvp -n "$BUILD/adv.vvp" > "$LOGS/adv7513_tb.log" 2>&1; grep -q "adv7513_tb: PASS" "$LOGS/adv7513_tb.log"; r=$?
grep "adv7513_tb: first\|adv7513_tb: after" "$LOGS/adv7513_tb.log" | sed 's/^/  /' | tee -a "$LOGS/run_phase4.txt"
check $r "ADV7513 configurator: HPD poll, the table written and acknowledged in order, rewritten after a hot-plug"

# ---- 10. mutants -------------------------------------------------------------------------------------
python3 "$TOOLS/cosim_l1_mutants.py" --out "$BUILD/l1_mutants" > "$LOGS/cosim_l1_mutants.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/cosim_l1_mutants.log")"
check $r "cosim_l1_mutants.py: every deliberate defect in the L1 RTL is caught"

# ---- 11. resources ------------------------------------------------------------------------------------
if command -v yowasp-yosys > /dev/null 2>&1; then
    mkdir -p "$BUILD/synth"; cp "$HERE"/wpms_l1_*.v "$HERE"/wpms_l1_consts.vh "$HERE"/wpms_exp2_table.hex "$HERE"/wpms_output_stage.v \
        "$HERE"/wpms_strobe_sync.v "$HERE"/wpms_i2s_master.v "$HERE"/wpms_video_720p.v "$HERE"/wpms_adv7513_cfg.v "$BUILD/synth/"
    : > "$LOGS/yosys_stat.txt"
    for top in wpms_l1_sin wpms_l1_exp2 wpms_l1_module wpms_output_stage wpms_i2s_master wpms_strobe_sync wpms_video_720p wpms_adv7513_cfg; do
        ( cd "$BUILD/synth" && yowasp-yosys -p "read_verilog -DSYNTHESIS wpms_l1_sin.v wpms_l1_exp2.v wpms_l1_module.v wpms_output_stage.v wpms_strobe_sync.v wpms_i2s_master.v wpms_video_720p.v wpms_adv7513_cfg.v; synth_intel_alm -family cyclonev -top $top -run begin:map_luts; abc -lut 6; opt -fast; clean; tee -o stat_$top.txt stat" > yosys_$top.log 2>&1 )
        line=$(grep -E '^\s+[0-9]+\s+(\$lut|MISTRAL_ALUT_ARITH|MISTRAL_FF|MISTRAL_MUL27X27|MISTRAL_MUL18X18|MISTRAL_M10K)$' "$BUILD/synth/stat_$top.txt" | sort -u -k2 | awk '{printf "%s %s; ", $2, $1}')
        echo "$top: $line" >> "$LOGS/yosys_stat.txt"
        say "  ESTIMATE $top: $line"
    done
else
    say "  resource estimate skipped: yowasp-yosys not installed (pip install yowasp-yosys)"
fi

# ---- 12. SD-15 ------------------------------------------------------------------------------------------
BUILD=$BUILD/sd15 "$HW/core/run_sd15.sh" > "$LOGS/run_sd15.txt" 2>&1; r=$?
say "  $(tail -1 "$LOGS/run_sd15.txt")"
check $r "SD-15 reproduction on the frozen Core and the copy (bug report to the Core's office)"

if [ "$FAIL" -eq 0 ]; then say "run_phase4: ALL PHASE 4 CHECKS PASSED"; else say "run_phase4: SOME CHECKS FAILED"; fi
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs"
    for f in run_phase4.txt oracle_all.log oracle_selected.log l1_model_selftest.log gen_l1_tables.log compile4.log \
             cosim_l1_units.txt cosim_l1_module.txt cosim_l1_mgfade.txt cosim_synth_grid.txt cosim_synth_oracle.txt \
             video_tb.log adv7513_tb.log cosim_l1_mutants.log yosys_stat.txt run_sd15.txt; do
        [ -f "$LOGS/$f" ] && sed "s#$WS/#<workspace>/#g" "$LOGS/$f" > "$EVID/logs/$f"
    done
    [ -f "$BUILD/phase3/logs3/run_phase3.txt" ] && sed "s#$WS/#<workspace>/#g" "$BUILD/phase3/logs3/run_phase3.txt" > "$EVID/logs/phase3_regression.txt"
    [ -f "$BUILD/phase3/phase2/logs/run_phase2.txt" ] && sed "s#$WS/#<workspace>/#g" "$BUILD/phase3/phase2/logs/run_phase2.txt" > "$EVID/logs/phase2_regression.txt"
fi
exit $FAIL
