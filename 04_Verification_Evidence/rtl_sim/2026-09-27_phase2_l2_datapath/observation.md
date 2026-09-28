# observation — Phase 2: the L2 Formation datapath against the golden model
# 観測判決 — Phase 2: L2 Formation データパスと黄金モデル

**Verdict / 判決: PASS.** `wpms_formation.v`, driven one instruction per clock the way the Core drives it, is **bit-identical to `pfasm_tools_w.Machine`** on 3,914 cases (105,519 issued instructions): the three window programs, all 13 negative cases, 377 encodings the assembler never emits, the prefetch port, and 3,000 random contract sequences. `exp_maclaurin_w` on the hardware gives **max |err| = 7.39e-09**, the oracle's figure. Twenty deliberate defects, each in a scratch copy of the RTL, are **all caught**. The Core copy decodes the assembled score exactly as encoded. Two new discrepancies are filed (SD-13, SD-14) and SD-05 is reproduced in simulation.

**合格。** Core と同じく1クロック1命令で駆動した `wpms_formation.v` は、3,914 ケース（発行 105,519 命令）すべてで `pfasm_tools_w.Machine` と**ビット同一**。対象は窓プログラム3本、否定試験13件、アセンブラが出さない符号 377 種、プリフェッチ口、契約内ランダム列 3,000 本。ハードウェア上の `exp_maclaurin_w` の最大誤差は **7.39e-09** でオラクルと一致。RTL の写しに1つずつ入れた欠陥20種は**すべて検出**。Core の写しは組み立てた楽譜を符号どおりに解読する。食い違い2件（SD-13, SD-14）を新規記録し、SD-05 をシミュレーションで再現した。

**Evidence class / 証拠クラス:** RTL-SIM (Icarus Verilog 12.0, `-g2012`), except §3.7: an ESTIMATE from Yosys. Nothing here is SILICON. **License:** CC0 1.0 Universal.

---

## 1. Setup / 環境

| Item | Value |
|---|---|
| RTL under test | `03_Sample_Implementations/hw/l2/wpms_formation.v` + the generated `wpms_decode.vh` |
| Golden model | `03_Sample_Implementations/tools/pfasm_tools_w.py` (`Machine`, `validate`) and `sweep_sim.py` (`Sequencer.strobe`, `Sequencer.prefetch`, `rand_block`, `bundle_of`) — **imported, never edited** |
| Testbench | `hw/l2/wpms_formation_tb.v`: plays a command file; each `I` presents one Global on `ext_op_*` for one clock, with the taps (K, I, SN, SSS) and the sequencer context (phase, `cur`, `q`) held beside it, as the Core does; the switch port, strobe, prefetch port and a backdoor for the initial store |
| Harness | `hw/tools/cosim_l2.py` (seed 20260927; four simulator runs in parallel); `hw/tools/cosim_mutants.py`; `hw/tools/score_rt.py` with `hw/l2/score_rt_tb.v` on `hw/core/ptsg_core_rh031p.v` |
| Recipe | `03_Sample_Implementations/hw/l2/run_phase2.sh <this directory>` — about 110 s; exits non-zero on any failed expectation; `logs/run_phase2.txt` is its output |
| Compared after each case | Accm, Temp, ADRS, SHV, SWEEP.a, the copied / take-set / sweep-copied bits, `inbox_taken`, LoopVal, JumpVal, error flag / code / instruction index / SN, `insert_req`, all 128 store words; at every prefetch the port's N and eight bundle words |
| Error rule | The model records errors and continues; the hardware halts at the first. For an erroring case the expected scene is the model's state **just before** the erroring instruction, with its code and index; the instructions issued after it must not execute |

## 2. Expected — written before the runs / 期待値（実行前に記述）

