// ============================================================================
//  wpms_host_bridge.v — the ISSP host path: source bits to port-0 transactions
//  ISSP ホスト経路: ソースビットからポート 0 のトランザクションへ
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  The architect's ruling of 2026-09-30: the host reaches the switch through
//  In-System Sources and Probes over JTAG, by hand from the Quartus editor.
//  The protocol is the simplest that stays correct when the source bits come
//  from another clock domain and change in any order:
//
//    source (48 bits)  [31:0]  WDATA      probe (36 bits)  [31:0]  RDATA
//                      [43:32] ADDR (word address, Ch.5 §5.6)  [32] WR_ACK
//                      [44]    WR  (toggle)                    [33] RD_ACK
//                      [45]    RD  (toggle)                    [34] REJ
//                      [47:46] 0                               [35] 0
//    in hex: source = C AAA DDDDDDDD, probe = S RRRRRRRR
//
//    Write: set ADDR and WDATA, then flip WR (in the same edit or later). The
//    bridge writes WDATA to ADDR, reads ADDR back into RDATA, sets REJ if the
//    switch refused the write, and only then makes WR_ACK equal to WR.
//    Read: set ADDR, flip RD; RDATA = the word, then RD_ACK = RD.
//    Nothing happens while WR = WR_ACK and RD = RD_ACK: editing ADDR or WDATA
//    alone never writes.
//  Every source bit passes two flip-flops; a toggle seen changed waits SETTLE
//  more clocks before ADDR and WDATA are taken, so fields that changed with
//  (or up to SETTLE clocks after) the toggle are taken whole. RDATA and REJ
//  are stable two clocks before the acknowledge moves. At reset the
//  acknowledges take the toggles' current values: the editor's sources survive
//  a design reset, and no stale toggle replays a transaction.
//  In wpms_system.v the source is the OR of the ISSP instance HOST and the
//  deterministic controller of the testbench (0 on the board).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_host_bridge #(
    parameter integer SETTLE = 4
) (
    input  wire         clk,
    input  wire         rst,
    input  wire [47:0]  src,                    // asynchronous (JTAG domain)
    output wire [35:0]  prb,

    output reg          p0_req,                 // one clock; the fields hold until p0_done
    output reg          p0_we,
    output reg  [11:0]  p0_addr,
    output reg  [31:0]  p0_wdata,
    input  wire         p0_done,
    input  wire [31:0]  p0_rdata,
    input  wire         p0_rej
);
    // ---- synchronizers ------------------------------------------------------------------
    reg  [47:0] s1, s2;
    always @(posedge clk) begin
        s1 <= src;
        s2 <= s1;
    end
    wire wt = s2[44];
    wire rt = s2[45];

    // ---- the probe --------------------------------------------------------------------
    reg         wack, rack, rej_r;
    reg  [31:0] rdata_r;
    assign prb = {1'b0, rej_r, rack, wack, rdata_r};

    // ---- one operation at a time --------------------------------------------------------
    localparam [2:0] B_IDLE = 3'd0, B_SETTLE = 3'd1, B_WR = 3'd2, B_WWAIT = 3'd3,
                     B_RD = 3'd4, B_RWAIT = 3'd5, B_ACK = 3'd6;
    localparam integer CW = (SETTLE < 2) ? 2 : $clog2(SETTLE + 1);
    reg [2:0]    st;
    reg [CW-1:0] cnt;
    reg          do_w, w_tgl, r_tgl;

    always @(posedge clk) begin
        p0_req <= 1'b0;
        if (rst) begin
            st <= B_IDLE;  cnt <= {CW{1'b0}};
            wack <= wt;  rack <= rt;  rej_r <= 1'b0;  rdata_r <= 32'd0;
            do_w <= 1'b0;  w_tgl <= wt;  r_tgl <= rt;
            p0_we <= 1'b0;  p0_addr <= 12'd0;  p0_wdata <= 32'd0;
        end else case (st)
            B_IDLE:
                if (wt != wack || rt != rack) begin
                    st  <= B_SETTLE;
                    cnt <= SETTLE[CW-1:0];
                end
            B_SETTLE:
                if (cnt != {CW{1'b0}}) cnt <= cnt - 1'b1;
                else begin                                  // everything has held still: take it
                    w_tgl    <= wt;
                    r_tgl    <= rt;
                    do_w     <= (wt != wack);
                    p0_addr  <= s2[43:32];
                    p0_wdata <= s2[31:0];
                    st       <= (wt != wack) ? B_WR : (rt != rack) ? B_RD : B_IDLE;
                end
            B_WR: begin
                p0_req <= 1'b1;  p0_we <= 1'b1;  st <= B_WWAIT;
            end
            B_WWAIT:
                if (p0_done) begin
                    rej_r <= p0_rej;
                    st    <= B_RD;                          // then read the word back
                end
            B_RD: begin
                p0_req <= 1'b1;  p0_we <= 1'b0;  st <= B_RWAIT;
            end
            B_RWAIT:
                if (p0_done) begin
                    rdata_r <= p0_rdata;
                    if (!do_w) rej_r <= 1'b0;               // a read is never refused
                    cnt <= 2'd2;
                    st  <= B_ACK;
                end
            B_ACK:
                if (cnt != {CW{1'b0}}) cnt <= cnt - 1'b1;
                else begin
                    wack <= w_tgl;
                    rack <= r_tgl;
                    st   <= B_IDLE;
                end
            default: st <= B_IDLE;
        endcase
    end
endmodule
