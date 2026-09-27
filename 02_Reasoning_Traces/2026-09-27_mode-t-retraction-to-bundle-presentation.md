# From Page Swap to Bundle — the Retraction of Mode T
# ページ交代からバンドルへ——Mode T の撤回

## Trace Metadata / 軌跡メタデータ

| Field | Value |
|---|---|
| **Dates / 日付** | 2026-09-26 → 2026-09-27 (prelude: the customer's Layer 1, 2026-09-24) |
| **Participants / 参加者** | **Tsuneo Ohnaka (大中庸生)** — FPGA architect; ruling authority; relays all inter-session messages. **Claude (Anthropic)** — PTSG-WPMS-Formation amanuensis. Cited, not present: the customer's amanuensis (FPGA Spectrum Engine) and the Core's office (PTSG-Core), through their published documents. |
| **Model record / モデル記録** | Turns of 2026-09-26 and 2026-09-27: **Claude Opus 5.5**. Earlier turns of the same thread are not recorded here. |
| **Topic / トピック** | Why the register map's block-selection design (Mode T, per-packet page commits) was withdrawn, and how bundle presentation with write windows replaced it |
| **Status / 状態** | Layer 2 trace — single-AI drafting, rulings by the architect |
| **Direct outputs / 直接成果物** | Decision Register W v0.6 → v0.7; Register Map v0.3; Deliverable 2 v0.1; Deliverable 3 v0.1; Layer 3 v0.2 (`isa_fold_w.py`, `pfasm_tools_w.py`, `sweep_sim.py`, `negative_tests.py`, `wpms_packet.pfasm`, `wpms_housekeeping.pfasm`) |
| **Related repositories** | PTSG-CPU-Formation @ `ad43cc2` (master); PTSG-Core @ `1b58ebc` (`stay_value`, PROVISIONAL); FPGA_Spectrum_Engine_OpenPrompt @ `891fce6` (customer Layer 1 Ch.1–5) |
| **License / ライセンス** | CC0 1.0 Universal |

---

## Reading Notes / 読解上の注

**Who this trace is for.** (1) The master's amanuensis, because the retraction turns on a sentence in the master's F-F14. (2) The customer's amanuensis, because its Appendix 5.A.2 and its decision DP-5 ("Mode T") are affected. (3) Claude Code or any context-isolated agent generating the sequencer, the block store or a testbench: the documents of 2026-09-07 describe a page swap that no longer exists.

**本軌跡の読み手。** マスター祐筆殿(F-F14 の一文が論点)、顧客祐筆殿(付録 5.A.2 と DP-5 に影響)、そしてシーケンサ・ブロック記憶・テストベンチを生成するコンテキスト非共有のエージェント(09-07 の文書にはもう存在しないページ交代が書かれている)。

**Read in this order.** Precedence → Ruling State → §3 (the sentence) → §4 (the model) → §6 (why the bundle) → Evidence (run the oracle).

---

## Precedence / 優先順位

1. **Register W v0.7, Register Map v0.3 and Deliverables 2–3 supersede** every description of active/shadow pages, CUR, Mode T and Mode W in the profile's documents of 2026-09-07 (Register Map v0.2 §2–§7, the first-week trace, Hackaday Log #1). Those remain as dated records.
2. The customer's **DP-5 (Mode T)** and the **+0xE row of Appendix 5.A.2** are superseded from the profile's side; the customer's text changes on its own schedule (PR-5).
3. Where an agent finds both, it implements the bundle and flags the older text.

---

## Timeline / 時系列

| Date | Event |
|---|---|
| 09-24 | The customer completes Layer 1 (Ch.1 v1.0, Ch.2 v1.1, Ch.3–5 v1.0 draft, Appendix 5.A, oracle 18/18) and asks the profile, in its Hook A, which requirements are costly — above all CR5-L1's clamp and CR3-B1's zero-gap bundle. |
| 09-26 (morning) | The profile reads Ch.1–5 in full and re-runs the customer's oracle (18/18 PASS). First-pass costs of CR5-L1, CR5-S1, CR5-I1. Re-reading F-F14 exposes the two-window gap; a small model confirms that Mode T loses phase advances. Two remedies are tested; the bundle passes. |
| 09-26 | **Rulings**: log-domain amplitude (CR3-A1); Mode T retracted; bundle presentation adopted; PPM-1/PPM-2 RESTRICTED for packet blocks; STP, masked block copy and the sequencer alias approved; the Core commits to g = 0 and to Branch-0 wake within 4 clocks. The Core's `stay_value` pin is published the same day. |
| 09-26 (evening) | Register W v0.6, Register Map v0.3, Deliverables 2 and 3, Layer 3 v0.2 issued. Sweep oracle: 60,000 samples, 0 mismatches. |
| 09-27 | **Rulings**: W-R12–W-R16 approved; W-R17 — R2 preferred, R1 retained for bring-up and quick packet checks, both selectable. This trace. |

---

## Ruling State as of 2026-09-27 / 裁定状態

| Item | State |
|---|---|
| Log-domain amplitude (W-R10 amplitude part, CR3-A1) | **Ruled** 09-26 |
| Mode T retracted; bundle presentation; PPM-1/PPM-2 RESTRICTED for packet blocks | **Ruled** 09-26 |
| STP, BCP, sweep-sequencer alias | **Ruled** 09-26 |
| g = 0 between consecutive Stays; Branch-0 wake ≤ 4 clocks | **Core commitment** 09-26 (Layer 4 measures) |
| W-R12: OMIT CMT and RTW; RT.OUT at +0xE; WSV RESTRICTED (sequencer is the sole writer) | **Ruled** 09-27 |
| W-R13: EW2 widened to N < N_MIN = 32; EW3–EW6 Error HALT | **Ruled** 09-27 |
| W-R14: mode 4 for STP (4·0) and BCP (4·1) | **Ruled** 09-27 |
| W-R15: ADD/SUB wrap modulo 2³² (W-F30) | **Ruled** 09-27 |
| W-R16: lanes STROBE / NONEMPTY / MORE; TS_CSEL, TS_PKT | **Ruled** 09-27 |
| W-R17: packet repetition in the Core score | **Ruled** 09-27: **R2 preferred**; R1 kept for bring-up; both stay selectable |
| PR-1 … PR-5 to the customer | relayed by the architect |
| W-D22 (F-F14 wording), W-D23 (name), W-D24 (customer README) | relayed by the architect |

---

## The Reasoning, in Order / 推論の順序

### 1. What Mode T was / Mode T とは何だったか

Register Map v0.1/v0.2 kept eight 16-word packet blocks in a **page pair** (active read by L1, shadow written by the datapath, swapped by CMT on the trailing edge). **Mode T** let L1 read "the block named by CUR", a slot of block 0 committed with the page. During packet b the program prepared packet b+1 — advanced its [S] slots in the shadow, wrote CUR, committed at the boundary. Per packet this was cheap (≈ 25 clocks, N_min ≈ 32), and the customer concurred (its DP-5). The design leaned on the master's **F-F14** (post-commit shadow inheritance) and on the profile's own note: *"programs rewrite only what changed."*

### 2. The trigger: three costs / きっかけ——三つの費用

Asked by the customer's Hook A which requirements were costly, the profile priced three:

- **CR5-L1** (level glide, `LP ← LP + clamp(LPT − LP, ±LE0)`): expressible in the current ISA with no compare and no scratch — 35 instructions — but **E8 fires exactly at the canonical edges** (LPT = −32 decay from LP = 0; attack from −32), because LPT − LP − LE0 leaves the 32-bit range. A one-instruction step-toward does it in 9, overflow-free.
- **CR5-S1** (sweep word as data): one BG program must address "the block now playing", but W-F1 forbids computed pointers and W-T3 forbids computed FG branches. Remedy: an alias the sequencer points at the current block.
- **CR5-I1** (masked copy): no AND, no compare — per-slot masking by arithmetic is an order of magnitude dearer than the glide. Remedy: a hardware masked block copy.

Pricing CR5-I1 raised the question that mattered: *into which page does the copy land, and does it survive the next swap?*

### 3. The sentence that was literally true / 文字どおりには正しかった一文

F-F14 (master Ch.4): *after a commit, the new shadow holds the former active page's contents (the natural consequence of a pointer flip)* — hence *everything a program does not touch is, by law, the value the consumer was just using.*

Both halves are true. But "just using" means **before the last commit**. During window k+1 the consumer uses the world committed at the end of window k; the shadow holds the world before that. A value written in window k is **absent** from the page written in window k+1 unless written again. Delta-programming under a pointer flip is correct only for **differences across two windows** — the rule every 1990s game programmer knew as *the back buffer is two frames old*: dirty rectangles under page flipping must cover the last two frames.

The profile's W-R8 note ("rewrite only what changed") inherited the gap. So did Mode T.

### 4. The model / モデル

A small model (two pages, flip on commit, L1 latching PH0 from the active page) against the closed form PH0(n) = PH0(0) + n·OM0:

| Scheme | P = 1 | P = 2 | P = 3 |
|---|---|---|---|
| Mode T (commit per packet, advance only the next block) | correct | **block 0 stuck**: 0, 7, 7, 7, … | blocks 1, 2 wrong |
| Commit per sweep, [S]-only delta writes | correct | correct | correct |
| Commit per sweep, with one retune | — | increments alternate 100, 7, 100, 7 — **the retune reverts every other sweep** | — |

With increments alternating sample by sample, the retuned partial settles **halfway** between the old and the new frequency, wobbling at Fs/2 (24 kHz) — a pitch no one ordered.

### 5. Two remedies, one random test / 二つの救済、一つのランダム試験

- **(i) Keep the page pair, mirror every change into both pages.** A straightforward two-pass rule (second pass writes [P] slots always, [S] slots only if the block was not advanced) **failed 1,263 of 2,000** random trials: re-seeds of paused blocks lose to page parity. A correct rule exists with per-slot bookkeeping, but the fragility is the finding.
- **(ii) One block store; L1 takes a bundle at packet start; every write falls inside its block's write window.** **0 of 2,000.**

### 6. Why (ii) is the natural form / なぜ (ii) が自然な形か

L1 reads a block at exactly one instant per sample: the Stay Set of the packet that plays it (CR3-B1), and nothing else ever (CR3-B2). A page pair protects every clock of every packet; L1 needs protection at one clock per packet. So the latch itself can be the presented world — the two-stage Stay-value register of W-F22 (staged by the Formation, presented at Stay Set) widened from one word to eight. The customer had already named this form as CR3-B1's candidate (b).

Between two latches of the same block — one in sweep n, the next in sweep n+1 — the block may be written freely: its **write window**. With one store there is no second copy to be stale, so delta writes are exact.

### 7. Construction / 構成

- **Write windows by construction.** In a packet window the only writable block is the current one, through the **CUR alias** (0x100–0x10F); in the housekeeping window that closes the sweep, every block is writable. Anything else is EW4. The sweep word never lists a block twice (EW5).
- **Sequencer.** Holds SWEEP.a and the packet index; points the alias; **prefetches** the next packet's bundle and Stay value from a block no remaining window may write; latches the GO's **take-set** at the strobe.
- **STP** (4·0) `Accm ← Accm + clamp(src − Accm, −Temp, +Temp)`; **BCP** (4·1) lands the take-set in housekeeping (≤ 10 clocks slot-parallel), raises inbox-taken.
- **Stay value.** The Core's new `stay_value` pin (IND-reverse, read at the Stay's execute clock, held) is driven by StayVal.p: N for a packet Stay, 0 for housekeeping, so its literal applies.
- **Packet window**: 25 instructions (one STP, three ADD) → N ≥ 29 → **N_MIN = 32**.

