// ============================================================================
//  wpms_sequencer.v — PTSG-WPMS-Formation, the sweep sequencer (W-F28)
//  PTSG-WPMS-Formation — スイープ・シーケンサ
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  Deliverable 3 (choreography) §2-§7, Register Map v0.3 §2, §4, W-F19, W-F22,
//  W-F28. Between the Core (PTSG-Core RH031p) and the Formation datapath
//  (wpms_formation.v), it owns:
//    * the packet index q of the current sweep, cur = order[q], P (from SWEEP.a,
//      which the Formation holds and BCP writes);
//    * the Condition lanes STROBE / NONEMPTY / MORE, selected by TS_CSEL on the
//      timing-signal bus (W-R16);
//    * StayVal.s <- N of the next packet's block at prefetch; StayVal.p <-
//      (TS_PKT ? StayVal.s : 0) at every Stay Set; StayVal.p drives the Core's
//      stay_value pin (W-F22, D3 §5; the Core reads it at the Stay's execute
//      clock, C4-F16);
//    * the bundle prefetch of order[q+1] during packet q, and of the new
//      sweep's first block after housekeeping (once BCP's copy has landed);
//    * the window label (SSS substitute, SD-03) and the L1 face.
//
//  STAY SET, AS SEEN FROM OUTSIDE THE CORE. The Core exports stay_counter (K):
//  it is 0 in a Stay Set's clock and 1 in the next (the Stay Set arms it and, at
//  PRESCALE 1, counts its own tick), and nothing else makes K step from 0 to 1.
//  So "K was 0, K is 1" marks the clock AFTER a Stay Set — the same clock in
//  which the Stay Set's own D16-D31 first appear on timing_signals (a registered
//  bus, SD-11). The sequencer acts in that clock: the first window instruction
//  is being issued in it, and the Formation captures this clock's context.
//
//  THE L1 FACE IS ONE CLOCK LATE, UNIFORMLY (SD-11, resolved this way): with a
//  registered timing-signal bus, TS_PKT in clock c tells whether clock c-1 was a
//  packet bin. So  l1_bin_valid(c) = TS_PKT(c),  l1_k(c) = K(c-1),
//  l1_packet_start(c) = "Stay Set in c-1" and TS_PKT(c). Bin 0 of every packet,
//  its last bin and the housekeeping edge all land where they should; L1 sees
//  the Core's timeline delayed by exactly one clock.
//
//  ERRORS (ruling 2026-09-28): l1_mute = the Formation's error_flag, used at
//  once — bin_valid and packet_start fall in the first clock the flag is high,
//  whatever the Core is still doing (its HALT comes through the insertion, SD-06).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-28       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 3).
// ============================================================================
`timescale 1ns/1ps

module wpms_sequencer (
    input  wire         clk,
    input  wire         rst,

    // ---- the Core --------------------------------------------------------------
    input  wire [15:0]  timing_signals,         // [0] TS_PKT, [2:1] TS_CSEL (decode_map.json)
    input  wire [11:0]  stay_counter,           // K
    input  wire [11:0]  state_number,
    input  wire         stay_cnt_match,         // Stay-timeup (one clock, registered)
    output reg          condition,              // the selected lane
    output wire [11:0]  stay_value,             // StayVal.p

    // ---- the synchronized sample strobe (48 kHz) --------------------------------
    input  wire         strobe_in,              // one clock

    // ---- the Formation --------------------------------------------------------------
    input  wire [27:0]  sweep_a,
    input  wire         inbox_taken,
    input  wire         error_flag,
    input  wire [31:0]  pf_n,
    input  wire [255:0] pf_bundle,              // {rt, lad2, lad1, ls0, lp, phd2, phd1, ph0}
    output wire         seq_pkt,
    output wire [2:0]   seq_cur,
    output wire [3:0]   seq_q,
    output wire         seq_strobe,
    output reg          pf_req,
    output reg  [2:0]   pf_block,
    output wire [11:0]  tap_sss,

    // ---- the L1 face (one clock after the Core's timeline, see above) -----------
    output wire         l1_packet_start,
    output wire         l1_bin_valid,
    output wire [11:0]  l1_k,
    output reg  [255:0] l1_bundle,              // staged: stable at l1_packet_start
    output reg  [2:0]   l1_block,
    output wire         l1_mute,

    // ---- status ------------------------------------------------------------------------
    output reg  [1:0]   phase,                  // 0 idle, 1 wake, 2 packets, 3 housekeeping
    output wire         idle                    // asleep, the next sweep's first bundle staged
);

    localparam [1:0] PH_IDLE = 2'd0, PH_WAKE = 2'd1, PH_PKT = 2'd2, PH_HK = 2'd3;
    localparam [1:0] L_STROBE = 2'd0, L_NONEMPTY = 2'd1, L_MORE = 2'd2;

    // ---- the sweep in effect ---------------------------------------------------------
    wire [3:0] P = sweep_a[3:0];
    function [2:0] order_of;
        input [27:0] w; input [3:0] k;
        begin order_of = w[4 + 3*k[2:0] +: 3]; end
    endfunction

    // ---- the Stay Set, one clock after (see header) ----------------------------------
    reg  [11:0] k_prev, sn_prev;
    wire        det     = (k_prev == 12'd0) && (stay_counter == 12'd1);
    wire        ts_pkt  = timing_signals[0];
    wire [1:0]  csel    = timing_signals[2:1];
    wire        pkt_now = det && ts_pkt;         // a packet Stay Set was executed last clock
    wire        hk_now  = det && !ts_pkt;        // the housekeeping Stay Set

    reg  [3:0]  q_r;                             // packets begun in this sweep
    reg  [3:0]  qplay_r;                         // index of the packet playing
    reg  [2:0]  cur_r;
    reg         pkt_r;
    reg  [11:0] sss_r;
    reg  [11:0] stayval_s, stayval_p;
    reg         pf_next;                         // prefetch order[q_r] next clock
    reg         hk_wait;                         // after housekeeping: prefetch when BCP has landed

    // ---- to the Formation: this clock's context (captured with each issue) -----------
    assign seq_pkt    = pkt_now ? 1'b1 : hk_now ? 1'b0 : pkt_r;
    assign seq_cur    = pkt_now ? order_of(sweep_a, q_r) : cur_r;
    assign seq_q      = pkt_now ? q_r : hk_now ? 4'd0 : (pkt_r ? qplay_r : 4'd0);
    assign seq_strobe = strobe_in;
    assign tap_sss    = det ? sn_prev : sss_r;
    assign stay_value = stayval_p;

    // ---- Condition lanes (W-F19, D3 §4) ---------------------------------------------------
    always @* begin
        case (csel)
            L_STROBE:   condition = strobe_in;
            L_NONEMPTY: condition = (P != 4'd0);
            L_MORE:     condition = (q_r < P);           // q + 1 < P, q = the packet just played
            default:    condition = 1'b0;                // 3: reserved (W-R16)
        endcase
    end

    // ---- L1 face --------------------------------------------------------------------------
    assign l1_mute         = error_flag;
    assign l1_bin_valid    = ts_pkt && !l1_mute;
    assign l1_packet_start = pkt_now && !l1_mute;
    assign l1_k            = k_prev;
    assign idle            = (phase == PH_IDLE) && !hk_wait && !pf_req && !pf_next;

    always @(posedge clk) begin
        if (rst) begin
            k_prev <= 12'd0; sn_prev <= 12'd0;
            q_r <= 4'd0; qplay_r <= 4'd0; cur_r <= 3'd0; pkt_r <= 1'b0; sss_r <= 12'd0;
            stayval_s <= 12'd0; stayval_p <= 12'd0;
            pf_req <= 1'b0; pf_block <= 3'd0; pf_next <= 1'b0; hk_wait <= 1'b0;
            l1_bundle <= 256'd0; l1_block <= 3'd0;
            phase <= PH_IDLE;
        end else begin
            k_prev  <= stay_counter;
            sn_prev <= state_number;
            pf_req  <= 1'b0;

            // ---- a sweep begins at the strobe (the Formation latches the take-set) ----
            if (strobe_in) begin
                q_r <= 4'd0;
                phase <= PH_WAKE;
            end

            // ---- Stay Sets ------------------------------------------------------------------
            if (pkt_now) begin
                pkt_r     <= 1'b1;
                cur_r     <= order_of(sweep_a, q_r);
                qplay_r   <= q_r;
                q_r       <= q_r + 4'd1;
                stayval_p <= stayval_s;                  // N of this packet's block (W-F22)
                sss_r     <= sn_prev;
                pf_next   <= (q_r + 4'd1 < P);           // the next packet's block, after this latch
                phase     <= PH_PKT;
            end
            if (hk_now) begin
                pkt_r     <= 1'b0;
                qplay_r   <= 4'd0;
                stayval_p <= 12'd0;                      // housekeeping: the literal applies
                sss_r     <= sn_prev;
                hk_wait   <= 1'b1;
                phase     <= PH_HK;
            end
            if (phase == PH_HK && stay_cnt_match) phase <= PH_IDLE;

            // ---- prefetch: order[q+1] during packet q; order'[0] once BCP has landed ----
            if (pf_next) begin
                pf_next  <= 1'b0;
                pf_req   <= 1'b1;
                pf_block <= order_of(sweep_a, q_r);      // q_r already counts this packet
            end else if (hk_wait && inbox_taken) begin
                hk_wait  <= 1'b0;
                if (P != 4'd0) begin
                    pf_req   <= 1'b1;
                    pf_block <= order_of(sweep_a, 4'd0);
                end
            end
            if (pf_req) begin                            // the port answers in the request clock
                l1_bundle <= pf_bundle;
                l1_block  <= pf_block;
                stayval_s <= pf_n[11:0];
            end
        end
    end

`ifndef SYNTHESIS
    // The latch must never see a bundle staged for another block (the sweep
    // oracle's stale-bundle check).
    always @(posedge clk) if (!rst && l1_packet_start && l1_block != order_of(sweep_a, q_r))
        $display("%t wpms_sequencer: WARNING bundle staged for block %0d latched for block %0d",
                 $time, l1_block, order_of(sweep_a, q_r));
`endif

endmodule
