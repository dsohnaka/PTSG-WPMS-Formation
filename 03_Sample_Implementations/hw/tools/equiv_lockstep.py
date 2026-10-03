#!/usr/bin/env python3
# ============================================================================
# equiv_lockstep.py — is a restructured module cycle for cycle the same as its
# previous revision? The previous revision (taken from a git commit, renamed
# *_ref) and the current file run side by side in one bench, on the same
# random stimulus, and are compared in every clock: every output, every
# register (the whole store and inbox of the Formation included) and the
# signals the restructure touched. One difference is a failure.
#
# SD-22 step 1 (ruling 2026-10-03): wpms_formation RH005 against RH004 and
# wpms_switch RH002 against RH001, each at NMAX 1,008 and 2,048.
#
#   python3 equiv_lockstep.py [--ref COMMIT] [--clocks N] [--seeds 1,2]
#                             [--only formation|switch] [--out DIR]
#
# The stimulus keeps the two rules the RTL itself checks in simulation (no
# inbox write to a block whose copy is pending, no prefetch while the copy
# runs; the switch's strobe/apply order), so that no warning drowns the run;
# everything else is random over the whole input space, illegal encodings,
# errors and resets included. Coverage counts say what the run exercised.
# Evidence class: RTL-SIM (Icarus Verilog -g2012). License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SD-22 step 1).
# ============================================================================
import argparse, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
L2, SW = os.path.join(HW, "l2"), os.path.join(HW, "switch")
REF_COMMIT = "e3d4985"          # Formation RH004, switch RH001 (the first fit's RTL)


