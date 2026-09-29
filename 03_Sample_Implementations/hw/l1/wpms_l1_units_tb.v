// ============================================================================
//  wpms_l1_units_tb.v — streams one phase and one log-amplitude per clock
//  through wpms_l1_sin and wpms_l1_exp2 and writes what comes out; the
//  comparison (against l1_model.sin_q040 and the oracle's exp2_q131) is done by
//  hw/tools/cosim_l1.py. Evidence class RTL-SIM. License: MIT (Layer 3).
//    +in=<file>   lines "PPPPPPPP LLLLLLLLLLLLLL" (hex: phase, 54-bit L)
//    +out=<file>  lines "SSSSSSSSSSS AAAAAAAA"   (hex: sin Q0.40 as 41 bits, a)
//    +n=<count>
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps
module wpms_l1_units_tb;
    parameter EXP2_HEX = "wpms_exp2_table.hex";
    reg clk = 0;
    always #5 clk = ~clk;

    reg  [31:0]        phase = 0;
    reg  signed [53:0] L = 0;
    wire signed [40:0] sin_out;
    wire [31:0]        a;
    wpms_l1_sin  u_sin  (.clk(clk), .phase(phase), .sin_out(sin_out));
    wpms_l1_exp2 #(.TABLE_HEX(EXP2_HEX)) u_exp2 (.clk(clk), .L(L), .a(a));

    integer fi, fo, n, j, r;
    reg [1023:0] fin, fout;
    reg [31:0] a_q [0:15];
    reg [31:0] p_in;  reg [53:0] l_in;
    initial begin
        if (!$value$plusargs("in=%s", fin) || !$value$plusargs("out=%s", fout) || !$value$plusargs("n=%d", n)) begin
            $display("usage: +in=<file> +out=<file> +n=<count>"); $finish;
        end
        fi = $fopen(fin, "r");  fo = $fopen(fout, "w");
        // input j is applied before edge j; the sin core's 16th register holds its
        // result after edge j+15, the exp2 unit's 6th after edge j+5
        for (j = 0; j < n + 15; j = j + 1) begin
            if (j < n) begin
                r = $fscanf(fi, "%h %h\n", p_in, l_in);
                phase <= p_in;  L <= $signed(l_in);
            end
            @(posedge clk); #1;
            if (j >= 5 && j - 5 < n)   a_q[(j - 5) % 16] = a;
            if (j >= 15 && j - 15 < n) $fdisplay(fo, "%011h %08h", sin_out, a_q[(j - 15) % 16]);
        end
        $fclose(fo);
        $display("units_tb: %0d inputs streamed", n);
        $finish;
    end
endmodule
