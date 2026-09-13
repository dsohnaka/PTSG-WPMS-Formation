#!/usr/bin/env python3
# ============================================================================
# pfasm_tools.py — validator + reference simulator for PTSG-CPU-Formation
# instruction lists (.pfasm).  License: MIT (Layer 3). Illustrative.
#
# The validator enforces the MECHANICAL LINK: every instruction and its band
# placement is checked against isa_table.json, which is derived from
# Layer 1 Chapter 3 by isa_from_chapter3.py (table-before-RTL, F-F8: what the
# table does not define, this tool rejects).
#
# The simulator is a numeric oracle for datapath programs: 32-bit Q4.28
# accumulator model (this implementation's documented Arena choice), MAC with
# internal product realignment (>>28; see proposed Tie F-T7).
# ============================================================================
import json, math, re, sys

Q = 28
WORD_MIN, WORD_MAX = -(1 << 31), (1 << 31) - 1

def to_fix(v):  return int(round(v * (1 << Q)))
def to_flt(w):  return w / (1 << Q)

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
        m = re.match(r'([A-Z]{3})(?:\s+(#-?\d+|@PPM|TEMP|K|I|SN|SSS|\d+))?$', line)
        if not m:
            raise SyntaxError(f"line {ln}: cannot parse '{line}'")
        prog.append({"ln": ln, "band": band, "mn": m.group(1), "op": m.group(2)})
    return prog

# ---------------------------------------------------------------- validate
SRC_KINDS = {"#": "IMM", "@PPM": "PPM", "TEMP": "TEMP", "K": "K", "I": "I", "SN": "SN", "SSS": "SSS"}

def validate(prog, isa):
    errs = []
    for p in prog:
        mn, band = p["mn"], p["band"]
        if band is None:
            errs.append(f"line {p['ln']}: instruction before any band directive")
            continue
        spec = isa["instructions"].get(mn)
        if spec is None:
            errs.append(f"line {p['ln']}: {mn} — not in the behavior table (E4: no row, no instruction)")
            continue
        legality = spec["legality"].get(band)
        if legality != "Legal":
            errs.append(f"line {p['ln']}: {mn} in {band} band — table says {legality} "
                        f"({'E3' if mn=='CMT' else 'E2' if band=='Q' else 'E1'})")
        # operand-kind checks for source-taking ops
        if mn in ("LDA", "ADD", "SUB", "MUL", "MAC"):
            op = p["op"] or ""
            kind = "IMM" if op.startswith("#") else SRC_KINDS.get(op)
            if kind is None:
                errs.append(f"line {p['ln']}: {mn} — unknown source '{op}' (E4)")
        if mn in ("SAD",) and not (p["op"] or "").isdigit():
            errs.append(f"line {p['ln']}: SAD needs a literal address")
    return errs

# ---------------------------------------------------------------- simulate
def simulate(prog, active_page, page_size=16):
    accm = temp = adrs = 0
    shadow = [0] * page_size
    active = list(active_page) + [0] * (page_size - len(active_page))
    committed = None
    errors = []

    def source(op, ctx):
        if op.startswith("#"): return int(op[1:])
        if op == "@PPM":
            if not (0 <= adrs < page_size): errors.append(f"E5 ADRS out of range at {ctx}")
            return active[adrs] if 0 <= adrs < page_size else 0
        if op == "TEMP": return temp
        raise ValueError(op)

    for p in prog:
        mn, op, ctx = p["mn"], p["op"], f"line {p['ln']}"
        if mn == "SAD": adrs = int(op)
        elif mn == "LDM": accm = source("@PPM", ctx)
        elif mn == "STM":
            if not (0 <= adrs < page_size): errors.append(f"E5 ADRS out of range at {ctx}")
            else: shadow[adrs] = accm
        elif mn == "LDA": accm = source(op, ctx)
        elif mn == "SWP": accm, temp = temp, accm
        elif mn == "ADD": accm = sat(accm + source(op, ctx), errors, ctx)
        elif mn == "SUB": accm = sat(accm - source(op, ctx), errors, ctx)
        elif mn == "MUL": accm = sat((accm * temp) >> Q, errors, ctx)  # demo model
        elif mn == "MAC": accm = sat(((accm * temp) >> Q) + source(op, ctx), errors, ctx)
        elif mn == "CMT": committed = list(shadow)  # boundary swap (oracle view)
        else: raise NotImplementedError(mn)
    return committed, errors

# ---------------------------------------------------------------- main
def main():
    isa = json.load(open(sys.argv[2] if len(sys.argv) > 2 else
                         "../tools/isa_table.json"))
    prog = parse(sys.argv[1])
    errs = validate(prog, isa)
    print(f"validate: {len(prog)} instructions; "
          + ("CLEAN" if not errs else f"{len(errs)} VIOLATIONS"))
    for e in errs: print("  " + e)
    if errs: sys.exit(1)

    coef = [to_fix(1 / math.factorial(n)) for n in range(9, -1, -1)]  # c9..c0
    print("sweep x in [-0.5, +0.5], Q4.28, 10-term Horner:")
    worst = (0, None)
    for i in range(-10, 11):
        x = i * 0.05
        page = [to_fix(x)] + coef            # addr0 = x, addr1..10 = c9..c0
        committed, errors = simulate(prog, page)
        assert not errors, errors
        got, want = to_flt(committed[11]), math.exp(x)
        err = abs(got - want)
        if err > worst[0]: worst = (err, x)
        if i in (-10, 0, 10):
            print(f"  x={x:+.2f}  exp={want:.9f}  got={got:.9f}  |err|={err:.2e}")
    print(f"max |err| over sweep = {worst[0]:.2e} at x={worst[1]:+.2f} "
          f"(Q4.28 LSB = {2**-Q:.2e})")

if __name__ == "__main__":
    main()
