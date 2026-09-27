# observation — Phase 1: PTSG-Core RH031 (provisional) on a copy — `stay_value`, form B
# 観測判決 — Phase 1: 写しの上の PTSG-Core RH031（仮）— `stay_value`、B 形

**Verdict / 判決: PASS.** With the pin silent the copy is bit-identical to the frozen RH030 source; with the pin speaking it behaves as C4-F15…F17 and C5-F4 say; the anti-pattern of sketch §4, built in the testbench only, is caught by SV-4 (an 8192-clock Stay). One nominal of the profile is replaced by an RTL-SIM number: a 25-instruction packet window needs **N ≥ 30** on this Core, not 29 (filed as SD-12; the profile constant N_MIN = 32 still holds).

**合格。** ピンが黙っていれば写しは凍結 RH030 とビット同一、ピンが語れば C4-F15〜F17・C5-F4 どおり。テストベンチ内だけで作った反パターンは SV-4 が 8192 クロックの Stay として捕えた。プロファイルの名目値一つを RTL-SIM 値で置き換える: 25 命令の窓には N ≥ 30 が要る（29 ではない。SD-12 に記録。定数 N_MIN = 32 は成立）。

**Evidence class / 証拠クラス:** RTL-SIM (Icarus Verilog 12.0, `-g2012`). Nothing here is SILICON. **License:** CC0 1.0 Universal.

---

## 1. Setup / 環境

| Item | Value |
|---|---|
| RTL under test | `03_Sample_Implementations/hw/core/ptsg_core_rh031p.v` (module `ptsg_core`): frozen RH030 + the RH029/030 header patch (comments) + `stay_value` form B + the RH031 draft entry. Diff against RH030: `rh030_vs_rh031p.diff` (+64 / −8 lines; logic: one port, two wires) |
| Reference | frozen `PTSG-Core/03_Sample_Implementations/ptsg_core_verilog/ptsg_core.v` at `1b58ebc`, sha256 `fb995687…60e0` — only read. For the lockstep it is compiled from a build copy renamed `ptsg_core_rh030` |
| Testbenches | the Core's own `ptsg_core_tb.v` (P = 1) and `ptsg_core_conformance_tb.v` (P = 5), **unchanged**, with `hw/tools/vcd_dump.v` as a second root; new `hw/core/ptsg_core_sv_tb.v` (`ptsg_core_sv_tb`: SV-1…SV-7 + SV-5b at P = 1; `ptsg_core_sv0_tb`: SV-0 lockstep) |
| Recipe | `03_Sample_Implementations/hw/core/run_phase1.sh <this directory>` — about 40 s; exits non-zero on any failed expectation |
| Clock | 10 ns period in simulation (the 100 MHz of the WPMS build); the sample instants below are 1 ns after each rising edge |

## 2. Expected — written before the runs / 期待値（実行前に記述）

| Item | Expected | Basis |
|---|---|---|
| Pin silent (unconnected, or tied 0) | bit-identical to RH030 on every signal the two share; the only one-sided nets are the copy's `stay_value` and `stay_dur_lit` | C4-F15 ("silent pin = bit-identical"); sketch §7 SV-0 |
| SV-1 | bare Stay, pin = N, P = 1: the Stay occupies N clocks; NOP + Stay + Jump loop = N + 2 | C4-F15; RH028 |
| SV-2 | pin = 1: one clock (same-clock bare timeup), loop period 3 | RH028; `ptsg_core_tb` F1 |
| SV-3 | pin 20 → 9 while a Stay waits: that Stay 20, the next 9 | C4-F16 (read once at execute, held in `stay_target`) |
| SV-4 | pin 0 in the clock before, 37 in the execute clock: that Stay 37. Anti-pattern: 8192 | C4-T5 (B); C5-F4; sketch §4 |
| SV-5 | windowed Stay, counter already at 7 when the Stay executes, pin = 3: timeup in the **first** S_WAIT clock (Stay visible 2 clocks). Contrast, pin silent, operand 100: Stay Set → resume = 100 clocks | C4-F17 (`>=`); C4-F10 grid anchoring |
| SV-5b (supplementary) | Stay Set · 25 BG NOPs · Prog End · queued Jump → Stay Set · Stay, pin = N: Stay Set to Stay Set = **max(N, 30)**, K = 0 … period−1, no idle clock. 30 = 25 window + Stay Set + Prog End + queued Jump + the Stay's execute clock + one S_WAIT clock (a windowed Stay never times up in its execute clock: the same-clock timeup of RH028 is for bare Stays only) | RTL reading of `OP_STAY`/`S_WAIT` |
| SV-6 | Stay(0), pin silent: 4096 clocks | C2-F3 |
| SV-7 | `len_lut[state_number]` {2: 7, 4: 11} → 7 / 11; {2: 7, 4: 0} → 7 / 5 (operand) | C5 §5.12a idiom (ii) |
| Anti-pattern (forced in the testbench) | SV-4 and SV-7 fail with 8192-clock Stays; SV-1, 2, 3, 5, 5b, 6 pass (a constant pin hides the slip) | sketch §4; CHANGES §10 (pre-check SV-4, SV-7) |
| Form A (forced, informative) | SV-4 and SV-7 fall back to the operands (5; 3 and 5): form A needs the length one clock ahead | sketch §3; C4-T5 |

