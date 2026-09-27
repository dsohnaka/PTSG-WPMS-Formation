# PTSG-WPMS-Formation — Deliverable 1
# L2 Formation: ISA-Visible Register Map / L2 Formation の ISA 可視レジスタマップ

*v0.3 DRAFT · WPMS-Formation amanuensis · 2026-09-26 · CC0 · rows first (F-F8).*
*Anchored in Decision Register W v0.7 as W-F18 (block format), W-F21 (integer widths), W-F22 (Stay-value path), W-F23 (SHV), W-F24 (single block store, bundle presentation), W-F25 (CMT/RTW omitted), W-F26 (STP), W-F27 (BCP), W-F28 (sweep sequencer), W-F29 (log-domain slots), W-F30 (modular ADD/SUB). Rulings through 2026-09-27 applied.*
*Master: PTSG-CPU-Formation @ `ad43cc2` (contains the 2026-09-03 fixes). Core: PTSG-Core @ `1b58ebc`, `stay_value` per CHANGES_Layer1_stay-value_2026-09-26 (PROVISIONAL). Customer: FPGA_Spectrum_Engine_OpenPrompt @ `891fce6` (Layer 1 Ch.1–5, Appendix 5.A).*

*成果物 1 v0.3。ISA が語るのは整数・番地・幅・書き手・書込み窓だけであり、Q の解釈と L1 への配線は WPMS 第3章の所有(W-R6)。本版は付録 5.A.2 のスロット表を正本とし、2026-09-26 の裁定(Mode T 撤回・バンドル提示・拡張二命令・シーケンサ別名)を反映する。*

---

## Changes from v0.2 / v0.2 からの変更

- **Mode T and Mode W retracted** (W-R-09-26). They relied on "rewrite only what changed" under pointer-flip commits, which holds only for two-window differences; an oracle model showed Mode T losing advances for P ≥ 2. Replaced by **bundle presentation** (§4).
- **No page pair.** One block store; L1 never reads it except through bundles latched at packet start; the datapath writes each block only inside its **write window** (§5). PPM-1/PPM-2 RESTRICTED for packet blocks (ruled 2026-09-26). CMT and RTW omitted (§3; W-R12, ruled 2026-09-27).
- **Slots per the customer's Appendix 5.A.2** (log-domain amplitude, LPT, LS0), with one change: **+0xE holds RT.OUT** (CUR retired with Mode T).
- **Two instructions added** (approved): **STP** step-toward, **BCP** masked block copy. **One region added**: the CUR alias, driven by the sweep sequencer (approved).
- **ADRS widened to 9 bits** for the alias and status regions.

---

## 0. Scope / 範囲

Fixed here: register names, instruction rows the profile adds or removes, the 9-bit L2 address space, the block format, write windows, and the profile's error rows. Not fixed here: Q-conventions (WPMS Ch.3; recorded in §6 for reference only), L1 internals, wiring, the input switch (WPMS Ch.5). The L1 consumer interface is Deliverable 2; the sweep choreography is Deliverable 3.

Layers: **L1 pipeline** (hardwired) · **L2 Formation** (this profile; one Stay = one packet; Stay counter = k) · **L4 Formation** (external controller, outside WPMS).

---

## 1. Width classes / 幅クラス

| Class | Bits | Used for |
|---|---|---|
| **W32** | 32 | datapath word; every parameter slot except N, TAG, RT.OUT |
| **W16** | 16 | TAG, RT.OUT (2 bits used), slot masks |
| **W12** | 12 in a W16 port | N, Stay value, quartet K / I / SN / SSS |
| **W5** | 5 | SHV |

W-R1 is satisfied: both 16-bit and 32-bit integer register formats are exposed.

---

## 2. Register file / レジスタファイル

