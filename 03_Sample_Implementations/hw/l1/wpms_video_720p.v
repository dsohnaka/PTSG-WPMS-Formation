// ============================================================================
//  wpms_video_720p.v — the video carrier (customer Ch.4 §4.7, C4-D9)
//  ビデオキャリア
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  HDMI carries audio only inside a video stream (Ch.4 §4.2): this is the
//  stream. 1280 x 720 progressive, 60 Hz, CEA-861 VIC 4, pixel clock 74.25 MHz
//  (clk_pix): 1650 clocks per line (1280 active, front porch 110, sync 40, back
//  porch 220), 750 lines per frame (720 active, 5, 5, 20); HSYNC and VSYNC
//  positive. 74.25 MHz / (1650 x 750) = 60.000 Hz.
//  Content is static (C4-D9): PATTERN 0 = black; 1 = eight vertical colour bars
//  (bring-up: a sink that shows the bars has locked the carrier). 24-bit RGB,
//  separate syncs, data enable — the ADV7513's input ID 0 (wpms_adv7513_cfg.v).
//  Nothing of the sound passes here.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_video_720p #(
    parameter integer PATTERN = 1
) (
    input  wire        clk_pix,                 // 74.25 MHz
    input  wire        rst,                     // synchronous to clk_pix
    output reg         hs,
    output reg         vs,
    output reg         de,
    output reg  [23:0] rgb,                     // {R, G, B}
    output wire        frame_start              // one clock at pixel (0, 0) (tap)
);
    localparam integer H_ACT = 1280, H_FP = 110, H_SY = 40, H_BP = 220, H_TOT = H_ACT + H_FP + H_SY + H_BP;
    localparam integer V_ACT = 720,  V_FP = 5,   V_SY = 5,  V_BP = 20,  V_TOT = V_ACT + V_FP + V_SY + V_BP;

    reg [10:0] h;  reg [9:0] v;
    always @(posedge clk_pix) begin
        if (rst) begin
            h <= 11'd0;  v <= 10'd0;
        end else if (h == H_TOT - 1) begin
            h <= 11'd0;
            v <= (v == V_TOT - 1) ? 10'd0 : v + 10'd1;
        end else begin
            h <= h + 11'd1;
        end
    end
    assign frame_start = (h == 11'd0) && (v == 10'd0) && !rst;

    // eight bars of 128 pixels (white, yellow, cyan, green, magenta, red, blue, black; 75 %), black beyond
    function [23:0] bar;
        input [2:0] i;
        begin
            case (i)
                3'd0: bar = 24'hBFBFBF;  3'd1: bar = 24'hBFBF00;  3'd2: bar = 24'h00BFBF;  3'd3: bar = 24'h00BF00;
                3'd4: bar = 24'hBF00BF;  3'd5: bar = 24'hBF0000;  3'd6: bar = 24'h0000BF;  default: bar = 24'h000000;
            endcase
        end
    endfunction

    wire act = (h < H_ACT) && (v < V_ACT);
    always @(posedge clk_pix) begin
        if (rst) begin
            hs <= 1'b0;  vs <= 1'b0;  de <= 1'b0;  rgb <= 24'd0;
        end else begin
            hs  <= (h >= H_ACT + H_FP) && (h < H_ACT + H_FP + H_SY);
            vs  <= (v >= V_ACT + V_FP) && (v < V_ACT + V_FP + V_SY);
            de  <= act;
            rgb <= (act && PATTERN == 1) ? bar(h[10:7] > 4'd7 ? 3'd7 : h[9:7]) : 24'd0;
        end
    end
endmodule
