#!/usr/bin/env python3
# ============================================================================
# pfasm_as.py — assembler for PTSG-WPMS-Formation window programs (.pfasm):
# each instruction becomes one Core Global word (opcode 0, mode >= 1) with the
# bit layout of hw/tools/decode_map.json — the same JSON gen_decode.py turns
# into the RTL decoder table (one source, two consumers).
#
#   python3 pfasm_as.py prog.pfasm [-o prog.hex] [--allow-removed]
#
# Syntax is the profile's (parsed with pfasm_tools_w.parse, imported, never
# edited). --allow-removed also encodes the rows the profile removed (RTW, CMT,
# PSH, POP, WSV) and STA ADRS, for hardware negative tests only (they decode
# to E4). The .hex output is $readmemh-ready, one word per line, with comments.
# License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
# ============================================================================
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "tools")))
sys.dont_write_bytecode = True                               # keep the golden tools directory clean
import pfasm_tools_w as T                                    # golden model: parse only

DM = json.load(open(os.path.join(HERE, "decode_map.json")))
W = DM["word"]
SRC = DM["source_ids"]
DST = DM["dest_ids"]
SRC_OPND = {"@PPM": "PPM", "TEMP": "TEMP", "K": "K", "I": "I", "SN": "SN", "SSS": "SSS"}
DST_OPND = {"TEMP": "TEMP", "@PPM": "STORE"}
REMOVED_DST_ADRS = 6                                         # master dest ID 6 (ADRS), removed by W-F1


class AsmError(Exception):
    pass


def _lit(op, lo, hi, what):
    if op is None or not re.match(r'^-?(0x[0-9A-Fa-f]+|\d+)$', op):
        raise AsmError(f"{what} needs a numeric literal, got {op!r}")
    v = int(op, 0)
    if not lo <= v <= hi:
        raise AsmError(f"{what} literal {v} outside {lo}..{hi}")
    return v


def word(mode, subop, rid=0, imm=0):
    return ((imm & 0xFFFF) << W["imm"]["lsb"]) | ((rid & 0xF) << W["rid"]["lsb"]) | \
           ((subop & 0xF) << W["subop"]["lsb"]) | ((mode & 0xF) << W["mode"]["lsb"])


def encode(mn, op, allow_removed=False):
    """Return the 32-bit word for one instruction (mnemonic, operand text or None)."""
    spec = DM["instructions"].get(mn)
    if spec is None:
        rem = DM["removed_rows_E4"].get(mn)
        if rem is None or not allow_removed:
            raise AsmError(f"{mn} is not in the profile decode map" + (" (removed row: E4)" if rem else ""))
        return word(rem["mode"], rem["subop"])               # operand ignored: decodes to E4
    kind, mode, subop = spec["kind"], spec["mode"], spec["subop"]
    if kind == "none":
        if op: raise AsmError(f"{mn} takes no operand")
        return word(mode, subop)
    if kind == "src":
        if op and op.startswith("#"):
            return word(mode, subop, SRC["IMM"], _lit(op[1:], -32768, 32767, f"{mn} #imm"))
        if op not in SRC_OPND: raise AsmError(f"{mn}: source {op!r} not in the contract")
        return word(mode, subop, SRC[SRC_OPND[op]])
    if kind == "dst":
        if op == "ADRS" and allow_removed:
            return word(mode, subop, REMOVED_DST_ADRS)         # W-F1: decodes to E4
        if op not in DST_OPND: raise AsmError(f"{mn}: destination {op!r} not in the contract")
        return word(mode, subop, DST[DST_OPND[op]])
    if kind == "lit9":
        return word(mode, subop, 0, _lit(op, 0, 0x1FF, mn))
    if kind == "shift":
        return word(mode, subop, 0, _lit(op, -32768, 32767, mn))
    raise AsmError(f"unknown operand kind {kind}")


def assemble(prog, allow_removed=False):
    """prog: list from pfasm_tools_w.parse. Returns [{'word', 'ln', 'mn', 'op', 'band'}]."""
    out = []
    for p in prog:
        try:
            w = encode(p["mn"], p["op"], allow_removed)
        except AsmError as e:
            raise AsmError(f"line {p['ln']}: {e}")
        out.append(dict(word=w, ln=p["ln"], mn=p["mn"], op=p["op"], band=p["band"]))
    return out


def assemble_file(path, allow_removed=False):
    return assemble(T.parse(path), allow_removed)


def to_hex(words, title):
    lines = [f"// {title} — assembled by pfasm_as.py (decode_map.json v{DM['provenance']['version']})"]
    for i, w in enumerate(words):
        lines.append(f"{w['word']:08X}   // {i:3d}: {w['mn']} {w['op'] or ''}  (line {w['ln']}, {w['band'] or '?'})")
    return "\n".join(lines) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow = "--allow-removed" in sys.argv
    if not args:
        print(__doc__ or "usage: pfasm_as.py prog.pfasm [-o out.hex] [--allow-removed]"); sys.exit(2)
    src = args[0]
    out = args[args.index("-o") + 1] if "-o" in args else None
    try:
        words = assemble_file(src, allow)
    except (AsmError, SyntaxError) as e:
        print(f"pfasm_as: {src}: {e}"); sys.exit(1)
    text = to_hex(words, os.path.basename(src))
    if out:
        open(out, "w").write(text)
        print(f"pfasm_as: {len(words)} words -> {out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
