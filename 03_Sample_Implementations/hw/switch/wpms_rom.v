// ============================================================================
//  wpms_rom.v — the built-in ROM of the input switch (customer Ch.5 §5.8)
//  入力スイッチの内蔵 ROM
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  DEPTH words of 44 bits, {address[11:0], data[31:0]}: a list of writes that
//  port 3 plays, ending at the first word whose address is 0xFFF (Ch.5 §5.8:
//  "a short list of (address, data) writes ending in GO_ALL"). Registered
//  address, unregistered output: q is valid in the clock after addr.
//  VENDOR "SIM"  : behavioural, $readmemh(INIT_HEX)
//         "M10K" : Cyclone V altsyncram in ROM mode with run-time modification,
//                  so the In-System Memory Content Editor can overwrite it (Ch.5
//                  §5.7, §5.8: "ISMCE edits the built-in ROM"); instance TORG.
//                  A reconfiguration restores INIT_MIF: the regression anchor.
//  Contents: hw/tools/gen_switch_rom.py (the test origin, one image per NMAX).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_rom #(
    parameter integer DEPTH    = 256,
    parameter         VENDOR   = "SIM",            // "SIM" | "M10K"
    parameter         INIT_HEX = "",
    parameter         INIT_MIF = ""
) (
    input  wire                     clk,
    input  wire [$clog2(DEPTH)-1:0] addr,
    output wire [43:0]              q
);
    localparam integer AW = $clog2(DEPTH);
    generate
    if (VENDOR == "SIM") begin : g_sim
        reg [43:0] mem [0:DEPTH-1];
        reg [43:0] q_r;
        integer i;
        initial begin
            for (i = 0; i < DEPTH; i = i + 1) mem[i] = {12'hFFF, 32'd0};     // an empty list
            if (INIT_HEX != "") $readmemh(INIT_HEX, mem);
        end
        always @(posedge clk) q_r <= mem[addr];
        assign q = q_r;
    end else begin : g_m10k
        altsyncram #(
            .operation_mode          ("ROM"),
            .width_a                 (44),
            .widthad_a               (AW),
            .numwords_a              (DEPTH),
            .outdata_reg_a           ("UNREGISTERED"),
            .address_aclr_a          ("NONE"),
            .outdata_aclr_a          ("NONE"),
            .init_file               (INIT_MIF),
            .lpm_hint                ("ENABLE_RUNTIME_MOD=YES,INSTANCE_NAME=TORG"),
            .intended_device_family  ("Cyclone V"),
            .ram_block_type          ("M10K"),
            .lpm_type                ("altsyncram")
        ) u_rom (
            .clock0    (clk),
            .address_a (addr),
            .q_a       (q)
        );
    end
    endgenerate
endmodule
