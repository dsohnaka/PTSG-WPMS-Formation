# ============================================================================
# issp_standin.tcl — OUTSIDE WPMS: stand-ins for the Quartus Prime commands
# wpms_issp_host.tcl calls, so the host script can run under a plain tclsh
# where Quartus is absent (hw/tools/host/check_host_tcl.py drives it).
#
# The HOST instance behaves as hw/switch/wpms_host_bridge.v does:
#   * nothing happens while WR = WR_ACK and RD = RD_ACK; flipping one toggle
#     makes one transaction on the fields of that same source write;
#   * a write is followed by its read-back; RDATA and REJ change before the
#     acknowledge moves, the acknowledge shows `delay` probe reads later;
#   * at start the acknowledges equal the toggles (no replay).
# Behind it stands a small register file, not the switch: ID, VERSION,
# CONFIG as at reset; GO_SEQ counts GO / GO_ALL / go-now / TEST_ORIGIN;
# APPLIED_SEQ catches up with GO_SEQ on the second poll after a GO.
# The switch's own semantics are checked in RTL-SIM (hw/tools/cosim_switch.py);
# this file checks only the script's use of the bit protocol and of the API.
#
# Knobs (set after sourcing): standin::delay (probe reads before an
# acknowledge shows), standin::ragged (1: answers in lower case without
# leading zeros), standin::dead (1: never acknowledge), standin::refuse
# (word addresses whose writes are refused), standin::src (the source value
# left by an earlier session; the acknowledges follow it), standin::logfile
# (the transactions, written by end_insystem_source_probe).
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-30       Claude Code   Add : First version (SILICON_BRIEF Phase 5).
# 002 2026-10-04       Claude Code   Chg : as Quartus, no instance list and no second start while a session
#                                          is open (the board's first run, 2026-10-04).
# ============================================================================

namespace eval standin {
    variable host 1
    variable src 0
    variable wr_ack 0
    variable rd_ack 0
    variable rej 0
    variable rdata 0
    variable pend {}
    variable wait 0
    variable delay 0
    variable ragged 0
    variable dead 0
    variable refuse {}
    variable log {}
    variable logfile ""
    variable started 0
    variable mem [dict create 0 0x57504D53 1 0x00010000 2 0x0003F081]
    variable go_seq 1
    variable applied_seq 1
    variable polls 0
}

proc standin::opt {argl name} {
    set i [lsearch -exact $argl "-$name"]
    if {$i < 0 || $i + 1 >= [llength $argl]} { error "stand-in: option -$name missing in {$argl}" }
    return [lindex $argl [expr {$i + 1}]]
}
proc standin::flag {argl name} { return [expr {[lsearch -exact $argl "-$name"] >= 0}] }

proc standin::hex {v n} {
    if {$::standin::ragged} { return [string tolower [format %lX $v]] }
    return [format %0${n}lX $v]
}

proc standin::instance {argl} {
    set idx [standin::opt $argl instance_index]
    if {!$::standin::started} { error "stand-in: no start_insystem_source_probe" }
    if {![standin::flag $argl value_in_hex]} { error "stand-in: -value_in_hex expected" }
    return $idx
}

# the (acknowledged or pending) state of the acknowledges
proc standin::acks {} {
    if {[llength $::standin::pend]} { return [lrange $::standin::pend 0 1] }
    return [list $::standin::wr_ack $::standin::rd_ack]
}

proc standin::rd {addr} {
    switch -- $addr {
        9  { return $::standin::go_seq }
        10 { return $::standin::applied_seq }
        11 { return [expr {1000 + $::standin::applied_seq}] }
        8  { return 0 }
    }
    if {[dict exists $::standin::mem $addr]} { return [dict get $::standin::mem $addr] }
    return 0
}

proc standin::do_write {addr data} {
    lappend ::standin::log [format "W %03X %08X" $addr $data]
    if {$addr in $::standin::refuse} { return [list 1 [standin::rd $addr]] }
    if {$addr == 0x008} {
        if {$data & 3} { incr ::standin::go_seq; set ::standin::polls 0 }
    } elseif {$addr == 0x01C} {
        # TEST_ORIGIN: the ROM plays its list (MG_TARGET = 0, ..., GO_ALL)
        if {$data & 1} { dict set ::standin::mem 16 0; incr ::standin::go_seq; set ::standin::polls 0 }
    } elseif {($addr >= 0x288 && $addr <= 0x28F) || $addr == 0x291} {
        dict set ::standin::mem $addr [expr {$data & 0x7FFFFFFF}]
        if {($data >> 31) & 1} { incr ::standin::go_seq; set ::standin::polls 0 }
    } else {
        dict set ::standin::mem $addr $data
    }
    return [list 0 [standin::rd $addr]]
}

