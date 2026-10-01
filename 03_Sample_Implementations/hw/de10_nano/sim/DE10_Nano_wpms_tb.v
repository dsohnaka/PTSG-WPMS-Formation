// ============================================================================
//  DE10_Nano_wpms_tb.v — board-level bench for DE10_Nano_wpms_top (Phase 6)
//  基板レベルのテストベンチ
//  License: MIT (Layer 3). Evidence class of its results: RTL-SIM.
// ----------------------------------------------------------------------------
//  The board top with VENDOR = "SIM": behavioural PLLs (wpms_pll_sim.v), the
//  ISSP instances reading 0, the memories in their $readmemh branches. Around
//  it: the three 50 MHz oscillators, KEY and SW, an ADV7513 on the I2C bus
//  (main map at 0x72/0x73, HPD high, one clock-stretched byte), an I2S receiver
//  on HDMI_SCLK/LRCLK/I2S, and a check of the video carrier's timing.
//  The host path is driven through the top's host_ext net (force), with the
//  ISSP bit protocol of wpms_host_bridge.v — the same as wpms_system_tb.v.
//
//  The VCD holds what SignalTap holds on the board: tap_ctl, tap_dat and
//  clk_sys (hw/tools/phase6_evidence.py reads both).
//
//  Commands (numbers in hex):
//    R n     SW[2] up for n clk_sys clocks (the DIP reset of Ch.5 §5.8)
//    W a d   host write      Q a     host read      N n   n idle clocks
//    G n     wait for n strobes                     K b   press KEY[b]
//    D v     SW[3:0] = v (SW[2] kept as is)         V b   VCD on (1) / off (0)
//    E       end
//  Log lines (cyc = clk_sys clocks since time 0):
//    W cyc addr data rdata rej · Q cyc addr rdata · R cyc · K cyc b
//    A cyc l r (one I2S frame decoded: left, right) · B cyc n l r (a bank written, n = strobes
//    since reset) · Z key=value (summary)
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
// ============================================================================
`timescale 1ns/1ps

module adv7513_i2c_model (
    inout wire scl,
    inout wire sda
);
    reg  s_sda_oe = 0, s_scl_oe = 0;
    assign sda = s_sda_oe ? 1'b0 : 1'bz;
    assign scl = s_scl_oe ? 1'b0 : 1'bz;
    reg  [7:0] regs [0:255];
    reg  [7:0] ptr = 0, sh = 0, rd_byte = 0;
    integer    bitc = 0, state = 0, i, writes = 0, reads = 0;
    reg        rd = 0, ack_phase = 0, addressed = 0, stretched = 0;
    initial begin
        for (i = 0; i < 256; i = i + 1) regs[i] = 8'h00;
        regs[8'h42] = 8'h40;                                 // HPD high
    end
    always @(negedge sda) if (scl === 1'b1) begin state = 1; bitc = 0; ack_phase = 0; end
    always @(posedge sda) if (scl === 1'b1) begin state = 0; s_sda_oe = 0; end
    always @(posedge scl) if (state != 0 && !ack_phase) begin
        if (state != 4) sh = {sh[6:0], sda === 1'b1};
        bitc = bitc + 1;
    end else if (state != 0 && ack_phase) begin
        if (state == 4 && sda === 1'b1) state = 0;
    end
    always @(negedge scl) if (state != 0) begin
        if (!ack_phase && bitc == 8) begin
            ack_phase = 1;
            case (state)
                1: begin
                       addressed = (sh[7:1] == 7'h39);
                       rd = sh[0];
                       s_sda_oe = addressed;
                       if (addressed) begin
                           if (rd) begin state = 4; rd_byte = regs[ptr]; reads = reads + 1; end
                           else state = 2;
                       end else state = 0;
                   end
                2: begin ptr = sh; s_sda_oe = 1; state = 3; end
                3: begin
                       regs[ptr] = sh; ptr = ptr + 1; s_sda_oe = 1; writes = writes + 1;
                       if (!stretched) begin stretched = 1; s_scl_oe = 1; #30000; s_scl_oe = 0; end
                   end
                4: s_sda_oe = 0;
            endcase
        end else if (ack_phase) begin
            ack_phase = 0;  bitc = 0;  s_sda_oe = 0;
            if (state == 4) s_sda_oe = ~rd_byte[7];
        end else if (state == 4) begin
            s_sda_oe = ~rd_byte[7 - bitc];
        end
    end
endmodule

module DE10_Nano_wpms_tb;
    parameter integer SYS_MHZ = 50;
    parameter         SCORE_HEX = "wpms_r1d.hex";
    parameter         EXP2_HEX  = "wpms_exp2_table.hex";
    parameter         ROM_HEX   = "wpms_rom_origin_1008.hex";
    parameter integer DEB = 16;

    reg  c1 = 0, c2 = 0, c3 = 0;
    always #10.000 c1 = ~c1;                                 // the three 50 MHz oscillators
    initial begin #3.1; forever #10.000 c2 = ~c2; end
    initial begin #7.3; forever #10.000 c3 = ~c3; end

    reg  [1:0] key = 2'b11;
    reg  [3:0] sw  = 4'b0111;                                // G = 12, SW[2] (reset) up at power-up
    wire [7:0] led;
    wire       scl, sda, i2s, lrclk, mclk, sclk, tx_clk, tx_de, tx_hs, tx_vs;
    wire [23:0] tx_d;
    pullup (scl);
    pullup (sda);
    adv7513_i2c_model u_adv (.scl(scl), .sda(sda));

    DE10_Nano_wpms_top #(
        .SYS_MHZ(SYS_MHZ), .VENDOR("SIM"),
        .SCORE_HEX(SCORE_HEX), .EXP2_HEX(EXP2_HEX), .ROM_HEX(ROM_HEX),
        .CFG_POWERUP_CLKS(2000), .CFG_POLL_CLKS(20000), .CFG_I2C_HZ(1_000_000), .KEY_DEBOUNCE(DEB), .POR_BITS(6),
        .HEARTBEAT(8),
        .SIM_SYS_HALF_PS(SYS_MHZ >= 100 ? 5000 : 10000)
    ) dut (
        .FPGA_CLK1_50(c1), .FPGA_CLK2_50(c2), .FPGA_CLK3_50(c3),
        .KEY(key), .SW(sw), .LED(led),
        .HDMI_I2C_SCL(scl), .HDMI_I2C_SDA(sda), .HDMI_I2S(i2s), .HDMI_LRCLK(lrclk), .HDMI_MCLK(mclk),
        .HDMI_SCLK(sclk), .HDMI_TX_CLK(tx_clk), .HDMI_TX_D(tx_d), .HDMI_TX_DE(tx_de), .HDMI_TX_HS(tx_hs),
        .HDMI_TX_INT(1'b1), .HDMI_TX_VS(tx_vs));

    wire clk = dut.clk_sys;
    integer fout, cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;

    // ---- the VCD: what SignalTap holds ---------------------------------------------------------------
    reg [1023:0] vcdfile;
    reg          vcd_on = 0;
    initial if ($value$plusargs("vcd=%s", vcdfile)) begin
        vcd_on = 1;
        $dumpfile(vcdfile);
        $dumpvars(0, dut.clk_sys, dut.tap_ctl, dut.tap_dat);
        $dumpoff;
    end

    // ---- the host path (the ISSP bit protocol) -----------------------------------------------------------
    reg  [47:0] hsrc = 48'd0;
    initial force dut.host_ext = hsrc;
    wire [35:0] prb = dut.u_sys.host_prb;
    integer gap = 4, waited;
    task host_op; input is_wr; input [11:0] a; input [31:0] d; begin
        hsrc = {2'b00, hsrc[45] ^ !is_wr, hsrc[44] ^ is_wr, a, d};
        waited = 0;
        while ((prb[32] != hsrc[44] || prb[33] != hsrc[45]) && waited < 50000) begin
            @(negedge clk); waited = waited + 1;
        end
        if (waited >= 50000) $fwrite(fout, "T %0d\n", cyc);
        if (is_wr) $fwrite(fout, "W %0d %03h %08h %08h %0d\n", cyc, a, d, prb[31:0], prb[34]);
        else       $fwrite(fout, "Q %0d %03h %08h\n", cyc, a, prb[31:0]);
        repeat (gap) @(negedge clk);
    end endtask

    // ---- the I2S receiver: every frame against the bank the master captured ------------------------------
    // LRCLK and data sampled on SCLK rising edges (C4-D8); a frame begins at the first rising edge
    // with LRCLK low after one with LRCLK high (slot 0); the left MSB is slot 1 (as wpms_synth_tb.v)
    integer slot = -1, frames = 0, i2s_bad = 0;
    reg [23:0] wl = 0, wr = 0, cap_l = 0, cap_r = 0;
    reg        lr_prev = 1;
    always @(posedge sclk) begin
        if (lrclk == 1'b0 && lr_prev == 1'b1) begin          // a frame begins (left channel)
            if (frames > 0) begin
                if (wl !== cap_l || wr !== cap_r) i2s_bad = i2s_bad + 1;
                if (fout) $fwrite(fout, "A %0d %06h %06h\n", cyc, wl, wr);
            end
            frames = frames + 1;
            slot = 0;
            cap_l = dut.u_sys.u_synth.u_i2s.l_r;  cap_r = dut.u_sys.u_synth.u_i2s.r_r;
        end else if (slot >= 0) slot = slot + 1;
        if (slot >= 1 && slot <= 24)  wl[24 - slot] = i2s;
        if (slot >= 33 && slot <= 56) wr[56 - slot] = i2s;
        lr_prev = lrclk;
    end

    // ---- the video carrier: line and frame periods, active area ------------------------------------------
    integer pix = 0, hs_last = -1, hs_per = 0, hs_bad = 0, lines = 0, vs_last = -1, vs_per = 0, vs_bad = 0, de_cnt = 0;
    integer de_line = 0, de_bad = 0, vframes = 0, tx_bad = 0;
    reg     hs_d = 0, vs_d = 0, de_d = 0;
    always @(posedge dut.clk_pix) begin
        pix = pix + 1;
        if (tx_hs && !hs_d) begin
            if (hs_last >= 0) begin hs_per = pix - hs_last; if (hs_per != 1650) hs_bad = hs_bad + 1; end
            hs_last = pix;  lines = lines + 1;
            if (de_line != 0 && de_line != 1280) de_bad = de_bad + 1;
            de_line = 0;
        end
        if (tx_de) de_line = de_line + 1;
        if (tx_vs && !vs_d) begin
            if (vs_last >= 0) begin vs_per = lines - vs_last; if (vs_per != 750) vs_bad = vs_bad + 1; vframes = vframes + 1; end
            vs_last = lines;
        end
        hs_d = tx_hs;  vs_d = tx_vs;  de_d = tx_de;
    end
    // HDMI_TX_CLK rises half a pixel period after the data change (the ADV7513 samples there)
    real t_pix = 0, t_tx = 0;
    always @(posedge dut.clk_pix) t_pix = $realtime;
    always @(posedge tx_clk) begin
        t_tx = $realtime;
        if (t_pix > 0 && ((t_tx - t_pix) < 6.0 || (t_tx - t_pix) > 7.5)) tx_bad = tx_bad + 1;
    end

    // ---- power-up: FPGA memories start at 0 ------------------------------------------------------------------
    task zero_memories; integer b; begin
        for (b = 0; b < 8; b = b + 1) begin
            dut.u_sys.u_synth.u_l2.form.st_n[b] = 0; dut.u_sys.u_synth.u_l2.form.ib_n[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[1].m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_store[2].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[3].m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_store[4].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[5].m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_store[6].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[7].m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_store[8].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[9].m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_store[10].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[11].m[b] = 0; dut.u_sys.u_synth.u_l2.form.g_store[12].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[13].m[b] = 0; dut.u_sys.u_synth.u_l2.form.g_store[14].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_store[15].m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[1].g_bank.m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_inbox[2].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[3].g_bank.m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_inbox[4].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[5].g_bank.m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_inbox[6].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[7].g_bank.m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_inbox[8].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[9].g_bank.m[b] = 0;  dut.u_sys.u_synth.u_l2.form.g_inbox[10].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[11].g_bank.m[b] = 0; dut.u_sys.u_synth.u_l2.form.g_inbox[12].g_bank.m[b] = 0;
            dut.u_sys.u_synth.u_l2.form.g_inbox[15].g_bank.m[b] = 0;
        end
    end endtask

    // ---- LEDs seen ------------------------------------------------------------------------------------------
    integer hb_toggles = 0;  reg hb_d = 0, led1_seen = 0, led2_seen = 0, led3_seen = 0, led6_seen = 0;
    always @(posedge clk) begin
        if (led[0] != hb_d) hb_toggles = hb_toggles + 1;
        hb_d = led[0];
        if (led[1]) led1_seen = 1;
        if (led[2]) led2_seen = 1;
        if (led[3]) led3_seen = 1;
        if (led[6]) led6_seen = 1;
    end

    // ---- every bank written: the PCM of a long run without a VCD (phase6_evidence.py --bench) -----------------
    always @(posedge clk)
        if (fout != 0 && dut.bank_we)
            $fwrite(fout, "B %0d %0d %06h %06h\n", cyc, dut.tap_n, dut.bank_l & 24'hFFFFFF, dut.bank_r & 24'hFFFFFF);

    // ---- command interpreter ----------------------------------------------------------------------------------
    integer fin, r, v0, v1, ns;
    reg [8*8-1:0] cmd;
    reg [8*512-1:0] stim_path, out_path;
    initial begin
        if (!$value$plusargs("stim=%s", stim_path)) stim_path = "stim.txt";
        if (!$value$plusargs("out=%s", out_path))   out_path  = "results.txt";
        fin  = $fopen(stim_path, "r");
        fout = $fopen(out_path, "w");
        if (fin == 0) begin $display("DE10_Nano_wpms_tb: cannot open %0s", stim_path); $finish; end
        zero_memories;
        // power-up with SW[2] up; release it once the PLLs have locked and POR has run
        wait (dut.lk_sys && dut.lk_aud && dut.lk_pix);
        repeat (200) @(negedge clk);
        sw[2] = 1'b0;
        $fwrite(fout, "R %0d\n", cyc);
        while (!$feof(fin)) begin
            r = $fscanf(fin, "%s", cmd);
            if (r != 1) r = $fgetc(fin);
            else case (cmd)
                "R": begin
                        r = $fscanf(fin, "%h", v0);
                        sw[2] = 1'b1;  repeat (v0) @(negedge clk);  sw[2] = 1'b0;
                        @(negedge clk);
                        $fwrite(fout, "R %0d\n", cyc);
                     end
                "W": begin r = $fscanf(fin, "%h %h", v0, v1); host_op(1'b1, v0, v1); end
                "Q": begin r = $fscanf(fin, "%h", v0); host_op(1'b0, v0, 32'd0); end
                "N": begin r = $fscanf(fin, "%h", v0); repeat (v0) @(negedge clk); end
                "G": begin
                        r = $fscanf(fin, "%h", v0);
                        for (ns = 0; ns < v0; ns = ns + 1) begin
                            @(negedge clk);
                            waited = 0;
                            while (!dut.strobe && waited < 20000) begin @(negedge clk); waited = waited + 1; end
                            if (waited >= 20000) $fwrite(fout, "T %0d\n", cyc);
                        end
                     end
                "K": begin
                        r = $fscanf(fin, "%h", v0);
                        key[v0] = 1'b0;  repeat (DEB + 8) @(negedge clk);
                        key[v0] = 1'b1;  repeat (DEB + 8) @(negedge clk);
                        $fwrite(fout, "K %0d %0d\n", cyc, v0);
                     end
                "D": begin r = $fscanf(fin, "%h", v0); sw = {v0[3], sw[2], v0[1:0]}; end
                "V": begin
                        r = $fscanf(fin, "%h", v0);
                        if (vcd_on) begin if (v0) $dumpon; else $dumpoff; end
                     end
                "E": ;
                default: $display("DE10_Nano_wpms_tb: unknown command %0s", cmd);
            endcase
        end
        repeat (8) @(negedge clk);
        $fwrite(fout, "Z i2s_frames=%0d i2s_mismatch=%0d\n", frames, i2s_bad);
        $fwrite(fout, "Z adv_writes=%0d adv_reads=%0d adv_done=%0d adv_nack=%0d adv_0x41=%02h adv_0x0C=%02h adv_N=%02h%02h%02h\n",
                u_adv.writes, u_adv.reads, dut.adv_done, dut.adv_nack, u_adv.regs[8'h41], u_adv.regs[8'h0C],
                u_adv.regs[8'h01], u_adv.regs[8'h02], u_adv.regs[8'h03]);
        $fwrite(fout, "Z video_lines=%0d hs_bad=%0d vs_frames=%0d vs_bad=%0d de_bad=%0d tx_clk_phase_bad=%0d\n",
                lines, hs_bad, vframes, vs_bad, de_bad, tx_bad);
        $fwrite(fout, "Z led_heartbeat_toggles=%0d led_locked=%0d led_adv_done=%0d led_hpd=%0d led_packets=%0d led_error=%0d led_halt=%0d led_nack=%0d\n",
                hb_toggles, led1_seen, led2_seen, led3_seen, led6_seen, led[4], led[5], led[7]);
        $fwrite(fout, "Z strobe_interval=%0d strobe_min=%0d strobe_max=%0d sweep_clocks_max=%0d overrun=%0d\n",
                dut.u_sys.u_synth.strobe_interval, dut.u_sys.u_synth.strobe_min, dut.u_sys.u_synth.strobe_max,
                dut.u_sys.u_sw.sweep_clocks_max, dut.u_sys.u_synth.overrun);
        $fclose(fout);
        $display("DE10_Nano_wpms_tb: done at clock %0d", cyc);
        $finish;
    end
endmodule