### 8. What fell away / 落ちたもの

CMT, RTW (routing moved to +0xE, the slot CUR vacated), WSV (the sequencer writes the Stay value), E3, E7. The profile has **no Q-band citizen**: at a packet boundary it asks the Core for nothing, so the Core's single reservation slot (C3-F26) is free for the transfer that re-enters the next packet. Under Mode T every boundary would have held a CMT *and* needed that transfer — the E7 conflict would have cost a clock per packet.

### 9. Found while building the oracle / オラクル構築中の発見

The phase advance `PH0 += OM0` is modular by definition, but the inherited model's ADD saturated and raised E8 on every wrap. **W-F30**: ADD/SUB wrap modulo 2³²; E8 stays with MUL/MAC.

---

## Decision Points / 決定点

| # | Point | Alternatives | Chosen | Rationale |
|---|---|---|---|---|
| DP-1 | Level glide | software clamp (35, E8 at edges) · STP | **STP** | 9 instructions; the result lies between LP and LPT, so it cannot overflow |
| DP-2 | Selecting "the block now playing" | computed ADRS (reopen W-F1) · computed FG branch (reopen W-T3) · alias | **alias** | purity kept; the same hardware prefetches bundles |
| DP-3 | Masked copy | arithmetic masking · hardware copy | **BCP** | one instruction; the datapath stays the only writer |
| DP-4 | Delta writes under a flip | accept two-window deltas · mirror to both pages · single store | **single store** | 0/2,000 vs 1,263/2,000 |
| DP-5 | Where L1's guarantee lives | page swap (CMT-2) · bundle latch | **bundle** | L1 reads once per packet; W-F22 generalized; the customer's candidate (b) |
| DP-6 | Where GO items land | in packet windows · in housekeeping | **housekeeping** | every block is inside its window; bound = one sweep |
| DP-7 | ADD overflow | saturate + E8 · wrap | **wrap** (W-F30) | phase slots are modular |
| DP-8 | Packet repetition in the Core score | R1 unrolled · R2 one body | **R2 preferred, R1 for bring-up** (architect) | both kept selectable |

