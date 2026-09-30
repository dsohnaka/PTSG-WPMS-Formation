// ============================================================================
//  wpms_system_tb.v — system bench for wpms_system (Phase 5), with the
//  deterministic controller of the host path
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  THE DETERMINISTIC CONTROLLER (architect's ruling of 2026-09-30): it drives
//  host_src_ext, which wpms_system ORs with the ISSP instance HOST (0 in
//  simulation), with exactly the bit protocol a person uses in the Quartus
//  editor (wpms_host_bridge.v): set ADDR/WDATA, flip WR or RD, wait until the
//  probe's acknowledge equals the toggle. With skew m > 0 the toggle moves m
//  clocks BEFORE the fields — worse than the ISSP itself, which updates all
//  its source bits at once.
//  Plays a command file written by hw/tools/cosim_switch.py and records events;
//  cosim_switch.py checks them against hw/tools/switch_model.py (the switch),
//  sweep_sim.Reference (the page) and l1_model.py over the customer's oracle
//  (the sound).
//
//  Commands (numbers in hex):
//    R n        reset both clock domains for n clk_sys clocks (memories keep
//               their contents, as on the board; zeroed once at time 0)
//    X n t      reset for n clocks and flip the toggles t (1 WR, 2 RD, 3 both)
//               in the middle of it (a design reset with the editor's sources set)
//    W a d      host write            Q a      host read
//    S m        skew for the next host operations (the fields lag the toggle by m)
//    P n        idle clocks after each host operation (default 4)
//    N n        n idle clocks          G n      wait for n strobes
//    A k        wait for the next strobe, then k clocks
//    K b        press KEY[b] (b = 0: GO_ALL, 1: test origin)
//    D v        DIP[3:0] = v           E        end
//  Events (cyc = clk_sys clocks since time 0):
//    S cyc                          the synchronized strobe
//    X exec port we addr wdata rdata rej live
//                                   a switch transaction (EXEC clock; answer of
//                                   the DONE clock); live = the tap the word reads,
//                                   taken by this bench at EXEC (read-through words)
//    U cyc open ft                  the switch's apply step (EXEC clock)
//    I cyc addr data hand seq       a write presented on the Formation's inbox port
//    B cyc                          inbox_taken rose
//    C cyc mgt mgr gctrl mute geff soft   the output stage's knobs in the strobe clock
//    W cyc addr data rdata rej      the controller's write, as its probe answered
//    Q cyc addr rdata               the controller's read
//    K cyc b                        a key press accepted (the debounced pulse)
//    O, L, P, F, H                  as wpms_synth_tb.v (banks, latches, packets, errors)
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps
module wpms_system_tb;
    parameter SCORE    = "wpms_r1d.hex";
    parameter EXP2_HEX = "wpms_exp2_table.hex";
    parameter ROM_HEX  = "wpms_rom_origin_1008.hex";
    parameter integer NMAX  = 1008;
    parameter integer N_MIN = 32;
    parameter integer DEB   = 16;
    parameter real    SYS_HALF = 10.0;

    reg clk = 0, rst = 1, aclk = 0, arst = 1;
    always #(SYS_HALF) clk = ~clk;
    always #40.690 aclk = ~aclk;               // 12.288 MHz

    reg  [1:0]  key_n = 2'b11;
    reg  [3:0]  dip = 4'b0011;                 // G = 12
    reg  [47:0] hsrc = 48'd0;                  // the deterministic controller's source bits
    wire [35:0] prb;
    wire        i2s_sclk, i2s_lrclk, i2s_sdata, strobe, bank_we, error_flag, core_error_flag, inbox_taken;
    wire signed [23:0] bank_l, bank_r;
    wire [27:0] sweep_a;
    wire        l1_packet_start, l1_bin_valid;  wire [11:0] l1_k;  wire [255:0] l1_bundle;

    wpms_system #(.NMAX(NMAX), .N_MIN(N_MIN), .SCORE_HEX(SCORE), .EXP2_HEX(EXP2_HEX), .ROM_HEX(ROM_HEX),
                  .KEY_DEBOUNCE(DEB)) dut (
        .clk_sys(clk), .rst_sys(rst), .clk_aud(aclk), .rst_aud(arst),
        .key_n(key_n), .dip(dip), .i2s_sclk(i2s_sclk), .i2s_lrclk(i2s_lrclk), .i2s_sdata(i2s_sdata),
        .host_src_ext(hsrc), .host_prb(prb),
        .strobe(strobe), .bank_we(bank_we), .bank_l(bank_l), .bank_r(bank_r),
        .error_flag(error_flag), .core_error_flag(core_error_flag), .inbox_taken(inbox_taken),
        .sweep_a(sweep_a), .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid),
        .l1_k(l1_k), .l1_bundle(l1_bundle));

    integer fout, cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    reg [1023:0] vcdfile;
    initial if ($value$plusargs("vcd=%s", vcdfile)) begin
        $dumpfile(vcdfile);
        $dumpvars(1, dut);
        $dumpvars(1, dut.u_sw, dut.u_bridge);
    end

    // ---- the switch, white-box -----------------------------------------------------------------
    reg         xe_v = 0, xe_p3, xe_we;  reg [11:0] xe_a;  reg [31:0] xe_d, xe_live;  integer xe_cyc;
    // SWEEP_CLOCKS_MAX kept here too, independently: the largest SWEEP_CLOCKS since reset or a write to 0x299
    reg  [11:0] tb_scm = 12'd0;
    always @(posedge clk)
        if (rst || (dut.u_sw.x_v && !dut.u_sw.x_unf && dut.u_sw.x_we && dut.u_sw.x_a == 12'h299)) tb_scm <= 12'd0;
        else if (dut.u_synth.sweep_clocks > tb_scm) tb_scm <= dut.u_synth.sweep_clocks;
    wire signed [49:0] tb_l26 = dut.u_synth.insp_L >>> 4;
    function [31:0] live_of; input [11:0] a; begin
        case (a)
            12'h012: live_of = dut.u_synth.mg;
            12'h014: live_of = {28'd0, dut.u_synth.g_eff};
            12'h016: live_of = {30'd0, dut.u_synth.clip};
            12'h018: live_of = {20'd0, dut.u_synth.strobe_interval};
            12'h019: live_of = {4'd0, dut.u_synth.strobe_max, 4'd0, dut.u_synth.strobe_min};
            12'h041: live_of = dut.u_synth.insp_phase;
            12'h042: live_of = (tb_l26 >  50'sd2147483647) ? 32'h7FFFFFFF :
                               (tb_l26 < -50'sd2147483648) ? 32'h80000000 : tb_l26[31:0];
            12'h043: live_of = dut.u_synth.insp_a;
            12'h292: live_of = {4'd0, sweep_a};
            12'h298: live_of = {20'd0, dut.u_synth.sweep_clocks};
            12'h299: live_of = {20'd0, tb_scm};
            default: live_of = 32'd0;
        endcase
    end endfunction
    always @(posedge clk) if (!rst) begin
        if (dut.u_sw.d_v && xe_v)
            $fwrite(fout, "X %0d %0d %0d %03h %08h %08h %0d %08h\n", xe_cyc, xe_p3 ? 3 : 0, xe_we, xe_a, xe_d,
                    dut.u_sw.rdata, dut.u_sw.rej, xe_live);
        xe_v <= 1'b0;
        if (dut.u_sw.x_v && !dut.u_sw.x_unf) begin
            xe_v <= 1'b1;  xe_cyc <= cyc;  xe_p3 <= dut.u_sw.x_p3;  xe_we <= dut.u_sw.x_we;
            xe_a <= dut.u_sw.x_a;  xe_d <= dut.u_sw.x_d;  xe_live <= live_of(dut.u_sw.x_a);
        end
        if (dut.u_sw.x_v && dut.u_sw.x_unf) $fwrite(fout, "U %0d %0d %03h\n", cyc, dut.u_sw.ft_open, dut.u_sw.ft);
        if (dut.u_sw.ibx_we)
            $fwrite(fout, "I %0d %02h %08h %0d %0d\n", cyc, dut.u_sw.ibx_addr, dut.u_sw.ibx_wdata,
                    dut.u_sw.ibx_hand, dut.u_sw.ibx_seq);
        if (strobe)
            $fwrite(fout, "C %0d %08h %08h %0d %0d %0d %0d\n", cyc, dut.u_synth.mg_target, dut.u_synth.mg_rate,
                    dut.u_synth.g_ctrl, dut.u_sw.mute, dut.u_synth.g_eff, dut.u_synth.soft_mute);
        if (dut.key_go_all) $fwrite(fout, "K %0d 0\n", cyc);
        if (dut.key_origin) $fwrite(fout, "K %0d 1\n", cyc);
    end
    reg taken_d = 0;
    always @(posedge clk) begin
        if (!rst && inbox_taken && !taken_d) $fwrite(fout, "B %0d\n", cyc);
        taken_d <= inbox_taken;
    end

    // ---- the L1 face and the output (as wpms_synth_tb.v) ---------------------------------------
    integer nbins = 0, kok = 1, in_pkt = 0, k;
    always @(posedge clk) if (!rst) begin
        if (l1_packet_start) begin
            if (in_pkt) $fwrite(fout, "P %0d %0d %0d\n", cyc, nbins, kok);
            $fwrite(fout, "L %0d %0d", cyc, (sweep_a >> (4 + 3 * dut.u_synth.u_l2.seq.q_r)) & 7);
            for (k = 0; k < 8; k = k + 1) $fwrite(fout, " %08h", l1_bundle[32*k +: 32]);
            $fwrite(fout, "\n");
            in_pkt = 1; nbins = 1; kok = (l1_k == 12'd0) && l1_bin_valid;
        end else if (in_pkt) begin
            if (l1_bin_valid) begin
                if (l1_k != nbins) kok = 0;
                nbins = nbins + 1;
            end else begin
                $fwrite(fout, "P %0d %0d %0d\n", cyc, nbins, kok);
                in_pkt = 0;
            end
        end
    end
    reg err_d = 0, cerr_d = 0;
    always @(posedge clk) if (!rst) begin
        if (strobe) $fwrite(fout, "S %0d\n", cyc);
        if (error_flag && !err_d) $fwrite(fout, "F %0d %0d %03h\n", cyc, dut.u_synth.error_code, dut.u_synth.error_sn);
        if (core_error_flag && !cerr_d) $fwrite(fout, "H %0d %03h\n", cyc, dut.u_synth.state_number);
        if (bank_we) $fwrite(fout, "O %0d %06h %06h %0d %08h %0d %0d\n", cyc, bank_l & 24'hFFFFFF, bank_r & 24'hFFFFFF,
                             dut.u_synth.clip, dut.u_synth.mg, dut.u_synth.sweep_clocks, dut.u_synth.overrun);
        err_d <= error_flag; cerr_d <= core_error_flag;
    end

    // ---- power-up: FPGA memories start at 0 ------------------------------------------------------
    task zero_memories; integer b; begin
        for (b = 0; b < 8; b = b + 1) begin
            dut.u_synth.u_l2.form.st_n[b] = 0; dut.u_synth.u_l2.form.ib_n[b] = 0;
            dut.u_synth.u_l2.form.g_store[1].m[b] = 0;  dut.u_synth.u_l2.form.g_store[2].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[3].m[b] = 0;  dut.u_synth.u_l2.form.g_store[4].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[5].m[b] = 0;  dut.u_synth.u_l2.form.g_store[6].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[7].m[b] = 0;  dut.u_synth.u_l2.form.g_store[8].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[9].m[b] = 0;  dut.u_synth.u_l2.form.g_store[10].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[11].m[b] = 0; dut.u_synth.u_l2.form.g_store[12].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[13].m[b] = 0; dut.u_synth.u_l2.form.g_store[14].m[b] = 0;
            dut.u_synth.u_l2.form.g_store[15].m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[1].g_bank.m[b] = 0;  dut.u_synth.u_l2.form.g_inbox[2].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[3].g_bank.m[b] = 0;  dut.u_synth.u_l2.form.g_inbox[4].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[5].g_bank.m[b] = 0;  dut.u_synth.u_l2.form.g_inbox[6].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[7].g_bank.m[b] = 0;  dut.u_synth.u_l2.form.g_inbox[8].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[9].g_bank.m[b] = 0;  dut.u_synth.u_l2.form.g_inbox[10].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[11].g_bank.m[b] = 0; dut.u_synth.u_l2.form.g_inbox[12].g_bank.m[b] = 0;
            dut.u_synth.u_l2.form.g_inbox[15].g_bank.m[b] = 0;
        end
    end endtask

    // ---- the deterministic controller ------------------------------------------------------------
    integer skew = 0, gap = 4, waited;
    task host_op; input is_wr; input [11:0] a; input [31:0] d; begin
        if (skew == 0) begin
            hsrc = {2'b00, hsrc[45] ^ !is_wr, hsrc[44] ^ is_wr, a, d};
        end else begin
            if (is_wr) hsrc[44] = ~hsrc[44]; else hsrc[45] = ~hsrc[45];
            repeat (skew) @(negedge clk);
            hsrc[43:0] = {a, d};
        end
        waited = 0;
        while ((prb[32] != hsrc[44] || prb[33] != hsrc[45]) && waited < 20000) begin
            @(negedge clk); waited = waited + 1;
        end
        if (waited >= 20000) $fwrite(fout, "T %0d\n", cyc);
        if (is_wr) $fwrite(fout, "W %0d %03h %08h %08h %0d\n", cyc, a, d, prb[31:0], prb[34]);
        else       $fwrite(fout, "Q %0d %03h %08h\n", cyc, a, prb[31:0]);
        repeat (gap) @(negedge clk);
    end endtask

    // ---- command interpreter -----------------------------------------------------------------
    integer fin, r, v0, v1, ns;
    reg [8*8-1:0] cmd;
    reg [8*512-1:0] stim_path, out_path;
    initial begin
        if (!$value$plusargs("stim=%s", stim_path)) stim_path = "stim.txt";
        if (!$value$plusargs("out=%s", out_path))   out_path  = "results.txt";
        fin  = $fopen(stim_path, "r");
        fout = $fopen(out_path, "w");
        if (fin == 0) begin $display("wpms_system_tb: cannot open %0s", stim_path); $finish; end
        zero_memories;
        @(negedge clk);
        while (!$feof(fin)) begin
            r = $fscanf(fin, "%s", cmd);
            if (r != 1) r = $fgetc(fin);
            else case (cmd)
                "R", "X": begin
                        r = $fscanf(fin, "%h", v0);
                        if (cmd == "X") r = $fscanf(fin, "%h", v1); else v1 = 0;
                        rst = 1; arst = 1;
                        repeat (v0 / 2) @(negedge clk);
                        if (v1[0]) hsrc[44] = ~hsrc[44];
                        if (v1[1]) hsrc[45] = ~hsrc[45];
                        repeat (v0 - v0 / 2) @(negedge clk);
                        @(negedge aclk); arst = 0;
                        @(negedge clk); rst = 0;
                        $fwrite(fout, "R %0d\n", cyc);
                     end
                "W": begin r = $fscanf(fin, "%h %h", v0, v1); host_op(1'b1, v0, v1); end
                "Q": begin r = $fscanf(fin, "%h", v0); host_op(1'b0, v0, 32'd0); end
                "S": begin r = $fscanf(fin, "%h", v0); skew = v0; end
                "P": begin r = $fscanf(fin, "%h", v0); gap = v0; end
                "N": begin r = $fscanf(fin, "%h", v0); repeat (v0) @(negedge clk); end
                "G": begin
                        r = $fscanf(fin, "%h", v0);
                        for (ns = 0; ns < v0; ns = ns + 1) begin
                            @(negedge clk);
                            waited = 0;
                            while (!strobe && waited < 10000) begin @(negedge clk); waited = waited + 1; end
                            if (waited >= 10000) $fwrite(fout, "T %0d\n", cyc);
                        end
                     end
                "A": begin
                        r = $fscanf(fin, "%h", v0);
                        @(negedge clk);
                        waited = 0;
                        while (!strobe && waited < 10000) begin @(negedge clk); waited = waited + 1; end
                        repeat (v0) @(negedge clk);
                     end
                "K": begin
                        r = $fscanf(fin, "%h", v0);
                        key_n[v0] = 1'b0;  repeat (DEB + 8) @(negedge clk);
                        key_n[v0] = 1'b1;  repeat (DEB + 8) @(negedge clk);
                     end
                "D": begin r = $fscanf(fin, "%h", v0); dip = v0; end
                "E": ;
                default: $display("wpms_system_tb: unknown command %0s", cmd);
            endcase
        end
        repeat (8) @(negedge clk);
        $fwrite(fout, "Y %0d %0d %0d %0d %0d\n", dut.u_synth.strobe_interval, dut.u_synth.strobe_min,
                dut.u_synth.strobe_max, dut.u_sw.sweep_clocks_max, dut.u_synth.overrun);
        $fclose(fout);
        $display("wpms_system_tb: done at clock %0d", cyc);
        $finish;
    end
endmodule