## 3. Observed / 観測

**Bit-identity, pin unconnected (the Core's testbenches unchanged).**

| Suite | Pass log | VCD comparison (`vcd_compare_*.txt`) |
|---|---|---|
| `ptsg_core_tb.v` A..G (P = 1) | identical to RH030's, `ALL TESTS PASSED` | 174 common signals, 8,376 value changes, **0 mismatching**; end time #4,276,000 ps in both; one-sided: `dut.stay_value`, `dut.stay_dur_lit` |
| `ptsg_core_conformance_tb.v` T1..T34 (P = 5) | identical to RH030's, `ALL CONFORMANCE TESTS PASSED` | 192 common signals, 579,164 value changes, **0 mismatching**; end time #234,246,000 ps in both; same two one-sided nets |

The common set includes the internal `stay_dur` wire itself, so the substitution point is shown equal, not only its consequences. / 共通集合には内部の `stay_dur` 自体が含まれる。置換点そのものが一致している。

**SV-0 lockstep, pin tied 0** — RH030 and the copy side by side; all outputs and 38 internal registers/wires compared every clock:

| Run | Clocks | Mismatching clocks | Stimulus actually delivered (RH030 side) |
|---|---|---|---|
| random programs, P = 1, 300 × 2,000 | 600,000 | **0** | 17,587 Stays (12,268 windowed, 5,319 bare, 5 Stay(0)), 17,571 timeups, 4,193 queued firings, 1,546 HALTs, 1,874 insertions, 4,719 pushes, 301 pops, 4,720 indirect reads, 6,363 external issues |
| random programs, P = 5, 200 × 3,000 | 600,000 | **0** | 6,794 Stays (4,790 windowed, 2,004 bare, 4 Stay(0)), 6,760 timeups, 1,995 queued firings, 1,404 HALTs, 1,920 insertions, 5,630 pushes, 301 pops, 3,131 indirect reads, 5,108 external issues |
| Scene 4 program, P = 6250 → `prescaler_value` = 20 live | 290,538 | **0** | `timing_signals[0]` high 25,000 / low 25,000 clocks, twice — the half-periods the SILICON capture of 2026-08-29 shows |

(The equal pop counts of the two random runs are a coincidence; an independent count of `stack_pop_req` rising edges gives 301 in both, and BG/queued Return mixes differ: 241 + 60 vs 251 + 50.)

**SV-1 … SV-7 on form B: 8 passed, 0 failed.**

| Test | Observed |
|---|---|
| SV-1 | N = 2, 3, 7, 100, 2048, 4095 → Stays of exactly 2, 3, 7, 100, 2048, 4095 clocks; loop periods N + 2 |
| SV-2 | 1 clock; loop period 3 |
| SV-3 | 20, then 9 |
| SV-4 | pin 0 → 37 at the execute clock; that Stay 37 clocks |
| SV-5 | pin 3 < elapsed 7: Stay visible 2 clocks, 1 S_WAIT clock; contrast (silent pin): Stay Set → resume 100 clocks, Stay visible 94 |
| SV-5b | N = 29 → 30; 30 → 30; 31 → 31; 32 → 32; 33 → 33; 64 → 64; 2048 → 2048; 4095 → 4095. K = 0 … period−1 with 0 errors in every case; the next Stay Set follows K = N−1 on the next clock (g = 0) |
| SV-6 | 4096 clocks |
| SV-7 | {7, 11} → on 7, off 11; {7, 0} → on 7, off 5 |

**The tests bite.** Anti-pattern forced in the testbench: `SV SUMMARY: 6 passed, 2 failed: SV-4 SV-7` — SV-4's Stay lasts **8192** clocks; SV-7's two table entries both run 8192. Form A forced (informative): `6 passed, 2 failed: SV-4 SV-7` — SV-4 lasts 5 (the operand), SV-7 gives 3 / 5 (the operands).

## 4. The SV-4 waveforms — where to look / SV-4 波形の見どころ

Files: `sv4_formB.vcd.gz` (≈ 0.8 KB) and `sv4_antipattern.vcd.gz` (≈ 73 KB), timescale 1 ps. Signals: `state_number`, `stay_value`, `dut.stay_dur`, `dut.stay_target`, `dut.stay_cnt` (13-bit), `stay_counter` (K, 12-bit), `stay_cnt_match`, `dut.fsm` (0 = S_RUN, 1 = S_WAIT). Program: 0 NOP · 1 NOP · 2 Stay 5 · 3 Jump 1; `stay_value` = 37 while `state_number` = 2, else 0.

| Sample (ns) | Form B | Anti-pattern |
|---|---|---|
| 26 | `state_number` 1, `stay_value` 0 — the clock before the Stay | same |
| 36 | `state_number` 2 (the Stay's execute clock), `stay_value` 37, **`stay_dur` 37** | `stay_value` 37, **`stay_dur` 0** (the registered sample is still 0) |
| 46 | `stay_target` 37, `fsm` 1, `stay_cnt` 1 | `stay_target` **0**, `fsm` 1, `stay_cnt` 1 |
| 396 / 81,946 | `stay_cnt` 36 = target − 1 → timeup | `stay_cnt` 8,191 = 0x1FFF → timeup (K reads 4,095: the 12-bit K wrapped once, at `stay_cnt` 4,096) |
| 406 / 81,956 | `state_number` 3, `stay_cnt_match` 1 — **37 clocks** | `state_number` 3, `stay_cnt_match` 1 — **8,192 clocks** |

The anti-pattern costs the whole Stay, as sketch §4 predicts; and under it K would wrap inside one packet, so an L1 indexing bins by K would repeat bin numbers — a second reason the WPMS build must never meet it. / 反パターンは Stay 全体を奪う。さらに K がパケット内で一周するため、K でビンを数える L1 はビン番号を重複させる——WPMS がこれを決して踏んではならない第二の理由。

## 5. Conclusion / 結論

**PASS** on every expectation of §2. RH031 (provisional), form B, width `CNT_W` = 12, is ready for the Core's office to review at its checkpoint. For the profile: the Stay-value path of Deliverable 3 §5 can be built on this pin as specified (StayVal.p stable from one Stay Set to the next satisfies both C4-T5 forms), and the packet floor on this Core is 30 for a 25-instruction window (SD-12).

§2 のすべての期待に対し合格。RH031（仮）B 形・幅 12 は Core 事務所のチェックポイント審査に供しうる。プロファイルにとって: 成果物 3 §5 の Stay 値経路はこのピンの上に仕様どおり組める（StayVal.p が Stay Set から次の Stay Set まで安定なら C4-T5 のどちらの形でも成立）。25 命令の窓に対するパケット下限はこの Core で 30（SD-12）。

## 6. Notes / 注記

- Compiler messages (all in `logs/compile_all.log`): the Core testbenches' pre-existing `prescaler_counter` width warning; `input port stay_value is coerced to inout` (Icarus, for a `tri0` input driven by a testbench net — the value seen is the driven one, as every SV test shows); `procedural continuous assignments are not yet fully supported` (Icarus evaluates a forced expression once; the testbench therefore re-issues the force whenever an operand changes).
- Not covered here: timing closure of the new combinational path `stay_value → mux → −1 → compare` in the bare same-clock timeup (sketch §2), and resources — both need Quartus (Phase 6).