def git_show(commit, rel):
    r = subprocess.run(["git", "-C", HW, "show", f"{commit}:./{rel}"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git show {commit}:{rel}: {r.stderr.strip()}")
    return r.stdout


def ref_copy(commit, rel, module, out):
    text = git_show(commit, rel)
    text, n = re.subn(rf"\bmodule\s+{module}\b", f"module {module}_ref", text, count=1)
    assert n == 1, f"no module {module} in {rel}@{commit}"
    path = os.path.join(out, f"{module}_ref.v")
    open(path, "w").write(text)
    return path


def cmp_line(name, x, y):
    return (f'        if (({x}) !== ({y})) begin mism = mism + 1; '
            f'if (mism <= 20) $display("%0d MISMATCH {name}: %h / %h", cyc, {x}, {y}); end\n')


# ============================================================================
#  The Formation
# ============================================================================
F_IN = [("ext_op_valid", 1), ("ext_op_subopcode", 4), ("ext_op_sub_operand", 8), ("ext_op_data", 16),
        ("tap_k", 12), ("tap_i", 16), ("tap_sn", 12), ("tap_sss", 12), ("seq_pkt", 1), ("seq_cur", 3),
        ("seq_q", 4), ("seq_strobe", 1), ("pf_req", 1), ("pf_block", 3), ("ibx_we", 1), ("ibx_addr", 8),
        ("ibx_wdata", 32), ("insert_ack", 1)]
F_OUT = [("ext_op_ready", 1), ("pf_n", 32), ("pf_ph0", 32), ("pf_phd1", 32), ("pf_phd2", 32), ("pf_lp", 32),
         ("pf_ls0", 32), ("pf_lad1", 32), ("pf_lad2", 32), ("pf_rt", 32), ("sweep_a", 28), ("inbox_taken", 1),
         ("bcp_busy", 1), ("loopval", 12), ("jumpval", 12), ("error_flag", 1), ("error_code", 5),
         ("error_sn", 12), ("insert_req", 1), ("insert_target", 12)]
F_REGS = ["accm", "temp", "adrs", "shv", "armed", "sweep_armed", "take", "take_sweep", "copied", "sweep_copied",
          "sweep_staged", "taken_due", "x_valid", "x_mode", "x_subop", "x_rid", "x_imm", "x_k", "x_i", "x_sn",
          "x_sss", "x_pkt", "x_cur", "x_q", "insert_req_r"]
# the signals the restructure touched (RH004 combinational, RH005 some registered)
F_TOUCHED = ["region", "a_block", "x_err", "dp_st_we", "cp_go", "cp_b", "bcp_commit", "pm_idle_next", "ew5",
             "chk_sum", "sw_invalid", "rd_val", "src", "rd_e5", "wr_err", "x_commit"]


def formation_bench():
    decl = "".join(f"    reg  [{w - 1}:0] {n} = 0;\n" for n, w in F_IN)
    decl += "".join(f"    wire [{w - 1}:0] a_{n}, b_{n};\n" for n, w in F_OUT)
    ports = lambda p: ", ".join([".clk(clk)", ".rst(rst)"] + [f".{n}({n})" for n, _ in F_IN] +
                                [f".{n}({p}_{n})" for n, _ in F_OUT])
    cmp = "".join(cmp_line(n, f"a_{n}", f"b_{n}") for n, _ in F_OUT)
    cmp += "".join(cmp_line(n, f"a.{n}", f"b.{n}") for n in F_REGS + F_TOUCHED)
    for arr in ("pmask", "cm_mask", "rtout", "st_n", "ib_n"):
        cmp += "".join(cmp_line(f"{arr}[{w}]", f"a.{arr}[{w}]", f"b.{arr}[{w}]") for w in range(8))
    for gs in range(1, 16):
        cmp += "".join(cmp_line(f"store bank {gs} word {w}", f"a.g_store[{gs}].m[{w}]", f"b.g_store[{gs}].m[{w}]")
                       for w in range(8))
    for gs in [g for g in range(1, 16) if g not in (13, 14)]:
        cmp += "".join(cmp_line(f"inbox bank {gs} word {w}", f"a.g_inbox[{gs}].g_bank.m[{w}]",
                                f"b.g_inbox[{gs}].g_bank.m[{w}]") for w in range(8))
    init = "".join(f"        v = $random(seed); a.g_store[{gs}].m[{w}] = v; b.g_store[{gs}].m[{w}] = v;\n"
                   for gs in range(1, 16) for w in range(8))
    init += "".join(f"        v = $random(seed); a.g_inbox[{gs}].g_bank.m[{w}] = v; b.g_inbox[{gs}].g_bank.m[{w}] = v;\n"
                    for gs in range(1, 16) if gs not in (13, 14) for w in range(8))
    init += "".join(f"        v = nval({{$random(seed)}} % 100, {{$random(seed)}}); a.st_n[{w}] = v; b.st_n[{w}] = v;\n"
                    f"        v = nval({{$random(seed)}} % 100, {{$random(seed)}}); a.ib_n[{w}] = v; b.ib_n[{w}] = v;\n"
                    for w in range(8))
    return FORMATION_TB.replace("@DECL@", decl).replace("@PORTS_A@", ports("a")) \
                       .replace("@PORTS_B@", ports("b")).replace("@CMP@", cmp).replace("@MEMINIT@", init)


FORMATION_TB = r"""`timescale 1ns/1ps
// equiv_formation_tb — generated by hw/tools/equiv_lockstep.py; do not edit.
module equiv_formation_tb;
    parameter integer NMAX  = 1008;
    parameter integer N_MIN = 32;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1;
    integer seed, clocks, cyc = 0, mism = 0;
@DECL@
    wpms_formation_ref #(.NMAX(NMAX), .N_MIN(N_MIN)) a (@PORTS_A@);
    wpms_formation     #(.NMAX(NMAX), .N_MIN(N_MIN)) b (@PORTS_B@);

    // ---- coverage (from the reference, in each X clock) ----------------------
    integer n_x = 0, n_rst = 0, n_strobe = 0, n_pf = 0, n_ibx = 0, n_stwe = 0, n_cpgo = 0, n_bcp = 0;
    integer n_taken = 0, n_fault = 0, n_bcpcp = 0, k;
    integer n_ok [0:15];
    integer n_err [0:31];
    integer n_reg [0:7];
    reg     taken_q = 0, flag_q = 0;
    initial for (k = 0; k < 32; k = k + 1) begin n_err[k] = 0; if (k < 16) n_ok[k] = 0; if (k < 8) n_reg[k] = 0; end

    // ---- stimulus helpers --------------------------------------------------------
    function [15:0] val16;
        input integer r, s;
        begin
            case (r % 5)
                0, 1:    val16 = (s % 128) - 64;                              // small, signed
                2:       case (s % 4) 0: val16 = 16'h7FFF; 1: val16 = 16'h8000; 2: val16 = 16'hFFFF; default: val16 = 16'h0001; endcase
                default: val16 = s;
            endcase
        end
    endfunction
    function [8:0] adrs9;
        input integer r, s;
        begin
            if      (r < 35) adrs9 = s % 128;                 // store
            else if (r < 50) adrs9 = 9'h080 + s % 128;        // inbox view
            else if (r < 75) adrs9 = 9'h100 + s % 16;         // CUR
            else if (r < 85) adrs9 = 9'h110 + s % 8;          // COMMIT view
            else if (r < 91) adrs9 = 9'h118 + s % 3;          // sweep words, status
            else if (r < 96) adrs9 = 9'h11B + s % 227;        // nothing (E5)
            else             adrs9 = 9'h1FE + s % 2;          // the top: post-increment to 0x200
        end
    endfunction
    function [31:0] nval;
        input integer r, s;
        begin
            if      (r < 60) nval = N_MIN + s % (NMAX / 4 - N_MIN + 1);
            else if (r < 85) nval = N_MIN + s % (NMAX - N_MIN + 1);
            else if (r < 90) nval = NMAX + 1;
            else             nval = s;                         // anything, negative included
        end
    endfunction
    function [27:0] sweep_word;
        input integer r, s, t;
        integer q;
        reg [23:0] e;
        begin
            e = t;
            if (r < 55)                                        // distinct blocks
                for (q = 0; q < 8; q = q + 1) e[3*q +: 3] = (s + q * (2 * (t % 4) + 1)) % 8;
            sweep_word = {e, 4'd0} | ((r < 90) ? (s % 9) : (9 + s % 7));   // P 0..8, sometimes 9..15
        end
    endfunction

    reg [7:0] row;
    reg [3:0] rid;
    reg [15:0] imm;
    integer rr, w, err_wait = 0, rst_left = 3;
    reg [2:0] bb;
    reg [3:0] ii;

    integer seed0, v;
    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("clocks=%d", clocks)) clocks = 100000;
        seed0 = seed;
        // The store and the inbox have no reset: the same defined words in both, so the
        // comparison is two-valued as the hardware is (an X read would only test how
        // the simulator treats X in each revision's if-conditions).
@MEMINIT@
    end

    always @(negedge clk) begin
        cyc = cyc + 1;
        // ---- compare: registers after the last edge, outputs for the inputs held -------
@CMP@
        // ---- coverage ------------------------------------------------------------------
        if (!rst && a.x_valid) begin
            n_x = n_x + 1;
            if (a.x_commit) n_ok[a.op] = n_ok[a.op] + 1;
            n_reg[a.region] = n_reg[a.region] + 1;
        end
        if (!rst && a.dp_st_we) n_stwe = n_stwe + 1;
        if (!rst && a.cp_go) n_cpgo = n_cpgo + 1;
        if (!rst && a.bcp_commit) begin n_bcp = n_bcp + 1; if (a.new_list != 0) n_bcpcp = n_bcpcp + 1; end
        if (!rst && a_error_flag && !flag_q) begin n_fault = n_fault + 1; n_err[a_error_code] = n_err[a_error_code] + 1; end
        flag_q = a_error_flag;
        if (!rst && a_inbox_taken && !taken_q) n_taken = n_taken + 1;
        taken_q = a_inbox_taken;

        // ---- reset: after an error halts the datapath, and now and then -------------------
        if (rst_left > 0) begin rst = 1; rst_left = rst_left - 1; end
        else begin
            rst = 0;
            if (a_error_flag) begin
                if (err_wait == 0) err_wait = 2 + {$random(seed)} % 10;
                else if (err_wait == 1) begin rst_left = 2; n_rst = n_rst + 1; err_wait = 0; end
                else err_wait = err_wait - 1;
            end else if ({$random(seed)} % 20000 == 0) begin rst_left = 2; n_rst = n_rst + 1; end
        end

        // ---- the sequencer context: packet windows and housekeeping in stretches ------------
        tap_k = $random(seed); tap_i = $random(seed); tap_sn = $random(seed); tap_sss = $random(seed);
        if ({$random(seed)} % 150 == 0) seq_pkt = !seq_pkt;
        seq_cur = $random(seed); seq_q = $random(seed);

        // ---- the issue port: one instruction in most clocks; legal nearly always (steered by
        //      the reference's state), so that a run goes on long enough to reach the copy,
        //      the strobes and EW5; errors of every kind still occur ---------------------------
        ext_op_valid = ({$random(seed)} % 100) < 82;
        rr = {$random(seed)} % 1000;
        if      (rr < 120) row = 8'h10;  else if (rr < 200) row = 8'h11;  else if (rr < 260) row = 8'h12;
        else if (rr < 300) row = 8'h13;  else if (rr < 380) row = 8'h14;  else if (rr < 460) row = 8'h15;
        else if (rr < 500) row = 8'h16;  else if (rr < 550) row = 8'h17;  else if (rr < 640) row = 8'h20;
        else if (rr < 720) row = 8'h21;  else if (rr < 820) row = 8'h22;  else if (rr < 840) row = 8'h31;
        else if (rr < 860) row = 8'h32;  else if (rr < 900) row = 8'h33;  else if (rr < 940) row = 8'h40;
        else if (rr < 999) row = 8'h41;
        else case ({$random(seed)} % 4) 0: row = 8'h23; 1: row = 8'h30; 2: row = 8'h00; default: row = 8'h5A; endcase
        rid = 0; imm = 0;
        w = {$random(seed)} % 1000;
        case (row)
            8'h10, 8'h12, 8'h13, 8'h14, 8'h15, 8'h40: begin                                  // a source
                if (w < 550) rid = 0; else if (w < 800) rid = 2; else if (w < 860) rid = 1;
                else if (w < 999) rid = 3 + {$random(seed)} % 4; else rid = 7 + {$random(seed)} % 9;
                if (rid == 0) imm = val16({$random(seed)}, {$random(seed)});
                else if ({$random(seed)} % 1000 == 0) imm = 16'h0001;                     // E4
            end
            8'h11: begin                                                                        // a destination
                rid = (w < 500) ? 4'd0 : (w < 999) ? 4'd1 : 4'd2 + {$random(seed)} % 14;
                if ({$random(seed)} % 1000 == 0) imm = 16'h0004;
            end
            8'h20: begin                                                                        // SAD
                imm = adrs9({$random(seed)} % 100, {$random(seed)});
                if ({$random(seed)} % 1000 == 0) imm[12] = 1'b1;
                if ({$random(seed)} % 1000 == 0) rid = 4'd1;
            end
            8'h17: imm = ({$random(seed)} % 81) - 40;                                          // SFT
            default: begin
                if ({$random(seed)} % 2000 == 0) rid = 4'd3;
                if ({$random(seed)} % 2000 == 0) imm = 16'h0010;
            end
        endcase
        // steering, 98 %: a store write only where the window allows it, BCP only in
        // housekeeping, no read of an unmapped word, no STP with Temp < 0; else move ADRS
        if ({$random(seed)} % 50 != 0) begin
            if (((row == 8'h22) || (row == 8'h11 && rid == 4'd1)) &&
                !((a.region == 3'd0 && !seq_pkt) || (a.region == 3'd2 && seq_pkt))) begin
                row = 8'h20; rid = 0; imm = seq_pkt ? (9'h100 + {$random(seed)} % 16) : ({$random(seed)} % 128);
            end
            if (row == 8'h41 && seq_pkt) begin row = 8'h10; rid = 0; imm = val16({$random(seed)}, {$random(seed)}); end
            if ((row == 8'h21 || rid == 4'd2) && a.region == 3'd7 && row != 8'h11) begin
                row = 8'h20; rid = 0; imm = {$random(seed)} % 128;
            end
            if (row == 8'h40 && a.temp[31]) begin row = 8'h16; rid = 0; imm = 0; end
            if ((row == 8'h14 || row == 8'h15) &&                                        // keep products small
                ((a.accm[31:16] != 16'h0000 && a.accm[31:16] != 16'hFFFF) ||
                 (row == 8'h15 && a.temp[31:12] != 20'h00000 && a.temp[31:12] != 20'hFFFFF))) begin
                row = 8'h10; rid = 0; imm = val16(0, {$random(seed)});
            end
            if ((row == 8'h14 || row == 8'h15) && rid == 0) imm = val16(0, {$random(seed)});
            if (row == 8'h17 && $signed(imm) < -4) imm = -({$random(seed)} % 5);
            if (row == 8'h20 && imm[8:1] == 8'hFF && {$random(seed)} % 4 != 0) imm = {$random(seed)} % 128;
        end
        ext_op_subopcode = row[7:4]; ext_op_sub_operand = {rid, row[3:0]}; ext_op_data = imm;
        seq_strobe = ({$random(seed)} % 40 == 0);
        if (seq_strobe) n_strobe = n_strobe + 1;

        // ---- prefetch: never while the copy runs (the sequencer's rule) ---------------------
        pf_req = ({$random(seed)} % 32 == 0) && !a_bcp_busy && !b_bcp_busy;
        pf_block = $random(seed);
        if ({$random(seed)} % 20 != 0 && ($signed(a.st_n[pf_block]) < N_MIN || $signed(a.st_n[pf_block]) > NMAX))
            pf_req = 0;                                                                   // EW2 now and then only
        if (pf_req) n_pf = n_pf + 1;

        // ---- the input switch's writes: never into a block whose copy is pending ----------
        ibx_we = ({$random(seed)} % 4 == 0);
        bb = $random(seed); ii = $random(seed);
        w = {$random(seed)} % 100;
        if (w < 50) begin
            ibx_addr = {1'b0, bb, ii};
            ibx_wdata = (ii == 0) ? nval({$random(seed)} % 100, {$random(seed)}) : $random(seed);
            if (a.pmask[bb] != 16'd0 || b.pmask[bb] != 16'd0) ibx_we = 0;
        end else if (w < 58) begin
            ibx_addr = {5'b10000, bb}; ibx_wdata = $random(seed);
            if (a.pmask[bb][14] || b.pmask[bb][14]) ibx_we = 0;
        end else if (w < 74) begin ibx_addr = {5'b10001, bb}; ibx_wdata = $random(seed); end
        else if (w < 80) begin ibx_addr = 8'h90; ibx_wdata = sweep_word({$random(seed)} % 100, {$random(seed)}, $random(seed)); end
        else if (w < 86) begin ibx_addr = 8'h91; ibx_wdata = $random(seed); end
        else if (w < 96) begin ibx_addr = 8'h9F; ibx_wdata = $random(seed); end
        else begin ibx_addr = 8'h92 + {$random(seed)} % 13; ibx_wdata = $random(seed); end
        if (ibx_we) n_ibx = n_ibx + 1;

        // ---- the Core acknowledges an insertion now and then ------------------------------
        insert_ack = a_insert_req && ({$random(seed)} % 2 == 0);

        if (cyc >= clocks) begin
            $display("equiv_formation NMAX %0d seed %0d: %0d clocks, %0d mismatches", NMAX, seed0, cyc, mism);
            $display("  X clocks %0d; resets %0d; strobes %0d; prefetches %0d; inbox-port writes %0d",
                     n_x, n_rst, n_strobe, n_pf, n_ibx);
            $display("  executed without error: LDA %0d STA %0d ADD %0d SUB %0d MUL %0d MAC %0d SWP %0d SFT %0d",
                     n_ok[0], n_ok[1], n_ok[2], n_ok[3], n_ok[4], n_ok[5], n_ok[6], n_ok[7]);
            $display("                          SAD %0d LDM %0d STM %0d WLV %0d WJV %0d WSH %0d STP %0d BCP %0d",
                     n_ok[8], n_ok[9], n_ok[10], n_ok[11], n_ok[12], n_ok[13], n_ok[14], n_ok[15]);
            $display("  errors %0d: E4 %0d E5 %0d E8 %0d EW2 %0d EW3 %0d EW4 %0d EW5 %0d EW6 %0d", n_fault,
                     n_err[4], n_err[5], n_err[8], n_err[18], n_err[19], n_err[20], n_err[21], n_err[22]);
            $display("  store writes %0d; copy clocks %0d; BCP commits %0d (%0d with blocks to copy); inbox_taken rises %0d",
                     n_stwe, n_cpgo, n_bcp, n_bcpcp, n_taken);
            $display("  region at X: store %0d inbox %0d CUR %0d COMMIT %0d SWST %0d SWA %0d STAT %0d none %0d",
                     n_reg[0], n_reg[1], n_reg[2], n_reg[3], n_reg[4], n_reg[5], n_reg[6], n_reg[7]);
            $finish;
        end
    end
endmodule
"""


# ============================================================================
#  The switch
# ============================================================================
S_IN = [("strobe", 1), ("p0_req", 1), ("p0_we", 1), ("p0_addr", 12), ("p0_wdata", 32), ("key_go_all", 1),
        ("key_origin", 1), ("inbox_taken", 1), ("sweep_a", 28), ("mg", 32), ("g_eff", 4), ("clip", 2),
        ("strobe_interval", 12), ("strobe_min", 12), ("strobe_max", 12), ("sweep_clocks", 12),
        ("insp_phase", 32), ("insp_L", 54), ("insp_a", 32)]
S_OUT = [("p0_done", 1), ("rdata", 32), ("rej", 1), ("ibx_we", 1), ("ibx_addr", 8), ("ibx_wdata", 32),
         ("mg_target", 32), ("mg_rate", 32), ("g_ctrl", 5), ("mute", 1), ("clip_clear", 2), ("minmax_clear", 1),
         ("insp_pos", 12), ("go_seq", 32), ("applied_seq", 32), ("applied_sample", 32), ("reject0", 32),
         ("reject3", 32), ("frozen", 9), ("sweep_clocks_max", 12), ("rom_busy", 1), ("insp_l_q626", 32)]
S_REGS = ["arm", "arm_p3", "fired", "fa", "ft", "ft_open", "fa_seq", "ft_seq", "n_take", "cmask_v", "rtout_v",
          "sw_st", "n_st_v", "nv_st", "n_fu_v", "nv_fu", "sw_fu", "sample_n", "sample_hi", "owner0", "insp_mod",
          "insp_pos_r", "p0_pend", "key_pend", "unf_pend", "taken_d", "rr", "p0_we_l", "p0_a_l", "p0_d_l",
          "rom_req", "rom_a", "rom_d", "x_v", "x_unf", "x_p3", "x_we", "x_a", "x_d", "d_v", "d_p3", "d_rej",
          "d_inbox", "d_rdata", "ibx_hand", "ibx_seq", "rom_st", "rom_idx", "rom_start", "shadow_q"]
S_TOUCHED = ["go_bad", "go_sum", "go_items", "sw_nx", "n_nx_v", "nv_nx"]


def switch_bench():
    decl = "".join(f"    reg  [{w - 1}:0] {n} = 0;\n" for n, w in S_IN)
    decl += "".join(f"    wire [{w - 1}:0] a_{n}, b_{n};\n" for n, w in S_OUT)
    ports = lambda p: ", ".join([".clk(clk)", ".rst(rst)"] + [f".{n}({n})" for n, _ in S_IN] +
                                [f".{n}({p}_{n})" for n, _ in S_OUT])
    cmp = "".join(cmp_line(n, f"a_{n}", f"b_{n}") for n, _ in S_OUT)
    cmp += "".join(cmp_line(n, f"a.{n}", f"b.{n}") for n in S_REGS + S_TOUCHED)
    return SWITCH_TB.replace("@DECL@", decl).replace("@PORTS_A@", ports("a")) \
                    .replace("@PORTS_B@", ports("b")).replace("@CMP@", cmp)


SWITCH_TB = r"""`timescale 1ns/1ps
// equiv_switch_tb — generated by hw/tools/equiv_lockstep.py; do not edit.
module equiv_switch_tb;
    parameter integer NMAX  = 1008;
    parameter integer N_MIN = 32;
    parameter         ROM_HEX = "wpms_rom_origin_1008.hex";
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1;
    integer seed, clocks, cyc = 0, mism = 0;
@DECL@
    wpms_switch_ref #(.NMAX(NMAX), .N_MIN(N_MIN), .ROM_HEX(ROM_HEX)) a (@PORTS_A@);
    wpms_switch     #(.NMAX(NMAX), .N_MIN(N_MIN), .ROM_HEX(ROM_HEX)) b (@PORTS_B@);

    // ---- coverage (from the reference, at EXEC) ---------------------------------------
    integer n_tr = 0, n_rst = 0, n_strobe = 0, n_go = 0, n_go_bad = 0, n_now = 0, n_now_bad = 0;
    integer n_bad_p = 0, n_bad_rep = 0, n_bad_nv = 0, n_bad_sum = 0, n_rej = 0, n_apply = 0, n_hand = 0;
    integer q, r;
    reg     rep, nvb, pb;

    function [31:0] nval;
        input integer r, s;
        begin
            if      (r < 60) nval = N_MIN + s % (NMAX / 4 - N_MIN + 1);
            else if (r < 85) nval = N_MIN + s % (NMAX - N_MIN + 1);
            else if (r < 90) nval = (s % 2) ? NMAX + 1 : N_MIN - 1;
            else             nval = s;
        end
    endfunction
    function [27:0] sweep_word;
        input integer r, s, t;
        integer q;
        reg [23:0] e;
        begin
            e = t;
            if (r < 55)
                for (q = 0; q < 8; q = q + 1) e[3*q +: 3] = (s + q * (2 * (t % 4) + 1)) % 8;
            sweep_word = {e, 4'd0} | ((r < 90) ? (s % 9) : (9 + s % 7));
        end
    endfunction

    integer w, busy = 0, period = 300, phase = 0, taken_at = 0, rst_left = 3, seed0;
    reg [2:0] bb;
    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("clocks=%d", clocks)) clocks = 100000;
        seed0 = seed;
    end

    always @(negedge clk) begin
        cyc = cyc + 1;
@CMP@
        // ---- coverage: what EXEC did in this clock ----------------------------------------------
        if (!rst && a.x_v && !a.x_unf) begin
            n_tr = n_tr + 1;
            if (a.x_go || a.x_nowb || a.x_nows) begin
                if (a.x_go) n_go = n_go + 1; else n_now = n_now + 1;
                if (a.go_bad) begin
                    if (a.x_go) n_go_bad = n_go_bad + 1; else n_now_bad = n_now_bad + 1;
                    pb = (a.sw_nx[3:0] > 8); rep = 0; nvb = 0;
                    for (q = 0; q < 8; q = q + 1) if (q < a.sw_nx[3:0]) begin
                        if (!a.nv_nx[a.sw_nx[4 + 3*q +: 3]]) nvb = 1;
                        for (r = 0; r < q; r = r + 1) if (a.sw_nx[4 + 3*r +: 3] == a.sw_nx[4 + 3*q +: 3]) rep = 1;
                    end
                    if (pb) n_bad_p = n_bad_p + 1;
                    if (rep) n_bad_rep = n_bad_rep + 1;
                    if (nvb) n_bad_nv = n_bad_nv + 1;
                    if (a.go_sum > NMAX) n_bad_sum = n_bad_sum + 1;
                end
            end
        end
        if (!rst && a.x_v && a.x_unf) n_apply = n_apply + 1;
        if (!rst && a_ibx_we && a.ibx_hand) n_hand = n_hand + 1;
        if (!rst && a.d_v && a_rej) n_rej = n_rej + 1;

        // ---- reset now and then (the ROM plays its list after each) ------------------------
        if (rst_left > 0) begin rst = 1; rst_left = rst_left - 1; end
        else begin rst = 0; if ({$random(seed)} % 40000 == 0) begin rst_left = 2; n_rst = n_rst + 1; busy = 0; end end

        // ---- the strobe and the Formation's inbox_taken (the take's copy lands, then the
        //      apply step leaves the flags long before the next strobe) ----------------------
        phase = phase + 1;
        strobe = (phase >= period);
        if (strobe) begin
            phase = 0; period = 120 + {$random(seed)} % 300; n_strobe = n_strobe + 1;
            inbox_taken = 0; taken_at = 4 + {$random(seed)} % 30;
        end else if (phase == taken_at) inbox_taken = 1;
        sweep_a = $random(seed);

        // ---- port 0: one transaction at a time ---------------------------------------------
        p0_req = 0;
        if (busy && a_p0_done) busy = 0;
        if (!busy && !rst && ({$random(seed)} % 4 == 0)) begin
            busy = 1; p0_req = 1; p0_we = ({$random(seed)} % 100) < 85;
            bb = $random(seed);
            w = {$random(seed)} % 100;
            if (w < 15) begin p0_addr = 12'h008; p0_wdata = 1 + {$random(seed)} % 2; end     // GO, GO_ALL
            else if (w < 45) begin                                                       // inbox slots
                p0_addr = 12'h200 + {$random(seed)} % 128;
                p0_wdata = (p0_addr[3:0] == 0 || {$random(seed)} % 3 == 0)
                           ? nval({$random(seed)} % 100, {$random(seed)}) : $random(seed);
                if ({$random(seed)} % 3 == 0) p0_addr[3:0] = 4'd0;
            end
            else if (w < 60) begin                                                       // COMMIT
                p0_addr = {9'h051, bb}; p0_wdata = $random(seed);
                p0_wdata[30] = ({$random(seed)} % 2 == 0); p0_wdata[31] = ({$random(seed)} % 5 == 0);
            end
            else if (w < 68) begin p0_addr = 12'h290; p0_wdata = sweep_word({$random(seed)} % 100, {$random(seed)}, $random(seed)); end
            else if (w < 75) begin
                p0_addr = 12'h291; p0_wdata = 0;
                p0_wdata[30] = ({$random(seed)} % 2 == 0); p0_wdata[31] = ({$random(seed)} % 4 == 0);
            end
            else if (w < 80) begin p0_addr = {9'h050, bb}; p0_wdata = $random(seed); end    // RTOUT
            else if (w < 95) begin                                                       // the global region
                case ({$random(seed)} % 12)
                    0: p0_addr = 12'h010; 1: p0_addr = 12'h011; 2: p0_addr = 12'h013; 3: p0_addr = 12'h015;
                    4: p0_addr = 12'h016; 5: p0_addr = 12'h019; 6: p0_addr = 12'h01C; 7: p0_addr = 12'h020;
                    8: p0_addr = 12'h030; 9: p0_addr = 12'h040; 10: p0_addr = 12'h00C; default: begin p0_addr = $random(seed); p0_addr[11:8] = 4'd0; end
                endcase
                p0_wdata = $random(seed);
            end
            else begin p0_addr = {$random(seed)} % 4096; p0_wdata = $random(seed); end
        end

        // ---- the board's keys, rarely; the taps, always ---------------------------------------
        key_go_all = ({$random(seed)} % 3000 == 0);
        key_origin = ({$random(seed)} % 20000 == 0);
        mg = $random(seed); g_eff = $random(seed); clip = $random(seed);
        strobe_interval = $random(seed); strobe_min = $random(seed); strobe_max = $random(seed);
        sweep_clocks = $random(seed); insp_phase = $random(seed); insp_L = {$random(seed), $random(seed)};
        insp_a = $random(seed);

        if (cyc >= clocks) begin
            $display("equiv_switch NMAX %0d seed %0d: %0d clocks, %0d mismatches", NMAX, seed0, cyc, mism);
            $display("  transactions %0d (refused %0d); resets %0d; strobes %0d; apply steps %0d; hand-overs %0d",
                     n_tr, n_rej, n_rst, n_strobe, n_apply, n_hand);
            $display("  GO/GO_ALL %0d (refused %0d); go-now %0d (refused %0d)", n_go, n_go_bad, n_now, n_now_bad);
            $display("  refusals by cause (a GO can have several): P > 8 %0d, a block twice %0d, N invalid %0d, sum > NMAX %0d",
                     n_bad_p, n_bad_rep, n_bad_nv, n_bad_sum);
            $finish;
        end
    end
endmodule
"""


def run(job):
    name, cmd, cwd = job
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return name, r.returncode, r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=REF_COMMIT, help="git commit of the previous revisions")
    ap.add_argument("--clocks", type=int, default=400000)
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--only", choices=["formation", "switch"])
    ap.add_argument("--out", default=os.path.join(HW, "l2", "build", "equiv"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seeds = [int(x) for x in a.seeds.split(",")]
    builds, jobs = [], []
    if a.only in (None, "formation"):
        ref = ref_copy(a.ref, "l2/wpms_formation.v", "wpms_formation", a.out)
        tb = os.path.join(a.out, "equiv_formation_tb.v")
        open(tb, "w").write(formation_bench())
        for nmax in (1008, 2048):
            exe = os.path.join(a.out, f"equiv_formation_{nmax}.vvp")
            builds.append((f"formation {nmax}", ["iverilog", "-g2012", "-I", L2, f"-Pequiv_formation_tb.NMAX={nmax}",
                           "-o", exe, ref, os.path.join(L2, "wpms_formation.v"), tb]))
            jobs += [(f"formation NMAX {nmax} seed {s}", ["vvp", "-n", exe, f"+seed={s}", f"+clocks={a.clocks}"], a.out)
                     for s in seeds]
    if a.only in (None, "switch"):
        ref = ref_copy(a.ref, "switch/wpms_switch.v", "wpms_switch", a.out)
        tb = os.path.join(a.out, "equiv_switch_tb.v")
        open(tb, "w").write(switch_bench())
        for nmax in (1008, 2048):
            exe = os.path.join(a.out, f"equiv_switch_{nmax}.vvp")
            hexf = os.path.join(SW, f"wpms_rom_origin_{nmax}.hex")
            builds.append((f"switch {nmax}", ["iverilog", "-g2012", f"-Pequiv_switch_tb.NMAX={nmax}",
                           f'-Pequiv_switch_tb.ROM_HEX="{hexf}"', "-o", exe, ref,
                           os.path.join(SW, "wpms_switch.v"), os.path.join(SW, "wpms_rom.v"), tb]))
            jobs += [(f"switch NMAX {nmax} seed {s}", ["vvp", "-n", exe, f"+seed={s}", f"+clocks={a.clocks}"], a.out)
                     for s in seeds]
    ok = True
    for name, cmd in builds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        notes = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and "is sensitive to all" not in l]
        if r.returncode or notes:
            print(f"equiv_lockstep: build {name} FAILED\n" + "\n".join(notes)); ok = False
    if not ok:
        sys.exit(1)
    print(f"equiv_lockstep: previous revisions from commit {a.ref}; {a.clocks} clocks per run — evidence class RTL-SIM")
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        for name, rc, text in ex.map(run, jobs):
            lines = [l for l in text.splitlines() if l.strip()]
            summ = [l for l in lines if l.startswith("equiv_") or l.startswith("  ")]
            bad = [l for l in lines if "MISMATCH" in l or "ERROR" in l or "WARNING" in l]
            m = re.search(r"(\d+) mismatches", text)
            good = rc == 0 and m is not None and int(m.group(1)) == 0 and not bad
            ok &= good
            print(f"[{'PASS' if good else 'FAIL'}] {name}")
            for l in summ + bad[:20]:
                print("    " + l)
    print(f"equiv_lockstep: {'PASS — cycle for cycle the same in every run' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
