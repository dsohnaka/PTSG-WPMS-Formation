# PTSG-WPMS-Formation — The First Week: a Profile Learns Where It Stands
# PTSG-WPMS-Formation — 最初の一週間: プロファイルは自分の席を知る

## Trace Metadata / 軌跡メタデータ

| Field | Value |
|---|---|
| **Date / 日付** | 2026-09-01 → 2026-09-07 |
| **Type / 型** | Founding trace of the profile: reading order, first rulings, two ISA-shaping discoveries, deliverable 1, three-way correspondence. Condensed; the full register history is `01_Architecture/…Decision_Register_W_v0_5.md` (changelogs v0.1→v0.5). |
| **Participants / 参加者** | Tsuneo Ohnaka (architect — all rulings); Claude (amanuensis of this profile — drafting, verification, this record). Correspondents: the master's amanuensis (PTSG-CPU-Formation) and the customer's amanuensis (FPGA Spectrum Engine), separate sessions. |
| **Deliverables / 成果物** | Decision Register W v0.5; L2 Formation register map v0.2; Layer 3 contract chain and oracle; four upstream defect filings (accepted and fixed 2026-09-03). |
| **License** | CC0 1.0 |

---

## 1. Reading before headlines / 見出しより先に制約を

The session charter (2026-07-31) prescribed an order: charter → hand-off brief (2026-07-13) → PTSG-Core Ch.1 and Ch.3 §3.4b → PTSG-CPU-Formation Layer 1 (five chapters) → WPMS Layer 1 Ch.1–2 read *with an errata sheet in hand*. The amanuensis read in that order and kept, unfiled, a list of everything that disagreed with something else. By the end of the reading the list held eighteen items. The architect asked that they be held, not filed: "some will resolve themselves." Most did.

憲章の読書順序に従い、食い違いは提出せず保持した。読了時点で十八件。設計者は「自然に解ける」と言い、大半はそうなった。

## 2. The rulings that made the profile a profile / プロファイルを成立させた裁定

- **Pin** (W-R0→W-R7): the master at its 2026-09-03 revision. The subtraction is judged on the resulting form, not the path — the profile may add first and let the master absorb later.
- **Numbers**: per sample period per module, 2,083 clocks against 2,048 bins; the **35-clock margin** is the meaningful quantity; quotients are not; N per module is a design variable. This one sentence retired three errata items.
- **Formats** (W-R1): the ISA speaks integers, 16- and 32-bit; fixed-point meaning belongs to programs and to WPMS Ch.3.
- **W-F1** RESTRICT F-F13 (first Fixed). **W-T1** OMIT the data stack. **W-T3** RESTRICT FG register-source branching. **W-T5** post-increment at need. **W-R8** post-commit shadow inheritance adopted now.
- **Vocabulary** (W-R4): "Upper/Lower" meant opposite layers in two governing sources; the profile speaks in layer numbers — L1 pipeline, L2 Formation, L4 Formation. L4 is outside WPMS: an external controller, first a verification tool.

## 3. Discovery one: the Stay is the packet / 発見一: Stay がパケットである

The architect: the difference engine's *k* is bin-layer information, needed at clock rate, and it **is** the Stay counter's output. Hence packet length = Stay value; variable packets need a variable Stay value; the profile must hold a Stay-value register and feed it back to the Core. The Core (via the architect) then explained its external-value input: 12 bits, captured at Stay-opcode execution, **changeable until the trailing edge** — decrease it below the counter and the Stay laps. The master's F-F4 had promised "sample once, frozen"; the Core does not freeze. So the profile freezes: **`StayVal.s`** (written by WSV) and **`StayVal.p`** (loaded at Stay Set, presented to the Core). W-F22. The Core's convention — internal operand 0 selects the external value — turned out to be INT-R1's "register-source bit" already in silicon. K = k, once a hypothesis to verify, became a construction.

k はステイカウンタ出力そのもの。Core の外部入力は後縁までライブなので、凍結は Formation 側の二段構えで実現する。

## 4. Discovery two: an integer ISA must let programs own the shift / 発見二

The master's amanuensis, reading the ruling "integers in the ISA, Q in programs," pointed out that it is coherent only if a program can express the MAC's realignment. Correct. The profile added **`SHV`** and **`WSH`** (mode 3, sub-op 3): `MAC ← ((Accm × Temp) >> SHV) + src`. The master's first program, re-issued with `LDA #28; WSH` in front, validates CLEAN on the profile contract with numerics identical to the master's run; the same program *without* those two lines overflows on every MAC. The ISA does not know your Q. W-F23.

## 5. Deliverable 1 and the customer's answer / 成果物 1 と顧客の回答

A 256-word space: eight 16-word packet blocks (active/shadow) and an eight-block **inbox** that only external writers touch, so the shadow keeps one writer. Blocks hold amplitude as geometric differences (A0, AR1, AR2 = exp(−2γ), E0) and phase as forward differences in *k* (PH0, PHD1, PHD2) with their per-sample increments (OM0, OMD1, OMD2): the sample-advance law is three integer additions. Two block-selection modes were left open for deliverable 2; the customer chose table-direct (≈ 25 clocks per packet, N_min ≈ 32 bins), filled the Q column (Q0.32 modular; Q1.31; Q4.28 → SHV = 28), numbered the routing channels, confirmed the slot set complete against Ch.1 §1.7, and proposed **C3-D1**: the WPMS boundary carries phase-domain integers only; Hz never crosses it.

## 6. On method / 方法について

Four master defects were caught by reading, not by machinery; the master's amanuensis fixed all four within a day and wrote that "the second amanuensis is a verification layer the master cannot supply itself." The profile, in turn, did not file complaints about the inherited oracle's gaps; it extended the oracle and will offer the extension upstream. Between the three sessions, what travels is register entries and filed discrepancies — not chat.

三つのセッションの間を行き来するのは台帳項目と食い違い提出であり、会話ではない。

## End of Trace / 軌跡の末尾

*The profile's first program computed e again tonight — the same digits as the master's, with two more instructions in front that say whose Q it is.*
