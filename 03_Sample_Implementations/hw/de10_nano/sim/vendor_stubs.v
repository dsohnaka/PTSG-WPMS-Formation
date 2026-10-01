// ============================================================================
//  vendor_stubs.v — stand-ins of the Intel primitives the board top
//  instantiates in its "INTEL" branches (altera_pll, altsyncram,
//  altsource_probe): their ports and the parameters the WPMS sources pass,
//  no behaviour (outputs 0). For an elaboration of the board top exactly as
//  Quartus is given it (hw/tools/cosim_board.py --elab): every INTEL branch
//  compiled, and each primitive prints the parameters it received, so the
//  strings the PLLs and memories will see are checked before Quartus does.
//  Never given to Quartus.
//  License: MIT (Layer 3 tooling).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
// ============================================================================
`timescale 1ns/1ps

module altera_pll #(
    parameter         fractional_vco_multiplier = "false",
    parameter         reference_clock_frequency = "",
    parameter         operation_mode            = "",
    parameter integer number_of_clocks          = 1,
    parameter         output_clock_frequency0   = "",
    parameter         phase_shift0              = "",
    parameter integer duty_cycle0               = 50,
    parameter         output_clock_frequency1   = "",
    parameter         phase_shift1              = "",
    parameter integer duty_cycle1               = 50,
    parameter         pll_type                  = "",
    parameter         pll_subtype               = ""
) (
    input  wire                        refclk,
    input  wire                        rst,
    output wire [number_of_clocks-1:0] outclk,
    output wire                        locked,
    output wire                        fboutclk,
    input  wire                        fbclk
);
    assign outclk = {number_of_clocks{1'b0}};
    assign locked = 1'b0;
    assign fboutclk = 1'b0;
    initial $display("STUB altera_pll %m | fractional=%0s | ref=%0s | mode=%0s | n=%0d | out0=%0s | phase0=%0s | out1=%0s | phase1=%0s",
                     fractional_vco_multiplier, reference_clock_frequency, operation_mode, number_of_clocks,
                     output_clock_frequency0, phase_shift0,
                     number_of_clocks > 1 ? output_clock_frequency1 : "-", number_of_clocks > 1 ? phase_shift1 : "-");
endmodule

module altsyncram #(
    parameter         operation_mode         = "ROM",
    parameter integer width_a                = 1,
    parameter integer widthad_a              = 1,
    parameter integer numwords_a             = 1,
    parameter         outdata_reg_a          = "UNREGISTERED",
    parameter         address_aclr_a         = "NONE",
    parameter         outdata_aclr_a         = "NONE",
    parameter         init_file              = "",
    parameter         lpm_hint               = "",
    parameter         intended_device_family = "",
    parameter         ram_block_type         = "",
    parameter         lpm_type               = "altsyncram"
) (
    input  wire                 clock0,
    input  wire [widthad_a-1:0] address_a,
    output wire [width_a-1:0]   q_a
);
    assign q_a = {width_a{1'b0}};
    initial $display("STUB altsyncram %m | mode=%0s | %0d x %0d | init=%0s | hint=%0s | block=%0s",
                     operation_mode, numwords_a, width_a, init_file, lpm_hint, ram_block_type);
endmodule

module altsource_probe #(
    parameter         sld_auto_instance_index = "YES",
    parameter integer sld_instance_index      = 0,
    parameter         instance_id             = "NONE",
    parameter integer probe_width             = 1,
    parameter integer source_width            = 1,
    parameter         source_initial_value    = "0",
    parameter         enable_metastability    = "NO",
    parameter         lpm_type                = "altsource_probe"
) (
    input  wire [probe_width-1:0]  probe,
    output wire [source_width-1:0] source
);
    assign source = {source_width{1'b0}};
    initial $display("STUB altsource_probe %m | id=%0s | sources=%0d | probes=%0d", instance_id, source_width, probe_width);
endmodule
