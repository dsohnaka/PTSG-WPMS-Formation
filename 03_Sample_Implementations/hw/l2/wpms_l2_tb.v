// ============================================================================
//  wpms_l2_tb.v — sweep-level testbench for wpms_l2_top.v (Phase 3)
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  Stands where the input switch (Phase 5) and L1 (Phase 4) will stand. Plays a
//  command file written by hw/tools/cosim_sweep.py and records what L1 would
//  see; cosim_sweep.py compares it with the sweep oracle (sweep_sim.py).
//
//  Commands (numbers in hex):
//    R n            reset for n clocks (the store and inbox power up as 0)
//    X addr data    input-switch write, one clock (Map v0.3 §4 inbox port)
//    W              wait until the sequencer is idle (the sweep has ended and
//                   the next first bundle is staged); timeout 20000 clocks
//    N n            n idle clocks
//    S              the sample strobe, one clock
//    E              end
//  Events written to the results file ("cyc" = clock count since time 0):
//    S cyc                         strobe ("cyc" of every event = the clock count before the
//                                  edge that samples it; written after the same clock's U)
//    L cyc blk w0 .. w7            L1 latch (packet_start): block and bundle
//    P cyc nbins kok               end of a packet on the L1 face: bins seen, K ran 0..n-1
//    A cyc kind sn stay_value      Stay Set seen by the sequencer (kind 1 packet, 0 HK),
//                                  its address, and the stay_value pin in that clock
//    V cyc sn pin                  a Stay executed: state_number, stay_value sampled then
//    D cyc                         the sequencer returned to idle (sweep over)
//    U cyc                         first clock, after the housekeeping timeup, in which
//                                  the Core executes a Branch-0 wait: a strobe there is caught
//    B cyc blocks                  BCP committed (Formation X clock), pending blocks
//    C cyc                         the background copy finished (bcp_busy fell)
//    F cyc code sn                 Formation error_flag rose
//    H cyc sn                      the Core entered S_HALT (core error_flag rose)
//    Q cyc sn                      the Core asked for a stack push (a spill: stalls)
//    M cyc                         L1 face active while muted (must never appear)
//    T cyc                         W timed out
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF Phase 3).
// ============================================================================
`timescale 1ns/1ps
module wpms_l2_tb;
    parameter SCORE = "wpms_r1d.hex";
    parameter integer NMAX = 2048;
    parameter integer N_MIN = 32;

    reg clk = 0, rst = 1;
    always #5 clk = ~clk;
    reg         strobe = 0, ibx_we = 0;
    reg  [7:0]  ibx_addr = 0;
    reg  [31:0] ibx_wdata = 0;
    wire        inbox_taken, l1_packet_start, l1_bin_valid, l1_mute;
    wire [11:0] l1_k, error_sn, state_number;
    wire [255:0] l1_bundle;
    wire        error_flag, core_error_flag, seq_idle, stack_spill;
    wire [4:0]  error_code;
    wire [15:0] timing_signals;
    wire [1:0]  seq_phase;
    wire [27:0] sweep_a;

    wpms_l2_top #(.NMAX(NMAX), .N_MIN(N_MIN), .SCORE_HEX(SCORE)) dut (
        .clk(clk), .rst(rst), .strobe_in(strobe),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata), .inbox_taken(inbox_taken),
        .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid), .l1_k(l1_k),
        .l1_bundle(l1_bundle), .l1_mute(l1_mute),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .core_error_flag(core_error_flag), .state_number(state_number), .timing_signals(timing_signals),
        .seq_phase(seq_phase), .seq_idle(seq_idle), .sweep_a(sweep_a), .stack_spill(stack_spill));

    integer fout, cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    // ---- L1 stand-in: latch, count bins, check K --------------------------------
    integer nbins = 0, kok = 1, in_pkt = 0, k;
    always @(posedge clk) if (!rst) begin
        if (l1_packet_start) begin
            if (in_pkt) $fwrite(fout, "P %0d %0d %0d\n", cyc, nbins, kok);
            $fwrite(fout, "L %0d %0d", cyc, (sweep_a >> (4 + 3 * dut.seq.q_r)) & 7);
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
        if (l1_mute && (l1_bin_valid || l1_packet_start)) $fwrite(fout, "M %0d\n", cyc);
    end

    // ---- Core / sequencer / Formation events -------------------------------------
    reg idle_d = 1, busy_d = 0, err_d = 0, cerr_d = 0, spill_d = 0, hk_end = 0;
    always @(posedge clk) if (!rst) begin
        if (dut.seq.det)
            $fwrite(fout, "A %0d %0d %03h %0d\n", cyc, timing_signals[0], dut.seq.sn_prev, dut.stay_value);
        if (dut.core.fsm == 3'd0 && dut.core.opcode == 4'd1)       // S_RUN, OP_STAY
            $fwrite(fout, "V %0d %03h %0d\n", cyc, state_number, dut.stay_value);
        if (seq_idle && !idle_d) $fwrite(fout, "D %0d\n", cyc);
        // U: the first clock, after the housekeeping timeup, in which the Core executes
        // a Branch-0 wait — the earliest clock a strobe can be caught
        if ((hk_end || (seq_phase == 2'd3 && dut.core.stay_cnt_match)) &&
            dut.core.fsm == 3'd0 && dut.core.opcode == 4'd2 && dut.core.operand == 12'd0) begin
            $fwrite(fout, "U %0d\n", cyc); hk_end <= 1'b0;
        end else if (seq_phase == 2'd3 && dut.core.stay_cnt_match) hk_end <= 1'b1;
        if (strobe) $fwrite(fout, "S %0d\n", cyc);       // after U: a strobe caught in the U clock starts the next sweep
        if (dut.form.bcp_commit) $fwrite(fout, "B %0d %02h\n", cyc, dut.form.new_list);
        if (!dut.form.bcp_busy && busy_d) $fwrite(fout, "C %0d\n", cyc);
        if (error_flag && !err_d) $fwrite(fout, "F %0d %0d %03h\n", cyc, error_code, error_sn);
        if (core_error_flag && !cerr_d) $fwrite(fout, "H %0d %03h\n", cyc, state_number);
        if (stack_spill && !spill_d) $fwrite(fout, "Q %0d %03h\n", cyc, state_number);
        idle_d <= seq_idle; busy_d <= dut.form.bcp_busy; err_d <= error_flag;
        cerr_d <= core_error_flag; spill_d <= stack_spill;
    end

    // ---- power-up: FPGA memories start at 0 --------------------------------------
    task zero_memories; integer b; begin
        for (b = 0; b < 8; b = b + 1) begin
            dut.form.st_n[b] = 0; dut.form.ib_n[b] = 0;
            dut.form.g_store[1].m[b] = 0;  dut.form.g_store[2].m[b] = 0;  dut.form.g_store[3].m[b] = 0;
            dut.form.g_store[4].m[b] = 0;  dut.form.g_store[5].m[b] = 0;  dut.form.g_store[6].m[b] = 0;
            dut.form.g_store[7].m[b] = 0;  dut.form.g_store[8].m[b] = 0;  dut.form.g_store[9].m[b] = 0;
            dut.form.g_store[10].m[b] = 0; dut.form.g_store[11].m[b] = 0; dut.form.g_store[12].m[b] = 0;
            dut.form.g_store[13].m[b] = 0; dut.form.g_store[14].m[b] = 0; dut.form.g_store[15].m[b] = 0;
            dut.form.g_inbox[1].g_bank.m[b] = 0;  dut.form.g_inbox[2].g_bank.m[b] = 0;
            dut.form.g_inbox[3].g_bank.m[b] = 0;  dut.form.g_inbox[4].g_bank.m[b] = 0;
            dut.form.g_inbox[5].g_bank.m[b] = 0;  dut.form.g_inbox[6].g_bank.m[b] = 0;
            dut.form.g_inbox[7].g_bank.m[b] = 0;  dut.form.g_inbox[8].g_bank.m[b] = 0;
            dut.form.g_inbox[9].g_bank.m[b] = 0;  dut.form.g_inbox[10].g_bank.m[b] = 0;
            dut.form.g_inbox[11].g_bank.m[b] = 0; dut.form.g_inbox[12].g_bank.m[b] = 0;
            dut.form.g_inbox[15].g_bank.m[b] = 0;
        end
    end endtask

    // ---- command interpreter ------------------------------------------------------
    integer fin, r, v0, v1, waited;
    reg [8*8-1:0] cmd;
    reg [8*512-1:0] stim_path, out_path;
    initial begin
        if (!$value$plusargs("stim=%s", stim_path)) stim_path = "stim.txt";
        if (!$value$plusargs("out=%s", out_path))   out_path  = "results.txt";
        fin  = $fopen(stim_path, "r");
        fout = $fopen(out_path, "w");
        if (fin == 0) begin $display("wpms_l2_tb: cannot open %0s", stim_path); $finish; end
        zero_memories;
        @(negedge clk);
        while (!$feof(fin)) begin
            r = $fscanf(fin, "%s", cmd);
            if (r != 1) r = $fgetc(fin);
            else case (cmd)
                "R": begin
                        r = $fscanf(fin, "%h", v0);
                        rst = 1; strobe = 0; ibx_we = 0;
                        repeat (v0) @(negedge clk);
                        rst = 0;
                     end
                "X": begin
                        r = $fscanf(fin, "%h %h", v0, v1);
                        ibx_we = 1; ibx_addr = v0; ibx_wdata = v1;
                        @(negedge clk); ibx_we = 0;
                     end
                "W": begin
                        waited = 0;
                        @(negedge clk);
                        while (!seq_idle && waited < 20000) begin @(negedge clk); waited = waited + 1; end
                        if (waited >= 20000) $fwrite(fout, "T %0d\n", cyc);
                     end
                "N": begin r = $fscanf(fin, "%h", v0); repeat (v0) @(negedge clk); end
                "S": begin strobe = 1; @(negedge clk); strobe = 0; end   // logged at the edge (events block)
                "E": ;
                default: $display("wpms_l2_tb: unknown command %0s", cmd);
            endcase
        end
        repeat (4) @(negedge clk);
        $fclose(fout);
        $display("wpms_l2_tb: done at clock %0d", cyc);
        $finish;
    end
endmodule
