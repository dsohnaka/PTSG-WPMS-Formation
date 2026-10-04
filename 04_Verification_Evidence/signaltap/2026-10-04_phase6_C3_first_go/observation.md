# C3 — first_go: first sound: the test origin, then one GO / 初音：試験原点、続いて GO 1 回 — SILICON, 2026-10-04

**Evidence class: SILICON**: the architect's SignalTap capture on the board, 2026-10-04. The Expected columns are copied unchanged from the template written on 2026-10-01, before any capture (`signaltap/phase6_pending/C3_first_go/`). The Observed column is `observed.json`, made here by `phase6_evidence.py` and set in the template's own form (`phase6_templates.py` rows).

**証拠クラス：SILICON**（2026-10-04、アーキテクトが基板で取った SignalTap の記録）。期待値の欄は、取得前の 2026-10-01 に書いた雛形（`signaltap/phase6_pending/C3_first_go/`）から変えずに写した。観測値の欄は、ここで `phase6_evidence.py` が出した `observed.json` である。

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7; revision `DE10_Nano_wpms` (50 MHz) |
| Date and time | 2026-10-04. The reset was about 22:12:35, and the GO (sweep 781,956) about 16 s later. Both are derived from the second run, which started at 22:16:06. The export is from 22:14:48 |
| Bitstream | as C2's, the same session (to be confirmed by the architect) |
| Switches | SW[1:0] = 11 (G = 12): the three banks equal the model at G = 12 |
| SignalTap | trigger `tap_ctl[43:40]` = 0011 (P becomes 3) at sample 512 of 4,096. The template asks for the storage qualifier enabled (`tap_ctl[100]`); the record is neither every clock nor only those events (note 2) |
| Action | a restart of the board after C5 (the architect's order: C2, C4, C5, a restart, C3); arm; `quartus_stp -t host/wpms_phase6_first_go_1008.tcl` (the captured run; its log was overwritten); a second run at 22:16:06 (GO 3), whose log is `first_go.log` |
| Files here | `C3_first_go.vcd.gz`, `analysis_first_go.log`, `first_go.log`, `observed.json` |
| Analysis | run in this folder: `python3 ../../../03_Sample_Implementations/hw/tools/phase6_evidence.py C3_first_go.vcd.gz --budget 50 --log analysis_first_go.log --json observed.json` |

## Expected and observed / 期待値と観測値

| Item | Quantity | Bound (brief) | RTL-SIM 50 MHz | RTL-SIM 100 MHz | Observed (SILICON) | Verdict |
|---|---|---|---|---|---|---|
| 7 | bundles at packet_start equal to the model (equal / compared) | all | 128 / 128 | 127 / 127 | 11 / 11 | equal where captured: 11 of the planned 128 (notes 2, 3) |
| 7/8 | banks equal to the model (equal / compared) | all | 47 / 47 | 46 / 46 | 3 / 3 | equal where captured: 3 of the planned 47 (notes 2, 3) |
| — | errors | none | none | none | none | as expected |

Item 8, the sound / 音:

| Quantity | Expected | Observed | Verdict |
|---|---|---|---|
| before the GO (by ear) | the test origin: a steady tone near 996 Hz | not reported separately | — |
| after the GO (by ear) | a C-major triad: left C5 + E5, right E5 + G5 | the architect: 「非常に味な音」 ("a very tasteful sound") | reported as pleasing; the chord itself not stated (asked) |
| spectral peaks, left channel, of the captured banks (dB re the strongest) | RTL-SIM `pcm` case — 50 MHz: 524.4 Hz (0.0 dB), 659.2 Hz (0.0 dB); 100 MHz: 524.4 Hz (0.0 dB), 659.2 Hz (0.0 dB); the model's for the same samples identical | not measured: 3 banks in the record | not measured |
| spectral peaks, right channel, of the captured banks (dB re the strongest) | RTL-SIM `pcm` case — 50 MHz: 660.6 Hz (0.0 dB), 782.2 Hz (0.0 dB); 100 MHz: 660.6 Hz (0.0 dB), 782.2 Hz (0.0 dB); the model's for the same samples identical | not measured: 3 banks in the record | not measured |

## Notes / 所見

1. **The captured run's log was overwritten.** The architect ran the script twice, both times with `> first_go.log`.
   - The first run is the one captured: its GO is GO 2, at sweep 781,956, about 16 s after a reset.
   - The second run, at 22:16:06, applied GO 3 at sweep 10,103,934. `first_go.log` is its log.
   - Before its own GO, the second run read back GO_SEQ = 2 and APPLIED_SAMPLE = 781,956. That is the captured GO. The script labels these "the ROM's GO", because it assumes it runs right after a reset.
   - **The analysis input.** `analysis_first_go.log` holds the second run's 51 writes, which are the script's fixed list, with the captured GO's read-back as its `applied` line.
   - Every captured bundle and bank equals the model run from this input. A wrong placement of the GO would not.
2. **The record is not every clock.**
   - Three times, the strobe count steps without a stored strobe, at samples 517, 1,559 and 1,799.
   - One sweep holds 560 samples instead of about 1,042 (samples 2,836 → 3,396).
   - Between these points the samples run clock by clock, in the RTL's sequence. The six strobes in the record need about 6,250 clocks, but it holds 4,096 samples.
   - Nor is it the template's qualified record. That one stores only the clocks with `tap_ctl[100]` set (packet_start or bank_we), and only 14 of these samples have that bit.
   - **The hardware played every sweep.** The banks at strobes 781,960 and 781,961 come after the gaps, and they equal the model. The phases build up sweep by sweep, so a skipped or shortened sweep would show. The gaps are in the record.
   - **Not used:** the tool's per-clock figures for this capture (strobe interval 560 / 2,003, g 241, sweep 1,696). They are artefacts of the gaps.
   - **The cause is open.** It is either a storage-qualifier setting other than the template's, or a fault in the acquisition. The architect's C3 setting is asked.
3. **Coverage.** The record holds 11 bundles and 3 banks, against the 128 and 47 a qualified record would hold. The spectral peaks need the banks of many sweeps; with 3, they are not measured.
4. **By ear (the architect):** 「C2、C3は非常に味な音が出ています」 ("C2 and C3 give a very tasteful sound"). Whether the chord after the GO was C major (left C5 + E5, right E5 + G5) was not stated; it is asked.
5. **The order.** C3 was taken last, after a restart that followed C5. That is as it should be: C5's injected images must give way to the normal score (`wpms_r1d.mif`) first, and the bundles here equal the normal score's model.

**和文.**
- 記録された GO は 2 回目（スイープ 781,956）。その実行のログは、2 回目の実行（22:16:06）で上書きされた。
  - 2 回目が GO の前に読み戻した値（GO_SEQ = 2、APPLIED_SAMPLE = 781,956）を使い、書込み 51 語（スクリプトの固定列）と合わせて解析入力とした。
  - 記録されたバンドル 11 個とバンク 3 個は、すべてモデルと一致した。
- 記録はクロックごとではなく、途中に 4 か所の欠けがある。
  - 欠けの後のバンクもモデルと一致するので、ハードウェアは全スイープを正しく演奏している。欠けは記録の側にある。
  - 原因（ストレージ・クオリファイアの設定か、取得の不具合か）は未解決で、アーキテクトに設定を伺う。
- バンクが 3 個しかないので、スペクトルは測れない。聴感は「非常に味な音」と報告された。C メジャーに聞こえたかどうかを伺う。
- C3 は C5 の後、再起動してから取った。注入像を通常の譜（`wpms_r1d.mif`）に戻すためにも正しい順序で、バンドルは通常の譜のモデルと一致した。
