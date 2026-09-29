// ============================================================================
//  wpms_i2s_master.v — I2S master and origin of the L3 strobe (customer Ch.4 §4.3, §4.6.1)
//  I2S マスターと L3 ストローブの起点
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  clk_aud = MCLK = 256 Fs = 12.288 MHz (C4-D2). Philips I2S (C4-D8): SCLK =
//  MCLK/4 = 64 Fs; LRCLK low = left; 32-bit slots; the 24-bit word MSB first,
//  one SCLK after the LRCLK edge, then zeros; data change on the SCLK falling
//  edge, the receiver samples on the rising edge (2 MCLK of set-up).
//
//  One frame = 256 MCLK, position cnt. F_m (the LRCLK falling edge, left
//  channel of frame m begins) is the MCLK edge where cnt becomes 0. There:
//    * the whole output bank (L, R) is captured — the stability-window
//      crossing of C4-D7: clk_sys writes the bank only a few clocks after the
//      strobe, which left this domain Delta_pre earlier;
//  and Delta_pre = 1 SCLK = 4 MCLK before it (cnt becomes 252):
//    * strobe_tgl toggles: the L3 strobe S_m = F_m - 1 SCLK (C4-D3), carried to
//      clk_sys by wpms_strobe_sync.
//  Latency (C4-D10): the sweep started by S_m is closed by S_{m+1}, captured at
//  F_{m+1}, and its left MSB is on the wire one SCLK later: T + 2 SCLK =
//  21.48 us = 1.031 periods.
//  The MCLK pin itself is the clock, forwarded by the board top (Phase 6).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_i2s_master (
    input  wire        mclk,
    input  wire        rst,                     // synchronous to mclk
    input  wire [23:0] bank_l,                  // clk_sys; stable around F_m (C4-D7)
    input  wire [23:0] bank_r,
    output reg         sclk,
    output reg         lrclk,
    output reg         sdata,
    output reg         strobe_tgl,
    output reg         frame_start              // one MCLK at F_m (tap)
);
    reg  [7:0]  cnt;
    reg  [23:0] l_r, r_r;
    wire [7:0]  nxt  = cnt + 8'd1;              // the position after this edge
    wire [5:0]  slot = nxt[7:2];

    // the bit of slot j: left word in slots 1..24, right word in 33..56, else 0
    function bit_of;
        input [5:0] j; input [23:0] l; input [23:0] r;
        begin
            if (j >= 6'd1 && j <= 6'd24)       bit_of = l[6'd24 - j];
            else if (j >= 6'd33 && j <= 6'd56) bit_of = r[6'd56 - j];
            else                               bit_of = 1'b0;
        end
    endfunction

    always @(posedge mclk) begin
        if (rst) begin
            cnt <= 8'd255;  sclk <= 1'b1;  lrclk <= 1'b1;  sdata <= 1'b0;
            strobe_tgl <= 1'b0;  frame_start <= 1'b0;  l_r <= 24'd0;  r_r <= 24'd0;
        end else begin
            cnt         <= nxt;
            sclk        <= nxt[1];
            lrclk       <= nxt[7];
            frame_start <= (nxt == 8'd0);
            if (nxt == 8'd0) begin                       // F_m: capture the bank
                l_r <= bank_l;  r_r <= bank_r;
            end
            if (nxt[1:0] == 2'd0)                        // SCLK falling edge: next bit
                sdata <= bit_of(slot, l_r, r_r);          // slot 0 is padding
            if (nxt == 8'd252) strobe_tgl <= ~strobe_tgl; // S_m = F_m - 4 MCLK
        end
    end
endmodule
