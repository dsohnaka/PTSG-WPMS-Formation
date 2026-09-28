// ============================================================================
//  ptsg_core_sv_tb.v — stay_value regression for the RH031 (provisional) copy
//  of PTSG-Core: tests SV-0 … SV-7 of stay_value_reference_sketch.md §7.
//  License: MIT (Layer 3 sample). Evidence class of every result: RTL-SIM.
// ----------------------------------------------------------------------------
//  Two top-level modules; run_phase1.sh builds each with `iverilog -s <top>`.
//
//  ptsg_core_sv_tb   — SV-1 … SV-7 (+ SV-5b, supplementary) on the patched copy
//                      alone (module ptsg_core from ptsg_core_rh031p.v), at
//                      PRESCALE = 1 as WPMS runs it. The Core is form B (the
//                      pin is read in the Stay's execute clock). Two other
//                      sampling forms are built HERE, in the testbench only,
//                      by forcing the copy's internal stay_dur wire — never in
//                      the RTL:
//                        +define+SV_FORM_ANTIPATTERN : sketch §4, a raw-pin zero
//                           test beside a registered value (RH029-as-built
//                           copied to Stay). SV-4 must FAIL here (8192 clocks):
//                           that is the proof that the test bites.
//                        +define+SV_FORM_A : sketch §3, registered one clock
//                           ahead (the Tie C4-T5 alternative). Informative only.
//                      Plusargs: +only=<n> runs only SV-<n> (5b is 55);
//                      +sv4vcd=<file> dumps SV-4's signals (use with +only=4).
//
//  ptsg_core_sv0_tb  — SV-0: the frozen RH030 source (compiled under the name
//                      ptsg_core_rh030 by run_phase1.sh; the frozen file itself
//                      is never edited) and the copy with stay_value tied 0,
//                      run in lockstep; every output and every internal
//                      register is compared on every clock. Parameter PRESCALE
//                      (-P). Default: random structured programs with random
//                      Condition, insertion, indirect and stack traffic, and a
//                      stimulus count so that a quiet run cannot pass as a
//                      clean one. +scene4: the Live Session #1 Scene 4 program
//                      (Stay 1250 / Stay 1250 / Reset) at PRESCALE = 6250 with
//                      prescaler_value switched to 20 live, as on 2026-08-29.
//
//  The unchanged Core testbenches (A..G, T1..T34) are the rest of SV-0; the
//  run script diffs their logs and VCDs against the frozen source.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 1;
//                                          C4-F15..F17, C5-F4, C2-F3; sketch §7 SV-0..SV-7).
// ============================================================================
`timescale 1ns/1ps

// ============================================================================
//  SV-1 … SV-7 on the patched copy
// ============================================================================
module ptsg_core_sv_tb;
    localparam integer PRESCALE = 1;          // WPMS runs the Core at P = 1
    localparam integer DEPTH    = 64;
    localparam [2:0]   S_WAIT   = 3'd1;       // the Core's FSM encoding (white-box probe)

    reg clk = 0, rst = 1, condition = 0;
    wire [11:0] state_number; wire [15:0] timing_signals;
    wire ext_op_valid; wire [3:0] ext_op_subopcode; wire [7:0] ext_op_sub_operand;
    wire [15:0] ext_op_data;
    wire stack_push_req, stack_pop_req; wire [40:0] stack_wdata;
    wire insert_ack; wire [15:0] loop_counter; wire loop_cnt_match;
    wire [11:0] stay_counter; wire stay_cnt_match;
    wire [15:0] prescaler_counter; wire prescaler_match; wire [15:0] prescaler_output;
    wire indirect_req; wire [1:0] indirect_purpose; wire error_flag;

    // ---- the stay_value source: a plain pin, or a table keyed by state_number
    //      (Formation idiom (ii) of Core Ch.5 §5.12a, CHANGES item 7) -------
    reg  [11:0] pin = 12'd0;
    reg         lut_on = 1'b0;
    reg  [11:0] lut_a0 = 12'hFFF, lut_v0 = 12'd0, lut_a1 = 12'hFFF, lut_v1 = 12'd0;
    wire [11:0] lut = (state_number == lut_a0) ? lut_v0 :
                      (state_number == lut_a1) ? lut_v1 : 12'd0;
    wire [11:0] stay_value = lut_on ? lut : pin;

    ptsg_core #(.IMEM_DEPTH(DEPTH), .PRESCALE(PRESCALE),
                .IMEM_VENDOR("SIM"), .INIT_FILE("")) dut (
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
        .stay_value(stay_value),
        .indirect_req(indirect_req), .indirect_purpose(indirect_purpose),
        .indirect_data(12'd0), .indirect_ready(1'b0),
        .error_flag(error_flag));

    always #5 clk = ~clk;                     // 100 MHz
    integer cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    // ---- sampling forms built in the testbench only (never in the RTL) -----
    //  Icarus 12 evaluates the right-hand side of a procedural `force` once,
    //  so the force is re-issued whenever an operand changes; the value it
    //  holds at every clock edge is the form's combinational value.
`ifdef SV_FORM_ANTIPATTERN
    // sketch §4 — WRONG: raw-pin zero test beside a registered value.
    reg [11:0] stay_valueR_tb = 12'd0;
    always @(posedge clk) stay_valueR_tb <= dut.stay_value;
    always @(dut.stay_value or stay_valueR_tb or dut.stay_dur_lit)
        force dut.stay_dur = (dut.stay_value != 12'd0) ? {1'b0, stay_valueR_tb} : dut.stay_dur_lit;
    localparam FORM = "ANTI-PATTERN (sketch 4), forced in the testbench";
