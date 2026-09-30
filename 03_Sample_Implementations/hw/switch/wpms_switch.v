// ============================================================================
//  wpms_switch.v — the minimal input switch (customer Ch.5 §5.4-§5.8), one module
//  最小の入力スイッチ（顧客 第5章 §5.4〜§5.8）、1 モジュール
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 5, with the architect's ruling of 2026-09-30
//  (the host path is ISSP over JTAG: wpms_host_bridge.v). The switch presents
//  the address map of Ch.5 §5.6 (32-bit words; the global region 0x000-0x0FF,
//  module 0 at 0x200-0x2FF) on two of the four ports of §5.5.1:
//    port 0  the host (the ISSP bridge); KEY[0] enters here as a GO_ALL
//    port 3  the built-in ROM: a list of (address, data) writes, played after
//            reset, on KEY[1] and on TEST_ORIGIN (§5.8; CR5-R1)
//  Ports 1 (camera) and 2 (HPS) are not built.
//
//  TRANSACTIONS. One at a time: a request is picked (an unfreeze first, then
//  ports 0 and 3 in turn), executed in the next clock (EXEC: checked and
//  applied; the inbox write it makes leaves registered, one clock later) and
//  answered in the clock after EXEC (done, rdata, rej). Reads are never
//  refused. A refused write changes nothing but REJECT[port].
//
//  STAGE, ARM, GO (§5.4). Nine items: blocks 0-7 and the sweep word. An item
//  is ARMED by COMMIT[b] / SWEEP_COMMIT bit 30 (the arming port is noted),
//  FIRED by a GO and APPLIED once the Formation has copied it; from arm to
//  apply it is FROZEN: writes to its slots, RTOUT, COMMIT or SWEEP are refused.
//    GO[0]   the items this port armed       GO[1]  GO_ALL: every armed item
//    KEY[0]  GO_ALL                          bit 31 of COMMIT / SWEEP_COMMIT:
//                                            go-now, this item alone
//  Every GO is checked before it fires (PR-1, PR-2, §5.4.4) against the state
//  that all earlier GOs leave: the sweep word then in effect has P <= 8, no
//  block twice among its first P entries, every listed block's N in
//  [N_MIN, NMAX] (the build's: EW2's range) and the sum of those N <= NMAX.
//  A GO that fails is refused and the items it would fire are disarmed (back
//  to staged); GO_SEQ counts the GOs that pass, empty ones included.
//
//  HAND-OVER. The fired set is written into the Formation's armed flags in ONE
//  clock (inbox port 0x9F, Formation RH004; a go-now uses its own item's arm
//  bit), so a strobe takes all of a GO or none of it (§5.2: "at one sample
//  boundary"). The Formation latches its take-set at the strobe (Map v0.3 §7),
//  including a write presented in the strobe clock itself (RH004): a GO is
//  taken by the first strobe after its EXEC clock and plays from the second
//  (§5.4.3). The switch mirrors the flags (fa) and the take (ft) with the same
//  rules.
//  APPLY. When inbox_taken rises (CR5-I3) the taken items leave the flags (one
//  more 0x9F write, a few clocks after the rise, long before the next strobe:
//  the Formation raises inbox_taken inside the housekeeping window), unfreeze,
//  and APPLIED_SEQ / APPLIED_SAMPLE publish the last GO that take carried and
//  n + 1, n being the take's strobe.
//  SAMPLE n: strobes since reset; the sweep a strobe starts bears its count.
//
//  CHOICES where Ch.5 is silent (reports/phase5_switch.md §4.4): a refused GO
//  disarms its items; writes to read-only, reserved or unmapped words are
//  refused and counted; OWNER is kept but not enforced (the two ports built
//  are the privileged ones, SD-20); after reset every block's N counts as
//  unknown (0) until written; INSPECT_L = the L1's Q.30 level >> 4, saturated
//  to Q6.26; CONFIG[31:24] = 0; VERSION = 0x0001_0000 (Ch.5 v1.0).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_switch #(
    parameter integer NMAX       = 1008,
    parameter integer N_MIN      = 32,
    parameter integer ROM_DEPTH  = 256,
    parameter         ROM_HEX    = "wpms_rom_origin_1008.hex",
    parameter         ROM_MIF    = "",
    parameter         ROM_VENDOR = "SIM"          // "SIM" | "M10K"
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         strobe,                   // synchronized, one clock (the Formation's seq_strobe)

    // ---- port 0: the host bridge ----------------------------------------------------------
    input  wire         p0_req,                   // one clock; the fields hold until p0_done
    input  wire         p0_we,
    input  wire [11:0]  p0_addr,
    input  wire [31:0]  p0_wdata,
    output wire         p0_done,
    output wire [31:0]  rdata,                    // valid with a done (port 0 or the ROM)
    output wire         rej,

    // ---- board events: one-clock pulses (wpms_key_pulse) ---------------------------------
    input  wire         key_go_all,               // KEY[0]
    input  wire         key_origin,               // KEY[1]

    // ---- module 0: the Formation's inbox port (wpms_l2_top) --------------------------------
    output reg          ibx_we,
    output reg  [7:0]   ibx_addr,
    output reg  [31:0]  ibx_wdata,
    input  wire         inbox_taken,
    input  wire [27:0]  sweep_a,

    // ---- Ch.4 knobs ------------------------------------------------------------------------
    output reg  signed [31:0] mg_target,
    output reg  [31:0]  mg_rate,
    output reg  [4:0]   g_ctrl,
    output reg          mute,
    output reg  [1:0]   clip_clear,               // one clock
    output reg          minmax_clear,             // one clock
    output wire [11:0]  insp_pos,

    // ---- taps read through the map ------------------------------------------------------
    input  wire signed [31:0] mg,
    input  wire [3:0]   g_eff,
    input  wire [1:0]   clip,
    input  wire [11:0]  strobe_interval,
    input  wire [11:0]  strobe_min,
    input  wire [11:0]  strobe_max,
    input  wire [11:0]  sweep_clocks,
    input  wire [31:0]  insp_phase,
    input  wire signed [53:0] insp_L,
    input  wire [31:0]  insp_a,

    // ---- status (the ISSP probes, the testbench) --------------------------------------------
    output reg  [31:0]  go_seq,
    output reg  [31:0]  applied_seq,
    output reg  [31:0]  applied_sample,
    output reg  [31:0]  reject0,
    output reg  [31:0]  reject3,
    output wire [8:0]   frozen,
    output reg  [11:0]  sweep_clocks_max,
    output wire         rom_busy,
    output wire [31:0]  insp_l_q626               // INSPECT_L as read (for the ISSP probe)
);
    localparam [31:0] ID       = 32'h5750_4D53;           // "WPMS"
    localparam [31:0] VERSION  = 32'h0001_0000;           // Ch.5 v1.0
    localparam [15:0] NMAX16   = NMAX;
    localparam [31:0] CONFIG   = {8'd0, NMAX16, 4'd8, 4'd1};   // M = 1, 8 blocks, NMAX
    localparam integer RAW     = $clog2(ROM_DEPTH);

    // ======================================================================================
    //  State
    // ======================================================================================
    // ---- items: [7:0] blocks, [8] the sweep word -----------------------------------------
    reg  [8:0]   arm;                     // armed, waiting for a GO
    reg  [8:0]   arm_p3;                  // armed by port 3 (else port 0)
    reg  [8:0]   fired;                   // fired, not yet applied (= the Formation's flags, one clock ahead)
    reg  [8:0]   fa;                      // mirror of the Formation's armed flags
    reg  [8:0]   ft;                      // mirror of the Formation's take-set
    reg          ft_open;                 // a take not yet applied
    reg  [31:0]  fa_seq, ft_seq;          // GO_SEQ of the last hand-over landed / taken
    reg  [31:0]  n_take;                  // n of the strobe that took ft
    assign frozen = arm | fired;

    // ---- staged values, and the sweep once every fired item has landed -----------------------
    reg  [135:0] cmask_v;                 // COMMIT[b] [16:0], 17 bits per block
    reg  [127:0] rtout_v;                 // RTOUT[b], 16 bits per block
    reg  [27:0]  sw_st;                   // SWEEP (staged)
    reg  [95:0]  n_st_v;  reg [7:0] nv_st;  // staged N: low 12 bits; N in [N_MIN, NMAX]
    reg  [95:0]  n_fu_v;  reg [7:0] nv_fu;  // N once every fired item has landed
    reg  [27:0]  sw_fu;                   // sweep word once every fired item has landed

    // ---- global registers ---------------------------------------------------------------------
    reg  [63:0]  sample_n;
    reg  [31:0]  sample_hi;
    reg  [17:0]  owner0;
    reg  [3:0]   insp_mod;
    reg  [11:0]  insp_pos_r;
    assign insp_pos = insp_pos_r;

    // ---- requests -----------------------------------------------------------------------------------
    reg          p0_pend, key_pend, unf_pend, taken_d, rr;
    reg          p0_we_l;  reg [11:0] p0_a_l;  reg [31:0] p0_d_l;
    reg          rom_req;  reg [11:0] rom_a;   reg [31:0] rom_d;
    // ---- EXEC and DONE ------------------------------------------------------------------------------
    reg          x_v, x_unf, x_p3, x_we;
    reg  [11:0]  x_a;
    reg  [31:0]  x_d;
    reg          d_v, d_p3, d_rej, d_inbox;
    reg  [31:0]  d_rdata;
    reg          ibx_hand;                // the inbox write in flight is a hand-over ...
    reg  [31:0]  ibx_seq;                 // ... carrying this GO_SEQ

    // ---- the Formation's armed flags after the write presented this clock (its RH004 rules) ----
    reg  [8:0]   fa_nx;
    always @* begin
        fa_nx = fa;
        if (ibx_we && ibx_addr[7]) begin
            if (ibx_addr[6:3] == 4'b0001) fa_nx[ibx_addr[2:0]] = ibx_wdata[30];
            if (ibx_addr[6:0] == 7'h11)   fa_nx[8] = ibx_wdata[30];
            if (ibx_addr[6:0] == 7'h1F)   fa_nx = ibx_wdata[8:0];
        end
    end
    wire [31:0]  fa_seq_nx = (ibx_we && ibx_hand) ? ibx_seq : fa_seq;

    // ======================================================================================
    //  Arbitration: an unfreeze first; then ports 0 and 3 in turn
    // ======================================================================================
    wire want0    = p0_pend || key_pend;
    wire pick_unf = unf_pend;
    wire pick0    = !pick_unf && want0 && (!rom_req || rr);
    wire pick3    = !pick_unf && rom_req && (!want0 || !rr);

    // ======================================================================================
    //  EXEC decode
    // ======================================================================================
    wire         x_glob   = (x_a[11:8] == 4'h0);
    wire         x_mod    = (x_a[11:8] == 4'h2);
    wire [7:0]   xo       = x_a[7:0];
    wire         x_inbox  = x_mod && !xo[7];
    wire         x_rtout  = x_mod && (xo[7:3] == 5'b10000);
    wire         x_commit = x_mod && (xo[7:3] == 5'b10001);
    wire [2:0]   xb       = x_inbox ? xo[6:4] : xo[2:0];
    wire [3:0]   xi       = xo[3:0];
    wire         x_slot_ok = x_inbox && xi != 4'hD && xi != 4'hE;
    wire         x_sweep  = x_mod && (xo == 8'h90);
    wire         x_swcmt  = x_mod && (xo == 8'h91);
    wire         x_go     = x_glob && (xo == 8'h08) && x_we && (x_d[1:0] != 2'b00);
    wire         x_nowb   = x_commit && x_we && x_d[31] && !frozen[xb];
    wire         x_nows   = x_swcmt  && x_we && x_d[31] && !frozen[8];
    wire         x_inrange = ($signed(x_d) >= N_MIN) && ($signed(x_d) <= NMAX);

    // ---- the items a GO fires ---------------------------------------------------------------------
    reg  [8:0] go_items;
    always @* begin
        go_items = 9'd0;
        if (x_go)        go_items = x_d[1] ? arm : (arm & (x_p3 ? arm_p3 : ~arm_p3));
        else if (x_nowb) go_items[xb] = 1'b1;
        else if (x_nows) go_items[8]  = 1'b1;
    end

    // ---- the state the GO would leave, and its check (PR-1, PR-2, §5.4.4) --------------------
    reg  [95:0] n_nx_v;  reg [7:0] nv_nx;
    reg         mb;
    integer     vb;
    always @* begin
        for (vb = 0; vb < 8; vb = vb + 1) begin
            mb = (x_nowb && xb == vb) ? x_d[0] : cmask_v[17*vb];        // mask bit 0 = slot N
            if (go_items[vb] && mb) begin
                n_nx_v[12*vb +: 12] = n_st_v[12*vb +: 12];  nv_nx[vb] = nv_st[vb];
            end else begin
                n_nx_v[12*vb +: 12] = n_fu_v[12*vb +: 12];  nv_nx[vb] = nv_fu[vb];
            end
        end
    end
    wire [27:0] sw_nx = go_items[8] ? sw_st : sw_fu;
    reg         go_bad;
    reg  [14:0] go_sum;
    reg  [7:0]  seen;
    reg  [2:0]  blk;
    integer     q;
    always @* begin
        go_bad = (sw_nx[3:0] > 4'd8);
        go_sum = 15'd0;
        seen   = 8'd0;
        blk    = 3'd0;
        for (q = 0; q < 8; q = q + 1)
            if (q < sw_nx[3:0]) begin
                blk = sw_nx[4 + 3*q +: 3];
                if (seen[blk] || !nv_nx[blk]) go_bad = 1'b1;
                seen[blk] = 1'b1;
                go_sum = go_sum + {3'd0, n_nx_v[12*blk +: 12]};
            end
        if (go_sum > NMAX) go_bad = 1'b1;
    end

    // ---- reads ----------------------------------------------------------------------------------
    wire signed [49:0] l26 = insp_L >>> 4;
    assign insp_l_q626 = (l26 > 50'sh7FFF_FFFF)  ? 32'h7FFF_FFFF :
                         (l26 < -50'sh8000_0000) ? 32'h8000_0000 : l26[31:0];
    reg  [31:0] rd_v;
    always @* begin
        rd_v = 32'd0;
        if (x_glob) begin
            case (xo)
                8'h00: rd_v = ID;
                8'h01: rd_v = VERSION;
                8'h02: rd_v = CONFIG;
                8'h03: rd_v = x_p3 ? 32'd3 : 32'd0;                      // PORT_ID
                8'h09: rd_v = go_seq;
                8'h0A: rd_v = applied_seq;
                8'h0B: rd_v = applied_sample;
                8'h0C: rd_v = sample_n[31:0];
                8'h0D: rd_v = sample_hi;
                8'h10: rd_v = mg_target;
                8'h11: rd_v = mg_rate;
                8'h12: rd_v = mg;
                8'h13: rd_v = {27'd0, g_ctrl};
                8'h14: rd_v = {28'd0, g_eff};
                8'h15: rd_v = {31'd0, mute};
                8'h16: rd_v = {30'd0, clip};
                8'h18: rd_v = {20'd0, strobe_interval};
                8'h19: rd_v = {4'd0, strobe_max, 4'd0, strobe_min};
                8'h20: rd_v = {14'd0, owner0};
                8'h30: rd_v = reject0;
                8'h33: rd_v = reject3;
                8'h40: rd_v = {16'd0, insp_pos_r, insp_mod};
                8'h41: rd_v = insp_phase;
                8'h42: rd_v = insp_l_q626;
                8'h43: rd_v = insp_a;
                default: rd_v = 32'd0;
            endcase
        end else if (x_mod) begin
            if (x_rtout)            rd_v = {16'd0, rtout_v[16*xb +: 16]};
            else if (x_commit)      rd_v = {1'b0, frozen[xb], 13'd0, cmask_v[17*xb +: 17]};
            else if (x_sweep)       rd_v = {4'd0, sw_st};
            else if (x_swcmt)       rd_v = {1'b0, frozen[8], 30'd0};
            else if (xo == 8'h92)   rd_v = {4'd0, sweep_a};
            else if (xo == 8'h98)   rd_v = {20'd0, sweep_clocks};
            else if (xo == 8'h99)   rd_v = {20'd0, sweep_clocks_max};
        end
    end

    // ---- the inbox shadow: what INBOX[b][i] reads (the Formation keeps the real inbox) --------
    reg  [31:0] shadow [0:127];
    reg  [31:0] shadow_q;
    integer     si;
    initial for (si = 0; si < 128; si = si + 1) shadow[si] = 32'd0;
    wire        sh_we = x_v && !x_unf && x_we && x_slot_ok && !frozen[xb];
    always @(posedge clk) begin
        if (sh_we) shadow[xo[6:0]] <= x_d;
        shadow_q <= shadow[xo[6:0]];
    end

    // ---- answers ----------------------------------------------------------------------------------
    assign p0_done = d_v && !d_p3;
    wire   rom_done = d_v && d_p3;
    assign rdata   = d_inbox ? shadow_q : d_rdata;
    assign rej     = d_rej;

    // ======================================================================================
    //  The ROM player (port 3)
    // ======================================================================================
    localparam [1:0] R_IDLE = 2'd0, R_ADDR = 2'd1, R_DATA = 2'd2, R_WAIT = 2'd3;
    reg  [1:0]     rom_st;
    reg  [RAW-1:0] rom_idx;
    reg            rom_start;             // TEST_ORIGIN written (port 0)
    wire [43:0]    rom_q;
    assign rom_busy = (rom_st != R_IDLE);

    wpms_rom #(.DEPTH(ROM_DEPTH), .VENDOR(ROM_VENDOR), .INIT_HEX(ROM_HEX), .INIT_MIF(ROM_MIF)) u_rom (
        .clk(clk), .addr(rom_idx), .q(rom_q));

    always @(posedge clk) begin
        if (rst) begin
            rom_st <= R_ADDR;  rom_idx <= {RAW{1'b0}};  rom_req <= 1'b0;   // CR5-R1: play after reset
            rom_a <= 12'd0;  rom_d <= 32'd0;
        end else begin
            if (pick3) rom_req <= 1'b0;
            case (rom_st)
                R_IDLE:
                    if (rom_start || key_origin) begin rom_idx <= {RAW{1'b0}}; rom_st <= R_ADDR; end
                R_ADDR:                                     // the ROM registers rom_idx now
                    rom_st <= R_DATA;
                R_DATA:
                    if (rom_q[43:32] == 12'hFFF) rom_st <= R_IDLE;
                    else begin
                        rom_req <= 1'b1;  rom_a <= rom_q[43:32];  rom_d <= rom_q[31:0];
                        rom_st  <= R_WAIT;
                    end
                R_WAIT:
                    if (rom_done) begin
                        if (rom_idx == ROM_DEPTH - 1) rom_st <= R_IDLE;
                        else begin rom_idx <= rom_idx + 1'b1; rom_st <= R_ADDR; end
                    end
            endcase
        end
    end

    // ======================================================================================
    //  Requests, EXEC, the strobe, the mirror
    // ======================================================================================
    reg        rej_now, fire_now, swmax_clr;
    reg [31:0] seq_nx;
    always @(posedge clk) begin
        ibx_we <= 1'b0;  ibx_hand <= 1'b0;
        clip_clear <= 2'b00;  minmax_clear <= 1'b0;  rom_start <= 1'b0;
        d_v <= 1'b0;
        rej_now = 1'b0;  fire_now = 1'b0;  swmax_clr = 1'b0;
        seq_nx = go_seq + 32'd1;
        if (rst) begin
            arm <= 9'd0;  arm_p3 <= 9'd0;  fired <= 9'd0;  fa <= 9'd0;  ft <= 9'd0;  ft_open <= 1'b0;
            fa_seq <= 32'd0;  ft_seq <= 32'd0;  n_take <= 32'd0;
            cmask_v <= 136'd0;  rtout_v <= 128'd0;  sw_st <= 28'd0;
            n_st_v <= 96'd0;  nv_st <= 8'd0;  n_fu_v <= 96'd0;  nv_fu <= 8'd0;  sw_fu <= 28'd0;
            sample_n <= 64'd0;  sample_hi <= 32'd0;  owner0 <= 18'd0;  insp_mod <= 4'd0;  insp_pos_r <= 12'd0;
            go_seq <= 32'd0;  applied_seq <= 32'd0;  applied_sample <= 32'd0;
            reject0 <= 32'd0;  reject3 <= 32'd0;  sweep_clocks_max <= 12'd0;
            mg_target <= 32'sd0;  mg_rate <= 32'd13_933;  g_ctrl <= 5'd0;  mute <= 1'b0;
            p0_pend <= 1'b0;  key_pend <= 1'b0;  unf_pend <= 1'b0;  taken_d <= 1'b0;  rr <= 1'b0;
            p0_we_l <= 1'b0;  p0_a_l <= 12'd0;  p0_d_l <= 32'd0;
            x_v <= 1'b0;  x_unf <= 1'b0;  x_p3 <= 1'b0;  x_we <= 1'b0;  x_a <= 12'd0;  x_d <= 32'd0;
            d_p3 <= 1'b0;  d_rej <= 1'b0;  d_inbox <= 1'b0;  d_rdata <= 32'd0;
            ibx_addr <= 8'd0;  ibx_wdata <= 32'd0;  ibx_seq <= 32'd0;
        end else begin
            // ---- requests --------------------------------------------------------------------
            if (p0_req) begin p0_pend <= 1'b1; p0_we_l <= p0_we; p0_a_l <= p0_addr; p0_d_l <= p0_wdata; end
            if (key_go_all) key_pend <= 1'b1;
            taken_d <= inbox_taken;
            if (inbox_taken && !taken_d) unf_pend <= 1'b1;

            // ---- pick ------------------------------------------------------------------------------
            x_v   <= pick_unf || pick0 || pick3;
            x_unf <= pick_unf;
            x_p3  <= pick3;
            if (pick_unf) unf_pend <= 1'b0;
            if (pick0) begin
                rr <= 1'b0;
                if (p0_pend) begin
                    p0_pend <= 1'b0;  x_we <= p0_we_l;  x_a <= p0_a_l;  x_d <= p0_d_l;
                end else begin                                   // KEY[0]: a GO_ALL on port 0
                    key_pend <= 1'b0; x_we <= 1'b1;     x_a <= 12'h008; x_d <= 32'd2;
                end
            end else if (pick3) begin
                rr <= 1'b1;  x_we <= 1'b1;  x_a <= rom_a;  x_d <= rom_d;
            end

            // ---- EXEC: apply (the Formation has copied the take) -------------------------------
            if (x_v && x_unf) begin
                if (ft_open) begin
                    ft_open <= 1'b0;
                    fired   <= fired & ~ft;
                    if (ft != 9'd0) begin
                        ibx_we <= 1'b1;  ibx_addr <= 8'h9F;  ibx_wdata <= {23'd0, fired & ~ft};
                    end
                    if (ft_seq != applied_seq) begin
                        applied_seq    <= ft_seq;
                        applied_sample <= n_take + 32'd1;
                    end
                end

            // ---- EXEC: a transaction ---------------------------------------------------------------
            end else if (x_v) begin
                d_v <= 1'b1;  d_p3 <= x_p3;  d_inbox <= !x_we && x_slot_ok;  d_rdata <= 32'd0;
                if (!x_we) begin
                    d_rdata <= rd_v;
                    if (x_glob && xo == 8'h0C) sample_hi <= sample_n[63:32];   // reading LO latches HI
                end else if (x_glob) begin
                    case (xo)
                        8'h08: if (x_d[1:0] != 2'b00) begin              // GO / GO_ALL
                                   if (go_bad) begin rej_now = 1'b1; arm <= arm & ~go_items; end
                                   else begin
                                       fire_now = 1'b1;
                                       ibx_we <= 1'b1;  ibx_addr <= 8'h9F;  ibx_wdata <= {23'd0, fired | go_items};
                                   end
                               end
                        8'h10: mg_target <= x_d;
                        8'h11: mg_rate   <= x_d;
                        8'h13: g_ctrl    <= x_d[4:0];
                        8'h15: mute      <= x_d[0];
                        8'h16: clip_clear <= x_d[1:0];
                        8'h19: minmax_clear <= 1'b1;
                        8'h1C: if (x_p3) rej_now = 1'b1;                  // the ROM cannot restart itself
                               else if (x_d[0] && !rom_busy) rom_start <= 1'b1;
                        8'h20: owner0 <= x_d[17:0];
                        8'h30: reject0 <= reject0 & ~x_d;
                        8'h31, 8'h32: ;                                  // ports not built: nothing to clear
                        8'h33: reject3 <= reject3 & ~x_d;
                        8'h40: begin insp_mod <= x_d[3:0]; insp_pos_r <= x_d[15:4]; end
                        default: rej_now = 1'b1;                          // read-only or unmapped
                    endcase
                end else if (x_mod) begin
                    if (x_inbox) begin
                        if (!x_slot_ok || frozen[xb]) rej_now = 1'b1;
                        else begin
                            ibx_we <= 1'b1;  ibx_addr <= {1'b0, xb, xi};  ibx_wdata <= x_d;
                            if (xi == 4'd0) begin n_st_v[12*xb +: 12] <= x_d[11:0]; nv_st[xb] <= x_inrange; end
                        end
                    end else if (x_rtout) begin
                        if (frozen[xb]) rej_now = 1'b1;
                        else begin
                            rtout_v[16*xb +: 16] <= x_d[15:0];
                            ibx_we <= 1'b1;  ibx_addr <= {5'b10000, xb};  ibx_wdata <= {16'd0, x_d[15:0]};
                        end
                    end else if (x_commit) begin
                        if (frozen[xb]) rej_now = 1'b1;
                        else if (x_d[31]) begin                            // go-now: arm and fire this block
                            if (go_bad) rej_now = 1'b1;
                            else begin
                                fire_now = 1'b1;
                                cmask_v[17*xb +: 17] <= x_d[16:0];
                                ibx_we <= 1'b1;  ibx_addr <= {5'b10001, xb};  ibx_wdata <= {1'b0, 1'b1, 13'd0, x_d[16:0]};
                            end
                        end else begin
                            cmask_v[17*xb +: 17] <= x_d[16:0];            // the Formation's flag stays 0
                            ibx_we <= 1'b1;  ibx_addr <= {5'b10001, xb};  ibx_wdata <= {15'd0, x_d[16:0]};
                            if (x_d[30]) begin arm[xb] <= 1'b1; arm_p3[xb] <= x_p3; end
                        end
                    end else if (x_sweep) begin
                        if (frozen[8]) rej_now = 1'b1;
                        else begin
                            sw_st <= x_d[27:0];
                            ibx_we <= 1'b1;  ibx_addr <= 8'h90;  ibx_wdata <= {4'd0, x_d[27:0]};
                        end
                    end else if (x_swcmt) begin
                        if (frozen[8]) rej_now = 1'b1;
                        else if (x_d[31]) begin                            // go-now: the sweep word alone
                            if (go_bad) rej_now = 1'b1;
                            else begin
                                fire_now = 1'b1;
                                ibx_we <= 1'b1;  ibx_addr <= 8'h91;  ibx_wdata <= 32'h4000_0000;
                            end
                        end else if (x_d[30]) begin arm[8] <= 1'b1; arm_p3[8] <= x_p3; end
                    end else if (xo == 8'h99) swmax_clr = 1'b1;           // SWEEP_CLOCKS_MAX: write clears
                    else rej_now = 1'b1;                                   // read-only or unmapped
                end else rej_now = 1'b1;                                   // no such module or region

                if (fire_now) begin
                    fired  <= fired | go_items;
                    arm    <= arm & ~go_items;
                    n_fu_v <= n_nx_v;  nv_fu <= nv_nx;  sw_fu <= sw_nx;
                    go_seq <= seq_nx;
                    ibx_hand <= 1'b1;  ibx_seq <= seq_nx;
                end
                if (rej_now) begin
                    d_rej <= 1'b1;
                    if (x_p3) reject3 <= reject3 + 32'd1;
                    else      reject0 <= reject0 + 32'd1;
                end else d_rej <= 1'b0;
            end

            // ---- the strobe: the Formation takes its armed flags, with this clock's write (mirror) ------
            if (strobe) begin
                ft <= fa_nx;  ft_seq <= fa_seq_nx;  ft_open <= 1'b1;
                n_take   <= sample_n[31:0] + 32'd1;
                sample_n <= sample_n + 64'd1;
            end
            // ---- the mirror of the Formation's armed flags: its own update rules (RH004) ------------
            fa     <= fa_nx;
            fa_seq <= fa_seq_nx;

            // ---- SWEEP_CLOCKS_MAX ---------------------------------------------------------------------
            if (swmax_clr) sweep_clocks_max <= 12'd0;
            else if (sweep_clocks > sweep_clocks_max) sweep_clocks_max <= sweep_clocks;
        end
    end

`ifndef SYNTHESIS
    // The one timing assumption of the apply path: the Formation's flags lose a
    // take's items before the next strobe could take them again. inbox_taken is
    // still high in the strobe clock when the take's copy landed in this sweep;
    // ft_open says its apply step has not executed yet (after it, an item may
    // lawfully be armed and fired again).
    always @(posedge clk) if (!rst && strobe && ft_open && inbox_taken && (fa_nx & ft) != 9'd0)
        $display("%t wpms_switch: ERROR a strobe met copied items still armed (fa %03h ft %03h)", $time, fa_nx, ft);
`endif

endmodule
