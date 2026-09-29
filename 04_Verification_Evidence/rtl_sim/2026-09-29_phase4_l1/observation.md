# observation — Phase 4: the L1 pipeline and the output path
# 観測判決 — Phase 4: L1 パイプラインと出力路

**Verdict / 判決: PASS.** The L1 pipeline and the output path are bit-exact at every level tested:

- with the customer's oracle (imported unchanged) — phase, exp2, amplitude with the master gain, the MG slew;
- with the published model of what the oracle does not model — the sin core, the product, the accumulators and the output stage.

The levels tested:

- 1,000,000 unit inputs each;
- 651,424 module bins and 1,203 samples;
- 154,135 samples of MG fade and soft mute;
- the whole synthesizer — under the sweep oracle's GO traffic (18,000 sweeps, 20.3 million bins, both clock budgets), and on the real 48 kHz I2S grid with a receiver on the wire.

The customer's numbers reproduce:

- 927 audible bins for σ = 71;
- a test-origin peak of −6.29 dBFS;
- MG −60 dB in 1.0000 s;
- 21.484 µs to the wire.

D_L1 = 19. One finding was fixed before the record (the JumpVal power-up, §3.9). The 50 MHz test origin needs a ruling (SD-17).

**合格。** 各段でビット一致した:

- 顧客オラクル（無改変）と——位相・exp2・マスターゲイン込みの振幅・MG スルー;
- オラクルがモデル化しない部分の公開モデルと——sin・積・累算器・出力段。

試験の範囲:

- ユニット各 100 万入力;
- モジュール 651,424 ビン・1,203 サンプル;
- MG フェードとソフトミュート 154,135 サンプル;
- 合成器全体——スイープ・オラクルの GO 通信下（両予算で 18,000 スイープ・2,030 万ビン）と、実際の 48 kHz I2S グリッド上（受信器で線上を復号）。

顧客の数値は再現した: σ = 71 で可聴 927 ビン、テスト原点のピーク −6.29 dBFS、MG −60 dB まで 1.0000 秒、線上まで 21.484 µs。D_L1 = 19。記録前に一件を発見・修正した（JumpVal の電源投入値、§3.9）。50 MHz のテスト原点は裁定待ち（SD-17）。

**Evidence class / 証拠クラス:** RTL-SIM (Icarus Verilog 12.0, `-g2012`); ORACLE for the model self-tests; ESTIMATE (Yosys 0.69) for resources. Nothing here is SILICON. **License:** CC0 1.0 Universal.

---

## 1. Setup / 環境

| Item | Value |
|---|---|
| RTL under test | `03_Sample_Implementations/hw/l1/`: `wpms_l1_module.v` (+ `wpms_l1_sin.v`, `wpms_l1_exp2.v`), `wpms_output_stage.v`, `wpms_strobe_sync.v`, `wpms_i2s_master.v`, `wpms_synth_top.v` (+ `hw/l2/wpms_l2_top.v` RH002, `wpms_formation.v` RH003, `wpms_sequencer.v`, `hw/core/ptsg_core_rh031p.v`); `wpms_video_720p.v`, `wpms_adv7513_cfg.v` |
| Golden model | The customer's `wpms_layer1_oracle.py`, **imported unchanged**: `exp2_q131`, `l1_amplitude` (with MG), `l1_phase`, `step_toward`, `gaussian_slots`; the profile's `sweep_sim.py` (bundles, `Reference` pages), unchanged |
| Published model (not golden) | `hw/tools/l1_model.py` — the parts the oracle does not model: the Maclaurin sin core (SD-16), the product (Q1.63, toward zero), the accumulators (Q12.63, closed on the strobe), the output stage (MG step, G, round, saturate, clip, soft mute, error silence) |
| Clocks in the system benches | clk_sys 20 ns (50 MHz budget: NMAX 1,008, T_min 1,041) or 10 ns (100 MHz budget: NMAX 2,048, T_min 2,083); clk_aud = MCLK 81.380 ns (12.288 MHz) |
| Recipe | `03_Sample_Implementations/hw/l1/run_phase4.sh <this directory>`; `logs/run_phase4.txt` is its output. The Phase 3 regression (step 1) was run once by `hw/l2/run_phase3.sh` on the identical L2 RTL; its log is `logs/phase3_regression.txt`. `logs/cosim_synth_grid.txt` was regenerated after the recorded run by the same eight grid cases, once `cosim_synth.py` also printed the Core's sweep length (same RTL, same results, one line more per case) |

