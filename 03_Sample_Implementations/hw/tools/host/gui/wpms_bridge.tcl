# ============================================================================
# wpms_bridge.tcl — OUTSIDE WPMS: a stand-in for the Layer 4 controller.
# A resident bridge between a TCP client (wpms_ctl.py, wpms_gui.py) and the
# ISSP instance HOST of hw/switch/wpms_system.v. It opens the ISSP session ONCE
# (wpms_open of ../wpms_issp_host.tcl, reused unchanged) and then serves one
# command per line on 127.0.0.1, one client at a time:
#
#   W <addr hex> <data hex>   -> OK <rdata hex> <rej 0/1> <us>   one wpms_write
#   R <addr hex>              -> OK <rdata hex> <us>             one wpms_read
#   B <n>, then n W/R lines   -> n reply lines, then END <us>    one round trip; executed in
#                                order, stopped at the first refusal or error (the rest: SKIP)
#   PING                      -> OK WPMS <ID hex> <CONFIG hex>   reads 0x000 and 0x002
#   QUIT                      -> BYE   (the client leaves; the session stays open)
#   SHUTDOWN                  -> BYE   (wpms_close, then exit)
#   anything else             -> ERR <text>
# <us> is the transaction's wall time (clock microseconds) as this process sees
# it: the JTAG round trips of one ISSP write or read, nothing of TCP.
# An ISSP error (no acknowledge, a Tcl error) answers ERR <text>; the bridge
# then sets its toggles back to the probe's acknowledges (no operation left
# pending) and keeps serving. A lost client is forgotten; the next is accepted
# without re-opening the session.
#
#   quartus_stp -t wpms_bridge.tcl [port] [--timeout ms]          (the board)
#   tclsh wpms_bridge.tcl --standin [port] [--timeout ms]          (no Quartus:
#        ../issp_standin.tcl answers the ISSP commands with the bit protocol
#        of hw/switch/wpms_host_bridge.v; a register file, not the switch)
# Port: default 50707; 0 = any free port. The line "wpms_bridge: listening on
# <addr>:<port>" tells which (hw/tools/host/gui/test_gui_bridge.py reads it).
# No `after` here: issp_standin.tcl replaces it (the demo's pauses are logged).
# License: MIT (Layer 3 tooling; not part of the WPMS design).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-14       Claude Code   Add : First version (GUI_BRIEF_WPMS_Host_Control_2026-10-14 §2).
# ============================================================================

namespace eval bridge {
    variable here [file dirname [file normalize [info script]]]
    variable port 50707
    variable standin 0
    variable timeout ""
    variable client ""
    variable done 0
}

# ---- arguments ---------------------------------------------------------------------------------
for {set i 0} {$i < [llength $::argv]} {incr i} {
    set a [lindex $::argv $i]
    if {$a eq "--standin"} {
        set ::bridge::standin 1
    } elseif {$a eq "--timeout"} {
        incr i
        set ::bridge::timeout [lindex $::argv $i]
    } elseif {[string is integer -strict $a]} {
        set ::bridge::port $a
    } else {
        puts stderr "wpms_bridge: unknown argument $a"
        exit 2
    }
}
if {$::bridge::standin && [info commands start_insystem_source_probe] eq ""} {
    source [file join $::bridge::here .. issp_standin.tcl]
}
source [file join $::bridge::here .. wpms_issp_host.tcl]
if {$::bridge::timeout ne ""} { set ::wpms::timeout_ms $::bridge::timeout }

# ---- one transaction ---------------------------------------------------------------------------
# The toggles back to the acknowledges after an ISSP error: no operation is left pending, and the
# next one starts from what the probe shows (wpms_op compares both toggles with both acknowledges).
proc bridge::resync {} {
    catch {
        lassign [wpms_probe] st rd
        scan [string index $::wpms::src 0] %x c
        set c [expr {($c & 0xC) | ($st & 3)}]
        set ::wpms::src [format %1X%s $c [string range $::wpms::src 1 end]]
        write_source_data -instance_index $::wpms::host -value $::wpms::src -value_in_hex
    }
}

proc bridge::errtext {e} { return [string map {"\n" " " "\r" " "} $e] }

