# C4 — ew6: EW6 injected by the host (LE0 = −1) / ホストによる EW6 注入（LE0 = −1） — SILICON, 2026-10-04

**Evidence class: SILICON**: the architect's SignalTap capture on the board, 2026-10-04. The Expected columns are copied unchanged from the template written on 2026-10-01, before any capture (`signaltap/phase6_pending/C4_ew6/`). The Observed column is `observed.json`, made here by `phase6_evidence.py` and set in the template's own form (`phase6_templates.py` rows).

**証拠クラス：SILICON**（2026-10-04、アーキテクトが基板で取った SignalTap の記録）。期待値の欄は、取得前の 2026-10-01 に書いた雛形（`signaltap/phase6_pending/C4_ew6/`）から変えずに写した。観測値の欄は、ここで `phase6_evidence.py` が出した `observed.json` である。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision `DE10_Nano_wpms` (50 MHz: the strobe intervals are 1,041 and 1,042 clocks) |
| Date and time | 2026-10-04 21:43:29 (the script); exported 21:44:23 |
| Bitstream | as C2's, the same session |
| Switches | per the template (the expected values here do not depend on G) |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, trigger at sample 512 (12.5 %); trigger `tap_ctl[4]` rising (error_flag); storage qualifier disabled |
| Action | arm; `quartus_stp -t host/wpms_phase6_ew6_1008.tcl` → GO 6 at sweep 82,243,832 (`ew6.log`). No reset before it: GO_SEQ read 5 (note 1) |
| Files here | `C4_ew6.vcd.gz`, `ew6.log`, `observed.json` |
| Analysis | run in this folder: `python3 ../../../03_Sample_Implementations/hw/tools/phase6_evidence.py C4_ew6.vcd.gz --budget 50 --log ew6.log --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 6 | error_flag: code | EW6 | EW6 | EW6 | EW6 | as expected |
| 6 | after the flag: packet_start, bin_valid, non-zero banks (L1 silent) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | as expected |
| 6 | the Core halts (LED[5]); clocks after the flag | halts | 1000 | 2040 | 1000 | as expected |

## Notes / 所見

1. **The board was not reset before the script.** The architect's order was C2, C4, C5, a restart, C3, so C4 followed C2 without a reset. GO_SEQ read 5, and the GO was GO 6, 28.5 min after the reset of 21:14:55. The template's action begins with a reset.
   - Item 6 does not depend on it: the error, the silence and the halt are measured from the record alone.
   - Without the history, the packet before the error cannot be compared with the model (RTL-SIM: 1 / 1, from reset). That is not an item here.
2. **The error.** It comes at the trigger (sample 512), in the sweep of the logged GO: the strobe count is 82,243,832, the logged sweep.
3. **After the flag.** Three banks are written, all zero. There is no packet_start and no bin. The Core halts 1,000 clocks after the flag, as in RTL-SIM.
4. **The log.** PowerShell wrote it in UTF-16; it is kept here as UTF-8, with the Quartus install path masked. Nothing else is changed. `phase6_evidence.py` RH002 now reads such logs as they are.

**和文.**
- 基板はスクリプトの前にリセットされていない（GO_SEQ = 5）。項目 6 は記録だけで測れるので、影響しない。
- エラー EW6 はトリガ位置で立った。その後の L1 は無音で、Core は 1,000 クロック後に停止した。いずれも RTL-SIM と同じ。
