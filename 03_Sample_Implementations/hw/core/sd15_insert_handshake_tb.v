// ============================================================================
//  sd15_insert_handshake_tb.v — minimal reproduction of discrepancy SD-15 (the
//  insertion handshake) for the PTSG-Core office. No Formation, no WPMS: one
//  Core, a four-word program, one insertion request.
//  License: MIT (Layer 3 sample). Evidence class of every result: RTL-SIM.
// ----------------------------------------------------------------------------
//  Core Layer 1 Ch.5 §5.9: `insert_req` is a level held until `insert_ack`;
//  "External logic should deassert insert_req no earlier than the clock in
//  which it sees insert_ack". `insert_ack` is a registered pulse, high in the
//  clock AFTER the Core accepted the request. This bench asks what happens
//  when the requester follows the text with an ordinary registered drop.
//
//  Parameters (iverilog -P):
//    SCENE 0  the Core runs a NOP loop (S_RUN): the request is honoured at once;
//          1  the Core waits in a bare Stay: the request is deferred to timeup;
//          2  the Core is inside a Stay window (Stay Set … Prog End · Stay), as
//             in WPMS: deferred to timeup (C3-F20).
//    DROP  0  registered drop: `req` falls at the clock edge that samples
//             insert_ack = 1 — the text's literal reading;
//          1  withdrawn within the ack clock: insert_req = req & ~insert_ack
//             (what the Core's own conformance bench does in T5a/T23, and the
//             WPMS Formation's workaround, wpms_formation.v RH002).
//    STACK 0  stack_ack tied 0 (WPMS ties it: no external stack);
//          1  a one-clock external stack responder.
//  The insertion target holds a foreground Prog End: the Core must HALT there
//  (C3-F23 -> C3-F24, error_flag). Expected by the text in every case:
//  one insert_ack, no stack push, HALT at the target.
//
//  Compile with EITHER the frozen PTSG-Core source (read, never edited) or the
//  RH031p copy — both define module ptsg_core; the bench leaves the copy's
//  stay_value pin unconnected (tri0: Stays as written). See run_sd15.sh.
//  Plusarg +vcd=<file> dumps the handshake signals.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SD-15 bug report to the
//                                          Core's office, architect's ruling 2026-09-29).
// ============================================================================
`timescale 1ns/1ps
module sd15_insert_handshake_tb;
    parameter integer SCENE = 0;
    parameter integer DROP  = 0;
    parameter integer STACK = 0;
    localparam [11:0] TARGET = 12'd10;

    reg clk = 0, rst = 1;
    always #5 clk = ~clk;

    wire [11:0] state_number; wire [15:0] timing_signals;
    wire ext_op_valid; wire [3:0] ext_op_subopcode; wire [7:0] ext_op_sub_operand;
    wire [15:0] ext_op_data;
    wire stack_push_req, stack_pop_req; wire [40:0] stack_wdata;
    wire insert_ack; wire [15:0] loop_counter; wire loop_cnt_match;
    wire [11:0] stay_counter; wire stay_cnt_match;
    wire [15:0] prescaler_counter; wire prescaler_match; wire [15:0] prescaler_output;
    wire indirect_req; wire [1:0] indirect_purpose; wire error_flag;

    // ---- the requester ---------------------------------------------------------
    reg fire = 1'b0;                          // one-clock pulse from the stimulus
    reg req  = 1'b0;
    always @(posedge clk)
        if (rst)             req <= 1'b0;
        else if (fire)       req <= 1'b1;
        else if (insert_ack) req <= 1'b0;     // falls at the edge that samples the ack
    wire insert_req = (DROP == 0) ? req : (req & ~insert_ack);

    // ---- optional external stack: one-clock turnaround ---------------------------
    reg        stack_ack = 1'b0;
    reg [40:0] stk_mem [0:7];
    reg [3:0]  stk_sp = 4'd0;
    reg [40:0] stack_rdata = 41'd0;
    always @(posedge clk)
        if (rst) begin
            stack_ack <= 1'b0; stk_sp <= 4'd0;
        end else begin
            stack_ack <= 1'b0;
            if (STACK != 0 && stack_push_req && !stack_ack) begin
                stk_mem[stk_sp] <= stack_wdata; stk_sp <= stk_sp + 4'd1; stack_ack <= 1'b1;
            end else if (STACK != 0 && stack_pop_req && !stack_ack) begin
                stack_rdata <= stk_mem[stk_sp - 4'd1]; stk_sp <= stk_sp - 4'd1; stack_ack <= 1'b1;
            end
        end

    ptsg_core #(.IMEM_DEPTH(32), .PRESCALE(1), .IMEM_VENDOR("SIM"), .INIT_FILE("")) dut (
        .clk(clk), .rst(rst), .condition(1'b0),
        .state_number(state_number), .timing_signals(timing_signals),
        .ext_op_valid(ext_op_valid), .ext_op_subopcode(ext_op_subopcode),
        .ext_op_sub_operand(ext_op_sub_operand), .ext_op_data(ext_op_data), .ext_op_ready(1'b1),
        .stack_push_req(stack_push_req), .stack_pop_req(stack_pop_req),
        .stack_wdata(stack_wdata), .stack_rdata(stack_rdata), .stack_ack(stack_ack),
        .insert_req(insert_req), .insert_target(TARGET), .insert_ack(insert_ack),
        .loop_counter(loop_counter), .loop_cnt_match(loop_cnt_match),
        .stay_counter(stay_counter), .stay_cnt_match(stay_cnt_match),
        .prescaler_counter(prescaler_counter), .prescaler_match(prescaler_match),
        .prescaler_output(prescaler_output),
        .indirect_req(indirect_req), .indirect_purpose(indirect_purpose),
        .indirect_data(12'd0), .indirect_ready(1'b0), .error_flag(error_flag));

    // ---- instruction words (D0-D3 opcode, D4-D15 operand, D16-D31 timing signals) ----
    function [31:0] W_NOP;     input d; W_NOP     = 32'h0000_0700; endfunction
    function [31:0] W_STAYSET; input d; W_STAYSET = 32'h0000_0200; endfunction
    function [31:0] W_PROGEND; input d; W_PROGEND = 32'h0000_0600; endfunction
    function [31:0] W_STAY;    input [11:0] n; W_STAY = {16'h0000, n, 4'd1}; endfunction
    function [31:0] W_JUMP;    input [11:0] a; W_JUMP = {16'h0000, a, 4'd3}; endfunction

    // ---- observation -------------------------------------------------------------
    integer acks = 0, pushes = 0, clk_n = 0, fire_clk = 0, ack_clk = -1;
    reg     push_prev = 1'b0;
    always @(posedge clk) if (!rst) begin
        clk_n <= clk_n + 1;
        if (insert_ack) begin acks <= acks + 1; if (ack_clk < 0) ack_clk <= clk_n; end
        if (stack_push_req && !push_prev) pushes <= pushes + 1;
        push_prev <= stack_push_req;
    end

    function [8*6-1:0] fsm_name; input [2:0] f;
        case (f) 3'd0: fsm_name = "S_RUN "; 3'd1: fsm_name = "S_WAIT"; 3'd2: fsm_name = "S_IND ";
                 3'd3: fsm_name = "S_PUSH"; 3'd4: fsm_name = "S_POP "; 3'd5: fsm_name = "S_HALT";
                 default: fsm_name = "?     "; endcase
    endfunction

    // +vcd=<file>: dump the handshake (ports, plus the Core's FSM as a white-box probe)
    reg [1023:0] vcdfile;
    initial if ($value$plusargs("vcd=%s", vcdfile)) begin
        $dumpfile(vcdfile);
        $dumpvars(0, clk, rst, req, insert_req, insert_ack, state_number, stack_push_req, stack_ack,
                  stay_cnt_match, error_flag, dut.fsm);
    end

    integer j;
    initial begin
        for (j = 0; j < 32; j = j + 1) dut.ptsg_imem.g_sim.mem[j] = W_NOP(0);
        case (SCENE)
        0: begin                                   // NOP loop in S_RUN
            dut.ptsg_imem.g_sim.mem[0] = W_NOP(0);
            dut.ptsg_imem.g_sim.mem[1] = W_NOP(0);
            dut.ptsg_imem.g_sim.mem[2] = W_JUMP(12'd1);
        end
        1: begin                                   // bare Stay loop
            dut.ptsg_imem.g_sim.mem[0] = W_NOP(0);
            dut.ptsg_imem.g_sim.mem[1] = W_STAY(12'd40);
            dut.ptsg_imem.g_sim.mem[2] = W_JUMP(12'd1);
        end
        default: begin                             // windowed Stay (the WPMS packet shape)
            dut.ptsg_imem.g_sim.mem[0] = W_NOP(0);
            dut.ptsg_imem.g_sim.mem[1] = W_STAYSET(0);
            dut.ptsg_imem.g_sim.mem[2] = W_NOP(0);     // background window body
            dut.ptsg_imem.g_sim.mem[3] = W_PROGEND(0); // window closes
            dut.ptsg_imem.g_sim.mem[4] = W_STAY(12'd40);
            dut.ptsg_imem.g_sim.mem[5] = W_JUMP(12'd1);
        end
        endcase
        dut.ptsg_imem.g_sim.mem[TARGET] = W_PROGEND(0);  // foreground Prog End: HALT (C3-F23 -> C3-F24)

        repeat (3) @(posedge clk);
        rst <= 1'b0;
        repeat (SCENE == 0 ? 7 : 12) @(posedge clk);    // S_RUN: mid-loop; 1, 2: inside the Stay
        fire <= 1'b1; fire_clk = clk_n;
        @(posedge clk); fire <= 1'b0;
        repeat (200) @(posedge clk);
        #1;
        if (SCENE == 0)      $write("SD15 scene=S_RUN     ");
        else if (SCENE == 1) $write("SD15 scene=bare-Stay ");
        else                 $write("SD15 scene=window    ");
        if (DROP == 0)       $write("drop=registered   ");
        else                 $write("drop=in-ack-clock ");
        if (STACK == 0)      $write("stack=none   : ");
        else                 $write("stack=1-clock: ");
        $write("first ack %0d clocks after the request; insert_ack pulses=%0d, stack pushes=%0d, final %s at 0x%03h, error_flag=%0d -> ",
               ack_clk - fire_clk, acks, pushes, fsm_name(dut.fsm), state_number, error_flag);
        if (acks == 1 && pushes == 0 && dut.fsm == 3'd5 && state_number == TARGET)
            $display("AS THE TEXT (one take, HALT at the target)");
        else
            $display("DOUBLE TAKE (the request was accepted again in the ack clock)");
        $finish;
    end
endmodule
