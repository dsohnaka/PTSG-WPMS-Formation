# PTSG-WPMS-Formation — Decision Register W
# PTSG-WPMS-Formation — 決定台帳 W

*v0.6 · WPMS-Formation amanuensis · 2026-09-26 · CC0 · Layer 1.*
*Status: rulings through 2026-09-26 recorded. Issued together with Register Map v0.3 (Deliverable 1), Deliverable 2 v0.1 (L1 consumer interface) and Deliverable 3 v0.1 (choreography), and Layer 3 v0.2 (contract, oracle, sweep oracle).*

*v0.6 · 2026-09-26 までの裁定を記帳。成果物 1〜3 と第 3 層 v0.2 を同時発行。*

---

## Changelog v0.5 → v0.6

- **Customer Layer 1 read in full** (WPMS Ch.1–5, Appendix 5.A, trace 2026-09-24); the customer's oracle re-run here: 18/18 PASS.
- **Rulings 2026-09-26**: W-R10 amplitude part → **log domain (CR3-A1)**; **Mode T retracted**, **bundle presentation adopted**, PPM-1/PPM-2 RESTRICTED for packet blocks; **STP, BCP and the sequencer alias approved**; the Core commits to g = 0 and to Branch-0 wake within 4 clocks; upstream/downstream notices relayed by the architect.
- **Why Mode T fell** (recorded, not hidden): under the master's pointer-flip F-F14 the new shadow holds the *previous* world, so "rewrite only what changed" holds only for two-window differences. An oracle model showed Mode T losing advances for P ≥ 2, and per-sweep commits reverting retunes every other sweep. The single store with write windows passed the same random test with zero mismatches.
- **New rows** W-F24 … W-F30; W-F22 amended; W-F9, W-T2, W-R5, W-V1–W-V3 closed; E3, E7 vanish.
- **Found while building the oracle**: phase advances need wrapping ADD; the inherited model saturated and raised E8 → **W-F30 (proposed)**.
- **PTSG-Core stay_value** (CHANGES 2026-09-26, PROVISIONAL) read and answered (Deliverable 3 §11).

**要旨:** 顧客第 1 層を通読、顧客オラクル 18/18 PASS を再確認。09-26 裁定(対数振幅、Mode T 撤回とバンドル提示、PPM-1/2 の制限、STP・BCP・シーケンサ別名)を記帳。Mode T の撤回理由を記録。オラクル構築中に見つかった「位相の ADD は折り返しが要る」を W-F30 として提案。

---

## 0. Pins / 釘付け

| Repository | Pinned at | Content relied on |
|---|---|---|
| PTSG-CPU-Formation (master) | `ad43cc2c4472` (main, contains the 2026-09-03 fixes; contract verified identical to the pinned copy) | Layer 1 Ch.1–5; `isa_table.json` |
| PTSG-Core | `1b58ebcdee6e` | Layer 1 Ch.2–3; CHANGES_Layer1_stay-value_2026-09-26 (PROVISIONAL); trace 2026-09-26 |
| FPGA_Spectrum_Engine_OpenPrompt (customer) | `891fce6dacdb` | Layer 1 Ch.1 v1.0, Ch.2 v1.1, Ch.3–5 v1.0 DRAFT; Appendix 5.A; oracle |

Subtraction is judged on the resulting form; profile additions may be absorbed upstream later.

---

## 1. Conventions / 記帳規約

As v0.5. Vocabulary: **L1 pipeline · L2 Formation (this profile) · L4 Formation (outside WPMS)**. New auxiliary: **CR-** = customer requirement (WPMS Ch.3 §3.8, Ch.5 §5.10); **PR-** = profile requirement back to the customer.

---

## 2. Rulings / 裁定

### 2.1 Ruled (cumulative) / 裁定済み

| ID | Ruling | Date |
|---|---|---|
| W-R0 / W-R7 | pin to the master's 2026-09-03 revision | 09-01 / 09-04 |
| W-R1 | 16- and 32-bit integer formats; the ISA speaks integers; Q downstream | 09-01 |
| W-R2 | W-F1 RESTRICT F-F13 | 09-01 |
| W-R3 | W-T1 OMIT data stack | 09-01 |
| — | W-T3 RESTRICT; W-T5 EXTEND-at-need; W-D2 → deliverable 3; k = Stay counter; packet length = Stay value | 09-02 |
| W-R4 / R5 / R6 | layer vocabulary; exp both options; ownership split | 09-03 |
| — | W-F22 two-stage; W-F23 option B; W-R8 (F-F14 now); W-R9 (EW2, EW3); L4 outside WPMS | 09-04 |
| W-R10 (phase) | Q0.32 modular; RT.OUT numbering | 09-23 (customer trace) |
| W-R11 | Ch.2 v1.1 first | 09-23 (customer trace) |
| **W-R10 (amplitude)** | **log domain, CR3-A1** | **09-26** |
| **—** | **Mode T retracted; bundle presentation (remedy ii) adopted; PPM-1/PPM-2 RESTRICTED for packet blocks** | **09-26** |
| **—** | **STP, masked block copy (BCP), sweep-sequencer alias approved** | **09-26** |
| **—** | **Core: no idle clock between consecutive Stays (g = 0); Branch-0 wake within 4 clocks (one clock or more is an investigation item)** | **09-26** |

