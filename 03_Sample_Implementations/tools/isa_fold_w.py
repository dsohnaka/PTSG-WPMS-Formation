#!/usr/bin/env python3
# ============================================================================
# isa_fold_w.py (v0.2) — derive the PTSG-WPMS-Formation translation contract
# (isa_table_w.json) from the MASTER contract by applying Decision Register W.
#
#   Ch.3 --isa_from_chapter3.py--> isa_table.json --isa_fold_w.py--> isa_table_w.json
#
# Never hand-edited: every change below cites a W-ID. License: MIT (Layer 3).
# ============================================================================
import json, sys, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "isa_table_master_2026-09-03.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "isa_table_w.json"
REGISTER = "Decision Register W v0.6"

m = json.load(open(SRC))
w = {"provenance": {"profile": "PTSG-WPMS-Formation (L2 Formation)", "derived_from": SRC,
                    "master_provenance": m.get("provenance", m.get("source")),
                    "folded": datetime.date.today().isoformat(), "register": REGISTER, "fold_log": []},
     "instructions": {}, "source_ids": {}, "dest_ids": {}}
log = w["provenance"]["fold_log"]

REMOVE = {
    "PSH": "W-T1 OMIT (no data stack)",
    "POP": "W-T1 OMIT (no data stack)",
    "CMT": "W-F25 OMIT (no page pair under W-F24: bundle presentation replaces the page swap)",
    "RTW": "W-F25 OMIT (routing merged into the block store at +0xE)",
    "WSV": "W-F28 RESTRICT (the sweep sequencer is the sole writer of the Stay-value path)",
}
for mn, spec in m["instructions"].items():
    if mn in REMOVE:
        log.append(f"{REMOVE[mn]}: {mn} removed -> E4 in this profile"); continue
    w["instructions"][mn] = json.loads(json.dumps(spec))

BG_ONLY = {"FG": "HALT", "BG": "Legal", "Q": "HALT"}
ADD = [("WSH", 3, 3, "W-F23", "SHV <- Accm[4:0]"),
       ("STP", 4, 0, "W-F26", "Accm <- Accm + clamp(src - Accm, -Temp, +Temp); Temp < 0 -> EW6"),
       ("BCP", 4, 1, "W-F27", "masked copy of the GO's take-set: inbox -> block store, sweep item -> SWEEP.a; HK only (EW4)")]
for mn, mode, sub, wid, sem in ADD:
    w["instructions"][mn] = {"mode": mode, "subop": sub, "legality": dict(BG_ONLY), "added_by": wid, "semantics": sem}
    log.append(f"{wid} EXTEND: {mn} (mode {mode}, sub-op {sub}) added; {sem}")

w["source_ids"] = dict(m["source_ids"])
for k, v in m["dest_ids"].items():
    if k == "6":
        log.append("W-F1 RESTRICT F-F13: dest ID 6 (ADRS) removed -> E4"); continue
    w["dest_ids"][k] = ("STORE" if v == "PPM_SHADOW" else v)
log.append("W-F24 RESTRICT PPM-1/PPM-2: dest ID 1 renamed PPM_SHADOW -> STORE (single block store, write windows)")

w["address_map"] = {
    "ADRS_width": 9,
    "0x000-0x07F": "block store, 8 blocks x 16 slots; datapath write only in HK (else EW4)",
    "0x080-0x0FF": "inbox view (+0xE = staged RT.OUT, +0xD reads 0); read-only (STM -> EW3)",
    "0x100-0x10F": "CUR alias = block order[q] of the packet now playing; write only inside a packet window (else EW4)",
    "0x110-0x117": "COMMIT[b] view: [15:0] mask, [16] RT.OUT bit, [29] copied, [30] armed-in-take-set; read-only",
    "0x118": "staged sweep word (inbox), read-only", "0x119": "SWEEP.a (sweep word in effect), read-only",
    "0x11A": "sequencer status [3:0] q, [7:4] P, [8] HK phase; read-only",
    "other": "E5"}
w["profile_registers"] = {
    "StayVal.s": {"width": 12, "written_by": "sweep sequencer (prefetch of N of the next packet's block)", "W": "W-F22 (amended), W-F28"},
    "StayVal.p": {"width": 12, "loaded_at": "Stay Set (N for a packet Stay, 0 otherwise)", "to": "PTSG-Core stay_value pin (C4-F15)", "W": "W-F22"},
    "SHV": {"width": 5, "written_by": "WSH", "W": "W-F23"},
    "SWEEP.a": {"width": 28, "written_by": "BCP (sweep item), reset to P = 0", "W": "W-F28"}}
w["profile_errors"] = {
    "EW2": "block N outside [N_MIN, NMAX] at prefetch -> Error HALT (W-R9, extended by W-R13)",
    "EW3": "STM into a read-only region (inbox, COMMIT view, status) -> Error HALT",
    "EW4": "write-window violation: store write outside HK not via CUR; CUR write outside a packet window; BCP outside HK -> Error HALT",
    "EW5": "invalid sweep word at BCP: P > 8, repeated block among the first P, or sum N > NMAX -> Error HALT",
    "EW6": "STP with Temp < 0 -> Error HALT"}
w["constants"] = {"NMAX": 2048, "N_MIN": 32, "BLOCKS": 8}

json.dump(w, open(OUT, "w"), indent=1, ensure_ascii=False)
print(f"{OUT}: {len(w['instructions'])} instructions ({len(m['instructions'])} in master); fold log:")
for l in log: print("  " + l)
