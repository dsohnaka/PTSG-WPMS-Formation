#!/usr/bin/env python3
# ============================================================================
# make_quartus_project.py — the Quartus Prime project of the WPMS silicon
# sample (SILICON_BRIEF_2026-09-27 Phase 6): one flat directory holding every
# source, include file and memory image, the SDC, and two revisions of one
# project, as the Core's harness keeps its files side by side.
#
#   python3 make_quartus_project.py [--out DIR] [--check [--mutants]] [--tclsh tclsh8.6]
#
#   DE10_Nano_wpms      SYS_MHZ  50: clk_sys 50 MHz, NMAX 1,008 (the
#                       effective target, rulings 2026-09-28/29)
#   DE10_Nano_wpms100   SYS_MHZ 100: clk_sys 100 MHz, NMAX 2,048
#
# The revisions differ in one integer (set_parameter -name SYS_MHZ); the top
# derives the PLL frequency and the ROM image from it. Also copied: the
# injection images (inject/, for the In-System Memory Content Editor) and the
# host scripts (host/, for quartus_stp). MANIFEST.txt records each file's
# source and SHA-256, and the commit it was taken from.
#
# --check also runs the project's Tcl (both .qsf and the .sdc) under a plain
# tclsh against stand-ins of the Quartus commands, with the clock names
# derive_pll_clocks gives a Cyclone V altera_pll, and checks: every port of
# the top has one pin and an I/O standard, no pin twice, the pins equal the
# Terasic golden top's (the Core's .qsf, when the Core is beside us), every
# file named exists, and the SDC finds the three PLLs, the forwarded clock,
# and puts every clock in exactly one asynchronous group. It then elaborates
# the project's Verilog (the very files Quartus gets) with Icarus, the INTEL
# branches taken and the Intel primitives stood in (sim/vendor_stubs.v), and
# checks the parameters each PLL, memory and ISSP instance receives, per
# revision. --mutants: seven broken copies of the project (a pin, a file,
# four SDC defects, an I/O standard), each of which --check must catch.
# A stand-in is not Quartus: this proves the Tcl runs and the Verilog
# elaborates as meant, nothing more.
# License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, datetime, glob, hashlib, os, re, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
PROFILE = os.path.normpath(os.path.join(HW, "..", ".."))
WS = os.environ.get("WS", os.path.normpath(os.path.join(PROFILE, "..")))
CORE = os.path.join(WS, "PTSG-Core", "03_Sample_Implementations")
CORE_QSF = os.path.join(CORE, "board_harnesses", "de10_nano", "DE10_Nano_golden_top.qsf")
PROJECT = "DE10_Nano_wpms"
REVISIONS = {"DE10_Nano_wpms": 50, "DE10_Nano_wpms100": 100}
TOP = "DE10_Nano_wpms_top"

SOURCES = [                                       # (directory, file); Verilog in compile order
    ("de10_nano", "DE10_Nano_wpms_top.v"), ("de10_nano", "wpms_pll.v"),
    ("switch", "wpms_system.v"), ("switch", "wpms_switch.v"), ("switch", "wpms_host_bridge.v"),
    ("switch", "wpms_issp.v"), ("switch", "wpms_rom.v"), ("switch", "wpms_key_pulse.v"),
    ("l1", "wpms_synth_top.v"), ("l1", "wpms_l1_module.v"), ("l1", "wpms_l1_sin.v"), ("l1", "wpms_l1_exp2.v"),
    ("l1", "wpms_output_stage.v"), ("l1", "wpms_strobe_sync.v"), ("l1", "wpms_i2s_master.v"),
    ("l1", "wpms_video_720p.v"), ("l1", "wpms_adv7513_cfg.v"),
    ("l2", "wpms_l2_top.v"), ("l2", "wpms_formation.v"), ("l2", "wpms_sequencer.v"),
    ("core", "ptsg_core_rh031p.v"),
    ("@core", "ai_friendly_vendor_wrappers/ptsg_imem/ptsg_imem.v"),
]
INCLUDES = [("l1", "wpms_l1_consts.vh"), ("l2", "wpms_decode.vh")]
MEMORIES = [("l2", "scores/wpms_r1d.mif"), ("l2", "scores/wpms_r1d.hex"),
            ("l1", "wpms_exp2_table.mif"), ("l1", "wpms_exp2_table.hex"),
            ("switch", "wpms_rom_origin_1008.mif"), ("switch", "wpms_rom_origin_2048.mif"),
            ("switch", "wpms_rom_origin_1008.hex"), ("switch", "wpms_rom_origin_2048.hex")]
