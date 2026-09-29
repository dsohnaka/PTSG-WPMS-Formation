// ============================================================================
//  wpms_adv7513_cfg.v — the ADV7513 configurator (customer Ch.4 §4.6.2, C4-D1)
//  ADV7513 設定器
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  A small FSM and an I2C master (100 kHz, open drain, clock stretching
//  honoured). After power-up (POWERUP_CLKS) it polls the transmitter's HPD
//  state (register 0x42 bit 6) every POLL_CLKS; whenever HPD is high and the
//  table has not been written since HPD last rose, it writes the table below
//  (Ch.4 §4.6.2: "after power-up and on hot-plug"). Main map at I2C address
//  0x72 (write) / 0x73 (read) [board fact, to be confirmed against the Terasic
//  schematic in Phase 6].
//
//  THE TABLE — intent (Ch.4 §4.6.2): power up; HDMI mode (not DVI); 24-bit RGB
//  4:4:4, separate syncs, 720p60 in the AVI InfoFrame; I2S, 24 bit, 2 ch,
//  48 kHz, N = 6144 with CTS from the transmitter; audio InfoFrame 2-ch L-PCM.
//  Each entry's basis is marked: [PG] the fixed/documented values confirmed
//  from the ADV7513 Programming Guide's published summaries on 2026-09-29;
//  [R] recalled from the guide's register map, NOT verified against the
//  document in this session (its host was blocked by the session's network
//  policy) — every [R] entry is to be confirmed on silicon in Phase 6 (read-back
//  of the register, HPD 0x42, detected VIC 0x3E). Regenerated from the
//  documentation, not copied from any framework (Ch.4 §4.2.1, C4-D11).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_adv7513_cfg #(
    parameter integer CLK_HZ       = 50_000_000,
    parameter integer I2C_HZ       = 100_000,
    parameter integer POWERUP_CLKS = 10_000_000,          // 200 ms at 50 MHz
    parameter integer POLL_CLKS    = 5_000_000,           // 100 ms
    parameter [7:0]   DEV          = 8'h72
) (
    input  wire       clk,
    input  wire       rst,
    output wire       scl_oe,                   // 1: pull SCL low
    output wire       sda_oe,                   // 1: pull SDA low
    input  wire       scl_in,
    input  wire       sda_in,
    output reg        hpd,                      // 0x42[6], last read
    output reg        done,                     // table written since HPD rose
    output reg        nack,                     // sticky: a byte was not acknowledged
    output reg  [7:0] tables                    // tables written (tap)
);
    // ---- the table ------------------------------------------------------------------------
    localparam integer NTAB = 29;
    function [15:0] tab;                        // {register, value}
        input [5:0] i;
        begin
            case (i)
            6'd0:  tab = 16'h41_10;   // [PG] 0x41[6] = 0: power up (while HPD is high)
            6'd1:  tab = 16'h98_03;   // [PG] fixed
            6'd2:  tab = 16'h9A_E0;   // [PG] fixed: [7:5] = 111
            6'd3:  tab = 16'h9C_30;   // [PG] fixed
            6'd4:  tab = 16'h9D_61;   // [PG] fixed: [1:0] = 01
            6'd5:  tab = 16'hA2_A4;   // [PG] fixed
            6'd6:  tab = 16'hA3_A4;   // [PG] fixed
            6'd7:  tab = 16'hE0_D0;   // [PG] fixed
            6'd8:  tab = 16'hF9_00;   // [PG] fixed
            6'd9:  tab = 16'h15_20;   // [PG] [7:4] I2S sampling frequency = 48 kHz (0010); [R] [3:0] input ID 0: 24-bit RGB 4:4:4, separate syncs
            6'd10: tab = 16'h16_30;   // [R] output 4:4:4, 8 bit per colour, input style 0, RGB
            6'd11: tab = 16'h17_02;   // [R] [1] aspect 16:9 (VIC 4)
            6'd12: tab = 16'h18_46;   // [R] [7] = 0: colour-space converter off
            6'd13: tab = 16'hAF_16;   // [R] [1] = 1: HDMI mode (not DVI), other bits at their defaults
            6'd14: tab = 16'h40_80;   // [R] general control packet enable
            6'd15: tab = 16'h55_00;   // [R] AVI InfoFrame: RGB
            6'd16: tab = 16'h56_28;   // [R] AVI InfoFrame: picture 16:9, active format = picture
            6'd17: tab = 16'h01_00;   // [PG] N = 6144 = 0x001800 (Ch.4 §4.6.2) ...
            6'd18: tab = 16'h02_18;   // [PG] ...
            6'd19: tab = 16'h03_00;   // [PG] ...
            6'd20: tab = 16'h0A_01;   // [PG] [6:4] = 000: I2S; [R] [7] = 0 automatic CTS, [1:0] = 01 MCLK = 256 Fs
            6'd21: tab = 16'h0C_04;   // [PG] [5:2] = 0001: I2S0 enabled, [1:0] = 00: standard I2S
            6'd22: tab = 16'h0D_18;   // [R] I2S bit width 24 (used by right-justified mode only; harmless)
            6'd23: tab = 16'h14_0B;   // [PG] [3:0] word length; [R] 1011 = 24 bit (IEC 60958 code)
            6'd24: tab = 16'h73_01;   // [R] audio InfoFrame channel count: 2
            6'd25: tab = 16'h76_00;   // [R] speaker allocation: FL, FR
            6'd26: tab = 16'hBA_60;   // [R] input clock delay: none
            6'd27: tab = 16'h94_C0;   // [R] interrupts: HPD, monitor sense
            default: tab = 16'h96_C0; // [R] clear the HPD / monitor-sense interrupts
            endcase
        end
    endfunction

    // ---- bit engine: quarter-period ticks, open drain -------------------------------------
    localparam integer QTR = CLK_HZ / (4 * I2C_HZ);
    reg  scl_o = 1'b1, sda_o = 1'b1;                        // 1 = released (high)
    assign scl_oe = ~scl_o;
    assign sda_oe = ~sda_o;
    reg  [15:0] qcnt;
    wire        qtick = (qcnt == QTR - 1);

    // op codes of the micro-sequence
    localparam [2:0] O_START = 3'd0, O_BYTE = 3'd1, O_READ = 3'd2, O_STOP = 3'd3, O_END = 3'd4;
    reg  [2:0]  op;         // current op
    reg  [1:0]  q;          // quarter within the bit
    reg  [3:0]  bitn;       // 0..8 (8 = the acknowledge bit)
    reg  [7:0]  shreg, rdata;
    reg  [2:0]  step;       // index into the transaction's ops
    reg         is_read;    // transaction: read 0x42 (else: write tab[idx])
    reg  [5:0]  idx;
    reg  [7:0]  b_reg, b_dat;
    reg         busy;

    // the transaction's ops: write = S, dev, reg, data, P ; read = S, dev, reg, S, dev|1, R, P
    function [10:0] op_of;       // {op, byte}
        input rd; input [2:0] s; input [7:0] rg; input [7:0] dt;
        begin
            if (!rd)
                case (s)
                    3'd0: op_of = {O_START, 8'h00};  3'd1: op_of = {O_BYTE, DEV};  3'd2: op_of = {O_BYTE, rg};
                    3'd3: op_of = {O_BYTE, dt};      3'd4: op_of = {O_STOP, 8'h00}; default: op_of = {O_END, 8'h00};
                endcase
            else
                case (s)
                    3'd0: op_of = {O_START, 8'h00};  3'd1: op_of = {O_BYTE, DEV};        3'd2: op_of = {O_BYTE, rg};
                    3'd3: op_of = {O_START, 8'h00};  3'd4: op_of = {O_BYTE, DEV | 8'h01}; 3'd5: op_of = {O_READ, 8'h00};
                    3'd6: op_of = {O_STOP, 8'h00};   default: op_of = {O_END, 8'h00};
                endcase
        end
    endfunction

    // ---- top FSM ------------------------------------------------------------------------------
    localparam [1:0] T_WAIT = 2'd0, T_POLL = 2'd1, T_WRITE = 2'd2;
    reg  [1:0]  top;
    reg  [31:0] wait_cnt;
    reg         start_tx;                                    // pulse: begin a transaction

    always @(posedge clk) begin
        if (rst) begin
            top <= T_WAIT;  wait_cnt <= POWERUP_CLKS;  start_tx <= 1'b0;
            hpd <= 1'b0;  done <= 1'b0;  nack <= 1'b0;  tables <= 8'd0;
            idx <= 6'd0;  is_read <= 1'b1;  b_reg <= 8'h42;  b_dat <= 8'h00;
        end else begin
            start_tx <= 1'b0;
            case (top)
            T_WAIT: if (wait_cnt != 0) wait_cnt <= wait_cnt - 1;
                    else if (!busy && !start_tx) begin
                        top <= T_POLL;  is_read <= 1'b1;  b_reg <= 8'h42;  start_tx <= 1'b1;
                    end
            T_POLL: if (!busy && !start_tx) begin                 // the read of 0x42 is over
                        hpd <= rdata[6];
                        if (!rdata[6]) done <= 1'b0;
                        if (rdata[6] && !done) begin
                            top <= T_WRITE;  idx <= 6'd0;  is_read <= 1'b0;
                            {b_reg, b_dat} <= tab(6'd0);  start_tx <= 1'b1;
                        end else begin
                            top <= T_WAIT;  wait_cnt <= POLL_CLKS;
                        end
                    end
            T_WRITE: if (!busy && !start_tx) begin
                        if (idx == NTAB - 1) begin
                            done <= 1'b1;  tables <= tables + 8'd1;
                            top <= T_WAIT;  wait_cnt <= POLL_CLKS;
                        end else begin
                            idx <= idx + 6'd1;  {b_reg, b_dat} <= tab(idx + 6'd1);  start_tx <= 1'b1;
                        end
                    end
            default: top <= T_WAIT;
            endcase
        end
    end

    // ---- transaction engine --------------------------------------------------------------------
    wire [10:0] cur = op_of(is_read, step, b_reg, b_dat);
    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0;  scl_o <= 1'b1;  sda_o <= 1'b1;  qcnt <= 16'd0;
            op <= O_END;  q <= 2'd0;  bitn <= 4'd0;  step <= 3'd0;  rdata <= 8'd0;  shreg <= 8'd0;
        end else if (start_tx) begin
            busy <= 1'b1;  step <= 3'd0;  q <= 2'd0;  bitn <= 4'd0;  qcnt <= 16'd0;
            op <= O_START;
        end else if (busy) begin
            // clock stretching: while SCL is released but held low by the slave, time stands still
            if (scl_o && !scl_in) qcnt <= 16'd0;
            else qcnt <= qtick ? 16'd0 : qcnt + 16'd1;
            if (qtick && !(scl_o && !scl_in)) begin
                case (op)
                O_START: case (q)                               // SDA falls while SCL is high
                    2'd0: begin scl_o <= 1'b0; sda_o <= 1'b1; q <= 2'd1; end
                    2'd1: begin scl_o <= 1'b1; q <= 2'd2; end
                    2'd2: begin sda_o <= 1'b0; q <= 2'd3; end
                    default: begin scl_o <= 1'b0; q <= 2'd0; step <= step + 3'd1;
                                   {op, shreg} <= op_of(is_read, step + 3'd1, b_reg, b_dat); bitn <= 4'd0; end
                    endcase
                O_BYTE, O_READ: case (q)
                    2'd0: begin
                              scl_o <= 1'b0;
                              if (bitn < 4'd8) sda_o <= (op == O_BYTE) ? shreg[7] : 1'b1;
                              else             sda_o <= (op == O_BYTE) ? 1'b1 : 1'b1;  // ack: slave drives / master NACKs
                              q <= 2'd1;
                          end
                    2'd1: q <= 2'd2;
                    2'd2: begin scl_o <= 1'b1; q <= 2'd3; end
                    default: begin
                              q <= 2'd0;
                              if (bitn < 4'd8) begin
                                  if (op == O_BYTE) shreg <= {shreg[6:0], 1'b0};
                                  else              rdata <= {rdata[6:0], sda_in};
                                  bitn <= bitn + 4'd1;
                              end else begin
                                  if (op == O_BYTE && sda_in) nack <= 1'b1;   // not acknowledged
                                  step <= step + 3'd1;
                                  {op, shreg} <= op_of(is_read, step + 3'd1, b_reg, b_dat);
                                  bitn <= 4'd0;
                              end
                          end
                    endcase
                O_STOP: case (q)                                 // SDA rises while SCL is high
                    2'd0: begin scl_o <= 1'b0; sda_o <= 1'b0; q <= 2'd1; end
                    2'd1: begin scl_o <= 1'b1; q <= 2'd2; end
                    2'd2: begin sda_o <= 1'b1; q <= 2'd3; end
                    default: begin q <= 2'd0; busy <= 1'b0; op <= O_END; end
                    endcase
                default: busy <= 1'b0;
                endcase
            end
        end
    end
endmodule
