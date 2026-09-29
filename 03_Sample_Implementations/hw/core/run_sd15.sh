#!/usr/bin/env bash
# ============================================================================
#  run_sd15.sh — the SD-15 reproduction (insertion handshake) for the PTSG-Core
#  office: sd15_insert_handshake_tb.v on the FROZEN PTSG-Core source (read
#  only; its sha256 is recorded) and on the RH031p copy, every scene x drop
#  style x stack. Evidence class RTL-SIM (Icarus Verilog -g2012).
#  Exits 0 when the observations are those recorded in the bug report:
#  the registered drop is taken twice in every scene, the in-ack-clock drop
#  once, on both sources.
#  License: MIT (Layer 3).
# ----------------------------------------------------------------------------
#  Usage: hw/core/run_sd15.sh [EVIDENCE_DIR]    BUILD=<dir> (default hw/core/build/sd15)
# ----------------------------------------------------------------------------
#  REVISION HISTORY(RH)
#  001 2026-09-29       Claude Code   Add : First version (SD-15 bug report).
# ============================================================================
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
WS=${WS:-$(cd "$HERE/../../../.." && pwd)}
FROZEN=$WS/PTSG-Core/03_Sample_Implementations/ptsg_core_verilog/ptsg_core.v
IMEM=$WS/PTSG-Core/03_Sample_Implementations/ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v
COPY=$HERE/ptsg_core_rh031p.v
BUILD=${BUILD:-$HERE/build/sd15}
EVID=${1:-}
mkdir -p "$BUILD"
LOG=$BUILD/run_sd15.txt
: > "$LOG"
say() { printf '%s\n' "$*" | tee -a "$LOG"; }

say "run_sd15: $(date -u +%Y-%m-%dT%H:%M:%SZ) — $( (iverilog -V 2>&1 || true) | sed -n 1p )"
say "  frozen source: $FROZEN"
say "  sha256 $(sha256sum "$FROZEN" | cut -c1-64)  (PTSG-Core $(git -C "$WS/PTSG-Core" rev-parse --short HEAD 2>/dev/null))"
FAIL=0
for src in frozen copy; do
    f=$FROZEN; [ "$src" = copy ] && f=$COPY
    for scene in 0 1 2; do
        for drop in 0 1; do
            for stack in 0 1; do
                out=$BUILD/${src}_s${scene}_d${drop}_k${stack}
                iverilog -g2012 -o "$out.vvp" -s sd15_insert_handshake_tb \
                    -P sd15_insert_handshake_tb.SCENE=$scene -P sd15_insert_handshake_tb.DROP=$drop \
                    -P sd15_insert_handshake_tb.STACK=$stack \
                    "$HERE/sd15_insert_handshake_tb.v" "$f" "$IMEM" > "$out.compile.log" 2>&1 \
                    || { say "  [$src] compile failed (see $out.compile.log)"; FAIL=1; continue; }
                line=$(vvp -n "$out.vvp" | grep '^SD15')
                say "  [$src] $line"
                # what the bug report states
                if [ "$drop" = 0 ]; then echo "$line" | grep -q "DOUBLE TAKE" || FAIL=1
                else                     echo "$line" | grep -q "AS THE TEXT"  || FAIL=1; fi
            done
        done
    done
done
if [ "$FAIL" -eq 0 ]; then say "run_sd15: reproduced — the registered drop is taken twice in every scene, the in-ack-clock drop once (both sources)"
else                       say "run_sd15: NOT as recorded"; fi
# one waveform per drop style: frozen source, the WPMS shape (window), no stack
for drop in 0 1; do
    vvp -n "$BUILD/frozen_s2_d${drop}_k0.vvp" +vcd="$BUILD/sd15_window_drop${drop}.vcd" > /dev/null
done
if [ -n "$EVID" ]; then
    mkdir -p "$EVID/logs"; cp "$LOG" "$EVID/logs/"
    for drop in 0 1; do gzip -9 -n -c "$BUILD/sd15_window_drop${drop}.vcd" > "$EVID/sd15_window_drop${drop}.vcd.gz"; done
fi
exit $FAIL
