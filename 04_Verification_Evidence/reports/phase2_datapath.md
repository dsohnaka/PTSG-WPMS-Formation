# Phase 2 — The L2 Formation datapath / L2 Formation データパス

*CC0 · 2026-09-27 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 2. Stops here, as the brief asks.*
*Verdict: **done and green.** `hw/l2/wpms_formation.v` is the Formation side of the nine-lane border for this profile. Driven one instruction per clock exactly as the Core drives it, it is **bit-identical to `pfasm_tools_w.Machine`** on 3,914 cases — the three window programs, the 13 negative cases, every encoding the assembler never emits, the prefetch port, and 3,000 random contract sequences; `exp_maclaurin_w` gives **7.39e-09**, the oracle's figure. **20 of 20** deliberate defects are caught. The decode map is one JSON feeding the RTL table, both assemblers and the published map. Two discrepancies are new (**SD-13**, **SD-14**) and SD-05 is now reproduced in simulation. Evidence class of every number: **RTL-SIM**, except the resource figures (**ESTIMATE**, Yosys).*

*判定: **完了・緑。** `hw/l2/wpms_formation.v` は本プロファイルの九レーン境界の Formation 側。Core と同じく1クロック1命令で駆動し、3,914 ケース（窓プログラム3本、否定試験13件、アセンブラが出さない全符号、プリフェッチ口、契約内ランダム列 3,000 本）で `pfasm_tools_w.Machine` と**ビット同一**。`exp_maclaurin_w` は **7.39e-09**（オラクルと同値）。故意の欠陥 **20/20** を検出。デコード表は一つの JSON から RTL 表・二つのアセンブラ・公開表を生成。新規の食い違い **SD-13**・**SD-14**、SD-05 はシミュレーションで再現。数値はすべて **RTL-SIM**、資源数のみ **ESTIMATE**（Yosys）。*

---

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `03_Sample_Implementations/hw/l2/wpms_formation.v` | The datapath (572 lines, MIT, Core header format). Issue register (stage I) + execute (stage X); Accm, Temp, ADRS (9 bits, SAD / post-increment only), SHV; sources IMM, TEMP, PPM, K, I, SN, SSS; the 9-bit L2 space of Map v0.3 §4 (store, inbox view, CUR alias, COMMIT view, sweep words, status); block store **slot-major** (sixteen 8 × 32 banks; bank 0 = N as a register file) and inbox likewise (banks 13, 14 not stored); STP; BCP with a background copy; errors E4, E5, E8, EW2–EW6 with Error HALT through the insertion bus; prefetch port (N + the eight-word bundle, EW2); input-switch port (Ch.5 §5.6.2 layout). |
| `03_Sample_Implementations/hw/l2/wpms_decode.vh` | The decoder table — **generated**, do not edit. |
| `03_Sample_Implementations/hw/l2/decode_map.md` | The published decode map (bilingual) — **generated** from the same JSON. |
| `03_Sample_Implementations/hw/tools/decode_map.json` | **The one source**: word layout (sub-op D8–D11, register ID D12–D15, immediate D16–D31), operand kinds and the must-be-zero rule, the 16 instructions, the 5 removed rows (E4), IDs, error codes, TS_PKT / TS_CSEL bits. |
| `03_Sample_Implementations/hw/tools/gen_decode.py` | Checks the JSON against `isa_table_w.json` (every contract row, no extra row, removed rows absent, IDs equal, fields tile D0–D31), then writes `wpms_decode.vh` and `decode_map.md`; `--check` verifies both are current. |
| `03_Sample_Implementations/hw/tools/pfasm_as.py` | `.pfasm` → Global words (`$readmemh` `.hex` with comments). Parses with the golden `pfasm_tools_w.parse` (imported). `--allow-removed` encodes removed rows and `STA ADRS` for negative tests only. |
| `03_Sample_Implementations/hw/tools/score_as.py` | Score assembler: Core words (Stay, Branch, Jump, the eight internal Globals), `PKT` / `CSEL=` timing bits, `Window` splices of `.pfasm` programs, labels, `.equ`, `.trap` (a foreground Prog End at `TRAP_ADDR`); writes `.hex` and `.mif` in the Core's formats. |
| `03_Sample_Implementations/hw/l2/programs/*.hex` | `wpms_packet` (25 words), `wpms_housekeeping` (1), `exp_maclaurin_w` (27), assembled. |
| `03_Sample_Implementations/hw/l2/scores/d3_sketch_r1_fixture.{score,hex,mif}` | **Test fixture, not the Phase 3 score**: the D3 §3 sketch (R1) transcribed literally, 240 words + trap. Its header says why it cannot be the score (SD-05, SD-14). |
| `03_Sample_Implementations/hw/l2/wpms_formation_tb.v` | Stimulus-driven testbench standing where the Core stands (one Global per clock on `ext_op_*`, taps and sequencer context held with it), plus switch writes, strobe, prefetch, backdoor, trace, and an invariant (`inbox_taken` never high while a copy is pending). |
| `03_Sample_Implementations/hw/tools/cosim_l2.py` | The cosimulation (§3): builds the cases, runs the golden model per instruction, writes stimuli, runs Icarus in parallel, compares. |
| `03_Sample_Implementations/hw/tools/cosim_mutants.py` | 20 defects, one per scratch copy of the RTL; each must make the cosimulation fail. |
| `03_Sample_Implementations/hw/l2/score_rt_tb.v`, `hw/tools/score_rt.py` | Round trip of an assembled score through the Core copy (`hw/core/ptsg_core_rh031p.v`) with a toy lane mux. |
| `03_Sample_Implementations/hw/l2/run_phase2.sh` | The recipe; exits non-zero on any failed expectation (§2). |
| `04_Verification_Evidence/rtl_sim/2026-09-27_phase2_l2_datapath/` | `observation.md` (expected before observed) and every log. |
| `04_Verification_Evidence/reports/discrepancies.md` | SD-13, SD-14 added; SD-03, SD-05, SD-06 updated with Phase 2 facts. |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

