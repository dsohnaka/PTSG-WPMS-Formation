#!/usr/bin/env python3
# ============================================================================
# isa_from_chapter3.py — derive the translation contract (isa_table.json)
# from the CANON: Layer 1 Chapter 3, not from the deliberation worksheet.
# License: MIT (Layer 3).
#
# The common law of Ch.3 §3.2 is applied mechanically:
#   CL-1  every instruction: FG = HALT
#   CL-3  Q = HALT for all but CMT; CMT is Q-only (BG = HALT, per §3.4)
#   rows  §3.3 / §3.4 / §3.5 tables supply {mode·subop, mnemonic}
# Defect W-D12 (WPMS-Formation amanuensis, 2026-09-03): the previous contract
# was extracted from the v0.3 worksheet. This generator makes canon the source
# and reports agreement with the worksheet-derived file as a cross-check.
# ============================================================================
import json, re, sys, datetime

CH3 = sys.argv[1] if len(sys.argv) > 1 else \
    "../../01_Architecture/PTSG_CPU_Formation_Layer1_Chapter3_The_Formation_Command_Phase_Table.md"
OUT = sys.argv[2] if len(sys.argv) > 2 else "isa_table.json"
OLD = sys.argv[3] if len(sys.argv) > 3 else None   # optional worksheet-derived file to cross-check

text = open(CH3, encoding="utf-8").read()
rows = re.findall(r"^\|\s*(\d)·(\d)\s*\|\s*([A-Z]{3})\s*\|", text, flags=re.M)
if not rows:
    sys.exit("no instruction rows found in Chapter 3")

isa = {
    "provenance": {
        "canon": "Layer 1 Chapter 3 — The Formation Command × Phase Table (DRAFT)",
        "derived_by": "isa_from_chapter3.py",
        "derived_on": datetime.date.today().isoformat(),
        "common_law_applied": ["CL-1 FG=HALT", "CL-3 Q=HALT except CMT", "CMT: Q-only (BG=HALT)"],
    },
    "instructions": {},
    "source_ids": {"0": "IMM", "1": "TEMP", "2": "PPM", "3": "K", "4": "I", "5": "SN", "6": "SSS"},
    "dest_ids": {"0": "TEMP", "1": "PPM_SHADOW", "6": "ADRS"},
}
for mode, subop, mn in rows:
    if mn == "CMT":
        leg = {"FG": "HALT", "BG": "HALT", "Q": "Legal"}
    else:
        leg = {"FG": "HALT", "BG": "Legal", "Q": "HALT"}
    isa["instructions"][mn] = {"mode": int(mode), "subop": int(subop), "legality": leg}

if OLD:
    old = json.load(open(OLD))["instructions"]
    same = {k: v["legality"] for k, v in isa["instructions"].items()} == \
           {k: v["legality"] for k, v in old.items()} and \
           {k: (v["mode"], v["subop"]) for k, v in isa["instructions"].items()} == \
           {k: (v["mode"], v["subop"]) for k, v in old.items()}
    isa["provenance"]["cross_check"] = (
        f"agrees with worksheet-derived {OLD.split('/')[-1]} "
        f"({len(isa['instructions'])}/{len(old)} instructions)" if same
        else f"DISAGREES with {OLD} — a defect to be reported (Ch.3 status note)")
    print("cross-check:", isa["provenance"]["cross_check"])

json.dump(isa, open(OUT, "w"), indent=1)
print(f"{OUT}: {len(isa['instructions'])} instructions derived from canon")
