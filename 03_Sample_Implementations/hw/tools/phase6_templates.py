#!/usr/bin/env python3
# ============================================================================
# phase6_templates.py — the observation templates of the Phase 6 SignalTap
# captures (SILICON_BRIEF Phase 6: "SignalTap captures exported to VCD with
# observation.md for each"), written BEFORE any capture: for every capture
# of hw/de10_nano/README.md §4 an observation.md whose Expected column holds
# the brief's bound and the RTL-SIM value at both budgets (from the
# cosim_board.py JSONs: the same RTL, the same host steps, the capture cut as
# SignalTap will hold it), and whose Observed column is empty.
#
#   python3 phase6_templates.py [--expected DIR] [--out DIR] [--check]
#     DIR defaults: 04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected
#                   04_Verification_Evidence/signaltap/phase6_pending
# License: MIT (Layer 3 tooling).
# ----------------------------------------------------------------------------
# REVISION HISTORY(RH)
# 001 2026-10-01       Claude Code   Add : First version (SILICON_BRIEF Phase 6).
# ============================================================================
import argparse, json, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
EVID = os.path.join(PROFILE, "04_Verification_Evidence")
DEF_EXP = os.path.join(EVID, "rtl_sim", "2026-10-01_phase6_board", "expected")
DEF_OUT = os.path.join(EVID, "signaltap", "phase6_pending")
NMAX = {50: 1008, 100: 2048}
TMIN = {50: 1041, 100: 2083}

CAPTURES = [
    # (folder, case, title EN, title JA, trigger, qualifier, action)
    ("C1_origin", "origin", "the test origin after reset", "リセット後の試験原点",
     "`tap_ctl[1]` = 1 (the first packet_start)", "disabled",
     "BRD source[0] → 1 (the sound held in reset); arm SignalTap; source[0] → 0"),
    ("C2_full8", "full8", "the full take-set and full-load sweeps", "全取込みと満載スイープ",
     "`tap_ctl[43:40]` = 1000 (P becomes 8)", "disabled",
     "reset (BRD source[0] 1 → 0); arm; `quartus_stp -t host/wpms_phase6_full8_<NMAX>.tcl > full8.log`"),
    ("C3_first_go", "first_go", "first sound: the test origin, then one GO", "初音：試験原点、続いて GO 1 回",
     "`tap_ctl[43:40]` = 0011 (P becomes 3)", "**enabled** (`tap_ctl[100]`)",
     "reset; listen; arm; `quartus_stp -t host/wpms_phase6_first_go_<NMAX>.tcl > first_go.log`; listen"),
    ("C4_ew6", "ew6", "EW6 injected by the host (LE0 = −1)", "ホストによる EW6 注入（LE0 = −1）",
     "`tap_ctl[4]` rising (error_flag)", "disabled",
     "reset; arm; `quartus_stp -t host/wpms_phase6_ew6_<NMAX>.tcl > ew6.log`"),
    ("C5_ew2", "ew2", "EW2 injected (ISMCE image: N = 16 in the playing block)", "EW2 注入（ISMCE 像：再生中ブロックに N = 16）",
     "`tap_ctl[4]` rising (error_flag)", "disabled",
     "BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew2.mif`; arm; source[0] → 0; afterwards restore `wpms_r1d.mif`"),
    ("C5_ew3", "ew3", "EW3 injected (ISMCE image: a store into the inbox view)", "EW3 注入（ISMCE 像：受信箱ビューへの書込み）",
     "`tap_ctl[4]` rising (error_flag)", "disabled",
     "BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew3.mif`; arm; source[0] → 0; afterwards restore `wpms_r1d.mif`"),
    ("C5_ew4", "ew4", "EW4 injected (ISMCE image: the window writes the store)", "EW4 注入（ISMCE 像：窓からストアへ直接書込み）",
     "`tap_ctl[4]` rising (error_flag)", "disabled",
     "BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew4.mif`; arm; source[0] → 0; afterwards restore `wpms_r1d.mif`"),
    ("C5_ew5", "ew5", "EW5 injected (ISMCE image: N = NMAX + 1; BCP re-checks the sum)", "EW5 注入（ISMCE 像：N = NMAX + 1、BCP が総和を再検査）",
     "`tap_ctl[4]` rising (error_flag)", "disabled",
     "BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew5_<NMAX>.mif`; arm; source[0] → 0; afterwards restore `wpms_r1d.mif`"),
]


