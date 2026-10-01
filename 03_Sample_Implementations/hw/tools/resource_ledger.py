#!/usr/bin/env python3
# ============================================================================
# resource_ledger.py — the Phase 6 resource ledger (SILICON_BRIEF: "ALMs,
# M10K, DSP per entity, in the Core's format") from a Quartus Fitter report:
# the table "Fitter Resource Utilization by Entity" of <revision>.fit.rpt.
#
#   python3 resource_ledger.py output_files/DE10_Nano_wpms.fit.rpt [--revision RH] [--date D]
#                              [--md OUT.md] [--json OUT.json]
#   python3 resource_ledger.py --selftest
#
# Printed: (1) the Core's ledger row for the Core instance (PTSG-Core
# ptsg_core_verilog/README.md: Date | Revision | ALMs needed (full trim) |
# Core proper (entity-only) | Comb. ALUTs | Notes), and (2) the same columns
# with M10K, DSP and block-memory bits for every WPMS entity of interest,
# totals with their own logic in brackets, as the Fitter prints them. Rows
# are matched by instance name, so the table survives hierarchy changes;
# an entity the report lacks is listed as absent, not guessed.
# Evidence class of the numbers: SILICON (a fit of the device), i.e. what
# the Fitter placed — not an estimate. License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, datetime, json, re, sys

sys.dont_write_bytecode = True

# (label, instance path pattern below the top; first match wins). Paths use the Fitter's
# "Full Hierarchy Name" with entity prefixes removed: u_sys|u_synth|u_l2|core
ROWS = [
    ("board top (all)",              r"^$"),
    ("wpms_system",                  r"^u_sys$"),
    ("synthesizer (L2 + L1 + out)",  r"^u_sys\|u_synth$"),
    ("L2: Core + Formation + seq.",  r"^u_sys\|u_synth\|u_l2$"),
    ("PTSG-Core (RH031p)",           r"^u_sys\|u_synth\|u_l2\|core$"),
    ("  its instruction memory",     r"^u_sys\|u_synth\|u_l2\|core\|ptsg_imem$"),
    ("Formation",                    r"^u_sys\|u_synth\|u_l2\|form$"),
    ("sequencer",                    r"^u_sys\|u_synth\|u_l2\|seq$"),
    ("L1 module",                    r"^u_sys\|u_synth\|u_l1$"),
    ("  its sine",                   r"^u_sys\|u_synth\|u_l1\|u_sin$"),
    ("  its exp2",                   r"^u_sys\|u_synth\|u_l1\|u_exp2$"),
    ("output stage",                 r"^u_sys\|u_synth\|u_out$"),
    ("I2S master",                   r"^u_sys\|u_synth\|u_i2s$"),
    ("strobe sync",                  r"^u_sys\|u_synth\|u_sync$"),
    ("input switch",                 r"^u_sys\|u_sw$"),
    ("  its ROM (TORG)",             r"^u_sys\|u_sw\|u_rom$"),
    ("host bridge",                  r"^u_sys\|u_bridge$"),
    ("ISSP HOST",                    r"^u_sys\|u_issp_host$"),
    ("ISSP STAT",                    r"^u_sys\|u_issp_stat$"),
    ("ISSP INSP",                    r"^u_sys\|u_issp_insp$"),
    ("ISSP BRD",                     r"^u_issp_brd$"),
    ("video carrier",                r"^u_video$"),
    ("ADV7513 configurator",         r"^u_cfg$"),
    ("PLL clk_sys",                  r"^u_pll_sys$"),
    ("PLL MCLK",                     r"^u_pll_aud$"),
    ("PLL pixel",                    r"^u_pll_pix$"),
    ("SignalTap",                    r"(^|\|)sld_signaltap:"),
    ("JTAG hub",                     r"(^|\|)sld_hub:"),
]
COLS = {"alms": "ALMs needed", "aluts": "Combinational ALUTs", "regs": "Dedicated Logic Registers",
        "bits": "Block Memory Bits", "m10k": "M10K", "dsp": "DSP Blocks"}


def num(cell):
    """'4520.5 (35.2)' -> (4520.5, 35.2); '12' -> (12.0, None); '' -> None."""
    c = cell.strip().replace(",", "")
    m = re.match(r"^([\d.]+)\s*\(([\d.]+)\)$", c)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^([\d.]+)$", c)
    return (float(m.group(1)), None) if m else None


