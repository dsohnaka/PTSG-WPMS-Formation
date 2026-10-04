# ============================================================================
# wpms_issp_host.tcl — OUTSIDE WPMS: a stand-in for the Layer 4 controller.
# The host path of the Phase 5 switch (architect's ruling of 2026-09-30):
# quartus_stp's In-System Sources and Probes Tcl API on the ISSP instance HOST
# of hw/switch/wpms_system.v, with the protocol of hw/switch/wpms_host_bridge.v:
#
#   source (48 bits) = {00, RD, WR, ADDR[11:0], WDATA[31:0]}   hex: C AAA DDDDDDDD
#   probe  (36 bits) = {0, REJ, RD_ACK, WR_ACK, RDATA[31:0]}   hex: S RRRRRRRR
#   write: set ADDR/WDATA and flip WR in one source write; wait until WR_ACK = WR;
#          RDATA is the word read back, REJ = 1 if the switch refused the write.
#   read:  set ADDR and flip RD; wait until RD_ACK = RD; RDATA is the word.
#
# The same protocol works by hand in the Quartus In-System Sources and Probes
# Editor (Tools > In-System Sources and Probes Editor): edit the HOST source as
# hex, flipping bit 44 (WR) or bit 45 (RD) in the same edit, then read the probe.
#
# Procedures: wpms_open, wpms_close, wpms_write addr data -> {rdata rej},
# wpms_read addr -> rdata, wpms_w / wpms_q (the same, with a log line),
# wpms_wait_applied (poll APPLIED_SEQ until it equals GO_SEQ), wpms_status.
# Word addresses are customer Ch.5 §5.6's (e.g. 0x200 + 16 b + i = INBOX[b][i]).
#
# First run against Quartus on the board on 2026-10-04 (Phase 6): Quartus refuses
# get_insystem_source_probe_instance_info while a session is open, so wpms_open
# reads the instance list before start_insystem_source_probe (RH002). The
# command names are those of Quartus Prime's ::quartus::insystem_source_probe
# package. Run here under tclsh against stand-ins of those commands
# (issp_standin.tcl, check_host_tcl.py); the steps it plays are checked in
# RTL-SIM through the identical bit protocol (cosim_switch.py --case music).
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# 002 2026-10-04       Claude Code   Fix : wpms_open reads the instance list before it starts the session
#                                          (Quartus: "There is already an active In-System Sources and Probes
#                                          session started", met by the architect at the C2 capture).
# ============================================================================

namespace eval wpms {
    variable hw ""
    variable dev ""
    variable host -1
    variable stat -1
    variable src "000000000000"
    variable timeout_ms 2000
}

proc wpms_open {{hw_name ""} {dev_name ""}} {
    set hws [get_hardware_names]
    if {$hw_name eq ""} { set hw_name [lindex $hws 0] }
    set devs [get_device_names -hardware_name $hw_name]
    if {$dev_name eq ""} {
        # the DE10-nano's JTAG chain: the HPS first, then the FPGA (5CSE)
        foreach d $devs { if {[string match "*5CSE*" $d]} { set dev_name $d } }
        if {$dev_name eq ""} { set dev_name [lindex $devs end] }
    }
    set ::wpms::hw $hw_name
    set ::wpms::dev $dev_name
    # the instance list first: Quartus refuses it while a session is open (RH002)
    set insts [get_insystem_source_probe_instance_info -device_name $dev_name -hardware_name $hw_name]
    start_insystem_source_probe -device_name $dev_name -hardware_name $hw_name
    foreach inst $insts {
        # each entry: {index source_width probe_width name}
        set idx [lindex $inst 0]; set name [lindex $inst 3]
        if {$name eq "HOST"} { set ::wpms::host $idx }
        if {$name eq "STAT"} { set ::wpms::stat $idx }
    }
    if {$::wpms::host < 0} { error "wpms_open: no ISSP instance named HOST on $dev_name" }
    set ::wpms::src [wpms_pad [read_source_data -instance_index $::wpms::host -value_in_hex] 12]
    puts "wpms: $hw_name / $dev_name, HOST = instance $::wpms::host, source $::wpms::src"
}

proc wpms_close {} { end_insystem_source_probe }

# a hex string, upper case, left-padded with zeros to n digits
proc wpms_pad {h n} {
    set h [string toupper [string trim $h]]
    if {[string length $h] < $n} { set h "[string repeat 0 [expr {$n - [string length $h]}]]$h" }
    return $h
}

# the probe as {status rdata}: status bit 0 WR_ACK, bit 1 RD_ACK, bit 2 REJ
proc wpms_probe {} {
    set p [wpms_pad [read_probe_data -instance_index $::wpms::host -value_in_hex] 9]
    scan [string index $p 0] %x st
    scan [string range $p 1 8] %x rd
    return [list $st $rd]
}

proc wpms_op {bit addr data} {
    scan [string index $::wpms::src 0] %x c
    set c [expr {$c ^ (1 << $bit)}]
    set ::wpms::src [format "%1X%03X%08X" $c [expr {$addr & 0xFFF}] [expr {$data & 0xFFFFFFFF}]]
    write_source_data -instance_index $::wpms::host -value $::wpms::src -value_in_hex
    set want [expr {($c >> $bit) & 1}]
    set t0 [clock milliseconds]
    while 1 {
        lassign [wpms_probe] st rd
        # both acknowledges must equal both toggles (an operation is finished)
        if {($st & 3) == ($c & 3)} { return [list $rd [expr {($st >> 2) & 1}]] }
        if {[clock milliseconds] - $t0 > $::wpms::timeout_ms} { error [format "wpms: no acknowledge (addr 0x%03X)" $addr] }
    }
}

proc wpms_write {addr data} { return [wpms_op 0 $addr $data] }
proc wpms_read  {addr}      { return [lindex [wpms_op 1 $addr 0] 0] }

proc wpms_w {addr data {note ""}} {
    lassign [wpms_write $addr $data] rd rej
    puts [format "W %03X %08X -> %08X%s  %s" $addr $data $rd [expr {$rej ? " REFUSED" : ""}] $note]
    return $rej
}
proc wpms_q {addr {note ""}} {
    set rd [wpms_read $addr]
    puts [format "R %03X -> %08X  %s" $addr $rd $note]
    return $rd
}

# wait until the last GO has been applied (Ch.5 §5.4.2 step 4): APPLIED_SEQ = GO_SEQ
proc wpms_wait_applied {{note ""}} {
    set go [wpms_read 0x009]
    set t0 [clock milliseconds]
    while {[wpms_read 0x00A] != $go} {
        if {[clock milliseconds] - $t0 > $::wpms::timeout_ms} { error "wpms: GO $go not applied" }
    }
    puts [format "   applied GO %d at sweep %d  %s" $go [wpms_read 0x00B] $note]
}

proc wpms_status {} {
    foreach {a n} {0x009 GO_SEQ 0x00A APPLIED_SEQ 0x00B APPLIED_SAMPLE 0x012 MG 0x014 G_EFF 0x016 CLIP
                   0x018 STROBE_INTERVAL 0x030 REJECT0 0x033 REJECT3 0x292 SWEEP_ACTIVE 0x298 SWEEP_CLOCKS} {
        puts [format "  %-16s %08X" $n [wpms_read $a]]
    }
}