`03_Sample_Implementations/hw/l2/run_phase2.sh 04_Verification_Evidence/rtl_sim/2026-09-27_phase2_l2_datapath` (Icarus Verilog 12.0 `-g2012`, Python 3.11; 111 s):

```
run_phase2: 2026-09-27T13:42:11Z — Icarus Verilog version 12.0 (stable) (); Python 3.11.15
  gen_decode: map consistent with the contract; RTL table up to date ; published map up to date
  [PASS] decode_map.json consistent with isa_table_w.json; wpms_decode.vh and decode_map.md regenerate identically
  [PASS] pfasm_as.py: wpms_packet (25), wpms_housekeeping (1), exp_maclaurin_w (27) equal the committed images
  [PASS] score_as.py: the D3 §3 sketch fixture equals the committed .hex/.mif
  iverilog -Wall: 11 '@* sensitive to all words' notes, 0 other lines
  [PASS] wpms_formation.v + wpms_formation_tb.v compile clean
  ORACLE: max |err| over sweep = 7.39e-09 at x=+0.40 (Q4.28 LSB = 3.73e-09)
    group      cases   pass   instr err-cases  first-error codes (expected = observed)
    packet        60     60   13100         0
    hk           300    300     397        73  EW5 73
    fwd          120    120    3645         0
    exp           21     21     567         0
    neg           15     15     151        12  E4 4, EW2 1, EW3 1, EW4 3, EW5 2, EW6 1
    e4           377    377    2646       376  E4 376
    prefetch      14     14      14         8  EW2 8
    timing         7      7      45         1  EW3 1
    random      3000   3000   84954       450  E5 125, E8 75, EW3 95, EW4 117, EW5 2, EW6 36
    total       3914   3914  105519       920
  cosim_l2: PASS — 3914/3914 cases bit-identical to the model
  [PASS] exp_maclaurin_w on the hardware: max |err| = 7.39e-09 (the oracle's figure)
  [PASS] negative cases N1..N13 (N12 three times) raise their codes on the hardware
  cosim_mutants: 20/20 mutants killed
  score_rt: PASS — the Core decodes the assembled words as encoded (observations above are discrepancies, filed, not failures)
  ESTIMATE (Yosys 0.69, synth_intel_alm cyclonev + abc -lut 6): $lut 4611; MISTRAL_MUL18X18 2; MISTRAL_MUL27X27 2; MISTRAL_ALUT_ARITH 931; MISTRAL_FF 1203; MISTRAL_MLAB 1568;
run_phase2: ALL PHASE 2 CHECKS PASSED
```