SDC = ("de10_nano", "DE10_Nano_wpms.sdc")

# The pins: the Terasic golden top's (as the Core's .qsf), all 3.3-V LVTTL
TX_D = ["AD12", "AE12", "W8", "Y8", "AD11", "AD10", "AE11", "Y5", "AF10", "Y4", "AE9", "AB4",
        "AE7", "AF6", "AF8", "AF5", "AE4", "AH2", "AH4", "AH5", "AH6", "AG6", "AF9", "AE8"]
PINS = ([("FPGA_CLK1_50", "V11"), ("FPGA_CLK2_50", "Y13"), ("FPGA_CLK3_50", "E11"),
         ("KEY[0]", "AH17"), ("KEY[1]", "AH16"),
         ("SW[0]", "Y24"), ("SW[1]", "W24"), ("SW[2]", "W21"), ("SW[3]", "W20")]
        + [(f"LED[{i}]", p) for i, p in enumerate(["W15", "AA24", "V16", "V15", "AF26", "AE26", "Y16", "AA23"])]
        + [("HDMI_I2C_SCL", "U10"), ("HDMI_I2C_SDA", "AA4"), ("HDMI_I2S", "T13"), ("HDMI_LRCLK", "T11"),
           ("HDMI_MCLK", "U11"), ("HDMI_SCLK", "T12"), ("HDMI_TX_CLK", "AG5"), ("HDMI_TX_DE", "AD19"),
           ("HDMI_TX_HS", "T8"), ("HDMI_TX_VS", "V13"), ("HDMI_TX_INT", "AF11")]
        + [(f"HDMI_TX_D[{i}]", p) for i, p in enumerate(TX_D)])
FAST_OUT = [f"HDMI_TX_D[{i}]" for i in range(24)] + ["HDMI_TX_DE", "HDMI_TX_HS", "HDMI_TX_VS"]
PULL_UP = ["HDMI_I2C_SCL", "HDMI_I2C_SDA"]


def src_path(d, f):
    return os.path.join(CORE, f) if d == "@core" else os.path.join(HW, d, f)


def qsf(rev, mhz, files):
    L = [f"# {rev}.qsf — generated by hw/de10_nano/make_quartus_project.py; edit the generator, not this",
         f"# WPMS silicon sample, SILICON_BRIEF_2026-09-27 Phase 6: clk_sys {mhz} MHz, NMAX "
         f"{2048 if mhz >= 100 else 1008}. License: MIT.",
         'set_global_assignment -name FAMILY "Cyclone V"',
         "set_global_assignment -name DEVICE 5CSEBA6U23I7",
         f"set_global_assignment -name TOP_LEVEL_ENTITY {TOP}",
         'set_global_assignment -name ORIGINAL_QUARTUS_VERSION "23.1std.1 Lite Edition"',
         'set_global_assignment -name LAST_QUARTUS_VERSION "23.1std.1 Lite Edition"',
         "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files",
         "set_global_assignment -name DEVICE_FILTER_PACKAGE FBGA",
         "set_global_assignment -name MIN_CORE_JUNCTION_TEMP 0",
         "set_global_assignment -name MAX_CORE_JUNCTION_TEMP 85",
         'set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"',
         "set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005",
         "set_global_assignment -name VERILOG_SHOW_LMF_MAPPING_MESSAGES OFF",
         "set_global_assignment -name TIMING_ANALYZER_MULTICORNER_ANALYSIS ON",
         "set_global_assignment -name NUM_PARALLEL_PROCESSORS ALL",
         f"set_parameter -name SYS_MHZ {mhz}",
         ""]
    L += [f"set_global_assignment -name VERILOG_FILE {f}" for f in files["verilog"]]
    L += [f"set_global_assignment -name VERILOG_INCLUDE_FILE {f}" for f in files["include"]]
    L += [f"set_global_assignment -name MIF_FILE {f}" for f in files["mif"]]
    L += [f"set_global_assignment -name SDC_FILE {files['sdc']}", ""]
    for port, pin in PINS:
        L.append(f"set_location_assignment PIN_{pin} -to {port}")
        L.append(f'set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to {port}')
    L.append("")
    L += [f"set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to {p}" for p in FAST_OUT]
    L += [f"set_instance_assignment -name WEAK_PULL_UP_RESISTOR ON -to {p}" for p in PULL_UP]
    return "\n".join(L) + "\n"


