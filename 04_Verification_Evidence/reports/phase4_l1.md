# Phase 4 — L1 pipeline and output path / L1 パイプラインと出力路

*CC0 · 2026-09-29 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 4, with the rulings of 2026-09-28 and 2026-09-29. Stops here, as the brief asks.*

*Verdict: **done and green.** `hw/l1/` holds one WPMS module's L1 pipeline and the whole output path of the customer's Ch.4. **Bit-exact with the customer's oracle**, which was imported unchanged:*

- *the phase path (`l1_phase`);*
- *the log-domain amplitude path with the master gain (`l1_amplitude`, `exp2_q131` with its table and polynomial, the clamps);*
- *the MG slew (`step_toward`).*

*It is also **bit-exact with a published model** (`hw/tools/l1_model.py`) of the parts the oracle does not model: the Maclaurin sin core, the product, the accumulators and the output stage.*

*Where it was checked:*

- *1,000,000 inputs each for the sin core and exp2;*
- *3 × 400 module sweeps (651,424 bins), plus 154,135 samples of MG fade and soft mute;*
- *the whole synthesizer (Core + Formation + sequencer + L1 + output stage + I2S) under the sweep oracle's GO traffic at both clock budgets;*
- *the whole synthesizer on the real 48 kHz I2S grid, with a receiver decoding the wire.*

*The customer's end-to-end numbers reproduce:*

- *927 audible bins for the σ = 71 Gaussian;*
- *a test-origin peak of −6.29 dBFS at G = 12;*
- *MG 0 → −60 dB in 1.0000 s;*
- *a latency to the wire of 21.484 µs = 1.031 periods.*

*D_L1 = **19** clocks (target ≤ 24). One module needs about **16 DSP blocks and 1 M10K** (ESTIMATE). Three items need a ruling or the customer's attention:*

- *SD-16: Ch.2's sin format table cannot meet Ch.2's own budget;*
- *SD-17: the test origin (N = 2,048) cannot play at NMAX = 1,008;*
- *the ADV7513 register values that could not be checked against the document.*

*Evidence class: **RTL-SIM** (model self-tests ORACLE, resources ESTIMATE).*

*判定: **完了・緑。** `hw/l1/` は 1 モジュール分の L1 パイプラインと顧客第4章の出力路一式である。**顧客オラクル（無改変で import）とビット一致**するのは、位相（`l1_phase`）、マスターゲイン込みの対数振幅（`l1_amplitude`、表と多項式・クランプ込みの `exp2_q131`）、MG スルー（`step_toward`）。オラクルがモデル化しない部分——マクローリン sin コア・積・累算器・出力段——は、公開モデル `hw/tools/l1_model.py` とビット一致する。検査の範囲:*

- *sin と exp2 は各 100 万入力;*
- *モジュール 3 × 400 スイープ（651,424 ビン）と、MG フェード・ソフトミュート 154,135 サンプル;*
- *合成器全体（Core・Formation・シーケンサ・L1・出力段・I2S）を、両クロック予算でスイープ・オラクルの GO 通信下に置いて;*
- *合成器全体を実際の 48 kHz I2S グリッドで動かし、受信器で線上を復号して。*

*顧客の端から端までの数値は再現した: σ = 71 のガウシアンで可聴 927 ビン、テスト原点のピーク −6.29 dBFS（G = 12）、MG 0 → −60 dB が 1.0000 秒、線上までのレイテンシ 21.484 µs = 1.031 周期。D_L1 は **19** クロック（目標 24 以内）、1 モジュールは DSP 約 **16**・M10K **1**（概算）。裁定または顧客の確認を要する項目は三つ: SD-16（第2章の sin 書式表は第2章自身の誤差予算を満たせない）、SD-17（テスト原点 N = 2,048 は NMAX = 1,008 では鳴らない）、文書と照合できなかった ADV7513 のレジスタ値。*

---

## 0. Rulings applied (2026-09-29) / 適用した裁定