The golden models' own figures, re-run: `pfasm_tools_w.py exp_maclaurin_w.pfasm` → 7.39e-09 (ORACLE, in the log above); `negative_tests.py` → 13/13 (ORACLE). / 黄金モデル自身の数値も再実行した。

## 3. Results, with evidence classes / 結果と証拠クラス

### 3.1 How the hardware meets the Core / Core との出会い方

- **The issue arrives late in the clock.** The Core reads its instruction memory on the falling edge, so `ext_op_*` is valid only in the second half of the clock its Global executes. The Formation therefore **registers the issue** (stage I) with the taps and the sequencer context, and **executes it in the next clock** (stage X), in order, one per clock. Every instruction sees the one before it (IF-2); K, I, SN, SSS are the values of the issue clock (F-F10). `ext_op_ready` is 1: every issue is accepted (IF-1). Mutant M10 (K read at execute) is caught — the alignment is tested, not assumed.
- **BCP is one issue.** Architecturally it completes in its X clock: the copied bits, SWEEP.a, the EW5 checks on the **post-copy** N. The physical copy runs in the background, one block per clock (slot-major: one clock copies all sixteen slots of a block). Until a slot has landed, store reads **forward** it from the inbox; a datapath write to a pending slot **cancels** its copy (the program's write wins, as in the model's order); the copy **pauses** in any clock the datapath writes the store. `inbox_taken` rises at the edge where the last slot lands.
- **Errors halt at the first one.** The violating instruction commits nothing; `error_flag`, `error_code[4:0]` (E4 = 4, E5 = 5, E8 = 8, EW2…EW6 = 18…22), `error_sn` hold; `insert_req` asks the Core for an insertion at `TRAP_ADDR` (SD-06, §6).
- **The strobe comes after an instruction in X.** If the sequencer's strobe falls in the clock an instruction executes, the instruction completes first (the model's order); for a BCP that means its flags restart with the strobe while its copy still lands (trace T5).

- **命令は Core のクロック後半で届く。** そこで Formation は発行をタップ類とともに一段レジスタし（I 段）、次のクロックで実行する（X 段）。1クロック1命令、順序どおり。K/I/SN/SSS は発行クロックの値（F-F10）。変異体 M10 で整列を検証。
- **BCP は1発行。** X クロックで構造上完了し（copied ビット、SWEEP.a、コピー後 N での EW5）、物理コピーは背後で1クロック1ブロック。着地前の読み出しは inbox から転送、ペンディング中のスロットへの書き込みはそのコピーを取り消し、データパスがストアに書くクロックはコピーが休む。
- **最初のエラーで停止。** 違反命令は何も書かない。挿入バスで Core に知らせる（SD-06）。
- **ストローブは X 段の命令の後。** 同一クロックなら命令が先（モデルの順序）。

### 3.2 The per-instruction clock table actually built / 実装したクロック表

Evidence class: RTL-SIM (traces T1–T5, `observation.md` §3.3). t = the Core clock in which the Global executes (the issue clock). This table replaces the model's assumption of "one clock per instruction, BCP 1 + blocks + item".

| Instruction | Issue | Executes (X) | Result visible to | Background after X | Model counts |
|---|---|---|---|---|---|
| LDA STA ADD SUB SWP SFT SAD LDM STM WLV WJV WSH STP | t | t + 1 | the next instruction (issued t + 1, X t + 2) | — | 1 |
| MUL, MAC (one 32 × 32 multiplier, realign by SHV, E8) | t | t + 1 | the next instruction | — | 1 |
| BCP, B taken blocks (0 … 8), with or without a sweep item | t | t + 1: copied, SWEEP.a, EW5 on the post-copy N | the next instruction sees the whole copy (forwarding) | the copy lands at t + 2 … t + 1 + B, one more clock per datapath store write meanwhile; `bcp_busy` for those clocks; `inbox_taken` high from **t + 2 + B** (measured: B = 0 → t + 2, B = 1 → t + 3, B = 8 → **t + 10**) | 1 + B + (item ? 1 : 0) ≤ 10 |
| any instruction that errors | t | t + 1: flag, code, SN; nothing committed | — | `insert_req` from t + 2 until acknowledged; halted until reset | — |
| prefetch (sequencer port, not an instruction) | — | N and the bundle combinational in the request clock; EW2 at its edge | — | must not overlap `bcp_busy` (asserted in simulation) | T_pf = 1 |

