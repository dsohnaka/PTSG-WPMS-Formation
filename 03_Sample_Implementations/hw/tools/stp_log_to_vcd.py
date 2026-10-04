#!/usr/bin/env python3
# ============================================================================
# stp_log_to_vcd.py — a SignalTap acquisition stored in a .stp file, written as
# the VCD that SignalTap's own export (File > Export > VCD) would give. For
# when that export fails: save the .stp right after the acquisition and
# convert its stored log here; phase6_evidence.py and vcd_i2s_check.py then
# read the result as they read an export.
#
#   python3 stp_log_to_vcd.py FILE.stp --list
#   python3 stp_log_to_vcd.py FILE.stp OUT.vcd[.gz] [--log N] [--period-ns 20]
#   python3 stp_log_to_vcd.py --check
#
# What the .stp holds (Quartus Prime 23.1, read from the architect's files):
# each acquisition is a <data> element under <trigger><log>, a string of
# '0'/'1' of D x W characters, sample by sample from the oldest;
# within a sample, character i is the node whose data_index is i (the nodes'
# data_index are in the signal set's <presentation>). The <extradata> after
# it marks each sample: '1' stored, 'T' the trigger sample; D is the number
# of marks (the data element's sample_depth can be one less). Every log is
# checked against its own trigger: a condition on one node ('n' == rising
# edge / falling edge / high / low) must hold at the sample marked T, else the
# conversion stops.
# The VCD follows the export's layout (QUARTUS_VCD_EXPORT 1.0): 1 ps, every
# bit its own variable, X at time 0, the acquisition clock listed with two
# time stamps per sample, "Sample n" comments counted from the trigger.
# --check builds a .stp from known data (the board bench's expected EW5
# capture) in Quartus's index order, converts it back, and requires the same
# values; three broken decoders must fail it.
# Evidence class: whatever the capture is (SILICON for the board). License:
# MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-04       Claude Code   Add : First version (Phase 6: an export failed after a capture).
# ============================================================================
import argparse, gzip, os, re, sys, tempfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
HW = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.normpath(os.path.join(HW, "..", ".."))


class StpError(Exception):
    pass


def _index_map(signal_set):
    """name -> data_index, from every element of the signal set that carries both."""
    idx = {}
    for el in signal_set.iter():
        n, i = el.get("name"), el.get("data_index")
        if n is None or i is None:
            continue
        i = int(i)
        if idx.setdefault(n, i) != i:
            raise StpError(f"node {n}: two data_index values ({idx[n]}, {i})")
    if not idx:
        raise StpError("no node with a data_index in the signal set")
    if sorted(idx.values()) != list(range(len(idx))):
        raise StpError("the data_index values are not 0 .. W-1, one each")
    return idx


def _condition(trigger):
    """(node, kind) of a basic one-node trigger condition, else None."""
    levels = [lv for lv in trigger.iter("level") if lv.get("enabled", "yes") == "yes"]
    if len(levels) != 1 or levels[0].get("type", "basic") != "basic":
        return None
    m = re.match(r"\s*'([^']+)'\s*==\s*(rising edge|falling edge|high|low)\s*$", levels[0].text or "")
    return (m.group(1), m.group(2)) if m else None


