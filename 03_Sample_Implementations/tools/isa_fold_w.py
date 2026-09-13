#!/usr/bin/env python3
# ============================================================================
# isa_fold_w.py — derive the PTSG-WPMS-Formation translation contract
# (isa_table_w.json) from the MASTER contract (isa_table.json, itself derived
# from PTSG-CPU-Formation Layer 1 Chapter 3 by isa_from_chapter3.py) by
# applying the profile's Decision Register W mechanically.
#
#   Ch.3 --isa_from_chapter3.py--> isa_table.json --isa_fold_w.py--> isa_table_w.json
#
# The fold is NEVER hand-edited: every change below cites a W-ID.
# License: MIT (Layer 3). Illustrative.
# ============================================================================
import json, sys, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "isa_table_master_2026-09-03.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "isa_table_w.json"

m = json.load(open(SRC))
w = {"provenance": {
        "profile": "PTSG-WPMS-Formation (L2 Formation)",
        "derived_from": SRC,
        "master_provenance": m.get("provenance", m.get("source")),
        "folded": datetime.date.today().isoformat(),
        "register": "Decision Register W v0.5",
        "fold_log": []},
     "instructions": {}, "source_ids": {}, "dest_ids": {}}
log = w["provenance"]["fold_log"]

# --- W-T1: data stack OMIT -> PSH/POP rows removed (fall to E4)
for mn, spec in m["instructions"].items():
    if mn in ("PSH", "POP"):
        log.append(f"W-T1 OMIT: {mn} removed (E4 in this profile)")
        continue
    w["instructions"][mn] = json.loads(json.dumps(spec))

# --- W-F23: new mode-3 sub-op 3 WSH (SHV <- Accm[4:0])
w["instructions"]["WSH"] = {"mode": 3, "subop": 3,
    "legality": {"FG": "HALT", "BG": "Legal", "Q": "HALT"},
    "added_by": "W-F23"}
log.append("W-F23 EXTEND: WSH (mode 3, sub-op 3) added; SHV <- Accm[4:0]")

# --- sources: inherited unchanged (ADRS is ID 7 reserved in the master too)
w["source_ids"] = dict(m["source_ids"])

# --- W-F1: RESTRICT F-F13 -> dest ID 6 (ADRS) removed (E4)
for k, v in m["dest_ids"].items():
    if k == "6":
        log.append("W-F1 RESTRICT F-F13: dest ID 6 (ADRS) removed (E4 in this profile)")
        continue
    w["dest_ids"][k] = v

# --- W-F22 / W-F21 / W-R9: registers and profile error rows (informational)
w["profile_registers"] = {
    "StayVal.s": {"width": 12, "written_by": "WSV", "W": "W-F22"},
    "StayVal.p": {"width": 12, "loaded_at": "Stay Set", "to": "Core external Stay-value input", "W": "W-F22"},
    "SHV": {"width": 5, "written_by": "WSH", "W": "W-F23"},
    "ADRS": {"width": 8, "space": "0x00-0x7F PPM (active/shadow), 0x80-0xFF inbox (read-only to datapath)"}}
w["profile_errors"] = {
    "EW2": "WSV with value 0 or > NMAX (2048) -> Error HALT (W-R9)",
    "EW3": "STM with ADRS in 0x80-0xFF (inbox) -> Error HALT (W-R9)"}
w["NMAX"] = 2048

json.dump(w, open(OUT, "w"), indent=1, ensure_ascii=False)
print(f"{OUT}: {len(w['instructions'])} instructions ({len(m['instructions'])} in master); fold log:")
for l in log: print("  " + l)
