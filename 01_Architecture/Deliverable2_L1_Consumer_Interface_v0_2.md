# PTSG-WPMS-Formation — Deliverable 2
# The L1 Consumer Interface / L1 消費者インターフェース

*v0.2 DRAFT (as built) · WPMS-Formation amanuensis · 2026-10-05 · CC0 · rows first (F-F8).*
*Anchored in Decision Register W v0.8 as **W-F17**. Changes from v0.1: the L1 face is one clock after Stay Set, uniformly (SD-11); T_wake, the floor and the bundle equality measured on silicon (C1–C3, 2026-10-04); §5 adds the proposed half-rate face (W-F37). Register map: v0.4.* Answers WPMS Ch.3 §3.8: CR3-B1, CR3-B2, CR3-R1, CR3-T1, CR3-T3 (and the L1-visible part of CR3-C1). Register map: `L2_Formation_Register_Map_v0_3.md`.*

*成果物 2。L1 パイプラインが L2 Formation から受け取るものの全て——パケット開始時に一度だけラッチするバンドル八値と、三本のレーン——と、その時刻の約束を定める。W-R6 により、本書が定めるのは信号・幅・時刻・保証であり、L1 内部と Q の解釈は WPMS 第3章の所有。*

---

## 1. The interface in one paragraph / 一段落で

At the **Stay Set** clock of every packet Stay, L1 latches a **bundle** of eight values — PH0, PHD1, PHD2, LP, LS0, LAD1, LAD2 and RT.OUT of the block that packet plays. It then runs its difference engine for the Stay, one bin per clock, indexed by the Core's Stay counter **K** while **bin_valid** is high. L1 reads nothing else from L2, ever. The bundle it latches is always a whole, consistent packet state for the current sample: the profile prefetches it from a block that no one may write at that moment, and the Core starts the next packet on the clock after the last bin of the previous one (g = 0).

---

## 2. Signals / 信号

| Signal | From | Width | Meaning | Requirement |
|---|---|---|---|---|
| `bun_ph0`, `bun_phd1`, `bun_phd2` | L2 bundle port | 32 each | phase slots of the packet (modular) | CR3-B1 |
| `bun_lp`, `bun_ls0`, `bun_lad1`, `bun_lad2` | L2 bundle port | 32 each | level and shape slots (log₂) | CR3-B1, CR3-A1 |
| `bun_rt` | L2 bundle port | 2 (of a W16 slot) | routing: bit 0 = L, bit 1 = R | CR3-R1 |
| `packet_start` | derived: the Core's Stay Set, seen **one clock later** through the registered timing signals | 1 | the clock on which L1 latches the bundle; L1's K = 0 on this clock | CR3-T3 |
| `bin_valid` | TS_PKT as registered (one clock after the word executes) | 1 | bins of this packet are in flight; low in housekeeping and sleep | CR3-T3 |
| `K` | Core stay counter, **delayed one clock** to the same face | 12 | bin index k of the packet (ruling 2026-09-02: K = k), prescaler = 1 | CR3-T3 |

**The one-clock face (SD-11).** The Core's `timing_signals` are registered: a word's D16–D31 appear one clock after the word executes. Rather than decode the Stay Set from `state_number`, the profile presents the whole L1 face one clock late, uniformly: `bin_valid(c) = TS_PKT(c)`, `K(c)` = the counter's value at c−1, `packet_start` one clock after the Stay Set. Every relation of §3 and §4 holds unchanged; the absolute offset is one clock. Verified: every packet of the sweep cosimulation has N bins with K = 0 … N−1 (RTL-SIM), and on silicon 45 bundles latched on `packet_start` equal the model (C1–C3).

