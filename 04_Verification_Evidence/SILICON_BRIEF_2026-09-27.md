# PTSG-WPMS-Formation — Silicon Brief for Claude Code
# PTSG-WPMS-Formation — Claude Code へのシリコン化指示書

*2026-09-27 · issued by the profile's amanuensis for the architect · CC0 · Layer 4 plan (not evidence).*

*要旨（アーキテクト向け）: 四つのリポジトリを並べた作業空間で、Claude Code に (1) 凍結中の Core を「写し」に対して RH029/030 のヘッダ修正と stay_value（RH031 仮）を当てて検証し、(2) L2 Formation のデータパス・ブロック記憶・inbox・別名・STP/BCP を、当方のオラクル（`pfasm_tools_w.Machine`）と命令単位で一致させ、(3) 掃引シーケンサと Core を統合して `sweep_sim.py` の参照と掃引単位で一致させ、(4) 顧客第3章・第4章の L1 パイプラインと出力路を顧客オラクルとビット一致で作り、(5) 最小の入力スイッチを付けて、(6) DE10-nano で g・T_wake・N_MIN・BCP 所要を測り、音を出す——という順序で進めさせる。台帳・マップ・成果物 2/3 が法、オラクルが黄金モデル、Core の Layer 4 の作法（expected before observed、VCD + observation.md）に従う。*

---

## 0. Mission / 任務

Bring the L2 Formation of Wave-Packet Modulation Synthesis to DE10-nano, on PTSG-Core, and produce **Layer 4 evidence**: the packet gap g, the wake latency T_wake, the shortest packet N_MIN, the housekeeping copy duration, a full-load sweep of 2,048 bins inside 2,083 clocks, every profile error row halting the machine on cue — and sound.

Everything you build already has a **golden model**. Your job is to make hardware agree with it, and to say plainly where it does not.

---

## 1. Workspace / 作業空間

Four repositories side by side (clone all four; do not nest):

```
workspace/
├── PTSG-Core/                        ← the timing core. FROZEN reference RTL at RH030 (never edit in place)
├── PTSG-CPU-Formation/               ← the master data ISA. Layer 1 only (no RTL exists); its Ch.2 §2.9 and Ch.5 govern IDs and lanes
├── PTSG-WPMS-Formation/              ← THIS profile. Layer 1 = law; Layer 3 = golden models; you write Layer 3 hardware and Layer 4 evidence here
└── FPGA_Spectrum_Engine_OpenPrompt/  ← the customer (WPMS). Layer 1 Ch.3–5 = the L1 pipeline, output path, input switch; its oracle = golden model for those
```

**What is law, and in which order** (when two texts disagree, the earlier one on this list wins; file the disagreement — §6 — never resolve it silently):

1. `PTSG-WPMS-Formation/01_Architecture/PTSG_WPMS_Formation_Decision_Register_W_v0_7.md` — every ruling, keyed to master IDs.
2. `L2_Formation_Register_Map_v0_3.md` — registers, instruction rows, the 9-bit address space, write windows, error rows.
3. `Deliverable2_L1_Consumer_Interface_v0_1.md` — the bundle port and the lanes to L1.
4. `Deliverable3_Choreography_v0_1.md` — the sweep, the Core score, Condition lanes, the Stay-value path, the windows, the inbox protocol, budgets.
5. `PTSG-CPU-Formation/01_Architecture/` Ch.2 (register file, ID spaces §2.9), Ch.3 (command × phase table), Ch.4 (memory law — RESTRICTED here for packet blocks), Ch.5 (the nine-lane Core interface).
6. `PTSG-Core/01_Architecture/` Ch.2, Ch.3, Ch.5 and `CHANGES_Layer1_stay-value_2026-09-26.md` (PROVISIONAL), `CHANGES_Layer1_free-running-fruits_RH029-030.md`.
7. `FPGA_Spectrum_Engine_OpenPrompt/01_Architecture/` Ch.3 (L1 engine and L2 binding), Ch.4 (output path), Ch.5 (boundary and address map, **Appendix 5.A** = the consolidated customer requirements).

