# observation — Phase 3: sequencer and integration (Core + Formation + sequencer, running the score)
# 観測判決 — Phase 3: シーケンサと統合（Core・Formation・シーケンサが楽譜を奏でる）

**Verdict / 判決: PASS.** Core RH031p + Formation + sequencer, running the R1 score, reproduce the sweep oracle exactly: every bundle L1 latches, every packet length, every K sequence and the `stay_value` pin at every Stay — 36,000 sweeps per clock budget with the dispatch form (128,321 packets at 100 MHz, 126,763 at 50 MHz), 12,000 with the branch form. The dispatch form plays packets with **g = 0** and starts the first **1 clock** after the strobe; its worst full-load sweep is **2,062 of 2,083** clocks (100 MHz) and **1,038 of 1,041** (50 MHz, NMAX 1024). Injected EW2–EW6 silence L1 in the clock the flag rises; the Core halts at the trap word. The first error run failed and exposed SD-15 (the insertion handshake), fixed on the Formation side before the recorded runs.

**合格。** Core RH031p・Formation・シーケンサが R1 楽譜でスイープ・オラクルを正確に再現した（ラッチされる全バンドル・全パケット長・全 K 列・各 Stay の `stay_value`）。ディスパッチ形はクロック予算ごとに 36,000 スイープ（100 MHz で 128,321 パケット、50 MHz で 126,763）、分岐形は 12,000 スイープ。ディスパッチ形は **g = 0**、ストローブ後 **1 クロック**で最初のパケット。全負荷スイープの最悪は **2,083 中 2,062**（100 MHz）、**1,041 中 1,038**（50 MHz、NMAX 1024）。注入した EW2〜EW6 はフラグの立つクロックで L1 を無音にし、Core はトラップ語で停止する。最初のエラー実行は失敗して SD-15（挿入ハンドシェイク）を露呈し、記録実行の前に Formation 側で修正した。

**Evidence class / 証拠クラス:** RTL-SIM (Icarus Verilog 12.0, `-g2012`). Nothing here is SILICON. **License:** CC0 1.0 Universal.

---

## 1. Setup / 環境

| Item | Value |
|---|---|
| RTL under test | `03_Sample_Implementations/hw/l2/wpms_l2_top.v` = `hw/core/ptsg_core_rh031p.v` (IMEM_DEPTH 1024, PRESCALE 1) + `hw/l2/wpms_formation.v` (RH002) + `hw/l2/wpms_sequencer.v`, with the Core's `ptsg_imem` wrapper (SIM branch) |
| Scores | `hw/l2/scores/wpms_r1d.score` (R1, dispatch form) and `wpms_r1b.score` (R1, branch form), assembled by `score_as.py`; the dispatch form's housekeeping window is `hw/l2/programs/wpms_housekeeping_dispatch.pfasm` |
| Golden model | `03_Sample_Implementations/tools/sweep_sim.py` with the customer's `wpms_layer1_oracle.py` for the glide law — **run unchanged** through `hw/tools/sweep_dump.py`, which only records (the brief's "`--dump` mode", done without editing the file). For the 50 MHz budget the profile constant NMAX is overridden to 1024 for the run (the files are not touched) |
| Testbench | `hw/l2/wpms_l2_tb.v`: stands where the input switch (Phase 5) and L1 (Phase 4) will stand. Before each sample's strobe it writes, through the Formation's switch port, whatever the oracle's writer changed; it latches what L1 would latch and checks the bins |
| Recipe | `03_Sample_Implementations/hw/l2/run_phase3.sh <this directory>` — about 40 min; exits non-zero on any failed expectation; `logs/run_phase3.txt` is its output |
| Strobe | given when the previous sweep is over (plus 0–3 clocks), not on a 48 kHz grid: the Core only waits in its Branch-0 SLEEP meanwhile. Whether each sweep fits the sample period is answered by its measured length against T_min (2,083 clocks at 100 MHz, 1,041 at 50 MHz) |