# one W or R line -> {reply class}, class = ok | rej | err
proc bridge::one {line} {
    if {[regexp {^W\s+([0-9A-Fa-f]{1,3})\s+([0-9A-Fa-f]{1,8})$} $line -> a d]} {
        scan $a %x addr
        scan $d %x data
        set t0 [clock microseconds]
        if {[catch {wpms_write $addr $data} r]} {
            bridge::resync
            return [list "ERR [bridge::errtext $r]" err]
        }
        set us [expr {[clock microseconds] - $t0}]
        lassign $r rd rej
        return [list [format "OK %08X %d %d" $rd $rej $us] [expr {$rej ? "rej" : "ok"}]]
    }
    if {[regexp {^R\s+([0-9A-Fa-f]{1,3})$} $line -> a]} {
        scan $a %x addr
        set t0 [clock microseconds]
        if {[catch {wpms_read $addr} r]} {
            bridge::resync
            return [list "ERR [bridge::errtext $r]" err]
        }
        set us [expr {[clock microseconds] - $t0}]
        return [list [format "OK %08X %d" $r $us] ok]
    }
    return [list "ERR not a W or R line: [bridge::errtext $line]" err]
}

# ---- the client --------------------------------------------------------------------------------
proc bridge::drop {ch why} {
    catch {close $ch}
    if {$::bridge::client eq $ch} { set ::bridge::client "" }
    puts "wpms_bridge: client $why"
    flush stdout
}

proc bridge::accept {ch addr cport} {
    if {$::bridge::client ne ""} {
        catch {puts $ch "ERR busy: one client at a time"; close $ch}
        return
    }
    set ::bridge::client $ch
    # full buffering, one flush per request: a batch's replies leave in one write (no Nagle wait
    # behind the client's delayed acknowledge between reply lines)
    fconfigure $ch -blocking 1 -buffering full -translation {auto lf} -encoding ascii
    fileevent $ch readable [list bridge::readable $ch]
    puts "wpms_bridge: client $addr:$cport"
    flush stdout
}

proc bridge::readable {ch} {
    if {[catch {gets $ch line} n] || $n < 0} {
        if {[catch {eof $ch} e] || $e} { bridge::drop $ch lost }
        return
    }
    set line [string trim $line]
    if {$line eq ""} return
    if {[catch {bridge::serve $ch $line; if {$::bridge::client eq $ch} { flush $ch }} e]} {
        # a write to a vanished client: forget it
        bridge::drop $ch "lost ([bridge::errtext $e])"
    }
}

proc bridge::serve {ch line} {
    set cmd [string toupper [lindex [split $line] 0]]
    switch -- $cmd {
        W - R {
            puts $ch [lindex [bridge::one $line] 0]
        }
        B {
            if {![regexp {^[Bb]\s+([0-9]+)$} $line -> n] || $n < 1 || $n > 4096} {
                puts $ch "ERR bad batch header: [bridge::errtext $line]"
                return
            }
            # all n lines first (the client sends them with the header), then the transactions
            set lines {}
            for {set k 0} {$k < $n} {incr k} {
                if {[gets $ch l] < 0} { bridge::drop $ch "lost inside a batch"; return }
                lappend lines [string trim $l]
            }
            set t0 [clock microseconds]
            set stop 0
            set out {}
            foreach l $lines {
                if {$stop} { lappend out SKIP; continue }
                lassign [bridge::one $l] reply cls
                lappend out $reply
                if {$cls ne "ok"} { set stop 1 }
            }
            set us [expr {[clock microseconds] - $t0}]
            foreach r $out { puts $ch $r }
            puts $ch "END $us"
        }
        PING {
            if {[catch {list [wpms_read 0x000] [wpms_read 0x002]} r]} {
                bridge::resync
                puts $ch "ERR [bridge::errtext $r]"
            } else {
                puts $ch [format "OK WPMS %08X %08X" {*}$r]
            }
        }
        QUIT {
            puts $ch BYE
            flush $ch
            bridge::drop $ch quit
        }
        SHUTDOWN {
            puts $ch BYE
            flush $ch
            bridge::drop $ch shutdown
            set ::bridge::done 1
        }
        default {
            puts $ch "ERR unknown command: [bridge::errtext $line]"
        }
    }
}

# ---- main --------------------------------------------------------------------------------------
wpms_open
set srv [socket -server bridge::accept -myaddr 127.0.0.1 $::bridge::port]
lassign [fconfigure $srv -sockname] baddr bname bport
puts "wpms_bridge: listening on $baddr:$bport"
flush stdout
vwait ::bridge::done
close $srv
wpms_close
puts "wpms_bridge: session closed"
flush stdout
exit 0