**Superseded, keep for history only:** anything in the profile describing active/shadow pages, CUR, Mode T, Mode W, per-packet CMT (Register Map v0.2, the 2026-09-07 trace, Hackaday Log #1). If you find yourself implementing a page swap, stop: read the 2026-09-27 trace.

**Where things are Arena** (implementation's choice, to be published): mnemonic-to-bit encodings inside D8–D31 (master Ch.3 CL-5 — "encodings are Implementation Arena"; IDs follow Ch.2 §2.9), the block store organization, the Condition-lane selection mechanism, the bundle port's physical form, port names and widths (master Ch.5: "each implementation publishes its own port map against the nine lanes").

---

## 2. The golden models, and what they are / 黄金モデルとその性格

The profile was verified **by oracle, not by silicon**, at three granularities. Match each one at its own granularity; do not try to make a hardware clock count agree with a model that never claimed one.

| Model | Where | Granularity | What it fixes | What it does *not* fix |
|---|---|---|---|---|
| **Instruction-level machine** `pfasm_tools_w.Machine` | `PTSG-WPMS-Formation/03_Sample_Implementations/tools/pfasm_tools_w.py` | one Formation instruction | architectural state after every instruction: Accm, Temp, ADRS, SHV, the block store, the inbox view, the CUR alias, COMMIT view, STP, BCP (take-set semantics, EW5), every error row EW2–EW6, E4/E5/E8; ADD/SUB wrap; MUL/MAC `>> SHV` with E8 | clock timing of an instruction (it counts one clock per instruction and 1 + one per copied item for BCP — a *reference realization*, slot-parallel) |
| **Sweep-level oracle** `sweep_sim.py` (`Sequencer`, `Reference`) | same directory | one packet, one sweep | what L1 latches at every packet start (the eight-value bundle) for every played block, under random GO traffic; the prefetch discipline (a prefetched bundle must equal the live block at the latch); take-set at the strobe; StayVal per packet; EW2 at prefetch; sweep-clock budget with **nominal** Core clocks (wake 2, 4 control clocks per packet, 3 in housekeeping) | the Core's real clocks (those are what you will measure) |
| **Contract** `isa_table_w.json` ← `isa_fold_w.py` | same directory | rows | which {mode, sub-op}, source IDs and dest IDs exist in this profile; `address_map`, `profile_registers`, `profile_errors`, `constants` | bit positions (Arena — you publish them) |
| **Negative tests** `negative_tests.py` | same directory | rows | every rejection the profile promises (13 cases) | — |
| **Programs** `instruction_lists/*.pfasm` | same directory tree | — | `wpms_packet.pfasm` (25 instructions), `wpms_housekeeping.pfasm` (BCP), `exp_maclaurin_w.pfasm` (27, non-packet window) | the Core score (FG) — Deliverable 3 §3 gives it as a sketch, in two realizations |
| **Customer oracle** `wpms_layer1_oracle.py` | `FPGA_Spectrum_Engine_OpenPrompt/04_Verification/oracle/` | one bin, one packet, one sweep (L1 side) | phase recurrence mod 2³² (`l1_phase`), log-domain amplitude and `exp2_q131`, `gaussian_slots`, `step_toward`, Schroeder/Dirichlet test origin, output-path law (18 checks) | anything on the L2 side |
| **Core testbenches** | `PTSG-Core/03_Sample_Implementations/ptsg_core_verilog/` | clock | `ptsg_core_tb.v` (PASS A..G), `ptsg_core_conformance_tb.v` (PASS T1..T34); `stay_value_reference_sketch.md` §7 lists SV-0..SV-7 for the patched copy | — |

Evidence classes used in this ecosystem: **ORACLE** (Python model), **RTL-SIM** (Icarus/ModelSim), **SILICON** (DE10-nano, SignalTap → VCD). Label every number you report with one of them. Numbers in the profile's documents today are ORACLE unless stated.

---

## 3. Toolchain and conventions / ツールと作法

- **Simulation:** Icarus Verilog `-g2012` (the Core's testbenches run with it; commands in `ptsg_core_verilog/README.md`). Python 3 for cosimulation harnesses; cocotb is welcome if you install it, but a plain Verilog testbench that reads a JSON/hex stimulus and compares against a JSON expectation is enough and easier to review.
- **Synthesis:** Quartus Prime Lite, Cyclone V SoC 5CSEBA6U23I7, DE10-nano. Reuse `PTSG-Core/03_Sample_Implementations/board_harnesses/de10_nano/` (`DE10_Nano_ptsg100_top.v`, `.qsf`, `.sdc`) as the starting top.
- **Instruction memory:** `.hex` (`$readmemh`) for simulation, `.mif` for M10K — see the Core's `examples/`.
- **Evidence discipline (Core Layer 4 README):** *expected before observed*; waveforms are VCD, not screenshots; a VCD without an `observation.md` is meaningless; `ptsg_vcd_decode.py` exists in `PTSG-Core/04_Verification_Evidence/tools/`.
- **Headers:** every RTL file you write carries a revision history in the Core's format (`// 001 date author Add/Mod/Fix : …`). Cite W-IDs and CR-IDs in comments where a line implements a row.
- **Language:** code comments in English; READMEs and reports bilingual (English first, Japanese gloss), like the repositories.
- **Prescaler:** P = 1 for WPMS (`PRESCALE = 1`); the coincident-tick discipline of RH028 applies. Sample period T_min = 2,083 clocks at 100 MHz / 48 kHz.

---

## 4. Phases / 段階

Each phase ends with a report (§7) and stops for the architect's reading before the next begins. Do not skip ahead to "make sound": the profile's promise is *measured, not promised*, and a sound demo without the measurements is a promise.

### Phase 0 — Baseline / 基線

1. Clone the four repositories; record commit hashes.
2. Run and record, unchanged: Core `ptsg_core_tb.v` (A..G) and `ptsg_core_conformance_tb.v` (T1..T34); profile `isa_fold_w.py`, `sweep_sim.py <customer oracle> 20000 2026` (expect 0 mismatches), `negative_tests.py` (13/13), `pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json`; customer `wpms_layer1_oracle.py` (18/18).
3. Read, in this order: Register W v0.7 §2–§4, Register Map v0.3, Deliverable 2, Deliverable 3, the 2026-09-27 trace, master Ch.2 §2.9 and Ch.5, Core Ch.3 §3.2–§3.4b and the stay-value CHANGES, customer Ch.3 and Appendix 5.A.

**Output:** `PTSG-WPMS-Formation/04_Verification_Evidence/reports/phase0_baseline.md`.

### Phase 1 — The Core, patched on a copy / Core の写しへの適用

The frozen `ptsg_core.v` (RH030 as built; the RH029/030 **code** is already in it — only their header entries are pending, see `RH029-030_header_patch.md`) stays untouched. Make a copy at `PTSG-WPMS-Formation/03_Sample_Implementations/hw/core/ptsg_core_rh031p.v` and apply:

1. The header/tag corrections of `RH029-030_header_patch.md` (comments only).
2. The `stay_value` change of `stay_value_reference_sketch.md`, **Form B** (read in the execute clock): one new port `input tri0 [CNT_W-1:0] stay_value`, and the two-line redefinition of `stay_dur` (`stay_dur_lit` + IND-reverse mux). Width `CNT_W` = 12 (the profile's answer to Tie C5-T2: longest Stay 2,048). Never the anti-pattern of sketch §4.
3. A draft header entry per sketch §8, numbered **RH031 (provisional — the Core's office assigns the number at its checkpoint)**.

Then prove it:

- With `stay_value` tied 0: A..G and T1..T34 **bit-identical** to the frozen source (diff the VCDs or the pass logs).
- **SV-0 … SV-7** from sketch §7, written as a new testbench `ptsg_core_sv_tb.v`; SV-4 must *fail* on the anti-pattern and pass on Form B (build the anti-pattern once, in the testbench only, to show the test bites).

**Output:** the patched copy, the SV testbench, `reports/phase1_core.md` with the diff of the copy against the frozen source (it should be a few dozen lines).

### Phase 2 — The L2 Formation datapath / データパス

Build `hw/l2/wpms_formation.v` (plus submodules as you see fit): the Formation side of the master's nine-lane border for this profile.

**Interface to the Core (fixed by the Core RTL):** `ext_op_valid`, `ext_op_subopcode[3:0]` (= mode, D4–D7), `ext_op_sub_operand[7:0]` (D8–D15), `ext_op_data[15:0]` (D16–D31), `ext_op_ready` (captured, not stalled on — IF-1: the Core never waits; accept every issue in its clock). Note: **the Core RTL exports no band signal on this bus** (`in_queued_band` is internal), although master Ch.5 §5.3 says the issue carries {mode, sub-op, operand, band}. Consequence: E2 (Formation instruction in the Q band) cannot be detected by the Formation from the bus alone. File this as a discrepancy (§6) and rely on the validator for E2 for now; do not modify the Core.

**Decode map (Arena — you publish it):** from `isa_table_w.json` (which {mode, sub-op} exist; source IDs 0–7; dest IDs) and master Ch.2 §2.9 (ID spaces), fix the bit positions of sub-op and of the source/dest ID inside D8–D31, and the immediate/literal width that remains (SAD needs a 9-bit literal; LDA #imm as wide as the layout allows; SFT's shift count; STP takes a source like ADD). Write `hw/l2/decode_map.md` **and generate both the RTL decoder table and the assembler from the same JSON** (`hw/tools/decode_map.json`): one source, two consumers. Then `hw/tools/pfasm_as.py` assembles `.pfasm` window programs into Global words, and a small score assembler turns the Deliverable 3 §3 sketch into a Core `.hex`/`.mif` (opcode, operand, D16–D31 timing bits incl. TS_PKT, TS_CSEL).

**Datapath rows (Register Map v0.3 §2–§4, §8):**
- Accm, Temp (32), ADRS (9, SAD/post-increment only — STA→ADRS = E4), SHV (5, WSH).
- Sources IMM/PPM/TEMP/K/I/SN/SSS; the quartet comes from the Core (`stay_counter` = K, `loop_counter` = I, `state_number` = SN; SSS = Stay Start State — check what the Core RTL exports; if SSS is not on a port, note it).
- ADD/SUB wrap (W-F30); MUL/MAC `>> SHV` with E8 on 32-bit overflow; SFT arithmetic.
- **Block store** 8 × 16 × 32: recommended **slot-major** (sixteen 8-deep memories, one per slot) so a bundle read and a BCP block copy each take one clock; if you choose word-serial, say so and recompute T_HK and NMAX (Deliverable 3 §9). Datapath write only in HK (EW4).
- **Inbox** 8 × 16 × 32 + `RTOUT[b]` + `COMMIT[b]` + staged sweep word, written by the switch side (Phase 5; in Phase 2, by the testbench), read-only to the datapath (EW3). L2 view: `+0xE` = staged RT.OUT, `+0xD` reads 0.
- **CUR alias** 0x100–0x10F → block `cur` given by the sequencer; readable in a packet window, writable only there (EW4).
- COMMIT view 0x110–0x117, staged sweep 0x118, SWEEP.a 0x119, status 0x11A; else E5.
- **STP** (4·0): `Accm ← Accm + clamp(src − Accm, −Temp, +Temp)`, 33-bit difference, EW6 on Temp < 0.
- **BCP** (4·1): masked copy of the take-set, RT.OUT via mask bit 16 → `+0xE`, sweep item → SWEEP.a with EW5 (P > 8, duplicate block, Σ N > NMAX), re-check Σ N of the sweep in effect, then `inbox_taken`; legal only in HK (EW4). Multi-clock: it must complete before the HK Stay's timeup (Core C3 §3.5: M ≥ i + L_ext).
- Errors: an `error_flag` and an `error_code` (E4, E5, E8, EW2–EW6) — halt the datapath and drive the Core's insertion bus or `condition` per the Core's Error-HALT convention (C3-F24) — pick one, document it.
- E4 in hardware for PSH, POP, CMT, RTW, WSV and any unlisted {mode, sub-op}.

**Cosimulation (the acceptance):** a testbench that issues one instruction per clock exactly as the Core does, running each `.pfasm` program assembled by `pfasm_as.py`, with `pfasm_tools_w.Machine` run on the same program and initial state; compare Accm, Temp, ADRS, SHV, the whole block store and every error after each program. Cover `wpms_packet.pfasm` in a packet window (phase = PKT, several `cur`), `wpms_housekeeping.pfasm` in HK with random take-sets, `exp_maclaurin_w.pfasm` in HK (max error 7.39e-09 as in the oracle), and all 13 negative cases (each must raise its code). Add random instruction sequences from the contract (a few thousand) and compare too.

**Output:** RTL, `decode_map.md/.json`, assemblers, testbenches, `reports/phase2_datapath.md` (include the per-instruction clock table you actually built — that table replaces the model's assumption).

### Phase 3 — Sequencer and integration / シーケンサと統合

Build `hw/l2/wpms_sequencer.v` and `hw/l2/wpms_l2_top.v` = Core (RH031p) + Formation + sequencer, per Deliverable 3:

- **SWEEP.a**, packet index q, `cur = order[q]`, `P`; lanes STROBE / NONEMPTY / MORE onto the Core's `condition` input, selected by `timing_signals` bits **TS_CSEL[1:0]**; **TS_PKT** → `bin_valid`, `packet_start = StaySet ∧ TS_PKT` (detect Stay Set from the Core: `state_number` transitions, or the Core's Stay Set execute — the Core exports `stay_counter`; K returns to 0 at Stay Set). The Core RTL resolves C3-T1 as (A): the Stay word's D16–D31 is held during the wait — Deliverable 2 already writes TS bits in both the Stay Set and Stay words.
- **Stay value:** StayVal.s ← N of the next packet's block at prefetch (EW2 if outside [32, 2048]); StayVal.p ← (TS_PKT ? StayVal.s : 0) at every Stay Set; StayVal.p drives the Core's `stay_value` pin. Verify against Core C4-F16: the value is read at the Stay instruction's execute clock, after the window.
- **Bundle port:** prefetch of `order[q+1]` during packet q (or after HK for the first packet); presentation = L1's latch at `packet_start`. Assert in simulation that the staged bundle equals the live block at the latch (the sweep oracle's check).
- **Take-set / inbox-taken:** latched at the strobe; raised by BCP; cleared at the next strobe.
- **The Core score in both realizations** (W-R17): **R2 preferred** — one packet body re-entered at Stay-timeup while MORE holds; **R1** — eight unrolled positions with a forward queued transfer at each timeup, for bring-up. For R2, investigate what the Core RTL offers for a data-driven, gap-free re-entry at timeup: a queued Loop with Base Set whose loop target comes from the indirect-read bus (`indirect_purpose` 01) supplied by the sequencer with P — check *when* the Core performs that read (if it is at timeup with a stall, it costs clocks); or another Core primitive. **If no gap-free R2 exists in the Core as built, do not modify the Core: report the options (Hook A of the 2026-09-27 trace) and proceed with R1.**
- **Sweep-level cosimulation:** add a `--dump` mode to `sweep_sim.py` that writes the GO stimulus (inbox contents, masks, RT.OUT, sweep words, at which sample each GO is armed) and the expected bundle at every packet start (plus N per packet) to JSON; drive the RTL from it; compare every latched bundle, `K` sequence and `bin_valid`. Run ≥ 10,000 samples (a few seeds), including full-load sweeps.
- **Measure in RTL-SIM** and report as predictions: g between packet Stays, T_wake (strobe → first packet_start), the packet window's clocks (→ N_MIN), BCP duration, the worst full-load sweep in clocks. Compare with Deliverable 3 §9 and the sweep oracle's nominals (2/4/3); where they differ, the RTL numbers replace the nominals in the report (not in the Layer 1 documents — those change only by ruling).

**Output:** RTL, score `.hex` for R1 and R2 (if achievable), testbenches, `reports/phase3_integration.md`.

### Phase 4 — L1 pipeline and output path (customer Ch.3, Ch.4) / L1 と出力路

Build `hw/l1/` from the customer's Layer 1, with the customer's oracle as golden model, bit-exact:

- Bundle latch at `packet_start` (Deliverable 2 §2–§3); phase recurrence by forward differences mod 2³² (`l1_phase`); log-domain amplitude (`l1_amplitude`: LS0/LAD1/LAD2/LP alignment to Q.30, `exp2_q131` with its table and polynomial, clamps); products, accumulators closed on the strobe; master gain in the log domain; RT.OUT routing; the 48 kHz strobe (2,083 clocks); the output stage of Ch.4 for DE10-nano (audio out as the chapter specifies).
- Cosimulate against the oracle's functions bin by bin for random bundles; then a full sweep against `sweep_sim` bundles + oracle L1; then the test origin of Ch.5 §5.8 (ROM port) end to end, checking the customer's E2E numbers (e.g., σ = 71 → 927 audible bins).

**Output:** RTL, testbenches, `reports/phase4_l1.md` with bit-exactness evidence and the DSP/M10K count.

### Phase 5 — Minimal input switch (customer Ch.5) / 最小の入力スイッチ

Only what the demo needs: the ROM port (test origin at reset, CR5-R1), and one host path (HPS bridge or UART — your choice, documented) that can write inbox slots, masks, RT.OUT, the sweep word, arm, GO, and read APPLIED. Stage-arm-go semantics per Ch.5 §5.4; reject Σ N > NMAX and duplicate blocks when computable (PR-1, PR-2) — the profile's EW5/EW2 remain as backstops. A tiny host script (Python) to drive a few musical GOs for the video is welcome but is **outside WPMS** (it stands in for the L4 controller); mark it so.

**Output:** RTL, host script, `reports/phase5_switch.md`.

### Phase 6 — DE10-nano and Layer 4 evidence / 実機と第4層

Quartus project from the Core's harness; 100 MHz; timing closure; SignalTap captures exported to VCD with `observation.md` for each of:

| Evidence item | Expected (write it *before* capturing) |
|---|---|
| g between consecutive packet Stays | 0 (Core commitment) |
| T_wake: strobe → first `packet_start` | ≤ 4 (nominal 2) |
| Packet window clocks → N_MIN | 25 + Core clocks; profile constant 32 must hold |
| BCP duration, full take-set | ≤ 10 (slot-parallel) |
| Full-load sweep (Σ N = 2,048) | fits in 2,083 with the housekeeping window |
| Each EW2–EW6 injected | `error_flag` with the right code; L1 silent |
| Bundle at packet_start vs prediction | equal (a few packets decoded from the VCD) |
| First sound: test origin, then one GO | audible; spectrum as the customer's oracle predicts |

Plus the **resource ledger** (ALMs, M10K, DSP per entity) in the Core's format, and `04_Verification_Evidence/README.md` updated with the entries.

---

## 5. Things you must not do / してはならないこと

- Do not edit the frozen `PTSG-Core/…/ptsg_core.v`, any Layer 1 document, or the profile's Layer 3 golden models to make hardware pass. If a model is wrong, say so in the report with a reproduction; the architect rules.
- Do not add an instruction, a register, a lane or a memory region that is not in Register Map v0.3. Need one? File it (§6) and stop that thread.
- Do not implement a page swap, a shadow page, CUR, or a per-packet commit.
- Do not let the Formation stall the Core (IF-1) or drive `stay_value` non-zero during the housekeeping Stay (its literal must apply).
- Do not report a number without the test that produced it and its evidence class.

---

## 6. Discrepancies / 食い違い

Keep `PTSG-WPMS-Formation/04_Verification_Evidence/reports/discrepancies.md`: one row per item — what the texts say, what you found, a proposed disposition, **and no fix applied**. Known already: (1) the Core RTL's ext_op bus carries no band (master Ch.5 §5.3 vs `ptsg_core.v`); (2) whether SSS (Stay Start State) is exported by the Core RTL as a readable source; (3) whether a gap-free data-driven re-entry (R2) exists in the Core as built.

---

## 7. Reports / 報告

`reports/phaseN_<name>.md`, bilingual, in this order: what was built (files) · commands run and their last lines · evidence class per number · deviations from the golden models (with reproductions) · discrepancies filed · questions for the architect · resource numbers (from Phase 2 on). Commit messages cite W-IDs / CR-IDs. Stop at the end of each phase.

---

## 8. The one-paragraph model of the machine (keep it in mind) / 機械の一段落モデル

A 48 kHz strobe wakes the Core from a Branch-0 sleep. If the sweep word says P > 0, the Core plays P packet Stays back to back, each N clocks long, the length handed in on `stay_value` by the sequencer one packet ahead. At each packet's Stay Set, L1 latches an eight-value bundle of the block that packet plays, and the window program (25 instructions, through the CUR alias) advances that block's phases and glides its level for the next sample — the block's next latch is a whole sweep away, so the write can never be seen half-done. After the last packet, one housekeeping Stay runs BCP, which lands the GO's items taken at the strobe into every armed block and the new sweep word, raises inbox-taken, and the sequencer prefetches the next sweep's first bundle. The Core goes back to sleep with clocks to spare — 19 of 2,083 at full load, by the oracle — and the measurements you make decide whether silicon agrees.

---

*End of brief.*
