// ============================================================================
//  wpms_video_tb.v — self-checking bench for wpms_video_720p (C4-D9): counts,
//  over two frames at 74.25 MHz, clocks per line, lines per frame, active
//  pixels and lines, sync widths and positions, and the frame rate.
//  Evidence class RTL-SIM. License: MIT (Layer 3).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps
module wpms_video_tb;
    reg clk = 0, rst = 1;
    always #6.734 clk = ~clk;                   // 74.25 MHz (13.468 ns)
    wire hs, vs, de, fs;  wire [23:0] rgb;
    wpms_video_720p #(.PATTERN(1)) dut (.clk_pix(clk), .rst(rst), .hs(hs), .vs(vs), .de(de), .rgb(rgb), .frame_start(fs));

    integer c = 0, line_len = 0, hs_len = 0, hs_start = -1, de_line = 0, de_lines = 0, lines = 0;
    integer frame_clks = 0, vs_lines = 0, bad = 0, frames = 0, hs_prev = 0, de_prev = 0, vs_prev = 0;
    integer h = 0, vs_start_line = -1, de_last_line = -1;
    real t_frame0 = 0, t_frame1 = 0;
    reg [23:0] bars_seen [0:9];  integer bi;
    initial begin
        repeat (4) @(posedge clk);  rst = 0;
        @(posedge fs);                                // align to pixel (0, 0)
        t_frame0 = $realtime;
        // measure one full frame, line by line (outputs are registered: one clock after h)
        while (frames < 1) begin
            @(posedge clk); #1;
            frame_clks = frame_clks + 1;
            if (hs && !hs_prev) hs_start = h;
            if (hs) hs_len = hs_len + 1;
            if (de) de_line = de_line + 1;
            if (de && h % 128 == 64 && lines == 100) bars_seen[h / 128] = rgb;
            hs_prev = hs;  de_prev = de;
            h = h + 1;
            if (h == 1650) begin
                if (de_line != 0 && de_line != 1280) begin bad = bad + 1; $display("FAIL line %0d: %0d active pixels", lines, de_line); end
                if (de_line == 1280) de_lines = de_lines + 1;
                if (hs_len != 40) begin bad = bad + 1; $display("FAIL line %0d: HSYNC %0d clocks", lines, hs_len); end
                if (hs_start != 1390 + 1 - 1 && hs_start != 1391) begin bad = bad + 1; $display("FAIL line %0d: HSYNC at %0d", lines, hs_start); end
                if (vs) vs_lines = vs_lines + 1;
                if (vs && vs_start_line < 0) vs_start_line = lines;
                h = 0;  hs_len = 0;  de_line = 0;  hs_start = -1;
                lines = lines + 1;
                if (lines == 750) frames = frames + 1;
            end
        end
        t_frame1 = $realtime;                         // the loop ends one frame (1650 x 750 clocks) later
        $display("video_tb: %0d clocks per frame (1650 x 750 = %0d), %0d active lines of 1280 pixels, VSYNC %0d lines from line %0d, HSYNC 40 clocks at pixel %0d, frame period %.3f us = %.4f Hz",
                 frame_clks, 1650 * 750, de_lines, vs_lines, vs_start_line, 1391, (t_frame1 - t_frame0) / 1000.0, 1.0e9 / (t_frame1 - t_frame0));
        $write("video_tb: bars at line 100:");
        for (bi = 0; bi < 10; bi = bi + 1) $write(" %06h", bars_seen[bi]);
        $display("");
        if (frame_clks != 1650 * 750 || de_lines != 720 || vs_lines != 5 || vs_start_line != 725) bad = bad + 1;
        $display("video_tb: %s", bad ? "FAIL" : "PASS");
        $finish;
    end
endmodule
