// ============================================================================
//  wpms_adv7513_tb.v — self-checking bench for wpms_adv7513_cfg: an I2C slave
//  model of the ADV7513 main map (address 0x72/0x73, register pointer, reads
//  and writes, one clock-stretched byte) on an open-drain bus. Checks: the
//  HPD poll (0x42 read), the whole table written in order and acknowledged,
//  nothing written while HPD is low, the rewrite after a hot-plug, the SCL rate.
//  Evidence class RTL-SIM. License: MIT (Layer 3).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps
module wpms_adv7513_tb;
    reg clk = 0, rst = 1;
    always #10 clk = ~clk;                       // 50 MHz
    wire scl_oe, sda_oe, hpd, done, nack;  wire [7:0] tables;
    reg  s_sda_oe = 0, s_scl_oe = 0;
    wire scl = !(scl_oe || s_scl_oe);            // open drain, pulled up
    wire sda = !(sda_oe || s_sda_oe);
    wpms_adv7513_cfg #(.CLK_HZ(50_000_000), .I2C_HZ(100_000), .POWERUP_CLKS(2000), .POLL_CLKS(20000)) dut (
        .clk(clk), .rst(rst), .scl_oe(scl_oe), .sda_oe(sda_oe), .scl_in(scl), .sda_in(sda),
        .hpd(hpd), .done(done), .nack(nack), .tables(tables));

    // ---- the slave: the ADV7513 main map --------------------------------------------------
    reg  [7:0] regs [0:255];
    reg  [7:0] ptr = 0, sh = 0, rd_byte = 0;
    integer    bitc = 0, state = 0, i;           // state 0 idle, 1 address, 2 register, 3 data (write), 4 read
    reg        rd = 0, ack_phase = 0, addressed = 0;
    integer    writes = 0, reads = 0, wlog_n = 0;
    reg [15:0] wlog [0:255];
    reg        stretched = 0;
    // START / STOP: SDA edges while SCL is high
    always @(negedge sda) if (scl) begin state = 1; bitc = 0; ack_phase = 0; end
    always @(posedge sda) if (scl) begin state = 0; s_sda_oe = 0; end
    // data sampled on SCL rising edges
    always @(posedge scl) if (state != 0 && !ack_phase) begin
        if (state == 4) begin
            ;                                     // the master samples our bit
        end else begin
            sh = {sh[6:0], sda};
        end
        bitc = bitc + 1;
    end else if (state != 0 && ack_phase) begin
        if (state == 4 && sda) state = 0;         // master NACK after a read byte: done
    end
    // on SCL falling edges: drive ACK / read bits
    always @(negedge scl) if (state != 0) begin
        if (!ack_phase && bitc == 8) begin
            ack_phase = 1;
            case (state)
                1: begin
                       addressed = (sh[7:1] == 7'h39);
                       rd = sh[0];
                       s_sda_oe = addressed;       // ACK
                       if (addressed) begin
                           if (rd) begin state = 4; rd_byte = regs[ptr]; reads = reads + 1; end
                           else state = 2;
                       end else state = 0;
                   end
                2: begin ptr = sh; s_sda_oe = 1; state = 3; end
                3: begin
                       regs[ptr] = sh; wlog[wlog_n] = {ptr, sh}; wlog_n = wlog_n + 1; writes = writes + 1;
                       ptr = ptr + 1; s_sda_oe = 1;
                       // clock stretching once: hold SCL low for 30 us after the first data byte
                       if (!stretched) begin stretched = 1; s_scl_oe = 1; #30000; s_scl_oe = 0; end
                   end
                4: s_sda_oe = 0;                   // release for the master's ACK/NACK
            endcase
        end else if (ack_phase) begin
            ack_phase = 0;  bitc = 0;  s_sda_oe = 0;
            if (state == 4) s_sda_oe = ~rd_byte[7];          // first read bit
        end else if (state == 4) begin
            s_sda_oe = ~rd_byte[7 - bitc];                   // next read bit (open drain: 0 = pull)
        end
    end

    // ---- the expected table (the same list the RTL holds; checked entry by entry) -----------
    function [15:0] tab; input integer i; begin tab = dut.tab(i[5:0]); end endfunction
    integer bad = 0, k, sclr = 0;  real t_scl0 = 0, t_scl1 = 0;
    always @(posedge scl) begin sclr = sclr + 1; if (sclr == 10) t_scl0 = $realtime; if (sclr == 110) t_scl1 = $realtime; end
    initial begin
        for (i = 0; i < 256; i = i + 1) regs[i] = 8'h00;
        regs[8'h42] = 8'h40;                      // HPD high
        repeat (5) @(posedge clk);  rst = 0;
        // first configuration
        wait (tables == 1);
        repeat (10) @(posedge clk);
        if (wlog_n != 29 || nack) bad = bad + 1;
        for (k = 0; k < 29; k = k + 1)
            if (wlog[k] !== tab(k)) begin bad = bad + 1; $display("FAIL write %0d: %h (expected %h)", k, wlog[k], tab(k)); end
        $display("adv7513_tb: first table: %0d writes acknowledged in order (%0d reads of 0x42 so far); nack %0d; SCL %.1f kHz (with one 30 us stretch)",
                 wlog_n, reads, nack, 100.0 / ((t_scl1 - t_scl0) / 1.0e6) );
        // hot-plug: HPD low -> nothing written; HPD high again -> the table again
        regs[8'h42] = 8'h00;
        repeat (60000) @(posedge clk);
        if (writes != 29 || done) begin bad = bad + 1; $display("FAIL: writes while HPD low (%0d) or done still set (%0d)", writes, done); end
        regs[8'h42] = 8'h40;
        wait (tables == 2);
        repeat (10) @(posedge clk);
        if (writes != 58 || nack) bad = bad + 1;
        for (k = 29; k < 58; k = k + 1)
            if (wlog[k] !== tab(k - 29)) begin bad = bad + 1; $display("FAIL rewrite %0d: %h", k - 29, wlog[k]); end
        $display("adv7513_tb: after the hot-plug: %0d writes in all (the table again), done %0d, hpd %0d; register file: 0x41=%h 0xAF=%h 0x0A=%h 0x0C=%h 0x15=%h N=%h%h%h",
                 writes, done, hpd, regs[8'h41], regs[8'hAF], regs[8'h0A], regs[8'h0C], regs[8'h15], regs[1], regs[2], regs[3]);
        $display("adv7513_tb: %s", bad ? "FAIL" : "PASS");
        $finish;
    end
    initial begin #200_000_000; $display("adv7513_tb: FAIL (timeout)"); $finish; end
endmodule
