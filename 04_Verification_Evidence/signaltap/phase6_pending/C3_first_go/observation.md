# C3 — first_go: first sound: the test origin, then one GO / 初音：試験原点、続いて GO 1 回 — PENDING

**Evidence class once filled: SILICON.** The Expected columns were written on 2026-10-01, before any capture: the brief's bound, and the RTL-SIM value of the same capture cut from the board-level bench (`hw/tools/cosim_board.py`, the same RTL and host steps; `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/first_go_<budget>.json` and `expected_first_go_<budget>.vcd.gz`). Fill the Observed column from `phase6_evidence.py`; a difference goes to `reports/discrepancies.md`, not into the design.

**記入後の証拠クラスは SILICON。** 期待値の欄は取得前の 2026-10-01 に記録した。内容は指示書の上限と、基板レベル試験台で同じ取得を切り出した RTL-SIM の値。観測値は `phase6_evidence.py` の出力で埋める。差異は設計を直さず `reports/discrepancies.md` に記録する。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision ____ (`DE10_Nano_wpms` 50 MHz / `DE10_Nano_wpms100` 100 MHz) |
| Date and time | ____ |
| Bitstream | `output_files/____.sof`, Quartus Prime Lite 23.1std.1, commit ____ |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, pre trigger position (12 %); trigger `tap_ctl[43:40]` = 0011 (P becomes 3); storage qualifier **enabled** (`tap_ctl[100]`) |
| Action | reset; listen; arm; `quartus_stp -t host/wpms_phase6_first_go_<NMAX>.tcl > first_go.log`; listen |
| Files here | `C3_first_go.vcd.gz` (the export), the host log if any, `observed.json` |
| Analysis | `python3 hw/tools/phase6_evidence.py C3_first_go.vcd.gz --budget 50|100 --log <log> --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 7 | bundles at packet_start equal to the model (equal / compared) | all | 128 / 128 | 127 / 127 | | |
| 7/8 | banks equal to the model (equal / compared) | all | 47 / 47 | 46 / 46 | | |
| — | errors | none | none | none | | |

Item 8, the sound / 音:

| Quantity | Expected | Observed | Verdict |
|---|---|---|---|
| before the GO (by ear) | the test origin: a steady tone near 996 Hz | | |
| after the GO (by ear) | a C-major triad: left C5 + E5, right E5 + G5 | | |
| spectral peaks, left channel, of the captured banks (dB re the strongest) | RTL-SIM `pcm` case — 50 MHz: 524.4 Hz (0.0 dB), 659.2 Hz (0.0 dB); 100 MHz: 524.4 Hz (0.0 dB), 659.2 Hz (0.0 dB); the model's for the same samples identical | | |
| spectral peaks, right channel, of the captured banks (dB re the strongest) | RTL-SIM `pcm` case — 50 MHz: 660.6 Hz (0.0 dB), 782.2 Hz (0.0 dB); 100 MHz: 660.6 Hz (0.0 dB), 782.2 Hz (0.0 dB); the model's for the same samples identical | | |

## Notes / 所見

(pending)
