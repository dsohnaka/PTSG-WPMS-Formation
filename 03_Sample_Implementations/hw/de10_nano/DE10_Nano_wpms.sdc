#**************************************************************
# DE10_Nano_wpms.sdc -- timing constraints of the WPMS silicon sample
# on the Terasic DE10-nano (5CSEBA6U23I7), both revisions:
#   DE10_Nano_wpms     clk_sys  50 MHz (NMAX 1,008)
#   DE10_Nano_wpms100  clk_sys 100 MHz (NMAX 2,048)
# License: MIT (Layer 3 sample implementation).
#
# Started from the Core's harness (PTSG-Core/03_Sample_Implementations/
# board_harnesses/de10_nano/DE10_Nano_golden_top.sdc, RH029): the same
# base clocks, derive_pll_clocks, the JTAG clock and its I/O, the human
# I/O cut. Added for WPMS:
#   * the clock domains as asynchronous groups. Every crossing between
#     them is synchronized in the RTL: resets and DIP/KEY by 2-FF levels,
#     the L3 strobe clk_aud -> clk_sys by a 2-FF toggle (wpms_strobe_sync),
#     the output bank clk_sys -> clk_aud by its stability window (written
#     a few clocks after the strobe, captured a frame later; C4-D7), the
#     ISSP host bits by 2-FF + settle (wpms_host_bridge). The groups are
#     found by the PLL instance names (u_pll_sys, u_pll_aud, u_pll_pix)
#     inside the clock names, so no full name that derive_pll_clocks
#     invents is spelled out here.
#   * the HDMI pixel bus as a source-synchronous output against the
#     forwarded HDMI_TX_CLK (ADV7513 data sheet Rev. B p. 3: set-up
#     t_VSU 1.8 ns, hold t_VHLD 1.3 ns), the clock being the pixel PLL's
#     second output, half a period late.
#
# ---- The imem half-cycle path stays as it is -------------------------
# As in the Core's harness: ptsg_imem (VENDOR "M10K", EDGE "NEG") is
# clocked on the falling edge of clk_sys, so TimeQuest analyzes two
# genuine half-period paths (core -> M10K address, M10K q -> core). At
# 100 MHz that is 5 ns each way, the expected critical path of the
# 100 MHz revision. No multicycle path relaxes it (the brief: no waiver);
# if it fails, the 50 MHz revision is the effective target (rulings
# 2026-09-28/29).
#
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF_2026-09-27 Phase 6).
#**************************************************************

#**************************************************************
# Create Clock
#**************************************************************

create_clock -name {FPGA_CLK1_50} -period 20.000 [get_ports FPGA_CLK1_50]
create_clock -name {FPGA_CLK2_50} -period 20.000 [get_ports FPGA_CLK2_50]
create_clock -name {FPGA_CLK3_50} -period 20.000 [get_ports FPGA_CLK3_50]

# JTAG TCK (USB-Blaster II): ISMCE (the score and ROM images), the ISSP
# instances (HOST, BRD) and SignalTap live in this domain.
create_clock -name {altera_reserved_tck} -period 40.000 [get_ports altera_reserved_tck]

#**************************************************************
# Create Generated Clock
#**************************************************************

# u_pll_sys: clk_sys from FPGA_CLK1_50; u_pll_aud: MCLK 12.288 MHz from
# FPGA_CLK2_50 (fractional); u_pll_pix: 74.25 MHz at 0 and at 180 degrees
# from FPGA_CLK3_50 (fractional).
derive_pll_clocks

# The PLL clocks, sorted by the PLL instance in their names (derive_pll_clocks
# names each clock after its PLL atom: u_pll_sys|..., the VCO phase clock and
# the output counter clocks alike); the pixel PLL's two outputs told apart by
# their rising edge (0 ns, or half a period).
set wpms_sys {}
set wpms_aud {}
set wpms_pix {}
set wpms_pix_tx ""
foreach_in_collection wpms_c [get_clocks *] {
    set wpms_n [get_clock_info -name $wpms_c]
    if {[string match "*u_pll_sys*" $wpms_n]} { lappend wpms_sys $wpms_n }
    if {[string match "*u_pll_aud*" $wpms_n]} { lappend wpms_aud $wpms_n }
    if {[string match "*u_pll_pix*" $wpms_n]} {
        lappend wpms_pix $wpms_n
        if {[lindex [get_clock_info -waveform $wpms_c] 0] > 3.0} { set wpms_pix_tx $wpms_n }
    }
}
post_message -type info "DE10_Nano_wpms.sdc: clk_sys {$wpms_sys}; clk_aud {$wpms_aud}; pixel {$wpms_pix}; forwarded {$wpms_pix_tx}"

