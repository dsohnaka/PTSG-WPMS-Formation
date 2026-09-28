# Phase 0 — Baseline / 基線

*CC0 · 2026-09-27 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 0.*
*Verdict: **the baseline is green.** Every golden model and both frozen Core testbenches run unchanged and agree with the numbers the profile publishes. Eleven discrepancies are filed (`discrepancies.md`), five of which bear on Phases 2–3; none is fixed.*

*判定: **基線は緑。** 黄金モデルと凍結 Core の二つのテストベンチを無改変で実行し、プロファイルの公表値とすべて一致した。食い違いを 11 件記録した（うち 5 件は Phase 2–3 に効く）。修正は一切していない。*

---

## 1. What was built / 作ったもの

Nothing of the design yet — Phase 0 only runs and reads. / 設計物はまだない。Phase 0 は実行と通読のみ。

| File | Purpose |
|---|---|
| `03_Sample_Implementations/hw/tools/run_phase0_baseline.sh` | Reproducible recipe for this phase: records the four commit hashes and the toolchain, runs the frozen Core testbenches and every golden model, writes the logs below. Writes nothing into the golden-model directories (the contract is regenerated into a temporary directory; byte-code caching off). / 本段階の再現手順。黄金モデルのディレクトリには何も書かない。 |
| `04_Verification_Evidence/reports/logs/phase0/*.log` | The thirteen logs of one run of that script. / スクリプト一回分のログ 13 本。 |
| `04_Verification_Evidence/reports/discrepancies.md` | The discrepancy register, opened here (SD-01 … SD-11). / 食い違い台帳（本段階で開設）。 |
| `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` | The brief itself, placed where the workspace `CLAUDE.md` says it lives. Unchanged. / 指示書本体（CLAUDE.md が示す場所に配置、無改変）。 |

## 2. Workspace and toolchain / 作業空間とツール

Four repositories side by side, not nested (`00_workspace.log`). Every hash equals the pin in Register W v0.7 §0 and Register Map v0.3.

| Repository | Commit | Date | Pin in Register W v0.7 |
|---|---|---|---|
| PTSG-Core | `1b58ebcdee6e2f53e17b2484c665a404784da10b` | 2026-09-26 20:08 +0900 | `1b58ebcdee6e` ✓ |
| PTSG-CPU-Formation | `ad43cc2c4472072b07c3e4660a01036be266863e` | 2026-09-07 14:31 +0900 | `ad43cc2c4472` ✓ |
| PTSG-WPMS-Formation | `dae44742a222b30c435e96308cf4069316a583c8` | 2026-09-27 17:32 +0900 | (this profile) |
| FPGA_Spectrum_Engine_OpenPrompt | `891fce6dacdb9ada8363bf73ab3faf18b33215c8` | 2026-09-24 22:43 +0900 | `891fce6dacdb` ✓ |

- Icarus Verilog **12.0 (stable)** — not preinstalled in the container; installed from the distribution package (`iverilog 12.0-2build2`). Python **3.11.15**. / Icarus は未導入だったためディストリビューションのパッケージから導入。
- Quartus Prime Lite and a DE10-nano are **not** available in this container: Phase 6 (SILICON) must run on the architect's bench. / Quartus と実機は本コンテナにない。Phase 6 は設計者の机で。
- Frozen Core source: `ptsg_core.v` sha256 `fb9956877bd24981541bbdd3e9316df168782c69b0b2d6a0633dccfbe13060e0`, equal to the blob at `1b58ebc` (`14_frozen_core_sha256.log`). / 凍結 Core のハッシュは `1b58ebc` の blob と一致。

## 3. Commands run and their last lines / 実行したコマンドと末尾行

