# C5 — ew5: EW5 injected (ISMCE image: N = NMAX + 1; BCP re-checks the sum) / EW5 注入（ISMCE 像：N = NMAX + 1、BCP が総和を再検査） — SILICON, 2026-10-04

**Evidence class: SILICON**: the architect's SignalTap capture on the board, 2026-10-04. The Expected columns are copied unchanged from the template written on 2026-10-01, before any capture (`signaltap/phase6_pending/C5_ew5/`). The Observed column is `observed.json`, made here by `phase6_evidence.py` and set in the template's own form (`phase6_templates.py` rows).

**証拠クラス：SILICON**（2026-10-04、アーキテクトが基板で取った SignalTap の記録）。期待値の欄は、取得前の 2026-10-01 に書いた雛形（`signaltap/phase6_pending/C5_ew5/`）から変えずに写した。観測値の欄は、ここで `phase6_evidence.py` が出した `observed.json` である。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision `DE10_Nano_wpms` (50 MHz: the strobe intervals are 1,041 and 1,042 clocks) |
| Date and time | 2026-10-04; exported 21:54:29 |
| Bitstream | as C2's, the same session (to be confirmed by the architect); the PTSG image written by ISMCE |
| Switches | per the template (the expected values here do not depend on G) |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, trigger at sample 512 (12.5 %); trigger `tap_ctl[4]` rising (error_flag); storage qualifier disabled |
| Action | BRD source[0] → 1; ISMCE PTSG ◂ `inject/wpms_r1d_ew5_1008.mif`; arm; source[0] → 0. The record starts one strobe after the release |
| Files here | `C5_ew5.vcd.gz`, `reset.log`, `observed.json` |
| Analysis | run in this folder: `python3 ../../../03_Sample_Implementations/hw/tools/phase6_evidence.py C5_ew5.vcd.gz --budget 50 --log reset.log --score ../../../03_Sample_Implementations/hw/de10_nano/inject/wpms_r1d_ew5_1008.score --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 6 | error_flag: code | EW5 | EW5 | EW5 | EW5 | as expected |
| 6 | after the flag: packet_start, bin_valid, non-zero banks (L1 silent) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | as expected |
| 6 | the Core halts (LED[5]); clocks after the flag | halts | 11 | 11 | 11 | as expected |

## Notes / 所見

1. **The release and the error.** The sound was held in reset while SignalTap was armed, then released. The record starts one strobe after the release, and the error comes in the first sweep (strobe count 2), at the trigger.
2. **Before the error.** The model starts from reset (`reset.log`, the injected score): no packet ran before the error, as in RTL-SIM.
3. **After the flag.** 4 banks are written, all zero. There is no packet_start and no bin. The Core halts 11 clocks after the flag, as in RTL-SIM.
4. **No host log:** ISMCE and the ISSP Editor were driven by hand.

**和文.**
- エラーはリセット解除後の最初のスイープで立った。エラー前にパケットは無い（RTL-SIM と同じ）。
- その後の L1 は無音で、Core は 11 クロック後に停止した。RTL-SIM と同じ。
