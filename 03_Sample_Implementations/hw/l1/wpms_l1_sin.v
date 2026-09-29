// ============================================================================
//  wpms_l1_sin.v — WPMS L1, the Maclaurin sin core (customer Ch.2 v1.1)
//  WPMS L1 — マクローリン sin コア
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  sin(2 pi phase) for one Q0.32 phase per clock, Q0.40 signed out, 16 clocks
//  later (C2-D9). Bit for bit the published model hw/tools/l1_model.py
//  sin_q040(); constants from wpms_l1_consts.vh (generated from that model).
//
//  Structure (C2-D1..D11):
//    E   quadrant = phase[31:30]; Q2/Q4 reflect: xi' = ~phase[29:0] (0.25 - xi,
//        Ch.2 §2.3.3); the sign (Q3/Q4) travels with the bin (§2.3.4)
//    R   u = xi'[29:4]        26 bits, the in-quadrant phase in cycles, 2^-28
//    0   U = (u*u) >> 26      26 bits, 2^-30                  (1 multiplier)
//    1-5 Horner, innermost first, S_j = c_j - (U * S_{j+1}) >> sh_j (S6 = c5):
//        each stage multiplies in its first clock and subtracts in its second
//        (Approach B, 2 clocks per stage)                      (5 multipliers)
//    F   v = (u * S1) >> 11, then the sign: Q0.40              (1 multiplier)
//  The 2 pi powers are absorbed into the coefficients c_j = (2 pi)^(2j+1)/(2j+1)!
//  (Ch.2 §2.9, "folded" Arena row): x' is never materialized, the last multiply
//  is by u itself. Every stage keeps its own power-of-two scale (§2.5.1
//  "pre-scaled"), so every operand holds 25-26 significant bits. All operands
//  are non-negative and at most 26 bits: seven 27x27 multipliers (C2-D7, D10).
//  Truncation toward zero (C2-D11: the values are non-negative, so a shift).
//  Max |error| vs sin(2 pi phase): 2^-24.0 (exhaustive over u, ORACLE — the
//  11th-order truncation itself; Ch.2 §2.8 budget 1.3e-7).
//
//  The core has no valid or enable: it computes every clock; the caller delays
//  its side-band (valid, routing, bin index) by LATENCY.
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-29       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 4).
// ============================================================================
`timescale 1ns/1ps

module wpms_l1_sin (
    input  wire               clk,
    input  wire [31:0]        phase,            // Q0.32 cycles, sampled every clock
    output reg  signed [40:0] sin_out           // Q0.40, for the phase of 16 clocks before
);
    localparam integer LATENCY = 16;
`include "wpms_l1_consts.vh"

    // ---- E: quadrant decode and reflection ------------------------------------------
    reg [29:0] xi_e;   reg sg_e;
    always @(posedge clk) begin
        xi_e <= phase[30] ? ~phase[29:0] : phase[29:0];
        sg_e <= phase[31];
    end

    // ---- R: u ------------------------------------------------------------------------
    reg [25:0] u_r;    reg sg_r;
    always @(posedge clk) begin
        u_r  <= xi_e[29:4];
        sg_r <= sg_e;
    end

    // ---- 0: U = u^2 (two clocks) ---------------------------------------------------------
    reg [51:0] uu_a;   reg [25:0] u_0a;   reg sg_0a;
    reg [25:0] U_0b;   reg [25:0] u_0b;   reg sg_0b;
    always @(posedge clk) begin
        uu_a <= u_r * u_r;               u_0a <= u_r;   sg_0a <= sg_r;
        U_0b <= uu_a[51:26];             u_0b <= u_0a;  sg_0b <= sg_0a;
    end

    // ---- 1..5: Horner, S_j = c_j - (U * S_{j+1}) >> sh_j -----------------------------
    // stage j: "a" clock multiplies, "b" clock subtracts; U and u travel with the bin
    reg [51:0] p1a, p2a, p3a, p4a, p5a;
    reg [25:0] S5, S4, S3, S2, S1;
    reg [25:0] U_1a, U_1b, U_2a, U_2b, U_3a, U_3b, U_4a, U_4b;
    reg [25:0] u_1a, u_1b, u_2a, u_2b, u_3a, u_3b, u_4a, u_4b, u_5a, u_5b;
    reg        s_1a, s_1b, s_2a, s_2b, s_3a, s_3b, s_4a, s_4b, s_5a, s_5b;
    always @(posedge clk) begin
        // stage 1 (innermost): S5 = c4 - U*c5
        p1a <= U_0b * SIN_C5;                                  U_1a <= U_0b; u_1a <= u_0b; s_1a <= sg_0b;
        S5  <= SIN_C4 - p1a[51:SIN_SH5];                       U_1b <= U_1a; u_1b <= u_1a; s_1b <= s_1a;
        // stage 2: S4 = c3 - U*S5
        p2a <= U_1b * S5;                                      U_2a <= U_1b; u_2a <= u_1b; s_2a <= s_1b;
        S4  <= SIN_C3 - p2a[51:SIN_SH4];                       U_2b <= U_2a; u_2b <= u_2a; s_2b <= s_2a;
        // stage 3: S3 = c2 - U*S4
        p3a <= U_2b * S4;                                      U_3a <= U_2b; u_3a <= u_2b; s_3a <= s_2b;
        S3  <= SIN_C2 - p3a[51:SIN_SH3];                       U_3b <= U_3a; u_3b <= u_3a; s_3b <= s_3a;
        // stage 4: S2 = c1 - U*S3
        p4a <= U_3b * S3;                                      U_4a <= U_3b; u_4a <= u_3b; s_4a <= s_3b;
        S2  <= SIN_C1 - p4a[51:SIN_SH2];                       U_4b <= U_4a; u_4b <= u_4a; s_4b <= s_4a;
        // stage 5 (outermost): S1 = c0 - U*S2
        p5a <= U_4b * S2;                                                    u_5a <= u_4b; s_5a <= s_4b;
        S1  <= SIN_C0 - p5a[51:SIN_SH1];                                     u_5b <= u_5a; s_5b <= s_5a;
    end

    // ---- F: v = u*S1 >> 11, sign ------------------------------------------------------
    reg [51:0] pf;     reg s_fa;
    wire [40:0] v = pf[51:SIN_SH0];                            // < 2^40 (exhaustive, l1_model.py)
    always @(posedge clk) begin
        pf      <= u_5b * S1;          s_fa <= s_5b;
        sin_out <= s_fa ? -$signed(v) : $signed(v);
    end
endmodule
