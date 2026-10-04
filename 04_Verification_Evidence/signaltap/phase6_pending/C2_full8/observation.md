# C2 — full8: the full take-set and full-load sweeps / 全取込みと満載スイープ — PENDING

**Evidence class once filled: SILICON.** The Expected columns were written on 2026-10-01, before any capture: the brief's bound, and the RTL-SIM value of the same capture cut from the board-level bench (`hw/tools/cosim_board.py`, the same RTL and host steps; `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/full8_<budget>.json` and `expected_full8_<budget>.vcd.gz`). Fill the Observed column from `phase6_evidence.py`; a difference goes to `reports/discrepancies.md`, not into the design.

**記入後の証拠クラスは SILICON。** 期待値の欄は取得前の 2026-10-01 に記録した。内容は指示書の上限と、基板レベル試験台で同じ取得を切り出した RTL-SIM の値。観測値は `phase6_evidence.py` の出力で埋める。差異は設計を直さず `reports/discrepancies.md` に記録する。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision ____ (`DE10_Nano_wpms` 50 MHz / `DE10_Nano_wpms100` 100 MHz) |
| Date and time | ____ |
| Bitstream | `output_files/____.sof`, Quartus Prime Lite 23.1std.1, commit ____ |
| Switches | SW[1:0] = 11, both up (G = 12, which the expected values assume); SW[2] = 0; SW[3] = 0 |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, pre trigger position (12 %); trigger `tap_ctl[43:40]` = 1000 (P becomes 8); storage qualifier disabled |
| Action | reset (BRD source[0] 1 → 0); arm; `quartus_stp -t host/wpms_phase6_full8_<NMAX>.tcl > full8.log` |
| Files here | `C2_full8.vcd.gz` (the export; if it fails, the `.stp` saved after the acquisition, converted by `hw/tools/stp_log_to_vcd.py`), the host log if any, `observed.json` |
| Analysis | `python3 hw/tools/phase6_evidence.py C2_full8.vcd.gz --budget 50|100 --log <log> --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 1 | g between the packets of a sweep (clocks) | 0 | 0 | 0 | | |
| 2 | T_wake: strobe → first packet_start (clocks) | ≤ 4 (nominal 2) | 2 | 2 | | |
| 3 | window: Stay Set → the Stay word (clocks); floor = window + 2 | floor ≤ N_MIN = 32 | 28 → 30 | 28 → 30 | | |
| 4 | BCP word → inbox_taken, the full take-set (8 blocks, full mask, sweep word) | ≤ 10 | 10 | 10 | | |
| 5 | full-load sweep (Σ N = NMAX): strobe → asleep, housekeeping included (clocks) | ≤ T_min (1,041 / 2,083) | 1023 | 2063 | | |
| 7 | bundles at packet_start equal to the model (equal / compared) | all | 28 / 28 | 14 / 14 | | |
| 7/8 | banks equal to the model (equal / compared) | all | 4 / 4 | 2 / 2 | | |
| — | errors | none | none | none | | |

## Notes / 所見

(pending)
