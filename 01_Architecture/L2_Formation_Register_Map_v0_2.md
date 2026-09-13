# PTSG-WPMS-Formation — Deliverable 1
# L2 Formation: ISA-Visible Register Map / L2 Formation の ISA 可視レジスタマップ

*v0.2 DRAFT · WPMS-Formation amanuensis · 2026-09-07 · CC0 · rows first (F-F8).*
*v0.2 records the WPMS Ch.3 side's answers of 2026-09-07 (Q column, RT.OUT channels, slot-set confirmation, Mode T support) — those are **Ch.3 proposals pending the architect's ruling**, shown here so the two documents stay aligned. v0.1 was accepted by the WPMS side as customer.*
*Anchored in Decision Register W as **W-F18** (page layout), **W-F21** (integer widths), **W-F22** (Stay-value register), **W-F23** (shift-value register). Master: PTSG-CPU-Formation, 2026-09-03 revision (W-R7).*

*成果物 1 v0.1 草案。台帳 W の W-F18/W-F21/W-F22/W-F23 に係留。ISA が語るのは整数と番地と幅だけであり、各値の Q 解釈と L1 パイプラインへの配線は WPMS 第3章の所有(W-R6)。*

---

## 0. Scope and reading rules / 範囲と読み方

- **What this document fixes**: register names, addresses, integer width classes, active/shadow status, who may write each place, and the commit law. Nothing here carries a Q-format; the column "Q (Ch.3)" is deliberately empty.
- **What it does not fix**: the L1 pipeline's internals, the wiring of slots to pipeline inputs, Q-conventions, DSP/LE accounting (WPMS Ch.3). The L1 consumer *interface* (which slots and lanes L1 reads, and when) is deliverable 2; this document only makes both candidate mechanisms possible (§4).
- **Layers**: L1 pipeline (hardwired) · **L2 Formation (this)** · L4 Formation (external controller; not part of WPMS).
- **Quantities**: kind · unit · owning scope, bound to DE10-nano. Instruction counts below are derived from the master ISA rows, **not measured**.

**要旨:** 本書が固定するのは名前・番地・整数幅クラス・活性/影・書き手・コミット則。Q 列は意図的に空欄。L1 内部と配線は第3章、消費者インターフェースは成果物 2。

---

## 1. Width classes / 幅クラス

| Class | Bits | Port | Used for |
|---|---|---|---|
| **W32** | 32 | 32-bit integer port | datapath word (Accm, Temp, every PPM parameter slot) |
| **W16** | 16 | 16-bit integer port | packet length, tags, routing masks, block index |
| **W12** | 12 (in a W16 port) | 16-bit port, low 12 bits | Stay value, Loop value, State Number, quartet K / I / SN / SSS |
| **W5** | 5 (in a W16 port) | — | shift value SHV |

W-R1 satisfied: the profile exposes both 16-bit and 32-bit integer register formats. The datapath word is 32 bits (this profile's Arena choice under the master's Free Precision Floor; documented here).

---

## 2. Register file / レジスタファイル

| Register | Class | Access (datapath) | Written by | Consumed by | Note |
|---|---|---|---|---|---|
| **Accm** | W32 | read / write | mode-1 ops, LDM, LDA | everything | master Ch.2 |
| **Temp** | W32 | read / write | SWP, STA | MUL/MAC multiplicand | master Ch.2 |
| **ADRS** | 8-bit | write only | SAD, STA (dest 6 — **RESTRICTED W-F1**); post-inc by LDM/STM | LDM, STM, source 2 | addresses the 256-word space of §3; out of range → E5 |
| **StayVal.s** | W12 | write only | **WSV** (← Accm[11:0]) | StayVal.p at Stay Set | staged value (W-F22 stage 1) |
| **StayVal.p** | W12 | none (not a register the program touches) | loaded from StayVal.s **at Stay Set only** | **Core external Stay-value input** (live comparator on the Core side; frozen here) | presented value (W-F22 stage 2); INT-R1's first implementation |
| **LoopVal.s / .p** | W12 | write only / none | WLV / at Loop Set | Core external Loop-value input | reserved, same shape (Core: same mechanism) |
| **JumpVal** | W12 | write only | WJV | register-source Jump/Branch — **FG use RESTRICTED (W-T3)** | BG-only computed dispatch |
| **SHV** | W5 | write only | **WSH** (new, mode 3·3; ← Accm[4:0]) | MUL, MAC realignment | W-F23; latch per F-F4: effective for the next MUL/MAC |
| **K** | W12 | read only (source 3) | Core stay counter | programs; **k of the L1 difference engine** (ruling 09-02) | prescaler = 1 in this profile |
| **I** | W12 | read only (source 4) | Core loop counter | programs | — |
| **SN** | W12 | read only (source 5) | Core | relative dispatch | — |
| **SSS** | W12 | read only (source 6) | Formation latch at window start | window-vectored preparation | — |
| **R0–R3** | — | reserved | — | — | R0 is the named candidate for a *consumer output value* (feedback path, §5.2); unimplemented until proven need (F-F6) |