## 2. Expected — written before the runs / 期待値（実行前に記述）

| Item | Expected | Basis |
|---|---|---|
| Every packet | the block, the eight-word bundle, N (bins with `bin_valid`), K = 0 … N−1 without a hole — equal to the oracle's | brief Phase 3; D2 §2-§3; the oracle's stale-bundle check |
| `stay_value` | N of the packet's block at every packet Stay's execute clock; 0 at the housekeeping Stay | W-F22, D3 §5, C4-F16; brief rule "never non-zero during the housekeeping Stay" |
| L1 face | one clock after the Core's timeline (SD-11 resolved that way): `packet_start` the clock after the Stay Set, `bin_valid` = TS_PKT on the bus, K delayed one clock | `wpms_sequencer.v` header |
| Dispatch form | T_wake (strobe clock → first packet Stay Set) **1**; g **0**; housekeeping Stay Set → first SLEEP clock **13** (T_HK); no holding-register use (no stack request) | the score's design: SLEEP_P falls through into its position; queued Jumps (Phase 1 SV-5b: g = 0); a background computed dispatch |
| Branch form | T_wake **3** (SD-14 ruled: the lane word); g **1**; housekeeping **14** (13 + the Reset) | the score's design |
| Packet floor | dispatch form: **30** (as SD-12); branch form: 29 + 1 | Phase 1 SV-5b; reading |
| Full-load sweep, 100 MHz | dispatch form: 1 + 2,048 + 13 = **2,062** ≤ 2,083; branch form ≤ 3 + 2,048 + 8 + 14 = 2,073 | the above |
| Full-load sweep, 50 MHz (NMAX 1024) | dispatch form: 1 + 1,024 + 13 = **1,038** ≤ 1,041; branch form ≈ 3 + 1,024 + up to 8 + 14 > 1,041 — **does not fit** | the above; ruling 2026-09-28 |
| Injected EW2, EW3, EW4, EW5, EW6 | `error_flag` with that code; no `packet_start` and no `bin_valid` from the clock the flag rises; the Core halts at the trap word 0x3FF through the insertion, within the Stay in progress (C3-F20) | ruling 2026-09-28 (SD-06); Core Ch.5 §5.9 |
| R2 probe | queued Base Set + queued Loop 3: three passes, gap-free; Loop 0: one pass, no indirect read | SD-04 by reading (Phase 0) |
| Sweep-level mutants | each of the 11 defects makes the cosimulation fail | — |

## 3. Observed / 観測

### 3.1 Sweep-level cosimulation (`logs/cs_*.txt`)

| Score · budget | Seeds × samples | Sweeps | Packets | Bins | Full-load | Stays, pin checked | Longer than T_min | vs oracle |
|---|---|---|---|---|---|---|---|---|
| dispatch · 100 MHz | 3 × 12,000 | 36,000 | 128,321 | 54,205,714 | 16,740 | 164,321 | 0 | **identical** |
| dispatch · 50 MHz | 3 × 12,000 | 36,000 | 126,763 | 27,954,068 | 17,730 | 162,763 | 0 | **identical** |
| branch · 100 MHz | 1 × 12,000 | 12,000 | 42,056 | 17,732,862 | 5,595 | 54,056 | 0 | **identical** |
| branch · 50 MHz (informative) | 1 × 3,000 | 3,000 | 9,798 | 2,178,264 | 1,362 | 12,798 | **1,362** | identical |

