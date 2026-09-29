// ============================================================================
//  wpms_output_stage.v — WPMS output stage (customer Ch.4 §4.4, §4.5)
//  WPMS 出力段
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  clk_sys. On every synchronized strobe (C4-D3):
//    S    the modules close their accumulators (wpms_l1_module); here the
//         master gain steps, MG <- MG + clamp(MG_target' - MG, +-MG_rate) — the
//         oracle's step_toward — and the new MG is what the sweep that this
//         strobe starts adds to every bin (C4-D4). MG_target' = the floor (-32)
//         under soft mute (DIP[3] | MUTE, C4-D6), else min(MG_TARGET, 0).
//    S+1  sum of the modules' closed accumulators (Q12.63 each -> Q13.63 for
//         M = 2, C3-D8)
//    S+2  round to nearest at 2^-23 * 2^G: add half, floor (C4-D5)
//    S+3  saturate to Q1.23, never wrap; sticky clip flag per channel; the
//         output bank is written (C4-D7: the bank changes only here, 3 clocks
//         after the strobe — at 50 MHz 60 ns, inside Delta_pre = 325.5 ns — and
//         is then stable for a whole period for the audio side's capture).
//  The bank is forced to exact zero (no clip) when the closed sweep was played
//  with MG at the floor under soft mute (C4-D6), or while the Formation's
//  error_flag is up (ruling 2026-09-28: L1 silenced at once — the bank reads
//  zero from the first close after the flag).
//  G = DIP[1:0] * 4 (0, 4, 8, 12), or g_ctrl[3:0] when g_ctrl[4] (Ch.5 0x013).
//  Bit for bit hw/tools/l1_model.py Output.strobe().
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_output_stage #(
    parameter integer M = 1                     // modules (Compact = 2)
) (
    input  wire               clk,
    input  wire               rst,
    input  wire               strobe,           // synchronized, one clock
    input  wire [75*M-1:0]    acc_l_closed,     // per module, Q12.63, valid from S+1
    input  wire [75*M-1:0]    acc_r_closed,
    input  wire [1:0]         dip_g,            // DIP[1:0]
    input  wire [4:0]         g_ctrl,           // [3:0] G override, [4] enable
    input  wire               soft_mute,        // DIP[3] | MUTE[0]
    input  wire               err_mute,         // the Formation's error_flag
    input  wire signed [31:0] mg_target,        // Q6.26, <= 0 (0x010)
    input  wire        [31:0] mg_rate,          // Q6.26 per sample, >= 0 (0x011)
    input  wire [1:0]         clip_clear,       // write-1-to-clear (0x016)
    output reg  signed [31:0] mg,               // current MG (0x012), to the L1 modules
    output wire [3:0]         g_eff,            // (0x014)
    output reg  signed [23:0] bank_l,           // Q1.23
    output reg  signed [23:0] bank_r,
    output reg                bank_we,          // one clock: the bank was written (tap)
    output reg  [1:0]         clip              // sticky (0x016)
);
    localparam signed [31:0] MG_FLOOR = 32'sh8000_0000;       // -32 in Q6.26
    localparam integer SW = 75 + ((M > 1) ? $clog2(M) : 0) + 2; // sum width, with rounding room

    assign g_eff = g_ctrl[4] ? g_ctrl[3:0] : {dip_g, 2'b00};

    // ---- S: master gain step (the oracle's step_toward) ------------------------------------
    wire signed [31:0] tgt  = soft_mute ? MG_FLOOR : (mg_target[31] ? mg_target : 32'sd0);
    wire signed [32:0] rate = mg_rate[31] ? 33'sd0 : $signed({1'b0, mg_rate});
    wire signed [32:0] dlt  = $signed({tgt[31], tgt}) - $signed({mg[31], mg});
    wire signed [32:0] stp  = (dlt > rate) ? rate : (dlt < -rate) ? -rate : dlt;
    wire signed [32:0] mg_n = $signed({mg[31], mg}) + stp;

    reg        go1, go2, go3;  reg zero1, zero2, zero3;  reg [3:0] g1, g2;
    always @(posedge clk) begin
        if (rst) begin
            mg <= 32'sd0;  go1 <= 1'b0;
        end else begin
            go1 <= strobe;
            if (strobe) begin
                mg    <= mg_n[31:0];
                zero1 <= err_mute || (soft_mute && mg == MG_FLOOR);   // mg = the closed sweep's MG
                g1    <= g_eff;
            end
        end
    end

    // ---- S+1: sum of modules -------------------------------------------------------------------
    reg signed [SW-1:0] sum_l, sum_r;
    integer mi;
    reg signed [SW-1:0] tl, tr;
    always @* begin
        tl = 0;  tr = 0;
        for (mi = 0; mi < M; mi = mi + 1) begin
            tl = tl + $signed(acc_l_closed[75*mi +: 75]);
            tr = tr + $signed(acc_r_closed[75*mi +: 75]);
        end
    end
    always @(posedge clk) begin
        go2 <= go1 && !rst;  zero2 <= zero1;  g2 <= g1;
        sum_l <= tl;  sum_r <= tr;
    end

    // ---- S+2: round to nearest at bit 40 + G ------------------------------------------------------
    reg signed [SW-41:0] rnd_l, rnd_r;
    wire signed [SW-1:0] half = $signed({{(SW-1){1'b0}}, 1'b1}) <<< (39 + g2);
    wire signed [SW-1:0] ul = (sum_l + half) >>> (40 + g2);
    wire signed [SW-1:0] ur = (sum_r + half) >>> (40 + g2);
    always @(posedge clk) begin
        go3 <= go2 && !rst;  zero3 <= zero2;
        rnd_l <= ul[SW-41:0];  rnd_r <= ur[SW-41:0];
    end

    // ---- S+3: saturate, clip, bank ---------------------------------------------------------------
    localparam signed [SW-41:0] PMAX =  (1 <<< 23) - 1;
    localparam signed [SW-41:0] PMIN = -(1 <<< 23);
    wire cl = (rnd_l > PMAX) || (rnd_l < PMIN);
    wire cr = (rnd_r > PMAX) || (rnd_r < PMIN);
    wire signed [23:0] sl = (rnd_l > PMAX) ? 24'sh7FFFFF : (rnd_l < PMIN) ? 24'sh800000 : rnd_l[23:0];
    wire signed [23:0] sr = (rnd_r > PMAX) ? 24'sh7FFFFF : (rnd_r < PMIN) ? 24'sh800000 : rnd_r[23:0];
    always @(posedge clk) begin
        if (rst) begin
            bank_l <= 24'sd0;  bank_r <= 24'sd0;  bank_we <= 1'b0;  clip <= 2'b00;
        end else begin
            bank_we <= go3;
            if (go3) begin
                bank_l <= zero3 ? 24'sd0 : sl;
                bank_r <= zero3 ? 24'sd0 : sr;
            end
            clip <= (clip & ~clip_clear) | ((go3 && !zero3) ? {cr, cl} : 2'b00);
        end
    end
endmodule
