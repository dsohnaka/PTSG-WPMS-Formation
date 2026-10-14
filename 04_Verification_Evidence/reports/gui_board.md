# WPMS host control GUI — on the board / ホスト制御 GUI——実機

*CC0 · prepared 2026-10-14 by Claude Code for the architect, per `GUI_BRIEF_WPMS_Host_Control_2026-10-14` §7. **OUTSIDE WPMS** (Layer 3 tooling, a stand-in for the Layer 4 controller). Before the board: `gui_v1_v3.md`.*

*State: **prepared — the expected values are written; the measured column waits for the board run.** Every expected value below was written before any board number exists (Silicon Brief §5: expected before observed). Evidence class of the measured column: **SILICON**.*

*状態：**準備完了。期待値は記入済みで、実測欄は実機の実行を待つ。** 下の期待値は、実機の数値が一つもない時点で書いた。実測欄の証拠区分は SILICON。*

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
| M0 | `wpms_ctl.py` first line | `ID 57504D53, CONFIG 0003F081 (NMAX 1008); sweep [0], N [1008]` | Phase 6 image, the ROM's test origin | — |
| M1 | One ISSP transaction (`<us>` of the bridge), mean and max over 1,000 reads | mean 5 … 30 ms; max < 100 ms | brief §7 (ESTIMATE) | — |
| M1h | Its histogram (`board_times.csv`; table in the output) | most reads within one 5 ms bin; few above 2 × median | — | — |
| M2 | Master-gain update rate | 19 … 179 /s, i.e. (1 / *t*) × 250 / (250 + 6 *t* [ms]) for *t* = 30 … 5 ms; the brief's 33 … 200 /s leaves out the status poll | this controller | — |
| M3 | Block-level GO rate, four blocks | 4 … 36 /s: one GO = 5 *t*, plus one status poll per 250 ms; the brief's ≈ 6 … 100 /s | this controller | — |
| M3p | APPLIED_SEQ polls per GO | **1.00**: the apply (≤ 42 µs) lands before the first poll | Ch.5 §5.4.3; V3 | — |
| M3l | GO sent → apply seen | ≈ 2 *t*: 10 … 60 ms median | the above | — |
| M4 | REJECT[0] before → after M3 | **unchanged**; refused 0, errors 0 | brief §4 | — |
| R1 | `cosim_gui_replay.py board_measure.json` | **PASS**: host writes refused by the RTL 0; APPLY with APPLIED_SEQ = GO_SEQ: all; samples equal the models; started at the test origin: True | V3 | — |

### By hand and by ear (P3) / 手と耳

| # | Action | Expected | Measured |
|---|---|---|---|
| S1 | **Test origin** | Its GO is applied; the panel follows the switch: play [0], Σ N = 1,008 / 1,008, MG_TARGET 0 dB. The tone (≈ 996 Hz) sounds as at power-on | — |
| S2 | Block 0: **N** 1,008 → 240; tick **Play** on blocks 1, 2, 3 (ticking before shrinking N is refused, with the reason in red) | block 0 re-seeded with the panel's note (C4); then C4, E4, G4, C5; Σ N = 960 / 1,008; REJECT[0] +0. Quieter than the origin: about −26 dBFS peak for the four at −6 dB (ESTIMATE: 4 × 0.5 × √(π / γ) ≈ 205 bin amplitudes, × 2⁻¹² at G = 12), against the origin's −12.4 dBFS | — |
| S3 | **Level** of one block swept fast, end to end, many times | the level follows with the glide (60 dB/s); **no clicks** | — |
| S4 | **Centre** and **Spacing** of one block swept | the pitch moves without zipper noise (PITCH: phase-continuous) | — |
| S5 | **Width γ** swept | the timbre and loudness change smoothly (phases continue) | — |
| S6 | **PANIC**, then MG_TARGET slider back to 0 dB | silence within MG_RATE's slew: −72 dB after 1.2 s, the floor after 3.2 s at 60 dB/s; then back up at 60 dB/s | — |
| S7 | SignalTap open or closed during P2 / P3 | no expectation; recorded. If open: M1 with it, and once with it closed, if possible | — |
| S8 | Status panel after S1–S6 | REJECT[0] "+0 since connect"; errors 0; pending "no GO" at rest | — |
| R2 | `cosim_gui_replay.py board_gui.json` | **PASS**, as R1 | — |

## 4. To be filled after the run / 実行後に記入

- **Transaction-time histogram:** from `board_times.csv`, as a table.
- **Deviations from §3, if any:** each with its cause, or with "unexplained".
- **Discrepancies filed:** none expected. Anything that needs the switch to change goes to `discrepancies.md`, not into the tools.
- **Layer 4 README row:** the measured transaction time and update rates, with the class SILICON.

---

**和文要約。** 実機の前に期待値を書いた。

手順：
1. ISSP エディタを閉じる。
2. `quartus_stp -t wpms_bridge.tcl` で橋を起動する。
3. `python wpms_ctl.py measure --n 1000 --seconds 60 --csv board_times.csv --log board_measure.json` で数値を測る（約 1.5 分）。
4. `python wpms_gui.py --connect` で、Test origin を押してから S1〜S6 を手と耳で確かめ、ログと時間を保存する。

期待値：
- 1 トランザクション：平均 5〜30 ms。
- マスター利得の更新：19〜179 回/秒。指示書の 33〜200 回/秒には、250 ms ごとの状態読出し 6 回が含まれていない。
- 4 ブロックのレベル GO：4〜36 回/秒。
- GO 1 回あたりの APPLIED_SEQ 読出し：1.00 回。
- REJECT[0] は不変。
- 二つのセッション記録は RTL 再生で PASS する。

ボードを使った記録の再生は、テスト原点から始めたものに限る（2026-10-14 裁定）。