**Removed relative to the master**: SP / data stack (W-T1 OMIT); ADRS as STA destination (W-F1). **Added**: StayVal.p, SHV, WSH.

**Mode-3 sub-op table of this profile**

| Sub-op | Mnemonic | Semantics |
|---|---|---|
| 3·0 | WSV | StayVal.s ← Accm[11:0] |
| 3·1 | WLV | LoopVal.s ← Accm[11:0] |
| 3·2 | WJV | JumpVal ← Accm[11:0] |
| **3·3** | **WSH** | **SHV ← Accm[4:0]** (values > 31 → EW1) |

**MUL / MAC in this profile**: `MUL: Accm ← (Accm × src) >> SHV` · `MAC: Accm ← ((Accm × Temp) >> SHV) + src`. Product width and rounding mode: Arena, to be stated by the implementation (proposal: 64-bit product, arithmetic shift, truncation — matches the inherited oracle).

**要旨:** マスターから SP/DSTK と ADRS 宛先を除き、StayVal.p・SHV・WSH を加えた。WSH はモード3 サブオペ 3。MUL/MAC は `>> SHV` で再整列。

---

## 3. Address space (256 words, ADRS = 8 bits) / アドレス空間

| Range | Region | Pages | Datapath read (LDM / source 2) | Datapath write (STM) | External write |
|---|---|---|---|---|---|
| `0x00–0x7F` | **PPM** — 8 blocks × 16 words | active / shadow pair | active | shadow | none |
| `0x80–0xFF` | **Inbox** — 8 blocks × 16 words, same block format | single (no shadow) | yes | **no → EW3** | yes (external port, §5.1) |

- **Commit**: one CMT swaps PPM active/shadow **and** the RT pages (CMT-1..4 inherited). The inbox is not paged and is untouched by CMT.
- **Post-commit shadow inheritance** (F-F14, adopted profile-side — W-R8): after CMT the new shadow holds the former active contents; programs rewrite only what changed.
- E5: ADRS outside `0x00–0xFF`.

### 3.1 Block format (16 words; identical for PPM blocks and inbox blocks) / ブロック形式

Every packet is described by one block. Slots marked **[S]** are *sample-advanced state* (the L2 program adds the matching **[P]** increment once per sample period); slots marked **[P]** are per-packet constants supplied from outside (inbox → block). All arithmetic is integer; phase slots wrap modulo 2³².

