#!/usr/bin/env bash
# ============================================================================
#  run_phase0_baseline.sh — Phase 0 of SILICON_BRIEF_2026-09-27: run, unchanged,
#  every golden model and the frozen Core testbenches, and keep the logs.
#  License: MIT (Layer 3). Evidence classes: RTL-SIM (Core testbenches, Icarus)
#  and ORACLE (Python models).
# ----------------------------------------------------------------------------
#  Workspace layout (the brief, section 1): four repositories side by side
#      $WS/PTSG-Core  $WS/PTSG-CPU-Formation  $WS/PTSG-WPMS-Formation
#      $WS/FPGA_Spectrum_Engine_OpenPrompt
#  Usage:  hw/tools/run_phase0_baseline.sh [LOG_DIR]
#          (default LOG_DIR = 04_Verification_Evidence/reports/logs/phase0)
#  Nothing in the golden-model directories is written: isa_fold_w.py writes
#  its contract to a temporary directory, and Python byte-code caching is off.
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-27       Claude Code   Add : First version (Phase 0 baseline).
# ============================================================================
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PROFILE=$(cd "$HERE/../../.." && pwd)                 # PTSG-WPMS-Formation
WS=${WS:-$(cd "$PROFILE/.." && pwd)}
LOG=${1:-$PROFILE/04_Verification_Evidence/reports/logs/phase0}
mkdir -p "$LOG"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1

CORE=$WS/PTSG-Core/03_Sample_Implementations
TOOLS=$PROFILE/03_Sample_Implementations/tools
ORACLE=$WS/FPGA_Spectrum_Engine_OpenPrompt/04_Verification/oracle/wpms_layer1_oracle.py

# ---- 1. commit hashes and toolchain ----------------------------------------
{
  for r in PTSG-Core PTSG-CPU-Formation PTSG-WPMS-Formation FPGA_Spectrum_Engine_OpenPrompt; do
    printf '%-34s %s  %s\n' "$r" "$(git -C "$WS/$r" rev-parse HEAD)" \
           "$(git -C "$WS/$r" log -1 --format=%cd --date=iso)"
  done
  echo
  (iverilog -V 2>&1 || true) | sed -n 1p
  python3 --version
} > "$LOG/00_workspace.log"

# ---- 2. frozen Core testbenches (RTL-SIM) ----------------------------------
V=$CORE/ptsg_core_verilog
IMEM=$CORE/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
( cd "$V" && iverilog -g2012 -o "$TMP/sim"  ptsg_core.v ptsg_core_tb.v             "$IMEM" ) > "$LOG/10_core_tb_compile.log" 2>&1
( cd "$TMP" && vvp -n sim  ) > "$LOG/11_core_tb_A-G.log" 2>&1
( cd "$V" && iverilog -g2012 -o "$TMP/simc" ptsg_core.v ptsg_core_conformance_tb.v "$IMEM" ) > "$LOG/12_core_conf_compile.log" 2>&1
( cd "$TMP" && vvp -n simc ) > "$LOG/13_core_conf_T1-T34.log" 2>&1
sha256sum "$V/ptsg_core.v" > "$LOG/14_frozen_core_sha256.log"

# ---- 3. profile golden models (ORACLE) -------------------------------------
( cd "$TOOLS" && python3 isa_fold_w.py isa_table_master_2026-09-03.json "$TMP/isa_table_w.json" ) > "$LOG/20_isa_fold_w.log" 2>&1
python3 - "$TOOLS/isa_table_w.json" "$TMP/isa_table_w.json" >> "$LOG/20_isa_fold_w.log" 2>&1 <<'EOF'
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
fa = a["provenance"].pop("folded", None); fb = b["provenance"].pop("folded", None)
print(f"regenerated contract == committed contract (ignoring 'folded' {fa} vs {fb}): {a == b}")
EOF
for seed in 2026 7 42; do
  ( cd "$TOOLS" && python3 sweep_sim.py "$ORACLE" 20000 "$seed" ) > "$LOG/21_sweep_sim_seed$seed.log" 2>&1
done
( cd "$TOOLS" && python3 negative_tests.py ) > "$LOG/22_negative_tests.log" 2>&1
( cd "$TOOLS" && python3 pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json ) > "$LOG/23_exp_maclaurin_w.log" 2>&1

# ---- 4. customer oracle (ORACLE) -------------------------------------------
python3 "$ORACLE" > "$LOG/30_customer_oracle.log" 2>&1

# ---- summary ---------------------------------------------------------------
echo "Phase 0 baseline logs in $LOG"
grep -h "ALL TESTS PASSED\|ALL CONFORMANCE TESTS PASSED\|FAILED" "$LOG"/11_*.log "$LOG"/13_*.log
grep -h "regenerated contract" "$LOG/20_isa_fold_w.log"
grep -h "mismatches" "$LOG"/21_*.log
tail -n 1 "$LOG/22_negative_tests.log"
grep -h "max |err|" "$LOG/23_exp_maclaurin_w.log"
tail -n 1 "$LOG/30_customer_oracle.log"
