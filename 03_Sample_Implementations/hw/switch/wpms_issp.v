// ============================================================================
//  wpms_issp.v — one In-System Sources and Probes instance (Intel), or its
//  simulation stand-in
//  ISSP 1 インスタンス（Intel）、またはそのシミュレーション代役
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; illustrative, not normative)
//
//  The architect's ruling of 2026-09-30: the Phase 5 host path is ISSP over
//  JTAG, read and written from the Quartus In-System Sources and Probes Editor
//  (or quartus_stp Tcl). The vendor IP is instantiated, not copied (Ch.5 §5.7,
//  Ch.4 §4.2.1: the MIT boundary).
//  VENDOR "INTEL": altsource_probe (altera_mf). The sources are a register in
//                  the JTAG domain: to the design they are ASYNCHRONOUS
//                  (enable_metastability "NO"; the users synchronize —
//                  wpms_host_bridge.v). Probes are sampled by the JTAG side.
//         "SIM"  : the sources read 0 (the IP's initial value); probes unused.
//                  The deterministic controller of the testbench drives the
//                  same bits through the OR of wpms_system.v.
//  INSTANCE_ID: up to four characters, shown by the editor (HOST, STAT, INSP).
//  SW >= 1 (a probe-only instance keeps one unused source bit).
//  Not compiled by Quartus in this session: the INTEL branch is checked in
//  Phase 6 (evidence class of its correctness until then: reading).
// ----------------------------------------------------------------------------
//  REVISION HISTORY(RH)
//  001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 5).
// ============================================================================
`timescale 1ns/1ps

module wpms_issp #(
    parameter         VENDOR      = "SIM",         // "SIM" | "INTEL"
    parameter         INSTANCE_ID = "NONE",
    parameter integer SW          = 1,             // source width, >= 1
    parameter integer PW          = 1              // probe width,  >= 1
) (
    input  wire [PW-1:0] probe,
    output wire [SW-1:0] source
);
    generate
    if (VENDOR == "INTEL") begin : g_intel
        altsource_probe #(
            .sld_auto_instance_index ("YES"),
            .sld_instance_index      (0),
            .instance_id             (INSTANCE_ID),
            .probe_width             (PW),
            .source_width            (SW),
            .source_initial_value    ("0"),
            .enable_metastability    ("NO"),
            .lpm_type                ("altsource_probe")
        ) u_issp (
            .probe  (probe),
            .source (source)
        );
    end else begin : g_sim
        assign source = {SW{1'b0}};
    end
    endgenerate
endmodule
