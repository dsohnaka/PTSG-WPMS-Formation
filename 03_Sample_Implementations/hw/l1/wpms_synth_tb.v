// ============================================================================
//  wpms_synth_tb.v — system-level bench for wpms_synth_top (Phase 4)
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  Stands where the input switch (Phase 5) and the ADV7513 (Phase 6) will
//  stand. Plays a command file written by hw/tools/cosim_synth.py and records
//  events; cosim_synth.py compares them with the sweep oracle (bundles) and
//  hw/tools/l1_model.py over the customer's oracle (samples).
//
//  Clocks: clk_sys with half period SYS_HALF (ns; 10 = 50 MHz, 5 = 100 MHz);
//  clk_aud = MCLK 12.288 MHz (half period 40.690 ns), always running.
//  Two modes:
//    +forcestrobe   the bench gives the strobe itself (command S), after the
//                   sweep and the L1 pipeline are over — the sweep oracle's GO
//                   traffic needs more clocks between sweeps than a full-load
//                   48 kHz period leaves (as Phase 3; each sweep's length and
//                   SWEEP_CLOCKS are still checked against T_min)
//    (default)      the strobe comes from the I2S master through the
//                   synchronizer: the real 48 kHz grid
//  Commands (numbers in hex):
//    R n        reset for n clocks (store and inbox power up as 0)
//    X a d      input-switch write, one clock
//    W          wait until the sequencer is idle and the L1 pipeline empty
//    N n        n idle clk_sys clocks
//    S          the strobe, one clock (+forcestrobe only)
//    G n        wait for n strobes (grid mode)
//    K          wait for inbox_taken to rise (BCP of this sweep has landed)
//    D g c      DIP[1:0] = g, g_ctrl = c
//    M t r s    MG_TARGET = t, MG_RATE = r, soft mute = s
//    E          end
//  Events (cyc = clk_sys clocks since time 0):
//    as wpms_l2_tb.v: S L P A V D U B C F H Q M T
//    O cyc l r clip mg sweep_clocks overrun   the output bank was written
//    Z cyc nbins nonzero                      end of a packet: bins with a != 0
//    I t_ns                                   the audio-side strobe toggled (time, ns)
//    J t_ns cyc l r cap_l cap_r               one I2S frame: its LRCLK falling edge F
//                                             (time, and clk_sys cycle), the words a
//                                             receiver decodes from SDATA, and the
//                                             words the master captured at F
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps
module wpms_synth_tb;
    parameter SCORE    = "wpms_r1d.hex";
    parameter EXP2_HEX = "wpms_exp2_table.hex";
    parameter integer NMAX  = 1008;
    parameter integer N_MIN = 32;
    parameter real    SYS_HALF = 10.0;

    reg clk = 0, rst = 1, aclk = 0, arst = 1;
    always #(SYS_HALF) clk = ~clk;
    always #40.690 aclk = ~aclk;               // 12.288 MHz (81.380 ns)

    reg         ibx_we = 0;  reg [7:0] ibx_addr = 0;  reg [31:0] ibx_wdata = 0;
    reg  [1:0]  dip_g = 3;   reg [4:0] g_ctrl = 0;    reg soft_m = 0;
    reg  [31:0] mg_target = 0, mg_rate = 13933;
    wire        inbox_taken, strobe, frame_start, bank_we, overrun;
    wire        i2s_sclk, i2s_lrclk, i2s_sdata;
    wire signed [23:0] bank_l, bank_r;
    wire [1:0]  clip;  wire signed [31:0] mg;  wire [3:0] g_eff;
    wire [11:0] strobe_interval, strobe_min, strobe_max, sweep_clocks, sweep_clocks_max;
    wire [31:0] insp_phase, insp_a;  wire signed [53:0] insp_L;
    wire        error_flag, core_error_flag, seq_idle, stack_spill;
    wire [4:0]  error_code;  wire [11:0] error_sn, state_number;  wire [27:0] sweep_a;
    wire        l1_packet_start, l1_bin_valid;  wire [11:0] l1_k;  wire [255:0] l1_bundle;

    wpms_synth_top #(.NMAX(NMAX), .N_MIN(N_MIN), .SCORE_HEX(SCORE), .EXP2_HEX(EXP2_HEX)) dut (
        .clk_sys(clk), .rst_sys(rst), .clk_aud(aclk), .rst_aud(arst),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata), .inbox_taken(inbox_taken),
        .dip_g(dip_g), .g_ctrl(g_ctrl), .soft_mute(soft_m), .mg_target(mg_target), .mg_rate(mg_rate),
        .clip_clear(2'b00), .minmax_clear(1'b0), .insp_pos(12'd0),
        .i2s_sclk(i2s_sclk), .i2s_lrclk(i2s_lrclk), .i2s_sdata(i2s_sdata),
        .strobe(strobe), .frame_start(frame_start), .bank_l(bank_l), .bank_r(bank_r), .bank_we(bank_we),
        .clip(clip), .mg(mg), .g_eff(g_eff), .strobe_interval(strobe_interval), .strobe_min(strobe_min),
        .strobe_max(strobe_max), .sweep_clocks(sweep_clocks), .sweep_clocks_max(sweep_clocks_max),
        .overrun(overrun), .insp_phase(insp_phase), .insp_L(insp_L), .insp_a(insp_a),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .core_error_flag(core_error_flag), .state_number(state_number), .sweep_a(sweep_a),
        .seq_idle(seq_idle), .stack_spill(stack_spill),
        .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid), .l1_k(l1_k), .l1_bundle(l1_bundle));

    // ---- mode -----------------------------------------------------------------------------------------
    reg tb_strobe = 0;  reg forced = 0;
    initial if ($test$plusargs("forcestrobe")) begin
        forced = 1;
        force dut.strobe = tb_strobe;
    end

    integer fout, cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    // +vcd=<file>: the top's ports and the Core's control state (debugging and evidence)
    reg [1023:0] vcdfile;
    initial if ($value$plusargs("vcd=%s", vcdfile)) begin
        $dumpfile(vcdfile);
        $dumpvars(1, dut);
        $dumpvars(1, dut.u_l2.core.fsm, dut.u_l2.core.state_num, dut.u_l2.core.window_open,
                  dut.u_l2.core.insert_req, dut.u_l2.core.insert_ack, dut.u_l2.core.hr_occupied,
                  dut.u_l2.core.stay_cnt_match, dut.u_l2.form.insert_req_r, dut.u_l2.form.jumpval);
    end

    // ---- the L1 face: latches, bins, K (as wpms_l2_tb.v), and a != 0 per packet -------------
    integer nbins = 0, kok = 1, in_pkt = 0, k;
    always @(posedge clk) if (!rst) begin
        if (l1_packet_start) begin
            if (in_pkt) $fwrite(fout, "P %0d %0d %0d\n", cyc, nbins, kok);
            $fwrite(fout, "L %0d %0d", cyc, (sweep_a >> (4 + 3 * dut.u_l2.seq.q_r)) & 7);
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
        if (dut.u_l2.l1_mute && (l1_bin_valid || l1_packet_start)) $fwrite(fout, "M %0d\n", cyc);
    end
    // nonzero amplitudes per packet, counted where a leaves the exp2 unit (c7)
    integer za_bins = 0, za_nz = 0;  reg za_in = 0;
    wire a7_valid = dut.u_l1.v_dly[5];
    reg  [11:0] a7_k;                                          // K of the c7 bin (from the face, 7 clocks back)
    reg  [11:0] kpipe [0:6];  integer kp;
    always @(posedge clk) begin
        kpipe[0] <= l1_k;
        for (kp = 1; kp < 7; kp = kp + 1) kpipe[kp] <= kpipe[kp-1];
    end
    always @(posedge clk) if (!rst) begin
        if (a7_valid && kpipe[6] == 12'd0 && za_in) begin
            $fwrite(fout, "Z %0d %0d %0d\n", cyc, za_bins, za_nz);  za_bins = 0;  za_nz = 0;
        end
        if (a7_valid) begin
            za_in = 1;  za_bins = za_bins + 1;  if (dut.u_l1.a7 != 0) za_nz = za_nz + 1;
        end else if (za_in) begin
            $fwrite(fout, "Z %0d %0d %0d\n", cyc, za_bins, za_nz);  za_bins = 0;  za_nz = 0;  za_in = 0;
        end
    end

    // ---- Core / sequencer / Formation / output events (as wpms_l2_tb.v, plus O) ---------
    reg idle_d = 1, busy_d = 0, err_d = 0, cerr_d = 0, spill_d = 0, hk_end = 0;
    always @(posedge clk) if (!rst) begin
        if (dut.u_l2.seq.det)
            $fwrite(fout, "A %0d %0d %03h %0d\n", cyc, dut.u_l2.timing_signals[0], dut.u_l2.seq.sn_prev, dut.u_l2.stay_value);
        if (dut.u_l2.core.fsm == 3'd0 && dut.u_l2.core.opcode == 4'd1)
            $fwrite(fout, "V %0d %03h %0d\n", cyc, state_number, dut.u_l2.stay_value);
        if (seq_idle && !idle_d) $fwrite(fout, "D %0d\n", cyc);
        if ((hk_end || (dut.u_l2.seq_phase == 2'd3 && dut.u_l2.core.stay_cnt_match)) &&
            dut.u_l2.core.fsm == 3'd0 && dut.u_l2.core.opcode == 4'd2 && dut.u_l2.core.operand == 12'd0) begin
            $fwrite(fout, "U %0d\n", cyc); hk_end <= 1'b0;
        end else if (dut.u_l2.seq_phase == 2'd3 && dut.u_l2.core.stay_cnt_match) hk_end <= 1'b1;
        if (strobe) $fwrite(fout, "S %0d\n", cyc);
        if (dut.u_l2.form.bcp_commit) $fwrite(fout, "B %0d %02h\n", cyc, dut.u_l2.form.new_list);
        if (!dut.u_l2.form.bcp_busy && busy_d) $fwrite(fout, "C %0d\n", cyc);
        if (error_flag && !err_d) $fwrite(fout, "F %0d %0d %03h\n", cyc, error_code, error_sn);
        if (core_error_flag && !cerr_d) $fwrite(fout, "H %0d %03h\n", cyc, state_number);
        if (stack_spill && !spill_d) $fwrite(fout, "Q %0d %03h\n", cyc, state_number);
        if (bank_we) $fwrite(fout, "O %0d %06h %06h %0d %08h %0d %0d\n", cyc, bank_l & 24'hFFFFFF, bank_r & 24'hFFFFFF,
                             clip, mg, sweep_clocks, overrun);
        idle_d <= seq_idle; busy_d <= dut.u_l2.form.bcp_busy; err_d <= error_flag;
        cerr_d <= core_error_flag; spill_d <= stack_spill;
    end

    // ---- the audio side: strobe toggles, and the I2S wire decoded -------------------------
    always @(dut.u_i2s.strobe_tgl) if (!arst) $fwrite(fout, "I %0.3f\n", $realtime);   // the toggle itself
    // a receiver: LRCLK and SDATA sampled on SCLK rising edges (C4-D8); a new frame
    // is the first rising edge with LRCLK low after one with LRCLK high (slot 0)
    real    t_f = 0.0, t_frame = 0.0;                     // LRCLK falling edge (ns)
    integer c_f = 0, c_frame = 0;                         // clk_sys cycle then
    always @(negedge i2s_lrclk) if (!arst) begin t_f = $realtime; c_f = cyc; end
    integer slot = -1;  reg [23:0] wl = 0, wr = 0;  reg lr_prev = 1;  reg framed = 0;
    reg [23:0] cap_l = 0, cap_r = 0;                      // what the master captured at this frame's F
    always @(posedge i2s_sclk) if (!arst) begin
        if (i2s_lrclk == 1'b0 && lr_prev == 1'b1) begin
            if (framed) $fwrite(fout, "J %0.3f %0d %06h %06h %06h %06h\n", t_frame, c_frame, wl, wr, cap_l, cap_r);
            framed = 1;  slot = 0;  t_frame = t_f;  c_frame = c_f;
            cap_l = dut.u_i2s.l_r;  cap_r = dut.u_i2s.r_r;
        end else if (slot >= 0) slot = slot + 1;
        if (slot >= 1 && slot <= 24)  wl[24 - slot] = i2s_sdata;
        if (slot >= 33 && slot <= 56) wr[56 - slot] = i2s_sdata;
        lr_prev = i2s_lrclk;
    end

    // ---- power-up: FPGA memories start at 0 --------------------------------------------------
    task zero_memories; integer b; begin
        for (b = 0; b < 8; b = b + 1) begin
            dut.u_l2.form.st_n[b] = 0; dut.u_l2.form.ib_n[b] = 0;
            dut.u_l2.form.g_store[1].m[b] = 0;  dut.u_l2.form.g_store[2].m[b] = 0;  dut.u_l2.form.g_store[3].m[b] = 0;
            dut.u_l2.form.g_store[4].m[b] = 0;  dut.u_l2.form.g_store[5].m[b] = 0;  dut.u_l2.form.g_store[6].m[b] = 0;
            dut.u_l2.form.g_store[7].m[b] = 0;  dut.u_l2.form.g_store[8].m[b] = 0;  dut.u_l2.form.g_store[9].m[b] = 0;
            dut.u_l2.form.g_store[10].m[b] = 0; dut.u_l2.form.g_store[11].m[b] = 0; dut.u_l2.form.g_store[12].m[b] = 0;
            dut.u_l2.form.g_store[13].m[b] = 0; dut.u_l2.form.g_store[14].m[b] = 0; dut.u_l2.form.g_store[15].m[b] = 0;
            dut.u_l2.form.g_inbox[1].g_bank.m[b] = 0;  dut.u_l2.form.g_inbox[2].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[3].g_bank.m[b] = 0;  dut.u_l2.form.g_inbox[4].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[5].g_bank.m[b] = 0;  dut.u_l2.form.g_inbox[6].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[7].g_bank.m[b] = 0;  dut.u_l2.form.g_inbox[8].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[9].g_bank.m[b] = 0;  dut.u_l2.form.g_inbox[10].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[11].g_bank.m[b] = 0; dut.u_l2.form.g_inbox[12].g_bank.m[b] = 0;
            dut.u_l2.form.g_inbox[15].g_bank.m[b] = 0;
        end
    end endtask

    // L1 pipeline empty: nothing between the face and the accumulator
    wire l1_busy = dut.u_l1.v1 || (|dut.u_l1.v_dly) || dut.u_l1.v18 || dut.u_l1.v19;

    // ---- command interpreter -----------------------------------------------------------------
    integer fin, r, v0, v1, v2, waited, ns;
    reg [8*8-1:0] cmd;
    reg [8*512-1:0] stim_path, out_path;
    reg taken_d = 0;
    initial begin
        if (!$value$plusargs("stim=%s", stim_path)) stim_path = "stim.txt";
        if (!$value$plusargs("out=%s", out_path))   out_path  = "results.txt";
        fin  = $fopen(stim_path, "r");
        fout = $fopen(out_path, "w");
        if (fin == 0) begin $display("wpms_synth_tb: cannot open %0s", stim_path); $finish; end
        zero_memories;
        @(negedge clk);
        while (!$feof(fin)) begin
            r = $fscanf(fin, "%s", cmd);
            if (r != 1) r = $fgetc(fin);
            else case (cmd)
                "R": begin
                        r = $fscanf(fin, "%h", v0);
                        rst = 1; arst = 1; tb_strobe = 0; ibx_we = 0;
                        repeat (v0) @(negedge clk);
                        @(negedge aclk); arst = 0;
                        @(negedge clk); rst = 0;
                     end
                "X": begin
                        r = $fscanf(fin, "%h %h", v0, v1);
                        ibx_we = 1; ibx_addr = v0; ibx_wdata = v1;
                        @(negedge clk); ibx_we = 0;
                     end
                "W": begin
                        waited = 0;
                        @(negedge clk);
                        while ((!seq_idle || l1_busy) && waited < 40000) begin @(negedge clk); waited = waited + 1; end
                        if (waited >= 40000) $fwrite(fout, "T %0d\n", cyc);
                     end
                "N": begin r = $fscanf(fin, "%h", v0); repeat (v0) @(negedge clk); end
                "S": begin tb_strobe = 1; @(negedge clk); tb_strobe = 0; end
                "G": begin
                        r = $fscanf(fin, "%h", v0);
                        for (ns = 0; ns < v0; ns = ns + 1) begin
                            @(negedge clk);
                            waited = 0;
                            while (!strobe && waited < 10000) begin @(negedge clk); waited = waited + 1; end
                            if (waited >= 10000) $fwrite(fout, "T %0d\n", cyc);
                        end
                     end
                "K": begin
                        waited = 0;
                        @(negedge clk);
                        while (!inbox_taken && waited < 10000) begin @(negedge clk); waited = waited + 1; end
                        if (waited >= 10000) $fwrite(fout, "T %0d\n", cyc);
                     end
                "D": begin r = $fscanf(fin, "%h %h", v0, v1); dip_g = v0; g_ctrl = v1; end
                "M": begin r = $fscanf(fin, "%h %h %h", v0, v1, v2); mg_target = v0; mg_rate = v1; soft_m = v2; end
                "E": ;
                default: $display("wpms_synth_tb: unknown command %0s", cmd);
            endcase
        end
        repeat (8) @(negedge clk);
        $fwrite(fout, "Y %0d %0d %0d %0d %0d\n", strobe_interval, strobe_min, strobe_max, sweep_clocks_max, overrun);
        $fclose(fout);
        $display("wpms_synth_tb: done at clock %0d", cyc);
        $finish;
    end
endmodule
