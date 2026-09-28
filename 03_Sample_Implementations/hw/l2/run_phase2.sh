#!/usr/bin/env bash
# ============================================================================
#  run_phase2.sh — Phase 2 of SILICON_BRIEF_2026-09-27: the L2 Formation
#  datapath. Reproduces every Phase 2 result (evidence class RTL-SIM, Icarus
#  Verilog -g2012; the resource numbers are an ESTIMATE from Yosys) and exits
#  non-zero if any expectation fails.
#  License: MIT (Layer 3).
# ----------------------------------------------------------------------------
#  1. The decode map agrees with the contract; the generated RTL table
#     (wpms_decode.vh) and the published map (decode_map.md) are up to date.
#  2. The three window programs assemble (pfasm_as.py) to the committed images
#     in hw/l2/programs/; the D3 §3 sketch fixture assembles (score_as.py) to the
#     committed hw/l2/scores/d3_sketch_r1_fixture.{hex,mif}.
#  3. The RTL compiles with no warning other than Icarus's "@* is sensitive to
#     all words" notes.
#  4. cosim_l2.py: the hardware against pfasm_tools_w.Machine — packet, HK,
#     forwarding, exp, 13 negatives, hardware-only E4, prefetch, traced timing,
#     3000 random contract sequences. All must be bit-identical.
#  5. cosim_mutants.py: 20 deliberate defects, each must be caught.
#  6. score_rt.py: the Core copy decodes the assembled score as encoded.
#  7. (if yowasp-yosys is installed) the Cyclone V resource estimate.
#  Usage: hw/l2/run_phase2.sh [EVIDENCE_DIR]
#         BUILD=<dir> overrides the build directory (default hw/l2/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-27       Claude Code   Add : First version (Phase 2).
# ============================================================================
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
HW=$(cd "$HERE/.." && pwd)
S3=$(cd "$HW/.." && pwd)
TOOLS=$HW/tools
GOLD=$S3/tools
BUILD=${BUILD:-$HERE/build}
EVID=${1:-}
mkdir -p "$BUILD"
LOGS=$BUILD/logs; mkdir -p "$LOGS"
: > "$LOGS/run_phase2.txt"
FAIL=0
say()  { printf '%s\n' "$*" | tee -a "$LOGS/run_phase2.txt"; }
check() { if [ "$1" -eq 0 ]; then say "  [PASS] $2"; else say "  [FAIL] $2"; FAIL=1; fi; }

say "run_phase2: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $( (iverilog -V 2>&1 || true) | sed -n 1p ); $(python3 -V 2>&1)"

# ---- 1. decode map -------------------------------------------------------------
python3 "$TOOLS/gen_decode.py" --check > "$LOGS/gen_decode.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/gen_decode.log")"
check $r "decode_map.json consistent with isa_table_w.json; wpms_decode.vh and decode_map.md regenerate identically"

# ---- 2. assembled images ---------------------------------------------------------
mkdir -p "$BUILD/programs" "$BUILD/scores"
: > "$LOGS/pfasm_as.log"
r=0
for p in wpms_packet wpms_housekeeping exp_maclaurin_w; do
    python3 "$TOOLS/pfasm_as.py" "$S3/instruction_lists/$p.pfasm" -o "$BUILD/programs/$p.hex" >> "$LOGS/pfasm_as.log" 2>&1 || r=1
    cmp -s "$BUILD/programs/$p.hex" "$HERE/programs/$p.hex" || { say "    $p.hex differs from the committed image"; r=1; }
done
say "  $(grep -c . "$LOGS/pfasm_as.log") programs assembled: $(tr '\n' ';' < "$LOGS/pfasm_as.log" | sed 's#[^;]*/##g')"
check $r "pfasm_as.py: wpms_packet (25), wpms_housekeeping (1), exp_maclaurin_w (27) equal the committed images"
python3 "$TOOLS/score_as.py" "$HERE/scores/d3_sketch_r1_fixture.score" -o "$BUILD/scores/d3_sketch_r1_fixture" > "$LOGS/score_as.log" 2>&1; r=$?
for e in hex mif; do cmp -s "$BUILD/scores/d3_sketch_r1_fixture.$e" "$HERE/scores/d3_sketch_r1_fixture.$e" || { say "    fixture .$e differs"; r=1; }; done
say "  $(tail -1 "$LOGS/score_as.log" | sed 's#/[^ ]*/##g')"
check $r "score_as.py: the D3 §3 sketch fixture equals the committed .hex/.mif"

