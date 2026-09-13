# Hackaday.io project — launch text / Hackaday.io プロジェクト発足テキスト

*Non-normative worksheet. Copy into the Hackaday.io project form; edit freely. English-primary (Hackaday.io convention of this ecosystem); a Japanese gloss follows each block for the architect.*

---

## Project name

**PTSG-WPMS-Formation**

## Summary (≤ 140 chars)

The first subtraction profile of the PTSG master ISA: the packet engine that lets one gesture reach 2,048 oscillators, seam-free.

*(JA: PTSG マスター ISA 最初の引き算プロファイル——一つの身振りを 2,048 のオシレータへ継ぎ目なく届けるパケットエンジン。)*

## Tags

fpga · synthesizer · additive-synthesis · isa · open-prompt · cyclone-v · de10-nano

## Links

- Repository: `https://github.com/dsohnaka/PTSG-WPMS-Formation`
- Master ISA: https://github.com/dsohnaka/PTSG-CPU-Formation · Core: https://github.com/dsohnaka/PTSG-Core
- Parent project: https://hackaday.io/project/205582-fpga-spectrum-engine

## Description

FPGA Spectrum Engine has 10,240 oscillators and, until recently, no humane way to tell them what to do: five years ago the architect worked out that a drawbar per oscillator would run 300 metres. Wave-Packet Modulation Synthesis (WPMS) is the answer to that: oscillators are addressed in *packets* — runs of adjacent bins described by a dozen numbers (an initial amplitude, two ratios, a phase, its first and second differences across the packet, and their per-sample increments) — and a hardwired difference engine unfolds those numbers into 2,048 bins per sample period, one bin per clock.

Something has to write those dozen numbers, per packet, per sample, and switch them without a click. That something is a tiny instruction-driven timing core (PTSG-Core) wearing a data-processing "formation" (PTSG-CPU-Formation, the master ISA). **PTSG-WPMS-Formation is the first *subtraction profile* of that master**: it keeps a decision register in which every choice is keyed to a master decision — inherit, restrict, omit, extend — and adds only what the master deliberately left to its first customer.

What the first week of the profile produced:

- **One Stay is one packet.** The Core's Stay counter *is* the difference engine's *k*. Packet length is the Stay value, supplied by the formation through a two-stage register so the Core always sees a frozen number — no packet can be stretched mid-flight.
- **The ISA speaks integers.** Every register and page slot has an integer width (16 or 32 bits). Fixed-point meaning belongs to programs: a program writes its shift register (`WSH`) before its first multiply-accumulate. The master's very first program, re-run on the profile with two extra instructions in front, computes *e* to the same digits; without them it overflows — the ISA does not know your Q.
- **A 256-word register map**: eight 16-word packet blocks (shadow written, active read, swapped on the trailing edge — zipper noise is impossible by construction) plus an *inbox* that external writers use so the shadow keeps a single writer. Accepted by the WPMS side as customer.
- **Nothing hand-edited.** The profile's translation contract is generated from the master's (itself generated from the master's normative chapter) by folding the register mechanically; a validator rejects what the register removed.

Everything is Open Prompt: the specification, the reasoning traces (including the correspondence between the three AI amanuenses — master, profile, customer — each a separate session), and the reference tools. Numbers bind to DE10-nano and are measured, not promised.

*(JA 要旨: 10,240 オシレータに人間らしく指示する唯一の道が「パケット」——十数個の数で記述される隣接ビン群——であり、それを毎パケット・毎サンプル書き換えて無音で切り替えるのが本 Formation。最初の一週間で、Stay = パケット、整数 ISA とプログラム所有のシフト、256 語のレジスタマップ、手編集なしの契約生成鎖が成立。三つの祐筆セッション間の往復も第2層として公開。)*

---

## Log #1 — The Profile Opens Its Office / プロファイル、事務所を開く

*(first build log; ~600 words)*

Every spin-off in this ecosystem is announced with the same two words: *measured, not promised.* This one begins with a smaller promise kept: the profile read its constraints before its headlines.

The charter for this session prescribed a reading order — the master's hand-off brief, the Core's trailing-edge principle, the master's five chapters, then WPMS's own first two chapters *with an errata sheet in hand*. The amanuensis read in that order and kept, unfiled, everything that disagreed with something else. Eighteen items by the end. The architect said: hold them, some will resolve themselves. Most did. Four went upstream to the master's amanuensis, who accepted all four as defects and fixed them within a day — and wrote back that "the second amanuensis is a verification layer the master cannot supply itself." That sentence is the reason profiles exist.

Two discoveries shaped the ISA.

The first was the architect's: the difference engine's *k* — which bin we are on — is bin-layer information, needed at clock rate, and it is simply the Stay counter's output. So a packet *is* a Stay, and packet length *is* the Stay value. The Core then told us how its external Stay-value input behaves: twelve bits, captured when the Stay instruction executes, and — importantly — changeable right up to the trailing edge; lower it below the running counter and the Stay takes an extra lap. The master's law had promised "sample once, frozen." The Core doesn't freeze. So the profile does: a staged register the program writes, and a presented register the Core reads, loaded only at Stay Set. From the Core's side it is exactly the law; from the program's side there is no way to stretch a packet by accident.

The second came from the master's amanuensis, reading the ruling that the ISA speaks integers and fixed-point meaning belongs to programs: that is coherent, they said, only if a program can express the multiply-accumulate's realignment. Correct. The profile added a five-bit shift register and one instruction to write it. The master's first program — ten Horner steps computing exp(x) — runs on the profile with `LDA #28; WSH` in front and produces the same digits as the master's published run. Without those two lines it overflows on every step. The ISA does not know your Q; the program does, and now it can say so.

Deliverable 1 followed: a 256-word map. Eight packet blocks of sixteen words, active and shadow, swapped atomically on the trailing edge. Amplitude is stored as geometric differences (initial value, ratio, ratio-of-ratios — the last is exp(−2γ), the Gaussian's second difference, computed once per packet). Phase is stored as forward differences across the packet together with their per-sample increments, so advancing a packet by one sample is three integer additions. An inbox region takes external writes so the shadow page keeps a single writer. The WPMS side, as customer, accepted it, filled in the fixed-point column, numbered the output channels, and proposed that Hz never crosses the WPMS boundary — only phase increments do.

The repository is open in the Open Prompt shape — specification, reasoning traces, reference tools, and an empty Layer 4 waiting for DE10-nano. The reference tools already contain the contract chain: the master's normative chapter generates the master's contract, the profile's register folds it into the profile's contract, and nothing along the way is hand-edited.

Next: the consumer interface (what the hardwired pipeline latches at packet start — six words, it turns out), the choreography of packet, sample and control periods, and the first multi-packet program. Then silicon.

*(JA 要旨: 制約を先に読み、十八件の食い違いを保持、四件を上流へ提出し全件修正。Stay = パケットと二段構えの Stay 値レジスタ、整数 ISA とプログラム所有シフト、256 語のマップと inbox、手編集なしの契約生成鎖。次は消費者インターフェース、振付、マルチパケットプログラム、そしてシリコン。)*
