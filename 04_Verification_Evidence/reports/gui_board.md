# WPMS host control GUI — on the board / ホスト制御 GUI——実機

*CC0 · prepared 2026-10-14 by Claude Code for the architect, per `GUI_BRIEF_WPMS_Host_Control_2026-10-14` §7. **OUTSIDE WPMS** (Layer 3 tooling, a stand-in for the Layer 4 controller). Before the board: `gui_v1_v3.md`.*

*State: **measured on 2026-10-15.** The architect ran P2 and P3 on the board. Every scripted number is far better than expected, REJECT[0] stayed 0 throughout, and by ear: no clicks, no zipper noise, PANIC as expected. Both sessions replay clean in RTL-SIM. The expected values below were written on 2026-10-14, before any board number existed (Silicon Brief §5); they are left as written. Evidence class of the measured column: **SILICON**, except the R rows (**RTL-SIM**).*

*状態：**2026-10-15 実測。** アーキテクトが実機で P2・P3 を実行した。スクリプトの数値はすべて期待を大きく上回り、REJECT[0] は全期間 0。耳ではクリックもジッパーもなく、PANIC も期待どおり。期待値は 2026-10-14、実機の数値がない時点で書いたまま残す。実測欄の証拠区分は SILICON（R 行は RTL-SIM）。*

---

## 0. Rulings applied (2026-10-14) / 適用した裁定

1. `gui_board.md` is prepared with the expected column filled first, as in Phase 6.
2. **A board session replayed in RTL-SIM must start at the test origin.** Connect right after the image is loaded, or press **Test origin** first. `cosim_gui_replay.py` reports a log that did not start there; such a log is not evidence.

## 1. What runs / 走らせるもの

| Tool | Where |
|---|---|
| `wpms_bridge.tcl` | `03_Sample_Implementations/hw/tools/host/gui/`, under `quartus_stp -t` |
| `wpms_ctl.py measure` | the same folder: M1–M4 below, scripted, with `--log` and `--csv` |
| `wpms_gui.py` | the same folder: S1–S6 below, by hand and by ear |
| `cosim_gui_replay.py` | here (no board): each session's log through the switch RTL |

A dry run of this whole procedure was made against the stand-ins with the test's freeze model (`measure --n 300 --seconds 3`, then its log replayed in RTL-SIM). It set up four blocks from the test origin (block 0 shrank first, then 1–3 joined) and made 1,755 level GOs. There were 0 refusals, and the replay passed with 1,760 / 1,760 GOs applied and 0 host writes refused. Its times measure the stand-in, not JTAG, and are not shown here.

## 2. Procedure / 手順

**P0. Board and PC.**

- The Phase 6 image is loaded (50 MHz revision: NMAX 1,008).
- SW[1:0] = 11 (G = 12), SW[2] = 0, SW[3] = 0.
- HDMI goes to a monitor with speakers.
- The In-System Sources and Probes Editor is **closed** (one ISSP session at a time).
- For the reset, use SW[2] up → down instead of BRD.
- SignalTap: record whether it is open (row S7).

**P1. The bridge** (terminal 1, in `hw/tools/host/gui/`):

```
quartus_stp -t wpms_bridge.tcl
```

It prints `wpms: DE-SoC [USB-1] / @2: 5CSEBA6… , HOST = instance <k>, source …`, then `wpms_bridge: listening on 127.0.0.1:50707`. Leave it running.

**P2. The measurements** (terminal 2, same folder; right after the image is loaded, or after SW[2] up → down; about 1.5 minutes):

```
python wpms_ctl.py measure --n 1000 --seconds 60 --csv board_times.csv --log board_measure.json > board_measure.txt
```

Do not redirect with PowerShell `>`, which writes UTF-16. Use `cmd.exe`, or `| Out-File -Encoding utf8 board_measure.txt`.

It makes:

