// ============================================================================
//  wpms_strobe_sync.v — the L3 strobe into clk_sys (customer Ch.4 §4.3.2)
//  L3 ストローブの clk_sys への同期
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  The audio side (wpms_i2s_master, clk_aud) toggles strobe_tgl once per frame,
//  at F_m - 1 SCLK (C4-D3). Here: a two-flip-flop synchronizer and an edge
//  detector give one clk_sys clock per frame — the single event that wakes the
//  L2 Formation (CR3-T2), closes the accumulators (C3-D9) and steps MG
//  (C4-D4). Latency 2 to 3 clk_sys clocks after the toggle.
//  STROBE_INTERVAL (Ch.5 0x018): clk_sys clocks between the last two strobes
//  (2,083 / 2,084 at 100 MHz; 1,041 / 1,042 at 50 MHz); STROBE_MINMAX (0x019)
//  from the second strobe after reset or a clear — the live check of the L3
//  master (Ch.4 §4.9).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_strobe_sync (
    input  wire        clk,                     // clk_sys
    input  wire        rst,
    input  wire        strobe_tgl,              // from clk_aud (asynchronous here)
    output wire        strobe,                  // one clock per frame
    input  wire        minmax_clear,
    output reg  [11:0] interval,
    output reg  [11:0] interval_min,
    output reg  [11:0] interval_max
);
    (* altera_attribute = "-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg s1, s2;
    reg s3;
    always @(posedge clk) begin
        s1 <= strobe_tgl;
        s2 <= s1;
        s3 <= s2;
    end
    assign strobe = (s2 ^ s3) && !rst;

    reg [11:0] cnt;
    reg        seen, valid;                     // a strobe seen; an interval measured
    always @(posedge clk) begin
        if (rst) begin
            cnt <= 12'd0;  seen <= 1'b0;  valid <= 1'b0;
            interval <= 12'd0;  interval_min <= 12'hFFF;  interval_max <= 12'd0;
        end else begin
            cnt <= (cnt == 12'hFFF) ? cnt : cnt + 12'd1;
            if (strobe) begin
                cnt <= 12'd1;
                seen <= 1'b1;
                if (seen) begin
                    interval <= cnt;
                    valid    <= 1'b1;
                    if (cnt < interval_min || minmax_clear) interval_min <= cnt;
                    if (cnt > interval_max || minmax_clear) interval_max <= cnt;
                end
            end else if (minmax_clear) begin
                interval_min <= 12'hFFF;  interval_max <= 12'd0;
            end
        end
    end
endmodule
