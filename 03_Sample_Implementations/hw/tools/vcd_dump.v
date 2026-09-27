// ============================================================================
//  vcd_dump.v — dump a testbench to VCD without editing it.
//  License: MIT (Layer 3). Icarus Verilog elaborates every module that no
//  other module instantiates as a root, so compiling this file beside a
//  testbench adds a second root that only opens the dump:
//      iverilog -g2012 -DVCD_TOP=ptsg_core_tb -o sim ... ptsg_core_tb.v vcd_dump.v
//  The dump file is `VCD_FILE (default "dump.vcd", in the run directory).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-27       Claude Code   Add : First version (Phase 1 bit-identity runs).
// ============================================================================
`ifndef VCD_FILE
 `define VCD_FILE "dump.vcd"
`endif
`ifndef VCD_TOP
 `define VCD_TOP ptsg_core_tb
`endif
module vcd_dump;
    initial begin
        $dumpfile(`VCD_FILE);
        $dumpvars(0, `VCD_TOP);
    end
endmodule