| Offset | Slot | Class | Kind | Role | Q (Ch.3) |
|---|---|---|---|---|---|
| `+0x0` | **N** | W16 (W12 used) | packet length, bins | Stay value of this packet (WSV copies it); **1 ≤ N ≤ NMAX** (NMAX = 2,048 bins per module, profile configuration constant bound to DE10-nano; a design variable) | integer |
| `+0x1` | **TAG** | W16 | packet tag | informational; free for the controller | integer |
| `+0x2` | **A0** | W32 | amplitude of bin 0 | **[S]**: `A0 ← (A0 × E0) >> SHV` per sample | Q1.31 signed (Ch.3 prop.) |
| `+0x3` | **AR1** | W32 | amplitude ratio, bin k+1 / bin k at k = 0 | [P] — first geometric difference (> 1 at k = 0 for a Gaussian centred at N/2) | Q4.28 signed (Ch.3 prop.) |
| `+0x4` | **AR2** | W32 | ratio of ratios (= exp(−2γ) in WPMS Ch.1 §1.7) | [P] — second geometric difference, constant in k | Q4.28 signed (Ch.3 prop.; Q8.24 kept in Arena) |
| `+0x5` | **E0** | W32 | per-sample amplitude ratio (envelope) | [P] — advances A0; **SHV = 28** for the A0 × E0 advance under these conventions | Q4.28 signed (Ch.3 prop.) |
| `+0x6` | **PH0** | W32 | phase of bin 0 | **[S]**: `PH0 ← PH0 + OM0` | Q0.32 modular (Ch.3 prop.) |
| `+0x7` | **PHD1** | W32 | first forward difference of phase across k, at k = 0 | **[S]**: `PHD1 ← PHD1 + OMD1` | Q0.32 modular |
| `+0x8` | **PHD2** | W32 | second forward difference of phase across k (constant) | **[S]**: `PHD2 ← PHD2 + OMD2` | Q0.32 modular |
| `+0x9` | — | — | reserved | (third-order phase — **not needed now**: Ch.1 §1.4 is quadratic in k; Ch.3 confirms) | |
| `+0xA` | **OM0** | W32 | phase increment per sample of bin 0 | [P] — OM0 = f₀/Fs mod 1 | Q0.32 modular |
| `+0xB` | **OMD1** | W32 | first forward difference of increment across k | [P] — OMD1 = (Δf+α)/Fs | Q0.32 modular |
| `+0xC` | **OMD2** | W32 | second forward difference of increment across k | [P] — OMD2 = 2α/Fs | Q0.32 modular |
| `+0xD` | — | — | reserved | (third-order increment — not needed now) | |
| `+0xE` | **CUR** | W16 | block index (block 0 only) | Mode T only (§4): which block L1 reads in the world committed with it | integer |
| `+0xF` | — | — | reserved | | |

**Why forward differences, not polynomial coefficients**: the L1 difference engine consumes running first/second differences directly (add chains per bin); storing them avoids a derivation step in L1. The sample-advance law is then slot-wise addition of the increment group onto the phase group — three ADDs — and one realigned MUL for the envelope.

**Naming convention for the frequency axis**: OM\* are *phase increments per sample*. WPMS Ch.3's proposed **C3-D1** (2026-09-07): the WPMS boundary (inbox) carries phase-domain integers only; Hz never crosses it; Hz → increment conversion is the external controller's duty. This document is consistent with C3-D1 and takes no position beyond it.

**What L1 consumes (Ch.3 reading, 2026-09-07)**: at each packet start L1 latches six words — PH0, PHD1, PHD2, A0, AR1, AR2 — and runs two additions and two multiplications per bin; **L1 never reads OM\*, E0, N, TAG** (those are L2-only). This six-word contract is the seed of deliverable 2.

**要旨:** 1 ブロック = 16 語 = 1 パケット。振幅群(A0, AR1, AR2, E0)は幾何差分、位相群(PH0, PHD1, PHD2)と増分群(OM0, OMD1, OMD2)は前進差分。[S] はサンプルごとに [P] を加えて前進させる状態、[P] は外部から与える定数。前進則は整数加算三回と再整列乗算一回。

---

## 4. Consumer block selection — two mechanisms kept open for deliverable 2 / 消費者ブロック選択——成果物 2 のため両案を残す

