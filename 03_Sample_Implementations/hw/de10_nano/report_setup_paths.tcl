# ============================================================================
# report_setup_paths.tcl — the failing setup paths of clk_sys, for the
# timing closure of the WPMS silicon sample (SILICON_BRIEF Phase 6, SD-22).
# Run in the project directory after a full compile:
#
#   quartus_sta -t report_setup_paths.tcl                    (revision DE10_Nano_wpms)
#   quartus_sta -t report_setup_paths.tcl DE10_Nano_wpms100
#
# or from the Timing Analyzer's Tcl console with the project open
# (source report_setup_paths.tcl): the open project and revision are used.
#
# Writes, in output_files/:
#   setup_clk_sys_groups.txt    every failing endpoint, grouped by register
#                               (bit and word indices folded): how many, the
#                               worst slack, the group's TNS, the logic levels
#                               and data delay of its worst path, where that
#                               path starts; then the same by start point.
#                               Small: the file to send first.
#   setup_clk_sys_keys.rpt      the worst path into each register class of
#                               the Formation's X clock and of the switch,
#                               cell by cell
#   setup_clk_sys_worst10.rpt   the ten worst endpoints, cell by cell
#   setup_clk_sys_summary.rpt   the worst 2,000 endpoints, one line each
# The slow corner (slow 1100 mV 85 C) is the one that failed.
# License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-03       Claude Code   Add : First version (SILICON_BRIEF Phase 6, timing closure).
# 002 2026-10-03       Claude Code   Add : the grouped list of every failing endpoint and the
#                                          worst path into each register class (SD-22).
# ============================================================================
set rev "DE10_Nano_wpms"
if {[info exists quartus(args)] && [llength $quartus(args)] > 0} { set rev [lindex $quartus(args) 0] }
set out output_files

set opened 0
if {![is_project_open]} {
    project_open DE10_Nano_wpms -revision $rev
    set opened 1
} else {
    set rev [get_current_revision]
}
catch {delete_timing_netlist}
create_timing_netlist -model slow
read_sdc
update_timing_netlist

# clk_sys: the output counter of u_pll_sys (no bracket in the pattern)
set sys [get_clocks {*u_pll_sys*PLL_OUTPUT_COUNTER*}]

# ---- 1. every failing endpoint, grouped -------------------------------------
proc fold {name} {
    regsub -all {\[[0-9]+\]} $name {[]} k
    regsub -all {ram_block([0-9]+)a[0-9]+} $k {ram_block\1a*} k
    return $k
}
set paths [get_timing_paths -setup -to_clock $sys -npaths 200000 -nworst 1 -less_than_slack 0.0]
set nfail 0
set tns_all 0.0
foreach_in_collection p $paths {
    incr nfail
    set s  [get_path_info $p -slack]
    set to [fold [get_node_info -name [get_path_info $p -to]]]
    set fr [fold [get_node_info -name [get_path_info $p -from]]]
    set tns_all [expr {$tns_all + $s}]
    if {![info exists cnt($to)]} { set cnt($to) 0; set tns($to) 0.0; set wst($to) 1e9 }
    incr cnt($to)
    set tns($to) [expr {$tns($to) + $s}]
    if {$s < $wst($to)} {
        set wst($to) $s
        set wfr($to) $fr
        if {[catch {get_path_info $p -num_logic_levels} lvl($to)]} { set lvl($to) "?" }
        if {[catch {get_path_info $p -data_delay} dly($to)]} { set dly($to) "?" }
    }
    if {![info exists fcnt($fr)]} { set fcnt($fr) 0; set ftns($fr) 0.0; set fwst($fr) 1e9 }
    incr fcnt($fr)
    set ftns($fr) [expr {$ftns($fr) + $s}]
    if {$s < $fwst($fr)} { set fwst($fr) $s }
}

set fh [open $out/setup_clk_sys_groups.txt w]
puts $fh "# clk_sys setup, slow model, revision $rev: $nfail failing endpoints, TNS [format %.3f $tns_all] ns"
puts $fh "# by endpoint register (bit and word indices folded to \[\]), the most negative TNS first"
puts $fh "# endpoints   worst_ns       tns_ns  levels  delay_ns  endpoint group  <-  start of its worst path"
set rows {}
foreach k [array names cnt] { lappend rows [list $tns($k) $k] }
foreach r [lsort -real -index 0 $rows] {
    set k [lindex $r 1]
    puts $fh [format "%11d %10.3f %12.3f %7s %9s  %s  <-  %s" $cnt($k) $wst($k) $tns($k) $lvl($k) $dly($k) $k $wfr($k)]
}
puts $fh ""
puts $fh "# by the start point of each endpoint's worst path"
puts $fh "# endpoints   worst_ns       tns_ns  start group"
set rows {}
foreach k [array names fcnt] { lappend rows [list $ftns($k) $k] }
foreach r [lsort -real -index 0 $rows] {
    set k [lindex $r 1]
    puts $fh [format "%11d %10.3f %12.3f  %s" $fcnt($k) $fwst($k) $ftns($k) $k]
}
close $fh

# ---- 2. the worst path into each register class -----------------------------
set keys {
    accm         {*wpms_formation:*|accm*}
    temp         {*wpms_formation:*|temp*}
    adrs         {*wpms_formation:*|adrs*}
    store        {*wpms_formation:*|g_store*}
    store_n      {*wpms_formation:*|st_n*}
    pmask        {*wpms_formation:*|pmask*}
    inbox_taken  {*wpms_formation:*|inbox_taken*}
    taken_due    {*wpms_formation:*|taken_due*}
    sweep_a      {*wpms_formation:*|sweep_a*}
    error        {*wpms_formation:*|error_*}
    switch       {*wpms_switch:*}
    sequencer    {*wpms_sequencer:*}
    core         {*ptsg_core:*}
    l1           {*wpms_l1_module:*}
}
set fk $out/setup_clk_sys_keys.rpt
file delete -force $fk
foreach {tag pat} $keys {
    set regs [get_registers -nowarn $pat]
    if {[get_collection_size $regs] == 0} {
        post_message -type warning "report_setup_paths.tcl: no register matches $pat ($tag)"
        continue
    }
    if {[catch {report_timing -setup -to_clock $sys -to $regs -npaths 1 -detail full_path \
                    -file $fk -append -panel_name "clk_sys setup: $tag"} msg]} {
        post_message -type warning "report_setup_paths.tcl: $tag: $msg"
    }
}

# ---- 3. the ten worst endpoints, and the worst 2,000 in one line each -------
report_timing -setup -to_clock $sys -npaths 10 -nworst 1 -detail full_path \
    -file $out/setup_clk_sys_worst10.rpt -panel_name {clk_sys setup: worst 10}
report_timing -setup -to_clock $sys -npaths 2000 -nworst 1 -detail summary \
    -file $out/setup_clk_sys_summary.rpt -panel_name {clk_sys setup: summary}

post_message -type info "report_setup_paths.tcl ($rev): $nfail failing endpoints; output_files/setup_clk_sys_{groups.txt,keys.rpt,worst10.rpt,summary.rpt}"

delete_timing_netlist
if {$opened} { project_close }