All runs are reproduced by `hw/tools/run_phase0_baseline.sh`. Expected values (from the brief and the profile's documents) are stated **before** the observed ones.

| # | Command (as in the brief) | Expected | Observed (last lines) | Class |
|---|---|---|---|---|
| 1 | `iverilog -g2012 … ptsg_core.v ptsg_core_tb.v ptsg_imem.v; vvp` | PASS A..G | `PASS A … PASS G2` (9 lines), `ALL TESTS PASSED` | RTL-SIM |
| 2 | `iverilog -g2012 … ptsg_core.v ptsg_core_conformance_tb.v ptsg_imem.v; vvp` | PASS T1..T34 | 35 PASS lines (T5 is split a/b), `ALL CONFORMANCE TESTS PASSED` | RTL-SIM |
| 3 | `python3 isa_fold_w.py` (output to a temporary file) | 16 instructions, fold log citing every W-ID | `16 instructions (18 in master)`; `regenerated contract == committed contract (ignoring 'folded' …): True` | ORACLE |
| 4 | `python3 sweep_sim.py <customer oracle> 20000 2026` | 0 mismatches | `20000 samples, 71341 packet plays, 1403 GOs (… 416 full-load GOs)` · `L1 bundle mismatches vs reference: 0   machine/sequencer errors: none` · `N_MIN = 25 + 4 = 29 (profile constant 32)` · `BCP worst case: 10 clocks; worst sweep (Core nominals included): 2064 of 2083 clocks` | ORACLE |
| 4b | same, seeds 7 and 42 (the profile's other two seeds; not required by the brief) | 0 mismatches | 70,042 and 74,244 packet plays, 0 mismatches each. **Three-seed totals 215,627 plays, 4,174 GOs, 1,175 full-load — exactly the published figures** | ORACLE |
| 5 | `python3 negative_tests.py` | 13/13 | `13/13 negative tests behave as specified` (N12 mutant: 2,798 mismatches, caught) | ORACLE |
| 6 | `python3 pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json` | CLEAN, max error 7.39e-09 | `validate: 27 instructions; CLEAN` · `max |err| over sweep = 7.39e-09 at x=+0.40` | ORACLE |
| 7 | `python3 wpms_layer1_oracle.py` (customer) | 18/18 | 18 `[PASS]` lines, `ALL PASS` | ORACLE |

Compile notes: both Core testbenches draw one pre-existing warning — `Port 23 (prescaler_counter) of ptsg_core expects 16 bits, got 32` (the testbenches declare a 32-bit wire for a `PRESC_W` = 16 port). Benign, unchanged. / 両テストベンチに既存の警告一件（32 ビットの wire を 16 ビットのポートへ）。無害・不変。

## 4. Deviations from the golden models / 黄金モデルからの逸脱

**None.** Every number above equals the value the profile's documents publish (Register W v0.7 §9; Layer 3 README; Deliverable 3 §8). The regenerated contract is byte-for-byte the committed one apart from the `folded` date field, which `isa_fold_w.py` stamps with the day it runs.

**なし。** 上記の数値はすべてプロファイルの公表値と一致する。再生成した契約は、実行日が入る `folded` 欄を除き、コミット済みのものと同一。

## 5. Reading notes — what the law fixes for the build / 通読メモ——構築に効く法

Read in the brief's order: Register W v0.7 §2–§4 → Register Map v0.3 → Deliverable 2 → Deliverable 3 → trace 2026-09-27 → master Ch.2 §2.9 and Ch.5 → Core Ch.3 §3.2–§3.4b and the stay-value CHANGES (with the reference sketch, the RH029/030 header patch and the frozen RTL) → customer Ch.3 and Appendix 5.A.

| Topic | What is fixed | Where |
|---|---|---|
| Rulings | All ruled through 09-27: CMT, RTW out; WSV restricted (sequencer is the sole Stay-value writer); EW2 (N ∉ [32, 2048]) … EW6 all Error HALT; STP 4·0, BCP 4·1; ADD/SUB wrap, E8 only MUL/MAC; lanes STROBE/NONEMPTY/MORE on TS_CSEL[1:0], TS_PKT for L1; **R2 preferred, R1 for bring-up** | W v0.7 §2.1 |
| Address space | 9-bit ADRS: store 0x000–0x07F (write in HK only), inbox view 0x080–0x0FF (read-only; +0xE = staged RT.OUT, +0xD reads 0), CUR alias 0x100–0x10F (write in a packet window only; reads 0 outside), COMMIT view 0x110–0x117, staged sweep 0x118, SWEEP.a 0x119, status 0x11A; other → E5 | Map §4 |
| Block format | 16 slots; bundle = PH0, PHD1, PHD2, LP, LS0, LAD1, LAD2, RT.OUT; L1 never reads N, TAG, LE0, LPT, OM\*; +0xE = RT.OUT (not CUR) | Map §6; D2 §2 |
| Bundle and timing | L1 latches the bundle at the packet's Stay Set clock with K = 0; g = 0; T_wake ≤ 4 (nominal 2); packet length exactly N for N ≥ N_MIN | D2 §2–§3 |
| Stay value | StayVal.s ← N at prefetch (EW2); StayVal.p ← TS_PKT ? StayVal.s : 0 at every Stay Set; drives the Core's `stay_value`; HK Stay sees 0 so its literal applies | D3 §5; Map §2 |
| Core `stay_value` | IND-reverse `D = pin ≠ 0 ? pin : (operand ≠ 0 ? operand : 4096)`; read once at the Stay's execute clock, held (C4-F16); `>=` compare (C4-F17); one sample for the zero test and the value (C5-F4); lean C4-T5 (B), C5-T2 (A) = `CNT_W` = 12 | CHANGES 2026-09-26; sketch §2, §7, §8 |
| Core bus as built | `ext_op_*` without band; no SSS port; no external error input; `timing_signals` registered; taken Branches auto-save | `ptsg_core.v` RH030 → SD-01…SD-06, SD-11 |
| Customer L1 | phase by forward differences mod 2³²; log-domain amplitude (54-bit Q23.30 shape loop, exp2 table 256 × Q2.30 + degree-2 polynomial); products Q1.63, accumulators Q12.63 closed on the strobe; D_L1 ≤ 24; test origin = Dirichlet block, N = 2,048, OM0 = 89,120,571, OMD1 = 350, LP = −2,948,988 | customer Ch.3 §3.4–§3.10 |
| Customer requirements | CR3-A1, B1, B2, R1, T1–T3, C1, M1 and CR5-I1–I3, S1, L1, R1 active; CR3-C2, C3 replaced; App. 5.A.2 still shows +0xE = CUR (already on the profile's shelf as W-D25 / PR-5) | customer App. 5.A |

## 6. Discrepancies filed / 記録した食い違い

Eleven rows, all by reading (details and Japanese glosses in `discrepancies.md`):

- **SD-01** band not on the issue port (brief's known #1) · **SD-03** SSS not exported (known #2) · **SD-04** no data-driven gap-free R2 (known #3, preliminary).
- **SD-02** the Core issues and executes an external-mode Global in the **foreground** (IF-3 assumes it halts) — E1, like E2, has no hardware detector.
- **SD-05** Core Branch law vs the Deliverable 3 sketch: taken Branches auto-save (a second save waits in `S_PUSH` for `stack_ack`), and a queued Branch not taken resumes at Branch + 1. Literally encoded, the NONEMPTY check would stall the Core on the second empty sweep (the reset state), and R1's "forward conditional" is not gap-free.
- **SD-06** no external error input on the Core (INT-R2) · **SD-07** I is 16 bits in the Core, W12 in the Map · **SD-11** registered timing signals shift TS_PKT one clock against K = 0.
- Editorial: **SD-08** (Register W v0.7 §2.2 fragment), **SD-09** (customer mask presets lack bit 16), **SD-10** (stale comments in the frozen Core header).

## 7. Questions for the architect / アーキテクトへの質問

1. **E1 and E2 (SD-01, SD-02).** With neither a band on the bus nor an FG trap for mode ≥ 1, may the silicon phase treat **both** E1 and E2 as validator-only, as the brief already does for E2? / E1 も E2 と同様に検証器のみで扱ってよいか。
2. **SSS (SD-03).** No WPMS program reads SSS. In Phase 2, is it acceptable that source ID 6 returns a documented substitute (and which do you prefer: the `state_number` latched at the profile's packet start, or 0 with a note), pending INT-R4? / ソース ID 6 の代替として何を返すのがよいか。
3. **The Core score (SD-04, SD-05, SD-11).** Before Phase 3: is the queued Branch's not-taken resume address (Branch + 1, as T16 pins it) the intended Core law, or should "not taken" advance past the Stay? The answer decides whether R1 can be gap-free without discharging the holding register every packet. / キュー帯域 Branch の not-taken 再開番地（Branch+1）は意図どおりか。R1 の無間隙性がこれで決まる。
4. **Width of I (SD-07).** Proceed with a 16-bit I, zero-extended? / I は 16 ビットのゼロ拡張でよいか。

Phase 1 proceeds on its own ground (it touches only the Core copy and needs none of these answers). / Phase 1 は Core の写しのみを扱い、上記の回答を必要としない。

## 8. Resource numbers / 資源数

Not applicable before Phase 2. / Phase 2 以前は該当なし。