---

## Supersession History / 置き換え履歴

| Was | Became | Where |
|---|---|---|
| Page pair; CMT at every packet boundary | single block store; bundle latched at Stay Set; write windows | W-F24; Map v0.3 §5 |
| Mode T / Mode W; CUR at +0xE of block 0 | sweep sequencer + CUR alias; +0xE = RT.OUT | W-F28; Map §4, §6 |
| "Programs rewrite only what changed" (F-F14 adopted early, W-R8) | exact delta writes because there is one store | W-F9 → R |
| WSV writes StayVal.s | the sequencer writes it; WSV RESTRICTED | W-F22 amended; W-F28 |
| `LP ← LP + LE0` (linear A0 · AR1 · AR2 before that) | `LP ← STP(LP, LPT, LE0)` | W-F29; W-F26 |
| Mid-sweep inbox re-fill (v0.2 note) | withdrawn; P ≤ 8 per sweep in the first implementation | PR-5 |
| ADD saturating with E8 | ADD/SUB wrap | W-F30 |

---

## Evidence / 根拠

`03_Sample_Implementations/tools/` (oracle, not silicon):

| Run | Result |
|---|---|
| `sweep_sim.py <customer oracle> 20000 {2026, 7, 42}` | 60,000 samples · 215,627 packet plays · 4,174 GOs (1,175 at full load) · **0 mismatches** against a reference built from WPMS Ch.3 §3.4.3 and Ch.5 §5.3–5.4, with the glide law imported from the customer's `step_toward` · worst sweep **2,064 of 2,083** clocks |
| `negative_tests.py` | **13/13**; a mutant window that advances PH0 twice: 2,798 mismatches in 3,000 samples |
| `isa_fold_w.py` | 16 instructions (master 18 − 5 + 3), fold log cites every W-ID |
| `pfasm_tools_w.py exp_maclaurin_w.pfasm` | 27 instructions, CLEAN, max error 7.39e-09 — unchanged numerics without CMT |

