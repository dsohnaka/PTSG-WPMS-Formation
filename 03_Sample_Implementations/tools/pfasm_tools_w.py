#!/usr/bin/env python3
# ============================================================================
# pfasm_tools_w.py — validator + reference oracle for PTSG-WPMS-Formation
# (L2 Formation) instruction lists. Inherits the master's pfasm_tools.py
# (PTSG-CPU-Formation Layer 3) and adds the profile's rows:
#
#   * contract = isa_table_w.json (folded from the master contract by
#     isa_fold_w.py; W-F1 / W-T1 / W-F23 applied mechanically)
#   * SHV shift register + WSH (W-F23): MUL/MAC realign by >> SHV; the
#     program owns its Q-convention. Reset value SHV = 0 (pure integer MAC).
#   * StayVal.s <- WSV with EW2 (0 or > NMAX -> Error HALT)   (W-F22, W-R9)
#   * 256-word address space: 0x00-0x7F PPM active/shadow, 0x80-0xFF inbox
#     (read-only to the datapath: STM there -> EW3)           (deliverable 1)
#   * quartet sources K / I / SN / SSS modelled as supplied constants
#     (the master oracle raised on them; profile-side extension, W-D11)
#   * STA destination checked against dest_ids (ADRS absent -> E4, W-F1)
#
# Product model: 64-bit product, arithmetic shift, truncation (deliverable 1 §2).
# License: MIT (Layer 3). Illustrative, not normative.
# ============================================================================
import json, math, re, sys

WORD_MIN, WORD_MAX = -(1 << 31), (1 << 31) - 1
PPM_WORDS, INBOX_BASE, SPACE = 128, 128, 256

def to_fix(v, q): return int(round(v * (1 << q)))
def to_flt(w, q): return w / (1 << q)

def sat(w, errors, ctx):
    if w < WORD_MIN or w > WORD_MAX:
        errors.append(f"E8 arithmetic overflow at {ctx}")
        return max(WORD_MIN, min(WORD_MAX, w))
    return w

# ---------------------------------------------------------------- parse
def parse(path):
    prog, band = [], None
    for ln, raw in enumerate(open(path), 1):
        line = raw.split(';')[0].strip()
        if not line: continue
        if line.startswith('.window'): continue
        if line == '.bg': band = 'BG'; continue
        if line == '.q':  band = 'Q';  continue
        m = re.match(r'([A-Z]{3})(?:\s+(#-?\d+|@PPM|TEMP|K|I|SN|SSS|ADRS|\d+))?$', line)
        if not m: raise SyntaxError(f"line {ln}: cannot parse '{line}'")
        prog.append({"ln": ln, "band": band, "mn": m.group(1), "op": m.group(2)})
    return prog

# ---------------------------------------------------------------- validate
SRC_KINDS = {"@PPM": "PPM", "TEMP": "TEMP", "K": "K", "I": "I", "SN": "SN", "SSS": "SSS"}
DST_KINDS = {"TEMP": "TEMP", "@PPM": "PPM_SHADOW", "ADRS": "ADRS"}

def validate(prog, isa):
    errs = []
    srcs, dsts = set(isa["source_ids"].values()), set(isa["dest_ids"].values())
    for p in prog:
        mn, band, op = p["mn"], p["band"], p["op"] or ""
        if band is None:
            errs.append(f"line {p['ln']}: instruction before any band directive"); continue
        spec = isa["instructions"].get(mn)
        if spec is None:
            errs.append(f"line {p['ln']}: {mn} — not in the profile contract (E4: no row, no instruction)"); continue
        legality = spec["legality"].get(band)
        if legality != "Legal":
            errs.append(f"line {p['ln']}: {mn} in {band} band — table says {legality} "
                        f"({'E3' if mn=='CMT' else 'E2' if band=='Q' else 'E1'})")
        if mn in ("LDA", "ADD", "SUB", "MUL", "MAC"):
            kind = "IMM" if op.startswith("#") else SRC_KINDS.get(op)
            if kind is None or kind not in srcs:
                errs.append(f"line {p['ln']}: {mn} — source '{op}' not in contract (E4)")
        if mn == "STA":
            kind = DST_KINDS.get(op)
            if kind is None or kind not in dsts:
                errs.append(f"line {p['ln']}: STA — destination '{op}' not in contract (E4; W-F1 if ADRS)")
        if mn == "SAD" and not op.isdigit():
            errs.append(f"line {p['ln']}: SAD needs a literal address")
    return errs

