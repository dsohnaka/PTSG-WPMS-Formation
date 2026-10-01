// ============================================================================
//  wpms_pll.v — one Cyclone V fractional PLL (altera_pll, direct instantiation)
//  PLL 1 基（altera_pll の直接インスタンス）
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  SILICON_BRIEF_2026-09-27 Phase 6. The same primitive the PLL IP generator
//  wraps, instantiated directly as in the Core's DE10-nano harness
//  (DE10_Nano_ptsg100_top.v); `derive_pll_clocks` in the SDC creates the
//  generated clocks from it. Up to two outputs:
//    OUT0 / PHASE0   e.g. "100.000000 MHz" / "0 ps"
//    OUT1 / PHASE1   "0 MHz" = unused; e.g. the HDMI transmit clock, the pixel
//                    clock shifted by half a period
//  FRACTIONAL = "true" lets the VCO multiplier be fractional (12.288 MHz from
//  50 MHz has no small integer ratio); "false" for the integer ratios.
//  VENDOR "INTEL" instantiates altera_pll; "SIM" instantiates wpms_pll_sim
//  (de10_nano/sim/wpms_pll_sim.v, the board-level bench only — it holds the
//  delays and is never given to Quartus).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
// ============================================================================
`timescale 1ns/1ps

module wpms_pll #(
    parameter         VENDOR     = "INTEL",            // "INTEL" | "SIM"
    parameter         FRACTIONAL = "false",
    parameter integer NCLK       = 1,                  // 1 or 2 outputs
    parameter         OUT0       = "50.000000 MHz",
    parameter         PHASE0     = "0 ps",
    parameter         OUT1       = "0 MHz",
    parameter         PHASE1     = "0 ps",
    parameter integer SIM_HALF0_PS = 10000,            // SIM: half period of outclk0
    parameter integer SIM_SHIFT1_PS = 0,               // SIM: outclk1 = outclk0 delayed by this
    parameter integer SIM_LOCK_NS  = 1000              // SIM: lock after this time
) (
    input  wire refclk,
    input  wire rst,
    output wire outclk0,
    output wire outclk1,
    output wire locked
);
    generate
        if (VENDOR == "INTEL") begin : g_intel
            wire [1:0] oc;
            if (NCLK == 2) begin : g_two
                altera_pll #(
                    .fractional_vco_multiplier (FRACTIONAL),
                    .reference_clock_frequency ("50.0 MHz"),
                    .operation_mode            ("direct"),
                    .number_of_clocks          (2),
                    .output_clock_frequency0   (OUT0),
                    .phase_shift0              (PHASE0),
                    .duty_cycle0               (50),
                    .output_clock_frequency1   (OUT1),
                    .phase_shift1              (PHASE1),
                    .duty_cycle1               (50),
                    .pll_type                  ("General"),
                    .pll_subtype               ("General")
                ) u_pll (
                    .refclk   (refclk),
                    .rst      (rst),
                    .outclk   (oc),
                    .locked   (locked),
                    .fboutclk (),
                    .fbclk    (1'b0)
                );
            end else begin : g_one
                altera_pll #(
                    .fractional_vco_multiplier (FRACTIONAL),
                    .reference_clock_frequency ("50.0 MHz"),
                    .operation_mode            ("direct"),
                    .number_of_clocks          (1),
                    .output_clock_frequency0   (OUT0),
                    .phase_shift0              (PHASE0),
                    .duty_cycle0               (50),
                    .pll_type                  ("General"),
                    .pll_subtype               ("General")
                ) u_pll (
                    .refclk   (refclk),
                    .rst      (rst),
                    .outclk   (oc[0]),
                    .locked   (locked),
                    .fboutclk (),
                    .fbclk    (1'b0)
                );
                assign oc[1] = 1'b0;
            end
            assign outclk0 = oc[0];
            assign outclk1 = oc[1];
        end else begin : g_sim
            wpms_pll_sim #(.HALF0_PS(SIM_HALF0_PS), .SHIFT1_PS(SIM_SHIFT1_PS), .LOCK_NS(SIM_LOCK_NS)) u_pll (
                .rst(rst), .outclk0(outclk0), .outclk1(outclk1), .locked(locked));
        end
    endgenerate
endmodule