| Item | Expected | Basis |
|---|---|---|
| Every case | bit-identical to the model under the error rule of §1 | brief Phase 2 acceptance |
| `wpms_packet` in packet windows | 25 instructions per window, CUR = the block given as `cur`; several blocks per case | D3 §6.1; Map v0.3 §4 |
| `wpms_housekeeping` (BCP) in HK | masked copy of the take-set, RT.OUT by bit 16, the sweep item into SWEEP.a, EW5 for P > 8, a repeated block, Σ N > NMAX (item or sweep in effect), then `inbox_taken` | W-F27; Map v0.3 §7 |
| `exp_maclaurin_w` in HK, x = −0.50 … +0.50 | max \|err\| = **7.39e-09** at x = +0.40 | ORACLE: `pfasm_tools_w.py` main, re-run by the recipe (`logs/oracle_exp.log`) |
| Negative cases | N1 EW4 · N2 EW4 · N3 EW4 · N4 EW3 · N5 EW6 · N6 EW5 · N7 EW5 · N8–N11 E4 · N12 the mutant window differs from the correct one · N13 EW2 | ORACLE: `negative_tests.py` 13/13 (Phase 0) |
| Encodings with no `.pfasm` form | E4 at the raw word, nothing after it executes | `decode_map.json` must-be-zero rule; Map v0.3 §3 |
| Clocks | issue at t, execute (stage X) at t + 1, every instruction, back to back. BCP: architectural at t + 1; the copy lands one block per clock from t + 2 (B taken blocks → t + 1 + B), one clock later for every datapath store write meanwhile; `inbox_taken` seen high from t + 2 + B | the design (`wpms_formation.v` header) |
| Mutants | each of the 20 defects makes at least one case fail | — |
| Score round trip | every external issue carries the assembled word; SD-05 (a): the second empty sweep waits in S_PUSH; SD-05 (b): with MORE true at timeup the packet period doubles (2 × 32); D3 §3-§4: P > 0 → NONEMPTY true → PKT0 | SD-05 by reading (Phase 0); D3 §3-§4 |

## 3. Observed / 観測

### 3.1 Cosimulation (`logs/cosim_l2.txt`)

| Group | Cases | Bit-identical | Instructions | Cases ending in an error (code: count) |
|---|---|---|---|---|
| packet — `wpms_packet`, 1–3 sweeps of 1–8 blocks, all 8 `cur` | 60 | 60 | 13,100 (524 windows) | — |
| hk — `wpms_housekeeping`, random take-sets, masks (presets, random 17-bit), items valid / P > 8 / repeated / Σ N > NMAX / backstop | 300 | 300 | 397 | EW5: 73 |
| fwd — BCP, then at once reads and writes of slots still being copied | 120 | 120 | 3,645 | — |
| exp — `exp_maclaurin_w`, 21 values of x | 21 | 21 | 567 | — |
| neg — N1 … N13 (N12 three times) | 15 | 15 | 151 | E4 4, EW2 1, EW3 1, EW4 3, EW5 2, EW6 1 |
| e4 — every illegal {mode, sub-op} (240) and every must-be-zero / reserved-ID violation, plus the legal extremes | 377 | 377 | 2,646 | E4: 376 |
| prefetch — N ∈ {16, 31, 32, 33, 64, 2047, 2048, 2049, 0, −1, −2048, 2³¹−1, −2³¹}, and all 8 bundles after a BCP | 14 | 14 | 14 | EW2: 8 |
| timing — traced cases (§3.3) | 7 | 7 | 45 | EW3: 1 |
| random — contract sequences, 1–60 instructions, 1–3 windows, GOs and strobes between them, idle gaps, taps changed per instruction | 3,000 | 3,000 | 84,954 | E5 125, E8 75, EW3 95, EW4 117, EW5 2, EW6 36 |
| **total** | **3,914** | **3,914** | **105,519** | 920 |

