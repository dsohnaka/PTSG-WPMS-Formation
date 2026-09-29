// ============================================================================
//  wpms_l2_top.v — PTSG-WPMS-Formation, L2: Core + Formation + sweep sequencer
//  PTSG-WPMS-Formation — L2 最上位: Core・Formation・スイープ・シーケンサ
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 3. What crosses the Core/Formation border is
//  the master's lanes only (Ch.5 §5.2), as this profile realizes them:
//    1 issue port        Core ext_op_*                 -> Formation
//    2-4 taps            stay_counter (K), loop_counter (I), state_number (SN)
//                        -> Formation; SSS = the sequencer's window label (SD-03)
//    5 value registers   StayVal.p -> Core stay_value (the sequencer, W-F22/W-F28);
//                        JumpVal / LoopVal -> the Core's indirect-read bus
//                        (purpose 00 Jump, 01 Loop), always ready (registered values)
//    6 Condition         the sequencer's lane mux (STROBE / NONEMPTY / MORE)
//    8 error             Formation insert_req -> Core insertion to TRAP_ADDR (SD-06)
//    9 clock, reset
//  (lane 7, CMT, does not exist in this profile.) The Core runs at PRESCALE 1:
//  one tick per clock, one L1 bin per clock. The Core's external stack is not
//  provided (stack_ack 0): the Phase 3 scores never spill; a spill would stall
//  the Core and is exported for the testbench (stack_spill).
//
//  Parameters for the two clock targets (rulings 2026-09-28, 2026-09-29): 100 MHz —
//  NMAX 2048 (sample period 2,083 clocks); 50 MHz — NMAX 1008 (1,041 clocks).
//  TAIL_BASE: the dispatch score's TAIL_0; JumpVal powers up there (see the
//  Formation's RH003), so that an error raised in the first housekeeping window
//  after reset, before its WJV, still reaches the Core's HALT.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 3).
//  002 2026-09-29       Claude Code   Add : parameter TAIL_BASE -> the Formation's JUMPVAL_RESET
//                                          (Phase 4 finding); header: NMAX 1008 at 50 MHz (ruling).
// ============================================================================
`timescale 1ns/1ps

module wpms_l2_top #(
    parameter integer NMAX        = 2048,
    parameter integer N_MIN       = 32,
    parameter integer IMEM_DEPTH  = 1024,
    parameter [11:0]  TRAP_ADDR   = 12'h3FF,         // = the score's .trap
    parameter [11:0]  TAIL_BASE   = 12'h300,         // = the dispatch score's TAIL_0 (JumpVal at power-up)
    parameter         SCORE_HEX   = "wpms_r1d.hex",
    parameter         SCORE_MIF   = "",
    parameter         IMEM_VENDOR = "SIM"            // "M10K" for Quartus
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         strobe_in,                  // synchronized 48 kHz strobe, one clock

    // ---- input switch port (Phase 5; the testbench in Phase 3) ----------------
    input  wire         ibx_we,
    input  wire [7:0]   ibx_addr,
    input  wire [31:0]  ibx_wdata,
    output wire         inbox_taken,

    // ---- the L1 face (one clock after the Core's timeline, see the sequencer) --
    output wire         l1_packet_start,
    output wire         l1_bin_valid,
    output wire [11:0]  l1_k,
    output wire [255:0] l1_bundle,
    output wire         l1_mute,

    // ---- status -------------------------------------------------------------------------
    output wire         error_flag,                 // Formation (sticky until reset)
    output wire [4:0]   error_code,
    output wire [11:0]  error_sn,
    output wire         core_error_flag,            // the Core in S_HALT
    output wire [11:0]  state_number,
    output wire [15:0]  timing_signals,
    output wire [1:0]   seq_phase,
    output wire         seq_idle,
    output wire [27:0]  sweep_a,
    output wire         stack_spill
);

    // ---- Core <-> Formation / sequencer nets ------------------------------------------------
    wire        ext_op_valid, ext_op_ready;
    wire [3:0]  ext_op_subopcode;
    wire [7:0]  ext_op_sub_operand;
    wire [15:0] ext_op_data;
    wire [11:0] stay_counter, stay_value;
    wire [15:0] loop_counter;
    wire        stay_cnt_match, condition;
    wire        insert_req, insert_ack;
    wire [11:0] insert_target;
    wire        indirect_req;
    wire [1:0]  indirect_purpose;
    wire [11:0] jumpval, loopval;
    wire [11:0] indirect_data = (indirect_purpose == 2'b01) ? loopval : jumpval;
    wire        stack_pop_req, loop_cnt_match, prescaler_match;
    wire [40:0] stack_wdata;
    wire [15:0] prescaler_counter, prescaler_output;

    ptsg_core #(
        .IMEM_DEPTH(IMEM_DEPTH), .PRESCALE(1), .IMEM_VENDOR(IMEM_VENDOR),
        .INIT_FILE(SCORE_HEX), .INIT_FILE_MIF(SCORE_MIF)
    ) core (
        .clk(clk), .rst(rst), .condition(condition),
        .state_number(state_number), .timing_signals(timing_signals),
        .ext_op_valid(ext_op_valid), .ext_op_subopcode(ext_op_subopcode),
        .ext_op_sub_operand(ext_op_sub_operand), .ext_op_data(ext_op_data), .ext_op_ready(ext_op_ready),
        .stack_push_req(stack_spill), .stack_pop_req(stack_pop_req),
        .stack_wdata(stack_wdata), .stack_rdata(41'd0), .stack_ack(1'b0),
        .insert_req(insert_req), .insert_target(insert_target), .insert_ack(insert_ack),
        .loop_counter(loop_counter), .loop_cnt_match(loop_cnt_match),
        .stay_counter(stay_counter), .stay_cnt_match(stay_cnt_match),
        .prescaler_counter(prescaler_counter), .prescaler_match(prescaler_match),
        .prescaler_value(16'd0), .prescaler_output(prescaler_output),
        .stay_value(stay_value),
        .indirect_req(indirect_req), .indirect_purpose(indirect_purpose),
        .indirect_data(indirect_data), .indirect_ready(1'b1),
        .error_flag(core_error_flag));

    // ---- sequencer <-> Formation ----------------------------------------------------------------
    wire        seq_pkt, seq_strobe, pf_req;
    wire [2:0]  seq_cur, pf_block;
    wire [3:0]  seq_q;
    wire [11:0] tap_sss;
    wire        bcp_busy;
    wire [31:0] pf_n, pf_ph0, pf_phd1, pf_phd2, pf_lp, pf_ls0, pf_lad1, pf_lad2, pf_rt;

    wpms_formation #(.NMAX(NMAX), .N_MIN(N_MIN), .TRAP_ADDR(TRAP_ADDR), .JUMPVAL_RESET(TAIL_BASE)) form (
        .clk(clk), .rst(rst),
        .ext_op_valid(ext_op_valid), .ext_op_subopcode(ext_op_subopcode),
        .ext_op_sub_operand(ext_op_sub_operand), .ext_op_data(ext_op_data), .ext_op_ready(ext_op_ready),
        .tap_k(stay_counter), .tap_i(loop_counter), .tap_sn(state_number), .tap_sss(tap_sss),
        .seq_pkt(seq_pkt), .seq_cur(seq_cur), .seq_q(seq_q), .seq_strobe(seq_strobe),
        .pf_req(pf_req), .pf_block(pf_block), .pf_n(pf_n),
        .pf_ph0(pf_ph0), .pf_phd1(pf_phd1), .pf_phd2(pf_phd2), .pf_lp(pf_lp), .pf_ls0(pf_ls0),
        .pf_lad1(pf_lad1), .pf_lad2(pf_lad2), .pf_rt(pf_rt),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata),
        .sweep_a(sweep_a), .inbox_taken(inbox_taken), .bcp_busy(bcp_busy),
        .loopval(loopval), .jumpval(jumpval),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .insert_req(insert_req), .insert_target(insert_target), .insert_ack(insert_ack));

    wpms_sequencer seq (
        .clk(clk), .rst(rst),
        .timing_signals(timing_signals), .stay_counter(stay_counter), .state_number(state_number),
        .stay_cnt_match(stay_cnt_match), .condition(condition), .stay_value(stay_value),
        .strobe_in(strobe_in),
        .sweep_a(sweep_a), .inbox_taken(inbox_taken), .error_flag(error_flag),
        .pf_n(pf_n), .pf_bundle({pf_rt, pf_lad2, pf_lad1, pf_ls0, pf_lp, pf_phd2, pf_phd1, pf_ph0}),
        .seq_pkt(seq_pkt), .seq_cur(seq_cur), .seq_q(seq_q), .seq_strobe(seq_strobe),
        .pf_req(pf_req), .pf_block(pf_block), .tap_sss(tap_sss),
        .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid), .l1_k(l1_k),
        .l1_bundle(l1_bundle), .l1_block(), .l1_mute(l1_mute),
        .phase(seq_phase), .idle(seq_idle));

endmodule