The oracle, in every run: "L1 bundle mismatches vs reference: 0 — machine/sequencer errors: none" (it checks itself against the customer's semantics). No simulator warning (stale bundle, prefetch during a copy, inbox write to a pending block), no stack request, no timeout.

### 3.2 Measured / 実測 (RTL-SIM, clocks)

| Term | Expected | Dispatch form | Branch form |
|---|---|---|---|
| T_wake: strobe → first packet Stay Set | 1 / 3 | **1** (every sweep) | **3** |
| g | 0 / 1 | **0** (every packet) | **1** |
| Packet floor, N = 28 29 30 31 32 33 (N_MIN lowered to 16 for this case) | 30 / 29 + 1 | **30 30 30 31 32 33** | **30 30 31 32 33 34** |
| HK Stay Set → first SLEEP clock | 13 / 14 | **13** | **14** |
| BCP commit → copy landed | ≤ 9 | 2 … 9 | 2 … 9 |
| Worst full-load sweep, 100 MHz (of 2,083) | 2,062 / ≤ 2,073 | **2,062** | **2,073** |
| Worst full-load sweep, 50 MHz (of 1,041) | 1,038 / does not fit | **1,038** | **1,049** (−8) |

All as expected. / すべて期待どおり。

### 3.3 Errors (`cs_r1d_100.txt`, directed part) / エラー

| Injected | `error_flag` | Latches / bins after the flag | Core |
|---|---|---|---|
| EW6 (LE0 < 0 landed; the next STP) | EW6, clock 650 | 0 / 0 | HALT at 0x3FF, 56 clocks later |
| EW5 (repeated block in the sweep item; BCP) | EW5, clock 564 | 0 / 0 | HALT at 0x3FF, 11 clocks later |
| EW2 (N = 16 landed; the post-HK prefetch) | EW2, clock 569 | 0 / 0 | HALT at 0x3FF, 8 clocks later |
| EW4 (negative_tests N1 as the packet window) | EW4, clock 168 | 0 / 0 | HALT at 0x3FF, 57 clocks later |
| EW3 (negative_tests N4 as the packet window) | EW3, clock 164 | 0 / 0 | HALT at 0x3FF, 61 clocks later |

In the branch form EW6, EW4, EW3 halt the same way; EW5 and EW2 (raised in housekeeping, after the sweep's one taken Branch) leave the Core waiting in S_PUSH at 0x0EE — L1 silent all the same (`cs_r1b_100.txt`). **Not as first expected:** the first run of these cases (before `wpms_formation.v` RH002) ended every case in S_PUSH at the trap word 0x3FF — the Core took the insertion twice (SD-15). The recorded runs are after the fix.

### 3.4 R2 probe (`logs/r2_probe.log`)

Queued Base Set + queued Loop 3: body Stay Sets at clocks 151, 183, 215 — periods 32, 32, 32 — then housekeeping; queued Loop 0: one pass; indirect reads requested: 0 in both. As read (SD-04).

### 3.5 Mutants (`logs/cosim_sweep_mutants.log`)

11 of 11 killed: S1 bundle of the wrong block · S2 bins (the pin followed StayVal.s) · S3 K sequence · S4 an extra packet (MORE) · S5 timeout (wrong dispatch) · S6 empty first bundle (prefetch before the copy) · S7 32,220 bins while muted · S8 a sweep longer than T_min (HK Stay not literal) · S9 a packet in an empty sweep · S10 the Core spilled at the trap · S11 a packet latched in housekeeping.

### 3.6 Regression and generators

Phase 2 recipe on the current RTL: ALL PHASE 2 CHECKS PASSED (`logs/phase2_regression.txt`). Scores assemble to the committed images; the dispatch program is CLEAN and the model computes JumpVal 0x300 … 0x380 for P = 0 … 8. Compile: 11 "@* sensitive to all words" notes and 1 note on the Core's `tri0` port, nothing else.

---

## 4. Verdict / 判決

**PASS.** Every expectation of §2 met by the recorded runs; one thing not expected beforehand (SD-15) was found by the first run, fixed in the Formation, filed, and is now guarded by mutant S10. No golden model, Layer 1 document or frozen Core source was edited.

**合格。** §2 の期待はすべて記録実行で満たした。事前に予期しなかった一件（SD-15）は最初の実行で見つかり、Formation で修正・記録し、変異体 S10 で守っている。黄金モデル・第1層文書・凍結 Core は一切編集していない。