## 2. Expected — written before the recorded run / 期待値（記録実行の前に記述）

| Item | Expected | Basis |
|---|---|---|
| exp2 unit | = the oracle's `exp2_q131` for every L, clamps included | Ch.3 §3.5.4; brief Phase 4 ("bit-exact") |
| Phase path | = `l1_phase` (mod 2³²) for every bin | Ch.3 §3.4.2, C3-D3 |
| Amplitude path | = `l1_amplitude(LS0, LAD1, LAD2, LP, N, MG)` for every bin | Ch.3 §3.5.4, Ch.4 §4.4.1 |
| sin core | = `l1_model.sin_q040`; max \|error\| vs sin(2πφ) ≈ 2⁻²⁴ (the 11th-order truncation, 5.7×10⁻⁸), within Ch.2 §2.8's ≈ 1.3×10⁻⁷ | Ch.2 v1.1; SD-16 |
| Product, accumulators, output stage | = the model, every bin and every sample (bank, clip, MG, SWEEP_CLOCKS, inspector) | Ch.3 §3.6, Ch.4 §4.4 |
| D_L1 (bin on the L1 face → its product in the accumulator) | **19** clocks (1 + 16 + 2), ≤ 24 | Ch.3 §3.6.5 (target ≤ 24); the design |
| Worst SWEEP_CLOCKS at full load | NMAX + 20: **1,028** of 1,041 (50 MHz), **2,068** of 2,083 (100 MHz) — T_wake 1 + the L1 face 1 + (NMAX − 1) + 19 | Ch.3 §3.7; Phase 3 (T_wake 1, SD-11) |
| MG slew | 0 → −60 dB at 13,933 per sample in **1.0 s** | Ch.4 §4.4.1, CH4-MG |
| Soft mute | the output is exact zero once MG sits at the floor (−32) | Ch.4 §4.4.5, C4-D6 |
| Strobe interval (clk_sys clocks) | 1,041 / 1,042 (50 MHz); 2,083 / 2,084 (100 MHz) | Ch.4 §4.3.2 |
| Latency S_m → left MSB on the wire | T + Δ_pre + 1 SCLK = 264 MCLK = **21.48 µs = 1.031 periods** | Ch.4 §4.8, C4-D10 |
| I2S wire | words a Philips receiver decodes = the words the master captured at F = the bank written before F | C4-D7, C4-D8 |
| Test origin (N = 2,048, G = 12, 100 MHz budget) | PCM peak **−6.3 dBFS** | Ch.3 §3.6.4, CH3-ORIGIN |
| σ = 71 Gaussian, N = 2,048 (naive and consistent slots) | **927** bins with a ≠ 0 per packet | Ch.3 §3.5.1, CH3-E2E |
| The literal test origin at NMAX 1,008 | refused with **EW5** at BCP (the new sweep word's Σ N > NMAX), L1 silent, the Core halts at the trap. *First read as EW2 at the prefetch; a development run corrected the reading before this record (§3.9)* | Map v0.3 EW5/EW2; ruling 2026-09-29 |
| The sweep oracle's GO traffic through the whole synthesizer | every bundle as the oracle (the Phase 3 checks); every output sample as the model; no sweep ≥ T_min | brief Phase 4 ("a full sweep against sweep_sim bundles + oracle L1") |
| Video carrier | 1,650 × 750 clocks, 1,280 × 720 active, HSYNC 40 at 1,390, VSYNC 5 lines at 725, 60 Hz | Ch.4 §4.7, C4-D9 |
| ADV7513 configurator | HPD read, 29 writes acknowledged in order; nothing while HPD is low; the table again after a hot-plug | Ch.4 §4.6.2 |
| Mutants | every deliberate L1 defect caught | — |
| Resources per module (ESTIMATE) | sin 7 multipliers (C2-D10); exp2 3–5 DSP + 1 M10K (§3.5.4); product 2–4 DSP; total 12–16 DSP, 1 M10K (§3.6.6); output path 0 DSP (Ch.4 §4.10) | the chapters |

## 3. Observed / 観測

From `logs/` (`run_phase4.txt` is the recipe's own output; `phase3_regression.txt` / `phase2_regression.txt` from `hw/l2/run_phase3.sh` on the identical L2 RTL).

### 3.1 The model and the oracle (ORACLE)

| Check | Observed |
|---|---|
| Customer oracle, unchanged, numpy 2.4.6 | ALL PASS; CH4-CREST ran its 7 sub-checks (crest 36.12 / 5.60 / 12.17 dB) — in Phase 0 it had skipped itself (numpy absent) and printed PASS |
| sin core (`l1_model.sin_q040`) vs sin(2πφ), exhaustive over u (2²⁶ values, both ends of each u's 16 phases) | max \|error\| **5.960×10⁻⁸ = 2⁻²⁴·⁰⁰** (at φ = 0x3FFFF88F); max output 1,099,511,611,388 ≤ 2⁴⁰ − 1 |
| The same core with Ch.2 v1.1's table read literally (for SD-16) | 3.97×10⁻⁷ = 2⁻²¹·²⁶ (200,000 phases) |
| Model phases vs the oracle's `l1_phase` | 0 mismatches (5 bins × 300 packets) |
| Generated table and constants | equal a fresh generation from the oracle (`_T`, `_C1`, `_C2`) and the model |

### 3.2 Units (RTL-SIM)

| Unit | Inputs | Mismatches |
|---|---|---|
| `wpms_l1_sin.v` vs `l1_model.sin_q040` | 1,000,000 phases (44 directed: quadrant and truncation edges) | **0** |
| `wpms_l1_exp2.v` vs the oracle's `exp2_q131` | 1,000,000 L (31,758 directed: every integer part × every table entry × 4 lo edges; the clamps at 0, −1, −31·2³⁰, −31·2³⁰ − 1, ±2⁵³) | **0** |

### 3.3 Module: `wpms_l1_module` + `wpms_output_stage`, bin by bin (RTL-SIM)

Per bin, four values are compared: the phase against `l1_phase`, a against `l1_amplitude` with MG, sin, and the Q1.63 product. Per sample: the bank L and R, the clip flags, MG, SWEEP_CLOCKS, and the inspector's capture of bin 7.

| Seed | Sweeps | Packets | Bins | a = 0 / clamped at 1 / between | Samples | Mismatches | Inspector captures | Overrun |
|---|---|---|---|---|---|---|---|---|
| 1 | 400 | 1,115 | 224,529 | 106,204 / 56,361 / 61,964 | 401 | **0** | 270 | 1 (the deliberate case) |
| 2 | 400 | 1,065 | 216,865 | 115,040 / 55,569 / 46,256 | 401 | **0** | 268 | 1 |
| 3 | 400 | 1,105 | 210,030 | 109,207 / 61,809 / 39,014 | 401 | **0** | 258 | 1 |

Controls exercised: G, the G override, the MG target and rate (including a negative rate and a positive target, both treated as 0), soft mute and the error silence. Timing cases exercised: packets back to back and with gaps of 1–2 clocks, a product landing in the strobe clock itself (included in the closing sample), and one late product (the overrun flag).

### 3.4 MG and soft mute (`cosim_l1_mgfade.txt`)

- **Fade.** MG goes from 0 to −60 dB (target −668,792,462) at 13,933 per sample and reaches it at strobe **48,001 = 1.0000 s** (CH4-MG: 1.0 s). The RTL's MG equals the model's at every one of the 154,135 strobes.
- **Soft mute.** MG then slides to the floor, reached at strobe 154,130. The last sweep played above the floor gave **128 LSB** (at G = 0, the level 2⁻¹⁶). From the first sweep played at the floor the output is **exactly zero** (C4-D6).

### 3.5 The whole synthesizer on the 48 kHz grid (`cosim_synth_grid.txt`)

| Budget · case | Samples = model | Bundles = Reference | I2S frames: decoded = captured = bank | Strobe interval | SWEEP_CLOCKS max | Other |
|---|---|---|---|---|---|---|
| 50 · test origin, N = 1,008 | 120 / 120 | 118 / 118 | 120 / 120 | 1,041 / 1,042 | 1,028 | peak 2,002,439 = **−12.44 dBFS** (G = 12) |
| 50 · test origin as written (N = 2,048) | — | — | 129 / 129 | 1,041 / 1,042 | 0 | **EW5** at clock 1,042; 0 non-zero samples after it; **HALT at 0x3FF 11 clocks later** |
| 50 · level glide + pitch retune in flight | 40 / 40 | 38 / 38 | 40 / 40 | 1,041 / 1,042 | 720 | — |
| 50 · full load, 8 × 126 bins | 40 / 40 | 304 / 304 | 40 / 40 | 1,041 / 1,042 | **1,028** | — |
| 100 · test origin, N = 2,048 | 120 / 120 | 118 / 118 | 120 / 120 | 2,083 / 2,084 | 2,068 | peak 4,068,448 = **−6.29 dBFS** (G = 12; customer −6.3) |
| 100 · σ = 71 Gaussian, naive then consistent | 8 / 8 | 6 / 6 | 8 / 8 | 2,083 / 2,084 | 2,068 | **927** bins with a ≠ 0 in each of 6 packets (customer 927) |
| 100 · level glide + pitch retune | 40 / 40 | 38 / 38 | 40 / 40 | 2,083 / 2,084 | 720 | — |
| 100 · full load, 8 × 256 bins | 40 / 40 | 304 / 304 | 40 / 40 | 2,083 / 2,084 | **2,068** | — |

Latency from S_m to the left MSB of that sweep's sample on the wire: **21.484 µs = 1.0312 periods** in every case (264 MCLK; Ch.4 §4.8: 21.48 µs = 1.031). The Core's side of the budget (strobe → first SLEEP clock) at full load: **1,022** of 1,041 and **2,062** of 2,083.

### 3.6 The whole synthesizer under the sweep oracle's GO traffic (`cosim_synth_oracle.txt`)

In each budget, three seeds (2026, 7, 42) × 3,000 samples, run with three control settings:

- G 12;
- a G override to 10;
- G 8 with MG gliding toward −1 log₂.

| Budget | Sweeps | Packets | Bins | Full-load | Output samples = model | T_wake / g | Sweep length | SWEEP_CLOCKS worst |
|---|---|---|---|---|---|---|---|---|
| 50 MHz (NMAX 1,008) | 9,000 | 32,473 | 6,867,874 | 0 (SD-18) | **9,003 / 9,003** | 1 / 0 | 14 … 1,019 | **1,025** of 1,041 |
| 100 MHz (NMAX 2,048) | 9,000 | 32,839 | 13,448,806 | 4,178 | **9,003 / 9,003** | 1 / 0 | 14 … 2,062 (full load 2,062) | **2,068** of 2,083 |

The Phase 3 checks all hold: every latched bundle and N as the oracle, K 0 … N−1, and `stay_value` at every Stay. The oracle's own verdict in every seed: "L1 bundle mismatches vs reference: 0 — machine/sequencer errors: none".

### 3.7 Timing summary (RTL-SIM, clocks)

| Quantity | 50 MHz budget | 100 MHz budget | Target |
|---|---|---|---|
| D_L1 (bin on the L1 face → product in the accumulator) | 19 | 19 | ≤ 24 (Ch.3 §3.6.5) |
| Worst SWEEP_CLOCKS at full load (1 + 1 + NMAX − 1 + 19) | 1,028 (12 before the strobe) | 2,068 (14 before) | < T_min (Ch.3 §3.7) |
| Worst Core sweep (strobe → first SLEEP clock), full load | 1,022 | 2,062 | ≤ T_min |
| Strobe interval | 1,041 / 1,042 | 2,083 / 2,084 | Ch.4 §4.3.2 |
| Bank written after the audio-side toggle S_m | 6–7 clk_sys clocks (synchronizer 2–3, output stage 4): 120–140 ns | 60–70 ns | < Δ_pre = 325.5 ns before the capture at F (C4-D7); every capture equal to the bank (§3.5) |

### 3.8 Output-path blocks

- **Video carrier** (`video_tb.log`):
  - 1,237,500 clocks per frame (1,650 × 750);
  - 720 active lines of 1,280 pixels;
  - VSYNC 5 lines from line 725, HSYNC 40 clocks;
  - 60.0001 Hz;
  - the bars as designed.
- **ADV7513 configurator** (`adv7513_tb.log`):
  - HPD read at 0x42, then 29 writes acknowledged in order, one of them clock-stretched;
  - nothing written while HPD was low; after the hot-plug, the table again (58 writes in all);
  - SCL ≈ 98 kHz.

### 3.9 Mutants, regression, resources, SD-15

- **Mutants:** **23 / 23** caught:
  - exp2 ×4;
  - sin ×3, including two's-complement reflection;
  - engines, routing, truncation, closing, delay, error gating ×8;
  - inspector ×1;
  - output stage ×4;
  - I2S ×2 (left-justified; strobe without Δ_pre);
  - synchronizer ×1.
- **Regression on the changed L2 RTL:**
  - run_phase3 ALL PASS, including run_phase2 ALL PASS;
  - the same numbers as the Phase 3 record — T_wake 1, g 0, HK 13, worst full-load sweep 2,062 / 1,038;
  - 11 / 11 sweep mutants.
- **Resources:** in `logs/yosys_stat.txt` (ESTIMATE); see the report §7.
- **SD-15:** reproduced, 24 of 24 runs (`run_sd15.txt`).
- **Found and fixed before this record.** An error raised in the first housekeeping window after reset did not halt the Core, because JumpVal was still at its power-up 0. Fixed by `wpms_formation.v` RH003 / `wpms_l2_top.v` RH002; the 50 MHz test-origin case above shows the HALT.
- **Not as first expected.**
  - The literal test origin is refused with EW5 at BCP, not EW2 at the prefetch — the profile's own order of checks.
  - The first latency measurement was one MCLK short: a bench timestamping artifact, fixed in the bench.
  - In the stress sweeps longer than 4,096 bins (above any real sweep), the inspector's position counter wrapped. It now saturates.

### 3.10 Waveform / 波形

`test_origin_50mhz_first_frames.vcd.gz`: the 50 MHz build playing the test origin (N = 1,008). It is the grid case's stimulus cut to 6 strobes, with the bench's `+vcd` (the top's ports and the Core's control state). Read from it:

1. Strobe 0 at 20,750 ns takes the GO; its sweep is empty.
2. From strobe 1 (41,570 ns), `l1_packet_start` follows every strobe by 40 ns — two clocks: T_wake 1 plus the L1 face.
3. The bundles latched are PH0 = PHD1 = 0, LP = 0xFFD30084 (log₂ 0.97), RT = 3, and then PH0 advanced by OM0 = 0x054FDF3B and PHD1 by OMD1 = 350 per sample — the [S] advance of Ch.3 §3.4.3.
4. The banks written 80 ns after the strobes are 0, 0, 0 (the first played sample is sin 0 = 0), then 0x03FAED, 0x07E47D, 0x0BAB9E, the rise of the Dirichlet envelope.
5. The I2S pins carry the same words.

This is the reference for the Phase 6 SignalTap capture of the same signals ("bundle at packet_start vs prediction").

`test_origin_50mhz_first_frames.vcd.gz`: 50 MHz 版（N = 1,008）でテスト原点を鳴らす最初の 6 ストローブ。ストローブ後 40 ns で packet_start、ラッチされたバンドル、バンク値（0, 0, 0, 0x03FAED, 0x07E47D, 0x0BAB9E）、I2S 端子。Phase 6 の SignalTap 取得と比べる基準波形。

## 4. Verdict / 判決

**PASS.** Every expectation of §2 holds in the recorded run, with one expectation corrected before the record: the literal test origin is refused by EW5, not EW2 (§3.9). No golden model, Layer 1 document or frozen Core source was edited.

**合格。** §2 の期待はすべて記録実行で満たした。記録前に訂正した期待は一件（字義どおりのテスト原点は EW2 ではなく EW5 で拒否される、§3.9）。黄金モデル・第1層文書・凍結 Core は一切編集していない。