def qpf():
    return (f'QUARTUS_VERSION = "23.1"\nDATE = "{datetime.date.today().isoformat()}"\n\n# Revisions\n\n'
            + "".join(f'PROJECT_REVISION = "{r}"\n' for r in REVISIONS))


def git_head():
    try:
        r = subprocess.run(["git", "-C", HW, "rev-parse", "HEAD"], capture_output=True, text=True)
        d = subprocess.run(["git", "-C", HW, "status", "--porcelain", "--", "."], capture_output=True, text=True)
        return r.stdout.strip() + (" (with uncommitted changes)" if d.stdout.strip() else "")
    except OSError:
        return "unknown"


def make(out):
    os.makedirs(out, exist_ok=True)
    man, files = [], dict(verilog=[], include=[], mif=[], sdc=None)

    def put(d, f, sub=""):
        s = src_path(d, f)
        if not os.path.exists(s):
            raise SystemExit(f"missing source: {s}")
        name = os.path.join(sub, os.path.basename(f)) if sub else os.path.basename(f)
        dst = os.path.join(out, name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(s, dst)
        man.append((name, os.path.relpath(s, PROFILE if not d == "@core" else WS),
                    hashlib.sha256(open(s, "rb").read()).hexdigest()))
        return name.replace(os.sep, "/")

    for d, f in SOURCES:
        files["verilog"].append(put(d, f))
    for d, f in INCLUDES:
        files["include"].append(put(d, f))
    for d, f in MEMORIES:
        n = put(d, f)
        if n.endswith(".mif"):
            files["mif"].append(n)
    files["sdc"] = put(*SDC)
    for p in sorted(glob.glob(os.path.join(HERE, "inject", "*.mif"))):
        put("de10_nano", os.path.join("inject", os.path.basename(p)), "inject")
    for p in sorted(glob.glob(os.path.join(HW, "tools", "host", "*.tcl"))):
        if os.path.basename(p) != "issp_standin.tcl":
            put("tools", os.path.join("host", os.path.basename(p)), "host")
    open(os.path.join(out, f"{PROJECT}.qpf"), "w").write(qpf())
    for rev, mhz in REVISIONS.items():
        open(os.path.join(out, f"{rev}.qsf"), "w").write(qsf(rev, mhz, files))
    head = git_head()
    with open(os.path.join(out, "MANIFEST.txt"), "w") as m:
        m.write(f"# {PROJECT} — generated {datetime.datetime.now().isoformat(timespec='seconds')} by "
                f"hw/de10_nano/make_quartus_project.py\n# PTSG-WPMS-Formation commit {head}\n"
                f"# file | source (relative to the workspace or the profile) | sha256\n")
        for name, s, h in man:
            m.write(f"{name} | {s} | {h}\n")
    return files


# ---------------------------------------------------------------------------------------------------
# --check: the project's Tcl under a plain tclsh, against stand-ins
# ---------------------------------------------------------------------------------------------------
STANDIN = r'''
# stand-ins of the Quartus commands the .qsf and the .sdc use (records, no semantics)
proc rec {args} { puts "REC [join $args \t]" }
# a .qsf names bus bits unquoted (-to HDMI_TX_D[0]); Quartus reads the brackets literally, Tcl would
# call a command "0": answer it with the brackets back
rename unknown _unknown
proc unknown {args} {
    if {[llength $args] == 1 && [string is integer -strict [lindex $args 0]]} { return "\[[lindex $args 0]\]" }
    uplevel 1 [list _unknown {*}$args]
}
proc set_global_assignment {args} { rec G {*}$args }
proc set_location_assignment {pin -to port} { rec L $pin $port }
proc set_instance_assignment {args} { rec I {*}$args }
proc set_parameter {args} { rec P {*}$args }
# clocks: name -> {period rise fall master target}
array set CLK {}
proc lit {p} { return [string map {[ \\[ ] \\]} $p] }          ;# Quartus filters: brackets are literal
proc get_ports {pat} { set out {}; foreach p $pat { lappend out "port:$p" }; return $out }
proc get_pins {pat} { return [list "pin:$pat"] }
proc create_clock {args} {
    array set a {-name "" -period 0}; set tgt [lindex $args end]
    for {set i 0} {$i < [llength $args] - 1} {incr i} { set k [lindex $args $i]
        if {$k in {-name -period}} { set a($k) [lindex $args [incr i]] } }
    set ::CLK($a(-name)) [list $a(-period) 0 [expr {$a(-period) / 2.0}] "" $tgt]
    rec C create_clock $a(-name) $a(-period)
}
proc gen {name period rise master target} {
    set ::CLK($name) [list $period $rise [expr {$rise + $period / 2.0}] $master $target]
}
proc derive_pll_clocks {args} {
    # the names derive_pll_clocks gives a Cyclone V altera_pll: the VCO phase clock and the counters
    set sp [expr {$::SYS_MHZ >= 100 ? 10.0 : 20.0}]
    gen "u_pll_sys|g_intel.g_one.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" 0.833 0 FPGA_CLK1_50 pin:vco_sys
    gen "u_pll_sys|g_intel.g_one.u_pll|general\[0\].gpll~PLL_OUTPUT_COUNTER|divclk" $sp 0 \
        "u_pll_sys|g_intel.g_one.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" pin:cnt_sys
    gen "u_pll_aud|g_intel.g_one.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" 0.814 0 FPGA_CLK2_50 pin:vco_aud
    gen "u_pll_aud|g_intel.g_one.u_pll|general\[0\].gpll~PLL_OUTPUT_COUNTER|divclk" 81.380 0 \
        "u_pll_aud|g_intel.g_one.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" pin:cnt_aud
    gen "u_pll_pix|g_intel.g_two.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" 1.347 0 FPGA_CLK3_50 pin:vco_pix
    gen "u_pll_pix|g_intel.g_two.u_pll|general\[0\].gpll~PLL_OUTPUT_COUNTER|divclk" 13.468 0 \
        "u_pll_pix|g_intel.g_two.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" pin:cnt_pix0
    gen "u_pll_pix|g_intel.g_two.u_pll|general\[1\].gpll~PLL_OUTPUT_COUNTER|divclk" 13.468 6.734 \
        "u_pll_pix|g_intel.g_two.u_pll|general\[0\].gpll~FRACTIONAL_PLL|vcoph\[0\]" pin:cnt_pix1
    rec D derive_pll_clocks
}
proc get_clocks {pat} {
    set out {}
    foreach p $pat { set hit 0
        foreach n [array names ::CLK] { if {[string match [lit $p] $n]} { lappend out $n; set hit 1 } }
        if {!$hit} { rec W "get_clocks: no clock matches $p" } }
    return [lsort -unique $out]
}
proc foreach_in_collection {var coll body} {
    upvar 1 $var v
    foreach v $coll { uplevel 1 $body }
}
proc get_clock_info {opt c} {
    if {![info exists ::CLK($c)]} { set c [lindex $c 0] }         ;# a one-clock "collection"
    lassign $::CLK($c) per rise fall master target
    switch -- $opt {
        -name { return $c } -waveform { return [list $rise $fall] } -period { return $per }
        -master_clock { return $master } -targets { return $target }
        default { error "get_clock_info: $opt not stood in" }
    }
}
proc create_generated_clock {args} {
    set name [lindex $args [expr {[lsearch $args -name] + 1}]]
    set src [lindex $args [expr {[lsearch $args -source] + 1}]]
    set master ""
    foreach n [array names ::CLK] { if {[lindex $::CLK($n) 4] eq $src} { set master $n } }
    if {$master eq ""} { error "create_generated_clock: -source $src is no clock's target" }
    lassign $::CLK($master) per rise
    set ::CLK($name) [list $per $rise [expr {$rise + $per / 2.0}] $master [lindex $args end]]
    rec C create_generated_clock $name $src [lindex $args end]
}
proc derive_clock_uncertainty {args} { rec D derive_clock_uncertainty }
proc set_input_delay {args} { rec IN {*}$args }
proc set_output_delay {args} { rec OUT {*}$args }
proc set_false_path {args} { rec FP {*}$args }
proc set_clock_groups {args} {
    set groups {}
    for {set i 0} {$i < [llength $args]} {incr i} {
        if {[lindex $args $i] eq "-group"} { lappend groups [lindex $args [incr i]] } }
    foreach g $groups { rec GRP [join $g ,] }
    rec ALL [join [lsort [array names ::CLK]] ,]
}
proc post_message {args} { rec MSG {*}$args }
'''


def tcl_run(tclsh, d, body):
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", dir=d, delete=False) as f:
        f.write(STANDIN + body)
        p = f.name
    try:
        r = subprocess.run([tclsh, p], capture_output=True, text=True, cwd=d)
    finally:
        os.unlink(p)
    recs = [l[4:].split("\t") for l in r.stdout.splitlines() if l.startswith("REC ")]
    return r.returncode, recs, r.stderr


def top_ports():
    s = open(os.path.join(HERE, "DE10_Nano_wpms_top.v")).read()
    head = s[s.index(") (", s.index("module DE10_Nano_wpms_top")):s.index(");", s.index("module DE10_Nano_wpms_top"))]
    ports = []
    for m in re.finditer(r"(input|output|inout)\s+wire\s*(\[(\d+):(\d+)\])?\s*(\w+)", head):
        if m.group(2):
            hi, lo = int(m.group(3)), int(m.group(4))
            ports += [f"{m.group(5)}[{i}]" for i in range(lo, hi + 1)]
        else:
            ports.append(m.group(5))
    return ports


def core_pins():
    if not os.path.exists(CORE_QSF):
        return None
    pins = {}
    for line in open(CORE_QSF):
        m = re.match(r"\s*set_location_assignment\s+PIN_(\w+)\s+-to\s+(\S+)", line)
        if m:
            pins[m.group(2)] = m.group(1)
    return pins


def check(out, files, tclsh):
    probs, notes = [], []
    ports = top_ports()
    gold = core_pins()
    for rev, mhz in REVISIONS.items():
        rc, recs, err = tcl_run(tclsh, out, f"set ::SYS_MHZ {mhz}\nsource {rev}.qsf\n")
        if rc:
            probs.append(f"{rev}.qsf: tclsh failed: {err.strip()[:300]}")
            continue
        loc = [(r[1], r[2]) for r in recs if r[0] == "L"]
        ios = [r[r.index("-to") + 1] for r in recs if r[0] == "I" and "-to" in r and r[2] == "IO_STANDARD"]
        lp = {}
        for pin, port in loc:
            lp.setdefault(port, []).append(pin)
        for p in ports:
            if len(lp.get(p, [])) != 1:
                probs.append(f"{rev}: port {p} has {len(lp.get(p, []))} pins")
            if ios.count(p) != 1:
                probs.append(f"{rev}: port {p} has no single IO_STANDARD")
        extra = set(lp) - set(ports)
        if extra:
            probs.append(f"{rev}: pins for ports the top does not have: {sorted(extra)}")
        used = [pin for pin, _ in loc]
        if len(used) != len(set(used)):
            probs.append(f"{rev}: a pin assigned twice")
        if gold is not None:
            bad = [p for p, (pin, *_) in ((p, lp.get(p, [None])) for p in ports) if gold.get(p) != (pin or "")[4:]]
            if bad:
                probs.append(f"{rev}: pins differ from the Terasic golden top (Core .qsf): {bad}")
        named = [r[3] for r in recs if r[0] == "G" and len(r) >= 4 and r[1] == "-name"
                 and r[2] in ("VERILOG_FILE", "VERILOG_INCLUDE_FILE", "MIF_FILE", "SDC_FILE")]
        for n in named:
            if not os.path.exists(os.path.join(out, n)):
                probs.append(f"{rev}: {n} named but not in the project directory")
        par = [r for r in recs if r[0] == "P"]
        if [r[1:] for r in par] != [["-name", "SYS_MHZ", str(mhz)]]:
            probs.append(f"{rev}: parameters {par}")
        # the SDC under this revision's clocks
        rc, srec, err = tcl_run(tclsh, out, f"set ::SYS_MHZ {mhz}\nsource {files['sdc']}\n")
        if rc:
            probs.append(f"{rev}: the SDC failed under tclsh: {err.strip()[:300]}")
            continue
        warn = [r for r in srec if r[0] == "W" or (r[0] == "MSG" and "critical_warning" in r)]
        if warn:
            probs.append(f"{rev}: SDC warnings: {warn[:3]}")
        gen = [r for r in srec if r[0] == "C" and r[1] == "create_generated_clock"]
        if not (len(gen) == 1 and gen[0][2] == "hdmi_tx_clk" and gen[0][3] == "pin:cnt_pix1"
                and gen[0][4] == "port:HDMI_TX_CLK"):
            probs.append(f"{rev}: hdmi_tx_clk not generated from the 180-degree counter: {gen}")
        outd = sorted((r[2], r[3], r[4]) for r in srec if r[0] == "OUT" and "hdmi_tx_clk" in r)
        if outd != [("hdmi_tx_clk", "-max", "2.0"), ("hdmi_tx_clk", "-min", "-1.5")]:
            probs.append(f"{rev}: pixel-bus output delays {outd}")
        grp = [set(r[1].split(",")) for r in srec if r[0] == "GRP"]
        allc = next((set(r[1].split(",")) for r in srec if r[0] == "ALL"), set())
        cover = [c for c in allc if sum(c in g for g in grp) != 1]
        if len(grp) != 5 or cover:
            probs.append(f"{rev}: clock groups {len(grp)}; clocks not in exactly one group: {cover}")
        fp = [" ".join(r[1:]) for r in srec if r[0] == "FP"]
        notes.append(f"{rev}: {len(loc)} pins; {len(named)} files; SDC: {len(allc)} clocks in {len(grp)} groups, "
                     f"hdmi_tx_clk from the 180-degree counter, pixel bus -max 2.0 / -min -1.5 ns; "
                     f"{len(fp)} false-path commands")
    return probs, notes


def elaborate(out, files, iverilog="iverilog", vvp="vvp"):
    """The project's Verilog, exactly the files Quartus is given, elaborated by Icarus with the INTEL
    branches taken and the Intel primitives stood in (sim/vendor_stubs.v): the parameters each
    primitive receives, per revision."""
    probs, notes = [], []
    stubs = os.path.join(HERE, "sim", "vendor_stubs.v")
    for rev, mhz in REVISIONS.items():
        exe = os.path.join(out, f".elab_{rev}.vvp")
        r = subprocess.run([iverilog, "-g2012", "-Wall", "-o", exe, "-s", TOP, f"-P{TOP}.SYS_MHZ={mhz}",
                            *files["verilog"], stubs], capture_output=True, text=True, cwd=out)
        bad = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not any(
               k in l for k in ("timescale", "sensitive to all", "coerced to inout"))]
        if r.returncode or bad:
            probs.append(f"{rev}: elaboration: {bad[:5]}")
            continue
        r = subprocess.run([vvp, "-n", exe], capture_output=True, text=True, cwd=out)
        os.unlink(exe)
        st = {}
        for line in r.stdout.splitlines():
            if line.startswith("STUB "):
                f = [x.strip() for x in line.split("|")]
                kind, inst = f[0].split()[1], f[0].split()[2]
                st[inst.split(".", 1)[1]] = (kind, dict(x.split("=", 1) for x in f[1:] if "=" in x))
        sys_f = "100.000000 MHz" if mhz >= 100 else "50.0000000 MHz"
        want = {
            "u_pll_sys.g_intel.g_one.u_pll": ("altera_pll", dict(fractional="false", out0=sys_f, phase0="0 ps")),
            "u_pll_aud.g_intel.g_one.u_pll": ("altera_pll", dict(fractional="true", out0="12.288000 MHz")),
            "u_pll_pix.g_intel.g_two.u_pll": ("altera_pll", dict(fractional="true", out0="74.250000 MHz",
                                                                  phase0="0 ps", out1="74.250000 MHz",
                                                                  phase1="6734 ps")),
            "u_sys.u_sw.u_rom.g_m10k.u_rom": ("altsyncram", dict(
                init=f"wpms_rom_origin_{2048 if mhz >= 100 else 1008}.mif",
                hint="ENABLE_RUNTIME_MOD=YES,INSTANCE_NAME=TORG")),
            "u_sys.u_synth.u_l2.core.ptsg_imem.g_m10k.u_rom": ("altsyncram", dict(
                init="wpms_r1d.mif", hint="ENABLE_RUNTIME_MOD=YES,INSTANCE_NAME=PTSG")),
            "u_sys.u_issp_host.g_intel.u_issp": ("altsource_probe", dict(id="HOST")),
            "u_sys.u_issp_stat.g_intel.u_issp": ("altsource_probe", dict(id="STAT")),
            "u_sys.u_issp_insp.g_intel.u_issp": ("altsource_probe", dict(id="INSP")),
            "u_issp_brd.g_intel.u_issp": ("altsource_probe", dict(id="BRD")),
        }
        for inst, (kind, kv) in want.items():
            got = st.get(inst)
            if not got or got[0] != kind or any(got[1].get(k) != v for k, v in kv.items()):
                probs.append(f"{rev}: {inst}: {got} (expected {kind} {kv})")
        extra = set(st) - set(want)
        if extra:
            probs.append(f"{rev}: primitives not expected: {sorted(extra)}")
        for inst, (kind, kv) in st.items():
            if kind == "altsyncram" and not os.path.exists(os.path.join(out, kv.get("init", ""))):
                probs.append(f"{rev}: {inst}: init file {kv.get('init')} not in the project directory")
        notes.append(f"{rev}: elaborated with the INTEL branches (Icarus, stand-in primitives): "
                     f"{len(st)} primitives, each with the parameters expected (clk_sys {sys_f})")
    return probs, notes


