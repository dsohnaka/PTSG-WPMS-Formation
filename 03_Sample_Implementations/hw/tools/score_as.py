#!/usr/bin/env python3
# ============================================================================
# score_as.py — a small assembler for PTSG-Core scores that host
# PTSG-WPMS-Formation windows: Core words (Core Ch.2 §2.2; the recap in
# PTSG-Core/03_Sample_Implementations/examples/README.md) plus the profile's
# timing-signal bits TS_PKT and TS_CSEL (Deliverable 3 §4, W-F19; bit positions
# from hw/tools/decode_map.json) and Formation windows assembled by pfasm_as.py.
#
#   python3 score_as.py score.score [-o out]      (writes out.hex and out.mif)
#
# Source (one statement per line, ';' comments):
#   .depth N              instruction-memory depth (default 4096; Core IMEM_DEPTH)
#   .trap  ADDR           where the Formation's error insertion lands (its TRAP_ADDR;
#                         default depth-1): a foreground Prog End is placed there, on
#                         which the Core HALTs (C3-F23 -> C3-F24)
#   .window NAME FILE     a .pfasm window program (path relative to the score, then to
#                         03_Sample_Implementations/instruction_lists)
#   .equ   NAME VALUE     a constant
#   LABEL:                a label (alone or before a statement)
#   Stay N | Branch OFF|LABEL | Jump ADDR|LABEL            opcodes 1, 2, 3
#   Reset | BaseSet | StaySet | Return | Call OFF|LABEL | Loop N | ProgEnd | NOP
#                                                           Global internal sub-ops 0-7
#   Window NAME           the window's Formation Global words, spliced here
#   Word VALUE            a raw word
# Timing-signal specs (after the operand; only on words whose D16-D31 are timing
# signals: Stay, Branch, Jump, Reset, StaySet, NOP): PKT (TS_PKT = 1),
# CSEL=STROBE|NONEMPTY|MORE|n (TS_CSEL), TS=VALUE (other bits, OR-ed).
# Branch LABEL encodes the 12-bit relative offset (target - here) mod 4096 (Core:
# taken -> state_number + operand); Call LABEL likewise in D16-D31. Jump LABEL is
# absolute; a Jump to address 0 would encode the indirect Jump, so it is refused.
# License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (SILICON_BRIEF Phase 2).
# ============================================================================
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import pfasm_as as A

LISTS = os.path.normpath(os.path.join(HERE, "..", "..", "instruction_lists"))
TSB = A.DM["timing_signal_bits"]
TS_PKT = 1 << TSB["TS_PKT"]["bit"]
CSEL_LSB, CSEL_W = TSB["TS_CSEL"]["lsb"], TSB["TS_CSEL"]["width"]
CSEL = {"STROBE": 0, "NONEMPTY": 1, "MORE": 2}
OPC = {"Stay": 1, "Branch": 2, "Jump": 3}
SUB = {"Reset": 0, "BaseSet": 1, "StaySet": 2, "Return": 3, "Call": 4, "Loop": 5, "ProgEnd": 6, "NOP": 7}
TS_WORDS = {"Stay", "Branch", "Jump", "Reset", "StaySet", "NOP"}


class ScoreError(Exception):
    pass


def num(tok, equ, labels=None):
    if labels is not None and tok in labels: return labels[tok]
    if tok in equ: return equ[tok]
    try:
        return int(tok, 0)
    except ValueError:
        raise ScoreError(f"not a number, constant or label: {tok!r}")


def parse(path):
    """Returns (statements, directives). A statement: dict(ln, label?, mn, arg, ts)."""
    st, equ, windows, labels_pending = [], {}, {}, []
    depth, trap = 4096, None
    for ln, raw in enumerate(open(path), 1):
        line = raw.split(";")[0].strip()
        if not line: continue
        m = re.match(r"^([A-Za-z_]\w*):\s*(.*)$", line)
        if m:
            labels_pending.append((m.group(1), ln)); line = m.group(2).strip()
            if not line: continue
        f = line.split()
        if f[0] == ".depth": depth = int(f[1], 0); continue
        if f[0] == ".trap": trap = f[1]; continue
        if f[0] == ".equ": equ[f[1]] = int(f[2], 0); continue
        if f[0] == ".window":
            p = os.path.join(os.path.dirname(os.path.abspath(path)), f[2])
            if not os.path.exists(p): p = os.path.join(LISTS, f[2])
            if not os.path.exists(p): raise ScoreError(f"line {ln}: window file {f[2]} not found")
            windows[f[1]] = (p, A.assemble_file(p)); continue
        mn = f[0]
        if mn not in OPC and mn not in SUB and mn not in ("Window", "Word"):
            raise ScoreError(f"line {ln}: unknown statement {mn!r}")
        arg, ts, rest = None, 0, f[1:]
        needs_arg = mn in ("Stay", "Branch", "Jump", "Call", "Loop", "Window", "Word")
        if needs_arg:
            if not rest: raise ScoreError(f"line {ln}: {mn} needs an operand")
            arg, rest = rest[0], rest[1:]
        tsspec = []
        for t in rest:
            if t == "PKT": ts |= TS_PKT
            elif t.startswith("CSEL="):
                v = t[5:]; c = CSEL[v] if v in CSEL else int(v, 0)
                if not 0 <= c < (1 << CSEL_W): raise ScoreError(f"line {ln}: CSEL {v} out of range")
                ts |= c << CSEL_LSB
            elif t.startswith("TS="): ts |= int(t[3:], 0) & 0xFFFF
            else: raise ScoreError(f"line {ln}: cannot read {t!r}")
            tsspec.append(t)
        if tsspec and mn not in TS_WORDS:
            raise ScoreError(f"line {ln}: {mn} has no timing-signal field (D16-D31 is its operand)")
        s = dict(ln=ln, mn=mn, arg=arg, ts=ts, tsspec=tsspec, labels=[l for l, _ in labels_pending])
        labels_pending = []
        st.append(s)
    if labels_pending: raise ScoreError(f"label {labels_pending[0][0]} at the end of the score")
    return st, dict(depth=depth, trap=trap, equ=equ, windows=windows)