def parse(path):
    """The rows of 'Fitter Resource Utilization by Entity': [{path, entity, depth, cols...}]."""
    lines = open(path, errors="replace").read().splitlines()
    try:
        t = next(i for i, l in enumerate(lines) if re.match(r"^; Fitter Resource Utilization by Entity\s*;", l))
    except StopIteration:
        raise SystemExit(f"{path}: no 'Fitter Resource Utilization by Entity' table")
    hdr_i = next(i for i in range(t + 1, len(lines)) if lines[i].startswith("; Compilation Hierarchy Node"))
    hdr = [h.strip() for h in lines[hdr_i].strip().strip(";").split(";")]
    idx = {}
    for k, name in COLS.items():
        idx[k] = next((j for j, h in enumerate(hdr) if h.startswith(name)), None)
    j_full = next((j for j, h in enumerate(hdr) if h == "Full Hierarchy Name"), None)
    j_ent = next((j for j, h in enumerate(hdr) if h == "Entity Name"), None)
    rows = []
    for l in lines[hdr_i + 1:]:
        if l.startswith("+"):
            if rows:
                break
            continue
        if not l.startswith(";"):
            break
        cells = l.strip()[1:-1].split(";") if l.strip().endswith(";") else l.strip()[1:].split(";")
        node = cells[0]
        depth = (len(node) - len(node.lstrip(" "))) // 3
        r = dict(node=node.strip(), depth=depth)
        for k, j in idx.items():
            r[k] = num(cells[j]) if j is not None and j < len(cells) else None
        full = cells[j_full].strip() if j_full is not None and j_full < len(cells) else ""
        r["entity"] = cells[j_ent].strip() if j_ent is not None and j_ent < len(cells) else ""
        # "|DE10_Nano_wpms_top|wpms_system:u_sys|..." -> path "u_sys|...", epath "wpms_system:u_sys|..."
        segs = [x for x in full.strip("|").split("|") if x]
        if segs and ":" not in segs[0]:
            segs = segs[1:]                                    # the top entity itself
        r["path"] = "|".join(x.split(":")[-1] for x in segs)
        r["epath"] = "|".join(segs)
        rows.append(r)
    return rows


def ledger(rows):
    out = []
    for label, pat in ROWS:
        key = "epath" if ":" in pat else "path"
        r = next((x for x in rows if re.search(pat, x[key])), None)
        out.append((label, r))
    return out


def fmt(v, self_too=True, ints=False):
    if v is None:
        return "—"
    a, b = v
    f = (lambda x: f"{int(round(x))}") if ints else (lambda x: f"{x:.1f}")
    return f"{f(a)} ({f(b)})" if (self_too and b is not None) else f(a)


def render(rows, rev, date):
    L = ledger(rows)
    core = dict(L).get("PTSG-Core (RH031p)")
    md = ["## Resource ledger / 資源台帳 (Fitter \"Resource Utilization by Entity\"; class SILICON)", "",
          "Core's format / Core の書式:", "",
          "| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs | Notes |",
          "|---|---|---|---|---|---|"]
    if core:
        md.append(f"| {date} | {rev} | {fmt(core['alms'], False)} | "
                  f"{fmt((core['alms'][1], None) if core['alms'] and core['alms'][1] is not None else None, False)} | "
                  f"{fmt(core['aluts'], True, True)} | inside WPMS (wpms_l2_top), score wpms_r1d, ISMCE port included |")
    else:
        md.append(f"| {date} | {rev} | — | — | — | the Core instance not found in the report |")
    md += ["", "Per entity / 実体ごと — total (entity-only):", "",
           "| Entity | ALMs needed | Comb. ALUTs | Registers | M10K | DSP | Block memory bits |",
           "|---|---|---|---|---|---|---|"]
    for label, r in L:
        if r is None:
            md.append(f"| {label} | absent | | | | | |")
        else:
            md.append(f"| {label} | {fmt(r['alms'])} | {fmt(r['aluts'], True, True)} | {fmt(r['regs'], True, True)} | "
                      f"{fmt(r['m10k'], True, True)} | {fmt(r['dsp'], True, True)} | {fmt(r['bits'], True, True)} |")
    return "\n".join(md) + "\n", L