### Measurement pitfalls (recorded because they were made) / 実際に踏んだ落とし穴

1. **A generator that stops generating looks like a clean run.** The first sweep oracle produced 53 GOs in 12,000 samples: an empty GO (no blocks, no sweep word) was never taken, so it was never cleared, and traffic stopped. Count the stimulus, not only the mismatches.
2. **A generator that breaks a neighbour's rule finds your missing backstop.** Random N changes that ignored the switch's Σ N ≤ NMAX rule produced 2,899-clock sweeps. The fix went to both sides: the generator obeys the switch (Ch.5 §5.4.4), and BCP now re-checks Σ N of the sweep in effect after block-only GOs (EW5).
3. **A failed rule is not an impossibility proof.** Remedy (i) lost to a two-pass rule written in a hurry; a careful per-slot mirror could pass. The recorded finding is fragility, and the choice rests on (ii)'s zero, not on (i)'s failure.
4. **Nominal Core clocks.** The oracle uses wake = 2, 4 control clocks per packet, 3 in housekeeping. They stand for the Core's commitments; Layer 4 replaces them.

---

## Acceptance Conditions / 受け入れ条件

Deliverable 2 §6 (D2-1 … D2-5) and Deliverable 3 §8. In short: every bundle equals the reference state of its block for that sample; K runs 0…N−1 with no gap; strobe → first packet ≤ 4 clocks; a block with N outside [32, 2,048] never reaches L1.