| Mode | L1 reads | Per-packet L2 work (BG, during the previous packet's Stay) | Cost (instruction count from master rows; clocks in BG ≈ instructions; not measured) |
|---|---|---|---|
| **W — window** | always **block 0** of the active page | advance next packet's [S] slots in its table block (3 ADD + 1 MUL, each SAD/LDM/…/STM ≈ 4–5 instr.) and **copy** its 14 slots into shadow block 0; WSV N; CMT | ≈ 20 + 14 × 4 ≈ **75 clocks per packet** |
| **T — table-direct** | the block named by **CUR** (committed with the page) | advance next packet's [S] slots in place (shadow), write CUR, WSV N; CMT | ≈ **25 clocks per packet** |

Both satisfy CMT-2 (L1 sees whole worlds only). Mode T needs the L1 side to take a block index (a 3-bit lane); Mode W needs nothing but block 0. **The minimum packet length (W-T2) is the chosen mode's per-packet cost** plus any exp() computation if W-R5 option (a) is used. Recommendation to deliverable 2: **Mode T** (three times cheaper; keeps short packets legal). *WPMS Ch.3 side supports Mode T (09-07) and reads N_min ≈ 32 bins.*

**Block count vs packets per sweep (note added 09-07).** With N_min ≈ 32 a sweep of 2,048 bins could hold up to 64 packets, but the page holds **8 blocks**. Eight is the cheap concurrency limit, not a hard one: a block whose packet has finished may be **re-filled from the inbox** for a later packet in the same sweep (≈ 60 clocks, all 14 slots), or the page may be enlarged (ADRS width is Arena). The first implementation is expected to use ≤ 8 packets per sweep; more is a documented cost, not a prohibition.

**要旨:** 窓方式(L1 は常にブロック 0 を読む、コピーが要る ≈ 75 クロック/パケット)と表直読方式(CUR で選ぶ ≈ 25 クロック/パケット)。推奨は T。最小パケット長はこの費用で決まる。

---

## 5. Boundaries with the outside / 外部との境界

### 5.1 External write path — the inbox (profile addition, rows first) / 外部書込経路——inbox

The master defines no external write port into the PPM (its writers are STM and RTW only). WPMS needs one (requirement R2, 2026-05): an external controller (L4 Formation or host) must deliver [P] values and initial [S] values. **Proposal**: 

- The external port writes **only the inbox** (`0x80–0xFF`), W32 words, any time.
- The external writer signals **inbox-ready** on a Condition lane (deliverable 3, W-F19; seed R5 "L4→L2 handshake"). The L2 program, in BG, copies inbox blocks into shadow blocks and commits — so the shadow keeps a single writer (the datapath) and CMT-4 arbitration is untouched.
- The inbox has no shadow; the external writer is responsible for not rewriting a block between inbox-ready and the L2 copy (a second Condition lane, *inbox-taken*, is the cheap protocol; optional).

### 5.2 Routing tables (RT) / ルーティング表

Paged pair, committed with the PPM (CMT-1). One entry per packet block, written by RTW into the RT shadow (operand per master §3.4).

| Field | Class | Role |
|---|---|---|
| **OUT** | W16 | output-channel mask (Ch.3 proposal 09-07): bit 0 = L, bit 1 = R, bits 2–7 reserved for surround, bits 8–15 reserved for auxiliary/feedback; first implementation honours bits 0–1 only |
| **FB_EN** | 1 bit | feedback enable — **reserved**: injecting a consumer output into a parameter slot requires a datapath source for that value (candidate R0, §2) and the same-sample multi-writer law (deliverable 3). Not implemented in the first step. |
| **FB_ADDR** | 8 bits | target address for feedback — reserved with FB_EN |

### 5.3 What the external controller sees / 外部制御者から見えるもの

Writes: inbox (W32). Reads: none required (the controller knows what it wrote; the Core's external Stay value is supplied by L2, not by the controller). Status/handshake: Condition lanes (deliverable 3).

**要旨:** 外部書込は inbox のみ、影は単一書き手(データパス)を保つ。RT は出力チャネルマスクと予約済みのフィードバック欄。

---

## 6. Profile error rows (proposed, W-R9) / プロファイル E 行

| Row | Cause | Action |
|---|---|---|
| E4 (inherited, folded) | dest 6; PSH/POP; reserved IDs | Error HALT |
| E5 (inherited) | ADRS outside `0x00–0xFF` | Error HALT |
| **EW1** | *(retired in this draft)* WSH reads only Accm[4:0]; the shift is total on 0–31, so no out-of-range case exists | — |
| **EW2** | WSV with Accm[11:0] = 0 **or > NMAX (2,048)**. Core convention: the external Stay value is selected by a zero internal Stay operand, and both-zero means 4,096; this profile forbids values above the sweep length, so that convention is never reached. **Ruled 2026-09-04.** | Error HALT |
| **EW3** | STM with ADRS in `0x80–0xFF` (inbox is read-only to the datapath) | Error HALT |

*(EW1 is recorded and retired in the same draft so that the register keeps the reasoning: masking makes the shift total. W-R9 — EW2 and EW3 — ruled 2026-09-04.)*

**Selection of the external Stay value (Core convention, recorded)**: a Stay instruction whose internal operand is 0 takes its value from the external input, i.e., from `StayVal.p`. In this profile every packet Stay is written with operand 0; the Formation supplies N via WSV. The both-zero → 4,096 case is excluded by EW2.

---

## 7. Worked example — per-packet preparation, Mode T (integer only) / 使用例

Sketch in `.pfasm` idiom (validated form to follow once `isa_table_w` is generated). Prepares block *b+1* during packet *b*; SHV is set to the amplitude convention's shift (a program-tier choice — here written symbolically).

```
.bg
LDA   #SHIFT_A        ; program-tier Q choice for amplitude
WSH                   ; SHV <- Accm[4:0]
SAD   B1+0x5          ; E0
LDM                   ; Accm <- E0
SWP                   ; Temp <- E0
SAD   B1+0x2          ; A0
LDM                   ; Accm <- A0
MUL   TEMP            ; Accm <- (A0 * E0) >> SHV
SAD   B1+0x2
STM                   ; shadow A0 <- advanced
SAD   B1+0x6 / LDM / SAD B1+0xA / ADD @PPM / SAD B1+0x6 / STM     ; PH0  += OM0
SAD   B1+0x7 / LDM / SAD B1+0xB / ADD @PPM / SAD B1+0x7 / STM     ; PHD1 += OMD1
SAD   B1+0x8 / LDM / SAD B1+0xC / ADD @PPM / SAD B1+0x8 / STM     ; PHD2 += OMD2
LDA   #B1             ; CUR <- b+1
SAD   0x0E
STM
SAD   B1+0x0          ; N of block b+1
LDM
WSV                   ; StayVal.s <- N ; presented at next Stay Set
.q
CMT                   ; world switch on the trailing edge of packet b
```

Instruction count ≈ 30 (kind: instructions; scope: L2 BG per packet). With W-T5 post-increment adopted at need, the SAD bookkeeping shrinks by about a third.

---

## 8. Open items handed to deliverables 2 and 3 / 成果物 2・3 への引き継ぎ

1. Block selection: Mode W vs Mode T (recommend T; WPMS side concurs) — deliverable 2. Customer seeds received 09-07: (i) packet-start lane (= Stay Set) latches the six words of the CUR block into L1's running registers; (ii) bin-tick lane = K transitions advance L1 one step (ruling 09-02); (iii) sample-boundary lane starts the accumulator flush; (iv) L1 may widen internally beyond 32 bits (Ch.3's side).
2. Which timing lanes L1 receives from the Core/Formation (packet start = Stay Set, per-bin tick, packet end = Stay-timeup, sample boundary) — deliverable 2 (seeds: requirement R4).
3. Condition lanes: sample-boundary wake; inbox-ready (and optional inbox-taken) — deliverable 3 (W-F19).
4. Same-sample multi-writer law (needed before FB_EN is ever enabled) — deliverable 3.
5. exp() placement (W-R5): with Mode T, an L2-resident exp adds ≈ 26 instructions per packet (the master demo), which the packet-length minimum must then include.

---

*End of v0.2. The three requests of v0.1 were answered by the WPMS side on 2026-09-07 (Q column, RT.OUT channels, slot set complete; third-order not needed). Their Q proposals await the architect's ruling.*

*v0.2 の末尾。v0.1 の三つの依頼(Q 列・RT.OUT・スロット集合)は 09-07 に第3章側から回答済み。Q 提案は設計者裁定待ち。*
