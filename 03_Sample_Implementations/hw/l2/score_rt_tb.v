// ============================================================================
//  score_rt_tb.v — round trip of a score_as.py image through the Core copy
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  Loads a score image (.hex from hw/tools/score_as.py) into ptsg_core_rh031p.v
//  (IMEM_DEPTH 4096, PRESCALE 1, stay_value tied 0 so every Stay keeps its
//  literal) and logs what the Core does with it, for hw/tools/score_rt.py:
//    "S cyc state tsig fsm"   whenever state_number changes
//    "O cyc state word"       every external-operation issue, the word rebuilt
//                             from the bus ({data, sub_operand, subopcode, 0})
//    "H cyc state"            a stack push request (auto-save spilled; S_PUSH)
//    "Z cyc state"            the Core raised error_flag (S_HALT)
//  The Condition input is the profile's lane mux (Deliverable 3 §4): TS_CSEL =
//  timing_signals[2:1] selects STROBE (a one-clock pulse every STROBE_T clocks),
//  NONEMPTY (P > 0) or MORE (packets begun since the strobe < P), where a packet
//  "begins" when state_number enters one of the score's PKT labels (passed as
//  +pkt0=..+pkt7=). A toy stand-in for the Phase 3 sequencer — nothing more.
//  Plusargs: +P=<n> +clocks=<n> +strobe=<n> +pkt0=<hex> .. +pkt7=<hex>
//  Parameter HEX: the image (set with iverilog -P).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
// ============================================================================
`timescale 1ns/1ps
module score_rt_tb;
    parameter HEX = "score.hex";
    reg clk = 0, rst = 1;
    always #5 clk = ~clk;

    wire [11:0] state_number;
    wire [15:0] timing_signals;
    wire        ext_op_valid;
    wire [3:0]  ext_op_subopcode;
    wire [7:0]  ext_op_sub_operand;
    wire [15:0] ext_op_data;
    wire        stack_push_req, stack_pop_req, insert_ack, loop_cnt_match, stay_cnt_match;
    wire [40:0] stack_wdata;
    wire [15:0] loop_counter, prescaler_counter, prescaler_output;
    wire [11:0] stay_counter;
    wire        prescaler_match, indirect_req, error_flag;
    wire [1:0]  indirect_purpose;
    reg         condition;

    ptsg_core #(.IMEM_DEPTH(4096), .PRESCALE(1), .IMEM_VENDOR("SIM"), .INIT_FILE(HEX)) core (
        .clk(clk), .rst(rst), .condition(condition),
        .state_number(state_number), .timing_signals(timing_signals),
        .ext_op_valid(ext_op_valid), .ext_op_subopcode(ext_op_subopcode),
        .ext_op_sub_operand(ext_op_sub_operand), .ext_op_data(ext_op_data), .ext_op_ready(1'b1),
        .stack_push_req(stack_push_req), .stack_pop_req(stack_pop_req),
        .stack_wdata(stack_wdata), .stack_rdata(41'd0), .stack_ack(1'b0),
        .insert_req(1'b0), .insert_target(12'd0), .insert_ack(insert_ack),
        .loop_counter(loop_counter), .loop_cnt_match(loop_cnt_match),
        .stay_counter(stay_counter), .stay_cnt_match(stay_cnt_match),
        .prescaler_counter(prescaler_counter), .prescaler_match(prescaler_match),
        .prescaler_value(16'd0), .prescaler_output(prescaler_output),
        .stay_value(12'd0),
        .indirect_req(indirect_req), .indirect_purpose(indirect_purpose),
        .indirect_data(12'd0), .indirect_ready(1'b0),
        .error_flag(error_flag));

    integer P = 0, clocks = 400, strobe_t = 150, cyc = 0, begun = 0, k, pk;
    integer pkt [0:7];
    reg strobe = 0;
    reg [11:0] last_state = 12'hFFF;
    reg push_seen = 0, halt_seen = 0;
    integer fout;

    always @* case (timing_signals[2:1])
        2'd0:    condition = strobe;
        2'd1:    condition = (P > 0);
        2'd2:    condition = (begun < P);
        default: condition = 1'b0;
    endcase

    function is_pkt; input [11:0] a; integer j; begin
        is_pkt = 1'b0;
        for (j = 0; j < 8; j = j + 1) if (pkt[j] == a) is_pkt = 1'b1;
    end endfunction

    always @(posedge clk) if (!rst) begin
        cyc <= cyc + 1;
        strobe <= ((cyc + 1) % strobe_t == 0);
        if (strobe) begun = 0;                                   // the take-set / sweep restart
        else if (state_number != last_state && is_pkt(state_number)) begun = begun + 1;
        if (state_number != last_state)
            $fwrite(fout, "S %0d %03h %04h %0d\n", cyc, state_number, timing_signals, core.fsm);
        last_state <= state_number;
        if (ext_op_valid)
            $fwrite(fout, "O %0d %03h %08h\n", cyc, state_number,
                    {ext_op_data, ext_op_sub_operand, ext_op_subopcode, 4'd0});
        if (stack_push_req && !push_seen) begin $fwrite(fout, "H %0d %03h\n", cyc, state_number); push_seen <= 1; end
        if (error_flag && !halt_seen) begin $fwrite(fout, "Z %0d %03h\n", cyc, state_number); halt_seen <= 1; end
    end

    reg [8*512-1:0] out_path;
    initial begin
        if (!$value$plusargs("out=%s", out_path)) out_path = "score_rt.txt";
        if (!$value$plusargs("P=%d", P)) P = 0;
        if (!$value$plusargs("clocks=%d", clocks)) clocks = 400;
        if (!$value$plusargs("strobe=%d", strobe_t)) strobe_t = 150;
        if (!$value$plusargs("pkt0=%h", pk)) pk = -1; pkt[0] = pk;
        if (!$value$plusargs("pkt1=%h", pk)) pk = -1; pkt[1] = pk;
        if (!$value$plusargs("pkt2=%h", pk)) pk = -1; pkt[2] = pk;
        if (!$value$plusargs("pkt3=%h", pk)) pk = -1; pkt[3] = pk;
        if (!$value$plusargs("pkt4=%h", pk)) pk = -1; pkt[4] = pk;
        if (!$value$plusargs("pkt5=%h", pk)) pk = -1; pkt[5] = pk;
        if (!$value$plusargs("pkt6=%h", pk)) pk = -1; pkt[6] = pk;
        if (!$value$plusargs("pkt7=%h", pk)) pk = -1; pkt[7] = pk;
        fout = $fopen(out_path, "w");
        repeat (3) @(posedge clk);
        @(negedge clk) rst = 0;
        repeat (clocks) @(posedge clk);
        $fwrite(fout, "E %0d %03h %0d\n", cyc, state_number, core.fsm);
        $fclose(fout);
        $finish;
    end
endmodule