### 2.2 Open / 裁定待ち

| ID | Question | Amanuensis's proposal |
|---|---|---|
| **W-R12** | Consequences of remedy (ii) | OMIT CMT and RTW (no page pair; routing at +0xE, CUR retired); RESTRICT WSV — the sequencer becomes the sole writer of the Stay-value path (W-F22 amended) |
| **W-R13** | Profile error rows | EW2 widened to N < N_MIN (= 32); EW3 covers every read-only region; new EW4 (write windows), EW5 (sweep word), EW6 (negative glide rate); all Error HALT |
| **W-R14** | Encoding of the extensions | mode 4 = the profile's extension mode: STP 4·0, BCP 4·1 (no master code re-used) |
| **W-R15** | W-F30: ADD/SUB wrap modulo 2³² | yes — the phase slots are modular by definition; E8 stays for MUL/MAC |
| **W-R16** | Condition lanes and timing-signal bits (W-F19) | STROBE / NONEMPTY / MORE on TS_CSEL[1:0]; TS_PKT for L1 |
| **W-R17** | Packet repetition in the Core score | R1 (unrolled positions, forward transfers) or R2 (one body, data-driven re-entry) — the Core's choice, via the architect |

---

## 3. The register proper / 台帳本体

Status: **F** Fixed · **P** Proposed · **T** Tracking · **R** Resolved.

### 3.1 Master decisions and ties

| W-ID | Master ID | Disposition | Status | Note |
|---|---|---|---|---|
| W-F1 | F-F13 | RESTRICT | F 09-01 | dest ID 6 → E4 |
| W-F2 | F-F1·F-F2·F-F3 | INHERIT | P | window-only citizens; BG computes. The "Q commits" half has no profile citizen now (W-F25): presentation happens at Stay Set |
| W-F3 | F-F4 | INHERIT | P | latch law; realized for Stay values by W-F22 |
| W-F4 | F-F5·F-F10 | INHERIT | P | quartet; K = k by construction |
| W-F5 | F-F6 | INHERIT | P | R0–R3 still unimplemented |
| W-F6 | F-F7 | INHERIT and elevate — **restated** | P | zero zipper noise by construction, now through **whole bundles at packet start** (W-F24) instead of page swaps |
| W-F7 | F-F8 | INHERIT | P | every extension here is rows first |
| W-F8 | F-F9·F-F11 | doctrine; no stack | F | — |
| W-F9 | F-F14 | **R — superseded by W-F24** | R 09-26 | no page pair in this profile; the master's claim is filed upstream (W-D22) |
| W-F10 | F-T2·F-T3·F-T6 | INHERIT closed stance | P | — |
| W-T1 | DSTK | OMIT | F 09-01 | E6 vanished |
| W-T2 | F-T1 | **R — N_MIN = 32** | R 09-26 | 25 window instructions + 4 Core clocks = 29, oracle-counted; Layer 4 measures |
| W-T3 | F-T5 | RESTRICT | F 09-02 | kept intact by the CUR alias |
| W-T4 | F-T7 | R (W-R1) | R | — |
| W-T5 | F-T8 | EXTEND-at-need | approved 09-02 | not triggered: the packet window already uses LDM/STM post-increment |

### 3.2 Treaty, common law, memory law

| W-ID | Master ID | Disposition | Status | Note |
|---|---|---|---|---|
| W-F11 | IF-1…5; nine lanes | INHERIT | P | the bundle port and `stay_value` are the profile's side, not new lanes |
| W-F12 | INT-R1…R4 | TRACK | T | W-F22 remains INT-R1's first realization, now through the Core's `stay_value` pin |
| W-F13 | CL-1…5 | INHERIT | P | — |
| W-F14 | PPM-1…3 · CMT-1…4 | **RESTRICT** PPM-1/PPM-2 for packet blocks; CMT-* not applicable (W-F25) | **F 09-26** | replaced by write windows and bundle presentation (W-F24) |
| W-F15 | DSTK-1·2 | OMIT | F | — |
| W-F16 | E1…E8 | INHERIT + profile rows | P → W-R13 | §4 |

### 3.3 Extensions / 拡張