# HDMI_TX_CLK: the 180-degree pixel clock on its pin
if {$wpms_pix_tx ne ""} {
    if {[catch {create_generated_clock -name {hdmi_tx_clk} \
                    -source [get_clock_info -targets [get_clocks $wpms_pix_tx]] \
                    [get_ports {HDMI_TX_CLK}]} wpms_err]} {
        post_message -type critical_warning "DE10_Nano_wpms.sdc: hdmi_tx_clk not created ($wpms_err)"
        set wpms_pix_tx ""
    }
}
if {$wpms_pix_tx eq ""} {
    post_message -type critical_warning "DE10_Nano_wpms.sdc: no forwarded pixel clock; HDMI_TX_CLK and the pixel bus are left unconstrained"
}

#**************************************************************
# Set Clock Uncertainty
#**************************************************************
derive_clock_uncertainty

#**************************************************************
# Set Input Delay
#**************************************************************

set_input_delay -clock altera_reserved_tck -clock_fall 3.000 [get_ports altera_reserved_tdi]
set_input_delay -clock altera_reserved_tck -clock_fall 3.000 [get_ports altera_reserved_tms]

#**************************************************************
# Set Output Delay
#**************************************************************

set_output_delay -clock altera_reserved_tck 3.000 [get_ports altera_reserved_tdo]

# The pixel bus against HDMI_TX_CLK: the ADV7513's set-up and hold
# (t_VSU 1.8 ns, t_VHLD 1.3 ns at 0xBA[7:5] = 011, no delay: the
# configurator leaves it there), plus a board allowance for the trace
# mismatch between the clock and the data lines.
set wpms_tvsu   1.8
set wpms_tvhld  1.3
set wpms_board  0.2
if {$wpms_pix_tx ne ""} {
    set_output_delay -clock {hdmi_tx_clk} -max [expr {$wpms_tvsu + $wpms_board}] \
        [get_ports {HDMI_TX_D[*] HDMI_TX_DE HDMI_TX_HS HDMI_TX_VS}]
    set_output_delay -clock {hdmi_tx_clk} -min [expr {-($wpms_tvhld + $wpms_board)}] \
        [get_ports {HDMI_TX_D[*] HDMI_TX_DE HDMI_TX_HS HDMI_TX_VS}]
}

#**************************************************************
# Set Clock Groups
#**************************************************************

# tck | FPGA_CLK1_50 (power-on counter, ADV7513 configurator) | clk_sys |
# FPGA_CLK2_50 + clk_aud | FPGA_CLK3_50 + the pixel clocks + hdmi_tx_clk.
# Every crossing is synchronized in the RTL (header).
set wpms_groups [list -group [get_clocks {altera_reserved_tck}] -group [get_clocks {FPGA_CLK1_50}]]
if {[llength $wpms_sys]} { lappend wpms_groups -group [get_clocks $wpms_sys] }
lappend wpms_groups -group [get_clocks [concat {FPGA_CLK2_50} $wpms_aud]]
set wpms_pixg [concat {FPGA_CLK3_50} $wpms_pix]
if {$wpms_pix_tx ne ""} { lappend wpms_pixg {hdmi_tx_clk} }
lappend wpms_groups -group [get_clocks $wpms_pixg]
set_clock_groups -asynchronous {*}$wpms_groups

#**************************************************************
# Set False Path
#**************************************************************

# Human/static I/O: push-buttons, slide switches, LEDs (each input passes
# a 2-FF synchronizer in its domain).
set_false_path -from [get_ports {KEY[*]}]
set_false_path -from [get_ports {SW[*]}]
set_false_path -to   [get_ports {LED[*]}]

# ADV7513 control: I2C at 100 kHz, open drain, inputs through 2 FFs in
# the FPGA_CLK1_50 domain; the interrupt line is only a BRD probe.
set_false_path -from [get_ports {HDMI_I2C_SCL HDMI_I2C_SDA}]
set_false_path -to   [get_ports {HDMI_I2C_SCL HDMI_I2C_SDA}]
set_false_path -from [get_ports {HDMI_TX_INT}]

# I2S to the ADV7513: SCLK, LRCLK and data are registers of clk_aud
# (MCLK); data and LRCLK change with SCLK's falling edge and are sampled
# on its rising edge 2 MCLK = 162.8 ns later, against a 2 ns set-up/hold
# (data sheet Rev. B p. 4): met by construction, not by placement. MCLK
# itself is clk_aud forwarded to its pin.
set_false_path -to [get_ports {HDMI_SCLK HDMI_LRCLK HDMI_I2S HDMI_MCLK}]

#**************************************************************
# Set Multicycle Path
#**************************************************************

# (deliberately none -- see the header note on the imem half-cycle path)