proc standin::do_read {addr} {
    lappend ::standin::log [format "R %03X" $addr]
    if {$addr == 10 && $::standin::applied_seq != $::standin::go_seq} {
        if {[incr ::standin::polls] >= 2} { set ::standin::applied_seq $::standin::go_seq }
    }
    return [standin::rd $addr]
}

# ---- the Quartus Prime commands the host script uses -------------------------------------------
proc get_hardware_names {} { return [list "DE-SoC \[USB-1\]"] }

proc get_device_names {args} {
    standin::opt $args hardware_name
    return [list "@1: SOCVHPS (0x4BA00477)" "@2: 5CSEBA6(.|ES)/5CSEMA6/.. (0x02D020DD)"]
}

proc start_insystem_source_probe {args} {
    if {$::standin::started} { error "There is already an active In-System Sources and Probes session started. Unable to start another session." }
    set dev [standin::opt $args device_name]
    standin::opt $args hardware_name
    if {![string match "*5CSE*" $dev]} { error "stand-in: the FPGA is 5CSEBA6, not $dev" }
    set ::standin::started 1
    set ::standin::wr_ack [expr {($::standin::src >> 44) & 1}]
    set ::standin::rd_ack [expr {($::standin::src >> 45) & 1}]
}

proc end_insystem_source_probe {} {
    set ::standin::started 0
    if {$::standin::logfile ne ""} {
        set f [open $::standin::logfile w]
        foreach l $::standin::log { puts $f $l }
        close $f
    }
}

proc get_insystem_source_probe_instance_info {args} {
    # Quartus opens a session of its own for this, so it fails while one is open
    if {$::standin::started} { error "There is already an active In-System Sources and Probes session started. Unable to start another session." }
    standin::opt $args device_name
    standin::opt $args hardware_name
    # {index source_width probe_width name}; HOST deliberately not first
    return [list {0 1 128 STAT} [list $::standin::host 48 36 HOST] {2 1 96 INSP}]
}

proc read_source_data {args} {
    if {[standin::instance $args] != $::standin::host} { error "stand-in: only HOST is read" }
    return [standin::hex $::standin::src 12]
}

proc write_source_data {args} {
    if {[standin::instance $args] != $::standin::host} { error "stand-in: only HOST is written" }
    set v [standin::opt $args value]
    if {![regexp {^[0-9A-Fa-f]{1,12}$} $v]} { error "stand-in: not a 48-bit hex value: $v" }
    scan $v %lx new
    if {$new >> 46} { error "stand-in: bits 47:46 must stay 0 ($v)" }
    set ::standin::src $new
    set wr [expr {($new >> 44) & 1}]
    set rd [expr {($new >> 45) & 1}]
    lassign [standin::acks] wa ra
    set go_w [expr {$wr != $wa}]
    set go_r [expr {$rd != $ra}]
    if {!$go_w && !$go_r} return
    if {[llength $::standin::pend]} { error "stand-in: a new operation before the last one was acknowledged" }
    if {$go_w && $go_r} { error "stand-in: WR and RD flipped in one write" }
    if {$::standin::dead} return
    set addr [expr {($new >> 32) & 0xFFF}]
    set data [expr {$new & 0xFFFFFFFF}]
    if {$go_w} {
        lassign [standin::do_write $addr $data] rj rb
        set ::standin::pend [list $wr $ra $rj $rb]
    } else {
        set ::standin::pend [list $wa $rd 0 [standin::do_read $addr]]
    }
    # RDATA and REJ first, the acknowledge `delay` probe reads later
    set ::standin::rej [lindex $::standin::pend 2]
    set ::standin::rdata [lindex $::standin::pend 3]
    set ::standin::wait $::standin::delay
}

proc read_probe_data {args} {
    if {[standin::instance $args] != $::standin::host} { error "stand-in: only HOST is read" }
    if {[llength $::standin::pend]} {
        if {$::standin::wait > 0} {
            incr ::standin::wait -1
        } else {
            lassign $::standin::pend ::standin::wr_ack ::standin::rd_ack
            set ::standin::pend {}
        }
    }
    set p [expr {($::standin::rej << 34) | ($::standin::rd_ack << 33) | ($::standin::wr_ack << 32) | $::standin::rdata}]
    return [standin::hex $p 9]
}

# the demo's pauses are logged, not slept
rename after standin::real_after
proc after {ms args} { lappend ::standin::log "S $ms" }
