// ============================================================================
//  wpms_l1_module.v — WPMS L1, one module's pipeline (customer Ch.3 §3.4-§3.7)
//  WPMS L1 — 1 モジュール分のパイプライン
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  From the L1 face of wpms_l2_top (Deliverable 2: packet_start, bin_valid, K,
//  the eight-word bundle; the face is one clock after the Core, SD-11) to two
//  accumulators closed on the sample strobe. Nothing is stored per bin (C3-D3).
//
//  c0   the bin is on the face. At packet_start the bundle is latched (CR3-B1)
//       and both difference engines start; otherwise they step:
//         phase (Ch.3 §3.4.2, C3-D3/D7, mod 2^32):  out = phi; phi += d; d += c
//         shape (§3.5.4, 54-bit Q.30):  L = lvl + s; s += e; e += c
//           with s0 = LS0<<10, e0 = LAD1<<6, c = LAD2, lvl = (LP<<4) + (MG<<4)
//           (Ch.4 §4.4.1: MG enters as one more term; MG is sampled at
//           packet_start — it changes only on the strobe, before any packet)
//       = the customer's oracle l1_phase() and l1_amplitude(), bin for bin.
//  c1   phase -> wpms_l1_sin (16 clocks), L -> wpms_l1_exp2 (6 clocks) + 10
//       delay stages (delay-matched, Ch.3 §3.6.1)
//  c17  product a x sin: Q1.31 x Q0.40 = Q1.71                     (C3-D8)
//  c18  truncated toward zero to Q1.63 (Ch.2 v1.1 §2.4.2, C2-D11's policy)
//  c19  accumulated: RT.OUT bit 0 -> L, bit 1 -> R, Q12.63 (§3.6.2, CR3-R1)
//  D_L1 (bin on the face -> product in the accumulator) = 19 clocks (§3.6.5
//  target <= 24).
//
//  CLOSING (C3-D9, Ch.4 §4.3.2): in the strobe clock the accumulators, plus a
//  product arriving in that very clock (it can only be the closing sweep's:
//  the new sweep's first bin reaches c19 no earlier than 2 + D_L1 clocks
//  later), are copied to acc_*_closed for the output stage and cleared. Each
//  bin carries a one-bit sample tag taken at c0; a product whose tag is not
//  the current sample's arrived after its sweep was closed: `overrun` (sticky)
//  — the inequality of §3.7 was broken — and it lands in the next sample.
//  sweep_clocks = clocks from the strobe to the last accumulated product of
//  the sweep just closed (Ch.4 §4.9, Ch.5 +0x98); _max is sticky.
//
//  ERROR (ruling 2026-09-28, SD-06): while `mute` (the Formation's error_flag)
//  is high nothing is accumulated and the accumulators read zero, so the next
//  close is silent; the sequencer already stops bin_valid and packet_start.
//
//  INSPECTOR (Ch.5 §5.6.1 0x040-0x043, Ch.1 §1.8): the phase, log2 amplitude
//  and amplitude of the bin at position insp_pos of the sweep (bins counted
//  from the strobe), captured every sweep.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_l1_module #(
    parameter EXP2_HEX = "wpms_exp2_table.hex"
) (
    input  wire         clk,
    input  wire         rst,

    // ---- the L1 face (wpms_l2_top) ------------------------------------------------------
    input  wire         packet_start,
    input  wire         bin_valid,
    input  wire [11:0]  k,
    input  wire [255:0] bundle,                 // {rt, lad2, lad1, ls0, lp, phd2, phd1, ph0}
    input  wire         mute,                   // the Formation's error_flag

    // ---- the sample strobe and the master gain (output stage) --------------------------
    input  wire         strobe,                 // synchronized, one clock
    input  wire signed [31:0] mg,               // Q6.26, <= 0

    // ---- to the output stage ------------------------------------------------------------------
    output reg  signed [74:0] acc_l_closed,     // Q12.63, valid from the clock after the strobe
    output reg  signed [74:0] acc_r_closed,

    // ---- Layer 4 hooks (Ch.4 §4.9) ----------------------------------------------------------
    output reg  [11:0]  sweep_clocks,
    output reg  [11:0]  sweep_clocks_max,
    output reg          overrun,
    input  wire [11:0]  insp_pos,
    output reg  [31:0]  insp_phase,
    output reg  signed [53:0] insp_L,
    output reg  [31:0]  insp_a
);
    localparam integer D_SIN = 16, D_EXP2 = 6;
    localparam integer D_L1  = 1 + D_SIN + 2;                  // 19: c0 -> c19

    // ======================================================================
    //  c0: bundle latch and difference engines
    // ======================================================================
    wire [31:0]        b_ph0  = bundle[31:0];
    wire [31:0]        b_phd1 = bundle[63:32];
    wire [31:0]        b_phd2 = bundle[95:64];
    wire signed [31:0] b_lp   = bundle[127:96];
    wire signed [31:0] b_ls0  = bundle[159:128];
    wire signed [31:0] b_lad1 = bundle[191:160];
    wire signed [31:0] b_lad2 = bundle[223:192];
    wire [1:0]         b_rt   = bundle[225:224];              // RT.OUT bits 0 (L), 1 (R)

    // shifts are wiring (§3.5.4): all terms aligned to Q.30, sign-extended to 54 bits
    wire signed [53:0] w_s0  = {{12{b_ls0[31]}},  b_ls0,  10'd0};
    wire signed [53:0] w_e0  = {{16{b_lad1[31]}}, b_lad1,  6'd0};
    wire signed [53:0] w_c   = {{22{b_lad2[31]}}, b_lad2};
    wire signed [53:0] w_lvl = {{18{b_lp[31]}}, b_lp, 4'd0} + {{18{mg[31]}}, mg, 4'd0};

    reg  [31:0]        phi, d, pc;                 // the next bin's phase state
    reg  signed [53:0] s, e, cc, lvl;              // the next bin's shape state
    reg  [1:0]         rt;
    reg                tag;                        // sample tag (toggles on the strobe)

    reg                v1;                         // c1: the engines' outputs
    reg  [31:0]        ph1;
    reg  signed [53:0] L1;
    reg  [1:0]         rt1;
    reg  [11:0]        k1;
    reg                tag1;

    always @(posedge clk) begin
        v1 <= bin_valid && !rst;  k1 <= k;  tag1 <= tag;
        if (bin_valid) begin
            if (packet_start) begin
                ph1 <= b_ph0;         phi <= b_ph0 + b_phd1;   d <= b_phd1 + b_phd2;   pc <= b_phd2;
                L1  <= w_lvl + w_s0;  s   <= w_s0 + w_e0;      e <= w_e0 + w_c;        cc <= w_c;
                lvl <= w_lvl;         rt  <= b_rt;             rt1 <= b_rt;
            end else begin
                ph1 <= phi;           phi <= phi + d;          d <= d + pc;
                L1  <= lvl + s;       s   <= s + e;            e <= e + cc;
                rt1 <= rt;
            end
        end
    end

    // ======================================================================
    //  c1 .. c16: sin (16) and exp2 (6) + delay (10)
    // ======================================================================
    wire signed [40:0] sin17;
    wire [31:0]        a7;
    wpms_l1_sin  u_sin  (.clk(clk), .phase(ph1), .sin_out(sin17));
    wpms_l1_exp2 #(.TABLE_HEX(EXP2_HEX)) u_exp2 (.clk(clk), .L(L1), .a(a7));

    reg [31:0] a_dly [0:D_SIN-D_EXP2-1];              // a7 -> a17
    reg [D_SIN-1:0] v_dly, tag_dly;                   // c1 -> c17
    reg [1:0]  rt_dly [0:D_SIN-1];
    integer i;
    always @(posedge clk) begin
        a_dly[0] <= a7;
        for (i = 1; i < D_SIN - D_EXP2; i = i + 1) a_dly[i] <= a_dly[i-1];
        v_dly   <= rst ? {D_SIN{1'b0}} : {v_dly[D_SIN-2:0], v1};
        tag_dly <= {tag_dly[D_SIN-2:0], tag1};
        rt_dly[0] <= rt1;
        for (i = 1; i < D_SIN; i = i + 1) rt_dly[i] <= rt_dly[i-1];
    end
    wire [31:0] a17   = a_dly[D_SIN-D_EXP2-1];
    wire        v17   = v_dly[D_SIN-1];
    wire        tag17 = tag_dly[D_SIN-1];
    wire [1:0]  rt17  = rt_dly[D_SIN-1];

    // ======================================================================
    //  c17: product; c18: to Q1.63 toward zero; c19: accumulate
    // ======================================================================
    reg  signed [73:0] prod18;                          // Q1.71 (a >= 0 as a 33-bit signed)
    reg                v18, tag18;  reg [1:0] rt18;
    reg  signed [63:0] p19;                             // Q1.63
    reg                v19, tag19;  reg [1:0] rt19;
    always @(posedge clk) begin
        prod18 <= $signed({1'b0, a17}) * sin17;
        v18 <= v17 && !rst;  tag18 <= tag17;  rt18 <= rt17;
        p19 <= prod18[73] ? -((-prod18) >>> 8) : (prod18 >>> 8);
        v19 <= v18 && !rst;  tag19 <= tag18;  rt19 <= rt18;
    end

    reg  signed [74:0] acc_l, acc_r;                    // Q12.63
    wire signed [74:0] p75   = {{11{p19[63]}}, p19};
    wire               add   = v19 && !mute;
    wire signed [74:0] add_l = (add && rt19[0]) ? p75 : 75'sd0;
    wire signed [74:0] add_r = (add && rt19[1]) ? p75 : 75'sd0;
    reg  [11:0]        cnt, last;                       // clocks since the strobe; last product's
    wire [11:0]        last_now = add ? cnt : last;
    always @(posedge clk) begin
        if (rst) begin
            acc_l <= 0;  acc_r <= 0;  acc_l_closed <= 0;  acc_r_closed <= 0;
            tag <= 1'b0;  cnt <= 12'd0;  last <= 12'd0;
            sweep_clocks <= 12'd0;  sweep_clocks_max <= 12'd0;  overrun <= 1'b0;
        end else begin
            if (strobe) begin                           // close (C3-D9)
                acc_l_closed <= mute ? 75'sd0 : acc_l + add_l;
                acc_r_closed <= mute ? 75'sd0 : acc_r + add_r;
                acc_l <= 75'sd0;  acc_r <= 75'sd0;
                tag   <= ~tag;
                cnt   <= 12'd1;
                sweep_clocks <= last_now;
                if (last_now > sweep_clocks_max) sweep_clocks_max <= last_now;
                last  <= 12'd0;
            end else begin
                acc_l <= mute ? 75'sd0 : acc_l + add_l;
                acc_r <= mute ? 75'sd0 : acc_r + add_r;
                if (cnt != 12'hFFF) cnt <= cnt + 12'd1;
                if (add) last <= cnt;
            end
            if (v19 && tag19 != tag) overrun <= 1'b1;   // a product of a sweep already closed
        end
    end

    // ======================================================================
    //  Inspector: the bin at position insp_pos of the sweep
    // ======================================================================
    reg [11:0] pos1;                                    // bin position of the c1 bin
    reg [11:0] pos0;
    always @(posedge clk) begin
        if (rst || strobe)   pos0 <= 12'd0;
        else if (bin_valid && pos0 != 12'hFFF) pos0 <= pos0 + 12'd1;   // saturates (a sweep has <= NMAX bins)
        pos1 <= pos0;
    end
    reg [31:0] insp_ph_c1;  reg insp_hit_c1;
    reg [D_EXP2-1:0] hit_dly;
    always @(posedge clk) begin
        insp_hit_c1 <= 1'b0;
        if (v1 && pos1 == insp_pos) begin
            insp_phase <= ph1;  insp_L <= L1;  insp_hit_c1 <= 1'b1;
        end
        hit_dly <= {hit_dly[D_EXP2-2:0], insp_hit_c1};
        if (hit_dly[D_EXP2-2]) insp_a <= a7;
    end
endmodule