def logs(path):
    """Every acquisition stored in the file, oldest first per trigger."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise StpError(f"{path}: not XML ({e})")
    out = []
    for inst in root.iter("instance"):
        for ss in inst.iter("signal_set"):
            clock = ss.find("clock")
            for trig in ss.iter("trigger"):
                log = trig.find("log")
                if log is None:
                    continue
                kids = list(log)
                for k, el in enumerate(kids):
                    if el.tag != "data":
                        continue
                    marks = kids[k + 1].text if k + 1 < len(kids) and kids[k + 1].tag == "extradata" else None
                    out.append(dict(instance=inst.get("name"), signal_set=ss, name=el.get("name", ""),
                                    depth=int(el.get("sample_depth", "0")),
                                    trigger_position=int(el.get("trigger_position", "-1")),
                                    bits=(el.text or "").strip(), marks=(marks or "").strip(),
                                    clock=clock.get("name") if clock is not None else None,
                                    condition=_condition(trig)))
    return out


def decode(lg):
    """(names by index, samples as strings of W '0'/'1', trigger sample, note on the trigger check)."""
    idx = _index_map(lg["signal_set"])
    w, bits, marks = len(idx), lg["bits"], lg["marks"]
    if set(bits) - set("01"):
        raise StpError(f"{lg['name']}: the data holds characters other than 0 and 1")
    depth = len(marks)                       # the log's sample_depth attribute can be one short (Core's file)
    if depth == 0 or len(bits) != depth * w:
        raise StpError(f"{lg['name']}: {len(bits)} data characters, not {depth} marked samples x {w} nodes")
    if set(marks) - set("1T") or marks.count("T") != 1:
        found = "".join(sorted(set(marks)))
        raise StpError(f"{lg['name']}: sample marks of length {len(marks)} with '{found}'; this tool knows "
                       f"one mark per sample, '1' (stored) and one 'T' (the trigger). Send the file as it is")
    t = marks.index("T")
    names = [None] * w
    for n, i in idx.items():
        names[i] = n
    samples = [bits[k * w:(k + 1) * w] for k in range(depth)]
    note = "no single-node condition to check"
    cond = lg["condition"]
    if cond and cond[0] in idx:
        i, kind = idx[cond[0]], cond[1]
        now = samples[t][i]
        before = samples[t - 1][i] if t > 0 else None
        ok = {"high": now == "1", "low": now == "0",
              "rising edge": before == "0" and now == "1",
              "falling edge": before == "1" and now == "0"}[kind]
        if not ok:
            raise StpError(f"{lg['name']}: the trigger '{cond[0]}' == {kind} does not hold at the sample "
                           f"marked T ({t}); the file's layout is not the one this tool knows")
        note = f"'{cond[0]}' == {kind} holds at sample {t}, the trigger mark"
    elif cond:
        note = f"the trigger node {cond[0]} is not among the stored nodes"
    return names, samples, t, note


def _ident(k):
    s, k = "", k + 1
    while k:
        k, r = divmod(k - 1, 94)
        s = chr(33 + r) + s
    return s


def _split(name):
    """A Quartus node name ('ent:inst|ent:inst|sig') as (scopes, last name)."""
    parts = name.split("|")
    return [p.split(":")[-1] for p in parts[:-1]], parts[-1]


def _order_key(name):
    m = re.match(r"^(.*)\[(\d+)\]$", name)
    return (m.group(1), -int(m.group(2))) if m else (name, 0)


def write_vcd(lg, out, period_ps=20000):
    names, samples, t, note = decode(lg)
    w, depth, half = len(names), len(samples), period_ps // 2
    clk_name = lg["clock"]
    clk_scopes, clk_last = _split(clk_name) if clk_name else ([], None)
    tree = {}                                                   # scopes -> [(last, index)]
    for i, n in enumerate(names):
        sc, last = _split(n)
        tree.setdefault(tuple(sc), []).append((last, i))
    ids = {i: _ident(i + 1) for i in range(w)}
    clk_id = _ident(0)
    m = re.search(r"(\d{4})/(\d\d)/(\d\d) (\d\d:\d\d:\d\d)", lg["name"])
    date = f"{m.group(2)}/{m.group(3)}/{m.group(1)} {m.group(4)}" if m else "unknown"
    L = ["$comment", f" {os.path.basename(out)}: the stored log \"{lg['name']}\" of instance {lg['instance']},",
         " converted by hw/tools/stp_log_to_vcd.py in the layout of a SignalTap VCD export", "$end",
         "$date", f"  {date}", "$end", "$version", " QUARTUS_VCD_EXPORT 1.0 (stp_log_to_vcd.py RH001)", "$end",
         "$timescale", "  1 ps", "$end"]
    keys = sorted(tree)
    if clk_last is not None and tuple(clk_scopes) not in tree:
        keys = sorted(keys + [tuple(clk_scopes)])
    open_ = []
    for sc in keys:
        while open_ and list(open_) != list(sc[:len(open_)]):
            L.append("$upscope $end")
            open_.pop()
        for s in sc[len(open_):]:
            L.append(f"$scope module {s} $end")
            open_.append(s)
        if clk_last is not None and list(sc) == clk_scopes:
            L.append(f"$var reg 1 {clk_id} {clk_last} $end")
        for last, i in sorted(tree.get(sc, []), key=lambda e: _order_key(e[0])):
            L.append(f"$var reg 1 {ids[i]} {last} $end")
    L += ["$upscope $end"] * len(open_)
    L += ["$enddefinitions $end", "#0", "$dumpvars"]
    if clk_last is not None:
        L.append(f"0{clk_id}")
    L += [f"X{ids[i]}" for i in range(w)] + ["$end"]
    prev = None
    for k, smp in enumerate(samples):
        t0 = half + k * period_ps
        L.append(f"#{t0}")
        tag = " (Start)" if k == 0 else " (Trigger)" if k == t else " (End)" if k == depth - 1 else ""
        if tag:
            L.append(f"$comment Sample {k - t}{tag} $end")
        if clk_last is not None:
            L.append(f"1{clk_id}")
        for i in range(w):
            if prev is None or smp[i] != prev[i]:
                L.append(f"{smp[i]}{ids[i]}")
        prev = smp
        if clk_last is not None:
            L.append(f"#{t0 + half}")
            L.append(f"0{clk_id}")
    L.append(f"#{half + depth * period_ps + half}")
    op = gzip.open if out.endswith(".gz") else open
    with op(out, "wt", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return names, samples, t, note


# ---------------------------------------------------------------------------------------------------
# --check: a .stp made from known data must come back unchanged
# ---------------------------------------------------------------------------------------------------
def _bench_samples(path):
    """(ctl, dat) per clock of a bench VCD as phase6_evidence reads it; tap_dat filled with a fixed
    pseudo-random pattern where the bench holds none, so that every bit of every sample is exercised."""
    import random
    import phase6_evidence as pe
    ctl, dat = pe.read_vcd(path)
    rnd = random.Random(20261004)
    return [(c, dat[k] if k in dat else rnd.getrandbits(304)) for k, c in enumerate(ctl)]


def _make_stp(template, rows, t, path):
    """The template .stp with one stored log of rows ((ctl, dat) per sample), trigger mark at t."""
    with open(template) as f:
        s = f.read()
    idx = {n: int(i) for i, n in re.findall(r'data_index="(\d+)"[^>]*\bname="([^"]+)"', s)}
    w = len(idx)
    pos_c = [idx[f"tap_ctl[{i}]"] for i in range(101)]
    pos_d = [idx[f"tap_dat[{i}]"] for i in range(304)]
    chunks = []
    for c, d in rows:
        b = ["0"] * w
        for i, p in enumerate(pos_c):
            if (c >> i) & 1:
                b[p] = "1"
        for i, p in enumerate(pos_d):
            if (d >> i) & 1:
                b[p] = "1"
        chunks.append("".join(b))
    marks = "1" * t + "T" + "1" * (len(rows) - t - 1)
    log = (f'<log>\n          <data global_temp="1" name="log: Trig @ 2026/10/04 00:00:00 (check)" '
           f'power_up_mode="false" sample_depth="{len(rows)}" trigger_position="{t}">{"".join(chunks)}</data>\n'
           f'          <extradata>{marks}</extradata>\n        </log>\n      </trigger>')
    s = re.sub(r"<log>.*?</log>\s*</trigger>|</trigger>", lambda m: log, s, count=1, flags=re.S)
    s = re.sub(r"(<level enabled=\"yes\" name=\"condition1\" type=\"basic\">)[^<]*",
               lambda m: m.group(1) + "'tap_ctl[4]' == rising edge\n            ", s, count=1)
    with open(path, "w") as f:
        f.write(s)


MUTANTS = [
    ("bits read from the end of each sample",
     lambda names, samples: (names, [x[::-1] for x in samples])),
    ("nodes taken in name order, data_index ignored",
     lambda names, samples: (sorted(names, key=_order_key), samples)),
    ("samples read newest first",
     lambda names, samples: (names, samples[::-1])),
]


def check():
    import phase6_evidence as pe
    template = os.path.join(HW, "de10_nano", "wpms_tap.stp")
    bench = os.path.join(ROOT, "04_Verification_Evidence", "rtl_sim", "2026-10-01_phase6_board", "expected",
                         "expected_ew5_50.vcd.gz")
    rows = _bench_samples(bench)
    err = next((k for k, (c, _) in enumerate(rows) if c & 0x10), None)
    if err is None:
        print(f"FAIL: no error flag in {bench}")
        return 1
    start = max(0, err - 512)
    rows = rows[start:start + 4096]
    t = err - start
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        stp, vcd = os.path.join(tmp, "check.stp"), os.path.join(tmp, "check.vcd")
        _make_stp(template, rows, t, stp)
        lgs = logs(stp)
        if len(lgs) != 1:
            print(f"FAIL: {len(lgs)} logs in the made file")
            return 1
        names, samples, tt, note = write_vcd(lgs[0], vcd)
        pos = {n: i for i, n in enumerate(names)}
        every = all(sum(1 << i for i in range(101) if x[pos[f"tap_ctl[{i}]"]] == "1") == c and
                    sum(1 << i for i in range(304) if x[pos[f"tap_dat[{i}]"]] == "1") == d
                    for x, (c, d) in zip(samples, rows)) and len(samples) == len(rows)
        ctl, dat = pe.read_vcd(vcd)
        want_ctl = [c for c, _ in rows]
        same_ctl = ctl == want_ctl
        same_dat = all(dat[k] == rows[k][1] for k in dat) and set(dat) == {k for k, c in enumerate(want_ctl) if c & 0x82}
        er = pe.errors_of(ctl, dat)
        got = (er[0]["code"], er[0]["packets_after"], er[0]["bins_after"], er[0]["banks_after_nonzero"],
               er[0]["halt_after"]) if er else None
        print(f"made: {len(rows)} samples of {os.path.relpath(bench, ROOT)} in the node order of "
              f"{os.path.relpath(template, ROOT)}, trigger at {t}")
        print(f"  trigger check: {note}")
        print(f"  decoded: all 405 bits of all {len(rows)} samples equal: {every}")
        print(f"  the VCD read by phase6_evidence: tap_ctl per sample equal: {same_ctl}; "
              f"tap_dat at packets and banks equal: {same_dat}")
        print(f"  phase6_evidence on the VCD: error {got} (bench: ('EW5', 0, 0, 0, 11))")
        ok = every and same_ctl and same_dat and tt == t and got == ("EW5", 0, 0, 0, 11)
        print(f"  {'PASS' if ok else 'FAIL'}")

        def as_vals(nm, sm):
            pc = {n: i for i, n in enumerate(nm)}
            out = []
            for x in sm:
                c = 0
                for i in range(101):
                    if x[pc[f"tap_ctl[{i}]"]] == "1":
                        c |= 1 << i
                out.append(c)
            return out
        killed = 0
        for label, mut in MUTANTS:
            nm, sm = mut(list(names), list(samples))
            caught = as_vals(nm, sm) != want_ctl
            killed += caught
            print(f"  mutant '{label}': {'killed' if caught else 'SURVIVED'}")
        ok = ok and killed == len(MUTANTS)
    print(f"stp_log_to_vcd --check: {'PASS' if ok else 'FAIL'} ({killed}/{len(MUTANTS)} mutants killed)")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stp", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--list", action="store_true", help="list the stored logs")
    ap.add_argument("--log", type=int, help="which log (from --list); needed when there are several")
    ap.add_argument("--period-ns", type=float, default=20.0, help="the sample clock's period (20 for 50 MHz)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    if not a.stp:
        ap.error("a .stp file is needed")
    try:
        lgs = logs(a.stp)
        if a.list or not a.out:
            if not lgs:
                print(f"{a.stp}: no stored log")
            for k, lg in enumerate(lgs):
                print(f"[{k}] {lg['instance']}: \"{lg['name']}\", depth {lg['depth']}, trigger position "
                      f"{lg['trigger_position']}, clock {lg['clock']}, condition {lg['condition']}")
            return 0
        if not lgs:
            raise StpError(f"{a.stp}: no stored log (save the .stp after the acquisition)")
        if a.log is None and len(lgs) > 1:
            raise StpError(f"{a.stp}: {len(lgs)} stored logs; choose one with --log (see --list)")
        lg = lgs[a.log or 0]
        names, samples, t, note = write_vcd(lg, a.out, int(round(a.period_ns * 1000)))
        print(f"{a.out}: \"{lg['name']}\", {len(samples)} samples of {len(names)} nodes, trigger at sample {t}")
        print(f"trigger check: {note}")
    except StpError as e:
        print(f"stp_log_to_vcd: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