Every mnemonic was issued: ADD 9,518 · BCP 1,647 · LDA 10,892 · LDM 14,074 · MAC 4,097 · MUL 4,232 · SAD 24,820 · SFT 4,051 · STA 4,671 · STM 6,190 · STP 3,445 · SUB 5,736 · SWP 4,457 · WJV 2,015 · WLV 1,943 · WSH 3,352 (and the removed rows CMT, PSH, WSV once each, as N8–N10). Of the 75 E8 endings, 34 are at SFT (SD-13). Simulator protocol warnings and invariant violations (`inbox_taken` high while a copy is pending): **0**.

### 3.2 exp and the negative cases / exp と否定試験

- `exp_maclaurin_w` on the hardware: **max |err| over 21 x = 7.39e-09 at x = +0.40** — the oracle prints the same line (`max |err| over sweep = 7.39e-09 at x=+0.40`).
- N1 EW4 at instruction 5 · N2 EW4 at 0 · N3 EW4 at 1 · N4 EW3 at 1 · N5 EW6 at 6 (the STP) · N6 EW5 · N7 EW5 · N8 CMT, N9 WSV, N10 PSH, N11 STA ADRS: E4 at 2 (after two legal instructions) · N12 (three random blocks): the mutant window runs bit-identically to the model of the mutant, and its store differs from the correct window's at slot 0x6 (PH0) of the CUR block · N13 EW2 at the prefetch. All as expected.

### 3.3 Clocks, traced (`[trace]` lines of `logs/cosim_l2.txt`) / 実測クロック

| Case | Observed |
|---|---|
| T1 — `wpms_packet` back to back | 25 issues in clocks 18,869 … 18,893; stage X in 18,870 … 18,894: **every X = issue + 1**, no gap |
| T2 — BCP, 0 blocks taken, sweep item | X 20,056; `inbox_taken` high from 20,057 (X + 1) |
| T2 — BCP, 1 block | X 19,919; block 0 lands at 19,920; `inbox_taken` from 19,921 (X + 2) |
| T2 — BCP, 8 blocks | X 20,101; blocks 0 … 7 land at 20,102 … 20,109 (`bcp_busy` 8 clocks); `inbox_taken` from 20,110 (**X + 9**) |
| T3 — BCP, 8 blocks, then STM STM … STA @PPM at once | X 19,024; blocks land at 19,025–27, 19,030–31, 19,033–35 — paused in 19,028, 19,029, 19,032, the three datapath store writes; `bcp_busy` 11 clocks; `inbox_taken` from 19,036. The LDM of block 7 slot 15 (X 19,026, still pending) returned the inbox value (forwarding) — the final store proves it |
| T4 — STM into the inbox view | EW3 at X 20,182; the three instructions issued after it are not executed; `insert_req` cleared by the acknowledge |
| T5 — strobe in BCP's X clock | the copy still lands (20,048 … 20,055); `copied`, `inbox_taken` restart with the strobe — the model's order, BCP then strobe |

All as expected in §2. / §2 の期待どおり。

### 3.4 Mutants (`logs/cosim_mutants.log`) / 変異体

20 of 20 killed. Each row: the defect → failing cases by group (400 random sequences per mutant run).

| ID | Defect | Caught by |
|---|---|---|
| M1 | store reads ignore pending slots (no forwarding) | fwd 53, timing 1, random 1 |
| M2 | a datapath write to a pending slot does not cancel its copy | fwd 33, timing 1 |
| M3 | ADD saturates instead of wrapping (W-F30) | packet 51, fwd 25, neg 2, timing 1, random 2 |
| M4 | BCP in the strobe's clock wins over the strobe | timing 1, random 1 |
| M5 | must-be-zero immediate not checked for operand-less instructions | e4 14 |
| M6 | the CUR alias follows ADRS instead of `cur` | packet 60, neg 3, timing 1, random 86 |
| M7 | MAC realigns with a logical shift | exp 10, random 73 |
| M8 | bundle order: LP and LS0 swapped | prefetch 14 |
| M9 | EW2 lower bound off by one | prefetch 1 |
| M10 | K read at execute instead of with the issue (F-F10) | random 17 |
| M11 | the violating STM still writes | e4 4, random 11 |
| M12 | BCP sums the pre-copy N | hk 19 |
| M13 | STP: E5 checked before EW6 | random 1 |
| M14 | `inbox_taken` before the copy has landed | invariant 1,850 |
| M15 | the copy does not pause for a datapath store write | fwd 71, timing 1, random 7 |
| M16 | STA TEMP also writes the store | neg 4, e4 377, random 178 |
| M17 | no E8 on a left SFT overflow | random 3 |
| M18 | status view: phase bit inverted | random 27 |
| M19 | no backstop: Σ N checked only with a sweep item | hk 6 |
| M20 | a repeated block in the sweep item accepted | hk 28, neg 1 |