`elsif SV_FORM_A
    // sketch §3 — form A: registered one clock ahead, zero test on the same sample.
    reg [11:0] stay_valueR_tb = 12'd0;
    always @(posedge clk) stay_valueR_tb <= dut.stay_value;
    always @(stay_valueR_tb or dut.stay_dur_lit)
        force dut.stay_dur = (stay_valueR_tb != 12'd0) ? {1'b0, stay_valueR_tb} : dut.stay_dur_lit;
    localparam FORM = "FORM A (sketch 3), forced in the testbench (informative)";
`else
    localparam FORM = "FORM B (the RTL as written)";
`endif

    // ---- instruction constructors (Ch.2 §2.2: D0-D3 opcode, D4-D15 operand,
    //      D16-D31 timing signals) --------------------------------------------
    function [31:0] I_NOP;     input [15:0] ts; I_NOP     = {ts, 16'h0700}; endfunction
    function [31:0] I_STAYSET; input [15:0] ts; I_STAYSET = {ts, 16'h0200}; endfunction
    function [31:0] I_PROGEND; input [15:0] ts; I_PROGEND = {ts, 16'h0600}; endfunction
    function [31:0] I_STAY;    input [15:0] ts; input [11:0] n; I_STAY = {ts, n, 4'h1}; endfunction
    function [31:0] I_JUMP;    input [15:0] ts; input [11:0] a; I_JUMP = {ts, a, 4'h3}; endfunction

    // ---- helpers -----------------------------------------------------------
    integer j;
    task clear_imem; begin for (j = 0; j < DEPTH; j = j + 1) dut.ptsg_imem.g_sim.mem[j] = I_NOP(16'h0000); end endtask
    task hold_reset; begin
        rst = 1; lut_on = 0; pin = 12'd0; lut_a0 = 12'hFFF; lut_a1 = 12'hFFF;
        @(posedge clk); @(posedge clk); clear_imem;
    end endtask
    task release_reset; begin @(negedge clk); rst = 0; end endtask
    task step; begin @(posedge clk); #1; end endtask   // sample 1 ns after each edge

    // Measure the next whole visit to address a: leave any current visit,
    // wait for the entry, count the consecutive samples spent there.
    task visit; input [11:0] a; input integer max; output integer len;
        integer k; begin
            len = 0; k = 0;
            while (state_number === a && k < max) begin step; k = k + 1; end
            while (state_number !== a && k < max) begin step; k = k + 1; end
            while (state_number === a && len < max) begin len = len + 1; step; end
            if (k >= max) len = -1;
        end
    endtask
    // Period between two consecutive entries into address a.
    task period_of; input [11:0] a; input integer max; output integer per;
        integer k, t0; begin
            per = -1; k = 0;
            while (state_number === a && k < max) begin step; k = k + 1; end
            while (state_number !== a && k < max) begin step; k = k + 1; end
            t0 = cyc;
            while (state_number === a && k < max) begin step; k = k + 1; end
            while (state_number !== a && k < max) begin step; k = k + 1; end
            if (k < max) per = cyc - t0;
        end
    endtask

    integer fails = 0, passes = 0, only = 0;
    reg [15:0]      failmask = 16'd0;       // bit n = SV-n failed (bit 8 = SV-5b)
    reg [8*256-1:0] vcdname;
    task verdict; input integer id; input ok; begin
        if (ok) passes = passes + 1;
        else begin fails = fails + 1; failmask[id] = 1'b1; end
    end endtask
    function run_it; input integer n; run_it = (only == 0) || (only == n); endfunction

    // ---- the programs (addresses are the same in every test that shares one)
    // P1: bare Stay loop — 0 NOP | 1 NOP ts1 | 2 Stay (op) ts2 | 3 Jump 1 ts4
    task load_bare; input [11:0] op; begin
        dut.ptsg_imem.g_sim.mem[0] = I_NOP(16'h0000);
        dut.ptsg_imem.g_sim.mem[1] = I_NOP(16'h0001);
        dut.ptsg_imem.g_sim.mem[2] = I_STAY(16'h0002, op);
        dut.ptsg_imem.g_sim.mem[3] = I_JUMP(16'h0004, 12'd1);
    end endtask

    integer len, len2, per, t_ss, t_res, k, ns_wait, kerr, expd;
    initial begin
        if (!$value$plusargs("only=%d", only)) only = 0;
        $display("ptsg_core_sv_tb — stay_value regression, PRESCALE=%0d, build: %0s", PRESCALE, FORM);

        // ================================================================
        // SV-1 — bare Stay, pin = N, P = 1: the Stay lasts exactly N clocks.
        //        (C4-F15: pin != 0 supersedes the operand; operand here = 5)
        // ================================================================
        if (run_it(1)) begin : sv1
            integer idx, ok; reg [11:0] Ns [0:5];
            Ns[0]=2; Ns[1]=3; Ns[2]=7; Ns[3]=100; Ns[4]=2048; Ns[5]=4095;
            ok = 1;
            for (idx = 0; idx < 6; idx = idx + 1) begin
                hold_reset; load_bare(12'd5); pin = Ns[idx]; release_reset;
                visit(12'd2, 20000, len);        // first visit
                visit(12'd2, 20000, len);        // steady state
                period_of(12'd1, 20000, per);
                $display("  SV-1 pin=%0d: Stay lasted %0d clocks (expected %0d); loop period %0d (expected %0d)",
                         Ns[idx], len, Ns[idx], per, Ns[idx] + 2);
                if (len != Ns[idx] || per != Ns[idx] + 2) ok = 0;
            end
            $display("%s SV-1: bare Stay with pin = N lasts N clocks (operand 5 superseded)", ok ? "PASS" : "FAIL");
            verdict(1, ok);
        end

        // ================================================================
        // SV-2 — pin = 1, P = 1: one clock, like an FG NOP (RH028 same-clock
        //        bare timeup reached through the pin).
        // ================================================================
        if (run_it(2)) begin
            hold_reset; load_bare(12'd5); pin = 12'd1; release_reset;
            visit(12'd2, 2000, len); visit(12'd2, 2000, len);
            period_of(12'd1, 2000, per);
            $display("%s SV-2: pin = 1 -> Stay lasted %0d clock (expected 1); loop period %0d (expected 3, as ptsg_core_tb F1)",
                     (len == 1 && per == 3) ? "PASS" : "FAIL", len, per);
            verdict(2, len == 1 && per == 3);
        end

        // ================================================================
        // SV-3 — pin N1 -> N2 during a Stay: the Stay in progress keeps N1
        //        (read once at execute, held in stay_target — C4-F16); the
        //        next Stay takes N2.
        // ================================================================
        if (run_it(3)) begin
            hold_reset; load_bare(12'd5); pin = 12'd20; release_reset;
            visit(12'd2, 2000, len);                         // settle
            while (state_number !== 12'd2) step;             // enter a Stay
            len = 0;
            while (state_number === 12'd2) begin
                len = len + 1;
                if (len == 5) begin @(negedge clk); pin = 12'd9; end  // change mid-wait
                step;
            end
            visit(12'd2, 2000, len2);
            $display("%s SV-3: pin 20 -> 9 at clock 5 of a Stay: that Stay lasted %0d (expected 20), the next %0d (expected 9)",
                     (len == 20 && len2 == 9) ? "PASS" : "FAIL", len, len2);
            verdict(3, len == 20 && len2 == 9);
        end

        // ================================================================
        // SV-4 — 0 -> N in the Stay's execute clock (form B stimulus): the pin
        //        is a table keyed by state_number, so it reads 0 in the clock
        //        before the Stay and N = 37 from the execute clock on. That
        //        Stay must last N. The anti-pattern latches 0 and runs 8192.
        // ================================================================
        if (run_it(4)) begin : sv4
            reg [11:0] pin_before, at_exec;
            hold_reset; load_bare(12'd5);
            lut_on = 1; lut_a0 = 12'd2; lut_v0 = 12'd37;
            if ($value$plusargs("sv4vcd=%s", vcdname)) begin
                $dumpfile(vcdname);
                $dumpvars(0, clk, rst, state_number, timing_signals, stay_value, stay_counter,
                          stay_cnt_match, dut.stay_dur, dut.stay_target, dut.stay_cnt, dut.fsm);
            end
            release_reset;
            while (state_number !== 12'd1) step;             // the clock before the Stay
            pin_before = stay_value;
            step; at_exec = stay_value;                      // the Stay's execute clock
            len = 1;
            while (state_number === 12'd2 && len < 20000) begin step; if (state_number === 12'd2) len = len + 1; end
            $display("%s SV-4: pin %0d -> %0d in the execute clock: that Stay lasted %0d clocks (expected 37; the anti-pattern gives 8192)",
                     (pin_before == 0 && at_exec == 37 && len == 37) ? "PASS" : "FAIL", pin_before, at_exec, len);
            verdict(4, pin_before == 0 && at_exec == 37 && len == 37);
        end

        // ================================================================
        // SV-5 — windowed Stay handed a pin below the count its window has
        //        already reached: timeup on the first tick in S_WAIT (RH028
        //        >=, C4-F17). Program: 0 NOP | 1 Stay Set | 2..6 BG NOP x5 |
        //        7 Stay 100 | 8 NOP ts 0x20 | 9 Jump 9. At the Stay's execute
        //        clock the counter reaches 7; pin = 3.
        //        Contrast (pin silent): Stay Set -> resume = the operand, 100
        //        clocks (C4-F10 grid anchoring).
        // ================================================================
        if (run_it(5)) begin : sv5
            integer ok_a, ok_b;
            for (k = 0; k < 2; k = k + 1) begin
                hold_reset;
                dut.ptsg_imem.g_sim.mem[0] = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[1] = I_STAYSET(16'h0010);
                for (j = 2; j <= 6; j = j + 1) dut.ptsg_imem.g_sim.mem[j] = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[7] = I_STAY(16'h0010, 12'd100);
                dut.ptsg_imem.g_sim.mem[8] = I_NOP(16'h0020);
                dut.ptsg_imem.g_sim.mem[9] = I_JUMP(16'h0020, 12'd9);
                pin = (k == 0) ? 12'd3 : 12'd0;
                release_reset;
                while (state_number !== 12'd1) step; t_ss = cyc;
                while (state_number !== 12'd7) step;
                len = 0; ns_wait = 0;
                while (state_number === 12'd7) begin
                    len = len + 1; if (dut.fsm == S_WAIT) ns_wait = ns_wait + 1; step;
                end
                t_res = cyc;
                if (k == 0) begin
                    ok_a = (len == 2 && ns_wait == 1 && state_number == 12'd8);
                    $display("  SV-5 pin=3 (< elapsed 7): Stay visible %0d clocks, %0d S_WAIT clock (expected 2 and 1); Stay Set -> resume %0d clocks",
                             len, ns_wait, t_res - t_ss);
                end else begin
                    ok_b = (len == 94 && (t_res - t_ss) == 100);
                    $display("  SV-5 contrast, pin silent: operand 100 -> Stay Set -> resume %0d clocks (expected 100), Stay visible %0d (expected 94)",
                             t_res - t_ss, len);
                end
            end
            $display("%s SV-5: windowed Stay, pin below the elapsed count -> timeup on the first S_WAIT tick", (ok_a && ok_b) ? "PASS" : "FAIL");
            verdict(5, ok_a && ok_b);
        end

        // ================================================================
        // SV-5b (supplementary, not in sketch §7) — the WPMS packet shape:
        //        1 Stay Set | 2..26 25 BG NOPs (the packet window's length) |
        //        27 Prog End | 28 Jump 1 (queued) | 29 Stay 32, pin = N.
        //        Stay Set -> next Stay Set must be exactly N, with K running
        //        0 … N-1 and no idle clock between packets (g = 0), for every
        //        N at or above the floor the Core's own clocks impose; below
        //        the floor the timeup fires at the first S_WAIT tick.
        // ================================================================
        if (run_it(55)) begin : sv5b
            integer idx, ok, floor_seen; reg [11:0] Ns [0:7];
            Ns[0]=29; Ns[1]=30; Ns[2]=31; Ns[3]=32; Ns[4]=33; Ns[5]=64; Ns[6]=2048; Ns[7]=4095;
            ok = 1; floor_seen = 0;
            for (idx = 0; idx < 8; idx = idx + 1) begin
                hold_reset;
                dut.ptsg_imem.g_sim.mem[0]  = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[1]  = I_STAYSET(16'h0001);
                for (j = 2; j <= 26; j = j + 1) dut.ptsg_imem.g_sim.mem[j] = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[27] = I_PROGEND(16'h0000);
                dut.ptsg_imem.g_sim.mem[28] = I_JUMP(16'h0000, 12'd1);
                dut.ptsg_imem.g_sim.mem[29] = I_STAY(16'h0001, 12'd32);
                pin = Ns[idx];
                release_reset;
                period_of(12'd1, 20000, per);                 // first packet (after the NOP)
                // steady state: walk K along one whole packet, Stay Set to Stay Set
                while (state_number !== 12'd1) step;
                kerr = 0; len = 0;
                begin : kwalk
                    while (len < 20000) begin
                        if (stay_counter !== len) kerr = kerr + 1;
                        len = len + 1; step;
                        if (state_number === 12'd1) disable kwalk;
                    end
                end
                expd = (Ns[idx] > 30) ? Ns[idx] : 30;
                $display("  SV-5b pin=%0d: packet period %0d clocks (expected %0d); K = 0..%0d with %0d errors",
                         Ns[idx], len, expd, len - 1, kerr);
                if (len != expd || kerr != 0) ok = 0;
                if (idx == 0) floor_seen = len;
            end
            $display("%s SV-5b (supplementary): packet Stay = N exactly for N >= %0d (25 window + 5 Core clocks), K = 0..N-1, g = 0",
                     ok ? "PASS" : "FAIL", floor_seen);
            verdict(8, ok);
        end

        // ================================================================
        // SV-6 — Stay(0) with the pin silent: 4096 clocks (C2-F3's escape —
        //        its first exercise in any test).
        // ================================================================
        if (run_it(6)) begin
            hold_reset; load_bare(12'd0); pin = 12'd0; release_reset;
            visit(12'd2, 20000, len);
            $display("%s SV-6: Stay(0), pin silent -> %0d clocks (expected 4096, C2-F3)", (len == 4096) ? "PASS" : "FAIL", len);
            verdict(6, len == 4096);
        end

        // ================================================================
        // SV-7 — two-entry len_lut[state_number]: per-state lengths; a 0 entry
        //        keeps the operand. Program: 0 NOP | 1 NOP ts1 | 2 Stay 3 ts1 |
        //        3 NOP ts0 | 4 Stay 5 ts0 | 5 Jump 1.  (a) lut{2:7, 4:11} ->
        //        on 7, off 11. (b) lut{2:7, 4:0} -> on 7, off 5 (as written).
        // ================================================================
        if (run_it(7)) begin : sv7
            integer on_a, off_a, on_b, off_b;
            for (k = 0; k < 2; k = k + 1) begin
                hold_reset;
                dut.ptsg_imem.g_sim.mem[0] = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[1] = I_NOP(16'h0001);
                dut.ptsg_imem.g_sim.mem[2] = I_STAY(16'h0001, 12'd3);
                dut.ptsg_imem.g_sim.mem[3] = I_NOP(16'h0000);
                dut.ptsg_imem.g_sim.mem[4] = I_STAY(16'h0000, 12'd5);
                dut.ptsg_imem.g_sim.mem[5] = I_JUMP(16'h0001, 12'd1);
                lut_on = 1; lut_a0 = 12'd2; lut_v0 = 12'd7; lut_a1 = 12'd4; lut_v1 = (k == 0) ? 12'd11 : 12'd0;
                release_reset;
                visit(12'd2, 20000, len);  visit(12'd4, 20000, len2);   // settle
                visit(12'd2, 20000, len);  visit(12'd4, 20000, len2);
                if (k == 0) begin on_a = len; off_a = len2; end else begin on_b = len; off_b = len2; end
            end
            $display("  SV-7a lut{2:7, 4:11}: on %0d, off %0d (expected 7, 11)", on_a, off_a);
            $display("  SV-7b lut{2:7, 4:0} : on %0d, off %0d (expected 7, 5 = operand)", on_b, off_b);
            $display("%s SV-7: len_lut[state_number] gives per-state lengths; a 0 entry keeps the operand",
                     (on_a == 7 && off_a == 11 && on_b == 7 && off_b == 5) ? "PASS" : "FAIL");
            verdict(7, on_a == 7 && off_a == 11 && on_b == 7 && off_b == 5);
        end

        if (fails == 0) $display("\nSV SUMMARY: %0d passed, 0 failed (build: %0s)", passes, FORM);
        else begin
            $write("\nSV SUMMARY: %0d passed, %0d failed:", passes, fails);
            for (k = 1; k <= 8; k = k + 1) if (failmask[k]) begin
                if (k == 8) $write(" SV-5b"); else $write(" SV-%0d", k);
            end
            $display(" (build: %0s)", FORM);
        end
        $finish;
    end

    initial begin #200_000_000; $display("WATCHDOG: simulation exceeded 20M clocks"); $finish; end
endmodule


// ============================================================================
//  SV-0 — lockstep equivalence: frozen RH030 vs the copy with stay_value = 0
// ============================================================================
module ptsg_core_sv0_tb;
    parameter integer PRESCALE     = 1;
    parameter integer EPOCHS       = 300;
    parameter integer EPOCH_CLOCKS = 2000;
    parameter integer SEED         = 20260927;
    localparam integer DEPTH = 64;
    localparam [2:0] S_RUN = 3'd0, S_WAIT = 3'd1, S_IND = 3'd2, S_PUSH = 3'd3, S_POP = 3'd4, S_HALT = 3'd5;

    reg clk = 0, rst = 1, condition = 0;
    reg insert_req = 0; reg [11:0] insert_target = 0;
    reg [11:0] indirect_data = 0; reg indirect_ready = 0;
    reg [40:0] stack_rdata = 0; reg stack_ack = 0;
    reg [15:0] prescaler_value = 0;

    // A = frozen RH030, B = RH031p with stay_value tied 0
    wire [11:0] a_sn, b_sn;  wire [15:0] a_ts, b_ts;
    wire a_xv, b_xv; wire [3:0] a_xs, b_xs; wire [7:0] a_xo, b_xo; wire [15:0] a_xd, b_xd;
    wire a_pu, b_pu, a_po, b_po; wire [40:0] a_sw, b_sw;
    wire a_ia, b_ia; wire [15:0] a_lc, b_lc; wire a_lm, b_lm;
    wire [11:0] a_sc, b_sc; wire a_sm, b_sm;
    wire [15:0] a_pc, b_pc; wire a_pm, b_pm; wire [15:0] a_po16, b_po16;
    wire a_ir, b_ir; wire [1:0] a_ip, b_ip; wire a_ef, b_ef;

    ptsg_core_rh030 #(.IMEM_DEPTH(DEPTH), .PRESCALE(PRESCALE), .IMEM_VENDOR("SIM"), .INIT_FILE("")) A (
        .clk(clk), .rst(rst), .condition(condition), .state_number(a_sn), .timing_signals(a_ts),
        .ext_op_valid(a_xv), .ext_op_subopcode(a_xs), .ext_op_sub_operand(a_xo), .ext_op_data(a_xd), .ext_op_ready(1'b1),
        .stack_push_req(a_pu), .stack_pop_req(a_po), .stack_wdata(a_sw), .stack_rdata(stack_rdata), .stack_ack(stack_ack),
        .insert_req(insert_req), .insert_target(insert_target), .insert_ack(a_ia),
        .loop_counter(a_lc), .loop_cnt_match(a_lm), .stay_counter(a_sc), .stay_cnt_match(a_sm),
        .prescaler_counter(a_pc), .prescaler_match(a_pm), .prescaler_value(prescaler_value), .prescaler_output(a_po16),
        .indirect_req(a_ir), .indirect_purpose(a_ip), .indirect_data(indirect_data), .indirect_ready(indirect_ready),
        .error_flag(a_ef));
    ptsg_core #(.IMEM_DEPTH(DEPTH), .PRESCALE(PRESCALE), .IMEM_VENDOR("SIM"), .INIT_FILE("")) B (
        .clk(clk), .rst(rst), .condition(condition), .state_number(b_sn), .timing_signals(b_ts),
        .ext_op_valid(b_xv), .ext_op_subopcode(b_xs), .ext_op_sub_operand(b_xo), .ext_op_data(b_xd), .ext_op_ready(1'b1),
        .stack_push_req(b_pu), .stack_pop_req(b_po), .stack_wdata(b_sw), .stack_rdata(stack_rdata), .stack_ack(stack_ack),
        .insert_req(insert_req), .insert_target(insert_target), .insert_ack(b_ia),
        .loop_counter(b_lc), .loop_cnt_match(b_lm), .stay_counter(b_sc), .stay_cnt_match(b_sm),
        .prescaler_counter(b_pc), .prescaler_match(b_pm), .prescaler_value(prescaler_value), .prescaler_output(b_po16),
        .stay_value(12'd0),
        .indirect_req(b_ir), .indirect_purpose(b_ip), .indirect_data(indirect_data), .indirect_ready(indirect_ready),
        .error_flag(b_ef));

    always #5 clk = ~clk;

    // ---- everything observable, and every register the two cores share ----
    wire [255:0] a_out = {a_sn, a_ts, a_xv, a_xs, a_xo, a_xd, a_pu, a_po, a_sw, a_ia, a_lc, a_lm,
                          a_sc, a_sm, a_pc, a_pm, a_po16, a_ir, a_ip, a_ef};
    wire [255:0] b_out = {b_sn, b_ts, b_xv, b_xs, b_xo, b_xd, b_pu, b_po, b_sw, b_ia, b_lc, b_lm,
                          b_sc, b_sm, b_pc, b_pm, b_po16, b_ir, b_ip, b_ef};
`define SV0_STATE(X) {X.fsm, X.state_num, X.loop_cnt, X.base_addr, X.hr_state, X.hr_loop, X.hr_base, \
        X.hr_ins, X.hr_occupied, X.stack_depth, X.window_open, X.prog_end_seen, X.base_pending,       \
        X.stay_start_state, X.q_base_pending, X.queued_valid, X.queued_subop, X.queued_opcode,        \
        X.queued_target, X.queued_save_state, X.pending_reset, X.pending_reset_tsig, X.stay_cnt,      \
        X.stay_target, X.presc_cnt, X.presc_valueM, X.presc_tick, X.ind_is_loop, X.ind_in_window,     \
        X.ind_resolved, X.ind_target, X.pend_state, X.pend_loop, X.pend_base, X.pend_ins,             \
        X.pend_target, X.pend_is_insert, X.stay_dur}
    wire [511:0] a_int = `SV0_STATE(A);
    wire [511:0] b_int = `SV0_STATE(B);

    // ---- lockstep check, 1 ns after every falling edge (instruction settled)
    reg checking = 0;
    integer mism = 0, clocks = 0;
    integer n_stay = 0, n_win = 0, n_bare = 0, n_op0 = 0, n_timeup = 0, n_halt = 0, n_ins = 0;
    integer n_push = 0, n_pop = 0, n_ind = 0, n_ext = 0, n_qfire = 0;
    reg a_ef_d = 0; reg [2:0] a_fsm_d = 0;
    always @(negedge clk) begin
        #1;
        if (checking) begin
            clocks = clocks + 1;
            if (a_out !== b_out || a_int !== b_int) begin
                mism = mism + 1;
                if (mism <= 5)
                    $display("  SV-0 MISMATCH at %0t: RH030 sn=%0d fsm=%0d stay_cnt=%0d target=%0d | RH031p sn=%0d fsm=%0d stay_cnt=%0d target=%0d",
                             $time, a_sn, A.fsm, A.stay_cnt, A.stay_target, b_sn, B.fsm, B.stay_cnt, B.stay_target);
            end
            // stimulus count (on RH030) — a quiet run must not pass as a clean one
            if (A.fsm == S_RUN && !A.insert_pending && !A.need_indirect && A.opcode == 4'd1) begin
                n_stay = n_stay + 1;
                if (A.window_open) n_win = n_win + 1; else n_bare = n_bare + 1;
                if (A.operand == 12'd0) n_op0 = n_op0 + 1;
            end
            if (A.fsm == S_WAIT && A.presc_tick && (A.stay_cnt >= A.stay_target - 1'b1) && A.queued_valid)
                n_qfire = n_qfire + 1;
            if (a_sm) n_timeup = n_timeup + 1;
            if (a_ef && !a_ef_d) n_halt = n_halt + 1;
            if (a_ia) n_ins = n_ins + 1;
            if (a_xv) n_ext = n_ext + 1;
            if (A.fsm != a_fsm_d) begin
                if (A.fsm == S_PUSH) n_push = n_push + 1;
                if (A.fsm == S_POP)  n_pop  = n_pop + 1;
                if (A.fsm == S_IND)  n_ind  = n_ind + 1;
            end
            a_ef_d = a_ef; a_fsm_d = A.fsm;
        end
    end

    // ---- responders: indirect read (registered 1 clock, C4-T1 lean B) and a
    //      16-deep external stack with a 1-clock acknowledge (C5-F2 style) --
    integer seed_i = SEED + 1, seed_s = SEED + 2, seed_p = SEED + 3;
    always @(posedge clk) begin
        indirect_ready <= a_ir;
        if (a_ir && !indirect_ready) indirect_data <= $random(seed_i) & (DEPTH - 1);
    end
    reg [40:0] stk_mem [0:15]; reg [4:0] stk_sp = 0;
    always @(posedge clk) begin
        if (rst) begin stack_ack <= 1'b0; stk_sp <= 5'd0; end
        else begin
            stack_ack <= 1'b0;
            if (a_pu && !stack_ack) begin
                stk_mem[stk_sp[3:0]] <= a_sw; stk_sp <= stk_sp + 5'd1; stack_ack <= 1'b1;
            end else if (a_po && !stack_ack) begin
                stack_rdata <= stk_mem[stk_sp[3:0] - 4'd1]; stk_sp <= stk_sp - 5'd1; stack_ack <= 1'b1;
            end
        end
    end
    // ---- Condition and insertion traffic (random, reproducible) ------------
    reg stim_on = 0;
    always @(negedge clk) begin
        if (rst || !stim_on) begin insert_req <= 1'b0; end
        else begin
            if (($random(seed_s) & 7) == 0) condition <= ~condition;
            if (!insert_req) begin
                if (($random(seed_s) & 255) == 0) begin
                    insert_req <= 1'b1; insert_target <= $random(seed_s) & (DEPTH - 1);
                end
            end else if (a_ia) insert_req <= 1'b0;
        end
    end

    // ---- structured random programs ----------------------------------------
    function [31:0] W; input [15:0] ts; input [11:0] opd; input [3:0] opc; W = {ts, opd, opc}; endfunction
    function [31:0] G; input [15:0] ts; input [7:0] sub; G = {ts, sub, 8'h00}; endfunction   // internal Global
    reg [31:0] prog [0:DEPTH-1];
    integer pc, r, nbg, q;
    task put; input [31:0] w; begin if (pc < DEPTH) begin prog[pc] = w; pc = pc + 1; end end endtask
    function [11:0] rnd; input integer m; rnd = ($random(seed_p) & 32'h7fffffff) % m; endfunction
    task gen_prog; begin
        for (pc = 0; pc < DEPTH; pc = pc + 1) prog[pc] = W(16'h0000, 12'd0, 4'h3);   // Jump 0
        pc = 0;
        put(G($random(seed_p), 8'd7));                                       // state 0: NOP
        while (pc < DEPTH - 12) begin
            r = rnd(100);
            if (r < 55) begin                                                // ---- a window
                put(G($random(seed_p), 8'd2));                               // Stay Set
                nbg = rnd(5);
                for (q = 0; q < nbg; q = q + 1) begin
                    r = rnd(100);
                    if      (r < 30) put(G(16'h0000, 8'd7));                                  // BG NOP
                    else if (r < 45) put(W($random(seed_p), (rnd(256) << 4) | (1 + rnd(15)), 4'h0)); // external mode
                    else if (r < 60) begin put(G(16'h0000, 8'd1)); put(G(16'h0000, 8'd7));
                                           put(G(rnd(4), 8'd5)); end                          // Base Set, body, Loop
                    else if (r < 68) put(G(1 + rnd(3), 8'd4));                                // Call +1..3
                    else if (r < 74) put(G(16'h0000, 8'd3));                                  // Return
                    else if (r < 82) put(W($random(seed_p), rnd(4), 4'h2));                   // Branch
                    else if (r < 88) put(W($random(seed_p), pc + 1, 4'h3));                   // Jump +1
                    else if (r < 92) put(G(16'h0000, 8'd2));                                  // Stay Set re-kick
                    else if (r < 95) put(G($random(seed_p), 8'd0));                           // Reset (BG)
                    else             put(W($random(seed_p), 12'd0, 4'h3));                    // indirect Jump
                end
                if (rnd(3) != 0) begin
                    put(G(16'h0000, 8'd6));                                  // Prog End
                    r = rnd(100);
                    if      (r < 25) put(W(16'h0000, rnd(DEPTH), 4'h3));    // queued Jump
                    else if (r < 40) begin put(G(16'h0000, 8'd1)); put(G(rnd(4), 8'd5)); end // Q Base Set + Loop
                    else if (r < 52) put(W(16'h0000, rnd(4), 4'h2));        // queued Branch
                    else if (r < 60) put(G(1 + rnd(3), 8'd4));              // queued Call
                    else if (r < 66) put(G(16'h0000, 8'd3));                // queued Return
                    else if (r < 72) put(G($random(seed_p), 8'd0));         // queued Reset
                    else if (r < 80) put(G(16'h0000, 8'd7));                // Q NOP
                    else if (r < 84) put(G(16'h0000, 8'd6));                // stray 2nd Prog End (HALT)
                end
                r = rnd(200);
                put(W($random(seed_p), (r == 0) ? 12'd0 : 12'd1 + rnd(8), 4'h1)); // Stay (0 = 4096, 1 in 200)
            end else begin                                                   // ---- foreground
                r = rnd(100);
                if      (r < 40) put(W($random(seed_p), 12'd1 + rnd(6), 4'h1));   // bare Stay
                else if (r < 60) put(G($random(seed_p), 8'd7));                   // NOP
                else if (r < 75) put(W($random(seed_p), rnd(4), 4'h2));           // Branch
                else if (r < 85) put(W($random(seed_p), rnd(DEPTH), 4'h3));       // Jump
                else if (r < 90) put(G($random(seed_p), 8'd0));                   // Reset
                else if (r < 95) put(W($random(seed_p), (rnd(256) << 4) | (1 + rnd(15)), 4'h0)); // ext op
                else             put(G(16'h0000, 8'd1 + rnd(6)));                 // FG-illegal (HALT)
            end
        end
        for (pc = 0; pc < DEPTH; pc = pc + 1) begin
            A.ptsg_imem.g_sim.mem[pc] = prog[pc];
            B.ptsg_imem.g_sim.mem[pc] = prog[pc];
        end
    end endtask

    // ---- Scene 4 measurement (on RH031p; RH030 is equal by the lockstep) ---
    integer e, t_rise, t_fall, hi, lo, hi2, lo2;
    reg [8*80-1:0] mode;
    initial begin
        if ($test$plusargs("scene4")) begin
            mode = "Scene 4";
            for (pc = 0; pc < DEPTH; pc = pc + 1) begin
                A.ptsg_imem.g_sim.mem[pc] = 32'h0000_0000; B.ptsg_imem.g_sim.mem[pc] = 32'h0000_0000;
            end
            A.ptsg_imem.g_sim.mem[0] = 32'h0000_4E21; B.ptsg_imem.g_sim.mem[0] = 32'h0000_4E21; // Stay 1250, tsig 0
            A.ptsg_imem.g_sim.mem[1] = 32'h0001_4E21; B.ptsg_imem.g_sim.mem[1] = 32'h0001_4E21; // Stay 1250, tsig 1
            // 2: 0000_0000 = Reset (zero fill)
            rst = 1; repeat (3) @(posedge clk); @(negedge clk); rst = 0; checking = 1;
            repeat (1000) @(posedge clk);
            @(negedge clk) prescaler_value = 16'd20;                 // live, as the ISSP probe did
            // skip the fail-loud wrap and two whole periods, then measure
            @(posedge b_ts[0]); @(posedge b_ts[0]); @(posedge b_ts[0]);
            t_rise = $time; @(negedge b_ts[0]); t_fall = $time; @(posedge b_ts[0]);
            hi = (t_fall - t_rise) / 10; lo = ($time - t_fall) / 10;
            t_rise = $time; @(negedge b_ts[0]); t_fall = $time; @(posedge b_ts[0]);
            hi2 = (t_fall - t_rise) / 10; lo2 = ($time - t_fall) / 10;
            checking = 0;
            $display("  SV-0 Scene 4 at P=20 (live): tsig[0] high %0d / low %0d, then %0d / %0d clocks (expected 25000 each, period 50000 — SILICON 2026-08-29)",
                     hi, lo, hi2, lo2);
            $display("%s SV-0 Scene 4: RH030 and RH031p (pin 0) in lockstep for %0d clocks, %0d mismatching clocks; half-periods %s",
                     (mism == 0 && hi == 25000 && lo == 25000 && hi2 == 25000 && lo2 == 25000) ? "PASS" : "FAIL",
                     clocks, mism, (hi == 25000 && lo == 25000) ? "as observed on silicon" : "DIFFER from silicon");
        end else begin
            mode = "random programs";
            for (e = 0; e < EPOCHS; e = e + 1) begin
                rst = 1; stim_on = 0; checking = 0; condition = 0;
                gen_prog;
                repeat (3) @(posedge clk);
                @(negedge clk); rst = 0; stim_on = 1; checking = 1;
                repeat (EPOCH_CLOCKS) @(posedge clk);
            end
            checking = 0; stim_on = 0;
            $display("  SV-0 stimulus (RH030 side): %0d Stays executed (%0d windowed, %0d bare, %0d with operand 0), %0d timeups, %0d queued firings,",
                     n_stay, n_win, n_bare, n_op0, n_timeup, n_qfire);
            $display("                               %0d HALTs, %0d insertions, %0d pushes, %0d pops, %0d indirect reads, %0d external issues",
                     n_halt, n_ins, n_push, n_pop, n_ind, n_ext);
            $display("%s SV-0 random, PRESCALE=%0d: %0d epochs x %0d clocks = %0d clocks in lockstep, %0d mismatching clocks",
                     (mism == 0 && n_stay > 1000 && n_op0 > 0 && n_win > 100 && n_bare > 100) ? "PASS" : "FAIL",
                     PRESCALE, EPOCHS, EPOCH_CLOCKS, clocks, mism);
        end
        $finish;
    end
endmodule
