// ============================================================================
//  wpms_synth_top.v — one WPMS module end to end: L2 + L1 + output path
//  WPMS 1 モジュールの端から端まで: L2・L1・出力路
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 4. The pieces, in signal order:
//    wpms_i2s_master   (clk_aud) the I2S frame, the L3 strobe toggle at F_m - 1 SCLK
//    wpms_strobe_sync  (clk_sys) the strobe, one clock per frame; its interval
//    wpms_l2_top       Core RH031p + Formation + sequencer, woken by the strobe
//                      (Phase 3; its L1 face is one clock after the Core, SD-11)
//    wpms_l1_module    bundle latch, difference engines, sin, exp2, product,
//                      accumulators closed on the strobe
//    wpms_output_stage MG, G, rounding, saturation, clip, the output bank
//    back to wpms_i2s_master, which captures the bank at F_{m+1}.
//  One module (M = 1). The Compact configuration's second module (CR3-M1) and
//  the input switch (Ch.5) are later work; the switch port of wpms_l2_top and
//  the control registers of Ch.5 §5.6.1 are ports here (Phase 5 drives them).
//  The video carrier and the ADV7513 configurator (Ch.4 §4.2) are separate
//  modules for the board top (Phase 6): nothing of the sound passes them.
//
//  Clock targets (rulings 2026-09-28, 2026-09-29): 50 MHz, NMAX = 1008
//  (T_min 1,041); the 100 MHz budget (NMAX 2048, T_min 2,083) is the same RTL
//  with NMAX = 2048.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_synth_top #(
    parameter integer NMAX        = 1008,
    parameter integer N_MIN       = 32,
    parameter integer IMEM_DEPTH  = 1024,
    parameter [11:0]  TRAP_ADDR   = 12'h3FF,
    parameter         SCORE_HEX   = "wpms_r1d.hex",
    parameter         SCORE_MIF   = "",
    parameter         IMEM_VENDOR = "SIM",
    parameter         EXP2_HEX    = "wpms_exp2_table.hex"
) (
    input  wire         clk_sys,
    input  wire         rst_sys,
    input  wire         clk_aud,                // MCLK, 12.288 MHz
    input  wire         rst_aud,

    // ---- input switch port (Phase 5; the testbench here) ----------------------------------
    input  wire         ibx_we,
    input  wire [7:0]   ibx_addr,
    input  wire [31:0]  ibx_wdata,
    output wire         inbox_taken,

    // ---- controls (Ch.5 §5.6.1; DIP of Ch.5 §5.8) --------------------------------------------
    input  wire [1:0]   dip_g,
    input  wire [4:0]   g_ctrl,
    input  wire         soft_mute,
    input  wire signed [31:0] mg_target,
    input  wire [31:0]  mg_rate,
    input  wire [1:0]   clip_clear,
    input  wire         minmax_clear,
    input  wire [11:0]  insp_pos,

    // ---- I2S to the ADV7513 (the board top forwards MCLK) ---------------------------------
    output wire         i2s_sclk,
    output wire         i2s_lrclk,
    output wire         i2s_sdata,

    // ---- status and Layer 4 taps (Ch.4 §4.9) --------------------------------------------------
    output wire         strobe,
    output wire         frame_start,
    output wire signed [23:0] bank_l,
    output wire signed [23:0] bank_r,
    output wire         bank_we,
    output wire [1:0]   clip,
    output wire signed [31:0] mg,
    output wire [3:0]   g_eff,
    output wire [11:0]  strobe_interval,
    output wire [11:0]  strobe_min,
    output wire [11:0]  strobe_max,
    output wire [11:0]  sweep_clocks,
    output wire [11:0]  sweep_clocks_max,
    output wire         overrun,
    output wire [31:0]  insp_phase,
    output wire signed [53:0] insp_L,
    output wire [31:0]  insp_a,
    output wire         error_flag,
    output wire [4:0]   error_code,
    output wire [11:0]  error_sn,
    output wire         core_error_flag,
    output wire [11:0]  state_number,
    output wire [27:0]  sweep_a,
    output wire         seq_idle,
    output wire         stack_spill,
    // the L1 face, for the testbench
    output wire         l1_packet_start,
    output wire         l1_bin_valid,
    output wire [11:0]  l1_k,
    output wire [255:0] l1_bundle
);
    wire        strobe_tgl;
    wire        l1_mute;
    wire [15:0] timing_signals;
    wire [1:0]  seq_phase;
    wire signed [74:0] acc_l_closed, acc_r_closed;

    // ---- audio domain: I2S and the strobe's origin -------------------------------------------
    wpms_i2s_master u_i2s (
        .mclk(clk_aud), .rst(rst_aud), .bank_l(bank_l), .bank_r(bank_r),
        .sclk(i2s_sclk), .lrclk(i2s_lrclk), .sdata(i2s_sdata),
        .strobe_tgl(strobe_tgl), .frame_start(frame_start));

    wpms_strobe_sync u_sync (
        .clk(clk_sys), .rst(rst_sys), .strobe_tgl(strobe_tgl), .strobe(strobe),
        .minmax_clear(minmax_clear), .interval(strobe_interval),
        .interval_min(strobe_min), .interval_max(strobe_max));

    // ---- L2 --------------------------------------------------------------------------------------
    wpms_l2_top #(.NMAX(NMAX), .N_MIN(N_MIN), .IMEM_DEPTH(IMEM_DEPTH), .TRAP_ADDR(TRAP_ADDR),
                  .SCORE_HEX(SCORE_HEX), .SCORE_MIF(SCORE_MIF), .IMEM_VENDOR(IMEM_VENDOR)) u_l2 (
        .clk(clk_sys), .rst(rst_sys), .strobe_in(strobe),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata), .inbox_taken(inbox_taken),
        .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid), .l1_k(l1_k),
        .l1_bundle(l1_bundle), .l1_mute(l1_mute),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .core_error_flag(core_error_flag), .state_number(state_number),
        .timing_signals(timing_signals), .seq_phase(seq_phase), .seq_idle(seq_idle),
        .sweep_a(sweep_a), .stack_spill(stack_spill));

    // ---- L1 ----------------------------------------------------------------------------------------
    wpms_l1_module #(.EXP2_HEX(EXP2_HEX)) u_l1 (
        .clk(clk_sys), .rst(rst_sys),
        .packet_start(l1_packet_start), .bin_valid(l1_bin_valid), .k(l1_k), .bundle(l1_bundle),
        .mute(l1_mute), .strobe(strobe), .mg(mg),
        .acc_l_closed(acc_l_closed), .acc_r_closed(acc_r_closed),
        .sweep_clocks(sweep_clocks), .sweep_clocks_max(sweep_clocks_max), .overrun(overrun),
        .insp_pos(insp_pos), .insp_phase(insp_phase), .insp_L(insp_L), .insp_a(insp_a));

    // ---- output stage -------------------------------------------------------------------------
    wpms_output_stage #(.M(1)) u_out (
        .clk(clk_sys), .rst(rst_sys), .strobe(strobe),
        .acc_l_closed(acc_l_closed), .acc_r_closed(acc_r_closed),
        .dip_g(dip_g), .g_ctrl(g_ctrl), .soft_mute(soft_mute), .err_mute(l1_mute),
        .mg_target(mg_target), .mg_rate(mg_rate), .clip_clear(clip_clear),
        .mg(mg), .g_eff(g_eff), .bank_l(bank_l), .bank_r(bank_r), .bank_we(bank_we), .clip(clip));
endmodule