- **M1:** 1,000 reads of ID, timed by the bridge.
- **M2:** 10 s of master-gain writes, as fast as the sender goes.
- Then it sets up blocks 0–3, N = 240 each, −6 dB, playing.
- **M3:** 60 s of random level changes on those four blocks.
- **M4:** REJECT[0] before and after M3.

You hear four notes (C4, E4, G4, C5) whose levels jump at random, gliding at 60 dB/s.

**P3. The GUI by hand** (terminal 2):

```
python wpms_gui.py --connect
```

Press **Test origin** first, then work through S1–S6 (§3). At the end:

- **Save log** → `board_gui.json`;
- **Save times** → `board_gui_times.csv`.

**P4. Close.** In the GUI, **Shut bridge down**, or Ctrl-C in terminal 1.

**P5. Send back:**

- `board_measure.txt`, `board_measure.json`, `board_times.csv`;
- `board_gui.json`, `board_gui_times.csv`;
- a screenshot of the GUI at the end, with its Status panel;
- notes on S1–S7 (one line each is enough);
- a short recording, if convenient.

**P6. Here (no board):**

```
python cosim_gui_replay.py board_measure.json board_gui.json
```

## 3. Expected and measured / 期待値と実測

*t* = one ISSP transaction. A knob GO costs 4 transactions in one batch: the changed slots (LPT, LE0), COMMIT go-now and a read of GO_SEQ. One APPLIED_SEQ poll follows; the apply takes at most 2 sample periods (42 µs), far below *t*. A status poll (6 reads) runs every 250 ms and, while knobs move, at most once between knob GOs. That status poll is why the rates below sit under the brief's estimates, which counted one transaction per update.

### Scripted (P2) / スクリプト

