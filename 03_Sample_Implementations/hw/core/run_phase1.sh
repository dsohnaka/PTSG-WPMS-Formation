#!/usr/bin/env bash
# ============================================================================
#  run_phase1.sh — Phase 1 of SILICON_BRIEF_2026-09-27: the Core, patched on a
#  copy. Reproduces every Phase 1 result (evidence class RTL-SIM, Icarus
#  Verilog -g2012) and exits non-zero if any expectation fails.
#  License: MIT (Layer 3).
# ----------------------------------------------------------------------------
#  1. The frozen source is untouched (sha256 equals the blob at PTSG-Core HEAD).
#  2. stay_value tied 0 / unconnected: the Core's own testbenches, UNCHANGED,
#     run on the frozen RH030 source and on ptsg_core_rh031p.v; the pass logs
#     are diffed and the VCDs compared signal by signal (vcd_compare.py). Only
#     the copy's two new nets (stay_value, stay_dur_lit) may be one-sided.
#  3. SV-0 lockstep (frozen RH030 renamed ptsg_core_rh030 in the build
#     directory, the frozen file itself is only read): random programs at
#     PRESCALE 1 and 5; the Live Session #1 Scene 4 program at 6250 -> 20.
#  4. SV-1 … SV-7 (+ SV-5b) on form B: all pass.
#  5. The same tests with the anti-pattern of sketch §4 forced in the
#     testbench: SV-4 must fail with an 8192-clock Stay (the test bites);
#     SV-7 fails with it. Form A of sketch §3 (informative): SV-4, SV-7 fail.
#  6. SV-4 waveforms (form B, anti-pattern) and the diff against RH030.
#  Usage: hw/core/run_phase1.sh [EVIDENCE_DIR]
#         BUILD=<dir> overrides the build directory (default hw/core/build).
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-27       Claude Code   Add : First version (Phase 1).
# ============================================================================
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PROFILE=$(cd "$HERE/../../.." && pwd)
WS=${WS:-$(cd "$PROFILE/.." && pwd)}
CORE=$WS/PTSG-Core/03_Sample_Implementations
FROZEN=$CORE/ptsg_core_verilog/ptsg_core.v
TB_DIR=$CORE/ptsg_core_verilog
IMEM=$CORE/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
COPY=$HERE/ptsg_core_rh031p.v
SVTB=$HERE/ptsg_core_sv_tb.v
TOOLS=$PROFILE/03_Sample_Implementations/hw/tools
BUILD=${BUILD:-$HERE/build}
EVID=${1:-}
rm -rf "$BUILD"; mkdir -p "$BUILD"
cd "$BUILD"

FAILS=0
ok()   { echo "  [ok]   $*"; }
bad()  { echo "  [FAIL] $*"; FAILS=$((FAILS + 1)); }
# Every compiler message goes to $BUILD/compile_all.log. Two known, benign
# Icarus 12 messages are not echoed: "input port stay_value is coerced to
# inout" (a tri0 port driven by a testbench net) and "procedural continuous
# assignments are not yet fully supported" (the testbench re-issues its force
# on every operand change, see ptsg_core_sv_tb.v). Anything else is echoed.
ivl() {
  local out rc
  out=$(iverilog -g2012 "$@" 2>&1); rc=$?
  { echo "## iverilog -g2012 $*"; echo "$out"; } >> "$BUILD/compile_all.log"
  echo "$out" | grep -v -e "is coerced to inout" -e "procedural continuous assignments are not yet fully supported" \
              -e '^$' | sed 's/^/  [iverilog] /'
  [ $rc -eq 0 ] || echo "  [compile error] iverilog $*"
  return 0
}

echo "== 1. frozen source"
H_FILE=$(sha256sum "$FROZEN" | cut -d' ' -f1)
H_GIT=$(git -C "$WS/PTSG-Core" show HEAD:03_Sample_Implementations/ptsg_core_verilog/ptsg_core.v | sha256sum | cut -d' ' -f1)
echo "  ptsg_core.v sha256 $H_FILE (PTSG-Core $(git -C "$WS/PTSG-Core" rev-parse --short HEAD))"
[ "$H_FILE" = "$H_GIT" ] && ok "frozen ptsg_core.v equals the committed RH030 blob" || bad "frozen ptsg_core.v differs from PTSG-Core HEAD"
diff -u --label ptsg_core.v@RH030 --label ptsg_core_rh031p.v "$FROZEN" "$COPY" > rh030_vs_rh031p.diff
echo "  diff: +$(grep -c '^+[^+]' rh030_vs_rh031p.diff) / -$(grep -c '^-[^-]' rh030_vs_rh031p.diff) lines"