# ---------------------------------------------------------------- simulate
def simulate(prog, active_page, quartet=None, inbox=None, nmax=2048):
    quartet = quartet or {"K": 0, "I": 0, "SN": 0, "SSS": 0}
    accm = temp = adrs = shv = 0
    stayval_s = None
    active = list(active_page) + [0] * (PPM_WORDS - len(active_page))
    shadow = list(active)                      # F-F14 profile-side (W-R8): shadow inherits active
    inbox = list(inbox or []) + [0] * (SPACE - INBOX_BASE - len(inbox or []))
    committed, errors = None, []

    def rd(a, ctx):
        if not (0 <= a < SPACE): errors.append(f"E5 ADRS out of range at {ctx}"); return 0
        return active[a] if a < INBOX_BASE else inbox[a - INBOX_BASE]

    def source(op, ctx):
        if op.startswith("#"): return int(op[1:])
        if op == "@PPM": return rd(adrs, ctx)
        if op == "TEMP": return temp
        if op in quartet: return quartet[op]
        raise ValueError(op)

    for p in prog:
        mn, op, ctx = p["mn"], p["op"], f"line {p['ln']}"
        if   mn == "SAD": adrs = int(op)
        elif mn == "LDM": accm = rd(adrs, ctx); adrs += 1
        elif mn == "STM":
            if not (0 <= adrs < SPACE): errors.append(f"E5 ADRS out of range at {ctx}")
            elif adrs >= INBOX_BASE:    errors.append(f"EW3 STM into inbox at {ctx}")
            else: shadow[adrs] = accm
            adrs += 1
        elif mn == "LDA": accm = source(op, ctx)
        elif mn == "STA":
            if op == "TEMP": temp = accm
            elif op == "@PPM":
                if adrs >= INBOX_BASE: errors.append(f"EW3 STA into inbox at {ctx}")
                else: shadow[adrs] = accm
        elif mn == "SWP": accm, temp = temp, accm
        elif mn == "ADD": accm = sat(accm + source(op, ctx), errors, ctx)
        elif mn == "SUB": accm = sat(accm - source(op, ctx), errors, ctx)
        elif mn == "MUL": accm = sat((accm * source(op, ctx)) >> shv, errors, ctx)
        elif mn == "MAC": accm = sat(((accm * temp) >> shv) + source(op, ctx), errors, ctx)
        elif mn == "SFT": accm = sat(accm >> int(op) if int(op) >= 0 else accm << -int(op), errors, ctx)
        elif mn == "WSH": shv = accm & 0x1F
        elif mn == "WSV":
            v = accm & 0xFFF
            if v == 0 or v > nmax: errors.append(f"EW2 Stay value {v} out of 1..{nmax} at {ctx}")
            stayval_s = v
        elif mn in ("WLV", "WJV", "RTW"): pass   # not modelled in this oracle
        elif mn == "CMT": committed = list(shadow)
        else: raise NotImplementedError(mn)
    return committed, errors, {"SHV": shv, "StayVal.s": stayval_s}

# ---------------------------------------------------------------- main
def main():
    isa = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "isa_table_w.json"))
    prog = parse(sys.argv[1])
    errs = validate(prog, isa)
    print(f"validate: {len(prog)} instructions; " + ("CLEAN" if not errs else f"{len(errs)} VIOLATIONS"))
    for e in errs: print("  " + e)
    if errs: sys.exit(1)
    Q = 28
    coef = [to_fix(1 / math.factorial(n), Q) for n in range(9, -1, -1)]
    print("sweep x in [-0.5, +0.5], program-owned Q4.28 (SHV=28), 10-term Horner:")
    worst = (0, None)
    for i in range(-10, 11):
        x = i * 0.05
        committed, errors, regs = simulate(prog, [to_fix(x, Q)] + coef)
        if errors:
            print("oracle: " + "; ".join(sorted(set(errors))))
            print("        (a program that does not own its Q — no WSH — overflows: the ISA speaks integers)")
            sys.exit(2)
        got, want = to_flt(committed[11], Q), math.exp(x)
        err = abs(got - want)
        if err > worst[0]: worst = (err, x)
        if i in (-10, 0, 10):
            print(f"  x={x:+.2f}  exp={want:.9f}  got={got:.9f}  |err|={err:.2e}")
    print(f"max |err| over sweep = {worst[0]:.2e} at x={worst[1]:+.2f} (Q4.28 LSB = {2**-Q:.2e}); SHV={regs['SHV']}")

if __name__ == "__main__":
    main()
