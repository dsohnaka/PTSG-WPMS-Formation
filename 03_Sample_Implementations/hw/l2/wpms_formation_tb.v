// ============================================================================
//  wpms_formation_tb.v — stimulus-driven testbench for wpms_formation.v
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  Plays a command file written by hw/tools/cosim_l2.py and writes what the
//  hardware did to a results file; cosim_l2.py compares it with the golden
//  model (pfasm_tools_w.Machine). The testbench stands where PTSG-Core stands:
//  it presents one Formation instruction per clock on the external-operation
//  bus (ext_op_valid, mode, {rid, sub-op}, data) exactly as the Core does, and
//  holds the taps and the sequencer context steady while it issues.
//
//  Commands (one per line; numbers in hex):
//    C id                      begin case id
//    R                         reset (2 clocks)
//    Q pkt cur q k i sn sss    sequencer context and taps
//    B addr data               backdoor: store word addr (0..7F = block*16+slot)
//    A accm temp adrs shv swa  backdoor: architectural registers and SWEEP.a
//    X addr data               input-switch write (one clock)
//    S                         synchronized strobe (one clock): latch the take-set
//    I word                    issue one Global word (one clock)
//    N n                       n idle clocks
//    P blk                     prefetch request of block blk (one clock)
//    W                         wait until the background copy has landed
//    K                         acknowledge the insertion request (one clock)
//    V on                      per-clock trace on (1) / off (0)
//    D                         dump the state to the results file
//    E                         end case
//  Results: "D id flag code idx sn accm temp adrs shv swa copied take swcop
//  taken loopval jumpval ireq busy" followed by "M" and the 128 store words;
//  "F id blk n ph0 phd1 phd2 lp ls0 lad1 lad2 rt" for every prefetch (the port's
//  outputs in the request clock). idx = index (0-based, within the case) of the
//  instruction that raised the error, -1 for a prefetch error (EW2) or none.
//  With the trace on, one "T" line per clock: "T id cyc v idx xv xidx xc xerr busy
//  cpgo cpb taken" sampled at the rising edge that closes the clock (v: an issue
//  presented in this clock; xv/xidx: the instruction in stage X; xc: it commits
//  at this edge; cpgo/cpb: the background copy lands block cpb at this edge).
//  Invariant checked every clock: inbox_taken is never high while a copy is still
//  pending (the switch unfreezes the inbox on it, CR5-I3) — "INVARIANT" line.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2 cosimulation).
//  002 2026-10-03       Claude Code   Chg : the backdoor A also sets the Formation's registered
//                                          decode of ADRS (region, a_block: wpms_formation RH005).
// ============================================================================
`timescale 1ns/1ps
module wpms_formation_tb;
    reg clk = 0, rst = 1;
    always #5 clk = ~clk;

    reg         ext_op_valid = 0;
    reg  [3:0]  ext_op_subopcode = 0;
    reg  [7:0]  ext_op_sub_operand = 0;
    reg  [15:0] ext_op_data = 0;
    reg  [11:0] tap_k = 0, tap_sn = 0, tap_sss = 0;
    reg  [15:0] tap_i = 0;
    reg         seq_pkt = 0, seq_strobe = 0, pf_req = 0;
    reg  [2:0]  seq_cur = 0, pf_block = 0;
    reg  [3:0]  seq_q = 0;
    reg         ibx_we = 0;
    reg  [7:0]  ibx_addr = 0;
    reg  [31:0] ibx_wdata = 0;
    wire        ext_op_ready, inbox_taken, bcp_busy, error_flag, insert_req;
    wire [27:0] sweep_a;
    wire [11:0] loopval, jumpval, error_sn, insert_target;
    wire [4:0]  error_code;
    wire [31:0] pf_n, pf_ph0, pf_phd1, pf_phd2, pf_lp, pf_ls0, pf_lad1, pf_lad2, pf_rt;
    reg         insert_ack = 0;

    wpms_formation dut (
        .clk(clk), .rst(rst),
        .ext_op_valid(ext_op_valid), .ext_op_subopcode(ext_op_subopcode),
        .ext_op_sub_operand(ext_op_sub_operand), .ext_op_data(ext_op_data), .ext_op_ready(ext_op_ready),
        .tap_k(tap_k), .tap_i(tap_i), .tap_sn(tap_sn), .tap_sss(tap_sss),
        .seq_pkt(seq_pkt), .seq_cur(seq_cur), .seq_q(seq_q), .seq_strobe(seq_strobe),
        .pf_req(pf_req), .pf_block(pf_block), .pf_n(pf_n),
        .pf_ph0(pf_ph0), .pf_phd1(pf_phd1), .pf_phd2(pf_phd2), .pf_lp(pf_lp), .pf_ls0(pf_ls0),
        .pf_lad1(pf_lad1), .pf_lad2(pf_lad2), .pf_rt(pf_rt),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata),
        .sweep_a(sweep_a), .inbox_taken(inbox_taken), .bcp_busy(bcp_busy),
        .loopval(loopval), .jumpval(jumpval),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .insert_req(insert_req), .insert_target(insert_target), .insert_ack(insert_ack));

    // ---- which issued instruction is in stage X (for the error index) -------
    integer issue_idx = -1;       // index of the instruction presented this clock (-1: none)
    integer n_issued = 0;
    integer x_idx = -1;           // index of the instruction in stage X this clock
    integer err_idx = -1;
    always @(posedge clk) begin
        if (!error_flag && dut.x_go && dut.x_err != 5'd0) err_idx <= x_idx;
        x_idx <= issue_idx;
    end

    // ---- invariant: the switch unfreezes the inbox on inbox_taken (CR5-I3), so
    //      inbox_taken must never be high while a copy is still landing -----------
    always @(posedge clk)
        if (!rst && inbox_taken && bcp_busy)
            $display("%t wpms_formation_tb: INVARIANT inbox_taken high while the copy is pending (case %0h)", $time, case_id);

    // ---- per-clock trace (command V) -----------------------------------------
    integer cyc = 0, trace = 0;
    always @(posedge clk) begin
        if (trace != 0 && !rst)
            $fwrite(fout, "T %0h %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n", case_id, cyc,
                    ext_op_valid, issue_idx, dut.x_valid, x_idx, dut.x_commit, dut.x_err,
                    bcp_busy, dut.cp_go, dut.cp_b, inbox_taken);
        cyc <= cyc + 1;
    end

    // ---- backdoor access to the slot-major store (constant generate indices) -
    task bd_store; input [6:0] a; input [31:0] d; begin
        case (a[3:0])
            4'd0:  dut.st_n[a[6:4]] = d;
            4'd1:  dut.g_store[1].m[a[6:4]] = d;   4'd2:  dut.g_store[2].m[a[6:4]] = d;
            4'd3:  dut.g_store[3].m[a[6:4]] = d;   4'd4:  dut.g_store[4].m[a[6:4]] = d;
            4'd5:  dut.g_store[5].m[a[6:4]] = d;   4'd6:  dut.g_store[6].m[a[6:4]] = d;
            4'd7:  dut.g_store[7].m[a[6:4]] = d;   4'd8:  dut.g_store[8].m[a[6:4]] = d;
            4'd9:  dut.g_store[9].m[a[6:4]] = d;   4'd10: dut.g_store[10].m[a[6:4]] = d;
            4'd11: dut.g_store[11].m[a[6:4]] = d;  4'd12: dut.g_store[12].m[a[6:4]] = d;
            4'd13: dut.g_store[13].m[a[6:4]] = d;  4'd14: dut.g_store[14].m[a[6:4]] = d;
            default: dut.g_store[15].m[a[6:4]] = d;
        endcase
    end endtask
    function [31:0] rd_store; input [6:0] a; begin
        case (a[3:0])
            4'd0:  rd_store = dut.st_n[a[6:4]];
            4'd1:  rd_store = dut.g_store[1].m[a[6:4]];   4'd2:  rd_store = dut.g_store[2].m[a[6:4]];
            4'd3:  rd_store = dut.g_store[3].m[a[6:4]];   4'd4:  rd_store = dut.g_store[4].m[a[6:4]];
            4'd5:  rd_store = dut.g_store[5].m[a[6:4]];   4'd6:  rd_store = dut.g_store[6].m[a[6:4]];
            4'd7:  rd_store = dut.g_store[7].m[a[6:4]];   4'd8:  rd_store = dut.g_store[8].m[a[6:4]];
            4'd9:  rd_store = dut.g_store[9].m[a[6:4]];   4'd10: rd_store = dut.g_store[10].m[a[6:4]];
            4'd11: rd_store = dut.g_store[11].m[a[6:4]];  4'd12: rd_store = dut.g_store[12].m[a[6:4]];
            4'd13: rd_store = dut.g_store[13].m[a[6:4]];  4'd14: rd_store = dut.g_store[14].m[a[6:4]];
            default: rd_store = dut.g_store[15].m[a[6:4]];
        endcase
    end endfunction

    // ---- the command interpreter ----------------------------------------------
    integer fin, fout, r, k, v0, v1, v2, v3, v4, v5, v6, case_id = 0, cases = 0, waited;
    reg [8*8-1:0] cmd;
    reg [8*512-1:0] stim_path, out_path;
    initial begin
        if (!$value$plusargs("stim=%s", stim_path)) stim_path = "stim.txt";
        if (!$value$plusargs("out=%s", out_path))   out_path  = "results.txt";
        fin  = $fopen(stim_path, "r");
        fout = $fopen(out_path, "w");
        if (fin == 0) begin $display("wpms_formation_tb: cannot open %0s", stim_path); $finish; end
        @(negedge clk);
        while (!$feof(fin)) begin
            r = $fscanf(fin, "%s", cmd);
            if (r != 1) begin
                r = $fgetc(fin);                          // skip a stray character
            end else case (cmd)
                "C": begin r = $fscanf(fin, "%h", case_id); n_issued = 0; err_idx = -1; cases = cases + 1; end
                "R": begin
                        rst = 1; ext_op_valid = 0; issue_idx = -1; seq_strobe = 0; pf_req = 0; ibx_we = 0;
                        @(negedge clk); @(negedge clk); rst = 0;
                        err_idx = -1; n_issued = 0;
                     end
                "Q": begin
                        r = $fscanf(fin, "%h %h %h %h %h %h %h", v0, v1, v2, v3, v4, v5, v6);
                        seq_pkt = v0; seq_cur = v1; seq_q = v2; tap_k = v3; tap_i = v4; tap_sn = v5; tap_sss = v6;
                     end
                "B": begin r = $fscanf(fin, "%h %h", v0, v1); bd_store(v0, v1); end
                "A": begin
                        r = $fscanf(fin, "%h %h %h %h %h", v0, v1, v2, v3, v4);
                        dut.accm = v0; dut.temp = v1; dut.adrs = v2; dut.shv = v3; dut.sweep_a = v4;
                        // RH005 registers the decode of ADRS: keep it equal to region_of(adrs)
                        dut.region  = dut.region_of(v2[9:0]);
                        dut.a_block = (dut.region == 3'd2) ? dut.x_cur : v2[6:4];   // 3'd2: R_CUR
                     end
                "X": begin
                        r = $fscanf(fin, "%h %h", v0, v1);
                        ibx_we = 1; ibx_addr = v0; ibx_wdata = v1;
                        @(negedge clk); ibx_we = 0;
                     end
                "S": begin seq_strobe = 1; @(negedge clk); seq_strobe = 0; end
                "I": begin
                        r = $fscanf(fin, "%h", v0);
                        ext_op_valid = 1; ext_op_subopcode = v0[7:4];
                        ext_op_sub_operand = v0[15:8]; ext_op_data = v0[31:16];
                        issue_idx = n_issued; n_issued = n_issued + 1;
                        @(negedge clk);
                        ext_op_valid = 0; issue_idx = -1;
                     end
                "N": begin r = $fscanf(fin, "%h", v0); for (k = 0; k < v0; k = k + 1) @(negedge clk); end
                "P": begin
                        r = $fscanf(fin, "%h", v0);
                        pf_req = 1; pf_block = v0; #1;
                        $fwrite(fout, "F %0h %0d %08h %08h %08h %08h %08h %08h %08h %08h %08h\n", case_id, v0,
                                pf_n, pf_ph0, pf_phd1, pf_phd2, pf_lp, pf_ls0, pf_lad1, pf_lad2, pf_rt);
                        @(negedge clk); pf_req = 0;
                     end
                "W": begin
                        @(negedge clk); @(negedge clk);           // let stage X drain
                        waited = 0;
                        while (bcp_busy && waited < 64) begin @(negedge clk); waited = waited + 1; end
                        @(negedge clk);
                     end
                "K": begin insert_ack = 1; @(negedge clk); insert_ack = 0; end
                "V": begin r = $fscanf(fin, "%h", v0); trace = v0; end
                "D": begin
                        $fwrite(fout, "D %0h %0d %0d %0d %03h %08h %08h %03h %02h %07h %02h %02h %0d %0d %03h %03h %0d %0d\n",
                                case_id, error_flag, error_code, err_idx, error_sn, dut.accm, dut.temp, dut.adrs,
                                dut.shv, sweep_a, dut.copied, dut.take, dut.sweep_copied, inbox_taken,
                                loopval, jumpval, insert_req, bcp_busy);
                        $fwrite(fout, "M");
                        for (k = 0; k < 128; k = k + 1) $fwrite(fout, " %08h", rd_store(k));
                        $fwrite(fout, "\n");
                     end
                "E": ;
                default: begin
                        $display("wpms_formation_tb: unknown command %0s", cmd);
                     end
            endcase
        end
        $fclose(fout);
        $display("wpms_formation_tb: %0d cases played", cases);
        $finish;
    end
endmodule
