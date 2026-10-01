// ============================================================================
//  wpms_system.v — the WPMS synthesizer with its input switch and host path
//  入力スイッチとホスト経路を備えた WPMS シンセサイザー
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 5. Everything of the sound and its control
//  that does not depend on the board: the board top of Phase 6 adds the PLLs,
//  the reset (DIP[2] holds it, Ch.5 §5.8), the pins, the video carrier and the
//  ADV7513 configurator (hw/l1).
//
//    KEY[1:0] -- wpms_key_pulse ----------------------------+
//    ISSP HOST source --+                                   |
//                       OR -- wpms_host_bridge -- port 0 -- wpms_switch -- inbox port -- wpms_synth_top (Phase 4)
//    host_src_ext ------+        (probe: ISSP HOST, host_prb)   port 3: ROM    Ch.4 knobs --^   (L2 + L1 + output + I2S)
//
//  THE OR (architect's ruling of 2026-09-30): the bridge's source is the OR of
//  the ISSP instance HOST and host_src_ext, the port of the deterministic
//  controller used for white-box verification. On the board host_src_ext is 0
//  and the Quartus editor drives HOST; in simulation the ISSP stand-in reads 0
//  and the testbench drives host_src_ext with the same bit protocol
//  (wpms_host_bridge.v). The probe goes to both.
//  ISSP instances (Ch.5 §5.7: "ISSP ... for probes and a few direct knobs"):
//    HOST  source 48, probe 36   the host path (wpms_host_bridge.v)
//    STAT  probe 128             live status (bit layout below)
//    INSP  probe 96              the inspector: {a Q1.31, L Q6.26, phase Q0.32}
//  STAT: [31:0] MG · [43:32] STROBE_INTERVAL · [47:44] G_EFF · [59:48]
//  SWEEP_CLOCKS · [61:60] CLIP · [62] Formation error_flag · [63] Core halted ·
//  [71:64] GO_SEQ[7:0] · [79:72] APPLIED_SEQ[7:0] · [84:80] error_code ·
//  [99:88] SWEEP_CLOCKS_MAX · [108:100] frozen items (blocks 0-7, sweep) ·
//  [109] soft mute in effect · [110] ROM playing · [111] L1 overrun ·
//  [119:112] REJECT[0][7:0] · [127:120] REJECT[3][7:0]. The editor samples
//  these asynchronously; a word that changes while it is sampled may read torn
//  (display only — the HOST path's RDATA is stable when its acknowledge moves).
//  DIP[1:0] = G, DIP[3] = soft mute (OR MUTE), through two flip-flops.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_system #(
    parameter integer NMAX         = 1008,
    parameter integer N_MIN        = 32,
    parameter integer IMEM_DEPTH   = 1024,
    parameter [11:0]  TRAP_ADDR    = 12'h3FF,
    parameter         SCORE_HEX    = "wpms_r1d.hex",
    parameter         SCORE_MIF    = "",
    parameter         IMEM_VENDOR  = "SIM",
    parameter         EXP2_HEX     = "wpms_exp2_table.hex",
    parameter         ROM_HEX      = "wpms_rom_origin_1008.hex",
    parameter         ROM_MIF      = "",
    parameter         ROM_VENDOR   = "SIM",       // "M10K" for Quartus (ISMCE instance TORG)
    parameter         ISSP_VENDOR  = "SIM",       // "INTEL" for Quartus
    parameter integer KEY_DEBOUNCE = 500_000,     // clk_sys clocks (10 ms at 50 MHz)
    parameter integer HOST_SETTLE  = 4
) (
    input  wire         clk_sys,
    input  wire         rst_sys,
    input  wire         clk_aud,                  // MCLK, 12.288 MHz
    input  wire         rst_aud,

    input  wire [1:0]   key_n,                    // KEY[0] GO_ALL, KEY[1] test origin (active low)
    input  wire [3:0]   dip,                      // DIP[1:0] G, DIP[3] soft mute (DIP[2]: reset, at the board top)

    output wire         i2s_sclk,
    output wire         i2s_lrclk,
    output wire         i2s_sdata,

    // ---- the deterministic controller (0 on the board), OR-ed with the ISSP HOST sources ----
    input  wire [47:0]  host_src_ext,
    output wire [35:0]  host_prb,

    // ---- taps (the testbench; SignalTap in Phase 6) -------------------------------------------
    output wire         strobe,
    output wire         bank_we,
    output wire signed [23:0] bank_l,
    output wire signed [23:0] bank_r,
    output wire         error_flag,
    output wire         core_error_flag,
    output wire         inbox_taken,
    output wire [27:0]  sweep_a,
    output wire         l1_packet_start,
    output wire         l1_bin_valid,
    output wire [11:0]  l1_k,
    output wire [255:0] l1_bundle
);
    // ---- board inputs -----------------------------------------------------------------------
    wire key_go_all, key_origin;
    wpms_key_pulse #(.DEBOUNCE(KEY_DEBOUNCE)) u_key0 (.clk(clk_sys), .rst(rst_sys), .key_n(key_n[0]), .press(key_go_all));
    wpms_key_pulse #(.DEBOUNCE(KEY_DEBOUNCE)) u_key1 (.clk(clk_sys), .rst(rst_sys), .key_n(key_n[1]), .press(key_origin));
    reg  [3:0] dip1 = 4'd0, dip2 = 4'd0;
    always @(posedge clk_sys) begin dip1 <= dip; dip2 <= dip1; end

    // ---- the host path: ISSP HOST OR the deterministic controller --------------------------------
    wire [47:0] issp_host_src;
    wire [47:0] host_src = issp_host_src | host_src_ext;
    wire        p0_req, p0_we, p0_done, rej;
    wire [11:0] p0_addr;
    wire [31:0] p0_wdata, rdata;
    wpms_issp #(.VENDOR(ISSP_VENDOR), .INSTANCE_ID("HOST"), .SW(48), .PW(36)) u_issp_host (
        .probe(host_prb), .source(issp_host_src));
    wpms_host_bridge #(.SETTLE(HOST_SETTLE)) u_bridge (
        .clk(clk_sys), .rst(rst_sys), .src(host_src), .prb(host_prb),
        .p0_req(p0_req), .p0_we(p0_we), .p0_addr(p0_addr), .p0_wdata(p0_wdata),
        .p0_done(p0_done), .p0_rdata(rdata), .p0_rej(rej));

    // ---- the switch ------------------------------------------------------------------------------------
    wire        ibx_we;
    wire [7:0]  ibx_addr;
    wire [31:0] ibx_wdata;
    wire signed [31:0] mg_target, mg;
    wire [31:0] mg_rate, insp_phase, insp_a, insp_l_q626;
    wire [31:0] go_seq, applied_seq, applied_sample, reject0, reject3;
    wire [4:0]  g_ctrl, error_code;
    wire        sw_mute, minmax_clear, overrun, rom_busy;
    wire [1:0]  clip_clear, clip;
    wire [3:0]  g_eff;
    wire [11:0] insp_pos, strobe_interval, strobe_min, strobe_max, sweep_clocks, sweep_clocks_max_l1, sweep_clocks_max;
    wire [8:0]  frozen;
    wire signed [53:0] insp_L;
    wpms_switch #(.NMAX(NMAX), .N_MIN(N_MIN), .ROM_HEX(ROM_HEX), .ROM_MIF(ROM_MIF), .ROM_VENDOR(ROM_VENDOR)) u_sw (
        .clk(clk_sys), .rst(rst_sys), .strobe(strobe),
        .p0_req(p0_req), .p0_we(p0_we), .p0_addr(p0_addr), .p0_wdata(p0_wdata),
        .p0_done(p0_done), .rdata(rdata), .rej(rej),
        .key_go_all(key_go_all), .key_origin(key_origin),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata),
        .inbox_taken(inbox_taken), .sweep_a(sweep_a),
        .mg_target(mg_target), .mg_rate(mg_rate), .g_ctrl(g_ctrl), .mute(sw_mute),
        .clip_clear(clip_clear), .minmax_clear(minmax_clear), .insp_pos(insp_pos),
        .mg(mg), .g_eff(g_eff), .clip(clip), .strobe_interval(strobe_interval),
        .strobe_min(strobe_min), .strobe_max(strobe_max), .sweep_clocks(sweep_clocks),
        .insp_phase(insp_phase), .insp_L(insp_L), .insp_a(insp_a),
        .go_seq(go_seq), .applied_seq(applied_seq), .applied_sample(applied_sample),
        .reject0(reject0), .reject3(reject3), .frozen(frozen),
        .sweep_clocks_max(sweep_clocks_max), .rom_busy(rom_busy), .insp_l_q626(insp_l_q626));

    // ---- the synthesizer (Phase 4) ----------------------------------------------------------------
    wire soft_mute = sw_mute | dip2[3];
    wire [11:0] error_sn, state_number;
    wire        frame_start, seq_idle, stack_spill;
    wpms_synth_top #(.NMAX(NMAX), .N_MIN(N_MIN), .IMEM_DEPTH(IMEM_DEPTH), .TRAP_ADDR(TRAP_ADDR),
                     .SCORE_HEX(SCORE_HEX), .SCORE_MIF(SCORE_MIF), .IMEM_VENDOR(IMEM_VENDOR),
                     .EXP2_HEX(EXP2_HEX)) u_synth (
        .clk_sys(clk_sys), .rst_sys(rst_sys), .clk_aud(clk_aud), .rst_aud(rst_aud),
        .ibx_we(ibx_we), .ibx_addr(ibx_addr), .ibx_wdata(ibx_wdata), .inbox_taken(inbox_taken),
        .dip_g(dip2[1:0]), .g_ctrl(g_ctrl), .soft_mute(soft_mute), .mg_target(mg_target),
        .mg_rate(mg_rate), .clip_clear(clip_clear), .minmax_clear(minmax_clear), .insp_pos(insp_pos),
        .i2s_sclk(i2s_sclk), .i2s_lrclk(i2s_lrclk), .i2s_sdata(i2s_sdata),
        .strobe(strobe), .frame_start(frame_start), .bank_l(bank_l), .bank_r(bank_r), .bank_we(bank_we),
        .clip(clip), .mg(mg), .g_eff(g_eff), .strobe_interval(strobe_interval),
        .strobe_min(strobe_min), .strobe_max(strobe_max), .sweep_clocks(sweep_clocks),
        .sweep_clocks_max(sweep_clocks_max_l1), .overrun(overrun),
        .insp_phase(insp_phase), .insp_L(insp_L), .insp_a(insp_a),
        .error_flag(error_flag), .error_code(error_code), .error_sn(error_sn),
        .core_error_flag(core_error_flag), .state_number(state_number), .sweep_a(sweep_a),
        .seq_idle(seq_idle), .stack_spill(stack_spill),
        .l1_packet_start(l1_packet_start), .l1_bin_valid(l1_bin_valid), .l1_k(l1_k), .l1_bundle(l1_bundle));

    // ---- live probes -------------------------------------------------------------------------------
    wire [127:0] stat = {reject3[7:0], reject0[7:0], overrun, rom_busy, soft_mute, frozen,
                         sweep_clocks_max, 3'd0, error_code, applied_seq[7:0], go_seq[7:0],
                         core_error_flag, error_flag, clip, sweep_clocks, g_eff, strobe_interval, mg};
    wire         stat_src, insp_src;                                   // unused source bits
    wpms_issp #(.VENDOR(ISSP_VENDOR), .INSTANCE_ID("STAT"), .SW(1), .PW(128)) u_issp_stat (
        .probe(stat), .source(stat_src));
    wpms_issp #(.VENDOR(ISSP_VENDOR), .INSTANCE_ID("INSP"), .SW(1), .PW(96)) u_issp_insp (
        .probe({insp_a, insp_l_q626, insp_phase}), .source(insp_src));
endmodule