SAMPLE = """+-----------------------------------------------------------------------------------+
; Fitter Resource Utilization by Entity                                             ;
+------------------------------------------+----------------------+---------------------+---------------------------+-------------------+--------+------------+---------------------------------------------------------------+-------------+--------------+
; Compilation Hierarchy Node               ; ALMs needed [=A-B+C] ; Combinational ALUTs ; Dedicated Logic Registers ; Block Memory Bits ; M10Ks  ; DSP Blocks ; Full Hierarchy Name                                           ; Entity Name ; Library Name ;
+------------------------------------------+----------------------+---------------------+---------------------------+-------------------+--------+------------+---------------------------------------------------------------+-------------+--------------+
; |DE10_Nano_wpms_top                      ; 5000.5 (40.5)        ; 7000 (50)           ; 6000 (500)                ; 900000 (0)        ; 120 (0) ; 140 (0)   ; |DE10_Nano_wpms_top                                           ; DE10_Nano_wpms_top ; work   ;
;    |wpms_system:u_sys|                   ; 4500.0 (10.0)        ; 6500 (20)           ; 5000 (30)                 ; 50000 (0)         ; 10 (0)  ; 140 (0)   ; |DE10_Nano_wpms_top|wpms_system:u_sys                         ; wpms_system ; work         ;
;       |wpms_synth_top:u_synth|           ; 4000.0 (5.0)         ; 6000 (10)           ; 4500 (20)                 ; 45000 (0)         ; 9 (0)   ; 140 (0)   ; |DE10_Nano_wpms_top|wpms_system:u_sys|wpms_synth_top:u_synth  ; wpms_synth_top ; work      ;
;          |wpms_l2_top:u_l2|              ; 1500.0 (2.0)         ; 2000 (4)            ; 1200 (6)                  ; 32768 (0)         ; 4 (0)   ; 0 (0)     ; |DE10_Nano_wpms_top|wpms_system:u_sys|wpms_synth_top:u_synth|wpms_l2_top:u_l2 ; wpms_l2_top ; work ;
;             |ptsg_core:core|             ; 441.8 (398.0)        ; 631 (585)           ; 300 (290)                 ; 32768 (0)         ; 4 (0)   ; 0 (0)     ; |DE10_Nano_wpms_top|wpms_system:u_sys|wpms_synth_top:u_synth|wpms_l2_top:u_l2|ptsg_core:core ; ptsg_core ; work ;
;    |sld_hub:auto_hub|                    ; 80.0 (1.0)           ; 120 (1)             ; 100 (0)                   ; 0 (0)             ; 0 (0)   ; 0 (0)     ; |DE10_Nano_wpms_top|sld_hub:auto_hub                          ; sld_hub     ; altera_sld   ;
;    |sld_signaltap:auto_signaltap_0|      ; 400.0 (2.0)          ; 500 (2)             ; 900 (0)                   ; 850000 (0)        ; 110 (0) ; 0 (0)     ; |DE10_Nano_wpms_top|sld_signaltap:auto_signaltap_0            ; sld_signaltap ; work       ;
+------------------------------------------+----------------------+---------------------+---------------------------+-------------------+--------+------------+---------------------------------------------------------------+-------------+--------------+
"""


def selftest():
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".rpt", delete=False) as f:
        f.write(SAMPLE)
        p = f.name
    try:
        rows = parse(p)
        md, L = render(rows, "RHtest", "2026-10-01")
    finally:
        os.unlink(p)
    d = dict(L)
    ok = (len(rows) == 7 and d["SignalTap"]["m10k"] == (110.0, 0.0) and d["JTAG hub"]["alms"] == (80.0, 1.0) and d["PTSG-Core (RH031p)"]["alms"] == (441.8, 398.0)
          and d["PTSG-Core (RH031p)"]["aluts"] == (631.0, 585.0) and d["board top (all)"]["dsp"] == (140.0, 0.0)
          and d["L2: Core + Formation + seq."]["m10k"] == (4.0, 0.0) and d["Formation"] is None
          and "| 2026-10-01 | RHtest | 441.8 | 398.0 | 631 (585) |" in md)
    print(md)
    print(f"resource_ledger --selftest: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?")
    ap.add_argument("--revision", default="(revision)")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--md", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.report:
        ap.error("a .fit.rpt is needed (or --selftest)")
    rows = parse(a.report)
    md, L = render(rows, a.revision, a.date)
    print(md)
    if a.md:
        open(a.md, "w").write(md)
    if a.json:
        json.dump(dict(revision=a.revision, date=a.date, rows=rows,
                       ledger=[dict(label=l, row=r) for l, r in L]), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