*Note 2026-10-03 (SD-22 step 2, Formation RH006).* An E8 of MUL or MAC, and a prefetch's EW2 met in a MUL's or MAC's X clock, are now raised one clock later, with the same code and SN: flag, code and SN in t + 2, `insert_req` from t + 3. Accm holds the product in t + 2 only, and the instruction then in X is squashed. Every other row is unchanged (`phase6_silicon.md` §11.3). / *2026-10-03 追記（SD-22 段階 2）。* MUL/MAC の E8 と、その X クロックに重なったプリフェッチの EW2 は、同じコードと SN のまま 1 クロック遅れて上がる（t + 2、`insert_req` は t + 3 から）。ほかの行は変わらない。

Consequences, by reading (Phase 3 measures them with the Core): a 25-instruction window occupies the Formation for 26 clocks, the last STM landing one clock after its issue — while the Core executes Prog End, far from the next latch; the housekeeping Stay (T_HK = 13 from Stay Set) holds BCP at Stay Set + 1, its full copy landing by Stay Set + 10, `inbox_taken` from Stay Set + 11, the first-bundle prefetch at Stay Set + 11 — inside T_HK with one clock to spare. / 帰結（読解、Phase 3 で Core と実測）: 25 命令の窓は Formation を 26 クロック占め、最後の STM は発行の1クロック後（Core は Prog End 中）。HK Stay（Stay Set から 13）では BCP が Stay Set + 1、全コピー着地が + 10、`inbox_taken` と最初のプリフェッチが + 11 で、T_HK に1クロック余る。

### 3.3 Cosimulation / 協調シミュレーション

RTL-SIM. 3,914 cases, 105,519 issued instructions, **all bit-identical** (group table in §2 and `observation.md` §3.1). The comparison covers Accm, Temp, ADRS, SHV, SWEEP.a, copied / take / sweep-copied, `inbox_taken`, LoopVal, JumpVal, error flag / code / index / SN, `insert_req`, the 128 store words, and the prefetch port's nine words at every prefetch. Every contract mnemonic was issued thousands of times; 920 cases end in an error, covering every code the hardware raises (E4, E5, E8, EW2–EW6).

- `wpms_packet` in packet windows: 60 cases, 524 windows, all eight `cur` blocks (brief: "several `cur`").
- `wpms_housekeeping` in HK: 300 random take-sets (presets and random 17-bit masks, RT.OUT, armed / not armed) with valid, over-long (P > 8), repeating, over-NMAX items and the block-only backstop; 73 end in EW5.
- `exp_maclaurin_w`: **max |err| = 7.39e-09 at x = +0.40**, equal to the oracle.
- Negative cases: all 13 raise their codes on the hardware (N12, the sensitivity case, three times: the mutant window matches the mutant model and differs from the correct window at PH0).
- 3,000 random contract sequences (1–60 instructions; 1–3 windows of either phase; GOs and strobes between them; idle gaps; K/I/SN/SSS changed per instruction; BCP mid-program followed by traffic to pending slots).

### 3.4 Does the test bite? / 試験は噛むか

RTL-SIM. **20 of 20** single defects are caught (`observation.md` §3.4), among them: no forwarding (M1), no cancel (M2), ADD saturating (M3), strobe order (M4), must-be-zero not enforced (M5), CUR on the wrong block (M6), MAC logical shift (M7), bundle order (M8), EW2 off by one (M9), tap alignment (M10), a violator that still writes (M11), pre-copy N in EW5 (M12), EW6/E5 priority (M13), early `inbox_taken` (M14), a copy that does not pause (M15), no E8 on SFT (M17), no backstop (M19), repeated block accepted (M20).

