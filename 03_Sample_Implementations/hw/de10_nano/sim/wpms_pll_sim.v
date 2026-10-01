// ============================================================================
//  wpms_pll_sim.v — behavioural stand-in for wpms_pll's altera_pll (bench only)
//  PLL の振る舞いモデル（ベンチ専用）
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//  A free-running clock of the given half period, a second output delayed by
//  SHIFT1_PS, and `locked` after LOCK_NS. Not related to refclk in phase: the
//  board's clock domains are asynchronous to each other, and the design treats
//  them so. Never given to Quartus (it holds delays).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
// ============================================================================
`timescale 1ns/1ps

module wpms_pll_sim #(
    parameter integer HALF0_PS  = 10000,
    parameter integer SHIFT1_PS = 0,
    parameter integer LOCK_NS   = 1000
) (
    input  wire rst,
    output reg  outclk0 = 1'b0,
    output reg  outclk1 = 1'b0,
    output reg  locked  = 1'b0
);
    always #(HALF0_PS / 1000.0) outclk0 = ~outclk0;
    always @(outclk0) outclk1 <= #(SHIFT1_PS / 1000.0) outclk0;
    initial begin
        #(LOCK_NS);
        locked = 1'b1;
    end
endmodule