# (name, file, text, replacement or None = delete the file): one defect each; --check must catch every one
MUTANTS = [
    ("a pin moved (LED[3] V15 -> V14)", "DE10_Nano_wpms.qsf", "PIN_V15 -to LED[3]", "PIN_V14 -to LED[3]"),
    ("the pixel PLL not found by the SDC", SDC[1], '"*u_pll_pix*"', '"*u_pll_px*"'),
    ("a source missing from the directory", "wpms_formation.v", None, None),
    ("HDMI_TX_CLK taken from the 0-degree output", SDC[1], "> 3.0}", "< 3.0}"),
    ("the hold allowance with the wrong sign", SDC[1], "-min [expr {-(", "-min [expr {("),
    ("the audio clocks left out of their group", SDC[1],
     "lappend wpms_groups -group [get_clocks [concat {FPGA_CLK2_50} $wpms_aud]]",
     "lappend wpms_groups -group [get_clocks {FPGA_CLK2_50}]"),
    ("an I/O standard missing (SW[1], 100 MHz revision)", "DE10_Nano_wpms100.qsf",
     'set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to SW[1]\n', ""),
]


def mutants(tclsh):
    """Each mutant applied to a fresh copy of the project; check() must report a problem."""
    killed, lines = 0, []
    for name, fn, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as t:
            files = make(t)
            p = os.path.join(t, fn)
            if old is None:
                os.unlink(p)
            else:
                txt = open(p).read()
                if txt.count(old) != 1:
                    lines.append(f"  ERROR    {name}: the text to break is not found once")
                    continue
                open(p, "w").write(txt.replace(old, new))
            probs, _ = check(t, files, tclsh)
        killed += bool(probs)
        lines.append(f"  {'KILLED  ' if probs else 'SURVIVED'} {name}" + (f"  ->  {probs[0][:100]}" if probs else ""))
    return killed, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "build", "quartus"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--mutants", action="store_true", help="with --check: also the broken copies of the project")
    ap.add_argument("--tclsh", default=shutil.which("tclsh") or shutil.which("tclsh8.6") or "tclsh")
    a = ap.parse_args()
    files = make(a.out)
    print(f"make_quartus_project: {a.out}: {PROJECT}.qpf, revisions {', '.join(REVISIONS)}; "
          f"{len(files['verilog'])} Verilog, {len(files['include'])} include, {len(files['mif'])} MIF, SDC")
    if a.check:
        probs, notes = check(a.out, files, a.tclsh)
        p2, n2 = elaborate(a.out, files)
        probs, notes = probs + p2, notes + n2
        for n in notes:
            print("  " + n)
        for p in probs:
            print("  FAIL " + p)
        if a.mutants:
            killed, lines = mutants(a.tclsh)
            print("\n".join(lines))
            print(f"  mutants {killed}/{len(MUTANTS)} broken copies of the project caught")
            if killed != len(MUTANTS):
                probs.append("a mutant survived")
        print(f"make_quartus_project --check: {'PASS' if not probs else 'FAIL'} (stand-ins, not Quartus)")
        sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