def load(d, case, bud):
    p = os.path.join(d, f"{case}_{bud}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def v(x):
    if x is None:
        return "—"
    if isinstance(x, list) and len(x) == 2 and all(isinstance(y, (int, float)) for y in x) and x[0] == x[1]:
        return str(x[0])
    if isinstance(x, list) and len(x) == 1:
        return str(x[0])
    return str(x).replace("'", "")


def peaks(pk):
    """[(Hz, dB), ...] -> '524.4 Hz (0.0 dB), 659.2 Hz (0.0 dB)'."""
    if not pk:
        return "—"
    return ", ".join(f"{f:.1f} Hz ({abs(d) if d == 0 else d:.1f} dB)" for f, d in pk)


ORDER = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "7/8": 8, "—": 9}


def rows_for(case, J):
    """[(item, quantity, bound, f(dry-run dict, full observed dict, budget) -> text)]"""
    R = []
    if case in ("origin", "full8", "first_go"):
        if case != "first_go":
            R.append(("2", "T_wake: strobe → first packet_start (clocks)", "≤ 4 (nominal 2)",
                      lambda d, o, b: v(d.get("t_wake"))))
            R.append(("3", "window: Stay Set → the Stay word (clocks); floor = window + 2", "floor ≤ N_MIN = 32",
                      lambda d, o, b: f"{v(d.get('window'))} → {v(d.get('floor'))}"))
        if case == "full8":
            R.append(("1", "g between the packets of a sweep (clocks)", "0", lambda d, o, b: v(d.get("g"))))
            R.append(("4", "BCP word → inbox_taken, the full take-set (8 blocks, full mask, sweep word)", "≤ 10",
                      lambda d, o, b: v(d.get("bcp_full_take"))))
        if case == "origin":
            R.append(("4", "BCP word → inbox_taken, sweeps without a take", "≤ 10", lambda d, o, b: v(d.get("bcp"))))
        if case in ("origin", "full8"):
            R.append(("5", "full-load sweep (Σ N = NMAX): strobe → asleep, housekeeping included (clocks)",
                      "≤ T_min (1,041 / 2,083)", lambda d, o, b: v(d.get("full_load_length"))))
        R.append(("7", "bundles at packet_start equal to the model (equal / compared)", "all",
                  lambda d, o, b: f"{(d.get('bundles') or {}).get('equal')} / {(d.get('bundles') or {}).get('compared')}"))
        R.append(("7/8", "banks equal to the model (equal / compared)", "all",
                  lambda d, o, b: f"{(d.get('pcm') or {}).get('equal')} / {(d.get('pcm') or {}).get('compared')}"))
        R.append(("—", "errors", "none", lambda d, o, b: v([e["code"] for e in d.get("errors", [])] or "none")))
    else:
        R.append(("6", "error_flag: code", f"{J['code']}", lambda d, o, b: v([e["code"] for e in d.get("errors", [])])))
        R.append(("6", "after the flag: packet_start, bin_valid, non-zero banks (L1 silent)", "0, 0, 0",
                  lambda d, o, b: ", ".join(str(d["errors"][0][k]) for k in ("packets_after", "bins_after",
                                                                              "banks_after_nonzero"))
                  if d.get("errors") else "—"))
        R.append(("6", "the Core halts (LED[5]); clocks after the flag", "halts",
                  lambda d, o, b: v((o.get("errors") or [{}])[0].get("halt_after"))))
    return sorted(R, key=lambda r: ORDER[r[0]])