| W-ID | Extension | Status | Where |
|---|---|---|---|
| W-F17 | L1 consumer interface | P (v0.1 issued) | Deliverable 2 |
| W-F18 | Block format (canonical: Appendix 5.A.2, +0xE = RT.OUT) | P (v0.3 issued) | Map §6 |
| W-F19 | Condition lanes: STROBE, NONEMPTY, MORE; TS_CSEL, TS_PKT | home F 09-02; assignment P → W-R16 | Deliverable 3 §4 |
| W-F20 | Choreography | P (v0.1 issued) | Deliverable 3 |
| W-F21 | 16/32-bit integer formats | F 09-01 | Map §1 |
| W-F22 | Two-stage Stay-value register → the Core's `stay_value` pin; StayVal.p loaded at Stay Set (N for packets, 0 otherwise). **Amended**: StayVal.s written by the sequencer | F 09-04; amendment P → W-R12 | Map §2; D3 §5 |
| W-F23 | SHV / WSH | F 09-04 | Map §3 |
| **W-F24** | **Single block store; bundle presentation; write windows** | **F 09-26** | Map §5; D2 §4 |
| W-F25 | OMIT CMT and RTW; RT.OUT at +0xE | P → W-R12 | Map §3, §6 |
| **W-F26** | **STP** — step-toward | **F 09-26** (encoding → W-R14) | Map §3 |
| **W-F27** | **BCP** — masked block copy of the GO's take-set | **F 09-26** (encoding → W-R14) | Map §3, §7 |
| **W-F28** | **Sweep sequencer**: SWEEP.a, packet index, CUR alias, bundle and Stay-value prefetch, take-set, inbox-taken; WSV RESTRICTED | **F 09-26** (WSV part → W-R12) | Map §2, §4; D3 |
| **W-F29** | **Log-domain slot semantics** (CR3-A1, with CR5-L1) | **F 09-26** | Map §6 |
| W-F30 | ADD/SUB wrap modulo 2³²; E8 only for MUL/MAC | P → W-R15 | Map §3 |

**要旨:** W-F24(単一ストア・バンドル提示・書込み窓)、W-F26 STP、W-F27 BCP、W-F28 シーケンサ、W-F29 対数スロットが Fixed。W-F25(CMT・RTW の省略)、WSV の制限、W-F30(ADD/SUB の折り返し)は提案。W-F9・W-T2 は解決。

---

## 4. E-taxonomy of this profile / E 分類

| E | Cause | This profile |
|---|---|---|
| E1, E2 | Formation instruction in FG / Q | INHERIT (the profile has no Q citizen) |
| E3, E7 | CMT-related | **vanished** (no CMT) |
| E4 | reserved or removed rows | PSH, POP, CMT, RTW, WSV; STA→ADRS |
| E5 | ADRS outside the map | 9-bit map of Map §4 |
| E6 | stack | vanished |
| E8 | arithmetic overflow | MUL/MAC only (W-F30) |
| EW2 | N ∉ [N_MIN, NMAX] at prefetch | proposed widening → W-R13 |
| EW3 | STM into a read-only region | → W-R13 |
| EW4 | write-window violation | → W-R13 |
| EW5 | invalid sweep word; Σ N > NMAX | → W-R13 |
| EW6 | STP with negative rate | → W-R13 |

The contract `isa_table_w.json` (16 instructions) is generated by `isa_fold_w.py` from the master's; every fold cites its W-ID.

---

## 5. Value formats / 値のフォーマット

ISA tier unchanged (W-R1). Program tier (WPMS Ch.3, reference only): PH\*/OM\* Q0.32 modular; LP, LE0, LPT Q6.26; LAD1 Q8.24; LAD2 Q2.30; LS0 Q12.20; N, TAG, RT.OUT integers. The WPMS hot path uses no MUL and no SHV.

---

## 6. Verification items / 検証項目

| W-V | Item | Status |
|---|---|---|
| W-V1 | K = k | closed 09-02 (construction) |
| W-V2 | F-F14 | closed (moot: W-F24) |
| W-V3 | Core external Stay value | **closed**: `stay_value` published (PROVISIONAL): IND-reverse, read at the Stay's execute clock and held (C4-F15, C4-F16). This supersedes the 09-03 answers (live until the trailing edge; operand 0 selects the pin); W-F22's two stages remain useful as the pin driver |
| W-V4 | g = 0 and T_wake ≤ 4 | Core commitment; Layer 4 |
| W-V5 | N_MIN, BCP duration on silicon | Layer 4 |
| W-V6 | Paused blocks freeze (reading of CR3-C1) | customer confirmation (PR-4) |

---

## 7. Customer requirements — dispositions / 顧客要求の処置