### 3.5 Score assembler and its round trip / 楽譜アセンブラと往復

RTL-SIM. The fixture (D3 §3, R1, literal) assembles to 240 words + a trap word; on the Core copy **every external issue carries exactly the assembled word**, the 25 window words issue in order, and the housekeeping Stay lasts T_HK = 13. The Core does with the literal sketch what SD-05 predicted by reading — (a) the second empty sweep waits in S_PUSH; (b) with MORE true the packet period doubles (64 = 2 × 32) — and one thing nobody had written down: **the NONEMPTY Branch reads the lane of the word before it** (SD-14).

## 4. Deviations from the golden models / 黄金モデルからの逸脱

**None.** Every compared value equals the model's, under the one rule the brief implies: the model accumulates errors and continues, the hardware halts at the first (the expected scene is the model's state before the erroring instruction). Two things the model does not hold are checked against the texts instead, and stated as such: **LoopVal / JumpVal** (Map v0.3 §3: WLV / WJV ← Accm[11:0]; the model's WLV/WJV are no-ops) and **encodings with no `.pfasm` form** (E4 by the must-be-zero rule of `decode_map.json`; the model has no encoding level). Where the model and the texts differ — **E8 for SFT** — the hardware follows the model and the difference is filed (SD-13).

**逸脱なし。** 比較した値はすべてモデルと一致（モデルはエラー後も続行、ハードウェアは最初で停止という規則のもと）。モデルが持たない LoopVal/JumpVal と「.pfasm に形のない符号」は文書（Map §3、must-be-zero 規則）に照らした。モデルと文書が食い違う SFT の E8 はモデルに従い、SD-13 に記録した。

**Choices made with the brief's defaults / 指示書の既定で決めたこと** (the questions of Phases 0–1 had no answer yet):

| Item | Choice | Where |
|---|---|---|
| E1, E2 | validator-only (the bus carries no band) | SD-01, SD-02 |
| SSS (source 6) | input `tap_sss`, driven in Phase 3 by the L2 top with the window label it latches at Stay Set | SD-03 |
| Error HALT into the Core | insertion bus to `TRAP_ADDR` (parameter, default 0xFFF); `score_as.py` places a foreground Prog End there (C3-F23 → C3-F24) | SD-06 |
| Width of I | 16 bits, zero-extended | SD-07 |
| Encoding | sub-op D8–D11, register ID D12–D15, immediate D16–D31: LDA #imm signed 16-bit, SAD 9-bit literal (D25–D31 must be 0), SFT signed 16-bit count | `decode_map.md` |
| Store organization | slot-major, as the brief recommends: a bundle read and a block copy each take one clock — D3 §9's T_HK and NMAX stand | `wpms_formation.v` |
| EW5 | one sum unit over (item if taken, else SWEEP.a): the model's two checks raise EW5 in exactly the same cases (M12, M19, M20 guard it) | `wpms_formation.v` |

## 5. Discrepancies filed / 記録した食い違い

| ID | In one line | Class · state |
|---|---|---|
| **SD-13** (new) | Register W §4 / W-F30 / Map §8 say E8 is "MUL/MAC only"; the golden model also raises E8 for a left SFT that leaves 32 bits (34 of the 75 random E8 endings). Hardware follows the model. Ruling asked: what "only" excludes | ORACLE + RTL-SIM · open |
| **SD-14** (new) | D3 §4 selects the Condition lane by "the word being executed"; the Core's timing-signal bus is registered, so a foreground Branch is decided on the lane of the word **before** it. The literal sketch plays every sweep empty (RT-2). Phase 3 remedy proposed: the lane's CSEL on the preceding word (T_wake 3 ≤ 4), or lane decode from `state_number` | RTL-SIM · open |
| SD-05 (updated) | Both consequences reproduced: the second empty sweep waits in S_PUSH (RT-1); MORE true doubles the packet (RT-3) | RTL-SIM · open |
| SD-06 (updated) | Insertion chosen, documented; Core wiring and HALT latency (an insertion inside a Stay window is deferred to timeup, C3-F20) measured in Phase 3 | Reading · Phase 2 choice made |
| SD-03 (updated) | `tap_sss` substitute in place | Reading · substitute in place |

## 6. Questions for the architect / アーキテクトへの質問

1. **SD-13.** Does "E8 — MUL/MAC only" exclude SFT (then SFT left shifts wrap or saturate silently, model and hardware change together), or only ADD/SUB (then the texts read "MUL/MAC/SFT" and nothing changes)? / 「E8 は MUL/MAC のみ」は SFT も除くのか、ADD/SUB だけを除くのか。
2. **SD-14.** For Phase 3, may the score carry the lane's CSEL on the word before a foreground Branch (the SLEEP → NONEMPTY step becomes `NOP CSEL=NONEMPTY` + Branch; T_wake 3, within the bound of 4)? The alternative is a lane decode from `state_number` in the sequencer. / Phase 3 で、前景 Branch の直前の語にレーン選択を載せる方式（T_wake 3）でよいか。
3. **Error HALT latency.** With insertion, the Core halts on the trap word at the next safe point — inside a packet window, at that Stay's timeup (≤ N ≤ 2,048 clocks later). The Formation's own `error_flag` is immediate and can silence L1 at once (Phase 3/4). Acceptable? / 挿入方式では Core の HALT は最大1 Stay 遅れる。Formation の `error_flag` で L1 を即座に黙らせる前提でよいか。
4. **Timing at 100 MHz (Phase 6 risk, by reading).** Three paths are long for one clock: `MUL @PPM` (address decode → bank/forwarding mux → 32 × 32 DSP multiply → 64-bit shift by SHV → overflow → Accm); BCP's EW5 (pending masks → N select → eight-term sum → compare → commit fan-out); and the commit fan-out itself. If Quartus misses 100 MHz, which relief do you prefer: a two-clock X for MUL/MAC/BCP with a rule that the next Formation instruction may not use their result (a validator row), or retiming inside the datapath only? / 100 MHz で長い経路が3本ある（読解）。タイミング未達時の方針を伺いたい。
5. **The Phase 0 questions** that shaped §4's defaults (E1/E2 validator-only; the SSS substitute; the queued-Branch not-taken address, SD-05; the width of I) remain open; Phase 3 needs SD-05 and SD-14 most. / Phase 0 の問いは未決。Phase 3 には SD-05 と SD-14 が最も要る。

## 7. Resource numbers / 資源数

**ESTIMATE** (not RTL-SIM, not SILICON): Yosys 0.69 (`yowasp-yosys`), `synth_intel_alm -family cyclonev`, LUT mapping by `abc -lut 6` (ABC9 does not run in the WebAssembly build); no Quartus in this container.

| Resource | Yosys count | Reading |
|---|---|---|
| LUTs (≤ 6 inputs) | 4,611 | about half is the EW5 check (eight N at once: an 8 × 32 N register file in store and inbox, 8:1 selects, an eight-term sum) — measured by removing it: −2,800 LUTs before the single-sum change, which alone saved 1,072 |
| Arithmetic ALUTs | 931 | carry chains: sums, STP bounds, ADD/SUB, ADRS |
| Flip-flops | 1,203 | registers, the issue stage, N register files (512), masks, error state |
| MLAB bit-cells (32 × 1) | 1,568 | = 49 × 32: the 8 × 32 banks of store and inbox, per read port (datapath, prefetch, copy); asynchronous reads keep them out of M10K |
| DSP | 2 × MUL27X27 + 2 × MUL18X18 | one 32 × 32 signed multiplier shared by MUL and MAC ≈ 3 Cyclone V DSP blocks |

Rough translation to the DE10-nano's 5CSEBA6: ≈ 3,200–4,000 ALMs of logic plus ≈ 79 MLAB LABs (≈ 790 ALMs) → **≈ 4–5 k of 41,910 ALMs (≈ 10 %)**, ≈ 3 of 112 DSP blocks, no M10K. Phase 6 replaces all of this with the Quartus ledger in the Core's format. / 概算で ALM の約 10 %、DSP 3 ブロック、M10K なし。Phase 6 で Quartus の数に置き換える。

---

*Stopped at the end of Phase 2, as instructed. / 指示どおり Phase 2 の終わりで停止する。*
