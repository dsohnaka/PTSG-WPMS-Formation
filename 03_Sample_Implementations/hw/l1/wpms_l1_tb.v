// ============================================================================
//  wpms_l1_tb.v — module-level cosimulation bench: wpms_l1_module +
//  wpms_output_stage, driven from a command file written by
//  hw/tools/cosim_l1.py, checked bin by bin and sample by sample against the
//  expectation files it writes (the customer's oracle + hw/tools/l1_model.py).
//  The bench stands where wpms_l2_top's L1 face and the strobe will stand.
//  Evidence class RTL-SIM. License: MIT (Layer 3).
//
//  +cmd=<file>   C dip_g g_ctrl soft err mg_target mg_rate | S | I n |
//                P n ph0 phd1 phd2 lp ls0 lad1 lad2 rt | E
//                (C: 0 clocks; S: one strobe clock; I: n idle clocks; P: n bins,
//                 packet_start with the first — the model counts the same clocks)
//  +bins=<file>  per bin, in order: phase a sin prod          (hex)
//  +banks=<file> per strobe: bank_l bank_r clip mg sweep_clocks, and the
//                inspector's capture of bin 7 of the closed sweep: valid phase L a (hex)
//  +nbins=, +nbanks=, +overrun=  expected counts and the expected overrun flag
//  Per bin the bench reads the module's own registers at their clocks: the
//  phase at c1, a at c7, sin at c17, the Q1.63 product at c19.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps
module wpms_l1_tb;
    parameter EXP2_HEX = "wpms_exp2_table.hex";
    reg clk = 0, rst = 1;
    always #5 clk = ~clk;

    // ---- stimulus ------------------------------------------------------------------------
    reg         packet_start = 0, bin_valid = 0, strobe = 0;
    reg  [11:0] k = 0;
    reg  [255:0] bundle = 0;
    reg  [1:0]  dip_g = 3;  reg [4:0] g_ctrl = 0;  reg soft_m = 0, err = 0;
    reg  [31:0] mgt = 0, mgr = 13933;

    wire signed [74:0] acc_l_closed, acc_r_closed;
    wire signed [31:0] mg;
    wire [11:0] sweep_clocks, sweep_clocks_max;  wire overrun;
    wire [31:0] insp_phase, insp_a;  wire signed [53:0] insp_L;
    wire signed [23:0] bank_l, bank_r;  wire bank_we;  wire [1:0] clip;  wire [3:0] g_eff;

    wpms_l1_module #(.EXP2_HEX(EXP2_HEX)) dut (
        .clk(clk), .rst(rst), .packet_start(packet_start), .bin_valid(bin_valid), .k(k),
        .bundle(bundle), .mute(err), .strobe(strobe), .mg(mg),
        .acc_l_closed(acc_l_closed), .acc_r_closed(acc_r_closed),
        .sweep_clocks(sweep_clocks), .sweep_clocks_max(sweep_clocks_max), .overrun(overrun),
        .insp_pos(12'd7), .insp_phase(insp_phase), .insp_L(insp_L), .insp_a(insp_a));
    wpms_output_stage #(.M(1)) out (
        .clk(clk), .rst(rst), .strobe(strobe), .acc_l_closed(acc_l_closed), .acc_r_closed(acc_r_closed),
        .dip_g(dip_g), .g_ctrl(g_ctrl), .soft_mute(soft_m), .err_mute(err),
        .mg_target(mgt), .mg_rate(mgr), .clip_clear(2'b00),
        .mg(mg), .g_eff(g_eff), .bank_l(bank_l), .bank_r(bank_r), .bank_we(bank_we), .clip(clip));

    // ---- expectation files ---------------------------------------------------------------------
    integer fc, fb, fk, r, nbins, nbanks, exp_over;
    integer bins_seen = 0, banks_seen = 0, bad_bins = 0, bad_banks = 0, shown = 0;
    reg [1023:0] fname;

    // ---- per-bin taps, aligned by small queues (the pipeline is in order) ------------------
    reg [31:0] q_ph [0:63];  integer ph_w = 0, ph_r = 0;
    reg [31:0] q_a  [0:63];  integer a_w = 0,  a_r = 0;
    reg [40:0] q_s  [0:63];  integer s_w = 0,  s_r = 0;
    reg [31:0] e_ph, e_a;  reg [40:0] e_s;  reg [63:0] e_p;
    always @(posedge clk) begin
        #2;
        if (!rst) begin
            if (dut.v1)          begin q_ph[ph_w % 64] = dut.ph1;   ph_w = ph_w + 1; end
            if (dut.v_dly[5])    begin q_a[a_w % 64]   = dut.a7;    a_w  = a_w + 1;  end
            if (dut.v17)         begin q_s[s_w % 64]   = dut.sin17; s_w  = s_w + 1;  end
            if (dut.v19) begin
                r = $fscanf(fb, "%h %h %h %h\n", e_ph, e_a, e_s, e_p);
                if (q_ph[ph_r % 64] !== e_ph || q_a[a_r % 64] !== e_a || q_s[s_r % 64] !== e_s || dut.p19 !== e_p) begin
                    bad_bins = bad_bins + 1;
                    if (shown < 8) begin
                        shown = shown + 1;
                        $display("MISMATCH bin %0d: phase %h/%h a %h/%h sin %h/%h prod %h/%h (RTL/expected)", bins_seen,
                                 q_ph[ph_r % 64], e_ph, q_a[a_r % 64], e_a, q_s[s_r % 64], e_s, dut.p19, e_p);
                    end
                end
                ph_r = ph_r + 1;  a_r = a_r + 1;  s_r = s_r + 1;  bins_seen = bins_seen + 1;
            end
        end
    end

    // ---- per-strobe: the bank, clip, MG, sweep_clocks ------------------------------------------
    reg [23:0] e_l, e_r;  reg [3:0] e_clip;  reg [31:0] e_mg;  reg [11:0] e_sc;
    reg [3:0]  e_iv;  reg [31:0] e_ip, e_ia;  reg [53:0] e_iL;  integer insp_checked = 0;
    always @(posedge clk) begin
        #2;
        if (!rst && bank_we) begin
            r = $fscanf(fk, "%h %h %h %h %h %h %h %h %h\n", e_l, e_r, e_clip, e_mg, e_sc, e_iv, e_ip, e_iL, e_ia);
            if (e_iv[0]) begin
                insp_checked = insp_checked + 1;
                if (insp_phase !== e_ip || insp_L !== e_iL || insp_a !== e_ia) begin
                    bad_banks = bad_banks + 1;
                    if (shown < 16) begin shown = shown + 1;
                        $display("MISMATCH inspector, sample %0d: phase %h/%h L %h/%h a %h/%h", banks_seen, insp_phase, e_ip, insp_L, e_iL, insp_a, e_ia); end
                end
            end
            if (bank_l !== e_l || bank_r !== e_r || clip !== e_clip[1:0] || mg !== e_mg || sweep_clocks !== e_sc) begin
                bad_banks = bad_banks + 1;
                if (shown < 16) begin
                    shown = shown + 1;
                    $display("MISMATCH sample %0d: L %h/%h R %h/%h clip %b/%b MG %h/%h sweep_clocks %0d/%0d (RTL/expected)",
                             banks_seen, bank_l, e_l, bank_r, e_r, clip, e_clip[1:0], mg, e_mg, sweep_clocks, e_sc);
                end
            end
            banks_seen = banks_seen + 1;
        end
    end

    // ---- the command loop ------------------------------------------------------------------------
    reg [7:0] op;  integer n, j, g_ctrl_i;
    reg [31:0] w0, w1, w2, w3, w4, w5, w6, w7;
    integer d_g, soft_i, err_i;
    task tick; begin @(posedge clk); #1; end endtask
    initial begin
        if (!$value$plusargs("cmd=%s", fname)) begin $display("TB: +cmd missing"); $finish; end
        fc = $fopen(fname, "r");
        r = $value$plusargs("bins=%s", fname);  fb = $fopen(fname, "r");
        r = $value$plusargs("banks=%s", fname); fk = $fopen(fname, "r");
        r = $value$plusargs("nbins=%d", nbins);  r = $value$plusargs("nbanks=%d", nbanks);
        r = $value$plusargs("overrun=%d", exp_over);
        repeat (4) tick;
        rst = 0;
        tick;
        forever begin
            r = $fscanf(fc, " %c", op);
            if (r != 1 || op == "E") begin
                repeat (8) tick;
                $display("TB: %0d/%0d bins compared (%0d mismatches), %0d/%0d samples compared (%0d mismatches, incl. %0d inspector captures); overrun %0d (expected %0d); sweep_clocks_max %0d",
                         bins_seen, nbins, bad_bins, banks_seen, nbanks, bad_banks, insp_checked, overrun, exp_over, sweep_clocks_max);
                if (bins_seen == nbins && banks_seen == nbanks && bad_bins == 0 && bad_banks == 0 && overrun == exp_over)
                    $display("TB: PASS");
                else
                    $display("TB: FAIL");
                $finish;
            end
            case (op)
            "C": begin
                r = $fscanf(fc, "%d %h %d %d %h %h", d_g, g_ctrl_i, soft_i, err_i, w0, w1);
                dip_g = d_g;  g_ctrl = g_ctrl_i;  soft_m = soft_i;  err = err_i;  mgt = w0;  mgr = w1;
            end
            "S": begin strobe = 1; tick; strobe = 0; end
            "I": begin r = $fscanf(fc, "%d", n); repeat (n) tick; end
            "P": begin
                r = $fscanf(fc, "%d %h %h %h %h %h %h %h %h", n, w0, w1, w2, w3, w4, w5, w6, w7);
                bundle = {w7, w6, w5, w4, w3, w2, w1, w0};
                for (j = 0; j < n; j = j + 1) begin
                    packet_start = (j == 0);  bin_valid = 1;  k = j;
                    tick;
                end
                packet_start = 0;  bin_valid = 0;
            end
            default: begin $display("TB: bad command %c", op); $finish; end
            endcase
        end
    end
endmodule
