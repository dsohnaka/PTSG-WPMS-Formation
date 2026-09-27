#!/usr/bin/env python3
# ============================================================================
# vcd_compare.py — compare two VCD files signal by signal, by hierarchical name.
#
#   python3 vcd_compare.py A.vcd B.vcd [--expect-only-b NAME ...] [--max-report N]
#
# Every signal present in both files must have the same value at every time
# stamp (after normalizing vector widths). Signals present in only one file are
# listed; with --expect-only-b / --expect-only-a the listed names (hierarchical
# suffixes, e.g. "dut.stay_value") are the only ones allowed to be one-sided.
# Exit status 0 = identical on the common set and no unexpected one-sided
# signal; 1 = otherwise. License: MIT (Layer 3).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-09-27       Claude Code   Add : First version (Phase 1 bit-identity proof, RH030 vs RH031p).
# ============================================================================
import argparse, sys


def parse(path):
    """Return (widths {name: width}, changes {name: [(time, value), ...]}, end_time)."""
    id_names, widths = {}, {}
    scope = []
    with open(path, encoding="utf-8", errors="replace") as f:
        # ---- header -------------------------------------------------------
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "$scope":
                scope.append(tok[2])
            elif tok[0] == "$upscope":
                scope.pop()
            elif tok[0] == "$var":
                # $var <type> <width> <id> <name> [<range>] $end
                width, ident, name = int(tok[2]), tok[3], tok[4]
                if len(tok) > 6 and tok[5].startswith("["):
                    name += tok[5]
                full = ".".join(scope + [name])
                id_names.setdefault(ident, []).append(full)
                widths[full] = width
            elif tok[0] == "$enddefinitions":
                break
        # ---- value changes ------------------------------------------------
        per_id = {i: [] for i in id_names}
        t = 0
        for line in f:
            if not line or line[0] in "$\n":
                continue
            c = line[0]
            if c == "#":
                t = int(line[1:])
            elif c in "01xzXZ":
                ident = line[1:].strip()
                per_id[ident].append((t, c.lower()))
            elif c in "bBrR":
                parts = line[1:].split()
                # Icarus dumps parameters too; an empty string parameter reads "b <id>"
                val, ident = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
                per_id[ident].append((t, val.lower() if c in "bB" else "r" + val))
    changes = {}
    for ident, names in id_names.items():
        for n in names:
            changes[n] = per_id[ident]
    return widths, changes, t


def norm(v, width):
    """Left-extend a VCD vector value to `width` bits per the VCD rule."""
    if v.startswith("r") or len(v) >= width:
        return v
    fill = v[0] if v[0] in "xz" else "0"
    return fill * (width - len(v)) + v


def squash(seq, width):
    """Normalize, and keep only real changes (drop repeats, keep last per time)."""
    out = []
    for t, v in seq:
        v = norm(v, width)
        if out and out[-1][0] == t:
            out[-1] = (t, v)
        else:
            out.append((t, v))
    ded = []
    for t, v in out:
        if not ded or ded[-1][1] != v:
            ded.append((t, v))
    return ded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--expect-only-a", nargs="*", default=[])
    ap.add_argument("--expect-only-b", nargs="*", default=[])
    ap.add_argument("--max-report", type=int, default=10)
    ap.add_argument("--label-a", default="A"); ap.add_argument("--label-b", default="B")
    args = ap.parse_args()

    wa, ca, ta = parse(args.a)
    wb, cb, tb = parse(args.b)
    common = sorted(set(ca) & set(cb))
    only_a = sorted(set(ca) - set(cb))
    only_b = sorted(set(cb) - set(ca))

    mismatches, n_changes = [], 0
    for n in common:
        if wa[n] != wb[n]:
            mismatches.append((n, "width", wa[n], wb[n]))
            continue
        sa, sb = squash(ca[n], wa[n]), squash(cb[n], wb[n])
        n_changes += len(sa)
        if sa != sb:
            k = next((i for i, (x, y) in enumerate(zip(sa, sb)) if x != y), min(len(sa), len(sb)))
            mismatches.append((n, "values", sa[k] if k < len(sa) else None, sb[k] if k < len(sb) else None))

    def unexpected(names, allowed):
        base = lambda n: n.split("[")[0]          # drop a trailing bit range
        return [n for n in names if not any(base(n).endswith(s) for s in allowed)]

    ua, ub = unexpected(only_a, args.expect_only_a), unexpected(only_b, args.expect_only_b)
    print(f"vcd_compare: {args.label_a} = {args.a}")
    print(f"             {args.label_b} = {args.b}")
    print(f"  end time: {args.label_a} #{ta}, {args.label_b} #{tb}")
    print(f"  signals in both: {len(common)}; value changes compared: {n_changes}")
    print(f"  only in {args.label_a}: {len(only_a)} {only_a[:args.max_report]}")
    print(f"  only in {args.label_b}: {len(only_b)} {only_b[:args.max_report]}")
    print(f"  mismatching common signals: {len(mismatches)}")
    for m in mismatches[:args.max_report]:
        print("   ", m)
    ok = not mismatches and not ua and not ub and ta == tb
    if ua or ub:
        print(f"  UNEXPECTED one-sided signals: {ua + ub}")
    print("  RESULT:", "IDENTICAL on the common set" if ok else "DIFFERENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