def template(folder, case, en, ja, trig, qual, action, E):
    J = dict(code={"ew2": "EW2", "ew3": "EW3", "ew4": "EW4", "ew5": "EW5", "ew6": "EW6"}.get(case, ""))
    L = [f"# {folder.replace('_', ' — ', 1)}: {en} / {ja} — PENDING",
         "",
         "**Evidence class once filled: SILICON.** The Expected columns were written on 2026-10-01, before any "
         "capture: the brief's bound, and the RTL-SIM value of the same capture cut from the board-level bench "
         "(`hw/tools/cosim_board.py`, the same RTL and host steps; "
         f"`04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/{case}_<budget>.json` and "
         f"`expected_{case}_<budget>.vcd.gz`). Fill the Observed column from `phase6_evidence.py`; a difference "
         "goes to `reports/discrepancies.md`, not into the design.",
         "",
         "**記入後の証拠クラスは SILICON。** 期待値の欄は取得前の 2026-10-01 に記録した。内容は指示書の上限と、"
         "基板レベル試験台で同じ取得を切り出した RTL-SIM の値。観測値は `phase6_evidence.py` の出力で埋める。"
         "差異は設計を直さず `reports/discrepancies.md` に記録する。",
         "",
         "| | |", "|---|---|",
         "| Board, revision | DE10-nano 5CSEBA6U23I7; revision ____ (`DE10_Nano_wpms` 50 MHz / `DE10_Nano_wpms100` 100 MHz) |",
         "| Date and time | ____ |",
         "| Bitstream | `output_files/____.sof`, Quartus Prime Lite 23.1std.1, commit ____ |",
         f"| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, pre trigger position (12 %); trigger {trig}; "
         f"storage qualifier {qual} |",
         f"| Action | {action} |",
         f"| Files here | `{folder}.vcd.gz` (the export), the host log if any, `observed.json` |",
         f"| Analysis | `python3 hw/tools/phase6_evidence.py {folder}.vcd.gz --budget 50|100"
         + (" --log <log>" if case in ("full8", "first_go", "ew6") else "")
         + (f" --score hw/de10_nano/inject/wpms_r1d_{case}{'_<NMAX>' if case == 'ew5' else ''}.score"
            if case in ("ew2", "ew3", "ew4", "ew5") else "") + " --json observed.json` |",
         "",
         "## Expected and observed / 期待値と観測値",
         "",
         "| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |",
         "|---|---|---|---|---|---|---|"]
    for item, q, bound, f in rows_for(case, J):
        cells = []
        for bud in (50, 100):
            o = (E.get(bud) or {}).get("observed") or {}
            d = o.get("signaltap_dry_run") or {}
            cells.append(f(d, o, bud) if d.get("found") else "—")
        L.append(f"| {item} | {q} | {bound} | {cells[0]} | {cells[1]} | | |")
    if case == "first_go":
        P = {b: ((E.get(("pcm", b)) or {}).get("observed") or {}) for b in (50, 100)}
        L += ["", "Item 8, the sound / 音:", "",
              "| Quantity | Expected | Observed | Verdict |", "|---|---|---|---|",
              "| before the GO (by ear) | the test origin: a steady tone near 996 Hz | | |",
              "| after the GO (by ear) | a C-major triad: left C5 + E5, right E5 + G5 | | |"]
        for ch, side in (("L", "left"), ("R", "right")):
            L.append(f"| spectral peaks, {side} channel, of the captured banks (dB re the strongest) | RTL-SIM `pcm` "
                     f"case — 50 MHz: {peaks(P[50].get(f'spectrum_peaks_captured_{ch}'))}; 100 MHz: "
                     f"{peaks(P[100].get(f'spectrum_peaks_captured_{ch}'))}; the model's for the same samples "
                     f"identical | | |")
    L += ["", "## Notes / 所見", "", "(pending)", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected", default=DEF_EXP)
    ap.add_argument("--out", default=DEF_OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    bad = 0
    for folder, case, en, ja, trig, qual, action in CAPTURES:
        E = {b: load(a.expected, case, b) for b in (50, 100)}
        if case == "first_go":
            for b in (50, 100):
                E[("pcm", b)] = load(a.expected, "pcm", b)
        if any(E[b] is None for b in (50, 100)):
            print(f"  missing {case}_50/100.json in {a.expected}")
            bad += 1
            continue
        text = template(folder, case, en, ja, trig, qual, action, E)
        p = os.path.join(a.out, folder, "observation.md")
        if a.check:
            same = os.path.exists(p) and open(p).read() == text
            bad += not same
            print(f"  {'same' if same else 'DIFFERENT'}  {folder}/observation.md")
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(text)
            print(f"  wrote {folder}/observation.md")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
