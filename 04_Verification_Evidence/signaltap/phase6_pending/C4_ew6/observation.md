# C4 — ew6: EW6 injected by the host (LE0 = −1) / ホストによる EW6 注入（LE0 = −1） — PENDING

**Evidence class once filled: SILICON.** The Expected columns were written on 2026-10-01, before any capture: the brief's bound, and the RTL-SIM value of the same capture cut from the board-level bench (`hw/tools/cosim_board.py`, the same RTL and host steps; `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/ew6_<budget>.json` and `expected_ew6_<budget>.vcd.gz`). Fill the Observed column from `phase6_evidence.py`; a difference goes to `reports/discrepancies.md`, not into the design.

**記入後の証拠クラスは SILICON。** 期待値の欄は取得前の 2026-10-01 に記録した。内容は指示書の上限と、基板レベル試験台で同じ取得を切り出した RTL-SIM の値。観測値は `phase6_evidence.py` の出力で埋める。差異は設計を直さず `reports/discrepancies.md` に記録する。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision ____ (`DE10_Nano_wpms` 50 MHz / `DE10_Nano_wpms100` 100 MHz) |
| Date and time | ____ |
| Bitstream | `output_files/____.sof`, Quartus Prime Lite 23.1std.1, commit ____ |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, pre trigger position (12 %); trigger `tap_ctl[4]` rising (error_flag); storage qualifier disabled |
| Action | reset; arm; `quartus_stp -t host/wpms_phase6_ew6_<NMAX>.tcl > ew6.log` |
| Files here | `C4_ew6.vcd.gz` (the export), the host log if any, `observed.json` |
| Analysis | `python3 hw/tools/phase6_evidence.py C4_ew6.vcd.gz --budget 50|100 --log <log> --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 6 | error_flag: code | EW6 | EW6 | EW6 | | |
| 6 | after the flag: packet_start, bin_valid, non-zero banks (L1 silent) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | | |
| 6 | the Core halts (LED[5]); clocks after the flag | halts | 1000 | 2040 | | |

## Notes / 所見

(pending)
