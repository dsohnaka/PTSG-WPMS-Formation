// ============================================================================
//  wpms_formation.v — PTSG-WPMS-Formation, the L2 Formation datapath
//  PTSG-WPMS-Formation — L2 Formation データパス
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  The Formation side of the master's nine-lane border for this profile
//  (Decision Register W v0.7; L2 Formation Register Map v0.3 §2-§4, §7-§9):
//    lane 1   issue port        ext_op_* from PTSG-Core (captured, never stalled: IF-1)
//    lanes 2-4 taps             K = stay_counter, I = loop_counter, SN = state_number,
//                               SSS = tap_sss (see note SSS below)
//    lane 5   value registers   LoopVal, JumpVal (StayVal belongs to the sequencer, W-F28)
//    lane 8   error path        error_flag / error_code, delivered to the Core as an
//                               insertion into a trap word (see note ERRORS below)
//  plus the profile's own equipment: the single block store (W-F24), the inbox and
//  its views, the CUR alias (W-F28), STP (W-F26), BCP (W-F27), SHV/WSH (W-F23),
//  modular ADD/SUB (W-F30) and the error rows E4, E5, E8, EW2-EW6 (W-R13).
//
//  Golden model: 03_Sample_Implementations/tools/pfasm_tools_w.py (Machine).
//  Encoding: hw/tools/decode_map.json -> wpms_decode.vh (generated; do not edit).
//
//  TIMING (per instruction; the model counts one clock each):
//    * The Core presents an issue in the clock its Global executes; its instruction
//      memory is read on the falling edge, so the issue is valid only in the second
//      half of that clock. This Formation therefore REGISTERS the issue (stage I)
//      and executes it in the next clock (stage X), in order, one per clock. Every
//      instruction sees the effects of the one issued before it (IF-2); the taps and
//      the sequencer context are captured with the issue, so K/I/SN/SSS read "as of
//      the reading instruction's execution clock" (F-F10). Latency 2, throughput 1.
//    * BCP completes architecturally in its X clock: copied bits, SWEEP.a, the EW5
//      checks (on the post-copy N) — the next instruction sees the whole copy. The
//      physical copy runs in the background, one block per clock (slot-major store),
//      and store reads forward from the inbox while a slot is still pending; a
//      datapath write to a pending slot cancels its copy. inbox_taken rises at the
//      edge where the last pending slot lands: BCP's own edge if nothing is taken,
//      else one edge per taken block later (plus one per clock the datapath writes
//      the store meanwhile, which pauses the copy).
//
//  STORE ORGANIZATION: slot-major (brief Phase 2, Deliverable 2 §5): sixteen banks,
//  one per slot, each 8 words (one per block). Bank 0 (N) is a register file so
//  the eight N values are read at once (EW5 sums, EW2 prefetch). Inbox likewise;
//  its banks 13 and 14 are not stored (+0xD reads 0, +0xE shows RTOUT[b]).
//
//  ERRORS: the first error halts the datapath (error_flag, error_code, error_sn =
//  SN of the violating instruction). The violating instruction commits nothing:
//  the scene is the state before it. The Core has no error input (SD-06), so the
//  Formation raises insert_req toward TRAP_ADDR; the score places there a word the
//  Core itself halts on (C3-F24), e.g. a foreground Prog End. Reset clears.
//  E1/E2 cannot be seen from the bus (no band on it: SD-01, SD-02).
//
//  SSS: the Core exports no Stay Start State (SD-03); tap_sss is driven by the L2
//  top (Phase 3) with the Formation-latched window label. I is 16 bits (SD-07).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 2;
//                                          W-F1, W-F22..W-F30, W-R12..W-R16; Map v0.3).
// ============================================================================
`timescale 1ns/1ps

module wpms_formation #(
    parameter integer NMAX      = 2048,         // Map v0.3 §9
    parameter integer N_MIN     = 32,           // Map v0.3 §9 (EW2)
    parameter [11:0]  TRAP_ADDR = 12'hFFF       // insertion target on Error HALT (set by the score)
) (
    input  wire         clk,
    input  wire         rst,                    // synchronous, active-high (Core C5-V1/V3)

    // ---- lane 1: the Core's external-operation bus ---------------------------
    input  wire         ext_op_valid,
    input  wire [3:0]   ext_op_subopcode,       // D4-D7  = mode
    input  wire [7:0]   ext_op_sub_operand,     // D8-D15 = {rid, sub-op}
    input  wire [15:0]  ext_op_data,            // D16-D31 = immediate
    output wire         ext_op_ready,           // 1: every issue is accepted in its clock

    // ---- lanes 2-4: taps, captured with each issue ---------------------------
    input  wire [11:0]  tap_k,                  // stay_counter
    input  wire [15:0]  tap_i,                  // loop_counter (16 bits, SD-07)
    input  wire [11:0]  tap_sn,                 // state_number
    input  wire [11:0]  tap_sss,                // Formation-latched window label (SD-03)

    // ---- sweep sequencer context (W-F28) --------------------------------------
    input  wire         seq_pkt,                // 1 = packet window, 0 = housekeeping
    input  wire [2:0]   seq_cur,                // block order[q] behind the CUR alias
    input  wire [3:0]   seq_q,                  // packet index (status view)
    input  wire         seq_strobe,             // latch the take-set (synchronized strobe)

    // ---- prefetch port (sequencer): N and bundle of one block ----------------
    input  wire         pf_req,                 // one clock; N checked here (EW2)
    input  wire [2:0]   pf_block,
    output wire [31:0]  pf_n,
    output wire [31:0]  pf_ph0, pf_phd1, pf_phd2, pf_lp, pf_ls0, pf_lad1, pf_lad2, pf_rt,

    // ---- inbox write port (input switch; customer Ch.5 §5.6.2 module layout) -
    //   0x00-0x7F slot b*16+i · 0x80-0x87 RTOUT[b] · 0x88-0x8F COMMIT[b]
    //   ([16:0] mask, [30] armed for the next strobe) · 0x90 staged sweep word ·
    //   0x91 sweep armed ([30])
    input  wire         ibx_we,
    input  wire [7:0]   ibx_addr,
    input  wire [31:0]  ibx_wdata,

    // ---- state visible outside ------------------------------------------------
    output reg  [27:0]  sweep_a,                // SWEEP.a, the sweep word in effect
    output reg          inbox_taken,            // CR5-I3
    output wire         bcp_busy,               // background copy still running
    output reg  [11:0]  loopval,                // WLV (no Core pin yet: TRACK)
    output reg  [11:0]  jumpval,                // WJV
    output reg          error_flag,
    output reg  [4:0]   error_code,
    output reg  [11:0]  error_sn,
    output reg          insert_req,             // Error HALT toward the Core (C3-F24 via insertion)
    output wire [11:0]  insert_target,
    input  wire         insert_ack
);

`include "wpms_decode.vh"

    assign ext_op_ready  = 1'b1;
    assign insert_target = TRAP_ADDR;

    // ========================================================================
    //  Architectural registers (Map v0.3 §2)
    // ========================================================================
    reg  [31:0] accm, temp;
    reg  [9:0]  adrs;          // 9-bit ADRS + bit 9: reached 0x200 by post-increment (E5 on use)
    reg  [4:0]  shv;

    // ---- take-set and COMMIT view state (Map v0.3 §4, §7) --------------------
    reg  [7:0]  armed;         // written by the switch (COMMIT[b][30])
    reg         sweep_armed;
    reg  [7:0]  take;          // latched at the strobe
    reg         take_sweep;
    reg  [7:0]  copied;        // architectural: set by BCP for every taken block
    reg         sweep_copied;
    reg  [16:0] cm_mask [0:7]; // COMMIT[b] [15:0] slot mask, [16] RT.OUT
    reg  [15:0] rtout   [0:7]; // RTOUT[b], staged RT.OUT (W16)
    reg  [27:0] sweep_staged;

    // ---- background copy (BCP's physical half) --------------------------------
    reg  [15:0] pmask [0:7];   // slot i of block b still to be copied (bit 14 = RT.OUT)
    reg         taken_due;     // BCP done architecturally, its copy still landing

    // ========================================================================
    //  Stage I: register the issue with the taps and the sequencer context
    // ========================================================================
    reg         x_valid;
    reg  [3:0]  x_mode, x_subop, x_rid;
    reg  [15:0] x_imm;
    reg  [11:0] x_k, x_sn, x_sss;
    reg  [15:0] x_i;
    reg         x_pkt;
    reg  [2:0]  x_cur;
    reg  [3:0]  x_q;

    always @(posedge clk) begin
        if (rst) x_valid <= 1'b0;
        else     x_valid <= ext_op_valid;
        x_mode  <= ext_op_subopcode;
        x_subop <= ext_op_sub_operand[3:0];
        x_rid   <= ext_op_sub_operand[7:4];
        x_imm   <= ext_op_data;
        x_k     <= tap_k;   x_i  <= tap_i;
        x_sn    <= tap_sn;  x_sss <= tap_sss;
        x_pkt   <= seq_pkt; x_cur <= seq_cur; x_q <= seq_q;
    end

    wire x_go = x_valid && !error_flag;          // halted: nothing executes

    // ========================================================================
    //  Stage X: decode (table generated from decode_map.json)
    // ========================================================================
    wire [7:0] dec   = wpms_decode(x_mode, x_subop);
    wire       d_row = dec[7];
    wire [2:0] kind  = dec[6:4];
    wire [3:0] op    = dec[3:0];

    reg e4;
    always @* begin
        case (kind)
            K_NONE:  e4 = (x_rid != 4'd0) || (x_imm != 16'd0);
            K_SRC:   e4 = (x_rid > SRC_SSS) || ((x_rid != SRC_IMM) && (x_imm != 16'd0));
            K_DST:   e4 = (x_rid > DST_STORE) || (x_imm != 16'd0);
            K_LIT9:  e4 = (x_rid != 4'd0) || (x_imm[15:9] != 7'd0);
            K_SHIFT: e4 = (x_rid != 4'd0);
            default: e4 = 1'b1;
        endcase
        if (!d_row) e4 = 1'b1;
    end

    wire uses_ppm_src = (kind == K_SRC) && (x_rid == SRC_PPM);
    wire is_store_dst = (op == OP_STA) && (x_rid == DST_STORE);

    // ========================================================================
    //  The 9-bit L2 address space (Map v0.3 §4) at ADRS
    // ========================================================================
    localparam [2:0] R_STORE = 3'd0, R_INBOX = 3'd1, R_CUR = 3'd2, R_COMMIT = 3'd3,
                     R_SWST = 3'd4, R_SWA = 3'd5, R_STAT = 3'd6, R_NONE = 3'd7;
    reg [2:0] region;
    always @* begin
        if      (adrs < 10'h080)  region = R_STORE;
        else if (adrs < 10'h100)  region = R_INBOX;
        else if (adrs < 10'h110)  region = R_CUR;
        else if (adrs < 10'h118)  region = R_COMMIT;
        else if (adrs == 10'h118) region = R_SWST;
        else if (adrs == 10'h119) region = R_SWA;
        else if (adrs == 10'h11A) region = R_STAT;
        else                      region = R_NONE;
    end
    wire [3:0] a_slot  = adrs[3:0];
    wire [2:0] a_block = (region == R_CUR) ? x_cur : adrs[6:4];

    // ========================================================================
    //  Store: sixteen slot banks x 8 blocks (bank 0 = N, a register file)
    // ========================================================================
    reg  [31:0] st_n [0:7];
    wire [31:0] st_rd_a [0:15];              // datapath read, block a_block
    wire [31:0] st_rd_p [0:15];              // prefetch read, block pf_block
    reg  [15:0] st_we;                       // per-bank write enable (this clock)
    reg  [2:0]  st_wa [0:15];
    reg  [31:0] st_wd [0:15];

    genvar gs;
    generate
        for (gs = 1; gs < 16; gs = gs + 1) begin : g_store
            reg [31:0] m [0:7];
            always @(posedge clk) if (st_we[gs]) m[st_wa[gs]] <= st_wd[gs];
            assign st_rd_a[gs] = m[a_block];
            assign st_rd_p[gs] = m[pf_block];
        end
    endgenerate
    always @(posedge clk) if (st_we[0]) st_n[st_wa[0]] <= st_wd[0];
    assign st_rd_a[0] = st_n[a_block];
    assign st_rd_p[0] = st_n[pf_block];

    // ---- inbox: banks 0 (register file), 1..12 and 15 (13, 14 not stored) ---
    reg  [31:0] ib_n [0:7];
    wire [31:0] ib_rd_a [0:15];              // datapath read (view / forwarding), block a_block
    wire [31:0] ib_rd_c [0:15];              // background copy read, block cp_block
    wire [2:0]  cp_block;
    wire        ibx_slot = ibx_we && !ibx_addr[7];
    wire [2:0]  ibx_b = ibx_addr[6:4];
    wire [3:0]  ibx_i = ibx_addr[3:0];
    generate
        for (gs = 1; gs < 16; gs = gs + 1) begin : g_inbox
            if (gs == 13 || gs == 14) begin : g_absent
                assign ib_rd_a[gs] = 32'd0;
                assign ib_rd_c[gs] = 32'd0;
            end else begin : g_bank
                reg [31:0] m [0:7];
                always @(posedge clk) if (ibx_slot && ibx_i == gs) m[ibx_b] <= ibx_wdata;
                assign ib_rd_a[gs] = m[a_block];
                assign ib_rd_c[gs] = m[cp_block];
            end
        end
    endgenerate
    always @(posedge clk) if (ibx_slot && ibx_i == 4'd0) ib_n[ibx_b] <= ibx_wdata;
    assign ib_rd_a[0] = ib_n[a_block];
    assign ib_rd_c[0] = ib_n[cp_block];

    // ---- the value a pending slot will receive, and the forwarded store read -
    wire [31:0] rt_a      = {16'd0, rtout[a_block]};
    wire [31:0] pend_a    = (a_slot == 4'd14) ? rt_a : ib_rd_a[a_slot];
    wire [15:0] pm_a      = pmask[a_block];
    wire [31:0] store_a   = pm_a[a_slot] ? pend_a : st_rd_a[a_slot];   // store as the program sees it

    // ========================================================================
    //  Reads of the L2 space (Map v0.3 §4; model Machine.read)
    // ========================================================================
    reg [31:0] rd_val;
    always @* begin
        case (region)
            R_STORE:  rd_val = store_a;
            R_INBOX:  rd_val = (a_slot == 4'hE) ? rt_a : (a_slot == 4'hD) ? 32'd0 : ib_rd_a[a_slot];
            R_CUR:    rd_val = x_pkt ? store_a : 32'd0;
            R_COMMIT: rd_val = {1'b0, take[adrs[2:0]], copied[adrs[2:0]], 12'd0, cm_mask[adrs[2:0]]};
            R_SWST:   rd_val = {4'd0, sweep_staged};
            R_SWA:    rd_val = {4'd0, sweep_a};
            R_STAT:   rd_val = {23'd0, !x_pkt, sweep_a[3:0], x_q};
            default:  rd_val = 32'd0;
        endcase
    end
    wire rd_e5 = (region == R_NONE);

    // write-window / read-only / range checks for STM and STA @PPM (model Machine.write)
    reg [4:0] wr_err;
    always @* begin
        case (region)
            R_STORE: wr_err = x_pkt ? ERR_EW4 : 5'd0;            // store: HK only
            R_CUR:   wr_err = x_pkt ? 5'd0 : ERR_EW4;            // CUR: packet window only
            R_NONE:  wr_err = ERR_E5;
            default: wr_err = ERR_EW3;                           // inbox, COMMIT, sweep words, status
        endcase
    end

    // ========================================================================
    //  Operand and ALU
    // ========================================================================
    reg [31:0] src;
    always @* begin
        case (x_rid)
            SRC_IMM:  src = {{16{x_imm[15]}}, x_imm};
            SRC_TEMP: src = temp;
            SRC_PPM:  src = rd_val;
            SRC_K:    src = {20'd0, x_k};
            SRC_I:    src = {16'd0, x_i};
            SRC_SN:   src = {20'd0, x_sn};
            SRC_SSS:  src = {20'd0, x_sss};
            default:  src = 32'd0;
        endcase
    end

    wire signed [31:0] s_accm = accm;
    wire signed [31:0] s_temp = temp;
    wire signed [31:0] s_src  = src;
    // MUL / MAC: exact product, arithmetic realignment by SHV, E8 outside signed 32.
    // One multiplier: MUL multiplies by the source, MAC by Temp (then adds the source).
    wire signed [31:0] m_b    = (op == OP_MAC) ? s_temp : s_src;
    wire signed [63:0] prod   = s_accm * m_b;
    wire signed [63:0] mul_r  = prod >>> shv;
    wire signed [64:0] mac_pe = {prod[63], prod};               // sign-extended to 65 bits
    wire signed [64:0] mac_sh = mac_pe >>> shv;                 // arithmetic (signed operand)
    wire signed [64:0] mac_r  = mac_sh + {{33{src[31]}}, src};
    wire mul_ovf = (mul_r[63:31] != {33{mul_r[31]}});
    wire mac_ovf = (mac_r[64:31] != {34{mac_r[31]}});
    // SFT: signed count; >= 0 arithmetic right (never overflows), < 0 left with E8
    wire signed [15:0] sft_n  = x_imm;
    wire        [15:0] sft_m  = -sft_n;                          // left amount when sft_n < 0
    wire signed [31:0] sft_rr = s_accm >>> ((sft_n > 16'sd31) ? 5'd31 : sft_n[4:0]);
    wire signed [63:0] sft_ll = {{32{accm[31]}}, accm} << sft_m[4:0];
    wire sft_left = sft_n[15];
    wire sft_ovf  = sft_left && (accm != 32'd0) &&
                    ((sft_m > 16'd31) || (sft_ll[63:31] != {33{sft_ll[31]}}));
    wire [31:0] sft_r = sft_left ? sft_ll[31:0] : sft_rr;
    // STP: clamp src into [accm - Temp, accm + Temp] (= accm + clamp(src - accm, -T, +T))
    wire signed [32:0] stp_lo = {s_accm[31], s_accm} - {s_temp[31], s_temp};
    wire signed [32:0] stp_hi = {s_accm[31], s_accm} + {s_temp[31], s_temp};
    wire signed [32:0] stp_s  = {s_src[31], s_src};
    wire [31:0] stp_r = (stp_s < stp_lo) ? stp_lo[31:0] : (stp_s > stp_hi) ? stp_hi[31:0] : src;

    // ========================================================================
    //  BCP, architectural half (W-F27; model Machine.bcp)
    // ========================================================================
    wire [7:0] new_list = take & ~copied;                       // taken, not yet copied
    function [15:0] mask_slots;                                 // COMMIT mask -> pending slots
        input [16:0] m;
        begin mask_slots = {m[15], m[16], 1'b0, m[12:0]}; end   // bits 13,14 ignored; 16 -> slot 14
    endfunction
    reg [31:0] n_post [0:7];                                    // N as the program will see it
    integer bn, bc, bp, bs;                                     // one loop variable per always block
    always @* begin : n_after_bcp
        reg [15:0] pe;                                          // pending after this BCP
        for (bn = 0; bn < 8; bn = bn + 1) begin
            pe = pmask[bn] | (new_list[bn] ? mask_slots(cm_mask[bn]) : 16'd0);
            n_post[bn] = pe[0] ? ib_n[bn] : st_n[bn];
        end
    end
    // sum of N over the first P entries of a sweep word; flags an invalid word
    function signed [35:0] sum_n;
        input [27:0] w;
        input [255:0] n_all;                                    // n_post[7..0] packed
        integer k;
        reg [2:0] blk;
        begin
            sum_n = 36'sd0;
            for (k = 0; k < 8; k = k + 1)
                if (k < w[3:0]) begin
                    blk = w[4 + 3*k +: 3];
                    sum_n = sum_n + {{4{n_all[32*blk + 31]}}, n_all[32*blk +: 32]};
                end
        end
    endfunction
    function sweep_invalid;                                     // P > 8, or a block repeated
        input [27:0] w;
        integer k;
        reg [7:0] seen;
        reg [2:0] blk;
        begin
            sweep_invalid = (w[3:0] > 4'd8);
            seen = 8'd0;
            for (k = 0; k < 8; k = k + 1)
                if (k < w[3:0]) begin
                    blk = w[4 + 3*k +: 3];
                    if (seen[blk]) sweep_invalid = 1'b1;
                    seen[blk] = 1'b1;
                end
        end
    endfunction
    wire [255:0] n_all = {n_post[7], n_post[6], n_post[5], n_post[4],
                          n_post[3], n_post[2], n_post[1], n_post[0]};
    wire         do_sweep   = take_sweep && !sweep_copied;
    wire         sw_invalid = sweep_invalid(sweep_staged);
    // One sum unit. The model checks the sweep item (P, repeats, sum N) and then
    // the sweep in effect (sum N, the backstop). With an item, a valid one becomes
    // the sweep in effect, so both sums are the item's; without one, only SWEEP.a
    // is checked. Summing over the one word below raises EW5 in exactly the cases
    // the two checks do (cosim_l2.py hk group; mutant M12).
    wire [27:0]  sweep_new  = do_sweep ? sweep_staged : sweep_a;   // lands only if BCP commits
    wire signed [35:0] chk_sum = sum_n(sweep_new, n_all);
    wire         ew5        = (do_sweep && sw_invalid) || (chk_sum > NMAX);

    // ========================================================================
    //  Error of the instruction in X (the first one only; model order)
    // ========================================================================
    reg [4:0] x_err;
    always @* begin
        x_err = 5'd0;
        if (e4) x_err = ERR_E4;
        else case (op)
            OP_LDA, OP_ADD, OP_SUB:  if (uses_ppm_src && rd_e5) x_err = ERR_E5;
            OP_MUL:  if (uses_ppm_src && rd_e5) x_err = ERR_E5; else if (mul_ovf) x_err = ERR_E8;
            OP_MAC:  if (uses_ppm_src && rd_e5) x_err = ERR_E5; else if (mac_ovf) x_err = ERR_E8;
            OP_SFT:  if (sft_ovf) x_err = ERR_E8;
            OP_LDM:  if (rd_e5) x_err = ERR_E5;
            OP_STM:  x_err = wr_err;
            OP_STA:  if (is_store_dst) x_err = wr_err;
            OP_STP:  if (temp[31]) x_err = ERR_EW6;                      // checked before the read
                     else if (uses_ppm_src && rd_e5) x_err = ERR_E5;
            OP_BCP:  if (x_pkt) x_err = ERR_EW4;
                     else if (ew5) x_err = ERR_EW5;
            default: x_err = 5'd0;
        endcase
    end
    wire x_commit = x_go && (x_err == 5'd0);

    // prefetch: N outside [N_MIN, NMAX] (EW2)
    assign pf_n    = st_n[pf_block];
    wire   pf_ew2  = pf_req && (($signed(pf_n) < N_MIN) || ($signed(pf_n) > NMAX));
    assign pf_ph0  = st_rd_p[6];  assign pf_phd1 = st_rd_p[7];  assign pf_phd2 = st_rd_p[8];
    assign pf_lp   = st_rd_p[2];  assign pf_ls0  = st_rd_p[15]; assign pf_lad1 = st_rd_p[3];
    assign pf_lad2 = st_rd_p[4];  assign pf_rt   = st_rd_p[14];

    // ========================================================================
    //  Store writes: the datapath (STM, STA @PPM) or the background copy
    // ========================================================================
    wire dp_st_we = x_commit && ((op == OP_STM) || is_store_dst) &&
                    ((region == R_STORE) || (region == R_CUR));
    // background copy: lowest pending block; paused while the datapath writes
    reg [2:0] cp_b;
    reg       cp_any;
    always @* begin
        cp_any = 1'b0; cp_b = 3'd0;
        for (bc = 7; bc >= 0; bc = bc - 1)
            if (pmask[bc] != 16'd0) begin cp_any = 1'b1; cp_b = bc[2:0]; end
    end
    assign cp_block = cp_b;
    wire cp_go = cp_any && !dp_st_we;
    wire [15:0] cp_slots = pmask[cp_b];

    integer s;
    always @* begin
        for (s = 0; s < 16; s = s + 1) begin
            st_we[s] = 1'b0; st_wa[s] = a_block; st_wd[s] = accm;
            if (dp_st_we) begin
                st_we[s] = (a_slot == s[3:0]);
            end else if (cp_go) begin
                st_we[s] = cp_slots[s];
                st_wa[s] = cp_b;
                st_wd[s] = (s == 14) ? {16'd0, rtout[cp_b]} : ib_rd_c[s];
            end
        end
    end
    assign bcp_busy = cp_any;

    // pending slots, next clock: the copy clears what it landed, a datapath write
    // to a pending slot cancels its copy (the program's write wins), BCP adds.
    reg [15:0] pm_next [0:7];
    always @* begin : pending_next
        reg [15:0] pn;
        for (bp = 0; bp < 8; bp = bp + 1) begin
            pn = pmask[bp];
            if (cp_go && cp_b == bp[2:0])        pn = 16'd0;
            if (dp_st_we && a_block == bp[2:0])  pn[a_slot] = 1'b0;
            if (x_commit && op == OP_BCP && new_list[bp])
                pn = pn | mask_slots(cm_mask[bp]);
            pm_next[bp] = pn;
        end
    end
    wire pm_idle_next = ~|{pm_next[7], pm_next[6], pm_next[5], pm_next[4],
                           pm_next[3], pm_next[2], pm_next[1], pm_next[0]};
    wire bcp_commit   = x_commit && (op == OP_BCP);

    // ========================================================================
    //  Sequential state
    // ========================================================================
    always @(posedge clk) begin
        if (rst) begin
            accm <= 32'd0; temp <= 32'd0; adrs <= 10'd0; shv <= 5'd0;
            loopval <= 12'd0; jumpval <= 12'd0;
            sweep_a <= 28'd0;                                    // CR5-R1: P = 0
            armed <= 8'd0; sweep_armed <= 1'b0; take <= 8'd0; take_sweep <= 1'b0;
            copied <= 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;
            sweep_staged <= 28'd0;
            for (bs = 0; bs < 8; bs = bs + 1) begin
                pmask[bs] <= 16'd0; cm_mask[bs] <= 17'd0; rtout[bs] <= 16'd0;
            end
            error_flag <= 1'b0; error_code <= 5'd0; error_sn <= 12'd0; insert_req <= 1'b0;
        end else begin
            // ---- the input switch writes the inbox side --------------------
            if (ibx_we && ibx_addr[7]) begin
                if (ibx_addr[6:3] == 4'b0000) rtout[ibx_addr[2:0]] <= ibx_wdata[15:0];
                if (ibx_addr[6:3] == 4'b0001) begin
                    cm_mask[ibx_addr[2:0]] <= ibx_wdata[16:0];
                    armed[ibx_addr[2:0]]   <= ibx_wdata[30];
                end
                if (ibx_addr[6:0] == 7'h10) sweep_staged <= ibx_wdata[27:0];
                if (ibx_addr[6:0] == 7'h11) sweep_armed  <= ibx_wdata[30];
            end

            // ---- background copy, write-after-pending, BCP (pm_next) ----------
            for (bs = 0; bs < 8; bs = bs + 1) pmask[bs] <= pm_next[bs];
            // inbox_taken (CR5-I3) rises at the edge where the last pending slot lands
            // (at BCP's own edge when it leaves nothing to copy)
            if ((taken_due || bcp_commit) && pm_idle_next) begin
                inbox_taken <= 1'b1; taken_due <= 1'b0;
            end else if (bcp_commit) taken_due <= 1'b1;

            // ---- execute ------------------------------------------------------
            if (x_commit) begin
                case (op)
                    OP_LDA: accm <= src;
                    OP_STA: if (x_rid == DST_TEMP) temp <= accm;       // STORE: see dp_st_we
                    OP_ADD: accm <= accm + src;                         // W-F30: wrap
                    OP_SUB: accm <= accm - src;
                    OP_MUL: accm <= mul_r[31:0];
                    OP_MAC: accm <= mac_r[31:0];
                    OP_SWP: begin accm <= temp; temp <= accm; end
                    OP_SFT: accm <= sft_r;
                    OP_SAD: adrs <= {1'b0, x_imm[8:0]};
                    OP_LDM: begin accm <= rd_val; adrs <= adrs + 10'd1; end
                    OP_STM: adrs <= adrs + 10'd1;                       // the write: dp_st_we
                    OP_WLV: loopval <= accm[11:0];
                    OP_WJV: jumpval <= accm[11:0];
                    OP_WSH: shv <= accm[4:0];
                    OP_STP: accm <= stp_r;
                    OP_BCP: begin                        // pending slots: pm_next; inbox_taken above
                        copied       <= copied | new_list;
                        sweep_copied <= sweep_copied | do_sweep;
                        sweep_a      <= sweep_new;
                    end
                    default: ;
                endcase
            end else if (x_go) begin                                      // x_err != 0
                error_flag <= 1'b1; error_code <= x_err; error_sn <= x_sn; insert_req <= 1'b1;
            end
            if (pf_ew2 && !error_flag && !(x_go && x_err != 5'd0)) begin
                error_flag <= 1'b1; error_code <= ERR_EW2; error_sn <= tap_sn; insert_req <= 1'b1;
            end
            if (insert_req && insert_ack) insert_req <= 1'b0;

            // ---- the strobe latches the take-set (sequencer) -----------------
            // Placed after execute: an instruction in X in the strobe's clock was
            // issued before the strobe and completes first (a BCP there is followed
            // by the strobe's clears, as in the model's order). The physical copy of
            // that BCP still lands (pmask); only the flags restart.
            if (seq_strobe) begin
                take <= armed; take_sweep <= sweep_armed;
                copied <= 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    // The input switch must not write a block whose copy is still pending (it is
    // frozen while armed, customer Ch.5 §5.4.2); the sequencer must not prefetch
    // while the copy runs (it prefetches after BCP has landed, Deliverable 3 §6.2).
    always @(posedge clk) if (!rst) begin
        if (ibx_slot && pmask[ibx_b] != 16'd0)
            $display("%t wpms_formation: WARNING inbox write to block %0d while its copy is pending", $time, ibx_b);
        if (ibx_we && ibx_addr[7:3] == 5'b10000 && pmask[ibx_addr[2:0]][14])
            $display("%t wpms_formation: WARNING RTOUT write to block %0d while its copy is pending", $time, ibx_addr[2:0]);
        if (pf_req && cp_any)
            $display("%t wpms_formation: WARNING prefetch while the background copy runs", $time);
    end
`endif

endmodule
