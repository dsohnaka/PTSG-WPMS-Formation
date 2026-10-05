# PTSG-WPMS-Formation — Decision Register W
# PTSG-WPMS-Formation — 決定台帳 W

*v0.8 · WPMS-Formation amanuensis · 2026-10-05 · CC0 · Layer 1.*
*Status: **as-built alignment.** Rulings through 2026-10-04 recorded; SILICON evidence of 2026-10-03/04 absorbed; the consequences of discrepancies SD-01 … SD-23 (Layer 4 ledger) folded into the rows. Companion documents: Register Map v0.4, Deliverable 2 v0.2, Deliverable 3 v0.2; Verification Scenario V-K v0.1 (Kuramoto Mode); Layer 2 trace 2026-09-27.*

*v0.8 · as-built 整合版。2026-10-04 までの裁定、実機の証拠、食い違い SD-01〜SD-23 の帰結を行に取り込む。*

---

## Changelog v0.7 → v0.8

- **SILICON.** DE10-nano, Cyclone V 5CSEBA6U23I7, the 50 MHz revision (clk_sys 30 % high), third fit 2026-10-04: every clock meets (clk_sys setup +0.978 ns, TNS 0). First sound 2026-10-03; the test origin's Dirichlet kernel observed with its predicted period (255.65 s). Captures C1–C5 on 2026-10-04: **every value measured on the board equals the RTL-SIM value written before the capture** — g = 0, T_wake 2, packet floor 30, BCP 10, full-load sweep 1,023 of 1,041 clocks, 45 bundles and 12 banks equal, EW2–EW6 each once with the pipeline silent and the Core halted after.
- **Rulings 2026-09-28 … 10-04** recorded from the Layer 4 ledger (§2.1).
- **SD-01 … SD-23 absorbed** (§3, §4, §8): I is 16 bits; E8 covers SFT as well; the Condition lane's select is taken from the word before a foreground Branch; the L1 face is one clock after Stay Set, uniformly; the take-set is the set *handed over* by a GO; the dispatch form is the standard score and a data-driven gap-free R2 does not exist in the Core as built; the error strobe rides the Core's insertion port; the issue port carries no band and SSS is substituted by the sequencer.
- **SD-08 fixed**: the stray "open" table fragment of v0.7 §2.2 is gone.
- **Architect's direction of 2026-10-05** entered as proposed rows for ruling: half-rate Stay (W-F37), packet output table (W-F38), PTSG at 50 MHz with L1 at 100 MHz. **V-K (Kuramoto Mode)** rows W-F31 … W-F36 referenced for ruling (W-R20).
- Public wording: "2,048 per module" is the 100 MHz-L1 number; the first silicon plays 1,008 at 50 MHz.

**要旨:** 実機で測った数（T_wake 2、床 30、BCP 10、満載 1,023/1,041）と、09-28〜10-04 の裁定、SD-01〜SD-23 の帰結を行へ。10-05 の方針二件（半速 Stay、パケット出力表）と V-K は裁定待ちの提案行として記帳。

---

## 0. Pins / 釘付け