# ---- 3. compile ------------------------------------------------------------------
iverilog -g2012 -Wall -I "$HERE" -o "$BUILD/compile_check.vvp" "$HERE/wpms_formation.v" "$HERE/wpms_formation_tb.v" > "$LOGS/compile.log" 2>&1; r=$?
other=$(grep -v "sensitive to all" "$LOGS/compile.log" | grep -c . || true)
say "  iverilog -Wall: $(grep -c "sensitive to all" "$LOGS/compile.log") '@* sensitive to all words' notes, $other other lines"
[ "$r" -eq 0 ] && [ "$other" -eq 0 ]; check $? "wpms_formation.v + wpms_formation_tb.v compile clean"

# ---- 4. golden model's own exp figure, then the cosimulation ------------------------
( cd "$GOLD" && python3 pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json ) > "$LOGS/oracle_exp.log" 2>&1
say "  ORACLE: $(tail -1 "$LOGS/oracle_exp.log")"
python3 "$TOOLS/cosim_l2.py" --out "$BUILD/cosim" --report "$LOGS/cosim_l2.txt" > "$LOGS/cosim_l2.log" 2>&1; r=$?
sed -n '2,14p' "$LOGS/cosim_l2.txt" | sed 's/^/  /' | tee -a "$LOGS/run_phase2.txt"
say "  $(tail -1 "$LOGS/cosim_l2.txt")"
check $r "cosim_l2.py: every case bit-identical to pfasm_tools_w.Machine; no protocol warning or invariant violation"
grep -q "max |err| over 21 x = 7.39e-09" "$LOGS/cosim_l2.txt"; check $? "exp_maclaurin_w on the hardware: max |err| = 7.39e-09 (the oracle's figure)"
grep -q "13 block N = 16" "$LOGS/cosim_l2.txt" && [ "$(grep -c '^\s*\[PASS\] N' "$LOGS/cosim_l2.txt")" -eq 15 ]
check $? "negative cases N1..N13 (N12 three times) raise their codes on the hardware"

# ---- 5. mutants ------------------------------------------------------------------------
python3 "$TOOLS/cosim_mutants.py" --out "$BUILD/mutants" > "$LOGS/cosim_mutants.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/cosim_mutants.log")"
check $r "cosim_mutants.py: every deliberate defect is caught (the cosimulation bites)"

# ---- 6. score round trip -----------------------------------------------------------------
python3 "$TOOLS/score_rt.py" --out "$BUILD/score_rt" > "$LOGS/score_rt.log" 2>&1; r=$?
say "  $(tail -1 "$LOGS/score_rt.log")"
check $r "score_rt.py: the Core copy issues exactly the assembled words"

# ---- 7. resource estimate (optional tool) ------------------------------------------------
if command -v yowasp-yosys > /dev/null 2>&1; then
    mkdir -p "$BUILD/synth"; cp "$HERE/wpms_formation.v" "$HERE/wpms_decode.vh" "$BUILD/synth/"
    ( cd "$BUILD/synth" && yowasp-yosys -p "read_verilog -DSYNTHESIS wpms_formation.v; synth_intel_alm -family cyclonev -top wpms_formation -run begin:map_luts; abc -lut 6; opt -fast; clean; tee -o yosys_stat.txt stat" > yosys.log 2>&1 )
    r=$?; cp "$BUILD/synth/yosys_stat.txt" "$LOGS/yosys_stat.txt" 2>/dev/null
    say "  ESTIMATE (Yosys $(yowasp-yosys -V 2>/dev/null | awk '{print $2}'), synth_intel_alm cyclonev + abc -lut 6): $(grep -E '^\s+[0-9]+\s+(\$lut|MISTRAL_ALUT_ARITH|MISTRAL_FF|MISTRAL_MLAB|MISTRAL_MUL27X27|MISTRAL_MUL18X18)$' "$LOGS/yosys_stat.txt" | tail -6 | awk '{printf "%s %s; ", $2, $1}')"
    check $r "Yosys synthesis for Cyclone V completes"
else
    say "  resource estimate skipped: yowasp-yosys not installed (pip install yowasp-yosys)"
fi

if [ "$FAIL" -eq 0 ]; then say "run_phase2: ALL PHASE 2 CHECKS PASSED"; else say "run_phase2: SOME CHECKS FAILED"; fi
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs"
    for f in run_phase2.txt gen_decode.log pfasm_as.log score_as.log compile.log oracle_exp.log cosim_l2.txt \
             cosim_mutants.log score_rt.log yosys_stat.txt; do
        [ -f "$LOGS/$f" ] && cp "$LOGS/$f" "$EVID/logs/"
    done
fi
exit $FAIL
