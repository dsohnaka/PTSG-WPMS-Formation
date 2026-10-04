# C1 — origin: the test origin after reset / リセット後の試験原点 — SILICON, 2026-10-04

**Evidence class: SILICON**: the architect's SignalTap capture on the board, 2026-10-04. The Expected columns are copied unchanged from the template written on 2026-10-01, before any capture (`signaltap/phase6_pending/C1_origin/`). The Observed column is `observed.json`, made here by `phase6_evidence.py` and set in the template's own form (`phase6_templates.py` rows).

**証拠クラス：SILICON**（2026-10-04、アーキテクトが基板で取った SignalTap の記録）。期待値の欄は、取得前の 2026-10-01 に書いた雛形（`signaltap/phase6_pending/C1_origin/`）から変えずに写した。観測値の欄は、ここで `phase6_evidence.py` が出した `observed.json` である。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision `DE10_Nano_wpms` (50 MHz: the strobe intervals are 1,041 and 1,042 clocks) |
| Date and time | 2026-10-04; exported 17:06:37, shortly after the acquisition |
| Bitstream | the SignalTap build on the board at 17:06, before the 20:56 compile that C2 ran on. Which commit is to be confirmed by the architect |
| Switches | SW[1:0] = 11 (G = 12): the four banks equal the model at G = 12 |
| SignalTap | `wpms_tap.stp`: clk_sys, depth 4,096, trigger at sample 512 (12.5 %); trigger `tap_ctl[1]` = 1 (the first packet_start); storage qualifier disabled |
| Action | BRD source[0] → 1 (the sound held in reset); arm; source[0] → 0. The strobe count is 1 at the start of the record and 2 at the trigger |
| Files here | `C1_origin.vcd.gz`, `reset.log`, `observed.json` |
| Analysis | run in this folder: `python3 ../../../03_Sample_Implementations/hw/tools/phase6_evidence.py C1_origin.vcd.gz --budget 50 --log reset.log --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 2 | T_wake: strobe → first packet_start (clocks) | ≤ 4 (nominal 2) | 2 | 2 | 2 | as expected |
| 3 | window: Stay Set → the Stay word (clocks); floor = window + 2 | floor ≤ N_MIN = 32 | 28 → 30 | 28 → 30 | 28 → 30 | as expected |
| 4 | BCP word → inbox_taken, sweeps without a take | ≤ 10 | 2 | 2 | 2 | as expected |
| 5 | full-load sweep (Σ N = NMAX): strobe → asleep, housekeeping included (clocks) | ≤ T_min (1,041 / 2,083) | 1023 | 2063 | 1023 | as expected |
| 7 | bundles at packet_start equal to the model (equal / compared) | all | 4 / 4 | 2 / 2 | 4 / 4 | as expected |
| 7/8 | banks equal to the model (equal / compared) | all | 4 / 4 | 2 / 2 | 4 / 4 | as expected |
| — | errors | none | none | none | none | as expected |

## Notes / 所見

1. **The model starts from reset.** The capture begins one strobe after the reset is released, so `reset.log` holds the one line `RESET`. This is the convention of the board README §4.
   - The template's command had no `--log`, and without one the tool does not compare with the model. The generator now adds it (`phase6_templates.py` RH004).
2. **Every item equals the RTL-SIM value at 50 MHz.** The bundles and banks are 4 / 4 each.
3. **Level.** The banks' peak, −24.2 dBFS, is the first four samples of the test origin after the ROM's GO.
4. **Bitstream.** C1 was taken at 17:06, on the build then on the board. C2–C5 ran on the build compiled at 20:56. Which commit the 17:06 build came from is asked of the architect.

**和文.**
- リセット解除の直後から記録が始まるので、モデルはリセットから動かす（`reset.log` は `RESET` の 1 行）。
  - 雛形のコマンドには `--log` が無く、それではモデルと比べない。生成器を直した（RH004）。
- 全項目が 50 MHz の RTL-SIM 値と一致した。バンドルとバンクはそれぞれ 4 / 4。
- 17:06 の取得で、C2〜C5 とは別のビルドである。そのコミットをアーキテクトに確認する。
