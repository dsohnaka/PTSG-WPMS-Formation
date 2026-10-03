// ============================================================================
//  DE10_Nano_wpms_top.v — the WPMS silicon sample on the Terasic DE10-nano
//  DE10-nano 上の WPMS シリコン試作のトップ
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 6. Started from the Core's harness
//  (PTSG-Core/03_Sample_Implementations/board_harnesses/de10_nano/
//  DE10_Nano_ptsg100_top.v: direct altera_pll, reset held until lock, the JTAG
//  domain asynchronous); the pins are the Terasic golden top's names, the
//  locations those of its .qsf. Everything of the sound and its control is
//  hw/switch/wpms_system.v (Phases 2-5); this file adds only what depends on
//  the board:
//
//    clocks   FPGA_CLK1_50 -> PLL clk_sys (SYS_MHZ 50: NMAX 1,008, the ROM's
//             origin N = 1,008; or 100: NMAX 2,048, N = 2,048 — rulings
//             2026-09-28/29; one integer, set by the Quartus revision; its duty
//             cycle SYS_DUTY likewise, 30 % high at 50 MHz: the Core's imem reads on
//             the falling edge, and its word must reach the Core's registers by the
//             next rising edge — 14 ns instead of 10, the address side keeping 6 ns
//             (SD-23)); FPGA_CLK2_50 ->
//             fractional PLL clk_aud = MCLK 12.288 MHz (C4-D2); FPGA_CLK3_50 ->
//             PLL clk_pix 74.25 MHz (720p60, C4-D9) and clk_pix_tx, the same
//             shifted by half a period, forwarded as HDMI_TX_CLK (the ADV7513
//             samples the pixel bus on its edge: 6.7 ns from each data edge,
//             against t_VSU 1.8 ns / t_VHLD 1.3 ns, data sheet Rev. B p. 3).
//             FPGA_CLK1_50 itself runs the ADV7513 configurator.
//    resets   power-on (POR_BITS of FPGA_CLK1_50), PLL lock, SW[2] (DIP[2]
//             holds the design in reset, Ch.5 §5.8) and the JTAG reset bit
//             (ISSP instance BRD, source[0]); each reset is a 2-FF level into
//             its own domain. The video carrier and the configurator do not
//             follow SW[2]: the HDMI link stays up while the sound restarts.
//    I/O      KEY[0] GO_ALL, KEY[1] test origin (Ch.5 §5.8), SW[1:0] G,
//             SW[3] soft mute; HDMI: video carrier, I2C (open drain, 2-FF
//             inputs), I2S (SCLK, LRCLK, data I2S0) and MCLK; LEDs below.
//    taps     tap_ctl and tap_dat: registered copies of the signals the
//             Layer 4 evidence needs, kept (noprune) for SignalTap; layout
//             below, decoded by hw/tools/phase6_evidence.py. One clock late,
//             all alike.
//
//  LED[0] heartbeat: toggles every 24,000 strobes (1 Hz while the sweeps run)
//  LED[1] all three PLLs locked          LED[2] ADV7513 table written (HPD up)
//  LED[3] HPD (a sink is connected)      LED[4] Formation error_flag
//  LED[5] Core halted (C3-F24)           LED[6] packets played in the last 0.5 s
//  LED[7] I2C not acknowledged (sticky)
//
//  tap_ctl (clk_sys, 128 bits)            tap_dat (clk_sys, 304 bits)
//    [0] strobe   [1] packet_start          [255:0]   the L1 bundle (D2 §2)
//    [2] bin_valid  [3] inbox_taken         [279:256] bank L   [303:280] bank R
//    [4] error_flag [5] Core halted
//    [6] seq_idle   [7] bank_we
//    [12:8] error_code   [24:13] K (L1 face)   [36:25] state_number (Core)
//    [39:37] q, the packet's index in its sweep (valid with packet_start)
//    [67:40] SWEEP.a ([43:40] P, [67:44] order)
//    [99:68] n, strobes since reset (the sweep a strobe starts is n after it)
//    [100] packet_start | bank_we: the storage qualifier of the bundle and
//          PCM captures (SignalTap "Input port" qualifier)
//    [127:101] 0
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
//  002 2026-10-03       Claude Code   Add : SYS_DUTY, clk_sys's duty cycle (SD-23; SD-22 step 2's third fit).
// ============================================================================
`timescale 1ns/1ps

module DE10_Nano_wpms_top #(
    parameter integer SYS_MHZ          = 50,                     // 50 | 100 (the Quartus revision sets it)
    parameter integer SYS_DUTY         = 50,                     // clk_sys time high, % (the revision sets it)
    parameter         VENDOR           = "INTEL",                // "INTEL" | "SIM" (the board-level bench)
    parameter         SCORE_HEX        = "wpms_r1d.hex",
    parameter         SCORE_MIF        = "wpms_r1d.mif",
    parameter         EXP2_HEX         = "wpms_exp2_table.hex",
    parameter         ROM_HEX          = "wpms_rom_origin_1008.hex",   // the bench's ($readmemh)
    parameter integer CFG_POWERUP_CLKS = 10_000_000,             // 200 ms of FPGA_CLK1_50
    parameter integer CFG_POLL_CLKS    = 5_000_000,              // 100 ms
    parameter integer CFG_I2C_HZ       = 100_000,                // SCL rate (the bench runs it faster)
    parameter integer KEY_DEBOUNCE     = 0,                      // clk_sys clocks; 0 = 10 ms
    parameter integer POR_BITS         = 16,                     // 1.3 ms of FPGA_CLK1_50
    parameter integer HEARTBEAT        = 24_000,                 // strobes per LED[0] toggle
    parameter integer SIM_SYS_HALF_PS  = 10_000                  // the bench's clk_sys (SIM only)
) (
    input  wire        FPGA_CLK1_50,
    input  wire        FPGA_CLK2_50,
    input  wire        FPGA_CLK3_50,
    input  wire [1:0]  KEY,
    input  wire [3:0]  SW,
    output wire [7:0]  LED,
    inout  wire        HDMI_I2C_SCL,
    inout  wire        HDMI_I2C_SDA,
    inout  wire        HDMI_I2S,
    inout  wire        HDMI_LRCLK,
    inout  wire        HDMI_MCLK,
    inout  wire        HDMI_SCLK,
    output wire        HDMI_TX_CLK,
    output wire [23:0] HDMI_TX_D,
    output wire        HDMI_TX_DE,
    output wire        HDMI_TX_HS,
    input  wire        HDMI_TX_INT,
    output wire        HDMI_TX_VS
);
    localparam integer NMAX   = (SYS_MHZ >= 100) ? 2048 : 1008;
    // strings of equal length, so the conditional never pads one with NUL characters
    localparam         SYS_FREQ = (SYS_MHZ >= 100) ? "100.000000 MHz" : "50.0000000 MHz";
    localparam         ROM_MIF  = (SYS_MHZ >= 100) ? "wpms_rom_origin_2048.mif" : "wpms_rom_origin_1008.mif";
    localparam integer KDB    = (KEY_DEBOUNCE > 0) ? KEY_DEBOUNCE : SYS_MHZ * 10_000;
    localparam         MEM_V  = (VENDOR == "SIM") ? "SIM" : "M10K";
    localparam         ISSP_V = (VENDOR == "SIM") ? "SIM" : "INTEL";

    // ---- clocks ------------------------------------------------------------------------------
    wire clk_sys, clk_aud, clk_pix, clk_pix_tx;
    wire lk_sys, lk_aud, lk_pix;
    wpms_pll #(.VENDOR(VENDOR), .FRACTIONAL("false"), .NCLK(1), .OUT0(SYS_FREQ), .DUTY0(SYS_DUTY),
               .SIM_HALF0_PS(SIM_SYS_HALF_PS), .SIM_LOCK_NS(2000)) u_pll_sys (
        .refclk(FPGA_CLK1_50), .rst(1'b0), .outclk0(clk_sys), .outclk1(), .locked(lk_sys));
    wpms_pll #(.VENDOR(VENDOR), .FRACTIONAL("true"), .NCLK(1), .OUT0("12.288000 MHz"),
               .SIM_HALF0_PS(40690), .SIM_LOCK_NS(3000)) u_pll_aud (
        .refclk(FPGA_CLK2_50), .rst(1'b0), .outclk0(clk_aud), .outclk1(), .locked(lk_aud));
    // 74.25 MHz = 50 MHz x 297/200: an integer ratio needs M = 297, N = 10 (the detector at 5 MHz,
    // its minimum) and a 1,485 MHz VCO, at the edge of the device's ranges; a fractional VCO
    // (742.5 MHz, C = 10) avoids the corner. The half-period shift is 40 VCO eighths: 6,734 ps.
    wpms_pll #(.VENDOR(VENDOR), .FRACTIONAL("true"), .NCLK(2),
               .OUT0("74.250000 MHz"), .PHASE0("0 ps"), .OUT1("74.250000 MHz"), .PHASE1("6734 ps"),
               .SIM_HALF0_PS(6734), .SIM_SHIFT1_PS(6734), .SIM_LOCK_NS(4000)) u_pll_pix (
        .refclk(FPGA_CLK3_50), .rst(1'b0), .outclk0(clk_pix), .outclk1(clk_pix_tx), .locked(lk_pix));

    // ---- resets --------------------------------------------------------------------------------
    reg  [POR_BITS-1:0] por_cnt = {POR_BITS{1'b0}};
    wire por = ~&por_cnt;
    always @(posedge FPGA_CLK1_50) if (por) por_cnt <= por_cnt + 1'b1;

    wire jtag_rst;                                          // ISSP BRD source[0]
    wire rq_sys = por | ~lk_sys | ~lk_aud | SW[2] | jtag_rst;
    wire rq_aud = por | ~lk_aud | SW[2] | jtag_rst;
    wire rq_pix = por | ~lk_pix;
    reg  [1:0] rs_sys = 2'b11, rs_aud = 2'b11, rs_pix = 2'b11;
    always @(posedge clk_sys) rs_sys <= {rs_sys[0], rq_sys};
    always @(posedge clk_aud) rs_aud <= {rs_aud[0], rq_aud};
    always @(posedge clk_pix) rs_pix <= {rs_pix[0], rq_pix};
    wire rst_sys = rs_sys[1];
    wire rst_aud = rs_aud[1];
    wire rst_pix = rs_pix[1];

    // ---- the system (Phases 2-5) -------------------------------------------------------------
    wire [47:0]  host_ext = 48'd0;                          // the deterministic controller's port: 0 on the board
    wire         i2s_sclk, i2s_lrclk, i2s_sdata;
    wire         strobe, bank_we, error_flag, core_error_flag, inbox_taken;
    wire         packet_start, bin_valid, seq_idle;
    wire signed [23:0] bank_l, bank_r;
    wire [27:0]  sweep_a;
    wire [11:0]  l1_k, state_number;
    wire [255:0] l1_bundle;
    wire [4:0]   error_code;
    wpms_system #(
        .NMAX(NMAX), .N_MIN(32), .IMEM_DEPTH(1024), .TRAP_ADDR(12'h3FF),
        .SCORE_HEX(SCORE_HEX), .SCORE_MIF(SCORE_MIF), .IMEM_VENDOR(MEM_V), .EXP2_HEX(EXP2_HEX),
        .ROM_HEX(ROM_HEX), .ROM_MIF(ROM_MIF), .ROM_VENDOR(MEM_V), .ISSP_VENDOR(ISSP_V),
        .KEY_DEBOUNCE(KDB), .HOST_SETTLE(4)
    ) u_sys (
        .clk_sys(clk_sys), .rst_sys(rst_sys), .clk_aud(clk_aud), .rst_aud(rst_aud),
        .key_n(KEY), .dip(SW),
        .i2s_sclk(i2s_sclk), .i2s_lrclk(i2s_lrclk), .i2s_sdata(i2s_sdata),
        .host_src_ext(host_ext), .host_prb(),
        .strobe(strobe), .bank_we(bank_we), .bank_l(bank_l), .bank_r(bank_r),
        .error_flag(error_flag), .core_error_flag(core_error_flag), .inbox_taken(inbox_taken),
        .sweep_a(sweep_a), .l1_packet_start(packet_start), .l1_bin_valid(bin_valid),
        .l1_k(l1_k), .l1_bundle(l1_bundle),
        .error_code(error_code), .state_number(state_number), .seq_idle(seq_idle));

    // ---- HDMI: the I2S wire and MCLK (C4-D2, C4-D8) ----------------------------------------------
    assign HDMI_SCLK  = i2s_sclk;
    assign HDMI_LRCLK = i2s_lrclk;
    assign HDMI_I2S   = i2s_sdata;
    assign HDMI_MCLK  = clk_aud;

    // ---- HDMI: the video carrier (Ch.4 §4.7) ---------------------------------------------------------
    wire        v_hs, v_vs, v_de, v_frame;
    wire [23:0] v_rgb;
    wpms_video_720p #(.PATTERN(1)) u_video (
        .clk_pix(clk_pix), .rst(rst_pix), .hs(v_hs), .vs(v_vs), .de(v_de), .rgb(v_rgb), .frame_start(v_frame));
    assign HDMI_TX_D   = v_rgb;
    assign HDMI_TX_DE  = v_de;
    assign HDMI_TX_HS  = v_hs;
    assign HDMI_TX_VS  = v_vs;
    assign HDMI_TX_CLK = clk_pix_tx;

    // ---- HDMI: the ADV7513 configurator on FPGA_CLK1_50 (Ch.4 §4.6.2) ------------------------------
    reg  [1:0] scl_s = 2'b11, sda_s = 2'b11;
    always @(posedge FPGA_CLK1_50) begin
        scl_s <= {scl_s[0], HDMI_I2C_SCL};
        sda_s <= {sda_s[0], HDMI_I2C_SDA};
    end
    wire       scl_oe, sda_oe, adv_hpd, adv_done, adv_nack;
    wire [7:0] adv_tables;
    wpms_adv7513_cfg #(.CLK_HZ(50_000_000), .I2C_HZ(CFG_I2C_HZ), .POWERUP_CLKS(CFG_POWERUP_CLKS),
                       .POLL_CLKS(CFG_POLL_CLKS)) u_cfg (
        .clk(FPGA_CLK1_50), .rst(por), .scl_oe(scl_oe), .sda_oe(sda_oe),
        .scl_in(scl_s[1]), .sda_in(sda_s[1]),
        .hpd(adv_hpd), .done(adv_done), .nack(adv_nack), .tables(adv_tables));
    assign HDMI_I2C_SCL = scl_oe ? 1'b0 : 1'bz;
    assign HDMI_I2C_SDA = sda_oe ? 1'b0 : 1'bz;

    // ---- LEDs ------------------------------------------------------------------------------------------
    localparam integer HBW = (HEARTBEAT < 2) ? 1 : $clog2(HEARTBEAT);
    reg [HBW-1:0] hb_cnt;
    reg           hb, act_seen, act_led;
    always @(posedge clk_sys) begin
        if (rst_sys) begin
            hb_cnt <= {HBW{1'b0}};  hb <= 1'b0;  act_seen <= 1'b0;  act_led <= 1'b0;
        end else begin
            if (packet_start) act_seen <= 1'b1;
            if (strobe) begin
                if (hb_cnt == HEARTBEAT - 1) begin
                    hb_cnt   <= {HBW{1'b0}};
                    hb       <= ~hb;
                    act_led  <= act_seen | packet_start;
                    act_seen <= 1'b0;
                end else
                    hb_cnt <= hb_cnt + 1'b1;
            end
        end
    end
    assign LED = {adv_nack, act_led, core_error_flag, error_flag, adv_hpd, adv_done,
                  lk_sys & lk_aud & lk_pix, hb};

    // ---- board status and the JTAG reset (ISSP instance BRD) ------------------------------------------
    wire [20:0] brd_probe = {adv_tables, adv_nack, adv_hpd, adv_done, HDMI_TX_INT,
                             lk_pix, lk_aud, lk_sys, SW, KEY};
    wpms_issp #(.VENDOR(ISSP_V), .INSTANCE_ID("BRD"), .SW(1), .PW(21)) u_issp_brd (
        .probe(brd_probe), .source(jtag_rst));

    // ---- the Layer 4 taps (SignalTap; hw/tools/phase6_evidence.py) ------------------------------------
    reg [31:0] tap_n;
    reg [2:0]  tap_q;
    always @(posedge clk_sys) begin
        if (rst_sys) begin
            tap_n <= 32'd0;  tap_q <= 3'd0;
        end else if (strobe) begin
            tap_n <= tap_n + 1'b1;  tap_q <= 3'd0;
        end else if (packet_start)
            tap_q <= tap_q + 1'b1;
    end
    (* noprune *) reg [127:0] tap_ctl;
    (* noprune *) reg [303:0] tap_dat;
    always @(posedge clk_sys) begin
        tap_ctl <= {27'd0, packet_start | bank_we, tap_n, sweep_a, tap_q, state_number, l1_k, error_code,
                    bank_we, seq_idle, core_error_flag, error_flag, inbox_taken,
                    bin_valid, packet_start, strobe};
        tap_dat <= {bank_r, bank_l, l1_bundle};
    end
endmodule
