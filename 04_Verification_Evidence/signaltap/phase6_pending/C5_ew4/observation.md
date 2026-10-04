# C5 — ew4: EW4 injected (ISMCE image: the window writes the store) / EW4 注入（ISMCE 像：窓からストアへ直接書込み） — PENDING

**Evidence class once filled: SILICON.** The Expected columns were written on 2026-10-01, before any capture: the brief's bound, and the RTL-SIM value of the same capture cut from the board-level bench (`hw/tools/cosim_board.py`, the same RTL and host steps; `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/ew4_<budget>.json` and `expected_ew4_<budget>.vcd.gz`). Fill the Observed column from `phase6_evidence.py`; a difference goes to `reports/discrepancies.md`, not into the design.

**記入後の証拠クラスは SILICON。** 期待値の欄は取得前の 2026-10-01 に記録した。内容は指示書の上限と、基板レベル試験台で同じ取得を切り出した RTL-SIM の値。観測値は `phase6_evidence.py` の出力で埋める。差異は設計を直さず `reports/discrepancies.md` に記録する。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision ____ (`DE10_Nano_wpms` 50 MHz / `DE10_Nano_wpms100` 100 MHz) |
| Date and time | ____ |
| Bitstream | `output_files/____.sof`, Quartus Prime Lite 23.1std.1, commit ____ |
| Switches | SW[1:0] = 11, both up (G = 12, which the expected values assume); SW[2] = 0; SW[3] = 0 |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, pre trigger position (12 %); trigger `tap_ctl[4]` rising (error_flag); storage qualifier disabled |
| Action | BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew4.mif`; arm; source[0] → 0; afterwards restore `wpms_r1d.mif` |
| Files here | `C5_ew4.vcd.gz` (the export), the host log if any, `observed.json` |
| Analysis | `python3 hw/tools/phase6_evidence.py C5_ew4.vcd.gz --budget 50|100 --score hw/de10_nano/inject/wpms_r1d_ew4.score --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 6 | error_flag: code | EW4 | EW4 | EW4 | | |
| 6 | after the flag: packet_start, bin_valid, non-zero banks (L1 silent) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | | |
| 6 | the Core halts (LED[5]); clocks after the flag | halts | 1001 | 2041 | | |

## Notes / 所見

(pending)