echo "== 2. unchanged Core testbenches, stay_value unconnected (tri0 = 0)"
for suite in tb:ptsg_core_tb conf:ptsg_core_conformance_tb; do
  tag=${suite%%:*}; top=${suite##*:}
  for which in rh030 rh031p; do
    src=$FROZEN; [ $which = rh031p ] && src=$COPY
    mkdir -p "$tag.$which"
    ( cd "$tag.$which" && ivl -DVCD_TOP=$top -o sim "$src" "$TB_DIR/$top.v" "$IMEM" "$TOOLS/vcd_dump.v" > compile.log
      vvp -n sim > run.log 2>&1 )
  done
  last=$(grep -h "ALL .*PASSED\|FAILED" "$tag.rh031p/run.log")
  cmp -s "$tag.rh030/run.log" "$tag.rh031p/run.log" && ok "$top: pass logs identical ($last)" || bad "$top: pass logs differ"
  python3 "$TOOLS/vcd_compare.py" "$tag.rh030/dump.vcd" "$tag.rh031p/dump.vcd" --label-a RH030 --label-b RH031p \
          --expect-only-b dut.stay_value dut.stay_dur_lit > "vcd_compare_$top.txt"
  [ $? -eq 0 ] && ok "$top: VCDs identical on the common set ($(grep -o 'signals in both: [0-9]*; value changes compared: [0-9]*' vcd_compare_$top.txt))" \
               || bad "$top: VCDs differ (see vcd_compare_$top.txt)"
done

echo "== 3. SV-0 lockstep, frozen RH030 vs RH031p with stay_value tied 0"
sed 's/^module ptsg_core #(/module ptsg_core_rh030 #(/' "$FROZEN" > ptsg_core_rh030_renamed.v
grep -q '^module ptsg_core_rh030 #(' ptsg_core_rh030_renamed.v || bad "rename of the frozen module failed"
SRCS="$COPY ptsg_core_rh030_renamed.v $SVTB $IMEM"
ivl -s ptsg_core_sv0_tb -Pptsg_core_sv0_tb.PRESCALE=1 -o sv0_p1 $SRCS
ivl -s ptsg_core_sv0_tb -Pptsg_core_sv0_tb.PRESCALE=5 -Pptsg_core_sv0_tb.EPOCHS=200 -Pptsg_core_sv0_tb.EPOCH_CLOCKS=3000 -o sv0_p5 $SRCS
ivl -s ptsg_core_sv0_tb -Pptsg_core_sv0_tb.PRESCALE=6250 -o sv0_scene4 $SRCS
vvp -n sv0_p1 > sv0_p1.log 2>&1
vvp -n sv0_p5 > sv0_p5.log 2>&1
vvp -n sv0_scene4 +scene4 > sv0_scene4.log 2>&1
for f in sv0_p1 sv0_p5 sv0_scene4; do
  l=$(grep -h "SV-0" $f.log | grep "PASS\|FAIL" | tail -1)
  case "$l" in PASS*) ok "$l";; *) bad "$f: ${l:-no verdict}";; esac
done

echo "== 4. SV-1 … SV-7 (+SV-5b) on form B"
ivl -s ptsg_core_sv_tb -o sv_formB $SRCS
ivl -s ptsg_core_sv_tb -DSV_FORM_ANTIPATTERN -o sv_anti $SRCS
ivl -s ptsg_core_sv_tb -DSV_FORM_A -o sv_formA $SRCS
vvp -n sv_formB > sv_formB.log 2>&1
grep -q "SV SUMMARY: 8 passed, 0 failed" sv_formB.log && ok "$(grep 'SV SUMMARY' sv_formB.log)" || bad "form B: $(grep 'SV SUMMARY' sv_formB.log)"

echo "== 5. the tests bite: anti-pattern (sketch §4) and form A (sketch §3) forced in the testbench"
vvp -n sv_anti > sv_anti.log 2>&1
vvp -n sv_formA > sv_formA.log 2>&1
grep -q "failed: SV-4 SV-7 (build: ANTI-PATTERN" sv_anti.log && grep -q "FAIL SV-4: .*lasted 8192 clocks" sv_anti.log \
  && ok "anti-pattern: SV-4 FAILS with an 8192-clock Stay (the test bites); SV-7 fails too; the rest pass" \
  || bad "anti-pattern did not fail exactly SV-4 (8192) and SV-7: $(grep 'SV SUMMARY' sv_anti.log)"
grep -q "failed: SV-4 SV-7 (build: FORM A" sv_formA.log \
  && ok "form A (informative): SV-4 and SV-7 fail — form A needs the length one clock ahead (the C4-T5 fork is real)" \
  || bad "form A: unexpected result: $(grep 'SV SUMMARY' sv_formA.log)"

echo "== 6. SV-4 waveforms"
vvp -n sv_formB +only=4 +sv4vcd=sv4_formB.vcd > sv4_formB.log 2>&1
vvp -n sv_anti  +only=4 +sv4vcd=sv4_antipattern.vcd > sv4_antipattern.log 2>&1
gzip -9 -n -f sv4_formB.vcd sv4_antipattern.vcd
ls -l sv4_*.vcd.gz | awk '{print "  " $5 " bytes  " $NF}'

if [ -n "$EVID" ]; then
  mkdir -p "$EVID/logs"
  cp rh030_vs_rh031p.diff vcd_compare_*.txt sv4_*.vcd.gz "$EVID/"
  cp compile_all.log "$EVID/logs/"
  cp sv0_p1.log sv0_p5.log sv0_scene4.log sv_formB.log sv_anti.log sv_formA.log sv4_formB.log sv4_antipattern.log "$EVID/logs/"
  for t in tb conf; do for w in rh030 rh031p; do cp "$t.$w/run.log" "$EVID/logs/core_${t}_$w.log"; done; done
  echo "  evidence copied to $EVID"
fi

echo
if [ $FAILS -eq 0 ]; then echo "PHASE 1: ALL CHECKS PASSED"; exit 0; else echo "PHASE 1: $FAILS CHECK(S) FAILED"; exit 1; fi