def assemble(path):
    st, d = parse(path)
    equ, windows, depth = d["equ"], d["windows"], d["depth"]
    # pass 1: addresses
    labels, a = {}, 0
    for s in st:
        for l in s["labels"]:
            if l in labels: raise ScoreError(f"line {s['ln']}: label {l} defined twice")
            labels[l] = a
        s["addr"] = a
        a += len(windows[s["arg"]][1]) if s["mn"] == "Window" else 1
    trap = depth - 1 if d["trap"] is None else num(d["trap"], equ, labels)
    if a > trap: raise ScoreError(f"score of {a} words overruns the trap word at 0x{trap:03X}")
    # pass 2: words
    words = []                                               # (addr, word, comment)
    for s in st:
        mn, arg, ts, here = s["mn"], s["arg"], s["ts"], s["addr"]
        tag = (",".join(s["labels"]) + ": ") if s["labels"] else ""
        tss = (" " + " ".join(s["tsspec"])) if s["tsspec"] else ""
        if mn == "Window":
            path_w, ws = windows[arg]
            for k, w in enumerate(ws):
                words.append((here + k, w["word"], f"{tag if k == 0 else ''}[{arg}] {w['mn']} {w['op'] or ''}".rstrip()))
            continue
        if mn == "Word":
            words.append((here, num(arg, equ, labels) & 0xFFFFFFFF, f"{tag}Word")); continue
        if mn in OPC:
            if mn == "Stay":
                n = num(arg, equ)
                if not 1 <= n <= 4096: raise ScoreError(f"line {s['ln']}: Stay {n} outside 1..4096")
                op = n & 0xFFF                               # 4096 -> 0 (C4-F15)
            elif mn == "Branch":
                op = ((num(arg, equ, labels) - here) if arg in labels else num(arg, equ)) & 0xFFF
            else:
                op = num(arg, equ, labels)
                if op == 0: raise ScoreError(f"line {s['ln']}: Jump 0 is the indirect Jump; use another address")
                if not 0 < op < 4096: raise ScoreError(f"line {s['ln']}: Jump target out of range")
            words.append((here, (ts << 16) | (op << 4) | OPC[mn], f"{tag}{mn} {arg}{tss}")); continue
        ext = ts
        if mn == "Call":
            ext = ((num(arg, equ, labels) - here) if arg in labels else num(arg, equ)) & 0xFFFF
        elif mn == "Loop":
            ext = num(arg, equ) & 0xFFFF
        words.append((here, (ext << 16) | (SUB[mn] << 8), f"{tag}{mn}{(' ' + arg) if arg else ''}{tss}"))
    words.append((trap, SUB["ProgEnd"] << 8, "TRAP: foreground Prog End -> Core HALT (C3-F23/C3-F24); Formation error insertion lands here"))
    return words, dict(depth=depth, trap=trap, labels=labels, size=a)


def to_hex(words, info, title):
    L = [f"// {title} — assembled by score_as.py (decode_map.json v{A.DM['provenance']['version']})",
         f"// depth {info['depth']}, {info['size']} words + trap word at 0x{info['trap']:03X}; "
         f"labels: " + ", ".join(f"{k}=0x{v:03X}" for k, v in info["labels"].items())]
    prev = -1
    for a, w, c in words:
        if a != prev + 1: L.append(f"@{a:03X}")
        L.append(f"{w:08X}   // {a:03X}: {c}")
        prev = a
    return "\n".join(L) + "\n"


def to_mif(words, info, title):
    L = [f"-- {title} — assembled by score_as.py (decode_map.json v{A.DM['provenance']['version']})",
         f"DEPTH = {info['depth']};", "WIDTH = 32;", "ADDRESS_RADIX = HEX;", "DATA_RADIX = HEX;", "CONTENT BEGIN"]
    prev = -1
    for a, w, c in words:
        if a > prev + 1:
            L.append(f"[{prev + 1:X}..{a - 1:X}] : 00000000;" if a - 1 > prev + 1 else f"{prev + 1:X} : 00000000;")
        L.append(f"{a:X} : {w:08X};   -- {c}")
        prev = a
    if prev < info["depth"] - 1:
        L.append(f"[{prev + 1:X}..{info['depth'] - 1:X}] : 00000000;" if info["depth"] - 1 > prev + 1 else f"{prev + 1:X} : 00000000;")
    L.append("END;")
    return "\n".join(L) + "\n"


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print("usage: score_as.py score.score [-o out]"); sys.exit(2)
    src = args[0]
    out = args[args.index("-o") + 1] if "-o" in args else os.path.splitext(src)[0]
    try:
        words, info = assemble(src)
    except (ScoreError, A.AsmError, SyntaxError) as e:
        print(f"score_as: {src}: {e}"); sys.exit(1)
    title = os.path.basename(src)
    open(out + ".hex", "w").write(to_hex(words, info, title))
    open(out + ".mif", "w").write(to_mif(words, info, title))
    print(f"score_as: {info['size']} words (+ trap at 0x{info['trap']:03X}) -> {out}.hex, {out}.mif")


if __name__ == "__main__":
    main()
