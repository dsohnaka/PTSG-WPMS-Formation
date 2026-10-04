# C2 — full8: the full take-set and full-load sweeps / 全取込みと満載スイープ — SILICON, 2026-10-04

**Evidence class: SILICON**: the architect's SignalTap capture on the board, 2026-10-04. The Expected columns are copied unchanged from the template written on 2026-10-01, before any capture (`signaltap/phase6_pending/C2_full8/`). The Observed column is `observed.json`, made here by `phase6_evidence.py` and set in the template's own form (`phase6_templates.py` rows).

**証拠クラス：SILICON**（2026-10-04、アーキテクトが基板で取った SignalTap の記録）。期待値の欄は、取得前の 2026-10-01 に書いた雛形（`signaltap/phase6_pending/C2_full8/`）から変えずに写した。観測値の欄は、ここで `phase6_evidence.py` が出した `observed.json` である。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision `DE10_Nano_wpms` (50 MHz: the strobe intervals are 1,041 and 1,042 clocks); NMAX = 1,008; clk_sys 30 % high |
| Date and time | 2026-10-04 21:15:28: the trigger (the log's name in the architect's `.stp`) |
| Bitstream | `output_files/DE10_Nano_wpms.sof`, Quartus Prime Lite 23.1std.1, compiled by the architect (Fitter 20:56:46) from the repository at 8040238 (main after PR #9). The architect's report notes that working files may differ, and gives the file's SHA-256, 14703DBB…2D27. Timing closed with SignalTap in: clk_sys +0.557 ns, TNS 0 (`quartus/2026-10-04_DE10_Nano_wpms_signaltap/`) |
| Switches | SW = 3 read back by the BRD probe before the run (SW[1:0] = 11, G = 12; SW[2] = 0; SW[3] = 0); all three PLLs locked (`reset.log`) |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, trigger at sample 512 (12.5 %); trigger `tap_ctl[43:40]` = 1000 (P becomes 8); storage qualifier disabled (the architect's `.stp`) |
| Action | reset at 21:14:55 (BRD source[0] 1 → 0, read back: `reset.log`); arm; `quartus_stp -t host/wpms_phase6_full8_1008.tcl` at 21:15:28 → GO 2 at sweep 1,541,413 (`full8.log`) |
| Files here | `C2_full8.vcd.gz`, `architect_report/analysis.log`, `architect_report/bitstream_sha256.txt`, `architect_report/capture_validation.json`, `architect_report/discrepancies.md`, `architect_report/observation.md`, `full8.log`, `reset.log`, `observed.json` |
| Analysis | run in this folder: `python3 ../../../03_Sample_Implementations/hw/tools/phase6_evidence.py C2_full8.vcd.gz --budget 50 --log full8.log --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 1 | g between the packets of a sweep (clocks) | 0 | 0 | 0 | 0 | as expected |
| 2 | T_wake: strobe → first packet_start (clocks) | ≤ 4 (nominal 2) | 2 | 2 | 2 | as expected |
| 3 | window: Stay Set → the Stay word (clocks); floor = window + 2 | floor ≤ N_MIN = 32 | 28 → 30 | 28 → 30 | 28 → 30 | as expected |
| 4 | BCP word → inbox_taken, the full take-set (8 blocks, full mask, sweep word) | ≤ 10 | 10 | 10 | 10 | as expected |
| 5 | full-load sweep (Σ N = NMAX): strobe → asleep, housekeeping included (clocks) | ≤ T_min (1,041 / 2,083) | 1023 | 2063 | 1023 | as expected |
| 7 | bundles at packet_start equal to the model (equal / compared) | all | 28 / 28 | 14 / 14 | 28 / 28 | as expected |
| 7/8 | banks equal to the model (equal / compared) | all | 4 / 4 | 2 / 2 | 3 / 3 | equal where compared: 3 of the capture's 4 banks (note 2) |
| — | errors | none | none | none | none | as expected |

## Notes / 所見

1. **The reset and the GO.** The board was reset at 21:14:55, and the script ran at 21:15:28. Its GO is GO 2, at sweep 1,541,413, 32.1 s after the reset. The trigger, P becoming 8, is at sample 512.
2. **Banks: 3 of the capture's 4 are compared, and all 3 are equal.**
   - This capture is 1.5 M sweeps after reset, so the model starts from the complete take of the GO (strobe 1,541,412).
   - The first bank closes the sweep before the take, so the model has no value for it. The RTL-SIM's 4 / 4 starts from reset.
3. **The switch's own registers equal the bench's.** The script reads SWEEP_CLOCKS_MAX = 0x404 (1,028) and STROBE_INTERVAL = 0x412 (1,042); the bench gives 1,028 and 1,042 (`expected/full8_50.json`).
4. **The architect's report** is in `architect_report/`, prepared with another AI assistant's help; local paths are masked.
   - Its figures are these. The `observed.json` here, made with the repository's tool from `full8.log`, equals the report's own in every field.
   - The oracle the report used (SHA-256 68AFAC62…AB20) is the one this repository's tools use.
   - The architect also saved the `.stp` after this capture (2.2 MB, not kept here). `stp_log_to_vcd.py` RH002 converts its stored log to the same 4,096 samples as the export, bit for bit, and its trigger condition holds at the T mark.
5. **Not kept, and not part of this capture:**
   - a later run of the same script (21:28:47, GO 4 at sweep 39,954,571);
   - a second export of this acquisition (21:41:27, equal in every sample).
6. **By ear (the architect):** 「C2、C3は非常に味な音が出ています」 ("C2 and C3 give a very tasteful sound").
7. **The SignalTap build's timing**, sent later the same day: every clock meets, with clk_sys at +0.557 ns and TNS 0 (`quartus/2026-10-04_DE10_Nano_wpms_signaltap/`).

**和文.**
- リセット（21:14:55）のあと 21:15:28 にスクリプトを実行し、GO 2 がスイープ 1,541,413 に入った。
- 項目 1〜5 とバンドル 28 / 28 はすべて期待どおり。
  - バンクは 4 個中 3 個を比べ、すべて一致した。
  - 残る 1 個は取込み前のスイープを閉じるもので、リセットから 1.5 M スイープ後のこの記録では、モデルに値がない。
- アーキテクトの報告（別の AI 支援を受けて作成。ローカルパスは伏せた）と、数値はすべて一致した。保存された `.stp` を変換すると、エクスポートとビット単位で一致した。