---

## Design Pattern Candidates / 設計パターン候補

| Pattern | Statement |
|---|---|
| **The Back Buffer Is Two Frames Old** | under a pointer-flip commit, untouched values are one commit stale; delta writes are safe only across two windows |
| **Present, Don't Swap** | when the consumer reads at known instants, protect the instant (a latched bundle), not the interval (a page pair) |
| **Write Windows** | a producer may write an item anywhere between two of the consumer's reads of that item; enforce it by construction, not by care |
| **Empty Q Band** | a Formation that needs nothing at the boundary leaves the Core's reservation slot to control flow |
| **Evidence-Driven Retraction** | (shared with the customer's trace of 2026-09-24) a ratified design withdrawn with its evidence, recorded rather than hidden |

---

## Resumption Hooks / 再開フック

**A — The Core score.** *Write the WPMS score in Core syntax both ways: R2 (one packet body, data-driven re-entry at timeup — preferred) and R1 (eight unrolled positions — bring-up). Which Core primitive carries R2's conditional re-entry without a clock?*

**B — Layer 4.** *On DE10-nano: g across consecutive packet Stays, strobe → first packet, window clocks (N_MIN), BCP duration in the chosen store organization.*

**C — Master absorption.** *Should the master take STP, BCP, bundle presentation and write windows as optional equipment, and restate F-F14's consequence as a two-window rule (W-D22)?*

**D — Customer alignment.** *PR-1 … PR-5; the paused-block reading of CR3-C1; Appendix 5.A.2's +0xE.*

**E — Generation.** *Claude Code: generate the sequencer and a slot-major block store, with `sweep_sim.py` as the golden model and Deliverable 2's acceptance conditions as the testbench plan.*

---

## Errata Noticed in Earlier Documents / 旧文書で気づいた誤り

- Register Map v0.2 §2 note and Register W v0.4–v0.5 (W-R8): "programs rewrite only what changed" — true only for two-window differences under a pointer flip. Superseded.
- The first-week trace (2026-09-07) and Hackaday Log #1 describe the page swap and CUR as current; they are dated records.

---

## End of Trace / 軌跡の末尾

> *Protect the instant the consumer reads, not the time between.*
> *消費者が読む瞬間を守れ。その間の時間ではなく。*

> *A retraction with its evidence is worth more than a decision without one.* — the customer's trace, 2026-09-24
> *根拠を添えた撤回は、根拠のない決定より価値がある。*

This trace is released into the public domain under CC0 1.0 Universal. Replay it. Resume it. Surpass it.

本軌跡は CC0 1.0 Universal のもとパブリックドメインに公開される。再生せよ。再開せよ。超えてゆけ。