| Repository | Pinned at | Content relied on |
|---|---|---|
| PTSG-CPU-Formation (master) | `ad43cc2` | Layer 1 Ch.1–5; `isa_table.json` |
| PTSG-Core | `1b58ebc` (frozen `ptsg_core.v` RH030 as built; RH031 provisional applied on the profile's copy `ptsg_core_rh031p.v`) | Ch.2, Ch.3, Ch.5; CHANGES stay-value 2026-09-26; `stay_value_reference_sketch.md` |
| FPGA_Spectrum_Engine_OpenPrompt (customer) | `891fce6` | Layer 1 Ch.1–5, Appendix 5.A/5.B; oracle |
| PTSG-WPMS-Formation (this repository) | `dea164f` | Layer 3 `hw/`, Layer 4 reports, ledger SD-01 … SD-23 |

---

## 1. Conventions / 記帳規約

As v0.7. Added: **SD-** = a Layer 4 discrepancy row (`04_Verification_Evidence/reports/discrepancies.md`); **evidence class** ORACLE / RTL-SIM / STA / SILICON on every number.

---

## 2. Rulings / 裁定

### 2.1 Ruled (cumulative; 2026-09-28 onward from the Layer 4 ledger) / 裁定済み

| ID / SD | Ruling | Date |
|---|---|---|
| W-R0 … W-R17 | as v0.7 | 09-01 … 09-27 |
| — | 50 MHz if 100 MHz is at all difficult; no pipelining of long paths before correct operation | 09-28 |
| SD-06 | the Formation's error strobe uses the Core's insertion port (`insert_req` → TRAP: a foreground Prog End halts, C3-F24) | 09-28 |
| SD-13 | E8 reading (a): ADD/SUB wrap; MUL, MAC **and SFT** keep the master's never-lost rule | 09-28 |
| SD-14 | lane select (a): the Condition lane's CSEL is carried by the word **before** a foreground Branch | 09-28 |
| — | NMAX = **1,008** at 50 MHz (T_min 1,041/1,042) | 09-29 |
| SD-04/05 | the **dispatch form** (R1-D) is the standard score; no INT-R1 request to the Core for now; LoopVal stays on the indirect-read bus | 09-29 |
| SD-15 | the Formation withdraws `insert_req` in the clock `insert_ack` is high; bug report to the Core's office | 09-29 |
| SD-16 | the published L1 sine realization is the official specification (customer note prepared) | 09-30 |
| SD-17 | (a): the 50 MHz ROM image's test origin has N = 1,008 | 09-30 |
| SD-19 | host path = **ISSP over JTAG** carrying port-0 transactions; overrides customer C5-D8 here (customer note prepared) | 09-30 / 10-01 |
| SD-20 | port 3 (the ROM) is exempt from ownership for its own list | 10-01 |
| SD-21 | Formation RH004: a GO hands its whole set over in one clock; the take-set is the handed-over set | 10-01 |
| SD-22 | SD-22 step 1 then step 2 (write-back clock for Accm/Temp/store, E8 decided next clock) — the 09-28 no-pipelining rule lifted for step 2 | 10-03 |
| SD-23 | clk_sys 30 % high in the 50 MHz revision (imem half-cycle read gets 14 ns); no SDC relaxation | 10-04 |

### 2.2 Open / 裁定待ち

| ID | Question | Amanuensis's proposal |
|---|---|---|
| **W-R18** | **Half-rate Stay** (W-F37): PTSG at 50 MHz, L1 at 100 MHz, a "bit −1" under K in the consumer interface; N in bins stays customer-visible; EW2 widened to "N odd, or N < 64" | adopt as stated by the architect 2026-10-05; the margin at NMAX 2,048 is 2 L2 clocks on 1,041-clock sweeps — housekeeping must not grow |
| **W-R19** | **Packet output table** (W-F38): per-packet sums → shallow FIFO → 2-bank table (1 write, 5 read ports by replication), readable by every L2 Formation as a source region; **delay two samples, uniform**; unplayed packets read 0 with a not-played bit | adopt; the only page swap that is correct, because every entry is rewritten every sample |
| **W-R20** | **V-K rows** W-F31 … W-F36 (Kuramoto Mode, separate document) | adopt as the next verification scenario; per-packet K through W-F38 |
| **W-R21** | SD-02: does C3-F23 (FG-Global exclusion) cover external modes? | Core-office item; until then E1 for external Globals is validator-only, like E2 |
| **W-R22** | SD-07: Map's quartet width for I | 16 bits (Core `LOOP_W`), read zero-extended — absorbed in Map v0.4 §1 pending the ruling |

---

## 3. The register proper / 台帳本体

Status: **F** Fixed · **P** Proposed · **T** Tracking · **R** Resolved. Rows unchanged since v0.7 are listed by ID only.

### 3.1 Master decisions and ties

| W-ID | Master ID | Disposition | Status | As built (SD) |
|---|---|---|---|---|
| W-F1, W-F2, W-F3, W-F5, W-F6, W-F7, W-F8, W-F10 | — | as v0.7 | — | — |
| W-F4 | F-F5·F-F10 | INHERIT | P | **I is 16 bits** (SD-07); K = k holds on silicon (C1–C3) |
| W-F9 | F-F14 | R | R | — |
| W-T1, W-T3, W-T4, W-T5 | — | as v0.7 | — | W-T3 kept: the dispatch form uses only BG computed dispatch (WJV) |
| W-T2 | F-T1 | R — N_MIN = 32 | R | **floor 30 measured** (RTL-SIM and SILICON): a windowed Stay needs one S_WAIT clock (SD-12); 2 clocks of margin remain |

### 3.2 Treaty, common law, memory law

| W-ID | Master ID | Disposition | Status | As built (SD) |
|---|---|---|---|---|
| W-F11 | IF-1…5; nine lanes | INHERIT | P | the Core's issue port carries **no band** (SD-01: E2 validator-only); an external Global in FG is not halted by the Core as built (SD-02 → W-R21); the error strobe rides the **insertion port** (SD-06); SSS is **substituted** by the sequencer's latch of the Stay Set address (SD-03) |
| W-F12 | INT-R1…R4 | TRACK | T | INT-R1 not requested (dispatch form); INT-R2 realized by insertion; INT-R4 open with the Core |
| W-F13, W-F14, W-F15 | — | as v0.7 | — | — |
| W-F16 | E1…E8 | INHERIT + profile rows | F | §4: **E8 includes SFT** (SD-13); EW2–EW6 each observed once on silicon |

### 3.3 Extensions / 拡張

| W-ID | Extension | Status | As built |
|---|---|---|---|
| W-F17 | L1 consumer interface | P (v0.2 issued) | the L1 face is **one clock after Stay Set, uniformly** (SD-11); T_wake 2 (SILICON) |
| W-F18 | Block format | P (Map v0.4) | unchanged; customer presets need bit 16 (SD-09) |
| W-F19 | Condition lanes | F 09-27 | CSEL one word before a foreground Branch (SD-14 a) |
| W-F20 | Choreography | P (v0.2 issued) | dispatch form standard (SD-04/05); R2 unavailable as built |
| W-F21 | integer formats | F | — |
| W-F22 | Stay-value path | F | `stay_value` RH031p on the Core copy; StayVal.p read at the Stay's execute clock; 0 at HK observed on every Stay (RTL-SIM 164,321 Stays) |
| W-F23 | SHV / WSH | F | — |
| W-F24 | single store, bundles, write windows | F | 45 bundles / 12 banks equal on silicon |
| W-F25 | OMIT CMT, RTW | F | — |
| W-F26 | STP | F | C4: EW6 once; glide bit-exact (Phase 4) |
| W-F27 | BCP | F | **10 clocks** full take-set (SILICON); 2 for a small one |
| W-F28 | sweep sequencer; WSV RESTRICTED | F | take-set = the set **handed over** by a GO (SD-21, RH004); SSS substitute (SD-03) |
| W-F29 | log-domain slots | F | bit-exact with the customer's oracle (Phase 4) |
| W-F30 | ADD/SUB wrap; E8 for MUL/MAC/**SFT** | F (amended by SD-13) | — |
| **W-F31 … W-F36** | **Kuramoto Mode** (V-K v0.1): rotor state memory; packet modes in RT.OUT bits 2–15; stateful and view passes; mean-field words; seeding; r² | **P → W-R20** | — |
| **W-F37** | **Half-rate Stay**: L1 at 100 MHz under a 50 MHz L2; bit −1 under K in the consumer interface; N even, N ≥ 64; margin 2 L2 clocks at NMAX 2,048 | **P → W-R18** (architect's direction 2026-10-05) | — |
| **W-F38** | **Packet output table**: per-packet sums → FIFO → 2-bank table, 1 write / 5 read; L2 source region; two-sample delay; not-played bit | **P → W-R19** (architect's direction 2026-10-05) | — |

**要旨:** 既存の Fixed 行は実機で確認済み。新規は W-F31〜38 で、すべて裁定待ちの提案。

---

## 4. E-taxonomy as built / E 分類（as built）

| E | Cause | Detection as built |
|---|---|---|
| E1 | Formation instruction in FG | Core halts internal Globals; **external Globals are not halted** (SD-02) → validator |
| E2 | Formation instruction in Q | **validator-only** (no band on the issue port, SD-01) |
| E4 | removed rows; STA→ADRS | hardware (Phase 2) |
| E5 | ADRS outside the map | hardware |
| E8 | MUL, MAC, **SFT** overflow (ADD/SUB wrap) | hardware, decided in the next clock (SD-22 step 2); Accm restored, the next instruction squashed |
| EW2 … EW6 | as Map v0.4 §8 | hardware; **each observed once on silicon** (C4, C5): code, silence, halt after 9 / 1,005 / 1,001 / 11 / 1,000 clocks |
| — | the error strobe | insertion port → TRAP → foreground Prog End → HALT (SD-06) |

---

## 5. Value formats / 値のフォーマット

As v0.7. The L1 sine's realization (Horner in u², folded coefficients, 7 multipliers, 16 clocks, max error 2⁻²⁴) is now the customer's official specification (SD-16, ruled 2026-09-30).

---

## 6. Verification items / 検証項目

| W-V | Item | Status |
|---|---|---|
| W-V1 … W-V3 | closed | — |
| W-V4 | g = 0; T_wake ≤ 4 | **closed on silicon**: g = 0, T_wake 2 (C2) |
| W-V5 | N_MIN; BCP duration | **closed on silicon**: floor 30 (N_MIN 32 holds), BCP 10 |
| W-V6 | paused blocks freeze | customer (PR-4) |
| **W-V7** | the 100 MHz L1 under a 50 MHz L2 (W-F37) | Layer 4 |
| **W-V8** | V-K: r(K), K_c | Layer 4 (Phase 7) |

---

## 7. Customer requirements and notices / 顧客要求と通知

CR3-/CR5- dispositions as v0.7, now **demonstrated on silicon** for CR3-B1, B2, R1, T1, T2, T3, C1 (bundles equal), CR5-I1, I2, I3, S1, L1, R1.

| PR | Request / notice | State |
|---|---|---|
| PR-1 … PR-5 | as v0.7 | relayed |
| **PR-6** | V-K notice (RT.OUT bits 2–15 as mode; raw sine sums into non-audio accumulators; rotor-view vocabulary) | prepared |
| **PR-7** | half-rate Stay: N even, N ≥ 64 in the 100 MHz-L1 build (W-F37) | pending W-R18 |
| **PR-8** | packet output table exists; two-sample delay; not-played bit (W-F38) | pending W-R19 |
| SD-09 | Appendix 5.B presets lack bit 16 (0x19E3B, 0x19FFF) | to relay |
| SD-16 | sine note | prepared (`customer_note_sd16_sin.md`) |
| SD-17 | 50 MHz test origin N = 1,008 | ruled; to relay |
| SD-19 | host path ISSP | prepared (`customer_note_sd19_host_path.md`) |
| SD-20 | ROM exempt from ownership | ruled; to relay |

---

## 8. Discrepancy shelf / 食い違い棚

| W-D | Item | State |
|---|---|---|
| W-D1 … W-D25 | as v0.7 | — |
| **W-D26** (SD-01) | Core issue port carries no band | Core office |
| **W-D27** (SD-02) | external Globals in FG not halted | Core office → W-R21 |
| **W-D28** (SD-03) | SSS / INT-R4 not exported | Core office |
| **W-D29** (SD-10) | stale header comments in `ptsg_core.v` | Core office |
| **W-D30** (SD-15) | insertion handshake accepts a held request twice | Core office (bug report, reproduced on the frozen source) |
| **W-D31** (SD-23) | imem half-cycle read binds at 50 MHz; migration EDGE "POS" + fetch stage is a Core Layer 1 matter (C2-T4) | Core office |
| **W-D32** (SD-04) | no data-driven gap-free re-entry in the Core as built | Core office (informative) |
| SD-08 | v0.7 editorial | **fixed in v0.8** |

---

## 9. Evidence / 証拠

| Class | Item | Value |
|---|---|---|
| ORACLE | sweep oracle | 60,000 samples, 0 mismatches (v0.6) |
| RTL-SIM | Phases 1–6 | Core copy bit-identical; datapath 3,914 cases; 36,000 sweeps; L1 bit-exact; 20 + 11 + … mutants caught |
| STA | fit 3 (2026-10-04) | clk_sys +0.978 ns, TNS 0; SignalTap build +0.557 ns; 11,052.8 ALMs (fit 1 ledger) |
| SILICON | first sound (10-03) | the test origin through HDMI; I2S words bit-exact after 39,684,738 sweeps |
| SILICON | Dirichlet kernel (10-04) | period 255.65 s predicted (10-03) — about 4 min 15 s observed |
| SILICON | C1–C5 (10-04) | g 0 · T_wake 2 · floor 30 · BCP 10 · 1,023/1,041 · 45 bundles, 12 banks equal · EW2–EW6 once each |

---

## 10. Status board / 状況板

| # | Deliverable | Status |
|---|---|---|
| 1 | Register map | v0.4 issued (as built) |
| 2 | L1 consumer interface | v0.2 issued (as built) |
| 3 | Choreography | v0.2 issued (dispatch form) |
| 4 | Rulings | W-R18 … W-R22 open |
| 5 | R7 scenario | **played on silicon** (C2: 8 packets, full load) |
| 6 | Contract and oracle | v0.2; silicon agrees |
| 7 | Layer 4 | **first sound; C1–C5 green** |
| 8 | Next | V-K (Phase 7); half-rate Stay; packet output table |

---

*End of v0.8.*