The thinnest catches (M9, M13 by one case; M4 by two) are named here so that later changes keep them covered. / 検出が薄いもの（M9, M13 は1件、M4 は2件）を明記する。

### 3.5 Score round trip (`logs/score_rt.log`) / 楽譜の往復

| Run | Expected | Observed |
|---|---|---|
| RT-1, P = 0 | issues = image words; HK Stay Set → Jump SLEEP = T_HK = 13; SD-05 (a): second empty sweep stalls in S_PUSH | 1 issue (BCP `00000140` at 0x0EC) = image; 13 clocks; `stack_push_req` at clock 302, state 0x002, FSM in S_PUSH to the end — **as SD-05 (a)** |
| RT-2, P = 2 | D3 §3-§4: NONEMPTY true → PKT0 | the Branch at 0x002 sees `timing_signals` = 0x0000 (SLEEP's STROBE lane, strobe low) and goes to HK — **not as D3 §4: filed SD-14** |
| RT-3, P = 2, `NOP CSEL=NONEMPTY` before the Branch | PKT0 → PKT1 = 2 × 32 (SD-05 b) | 101 issues = image; window 0 in order; PKT0 → PKT1 **64** clocks, PKT1 → HK 32 — **as SD-05 (b)** |

### 3.6 Compile and generators / コンパイルと生成器

`gen_decode.py --check`: map consistent with `isa_table_w.json`; `wpms_decode.vh` and `decode_map.md` regenerate identically. `pfasm_as.py`: 25, 1 and 27 words, equal to `hw/l2/programs/*.hex`. `score_as.py`: 240 words + trap, equal to the committed fixture image. `iverilog -Wall`: 11 "@* is sensitive to all words" notes, nothing else.

### 3.7 Resource estimate (ESTIMATE, not RTL-SIM) / 資源見積り

Yosys 0.69 (`yowasp-yosys`), `synth_intel_alm -family cyclonev`, LUT mapping by `abc -lut 6` (ABC9 does not run in the WebAssembly build): **4,611 LUTs + 931 arithmetic ALUTs, 1,203 flip-flops, 1,568 MLAB bit-cells (32 × 1), DSP 2 × MUL27X27 + 2 × MUL18X18** (`logs/yosys_stat.txt`). Quartus replaces these in Phase 6.

---

## 4. Verdict / 判決

**PASS** on every expectation of §2 except RT-2, which did not behave as Deliverable 3 §4 says and is filed as **SD-14** (a property of the Core as built: its timing-signal bus is registered — the same root as SD-11). SD-05 (a) and (b) are now RTL-SIM, not only reading. SD-13 (E8 for SFT: the model and the hardware agree; the texts say "MUL/MAC only") awaits a ruling. No golden model, Layer 1 document or frozen Core source was edited.

**合格。** §2 の期待はすべて満たした。例外は RT-2 で、Deliverable 3 §4 のとおりには動かず SD-14 として記録した（Core のタイミング信号が登録出力であることに由来し、SD-11 と同根）。SD-05 の (a)(b) は読解から RTL-SIM に格上げ。SD-13（SFT の E8：モデルとハードウェアは一致、文書は「MUL/MAC のみ」）は裁定待ち。黄金モデル・第1層文書・凍結 Core は一切編集していない。
