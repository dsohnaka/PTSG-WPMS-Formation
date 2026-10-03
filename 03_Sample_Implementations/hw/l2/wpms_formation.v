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
//      The decode of ADRS is registered with it (RH005), and the word at the next ADRS is
//      read one clock ahead (RH006): the X clock starts from the region, the block and
//      the operand already read.
//    * E8 of MUL and MAC is decided in the clock after X (RH006, stage W): Accm is
//      written in X and restored if the result did not fit; the instruction then in X
//      is squashed, so nothing after the violator executes, as before. A prefetch's
//      EW2 met in a MUL's or MAC's X clock waits for that decision (an E8 comes first,
//      as in the model's order). Every error keeps its code and SN; these two are
//      raised one clock later.
//    * BCP completes architecturally in its X clock: copied bits, SWEEP.a, the EW5
//      checks (on the post-copy N; their sum reduced one clock ahead, RH006) — the
//      next instruction sees the whole copy. The
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
//  002 2026-09-28       Claude Code   Fix : insert_req withdrawn while insert_ack is up (found in
//                                          Phase 3 integration: the Core took the insertion twice
//                                          and spilled its holding register at the trap word).
//  003 2026-09-29       Claude Code   Add : parameter JUMPVAL_RESET, the power-up value of JumpVal
//                                          (default 0, the model's). The L2 top sets the dispatch
//                                          score's TAIL_0, so a dispatch reached before the first WJV —
//                                          only after an error in the first housekeeping window —
//                                          lands on a housekeeping tail, whose Stay timeup lets the
//                                          Core take the error insertion (C3-F20) and HALT (found in
//                                          Phase 4: the grid test of the literal test origin at NMAX 1008).
//  004 2026-09-30       Claude Code   Add : inbox port address 0x9F — the nine armed flags written in one
//                                          clock ([7:0] blocks, [8] sweep word). The input switch (Phase 5)
//                                          hands a GO over with it, so a strobe takes all of a GO or none of
//                                          it (customer Ch.5 §5.2). And the take-set latched at the strobe
//                                          includes an arm write presented in the strobe clock itself (0x88-
//                                          0x8F bit 30, 0x91, 0x9F), so a GO handed over in the clock before
//                                          the strobe edge is taken by that strobe: it plays from the second
//                                          strobe after its acceptance at the latest (Ch.5 §5.4.3; found by
//                                          the Phase 5 timing case: 2 periods + 1 clock without it).
//  005 2026-10-03       Claude Code   Chg : timing restructure, behaviour unchanged (SD-22 step 1, ruling
//                                          2026-10-03; the first fit missed 50 MHz by 14.3 ns): (a) each
//                                          register's enable from the errors its own instructions can
//                                          raise, not from one commit of every instruction — the store,
//                                          the background copy, the pending masks and ADRS no longer wait
//                                          for the multiplier's overflow; (b) the address decode (region,
//                                          block) registered with ADRS and x_cur; (c) EW5's sum of N as a
//                                          balanced tree and its repeat check pairwise. Cycle for cycle the
//                                          same: a simulation check compares the split enables with the
//                                          commit they replace in every clock.
//  006 2026-10-03       Claude Code   Chg : timing, SD-22 step 2 (ruling 2026-10-03; the second fit was
//                                          short by 7 ns on MUL/MAC @PPM): (a) the E8 check of MUL and
//                                          MAC moves to the next clock (W): Accm is written in X,
//                                          restored from a one-clock copy on E8, and the instruction
//                                          then in X is squashed; E8 is raised one clock later, and so
//                                          is a prefetch's EW2 met in a MUL's or MAC's X clock (held
//                                          back so that the E8 keeps its priority: every error keeps
//                                          its code and SN). (b) The operand is read one clock ahead:
//                                          the store word (with its pending-slot forwarding) and the
//                                          inbox view at the next ADRS, from the next pending masks and
//                                          the writes of this clock, into registers, the instruction in
//                                          X taken to complete (if it does not, the Formation halts at
//                                          that edge and the value is never read; behaviour unchanged).
//                                          Simulation checks compare the pre-read with the direct read
//                                          in every clock. (c) EW5's sum of N is reduced
//                                          one clock ahead, from the next values, to two words by
//                                          carry-save adders (with the bound as a ninth term); in X one
//                                          add gives its sign. And the idle test of the pending masks
//                                          takes BCP's commit last. Both exact, and checked in
//                                          simulation against the direct computation.
// ============================================================================
`timescale 1ns/1ps

module wpms_formation #(
    parameter integer NMAX      = 2048,         // Map v0.3 §9
    parameter integer N_MIN     = 32,           // Map v0.3 §9 (EW2)
    parameter [11:0]  TRAP_ADDR = 12'hFFF,      // insertion target on Error HALT (set by the score)
    parameter [11:0]  JUMPVAL_RESET = 12'h000   // JumpVal at power-up (Map v0.3 gives none; the model: 0)
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
    //   0x91 sweep armed ([30]) · 0x9F all nine armed flags at once ([7:0] blocks, [8] sweep; RH004)
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
    output wire         insert_req,             // Error HALT toward the Core (C3-F24 via insertion)
    output wire [11:0]  insert_target,
    input  wire         insert_ack
);

`include "wpms_decode.vh"

    assign ext_op_ready  = 1'b1;
    assign insert_target = TRAP_ADDR;
    // The Core takes an insertion in the clock it sees insert_req and answers with a
    // registered insert_ack one clock later; in that clock it looks at insert_req
    // again (its own testbench drops the request as soon as the ack shows). So the
    // request is withdrawn combinationally while the ack is up, else it would be
    // taken twice — the second time at the trap word, spilling the holding register.
    reg  insert_req_r;
    assign insert_req    = insert_req_r && !insert_ack;

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
    function [2:0] region_of;
        input [9:0] a;
        begin
            if      (a < 10'h080)  region_of = R_STORE;
            else if (a < 10'h100)  region_of = R_INBOX;
            else if (a < 10'h110)  region_of = R_CUR;
            else if (a < 10'h118)  region_of = R_COMMIT;
            else if (a == 10'h118) region_of = R_SWST;
            else if (a == 10'h119) region_of = R_SWA;
            else if (a == 10'h11A) region_of = R_STAT;
            else                   region_of = R_NONE;
        end
    endfunction
    // The decode is registered (RH005, SD-22): in every clock region = region_of(adrs)
    // and a_block = (region == R_CUR) ? x_cur : adrs[6:4]. Both are loaded from the
    // values ADRS and x_cur take at the same edge (adrs_nx, seq_cur: see below).
    reg  [2:0] region;
    reg  [2:0] a_block;
    wire [3:0] a_slot  = adrs[3:0];
    wire [9:0] adrs_nx;                                 // ADRS after this clock (below)
    wire [2:0] a_block_nx;                              // the block after this clock (below)
    wire [2:0] a_block_sx;                              // the same, the instruction in X taken to complete
    wire [3:0] s_sx;                                    //   (the operand read ahead, RH006: below)

    // ========================================================================
    //  Store: sixteen slot banks x 8 blocks (bank 0 = N, a register file)
    // ========================================================================
    reg  [31:0] st_n [0:7];
    wire [31:0] st_rd_a [0:15];              // datapath read, block a_block (simulation check only)
    wire [31:0] st_rd_n [0:15];              // pre-read, block a_block_sx (RH006)
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
            assign st_rd_n[gs] = m[a_block_sx];
            assign st_rd_p[gs] = m[pf_block];
        end
    endgenerate
    always @(posedge clk) if (st_we[0]) st_n[st_wa[0]] <= st_wd[0];
    assign st_rd_a[0] = st_n[a_block];
    assign st_rd_n[0] = st_n[a_block_sx];
    assign st_rd_p[0] = st_n[pf_block];

    // ---- inbox: banks 0 (register file), 1..12 and 15 (13, 14 not stored) ---
    reg  [31:0] ib_n [0:7];
    wire [31:0] ib_rd_a [0:15];              // datapath read, block a_block (simulation check only)
    wire [31:0] ib_rd_n [0:15];              // pre-read (view / forwarding), block a_block_sx (RH006)
    wire [31:0] ib_rd_c [0:15];              // background copy read, block cp_block
    wire [2:0]  cp_block;
    wire        ibx_slot = ibx_we && !ibx_addr[7];
    wire [2:0]  ibx_b = ibx_addr[6:4];
    wire [3:0]  ibx_i = ibx_addr[3:0];
    generate
        for (gs = 1; gs < 16; gs = gs + 1) begin : g_inbox
            if (gs == 13 || gs == 14) begin : g_absent
                assign ib_rd_a[gs] = 32'd0;
                assign ib_rd_n[gs] = 32'd0;
                assign ib_rd_c[gs] = 32'd0;
            end else begin : g_bank
                reg [31:0] m [0:7];
                always @(posedge clk) if (ibx_slot && ibx_i == gs) m[ibx_b] <= ibx_wdata;
                assign ib_rd_a[gs] = m[a_block];
                assign ib_rd_n[gs] = m[a_block_sx];
                assign ib_rd_c[gs] = m[cp_block];
            end
        end
    endgenerate
    always @(posedge clk) if (ibx_slot && ibx_i == 4'd0) ib_n[ibx_b] <= ibx_wdata;
    assign ib_rd_a[0] = ib_n[a_block];
    assign ib_rd_n[0] = ib_n[a_block_sx];
    assign ib_rd_c[0] = ib_n[cp_block];

    // ---- the operand, read one clock ahead (RH006): the store as the program sees
    //      it (a pending slot reads what it will receive) and the inbox view, at
    //      ADRS and the block of this clock; loaded below from the next values ----
    reg  [31:0] store_q;                     // = pmask[a_block][a_slot] ? pending value : store word
    reg  [31:0] inbox_q;                     // = the inbox view at (a_block, a_slot)

    // ========================================================================
    //  Reads of the L2 space (Map v0.3 §4; model Machine.read)
    // ========================================================================
    reg [31:0] rd_val;
    always @* begin
        case (region)
            R_STORE:  rd_val = store_q;
            R_INBOX:  rd_val = inbox_q;
            R_CUR:    rd_val = x_pkt ? store_q : 32'd0;
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
    // sum of N over the first P entries of a sweep word, as a balanced tree (RH005,
    // SD-22; the chain it replaces gives the same sum: eight signed 32-bit terms
    // never overflow 36 bits); flags an invalid word
    function signed [35:0] sum_n;
        input [27:0] w;
        input [255:0] n_all;                                    // n_post[7..0] packed
        integer k;
        reg [2:0] blk;
        reg [287:0] t;                                          // the eight terms, 36 bits each
        begin
            for (k = 0; k < 8; k = k + 1) begin
                blk = w[4 + 3*k +: 3];
                t[36*k +: 36] = (k < w[3:0]) ? {{4{n_all[32*blk + 31]}}, n_all[32*blk +: 32]} : 36'd0;
            end
            sum_n = ((t[  0 +: 36] + t[ 36 +: 36]) + (t[ 72 +: 36] + t[108 +: 36]))
                  + ((t[144 +: 36] + t[180 +: 36]) + (t[216 +: 36] + t[252 +: 36]));
        end
    endfunction
    function sweep_invalid;                                     // P > 8, or a block repeated
        input [27:0] w;
        integer k, j;
        begin
            sweep_invalid = (w[3:0] > 4'd8);
            for (k = 1; k < 8; k = k + 1)                       // every pair at once (RH005)
                for (j = 0; j < k; j = j + 1)
                    if (k < w[3:0] && w[4 + 3*j +: 3] == w[4 + 3*k +: 3]) sweep_invalid = 1'b1;
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
    wire signed [35:0] chk_sum = sum_n(sweep_new, n_all);         // the direct sum (simulation check)
    // RH006: the sum minus (NMAX + 1), reduced one clock ahead to two words (ew5_s,
    // ew5_c, loaded below); its sign is the check chk_sum > NMAX.
    localparam [35:0] NEG_NMAX1 = -(NMAX + 1);
    reg  [35:0]  ew5_s, ew5_c;
    wire [35:0]  ew5_d = ew5_s + ew5_c;
    wire         ew5;

    // ========================================================================
    //  Error of the instruction in X (the first one only; model order)
    // ========================================================================
    reg [4:0] x_err;
    always @* begin
        x_err = 5'd0;
        if (e4) x_err = ERR_E4;
        else case (op)
            OP_LDA, OP_ADD, OP_SUB:  if (uses_ppm_src && rd_e5) x_err = ERR_E5;
            OP_MUL:  if (uses_ppm_src && rd_e5) x_err = ERR_E5;          // E8: in W (RH006)
            OP_MAC:  if (uses_ppm_src && rd_e5) x_err = ERR_E5;          // E8: in W (RH006)
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
    // Each register's enable from the errors its own instructions can raise (RH005,
    // SD-22). For every op the enable used equals x_go && x_err == 0, the one commit
    // it replaces (checked in simulation below); split so that the store, the
    // background copy, the pending masks and ADRS do not wait for the multiplier's
    // overflow, which none of the instructions writing them can raise.
    // RH006: the instruction in X is squashed when the error of the clock before is
    // decided only now (w_kill: the MUL/MAC's E8, or an EW2 held back behind it).
    wire w_e8, w_kill;
    wire x_ok0   = x_go && !e4 && !w_kill;
    wire ok_src  = x_ok0 && !(uses_ppm_src && rd_e5);        // LDA ADD SUB MUL MAC (E8: in W)
    wire ok_mem  = x_ok0 && (wr_err == 5'd0);                // STM, STA @PPM
    wire ok_stp  = x_ok0 && !temp[31] && !(uses_ppm_src && rd_e5);
    wire ok_bcp  = x_ok0 && !x_pkt && !ew5;                  // BCP
    wire x_fault = x_go && !w_kill && (x_err != 5'd0);       // error_flag, error_code, the trap

    // ---- stage W (RH006): the E8 check of the MUL or MAC that wrote Accm last clock ----
    reg         w_chk;                       // a MUL or MAC wrote Accm in the last clock
    reg  [33:0] w_hi;                        // its result's bits 64..31 (MUL's sign-extended)
    reg  [31:0] w_bk;                        // Accm before it
    reg  [11:0] w_sn;                        // its SN
    assign w_e8 = w_chk && (w_hi != {34{w_hi[0]}});
    wire mm_spec = ok_src && ((op == OP_MUL) || (op == OP_MAC));

    // prefetch: N outside [N_MIN, NMAX] (EW2)
    assign pf_n    = st_n[pf_block];
    wire   pf_ew2  = pf_req && (($signed(pf_n) < N_MIN) || ($signed(pf_n) > NMAX));
    // RH006: an EW2 met in the X clock of a MUL/MAC waits one clock (pf_w), so that the
    // instruction's own E8, decided in W, keeps its priority (the model's order, as before).
    reg         pf_w;                        // an EW2 held back to W
    reg  [11:0] pf_w_sn;                     // its SN (the tap of that clock)
    assign w_kill = w_e8 || pf_w;
    assign pf_ph0  = st_rd_p[6];  assign pf_phd1 = st_rd_p[7];  assign pf_phd2 = st_rd_p[8];
    assign pf_lp   = st_rd_p[2];  assign pf_ls0  = st_rd_p[15]; assign pf_lad1 = st_rd_p[3];
    assign pf_lad2 = st_rd_p[4];  assign pf_rt   = st_rd_p[14];

    // ========================================================================
    //  Store writes: the datapath (STM, STA @PPM) or the background copy
    // ========================================================================
    wire dp_st_we = ok_mem && ((op == OP_STM) || is_store_dst) &&
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
    wire bcp_commit = ok_bcp && (op == OP_BCP);
    reg [15:0] pm_next [0:7];
    reg [15:0] pm_base [0:7];                                   // pm_next but for BCP's additions
    reg [7:0]  bcp_add;                                         // the blocks BCP adds slots to
    always @* begin : pending_next
        reg [15:0] pn;
        for (bp = 0; bp < 8; bp = bp + 1) begin
            pn = pmask[bp];
            if (cp_go && cp_b == bp[2:0])        pn = 16'd0;
            if (dp_st_we && a_block == bp[2:0])  pn[a_slot] = 1'b0;
            pm_base[bp] = pn;
            bcp_add[bp] = new_list[bp] && (mask_slots(cm_mask[bp]) != 16'd0);
            if (bcp_commit && new_list[bp])
                pn = pn | mask_slots(cm_mask[bp]);
            pm_next[bp] = pn;
        end
    end
    // idle after this clock: nothing left to copy, and BCP adds nothing. Equal to
    // ~|pm_next; written so that BCP's commit enters at the last gate (RH006).
    wire pm_idle_base = ~|{pm_base[7], pm_base[6], pm_base[5], pm_base[4],
                           pm_base[3], pm_base[2], pm_base[1], pm_base[0]};
    wire pm_idle_next = pm_idle_base && !(bcp_commit && (bcp_add != 8'd0));

    // ---- ADRS after this clock (SAD, LDM, STM write it) and its decode (RH005) ----
    wire [9:0] adrs_sad   = {1'b0, x_imm[8:0]};
    wire [9:0] adrs_inc   = adrs + 10'd1;
    wire       we_sad     = x_ok0 && (op == OP_SAD);
    wire       we_inc     = (x_ok0 && (op == OP_LDM) && !rd_e5) || (ok_mem && (op == OP_STM));
    assign     adrs_nx    = we_sad ? adrs_sad : we_inc ? adrs_inc : adrs;
    wire [2:0] region_nx  = we_sad ? region_of(adrs_sad) : we_inc ? region_of(adrs_inc) : region;
    assign     a_block_nx = (region_nx == R_CUR) ? seq_cur : adrs_nx[6:4];   // x_cur <= seq_cur

    // ---- the operand of the next clock, read now (RH006) ---------------------------
    // Every term is what the X-stage read of the next clock would see: the store word
    // after this clock's write, the inbox and RT.OUT after this clock's inbox-port
    // write, and the slot's pending bit after this clock's copy, cancel and BCP.
    // The instruction in X is taken to complete (sx_*: no error check in front). When
    // it does not — an error of its own, or the squash behind a late one — the
    // Formation halts at this edge, and nothing reads store_q, inbox_q or the EW5
    // lookahead below until a reset; whenever it runs on, each sx_* equals the signal
    // it stands for (named on its line).
    wire        sx_sad   = x_valid && (op == OP_SAD);                            // we_sad
    wire        sx_inc   = x_valid && ((op == OP_LDM) || (op == OP_STM));        // we_inc
    wire        sx_st    = x_valid && ((op == OP_STM) || is_store_dst);          // dp_st_we
    wire        sx_bcp   = x_valid && !x_pkt && (op == OP_BCP);                  // bcp_commit
    wire        sx_cp    = cp_any && !sx_st;                                     // cp_go
    wire [9:0]  adrs_sx  = sx_sad ? adrs_sad : sx_inc ? adrs_inc : adrs;
    wire [2:0]  region_sx = sx_sad ? region_of(adrs_sad) : sx_inc ? region_of(adrs_inc) : region;
    assign      a_block_sx = (region_sx == R_CUR) ? seq_cur : adrs_sx[6:4];
    assign      s_sx     = adrs_sx[3:0];
    wire [15:0] pmA_n    = pmask[a_block_sx];
    wire [15:0] msA_n    = mask_slots(cm_mask[a_block_sx]);
    wire        pend_n   = (pmA_n[s_sx] && !(sx_cp && cp_b == a_block_sx)
                                        && !(sx_st && a_block == a_block_sx && a_slot == s_sx))
                        || (sx_bcp && new_list[a_block_sx] && msA_n[s_sx]);
    wire        dpw_n    = sx_st && (a_block == a_block_sx) && (a_slot == s_sx);   // X writes the word now
    wire        cpw_n    = sx_cp && (cp_b == a_block_sx) && pmA_n[s_sx];          // the copy lands it now
    wire [31:0] cpv_n    = (s_sx == 4'd14) ? {16'd0, rtout[a_block_sx]} : ib_rd_n[s_sx];   // (cp_b = a_block_sx)
    wire [31:0] st_val_n = dpw_n ? accm : cpw_n ? cpv_n : st_rd_n[s_sx];
    wire        ib_fwd_n = ibx_slot && (ibx_i == s_sx) && (ibx_b == a_block_sx) &&
                           (s_sx != 4'd13) && (s_sx != 4'd14);          // banks 13, 14 not stored
    wire [31:0] ib_val_n = ib_fwd_n ? ibx_wdata : ib_rd_n[s_sx];
    wire        rt_fwd_n = ibx_we && (ibx_addr == {5'b10000, a_block_sx});
    wire [15:0] rt_val_n = rt_fwd_n ? ibx_wdata[15:0] : rtout[a_block_sx];
    wire [31:0] pend_v_n = (s_sx == 4'd14) ? {16'd0, rt_val_n} : ib_val_n;
    always @(posedge clk) begin
        store_q <= pend_n ? pend_v_n : st_val_n;
        inbox_q <= (s_sx == 4'hE) ? {16'd0, rt_val_n} : (s_sx == 4'hD) ? 32'd0 : ib_val_n;
    end

    // ---- stage W registers (RH006) ---------------------------------------------------
    always @(posedge clk) begin
        if (rst) begin w_chk <= 1'b0; pf_w <= 1'b0; end
        else begin
            w_chk <= mm_spec;
            pf_w  <= pf_ew2 && mm_spec && !error_flag;
        end
        w_hi <= (op == OP_MAC) ? mac_r[64:31] : {mul_r[63], mul_r[63:31]};
        w_bk <= accm;
        w_sn <= x_sn;
        pf_w_sn <= tap_sn;
    end

    // ---- the arm bits after this clock's inbox-port write (RH004) ----------------
    reg  [7:0]  armed_nx;
    reg         sweep_armed_nx;
    always @* begin
        armed_nx = armed;
        sweep_armed_nx = sweep_armed;
        if (ibx_we && ibx_addr[7]) begin
            if (ibx_addr[6:3] == 4'b0001) armed_nx[ibx_addr[2:0]] = ibx_wdata[30];
            if (ibx_addr[6:0] == 7'h11)   sweep_armed_nx = ibx_wdata[30];
            if (ibx_addr[6:0] == 7'h1F) begin armed_nx = ibx_wdata[7:0]; sweep_armed_nx = ibx_wdata[8]; end
        end
    end

    // ---- EW5's sum, reduced one clock ahead (RH006) -------------------------------------
    // From the values the next clock will hold: the take-set and the copied flags after
    // this clock's BCP and strobe; COMMIT's slot-0 bit, the inbox's and the store's N
    // after this clock's writes; the sweep word in effect or staged. Hence each block's
    // N as BCP will see it (n_post), the nine terms (the N of the first P entries and
    // -(NMAX + 1)) and, through four levels of carry-save adders, two words whose sum
    // is the check's. As for the pre-read, the instruction in X is taken to complete
    // (sx_*): when it does not, the Formation halts and no BCP reads ew5_s and ew5_c.
    reg  [7:0]  take_n, copied_n;
    reg         take_sweep_n, sweep_copied_n;
    always @* begin
        take_n = take;  copied_n = copied;  take_sweep_n = take_sweep;  sweep_copied_n = sweep_copied;
        if (sx_bcp) begin copied_n = copied | new_list; sweep_copied_n = sweep_copied | do_sweep; end
        if (seq_strobe) begin                                   // after execute, as below
            take_n = armed_nx; take_sweep_n = sweep_armed_nx; copied_n = 8'd0; sweep_copied_n = 1'b0;
        end
    end
    wire [7:0]  new_list_n  = take_n & ~copied_n;
    wire        do_sweep_n  = take_sweep_n && !sweep_copied_n;
    wire [27:0] sweep_stg_n = (ibx_we && ibx_addr[7] && ibx_addr[6:0] == 7'h10) ? ibx_wdata[27:0] : sweep_staged;
    wire [27:0] sweep_a_n   = sx_bcp ? sweep_new : sweep_a;
    wire [27:0] sweep_new_n = do_sweep_n ? sweep_stg_n : sweep_a_n;
    reg  [31:0] n_post_n [0:7];
    integer bq;
    always @* begin : n_after_bcp_next
        reg pe0, cm0;
        reg [31:0] ibn, stn;
        for (bq = 0; bq < 8; bq = bq + 1) begin
            cm0 = (ibx_we && ibx_addr[7] && ibx_addr[6:3] == 4'b0001 && ibx_addr[2:0] == bq[2:0])
                  ? ibx_wdata[0] : cm_mask[bq][0];
            pe0 = (pmask[bq][0] && !(sx_cp && cp_b == bq[2:0]) && !(sx_st && a_block == bq[2:0] && a_slot == 4'd0))
               || (sx_bcp && new_list[bq] && cm_mask[bq][0])
               || (new_list_n[bq] && cm0);
            ibn = (ibx_slot && ibx_i == 4'd0 && ibx_b == bq[2:0]) ? ibx_wdata : ib_n[bq];
            stn = (sx_st && a_block == bq[2:0] && a_slot == 4'd0) ? accm :
                  (sx_cp && cp_b == bq[2:0] && pmask[bq][0])      ? ib_n[bq] : st_n[bq];   // the copy lands it
            n_post_n[bq] = pe0 ? ibn : stn;
        end
    end
    function [71:0] csa;                                        // a + b + c = s + t (mod 2^36): {s, t}
        input [35:0] a, b, c;
        reg [35:0] cy;
        begin
            cy  = (a & b) | (a & c) | (b & c);
            csa = {a ^ b ^ c, cy[34:0], 1'b0};
        end
    endfunction
    reg  [323:0] tm;                                            // nine terms, 36 bits each
    integer kq;
    always @* begin : ew5_terms
        reg [2:0] blk;
        for (kq = 0; kq < 8; kq = kq + 1) begin
            blk = sweep_new_n[4 + 3*kq +: 3];
            tm[36*kq +: 36] = (kq < sweep_new_n[3:0]) ? {{4{n_post_n[blk][31]}}, n_post_n[blk]} : 36'd0;
        end
        tm[288 +: 36] = NEG_NMAX1;                              // the bound, as a term
    end
    function [71:0] csa9;                                       // nine terms -> two words, the same sum
        input [323:0] t;
        reg   [71:0]  c1a, c1b, c1c, c2a, c2b, c3;
        begin
            c1a  = csa(t[  0 +: 36], t[ 36 +: 36], t[ 72 +: 36]);
            c1b  = csa(t[108 +: 36], t[144 +: 36], t[180 +: 36]);
            c1c  = csa(t[216 +: 36], t[252 +: 36], t[288 +: 36]);
            c2a  = csa(c1a[71:36], c1a[35:0], c1b[71:36]);
            c2b  = csa(c1b[35:0],  c1c[71:36], c1c[35:0]);
            c3   = csa(c2a[71:36], c2a[35:0], c2b[71:36]);
            csa9 = csa(c3[71:36],  c3[35:0],  c2b[35:0]);
        end
    endfunction
    wire [71:0] cs4 = csa9(tm);
    always @(posedge clk) begin ew5_s <= cs4[71:36]; ew5_c <= cs4[35:0]; end
    // EW5: an invalid sweep item, or the sum of N above NMAX (ew5_d = sum - NMAX - 1 >= 0;
    // the sum of eight signed 32-bit N and the bound never leaves 36 bits)
    assign ew5 = (do_sweep && sw_invalid) || !ew5_d[35];

    // ========================================================================
    //  Sequential state
    // ========================================================================
    always @(posedge clk) begin
        if (rst) begin
            accm <= 32'd0; temp <= 32'd0; adrs <= 10'd0; shv <= 5'd0;
            region <= R_STORE; a_block <= 3'd0;                  // region_of(0); adrs[6:4]
            loopval <= 12'd0; jumpval <= JUMPVAL_RESET;
            sweep_a <= 28'd0;                                    // CR5-R1: P = 0
            armed <= 8'd0; sweep_armed <= 1'b0; take <= 8'd0; take_sweep <= 1'b0;
            copied <= 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;
            sweep_staged <= 28'd0;
            for (bs = 0; bs < 8; bs = bs + 1) begin
                pmask[bs] <= 16'd0; cm_mask[bs] <= 17'd0; rtout[bs] <= 16'd0;
            end
            error_flag <= 1'b0; error_code <= 5'd0; error_sn <= 12'd0; insert_req_r <= 1'b0;
        end else begin
            // ---- the input switch writes the inbox side --------------------
            if (ibx_we && ibx_addr[7]) begin
                if (ibx_addr[6:3] == 4'b0000) rtout[ibx_addr[2:0]] <= ibx_wdata[15:0];
                if (ibx_addr[6:3] == 4'b0001) cm_mask[ibx_addr[2:0]] <= ibx_wdata[16:0];
                if (ibx_addr[6:0] == 7'h10) sweep_staged <= ibx_wdata[27:0];
            end
            armed       <= armed_nx;                                    // the arm bits (RH004: armed_nx)
            sweep_armed <= sweep_armed_nx;

            // ---- background copy, write-after-pending, BCP (pm_next) ----------
            for (bs = 0; bs < 8; bs = bs + 1) pmask[bs] <= pm_next[bs];
            // inbox_taken (CR5-I3) rises at the edge where the last pending slot lands
            // (at BCP's own edge when it leaves nothing to copy)
            if ((taken_due || bcp_commit) && pm_idle_next) begin
                inbox_taken <= 1'b1; taken_due <= 1'b0;
            end else if (bcp_commit) taken_due <= 1'b1;

            // ---- execute: each register under its own instructions' errors (RH005) --
            case (op)
                OP_LDA: if (ok_src) accm <= src;
                OP_STA: if (x_ok0 && x_rid == DST_TEMP) temp <= accm;   // STORE: see dp_st_we
                OP_ADD: if (ok_src) accm <= accm + src;                 // W-F30: wrap
                OP_SUB: if (ok_src) accm <= accm - src;
                OP_MUL: if (ok_src) accm <= mul_r[31:0];                // E8 checked in W (RH006)
                OP_MAC: if (ok_src) accm <= mac_r[31:0];
                OP_SWP: if (x_ok0) begin accm <= temp; temp <= accm; end
                OP_SFT: if (x_ok0 && !sft_ovf) accm <= sft_r;
                OP_LDM: if (x_ok0 && !rd_e5) accm <= rd_val;            // ADRS: adrs_nx
                OP_WLV: if (x_ok0) loopval <= accm[11:0];
                OP_WJV: if (x_ok0) jumpval <= accm[11:0];
                OP_WSH: if (x_ok0) shv <= accm[4:0];
                OP_STP: if (ok_stp) accm <= stp_r;
                OP_BCP: if (ok_bcp) begin                // pending slots: pm_next; inbox_taken above
                            copied       <= copied | new_list;
                            sweep_copied <= sweep_copied | do_sweep;
                            sweep_a      <= sweep_new;
                        end
                default: ;
            endcase
            adrs <= adrs_nx;  region <= region_nx;  a_block <= a_block_nx;   // SAD, LDM, STM; x_cur
            if (x_fault) begin
                error_flag <= 1'b1; error_code <= x_err; error_sn <= x_sn; insert_req_r <= 1'b1;
            end
            if (w_e8) begin                                       // RH006: the late E8
                accm <= w_bk;                                     // the scene before the violator
                if (!error_flag) begin
                    error_flag <= 1'b1; error_code <= ERR_E8; error_sn <= w_sn; insert_req_r <= 1'b1;
                end
            end else if (pf_w && !error_flag) begin               // RH006: the EW2 held back to W
                error_flag <= 1'b1; error_code <= ERR_EW2; error_sn <= pf_w_sn; insert_req_r <= 1'b1;
            end
            if (pf_ew2 && !error_flag && !x_fault && !w_kill && !mm_spec) begin
                error_flag <= 1'b1; error_code <= ERR_EW2; error_sn <= tap_sn; insert_req_r <= 1'b1;
            end
            if (insert_req_r && insert_ack) insert_req_r <= 1'b0;

            // ---- the strobe latches the take-set (sequencer) -----------------
            // Placed after execute: an instruction in X in the strobe's clock was
            // issued before the strobe and completes first (a BCP there is followed
            // by the strobe's clears, as in the model's order). The physical copy of
            // that BCP still lands (pmask); only the flags restart.
            if (seq_strobe) begin
                take <= armed_nx; take_sweep <= sweep_armed_nx;         // RH004: with this clock's arm write
                copied <= 8'd0; sweep_copied <= 1'b0; inbox_taken <= 1'b0; taken_due <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    // RH005 (SD-22): the split enables equal the one commit they replace. x_ok_split
    // is the enable each op's registers use above; x_commit is RH004's (also traced
    // by wpms_formation_tb.v).
    wire x_commit = x_go && !w_kill && (x_err == 5'd0);         // RH006: with the squash
    reg  x_ok_split;
    always @* begin
        case (op)
            OP_LDA, OP_ADD, OP_SUB: x_ok_split = ok_src;
            OP_MUL:  x_ok_split = ok_src;                          // RH006: E8 in W
            OP_MAC:  x_ok_split = ok_src;
            OP_SFT:  x_ok_split = x_ok0 && !sft_ovf;
            OP_LDM:  x_ok_split = x_ok0 && !rd_e5;
            OP_STM:  x_ok_split = ok_mem;
            OP_STA:  x_ok_split = is_store_dst ? ok_mem : x_ok0;
            OP_STP:  x_ok_split = ok_stp;
            OP_BCP:  x_ok_split = ok_bcp;
            default: x_ok_split = x_ok0;
        endcase
    end
    always @(posedge clk) if (!rst && x_valid && (x_ok_split !== x_commit))
        $display("%t wpms_formation: ERROR split enable %b against x_err %0d (op %0d)", $time, x_ok_split, x_err, op);

    // RH006: the pre-read equals the direct read of RH005 whenever an instruction is
    // in X and the Formation runs (the only shortcut, a failed BCP, halts it).
    wire [31:0] rt_a_d    = {16'd0, rtout[a_block]};
    wire [31:0] pend_a_d  = (a_slot == 4'd14) ? rt_a_d : ib_rd_a[a_slot];
    wire [15:0] pm_a_d    = pmask[a_block];
    wire [31:0] store_a_d = pm_a_d[a_slot] ? pend_a_d : st_rd_a[a_slot];
    wire [31:0] inbox_a_d = (a_slot == 4'hE) ? rt_a_d : (a_slot == 4'hD) ? 32'd0 : ib_rd_a[a_slot];
    always @(posedge clk) if (!rst && x_go && (store_q !== store_a_d || inbox_q !== inbox_a_d))
        $display("%t wpms_formation: ERROR pre-read %h %h against the direct read %h %h (block %0d slot %0d)",
                 $time, store_q, inbox_q, store_a_d, inbox_a_d, a_block, a_slot);
    // RH006: the reduced sum equals the direct sum minus NMAX + 1 whenever the Formation runs
    always @(posedge clk) if (!rst && x_go && (ew5_d !== (chk_sum - (NMAX + 1))))
        $display("%t wpms_formation: ERROR EW5 lookahead %h against the direct sum %h", $time, ew5_d, chk_sum);
    // RH006: the late E8 is RH005's E8 (mul_ovf / mac_ovf in X), one clock later
    reg w_ovf_ref;
    always @(posedge clk) w_ovf_ref <= (op == OP_MAC) ? mac_ovf : mul_ovf;
    always @(posedge clk) if (!rst && w_chk && (w_e8 !== w_ovf_ref))
        $display("%t wpms_formation: ERROR late E8 %b against the overflow seen in X %b", $time, w_e8, w_ovf_ref);
    // RH006: the idle test written with BCP's commit last equals RH005's
    wire pm_idle_d = ~|{pm_next[7], pm_next[6], pm_next[5], pm_next[4], pm_next[3], pm_next[2], pm_next[1], pm_next[0]};
    always @(posedge clk) if (!rst && (pm_idle_next !== pm_idle_d))
        $display("%t wpms_formation: ERROR idle test %b against %b", $time, pm_idle_next, pm_idle_d);
    // The same four checks as wires, for the proof (tools/equiv_formal.py: one clock from any state)
    wire chk_pre  = !x_go  || (store_q == store_a_d && inbox_q == inbox_a_d);
    wire chk_ew5  = !x_go  || (ew5_d == chk_sum - (NMAX + 1));
    wire chk_e8   = !w_chk || (w_e8 == w_ovf_ref);
    wire chk_idle = (pm_idle_next == pm_idle_d);
    // chk_ew5 for the proof in three steps, each one a plain claim: the terms reduced at
    // the last edge are the direct terms now (chk_tm); the registers hold csa9 of them
    // and the bound (chk_csa); the direct sum is the tree of those terms (chk_tree). With
    // equiv_formal's arithmetic claim (csa9's two words add up to the tree minus
    // NMAX + 1, for any eight sign-extended terms), they give chk_ew5.
    reg  [287:0] tm_q;
    always @(posedge clk) tm_q <= tm[287:0];
    reg  [287:0] tm_d;
    integer kd;
    always @* begin : direct_terms
        reg [2:0] blk;
        for (kd = 0; kd < 8; kd = kd + 1) begin
            blk = sweep_new[4 + 3*kd +: 3];
            tm_d[36*kd +: 36] = (kd < sweep_new[3:0]) ? {{4{n_all[32*blk + 31]}}, n_all[32*blk +: 32]} : 36'd0;
        end
    end
    wire chk_tm   = !x_go || (tm_q == tm_d);
    wire chk_csa  = ({ew5_s, ew5_c} == csa9({NEG_NMAX1, tm_q}));
    wire chk_tree = (chk_sum == ((tm_d[  0 +: 36] + tm_d[ 36 +: 36]) + (tm_d[ 72 +: 36] + tm_d[108 +: 36]))
                              + ((tm_d[144 +: 36] + tm_d[180 +: 36]) + (tm_d[216 +: 36] + tm_d[252 +: 36])));

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