`TS_PKT` is a timing-signal bit assigned by the profile (Deliverable 3 §4). It is set in the packet's **Stay Set word and Stay word** — the two words whose D16–D31 carry timing signals; the window's Global words carry operands there — and clear in every other word. The value held through the window is therefore correct whichever option the Core adopts for its Tie C3-T1 (which word's D16–D31 is held during the window).

**L1 never reads** (CR3-B2, adopted): N, TAG, LE0, LPT, OM0, OMD1, OMD2, the inbox, the sweep word. It has no address into the L2 space.

---

## 3. Timing / 時刻

```
clk (Core)     │ s  │s+1 │ .. │s+N-1│ s+N │s+N+1│ ..
state          │ SS │ window …     Stay (wait)   │ SS' │ window' …
— the L1 face, one clock later (SD-11) —
clk (face)     │s+1 │s+2 │ .. │ s+N │s+N+1│s+N+2│ ..
packet_start   │ ▔▔ │    │    │     │ ▔▔▔ │     │
bin_valid      │ ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔│ ▔▔▔▔▔▔▔▔▔▔▔▔▔
K              │ 0  │ 1  │ .. │ N-1 │  0  │  1  │ ..
bundle latched │ B_p│    │    │     │B_p+1│     │
bin            │ 0  │ 1  │ .. │ N-1 │ 0'  │ 1'  │
```

- **Latch.** On the `packet_start` clock the bundle port already shows the packet's values (they were prefetched during the previous packet, or after the housekeeping window for the first packet of a sweep). L1 latches all eight on that clock — zero gap (CR3-B1).
- **Zero gap between packets (CR3-T1).** The next packet's Stay Set is the clock after the last bin (K = N−1) of the previous packet. From the profile's side nothing stands in the way: the profile issues no Q-band command at packet boundaries (no CMT exists in this profile), so the Core's single reservation slot is free for the control transfer that re-enters the next packet. The Core has committed to g = 0 (architect, 2026-09-26); the value is measured in Layer 4.
- **First packet of a sweep.** strobe → wake → Stay Set → the face: **T_wake = 2 clocks on silicon** (C1, C2; the Core's own Stay Set is 1 clock after the strobe in the dispatch form, the face one later), ≤ 4 (CR3-T2).
- **Empty sweep (P = 0).** No packet_start, bin_valid stays low; L1 accumulates nothing and the accumulators close at zero on the next strobe (WPMS Ch.3 §3.6.3).
- **Packet length.** Exactly N clocks for N ≥ N_MIN. The Core's floor for the 25-instruction window is **30** (a windowed Stay needs one S_WAIT clock, SD-12; measured RTL-SIM and SILICON), so N_MIN = 32 holds with 2 clocks of margin. A block with N outside [N_MIN, NMAX] is refused at prefetch (EW2) — it can never reach L1.

---

## 4. What the bundle guarantees / バンドルの保証

**B-1 Whole.** The eight values come from one block at one instant; no value belongs to a different sample or a different block.

**B-2 Current.** For a packet playing block b at sample n, the bundle equals the block's state for sample n: [S] slots advanced exactly once per sample while b is listed in the sweep, [P] slots as last written by a GO whose APPLIED_SAMPLE ≤ n.

**B-3 One latch, one packet.** L1 latches each listed block exactly once per sweep (the sweep word never lists a block twice — EW5).

Why they hold (Register Map v0.3 §5): the only writes a block receives in a sweep happen after its own latch (its packet window, through the CUR alias) or after every latch of the sweep (housekeeping); the prefetch reads a block that no window of the sweep may write. B-2 is the L1-visible form of the coherence invariant CR3-C1; it is proven in Deliverable 3 §8 and tested by the sweep oracle.

---

## 5. Realization notes (Arena) / 実装の余地

| Item | Reference | Alternatives |
|---|---|---|
| Bundle port | a 7 × 32 + 2-bit **staged register** filled by the sequencer; L1's running registers are the presented copy — W-F22's staged/presented pair widened to a bundle (the customer's candidate (b)) | PPM held in registers with a wide read (candidate (a)) |
| Block store organization | **slot-major**: sixteen 8 × 32 memories, one per slot, so a bundle (and a BCP block copy) moves in one clock | word-serial store with an 8-clock prefetch (still inside N_MIN) |
| TS_PKT decoding | a Core timing-signal bit, taken one clock late with the whole face (SD-11) | a `state_number` range compare |
| **Half-rate face (proposed, W-F37)** | with L1 at 100 MHz under a 50 MHz L2, the face adds **bit −1** under K: L1 sees {K, half} at 100 MHz, two bins per L2 clock; `packet_start` and `bin_valid` are L2-clock signals; N stays in bins, even, ≥ 64 (EW2) | — |

---

## 6. Acceptance conditions for testbenches / テストベンチの受け入れ条件

| AC | Condition | Oracle |
|---|---|---|
| **D2-1** | On every `packet_start`, the eight bundle values equal the reference model's state of the played block for that sample | ORACLE 60,000 samples 0 mismatches; RTL-SIM 36,000 sweeps; **SILICON 45 / 45** (C1–C3) |
| **D2-2** | `K` runs 0…N−1 with `bin_valid` high for exactly N clocks per packet; the next `packet_start` follows K = N−1 on the next clock | **SILICON: g = 0** (C2, 8 packets) |
| **D2-3** | strobe → first `packet_start` ≤ 4 clocks | **SILICON: 2** (C1, C2) |
| **D2-4** | A block with N < N_MIN or N > NMAX never reaches L1 (EW2 instead) | `negative_tests.py` N13; **SILICON: C5 EW2**, pipeline silent, halt after 9 clocks |
| **D2-5** | Nothing in L1 addresses the L2 space; the bundle port is its only input from L2 | design review |

---

## 7. Customer requirements answered / 顧客要求への回答

| CR | Answer |
|---|---|
| CR3-B1 | Met: eight values latched on the Stay Set clock from a prefetched staged bundle (§3, §5). |
| CR3-B2 | Met (adopted since v0.2). |
| CR3-R1 | Met: RT.OUT is +0xE of the block and travels in the bundle. |
| CR3-T1 | **Met on silicon: g = 0** (C2). |
| CR3-T3 | Met: `packet_start`, `bin_valid`, `K` as in §2. |
| CR3-C1 | L1-visible form B-2; proof and evidence in Deliverable 3 §8. |

---

*End of Deliverable 2 v0.2.*