| # | Item | Expected | From | Measured |
|---|---|---|---|---|
| M0 | `wpms_ctl.py` first line | `ID 57504D53, CONFIG 0003F081 (NMAX 1008); sweep [0], N [1008]` | Phase 6 image, the ROM's test origin | ID 57504D53, CONFIG 0003F081, NMAX 1,008; sweep [0], N [1008] (the log's connect record; `board_measure.txt` arrived empty, so every M value here is recomputed from `board_measure.json`) ✓ |
| M1 | One ISSP transaction (`<us>` of the bridge), mean and max over 1,000 reads | mean 5 … 30 ms; max < 100 ms | brief §7 (ESTIMATE) | **mean 0.409 ms, median 0.369, p99 1.47, max 3.49 ms** (1,000 reads of ID, all = 57504D53): **12 × faster** than the lower bound — deviation D1 |
| M1h | Its histogram (`board_times.csv`; table in the output) | most reads within one 5 ms bin; few above 2 × median | — | 94.3 % within 0 … 0.5 ms; 99.4 % below 2 ms (table in §4) ✓ |
| M2 | Master-gain update rate | 19 … 179 /s, i.e. (1 / *t*) × 250 / (250 + 6 *t* [ms]) for *t* = 30 … 5 ms; the brief's 33 … 200 /s leaves out the status poll | this controller | **1,826 /s** (18,263 writes in 10.0 s): above the range, because *t* is (D1). With the measured *t* = 0.41 ms the formula gives 2,415 /s; the rest is one TCP round trip and Python per write, ≈ 0.13 ms |
| M3 | Block-level GO rate, four blocks | 4 … 36 /s: one GO = 5 *t*, plus one status poll per 250 ms; the brief's ≈ 6 … 100 /s | this controller | **374 /s** (22,445 level GOs in 60.0 s on blocks 0–3; interval median 2.38 ms, p99 6.7, max 18.1 ms): above the range, because *t* is (D1); 5 *t* + 2 round trips ≈ 2.3 ms predicts the median |
| M3p | APPLIED_SEQ polls per GO | **1.00**: the apply (≤ 42 µs) lands before the first poll | Ch.5 §5.4.3; V3 | **0.992** (22,266 polls for 22,445 GOs: 179 applies were seen first by a status poll, which also reads APPLIED_SEQ) ✓ |
| M3l | GO sent → apply seen | ≈ 2 *t*: 10 … 60 ms median | the above | median **0.57 ms**, p99 2.5, max 7.9 ms (from the batch's reply to the APPLY): one poll after the batch; the range was written for the estimated *t* (D1) |
| M4 | REJECT[0] before → after M3 | **unchanged**; refused 0, errors 0 | brief §4 | **0 → 0** (240 status reads over 70.6 s, every one 0); refused 0, ISSP errors 0; CLIP 0 in all 240 reads; GO_SEQ 1 → 22,451 ✓ |
| R1 | `cosim_gui_replay.py board_measure.json` | **PASS**: host writes refused by the RTL 0; APPLY with APPLIED_SEQ = GO_SEQ: all; samples equal the models; started at the test origin: True | V3 | **PASS** (3 h 15 min of simulation): started at the test origin; 22,450 GOs, all accepted by the RTL (0 host writes refused of 85,664); APPLY with APPLIED_SEQ = GO_SEQ 22,450 / 22,450; GO → play from strobe 2 (1.59 … 1.93 periods); 263,418 transactions = switch_model's; **67,816 / 67,816 samples** and 269,834 bundles equal the models; overrun 0 ✓ |

### By hand and by ear (P3) / 手と耳

| # | Action | Expected | Measured |
|---|---|---|---|
| S1 | **Test origin** | Its GO is applied; the panel follows the switch: play [0], Σ N = 1,008 / 1,008, MG_TARGET 0 dB. The tone (≈ 996 Hz) sounds as at power-on | As expected: the sliders went back to their initial values (the architect). In the log: TEST_ORIGIN was the first write, at 11.3 s; its GO (22,453) applied at once; the resync read sweep [0], N0 = 1,008 ✓ |
| S2 | Block 0: **N** 1,008 → 240; tick **Play** on blocks 1, 2, 3 (ticking before shrinking N is refused, with the reason in red) | block 0 re-seeded with the panel's note (C4); then C4, E4, G4, C5; Σ N = 960 / 1,008; REJECT[0] +0. Quieter than the origin: about −26 dBFS peak for the four at −6 dB (ESTIMATE: 4 × 0.5 × √(π / γ) ≈ 205 bin amplitudes, × 2⁻¹² at G = 12), against the origin's −12.4 dBFS | As expected: ticking blocks 1–3 in turn, "the Dirichlet kernels sounded one after another like a scale" (the architect). In the log: blocks 0–3 seeded, 3 SWEEP_COMMITs; REJECT[0] 0 ✓ |
| S3 | **Level** of one block swept fast, end to end, many times | the level follows with the glide (60 dB/s); **no clicks** | **No clicks at all** (the architect). In the log: 782 level GOs on block 3 ✓ |
| S4 | **Centre** and **Spacing** of one block swept | the pitch moves without zipper noise (PITCH: phase-continuous) | **No zipper noise at all**; while the centre was moved fast across the main lobe, "a very tasteful sound" (the architect). In the log: 1,429 PITCH GOs on block 0, up to 80 GOs in one second ✓ |
| S5 | **Width γ** swept | the timbre and loudness change smoothly (phases continue) | Smooth (the architect, with S3–S4). In the log: 590 envelope GOs on block 0 ✓ |
| S6 | **PANIC**, then MG_TARGET slider back to 0 dB | silence within MG_RATE's slew: −72 dB after 1.2 s, the floor after 3.2 s at 60 dB/s; then back up at 60 dB/s | "PANIC works perfectly and beautifully" (the architect). MG read back by the status poll after PANIC: −9.8 dB at 0.17 s, −41.5 at 0.69 s, **−72.5 at 1.22 s**, −135.0 at 2.25 s, **the floor −192.7 dB at 3.28 s**, then held; exactly 60 dB/s ✓. The slider was not moved back after PANIC (the architect, 2026-10-18): the log is complete |
| S7 | SignalTap open or closed during P2 / P3 | no expectation; recorded. If open: M1 with it, and once with it closed, if possible | **closed** (the architect, 2026-10-18): every time in §4.1 is without SignalTap |
| S8 | Status panel after S1–S6 | REJECT[0] "+0 since connect"; errors 0; pending "no GO" at rest | In the log: REJECT[0] 0 in all 655 status reads; refused 0; errors 0 ✓. Screenshot of a later session, 2026-10-18 (`media/wpms_gui_2026-10-18_screenshot.png`): all eight blocks playing, Σ N = 1,008 / 1,008, G override 8; REJECT[0] 0 "(+0 since connect)", errors 0, pending "no GO"; ISSP 0.49 ms last, 0.80 / 4.18 ms mean / max over 7,300 ✓ |
| R2 | `cosim_gui_replay.py board_gui.json` | **PASS**, as R1 | **PASS**: started at the test origin (Test origin pressed first); 2,808 GOs, all accepted by the RTL (0 host writes refused of 10,494); APPLY with APPLIED_SEQ = GO_SEQ 2,809 / 2,809; GO → play from strobe 2; 36,178 transactions = switch_model's; 9,571 / 9,571 samples equal the models ✓ |

## 4. Results / 結果

Files: `04_Verification_Evidence/host_gui/2026-10-15_board/`:

- `step_logs/`: `board_measure.json.gz`, `wpms_gui_20261015_195411.json.gz` (the two sessions);
- `times/`: `board_times.csv.gz`, `wpms_times_20261015_195429.csv.gz` (every transaction time);
- `logs/`: the two replays and `board_stats.txt` (the numbers below, recomputed from the logs).

### 4.1 Transaction-time histogram (SILICON) / トランザクション時間の分布

`<us>` of the bridge: the time of one `wpms_write` or `wpms_read` inside quartus_stp, JTAG only.

| Bin | M1: 1,000 ID reads | P2 all: 132,831 | P3 (GUI) all: 20,250 |
|---|---|---|---|
| 0 … 0.5 ms | 943 (94.3 %) | 123,233 (92.8 %) | 13,962 (69.0 %) |
| 0.5 … 1 ms | 44 (4.4 %) | 6,580 (5.0 %) | 4,759 (23.5 %) |
| 1 … 2 ms | 7 (0.7 %) | 1,744 (1.3 %) | 1,217 (6.0 %) |
| 2 … 5 ms | 6 (0.6 %) | 1,274 (1.0 %) | 307 (1.5 %) |
| 5 … 10 ms | 0 | 0 | 5 (0.02 %) |
| ≥ 10 ms | 0 | 0 | 0 |
| mean / median / max | 0.409 / 0.369 / 3.49 ms | 0.433 / 0.380 / 4.15 ms | 0.562 / 0.427 / 7.12 ms |

Writes and reads cost the same: 0.432 and 0.434 ms mean over P2. P3's slightly longer times come while the GUI and Tk run on the same PC.

### 4.2 Deviations / 逸脱

- **D1 — one ISSP transaction is 0.41 ms, not 5 … 30 ms.** The 5 … 30 ms was the brief's ESTIMATE, written before anything ran on this path. The other expected numbers (M2, M3, M3l) were derived from it, so they are low by the same factor. The formulas themselves hold with the measured *t*:
  - M2: 1 / (*t* + one TCP round trip) ≈ 1 / 0.55 ms ≈ 1,830 /s; measured 1,826 /s.
  - M3: 5 *t* + 2 round trips ≈ 2.3 ms per GO; measured median interval 2.38 ms.
  - M3p: one APPLIED_SEQ poll per GO; measured 0.992.

  Cause: each transaction is one `write_source_data` and, mostly, one `read_probe_data` (the switch acknowledges within microseconds). quartus_stp and the USB-Blaster II do each of these in about 0.2 ms, which nothing here had measured before. It is a finding about the JTAG path, not a defect.
- **D2 — `board_measure.txt` arrived empty** (0 bytes; most likely the redirect). Nothing is lost: every M value is recomputed from `board_measure.json`, which holds every transaction with its time and reply (`logs/board_stats.txt`).
- **D3 — the GUI session did not connect at the origin.** It connected after P2, with four blocks playing. **Test origin was its first write**, as the ruling allows. `cosim_gui_replay.py` RH002 now accepts exactly that, and still fails any other start.

### 4.3 What this means for the knobs / つまみにとっての意味

- **Master gain:** one transaction per update, about 1,800 updates/s.
- **Block knob (LEVEL, PITCH, envelope):** about 400 GOs/s with the apply confirmed before the next GO.
- **Fast hand:** the GUI session's fastest second carried 80 GOs. The sender kept up with the hand, and the coalescing law never had to drop more than the intermediate values of a drag.
- **Limits:** the JTAG path is not the limit for knobs. A MIDI input (the next step in the brief §8) at a few hundred events per second fits.

### 4.4 Discrepancies filed / 記録した食い違い

None. Nothing needed the switch to change.

### 4.5 The recording of 2026-10-18 / 2026-10-18 の録音

`media/wpms_test001_2026-10-18.flac`: 26.2 s, 48 kHz, 24 bit, stereo. It is lossless from the WAV the architect sent (the decoded PCM has the same MD5). It was recorded in a later session than the logs, the one in the screenshot, with the eight blocks playing. The analysis is `logs/recording_analysis.py` → `.txt`, and its class is SILICON (an analog recording).

- **Level.** Peak −21.3 dBFS, no sample at full scale.
- **The notes.** The spectrum's strongest lines are 131.4, 261.7, 329.6, 391.9, 523.2, 659.3, 784.1 and 1,046.5 Hz: the eight panel defaults C3 … C6.
- **The bursts.** Each block is heard as one burst, its Dirichlet kernel's main lobe in time (about 180 ms at −6 dB, for N = 48 at 1/16 Hz).
  - Every burst comes back after **16.00 s** = 1 / (1/16 Hz): C5 at 2.68 → 18.68 s, E5 at 5.90 → 21.90 s, G5 at 9.22 → 25.24 s.
  - This is the architect's "Dirichlet kernels like a scale", measured.
- **The noise the architect hears.** Between the bursts (85 % of the time below −50 dBFS) there is a comb of lines at multiples of 250 Hz: 500, 750, 1,000, … 7,000 Hz. 750 Hz is the strongest, at **−57 dBFS**; the others lie at −72 … −100 dBFS.
  - The comb is identical in L and R (correlation 0.995 in the 750 Hz band).
  - Its level does not change with the music: 750 Hz stays at −57 … −58 dBFS inside the bursts and between them.
  - Its fundamental reads 750.015 Hz on the recorder's clock (+20 ppm), so it is not made by the recorder's own clock.
  - Apart from these lines the floor is very low: −148 dBFS per bin.
- **Where it comes from — the recording chain's HDMI audio splitter (settled 2026-10-18, §4.6 Q4).** The reasoning before the test:
  - The digital output of this design equals the models sample for sample: RTL-SIM, the 77,387 samples of R1 and R2, and the Phase 6 SignalTap captures C1–C5, which agreed with RTL-SIM.
  - The models put energy only on the blocks' bins. The sine core's error budget is ≈ 1.3 × 10⁻⁷ (Ch.2 §2.8.2; SD-16), and rounding to 24 bits adds nothing near −57 dBFS.
  - A 250 Hz comb, the same in both channels and indifferent to the music, therefore enters after the samples: in the ADV7513 / HDMI link, the monitor's DAC, or the recording path. A 1 kHz line is also present; for 720p60 the HDMI audio clock regeneration runs at 74.25 MHz / 74,250 = 1 kHz, which would fit a sink-side origin. **This is an inference, not yet a measurement.**
- **The test that settles it** (question Q4): record the same chain once with **SW[3] = 1**. Soft mute drives MG to the floor, and a sweep played there while muted outputs exact zeros (Ch.4 §4.4, C4-D6; `l1_model.py`). If the comb is still there, it is outside WPMS. A second short recording with HDMI audio unplugged gives the recorder's own floor.
- **The test, made by the architect (2026-10-18).** The recording chain is HDMI → an inexpensive HDMI audio splitter → Zoom H4n Pro analog input → USB → Cubase.
  - The noise stays at the same level and with the same waveform with soft mute (SW[3] = 1), through a reset, and with HDMI unplugged. It is therefore not in WPMS's output, nor in the HDMI link.
  - On an oscilloscope the splitter's output carries the noise in a band far above the sampling rate, around 1 MHz.
  - Its level halves when the splitter's USB-C power comes from a separate AC adapter instead of the PC's USB.
  - Conclusion: the analog limits of the splitter, fed by noisy USB power. The comb in the recording is that interference after the H4n's sampling.
  - **Outside WPMS; nothing in the design or the tools changes.** For future recordings a cleaner analog path is needed (a better splitter or DAC, a clean supply); the measurements of §3–§4.1 do not depend on it.

### 4.6 Questions for the architect / 質問

Q1–Q3 are answered (2026-10-18):

- **Q1 (PANIC):** the slider was not moved back after PANIC.
- **Q2 (SignalTap):** it was closed throughout.
- **Q3 (screenshot and recording):** both received; filed in `media/`.

- **Q4 (the noise in the recording, §4.5) — answered the same day:** it comes from the HDMI audio splitter of the recording chain, not from WPMS. With soft mute, after a reset and with HDMI unplugged the noise is unchanged; it lies around 1 MHz on the oscilloscope and halves on a separate AC adapter. Nothing to change in the design or the tools.

No question is open.

---

**和文要約。** 2026-10-15 に実機で測定した。

- **1 トランザクション：** 平均 0.41 ms、中央値 0.37 ms、最大 4.2 ms。見積もり 5〜30 ms の十数分の一で、92.8 % が 0.5 ms 未満だった。
- **更新速度：** マスター利得は 1,826 回/秒。4 ブロックのレベル GO は 374 回/秒で、APPLIED_SEQ 読出しは GO 1 回あたり 0.992 回。
- **REJECT[0]：** 70 秒間、全期間 0。拒否・ISSP 誤り・CLIP もすべて 0。
- **耳での確認：** クリックもジッパーもなかった。PANIC は −72 dB に 1.22 秒、床（−192.7 dB）に 3.28 秒で到達し、60 dB/s の理論どおり。

期待値の数字が外れたのは、指示書の見積もり *t* が大きすぎたためで、式は実測の *t* でそのまま成り立つ（D1）。`board_measure.txt` は空で届いたが、数値はすべて JSON から再計算した（D2）。GUI のセッションは、Test origin を最初に押したので原点から始まった扱いになる。再生ツールをそのように直した（D3）。GUI のセッション記録は RTL 再生で PASS（GO 2,808 回、拒否 0、全サンプル一致）。measure の記録も PASS（GO 22,450 回、拒否 0、67,816 サンプル全一致）。 食い違いの登録はない。2026-10-18：SignalTap は閉じていた。PANIC 後のスライダーは戻していない。スクリーンショットと録音を受け取った。録音では各ブロックのメインローブが 16.00 秒（= 1/(1/16 Hz)）ごとに巡ることを確認した。気になるノイズは 250 Hz 間隔の線スペクトル（750 Hz が −57 dBFS）で、左右同一・音楽と無関係。WPMS のデジタル出力はモデルとサンプル単位で一致しているので、HDMI 以降または録音経路で入ったと推定している（未測定）。アーキテクトの切り分け（Q4）で原因が判明した。録音経路の安価な HDMI 音声分離器のアナログ性能の限界である。ソフトミュートでも、リセット中でも、HDMI を外しても、ノイズは同じレベル・同じ波形で残る。オシロでは 1 MHz 付近にあり、分離器の USB-C 電源を独立 AC アダプタにすると約半分になる。WPMS の外であり、設計にもツールにも変更はない。未解決の質問はない。