| Ruling | How Phase 4 applies it |
|---|---|
| (1) The dispatch form of the R1 score is the standard score | `wpms_synth_top` runs `wpms_r1d`; every system test uses it |
| (2) NMAX = 1,008 at 50 MHz | the 50 MHz budget is NMAX 1,008, T_min 1,041. At full load the last product reaches the accumulator at clock **1,028**, 12 clocks before the next strobe (§3.4). The test origin as written does not fit (SD-17) |
| (3) SD-04: no INT-R1 request for now | recorded; nothing to build |
| (4) SD-15: the workaround stands; a bug report to the Core team | a six-word reproduction on the **frozen** Core source (`hw/core/sd15_insert_handshake_tb.v`, `run_sd15.sh`, `rtl_sim/2026-09-29_sd15_insert_handshake/`). Conveyed as [dsohnaka/PTSG-Core#5](https://github.com/dsohnaka/PTSG-Core/issues/5), the Core repository's channel for proposals ("open an issue first") |
| (5) LoopVal stays connected | unchanged (`wpms_l2_top.v`, indirect purpose 01) |
| 2026-09-28: L1 silenced at once on error; no pipelining of long paths now | L1 stops accumulating in the clock the flag rises. The accumulators read zero and the bank is zero from the next close. The L1 pipeline has the chapters' own depth (sin 16 clocks, Approach B) and nothing more |

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `hw/l1/wpms_l1_module.v` | One module's L1 (219 lines, MIT):<br>• c0: bundle latch at `packet_start`, and two difference engines — phase mod 2³², and shape at 54 bits Q.30 with `lvl = (LP≪4) + (MG≪4)`;<br>• c1–c16: sin (16 clocks) in parallel with exp2 (6 clocks + 10 delay);<br>• c17–c18: the product Q1.71 → Q1.63, truncated toward zero;<br>• c19: the accumulators, L and R Q12.63, gated by RT.OUT, closed on the strobe.<br>Also: a sample tag per bin and a sticky **overrun** flag; SWEEP_CLOCKS / _MAX (Ch.4 §4.9); the inspector (Ch.5 0x040). **D_L1 = 19** |
| `hw/l1/wpms_l1_sin.v` | The Maclaurin core (99 lines), bit for bit `l1_model.sin_q040`:<br>• 11th order, Horner, 2 clocks per stage, 16 clocks in all;<br>• 7 multipliers, every operand ≤ 26 bits;<br>• reflection by bit inversion, truncation toward zero, Q0.40 out.<br>It is the published realization of SD-16 (§3.1) |
| `hw/l1/wpms_l1_exp2.v` | The exp2 unit (88 lines), bit for bit the oracle's `exp2_q131`: split, clamps, the 256-entry table in one M10K, the degree-2 polynomial at the oracle's widths, and the barrel shift. 6 clocks |
| `hw/l1/wpms_l1_consts.vh`, `wpms_exp2_table.hex/.mif` | Generated by `hw/tools/gen_l1_tables.py` — the table, C1 and C2 from the oracle's own integers, the sin constants from the model. One source, two consumers |
| `hw/l1/wpms_output_stage.v` | Ch.4 §4.4 (125 lines):<br>• MG steps on every strobe (`step_toward`; the new MG plays in the sweep that strobe starts);<br>• Σ modules, then `saturate(round(acc · 2⁻ᴳ))` → Q1.23, with G = DIP·4 or an override;<br>• sticky clip flags;<br>• soft mute drives MG to the floor, then exact zero;<br>• silence on error;<br>• the output bank is written 3 clocks after the strobe |
| `hw/l1/wpms_i2s_master.v` | Ch.4 §4.3, §4.6.1 (73 lines):<br>• MCLK 12.288 MHz, SCLK = MCLK/4, LRCLK;<br>• Philips I2S, 24 bits in 32-bit slots;<br>• the **L3 strobe** toggles at F_m − 4 MCLK;<br>• the bank is captured at F_m (the stability window, C4-D7) |
| `hw/l1/wpms_strobe_sync.v` | A two-flip-flop toggle synchronizer into clk_sys, one clock per frame, plus STROBE_INTERVAL / MINMAX (64 lines) |
| `hw/l1/wpms_video_720p.v` | The video carrier (Ch.4 §4.7): 720p60, VIC 4, static colour bars for bring-up or black |
| `hw/l1/wpms_adv7513_cfg.v` | The ADV7513 configurator (Ch.4 §4.6.2, 223 lines):<br>• an I2C master at 100 kHz, open drain, honouring clock stretching;<br>• HPD polled at 0x42[6];<br>• a 29-entry table written after power-up and after every hot-plug;<br>• each entry marked by its basis (§3.8) |
| `hw/l1/wpms_synth_top.v` | One module end to end: I2S master → strobe sync → `wpms_l2_top` → `wpms_l1_module` → output stage → I2S. The switch port and the Ch.5 control registers are ports, for Phase 5 to drive |
| `hw/l1/wpms_l1_units_tb.v`, `wpms_l1_tb.v`, `wpms_synth_tb.v`, `wpms_video_tb.v`, `wpms_adv7513_tb.v` | The benches (§2) |
| `hw/l1/run_phase4.sh` | The recipe |
| `hw/tools/l1_model.py` | The bit-level model (284 lines):<br>• golden parts imported from the customer's oracle;<br>• the sin core, product, accumulators and output stage published here;<br>• a self-test (the sin core exhaustively over u, the phase path against `l1_phase`) |
| `hw/tools/gen_l1_tables.py`, `cosim_l1.py`, `cosim_synth.py`, `cosim_l1_mutants.py` | Table generator; unit / module / MG-fade cosimulation; system cosimulation (oracle traffic and grid cases, with an I2S receiver); the 23 L1 mutants |
| changed: `hw/l2/wpms_formation.v` (RH003), `hw/l2/wpms_l2_top.v` (RH002) | JumpVal powers up at the dispatch score's TAIL_0 (the finding of §4.2). Also a header correction: NMAX 1,008 at 50 MHz |
| `hw/core/sd15_insert_handshake_tb.v`, `run_sd15.sh` | The SD-15 reproduction for the Core's office (ruling (4)) |
| `04_Verification_Evidence/rtl_sim/2026-09-29_phase4_l1/`, `…/2026-09-29_sd15_insert_handshake/` | `observation.md` (expected before observed) and the logs |
| `04_Verification_Evidence/reports/discrepancies.md` | Rulings of 2026-09-29; SD-16, SD-17, SD-18 new; SD-04 closed; SD-05, SD-06, SD-15 updated |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

```
$ REGRESSION=0 03_Sample_Implementations/hw/l1/run_phase4.sh 04_Verification_Evidence/rtl_sim/2026-09-29_phase4_l1
run_phase4: 2026-09-29T13:15:47Z — Icarus Verilog version 12.0 (stable); Python 3.11.15; numpy 2.4.6; 3000 samples per seed
  [PASS] wpms_layer1_oracle.py (unchanged): ALL PASS, CH4-CREST with numpy
  [PASS] l1_model.py self-test: the sin core within 2^-23.9 of sin(2 pi phi) (exhaustive over u), phases = l1_phase (ORACLE)
  [PASS] wpms_exp2_table.hex/.mif and wpms_l1_consts.vh equal a fresh generation (oracle _T/_C1/_C2; model constants)
  [PASS] wpms_synth_top (L2 + L1 + output path) and the output-path blocks compile
  [PASS] sin core = l1_model.sin_q040 and exp2 unit = the oracle's exp2_q131, 1,000,000 inputs each
  [PASS] wpms_l1_module + output stage: every bin (phase = l1_phase, a = l1_amplitude, sin, product) and every sample (bank, clip, MG, SWEEP_CLOCKS)
  [PASS] MG 0 -> -60 dB in 1.0 s at 13,933 per sample (CH4-MG); soft mute to the floor, then exact zero (C4-D6)
  [PASS] wpms_synth_top on the 48 kHz grid: samples = model, I2S wire = bank, latency 21.48 us, strobe 1041/1042 and 2083/2084, 927 audible bins, test-origin peak
  [PASS] wpms_synth_top under sweep_sim's GO traffic: bundles as the oracle, every output sample as the model, SWEEP_CLOCKS < T_min
  [PASS] video carrier: 720p60 timing (VIC 4)
  [PASS] ADV7513 configurator: HPD poll, the table written and acknowledged in order, rewritten after a hot-plug
  [PASS] cosim_l1_mutants.py: every deliberate defect in the L1 RTL is caught
  [PASS] SD-15 reproduction on the frozen Core and the copy (bug report to the Core's office)
run_phase4: ALL PHASE 4 CHECKS PASSED

$ 03_Sample_Implementations/hw/l2/run_phase3.sh          # step 1 of the recipe, run once on the identical L2 RTL
run_phase3: ALL PHASE 3 CHECKS PASSED                      # (it runs run_phase2.sh first: ALL PHASE 2 CHECKS PASSED)
```

The recipe without `REGRESSION=0` runs step 1 itself (about 40 minutes more). Every log is in `rtl_sim/2026-09-29_phase4_l1/logs/`.

## 3. Results, with evidence classes / 結果と証拠クラス

Details in `rtl_sim/2026-09-29_phase4_l1/observation.md` §3.

### 3.1 The sin core (SD-16) — ORACLE and RTL-SIM

The oracle does not model sin, so the core's bits are the implementation's: they are published in `l1_model.py` and generated into the RTL.

| | Ch.2 v1.1 table, literally | Published realization |
|---|---|---|
| Variable | x′ = 2πξ (Q2.25), X = x′² (Q4.23) | u = ξ′ in cycles (26 bits), U = u² (26 bits) |
| Horner | Y = C − X·Y, all Y and C in Q1.26 (C₁₁ = 2 LSB) | S_j = c_j − U·S_{j+1}, c_j = (2π)^(2j+1)/(2j+1)!, one power-of-two scale per stage |
| Multipliers · clocks | 7 · 16 | 7 · 16 (the last multiply by u: x′ is never materialized) |
| Max \|sin error\| | 3.97×10⁻⁷ = 2⁻²¹·³ (200,000 phases) | **5.96×10⁻⁸ = 2⁻²⁴·⁰** (exhaustive over u) — the 11th-order truncation, (π/2)¹³/13! = 5.7×10⁻⁸ |

The RTL equals the model on 1,000,000 phases.

### 3.2 Bit-exactness — RTL-SIM

| Level | What is compared | Against | Volume | Mismatches |
|---|---|---|---|---|
| exp2 unit | a | oracle `exp2_q131` | 1,000,000 L (31,758 directed) | **0** |
| sin core | sin | `l1_model.sin_q040` | 1,000,000 phases | **0** |
| L1 module + output stage | per bin: phase, a, sin, product | oracle `l1_phase`, `l1_amplitude` (+MG); model | 651,424 bins, 3 seeds | **0** |
| | per sample: bank L/R, clip, MG, SWEEP_CLOCKS, inspector | model (+ oracle `step_toward`) | 1,203 samples, 796 captures | **0** |
| MG fade and soft mute | MG, bank | oracle `step_toward`; model | 154,135 samples | **0** |
| Whole synthesizer, oracle traffic | bundles, N, K, `stay_value` | `sweep_sim.py` | 18,000 sweeps, 20.3 M bins | **0** |
| | every output sample | model over the oracle's bundles | 18,006 samples | **0** |
| Whole synthesizer, 48 kHz grid | every output sample; bundles | model over `sweep_sim.Reference` pages | 8 cases, 2 budgets | **0** |
| | I2S wire | the master's capture; the bank | 537 frames | **0** |

### 3.3 The customer's end-to-end numbers — RTL-SIM

| Number | Customer (ORACLE) | Here (RTL-SIM) |
|---|---|---|
| σ = 71 Gaussian, N = 2,048: bins with a ≠ 0 | 927 (CH3-E2E) | **927** in each of 6 packets (naive and consistent slots) |
| Test origin, G = 12: peak | −6.3 dBFS (CH3-ORIGIN, Ch.3 §3.6.4) | **−6.29 dBFS** (4,068,448 of 2²³, first 120 samples) |
| MG 0 → −60 dB at 13,933 per sample | 1.0 s (CH4-MG) | **1.0000 s** (strobe 48,001) |
| Latency, sweep start → left MSB on the wire | 21.48 µs = 1.031 periods (Ch.4 §4.8) | **21.484 µs = 1.0312** |
| Strobe interval | 2,083 / 2,084 (Ch.4 §4.3.2) | **2,083 / 2,084**; at 50 MHz **1,041 / 1,042** |
| D_L1 | ≤ 24 (Ch.3 §3.6.5) | **19** |

### 3.4 The budget at both clock targets — RTL-SIM

- **50 MHz, NMAX 1,008.**
  - At full load (8 × 126 bins) the last product enters the accumulator **1,028** clocks after the strobe: 12 clocks before the next strobe.
  - The Core is back in SLEEP at 1,022 (measured in the same full-load case).
  - The sweep oracle's traffic peaked at 1,025 (its sweeps never reach NMAX: SD-18).
- **100 MHz, NMAX 2,048.** The worst is 2,068 of 2,083, and the Core is back at 2,062.

This is the customer's inequality T_wake + Σ N + g·(P − 1) + D_L1 ≤ T_min, measured: 1 + 1 (the L1 face, SD-11) + 1,008 + 19 = 1,029 ≤ 1,041. The architect's arithmetic of 2026-09-28 (NMAX ≤ 1,015 with D_L1 24) now reads NMAX ≤ 1,020 with the measured D_L1 = 19; the ruled 1,008 keeps 12 clocks in hand.

### 3.5 Output path — RTL-SIM

- **I2S:** Philips format, 24 bits in 32-bit slots. A receiver bench decodes every frame, and each one equals the words the master captured at F, which equal the bank.
- **Strobe:** 4 MCLK before F.
- **Video carrier:** 1,650 × 750 clocks, 1,280 × 720 active, 60.0001 Hz.
- **ADV7513 configurator:** 29 writes acknowledged in order, and the table again after a hot-plug. §3.8 of the evidence note gives the table's basis.

## 4. Deviations and findings / 逸脱と発見

**4.1 From the golden models: none.** Every quantity the customer's oracle defines was matched bit for bit:

- the phase path (`l1_phase`) and the amplitude path with MG (`l1_amplitude`);
- the exp2 unit (`exp2_q131`, clamps included);
- the MG slew (`step_toward`).

The profile's `sweep_sim.py` supplied the bundles and the pages (its `Reference`), and every one was matched. Every golden file ran unchanged; no `__pycache__` was left beside them (`sys.dont_write_bytecode`).

The sin core, the product truncation, the accumulators and the output stage are compared with the **published model** `hw/tools/l1_model.py`. That model is mine, not golden: the oracle has no model of them (SD-16). Its sin core is checked against sin(2πφ) exhaustively, and its output stage uses the oracle's `step_toward` for MG.

**4.1 黄金モデルからの逸脱: なし。** 顧客オラクルが定める量はすべてビット一致した: 位相経路（`l1_phase`）とマスターゲイン込みの振幅経路（`l1_amplitude`）、クランプ込みの exp2（`exp2_q131`）、MG スルー（`step_toward`）。`sweep_sim.py` が与えるバンドルとページ（`Reference`）も一致。黄金ファイルは無改変で動かし、`__pycache__` も残していない。sin・積の切り捨て・累算器・出力段は、私が公開したモデル `l1_model.py` と比べている——オラクルにはそれらのモデルがない（SD-16）。

**4.2 Found and fixed: an error in the first housekeeping window after reset did not halt the Core.** The new grid test found this when it played the literal test origin at NMAX 1,008.

1. BCP raises EW5 in the first sweep's housekeeping, before the dispatch program's WJV.
2. JumpVal is still at its power-up value, 0.
3. The dispatch's background indirect Jump goes to 0x000, inside the open window.
4. The Core then loops through SLEEP_0 and never reaches a Stay, so the deferred insertion (C3-F20) is never taken. It did not halt.

L1 was silent all the same: the ruling's safety requirement held.

- **Fix** (Formation side): JumpVal powers up at the dispatch score's TAIL_0 (0x300). This is a `wpms_formation.v` RH003 parameter `JUMPVAL_RESET`, with default 0 as the model; `wpms_l2_top.v` RH002 sets it through `TAIL_BASE`.
- **Now:** EW5, L1 silent, **HALT at 0x3FF 11 clocks after the flag**, as Phase 3's EW5 case.
- **Regression:** the Phase 2 and Phase 3 recipes were re-run on the changed RTL: green (§3.10).

In steady state JumpVal always holds a valid tail from the previous housekeeping, which is why Phase 3's injections (all in later sweeps) never met this.

**4.2 発見と修正: リセット直後の最初のハウスキーピング窓でのエラーで Core が停止しなかった。** グリッド試験（NMAX 1,008 で字義どおりのテスト原点）で発見。BCP が最初のスイープのハウスキーピングで WJV より前に EW5 を上げると、JumpVal は電源投入値 0 のまま。ディスパッチの BG 間接 Jump が開いた窓の中で 0x000 へ飛び、Core は Stay に達しないまま SLEEP_0 を回るので、延期された挿入（C3-F20）が取られない。L1 は無音で、裁定の安全要求は満たされていた。修正: JumpVal の電源投入値を楽譜の TAIL_0 にした（Formation RH003 のパラメータ、既定値はモデルどおり 0。L2 最上位 RH002 が設定）。修正後は EW5・即無音・フラグの 11 クロック後に 0x3FF で停止。Phase 2/3 の手順を再実行して緑。

**4.3 Not as first expected (all found before the recorded run) / 事前の予想と異なった点**

- **The literal test origin at NMAX 1,008.** I first expected EW2 at the prefetch. The refusal is **EW5 at BCP**: the new sweep word's Σ N exceeds NMAX, and BCP's check comes first. That is the profile's own rule, so the expectation was corrected, not the RTL.
- **The first latency measurement was 1 MCLK short (21.403 µs).** This was the bench, not the design. It sampled the strobe toggle one MCLK edge late (a nonblocking-assignment ordering). The bench now timestamps the toggle itself, and the latency is exactly 264 MCLK.
- **The inspector's bin-position counter wrapped at 4,096.** The module test's stress sweeps (up to about 4,700 bins, longer than any real sweep of ≤ NMAX bins) made it capture bin 4,096 + 7. It now saturates at 4,095, as the 12-bit field of Ch.5 §5.6.1 implies.
- **Phase 0's customer-oracle "18/18 PASS" included a vacuous CH4-CREST.** numpy was absent, so the check skipped itself and still printed PASS; its INFO line only appears with `-v`. numpy 2.4.6 is now installed. CH4-CREST runs for real and passes all 7 sub-checks (crest factors 36.12 / 5.60 / 12.17 dB). This corrects the Phase 0 record; the substance stands.

- **字義どおりのテスト原点**は、プリフェッチの EW2 ではなく BCP の EW5 で拒否された（新スイープ語の Σ N 超過が先に検出される——プロファイル自身の規則）。
- **レイテンシの初回測定が 1 MCLK 短かった**のは試験台の計時で、設計は 264 MCLK ちょうど。
- **インスペクタのビン位置カウンタ**が 4,096 超の負荷試験で一周した。飽和に変更。
- **Phase 0 の顧客オラクル「18/18」**の CH4-CREST は numpy 不在で空の合格だった。numpy を入れて実行し、7 項目とも合格。Phase 0 の記録を訂正する（実質は変わらない）。

**4.4 Choices where the texts are silent (published in the model; please confirm) / 文書が沈黙する箇所の選択**

| Item | Choice | Texts |
|---|---|---|
| Which sweep uses a new MG | the sweep that the strobe starts (MG steps in the strobe clock; packets start ≥ 2 clocks later) | Ch.4 §4.4.1 "at each synchronized strobe" |
| "exact zero once MG reaches the floor" | a sweep played with MG = −32 under soft mute outputs exactly zero (the last sweep above the floor still sounds: 128 LSB in the test) | Ch.4 §4.4.5 |
| "round to nearest" | add half, then floor (ties toward +∞) | Ch.4 §4.4.2 |
| Product truncation | toward zero (Ch.2's policy, C2-D11) | Ch.3 §3.6.1 "truncated" |
| Silence on error | nothing accumulated from the flag's clock; the bank is zero from the first close after it (the bank changes only on strobes, C4-D7) | ruling 2026-09-28 |
| A product landing in the strobe clock | belongs to the closing sample (it can only be the closing sweep's) | Ch.3 §3.6.3 "arrive before strobe n+1" |
| MG_TARGET > 0, MG_RATE < 0 | treated as 0 (MG attenuates only; a rate is ≥ 0) | Ch.4 §4.4.1, Ch.5 0x010/0x011 |

## 5. Discrepancies filed / 記録した食い違い

`reports/discrepancies.md`:

- **SD-16 — the Maclaurin core.** The Ch.2 v1.1 format table, read literally, gives 2⁻²¹·³ against its own budget of about 1.3×10⁻⁷. Other points: the reflection wording ("equivalent to two's complement" is wrong at the quadrant boundary), (π/2)¹³/13! = 5.7×10⁻⁸, and the oracle has no sin model. The published realization gives 2⁻²⁴·⁰. For the customer, via the architect.
- **SD-17 — the test origin at NMAX 1,008.** It is refused by EW5. A ruling is needed on the 50 MHz ROM image.
- **SD-18 — the sweep oracle's full-load GOs reach Σ N = 992 at NMAX 1,008.** Informative; covered by a directed case.
- **Updated:**
  - SD-04: ruled and closed.
  - SD-05: the standard score does not meet it.
  - SD-06: the Phase 4 finding of §4.2.
  - SD-15: ruled, and conveyed as [dsohnaka/PTSG-Core#5](https://github.com/dsohnaka/PTSG-Core/issues/5).

## 6. Questions for the architect / アーキテクトへの質問

1. **SD-17, the test origin on the 50 MHz build.** The ROM's block has N = 2,048 and is refused at NMAX 1,008. Options: (a) N = 1,008 with every other integer as §3.10 (proposed; plays bit-exact at −12.44 dBFS peak at G = 12); (b) keep N = 2,048 and play the test origin only on a 100 MHz build. Phase 5 builds the ROM port. / 50 MHz 版の ROM のテスト原点は N = 1,008 でよいか。
2. **SD-16, the Maclaurin core.** May the published realization (`l1_model.py`, 2⁻²⁴·⁰) be the L1's sin definition until the customer's next Ch.2? And may the notes (the formats, the reflection wording, 5.7×10⁻⁸, a sin model in the oracle) go to the customer? / sin の公開実現を当面の定義としてよいか。顧客へ伝えてよいか。
3. **The ADV7513 table.** The entries marked [R] come from recall of the programming guide's register map. The guide's host (www.analog.com) is blocked by this session's network policy, so they are not verified against the document. Either allow that host (or place the PDF in a repository) so I can check the table before Phase 6, or accept confirming it on silicon in Phase 6 by reading the registers back. / ADV7513 の [R] 項目は文書未照合。文書を参照可能にするか、Phase 6 の実機読み返しで確認するか。
4. **§4.4, the choices where the texts are silent.** Please confirm them, or rule otherwise. / 文書が沈黙する箇所の選択（§4.4）の確認をお願いしたい。
5. **Modules.** Phase 4 builds one module (M = 1). Compact is two (CR3-M1): a second L2 + L1, about 16 more DSP blocks, and a second inbox for the switch. Should the second module wait for Phase 5/6, after first sound, or go in at Phase 5 with the switch? / 2 モジュール目は初音の後か、Phase 5 でスイッチと同時か。

## 7. Resource numbers / 資源数

**ESTIMATE** (Yosys 0.69, `synth_intel_alm -family cyclonev` + `abc -lut 6`; no Quartus here), per entity (`logs/yosys_stat.txt`):

| Entity | LUT | Arith ALUT | FF | 27×27 | 18×18 | M10K |
|---|---|---|---|---|---|---|
| `wpms_l1_sin` | 67 | 177 | 962 | **7** | 0 | 0 |
| `wpms_l1_exp2` | 173 | 261 | 312 | 5 | 2 | **1** |
| `wpms_l1_module` (the two above + engines, product, accumulators, inspector) | 880 | 1,396 | 2,664 | 14 | 4 | 1 |
| `wpms_output_stage` | 792 | 488 | 321 | 0 | 0 | 0 |
| `wpms_i2s_master` | 44 | 20 | 61 | 0 | 0 | 0 |
| `wpms_strobe_sync` | 54 | 38 | 52 | 0 | 0 | 0 |
| `wpms_video_720p` | 31 | 90 | 45 | 0 | 0 | 0 |
| `wpms_adv7513_cfg` | 180 | 70 | 117 | 0 | 0 | 0 |

- **DSP blocks per module.** A Cyclone V DSP block takes one 27×27 or two 18×18, so a module needs **16**: sin 7 (C2-D10), exp2 6, product 3. The customer estimated 12–16 (Ch.3 §3.6.6). The output path uses none (Ch.4 §4.10).
- **M10K:** 1, the exp2 table (§3.5.4).
- **L1 plus the output path:** roughly 2–2.5 k ALMs.
- **Whole synthesizer.** With Phase 3's L2 (≈ 5–6 k ALMs, 4 M10K, 3 DSP) one module comes to about **8 k ALMs, 19 DSP and 5 M10K** of the 5CSEBA6 (41,910 ALMs, 112 DSP, 553 M10K). A second module (Compact) would bring it to about 16 k ALMs and 38 DSP.
- **Timing.** Phase 6 replaces all of this with Quartus and closes timing at 50 MHz. The longest L1 paths are the 77-bit round-and-shift of the output stage and the 54-bit shape adders, and nothing in the L1 is wider than those.

---

*Stopped at the end of Phase 4, as instructed. / 指示どおり Phase 4 の終わりで停止する。*