| CR | Disposition | Realized by |
|---|---|---|
| CR3-A1 | accepted | W-F29; D3 §6.1 |
| CR3-B1 | accepted | W-F24, W-F28; D2 §3, §5 |
| CR3-B2 | accepted | D2 §2 |
| CR3-R1 | accepted | +0xE in the bundle |
| CR3-T1 | accepted (profile side); Core commitment | D3 §3, §9 |
| CR3-T2 | accepted; Core commitment | D3 §9 |
| CR3-T3 | accepted | D2 §2 |
| CR3-C1 | accepted, by construction; paused blocks freeze (PR-4) | D3 §8; sweep oracle |
| CR3-C2, CR3-C3 | replaced (by CR5-I1, CR5-R1) | — |
| CR3-M1 | accepted | D3 §13 |
| CR5-I1 | accepted | BCP (W-F27) |
| CR5-I2 | accepted — **bound: one sweep** | D3 §7, §9 |
| CR5-I3 | accepted | BCP raises inbox-taken |
| CR5-S1 | accepted | SWEEP.a (W-F28) |
| CR5-L1 | accepted | STP (W-F26) |
| CR5-R1 | accepted | Map §9 |

**Profile requirements back to the customer (PR)**

| PR | Request |
|---|---|
| PR-1 | The switch rejects sweep words that repeat a block among the first P entries (EW5 is the backstop). |
| PR-2 | The switch rejects GOs that leave a listed block with N ∉ [32, 2,048]; CONFIG (Ch.5 §5.6.1) may expose N_MIN beside NMAX (EW2 backstop). |
| PR-3 | Writers keep LE0 ≥ 0 (EW6 backstop); a guideline for the L4 tool. |
| PR-4 | Confirm the reading of CR3-C1 for paused blocks: an unlisted block freezes and resumes where it stopped. |
| PR-5 | Wording: Appendix 5.A.2 and Ch.5 §5.4.2 — +0xE now holds RT.OUT (selected by mask bit 16; bit 14 stays ignored). Ch.3 §3.3 — within a sweep, P ≤ 8 is firm in the first implementation; mid-sweep inbox re-fill (register map v0.2's note) is withdrawn with Mode T; more packets per sweep come only from more blocks (Arena). |

---

## 8. Discrepancy shelf / 食い違い棚

| W-D | Item | State |
|---|---|---|
| W-D1–D5, D13, D17–D21 | earlier items | resolved |
| W-D14–D16 | Ch.1 superseded text | accepted downstream (Ch.1 v1.1, Appendix 5.A.3) |
| W-D6 | Core §3.3a blank-shot wording | resolved (HALT is correct) |
| W-D7–D9, D12 | master defects | fixed 09-03, verified |
| W-D10, D11 | oracle gaps | done profile-side (Layer 3 v0.2) |
| **W-D22** | master F-F14: "untouched values are what the consumer was just using" holds only for two-window differences under pointer flip | **filed via the architect, 09-26** |
| **W-D23** | CPU-Formation README gives the architect's name as 大中恒夫; correct: 大中庸生 | **filed via the architect** |
| **W-D24** | customer `01_Architecture/README.md` inventory predates Ch.1–5 | **filed via the architect** |
| **W-D25** | customer text touched by the Mode T retraction (+0xE; mid-sweep re-fill) | → PR-5 |

---

## 9. Layer 3 assets and evidence / 第 3 層の資産と証拠

| Asset | Result (oracle, not silicon) |
|---|---|
| `isa_fold_w.py` → `isa_table_w.json` | 16 instructions; fold log cites W-F1, W-T1, W-F23, W-F25–W-F28 |
| `wpms_packet.pfasm` (25) · `wpms_housekeeping.pfasm` (1) | CLEAN on the profile contract |
| `sweep_sim.py` | 3 seeds × 20,000 samples; 215,627 packet plays; 4,174 GOs (1,175 full-load); **0 mismatches** against a reference built from WPMS Ch.3/Ch.5 with the customer's `step_toward`; worst sweep 2,064 of 2,083 clocks |
| `negative_tests.py` | **13/13**: EW2–EW6 and E4 each reject what they should; a mutant window (PH0 advanced twice) is caught |
| `exp_maclaurin_w.pfasm` v0.2 | 27 instructions, CLEAN; max error 7.39e-09 — unchanged numerics without CMT |

---

## 10. Status board / 状況板

| # | Deliverable | Status |
|---|---|---|
| 1 | Register map | **v0.3 issued** |
| 2 | L1 consumer interface | **v0.1 issued** |
| 3 | Choreography | **v0.1 issued**; FG realization R1/R2 with the Core |
| 4 | Rulings | W-R12 … W-R17 open |
| 5 | R7 scenario | windows in `.pfasm` + sweep oracle done; the Core score awaits R1/R2 |
| 6 | Profile contract and oracle | v0.2 done |
| 7 | Layer 4 on DE10-nano | next: g, T_wake, N_MIN, BCP duration |

---

*End of v0.6.*