| Register | Class | Datapath access | Written by | Consumed by | Note |
|---|---|---|---|---|---|
| Accm | W32 | read/write | mode-1 ops, LDM, LDA | everything | master |
| Temp | W32 | read/write | SWP, STA | MUL/MAC multiplicand; **STP rate** | master |
| ADRS | **9-bit** | write only (SAD, LDM/STM post-increment) | — | LDM, STM, source 2 | STA→ADRS RESTRICTED (W-F1) |
| SHV | W5 | write only | WSH | MUL, MAC | W-F23 |
| **StayVal.s** | W12 | none | **sweep sequencer** (prefetch of N of the next packet's block) | StayVal.p | W-F22 as amended by W-F28 |
| **StayVal.p** | W12 | none | loaded at every Stay Set: **N for a packet Stay, 0 otherwise** | **PTSG-Core `stay_value` pin** (C4-F15; read at the Stay's execute clock, C4-F16) | W-F22 |
| **SWEEP.a** | 28-bit | read (0x119) | BCP (sweep item); reset → P = 0 | sweep sequencer | W-F28 |
| LoopVal.s | W12 | write (WLV) | WLV | none at present (no Core pin) | TRACK |
| JumpVal | W12 | write (WJV) | WJV | BG computed dispatch only (FG: W-T3) | master |
| K / I / SN / SSS | W12 | read (sources 3–6) | Core | programs; **K is L1's k** | quartet |

Removed relative to the master: data stack and SP (W-T1); the PPM page pair and RT page pair (W-F24/W-F25). Added: StayVal.p, SHV, SWEEP.a, the CUR alias.

---

## 3. Instruction rows of this profile / 命令行

All Formation instructions of this profile are **BG-only** (FG → E1 at the Core, Q → E2). The profile has **no Q-band citizen**: with no page to swap, the Q band's single reservation slot is left entirely to the Core's control transfers (Deliverable 3 §4).

| Mode·sub | Mnemonic | Semantics | Status |
|---|---|---|---|
| 1·0–1·7 | LDA STA ADD SUB MUL MAC SWP SFT | master semantics, except: **ADD/SUB wrap modulo 2³²** (W-F30); MUL `Accm ← (Accm × src) >> SHV`; MAC `Accm ← ((Accm × Temp) >> SHV) + src`; MUL/MAC overflow → E8 | INHERIT (+W-F23, W-F30) |
| 2·0 | SAD | ADRS ← literal (9 bits) | INHERIT |
| 2·1 | LDM | Accm ← [ADRS]; ADRS += 1 (reads the L2 space of §4) | INHERIT, space per W-F24 |
| 2·2 | STM | [ADRS] ← Accm; ADRS += 1 (subject to write windows, §5) | INHERIT, rule per W-F24 |
| 2·3 | RTW | — | **OMIT** (W-F25): routing lives at +0xE of each block |
| 2·4 | CMT | — | **OMIT** (W-F25): no page pair |
| 2·5, 2·6 | PSH, POP | — | OMIT (W-T1) |
| 3·0 | WSV | — | **RESTRICT** (W-F28, W-R12): the sequencer is the sole writer of the Stay-value path |
| 3·1 | WLV | LoopVal.s ← Accm[11:0] | INHERIT (unconnected) |
| 3·2 | WJV | JumpVal ← Accm[11:0] | INHERIT |
| 3·3 | WSH | SHV ← Accm[4:0] | W-F23 |
| **4·0** | **STP** src | `Accm ← Accm + clamp(src − Accm, −Temp, +Temp)`; the difference is taken in 33 bits; **Temp < 0 → EW6**. The result lies between the old Accm and src, so it can never overflow. | **W-F26** |
| **4·1** | **BCP** | Masked copy of the GO's **take-set** (§7): for every taken, not-yet-copied block b, slots i with mask bit i set (bits 13, 14 ignored) ← inbox; mask bit 16 → +0xE ← staged RT.OUT; the taken sweep item → SWEEP.a (EW5-checked); then Σ N of the sweep in effect is re-checked (EW5); finally **inbox-taken** is raised. **Legal only in the housekeeping window** (else EW4). Duration: 1 + one clock per copied item in the reference realization (≤ 10). | **W-F27** |

Mode 4 is the profile's extension mode (W-R14), used so that no master code is re-used; if the master absorbs STP/BCP, their encoding is the master's to choose (path independence).

---

## 4. L2 address space (ADRS = 9 bits) / アドレス空間

| Range | Region | Read | Write |
|---|---|---|---|
| `0x000–0x07F` | **Block store**, block b at `0x10·b`, slot i at `+i` | always | **HK window only** (else EW4) |
| `0x080–0x0FF` | **Inbox view**, same layout; `+0xE` shows the staged RT.OUT of the block; `+0xD` reads 0 | always | never (EW3) |
| `0x100–0x10F` | **CUR alias** → block `order[q]` of the packet now playing | in a packet window (else reads 0) | **packet window only** (else EW4) |
| `0x110–0x117` | **COMMIT[b] view**: [15:0] slot mask · [16] RT.OUT bit · [29] copied · [30] in take-set | always | never (EW3) |
| `0x118` | staged sweep word (inbox) | always | never (EW3) |
| `0x119` | **SWEEP.a** — sweep word in effect | always | never (EW3) |
| `0x11A` | sequencer status: [3:0] q · [7:4] P · [8] HK phase | always | never (EW3) |
| other | — | E5 | E5 |

CR5-I1's requirement that the mask and the staged RT.OUT be readable by the datapath is met by `0x110–0x117` and the inbox view's `+0xE`.

---

## 5. Write windows — why L1 sees whole packets / 書込み窓

L1 reads a block only by latching its **bundle** at the Stay Set of the packet that plays it (Deliverable 2). Between two latches of the same block — one in sweep n, the next in sweep n+1 — the block is free to be written; that interval is its **write window**. The profile makes every datapath write fall inside the written block's window by construction:

- In a **packet window** (the BG window of packet q), the only writable block is `order[q]`, through the CUR alias. Its bundle was latched at this Stay Set; its next latch is in the next sweep. The sweep word never lists a block twice (EW5), so no other block of this sweep can be touched.
- In the **housekeeping window** that closes the sweep, every block's latch of this sweep is past and its next latch is in the next sweep: all blocks are writable, and BCP lands the GO's items there.
- The sequencer prefetches the next packet's bundle from a block that no window of this sweep may write, so the prefetched bundle equals what L1 would have read at the latch.

This replaces the page pair's guarantee (CMT-2, whole worlds) with a per-packet one (whole bundles), and delta writes become exact: there is only one store, so what a window does not touch is simply the current value.

---

## 6. Block format (canonical: WPMS Ch.5 Appendix 5.A.2, with +0xE) / ブロック形式

| Offset | Slot | Class | Kind | Advance per sample (L2) | L1 bundle | Q (WPMS Ch.3, reference only) |
|---|---|---|---|---|---|---|
| +0x0 | **N** | W12 | [P] packet length, bins; **N_MIN ≤ N ≤ NMAX** (EW2) | — | — | integer |
| +0x1 | TAG | W16 | [P] free for the controller | — | — | integer |
| +0x2 | **LP** | W32 | [S] level, log₂ | `LP ← STP(LP, LPT, LE0)` | yes | Q6.26 |
| +0x3 | LAD1 | W32 | [P] shape, first difference | — | yes | Q8.24 |
| +0x4 | LAD2 | W32 | [P] shape, second difference | — | yes | Q2.30 |
| +0x5 | **LE0** | W32 | [P] glide rate ≥ 0 (EW6) | — | — | Q6.26 |
| +0x6 | PH0 | W32 | [S] phase of bin 0 | `+= OM0` (mod 2³²) | yes | Q0.32 modular |
| +0x7 | PHD1 | W32 | [S] first phase difference in k | `+= OMD1` | yes | Q0.32 modular |
| +0x8 | PHD2 | W32 | [S] second phase difference in k | `+= OMD2` | yes | Q0.32 modular |
| +0x9 | **LPT** | W32 | [P] level target | — | — | Q6.26 |
| +0xA | OM0 | W32 | [P] per-sample increment of PH0 | — | — | Q0.32 modular |
| +0xB | OMD1 | W32 | [P] per-sample increment of PHD1 | — | — | Q0.32 modular |
| +0xC | OMD2 | W32 | [P] per-sample increment of PHD2 | — | — | Q0.32 modular |
| +0xD | — | — | reserved (inbox mask bit 13 ignored) | — | — | — |
| +0xE | **RT.OUT** | W16 | [P] output routing, bit 0 = L, bit 1 = R | — | yes | integer |
| +0xF | **LS0** | W32 | [P] shape offset at k = 0 | — | yes | Q12.20 |

**Bundle** (Deliverable 2): PH0, PHD1, PHD2, LP, LS0, LAD1, LAD2, RT.OUT. **L1 never reads** N, TAG, LE0, LPT, OM0, OMD1, OMD2 (CR3-B2).

**Difference from 5.A.2**: `+0xE` was "CUR (block 0, Mode T)". With Mode T retracted, `+0xE` holds RT.OUT inside the store; writers still stage RT.OUT in `RTOUT[b]` and select it with mask bit 16, and mask bit 14 stays ignored, so the customer's switch-side map (Ch.5 §5.6.2) is unchanged.

---

## 7. Inbox, take-set, sweep word / inbox・取込み集合・掃引語

- The **inbox** is written only by the input switch (WPMS Ch.5), read-only to the datapath.
- At each synchronized strobe the sequencer latches the **take-set**: the blocks and sweep item armed at that moment. BCP in the housekeeping window of the same sweep copies exactly the take-set, raises **inbox-taken** (CR5-I3), and the switch then unfreezes and publishes APPLIED. Items armed after the strobe wait for the next one.
- **Sweep word** (Ch.5 §5.4.4): `[3:0] P (0…8) | [27:4] order`. SWEEP.a is the word in effect; it changes only inside BCP, between sweeps. Rejected at BCP (EW5): P > 8, a block repeated among the first P entries, or Σ N of the listed blocks > NMAX. BCP also re-checks Σ N of the sweep in effect after block-only GOs.
- **Paused blocks.** A block not listed in the sweep word is not advanced; its [S] slots freeze and resume from there when it is listed again (the profile's reading of CR3-C1; customer confirmation requested, Register W §7).

---

## 8. Profile error rows / プロファイル E 行

| Row | Cause | Action |
|---|---|---|
| E1, E2 | Formation instruction in FG / in Q (the profile has no Q citizen) | inherited |
| E4 | reserved or removed row: PSH, POP, CMT, RTW, WSV; STA→ADRS | Error HALT |
| E5 | ADRS outside §4's map | Error HALT |
| E8 | MUL/MAC overflow (ADD/SUB wrap and never raise E8, W-F30) | inherited routing |
| **EW2** | the sequencer prefetches a block with **N < N_MIN or N > NMAX** | Error HALT |
| **EW3** | STM into a read-only region (inbox, COMMIT view, sweep words, status) | Error HALT |
| **EW4** | write-window violation: store written directly outside HK; CUR written outside a packet window; BCP outside HK | Error HALT |
| **EW5** | invalid sweep word at BCP (P > 8, repeated block, Σ N > NMAX), or Σ N of the sweep in effect > NMAX after a block-only GO | Error HALT |
| **EW6** | STP with Temp < 0 | Error HALT |

E3 and E7 vanish with CMT. E6 vanished with the data stack.

---

## 9. Constants and reset / 定数とリセット

| Constant | Value | Kind · unit · scope |
|---|---|---|
| NMAX | 2,048 | bins per module per sweep (design variable, bound to DE10-nano) |
| N_MIN | **32** | bins per packet; derived from the packet window (25 instructions + 4 Core clocks = 29, oracle-counted), rounded up with margin; to be measured in Layer 4 |
| BLOCKS | 8 | blocks per module |

**Reset (CR5-R1)**: SWEEP.a ← P = 0; take-set empty; block store contents undefined (the ROM port of the switch loads the test origin through the inbox). The Formation runs empty sweeps — wake, housekeeping, sleep — and accepts the inbox from the first strobe.

---

*End of v0.3. Next: Layer 4 measurement of N_MIN, T_wake, g and BCP duration on DE10-nano.*
*v0.3 の末尾。次は DE10-nano での N_MIN・T_wake・g・BCP 所要の実測。*
