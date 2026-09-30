// ============================================================================
//  wpms_key_pulse.v — a push button (active low) to one clock per press
//  押しボタン（負論理）を押下 1 回につき 1 クロックのパルスに
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  Two flip-flops (the button is asynchronous), then a debouncer: the level
//  must hold DEBOUNCE clocks before it counts (10 ms = 500,000 at 50 MHz).
//  `press` is one clock at the accepted falling edge. At reset the button is
//  taken as released, so a button held through reset presses once after it.
//  For KEY[0] (GO_ALL) and KEY[1] (test origin), customer Ch.5 §5.8.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_key_pulse #(
    parameter integer DEBOUNCE = 500_000
) (
    input  wire clk,
    input  wire rst,
    input  wire key_n,
    output reg  press
);
    localparam integer CW = (DEBOUNCE < 2) ? 1 : $clog2(DEBOUNCE);
    reg          k1 = 1'b1, k2 = 1'b1;
    reg          level;                         // the accepted level (1 = released)
    reg [CW-1:0] cnt;
    always @(posedge clk) begin
        k1 <= key_n;
        k2 <= k1;
    end
    always @(posedge clk) begin
        press <= 1'b0;
        if (rst) begin
            level <= 1'b1;
            cnt   <= {CW{1'b0}};
        end else if (k2 == level) begin
            cnt <= {CW{1'b0}};
        end else if (cnt == DEBOUNCE - 1) begin
            level <= k2;
            cnt   <= {CW{1'b0}};
            press <= !k2;
        end else begin
            cnt <= cnt + 1'b1;
        end
    end
endmodule
