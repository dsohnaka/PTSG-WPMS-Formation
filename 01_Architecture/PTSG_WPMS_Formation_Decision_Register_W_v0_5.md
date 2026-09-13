# PTSG-WPMS-Formation — Decision Register W
# PTSG-WPMS-Formation — 決定台帳 W

*v0.5 · drafted by the WPMS-Formation amanuensis · 2026-09-07 · CC0 · Layer 1 of the PTSG-WPMS-Formation repository.*
*Status: rulings through 2026-09-04 recorded; downstream (WPMS Ch.3) answers of 2026-09-07 recorded; profile contract and oracle exist (Layer 3). Deliverable 1 is `L2_Formation_Register_Map_v0_2.md`, anchored here as W-F18.*

*v0.5 · WPMS-Formation 祐筆起草 · 2026-09-07 · CC0 · 本リポジトリの第1層。*
*状態: 09-04 までの裁定と 09-07 の下流(WPMS 第3章)回答を記帳。プロファイル契約とオラクルが第3層に存在。成果物 1 は `L2_Formation_Register_Map_v0_2.md`。*

## Changelog v0.4 → v0.5 (2026-09-07)

- **Downstream answers recorded** (WPMS / Spectrum Engine amanuensis, 09-07): deliverable 1 accepted as customer; Q column proposed (PH\*/OM\* Q0.32 modular; A0 Q1.31; AR1/AR2/E0 Q4.28 → SHV = 28; Q8.24 in Arena); RT.OUT channels (L, R, surround 2–7, aux 8–15); slot set confirmed complete against Ch.1 §1.7; third-order reserved slots not needed; Mode T supported, N_min ≈ 32; **C3-D1 (proposed)**: the WPMS boundary carries phase-domain integers only. → register map **v0.2**. The Q proposals await the architect's ruling (**W-R10**).
- **W-D21** (new, resolved in the map): 8 blocks vs "64 packets per sweep" — eight is the cheap concurrency limit; more via block re-fill or page enlargement.
- **Layer 3 exists**: `isa_fold_w.py` (contract chain Ch.3 → master → profile, every fold citing a W-ID), `isa_table_w.json` (17 instructions: PSH/POP out, WSH in, dest 6 out), `pfasm_tools_w.py` (SHV/WSH, EW2/EW3, inbox space, quartet sources), `exp_maclaurin_w.pfasm` (the W1 gift re-issued **owning its Q**: `LDA #28; WSH`). Evidence: CLEAN, max |err| 7.39e-09 (identical to the master run); five negative tests (master program without WSH → E8; STA ADRS → E4; PSH → E4; CMT in BG → E3; WSV 0/2049 and STM-into-inbox → EW2/EW3). See `03_Sample_Implementations/README.md`.
- **Repository opened** (this file is Layer 1). Master pin commit hash still to be filled (§0).
- Deliverable 2 customer seeds received (six-word latch at packet start; bin tick = K; sample-boundary flush; 3-bit CUR lane) → W-F17.

**要旨:** 下流回答(Q 提案・RT.OUT・スロット集合確認・Mode T 支持・C3-D1)を記帳、Q 提案は W-R10 として裁定待ち。第3層にプロファイル契約と オラクルが成立し、手土産プログラムは Q を自ら所有する形で CLEAN・同一数値。リポジトリ開設。

### Open at v0.5 / v0.5 時点の裁定待ち

| ID | Question |
|---|---|
| **W-R10** | Ratify the WPMS Ch.3 Q proposals as the first-implementation conventions (they are program-tier, downstream-owned under W-R6; the ISA-side consequence is only SHV = 28 for the amplitude advance and the 64-bit-product / arithmetic-shift / truncation MUL-MAC model). |
| **W-R11** | Order of downstream work: WPMS Ch.2 v1.1 errata first, or together with Ch.3; and whether Ch.3's L1 section (six-word input contract) is drafted now ahead of deliverables 2–3. (The amanuensis recommends: yes, draft it now — it depends only on deliverable 1.) |

---

## Changelog v0.3 → v0.4

- **W-R4, W-R5, W-R6 approved** (09-03). Layer vocabulary is now law of this register: **L1 pipeline / L2 Formation (this profile) / L4 Formation (outside WPMS)**.
- **L4 positioning ruled** (09-04): L4 Formation is **not part of WPMS**; it controls WPMS from outside. It will first exist as an Open Prompt **Layer 4 verification tool** for WPMS and evolve later (e.g., toward MIDI interpretation). Out of this register's scope; this register only ensures L2 exposes what an external controller needs.
- **W-R7 (re-pin) approved**: the master moved on 2026-09-03 (defect fixes W-D7/D8/D9/D12). Pin updated (§0).
- **W-F22 redesigned and approved**: two-stage Stay-value register (staged by WSV; presented value latched at Stay Set; the Core's live-change capability deliberately unused). 12-bit content.
- **W-F23 approved (option B)**: program-specified MAC realignment via a **shift-value register** written by a new mode-3 instruction. Resolves the coherence condition raised upstream on F-T7.
- **W-V3 updated** with the Core's answers; one residual question.
- **New proposal W-F9→INHERIT-now**: the register map (deliverable 1) depends on post-commit shadow inheritance (F-F14); the profile adopts it as law profile-side.
- Upstream defects W-D7/D8/D9/D12 **verified fixed** on the delivered files; **W-D6 resolved** (HALT is correct).
- §9 replies updated.

**要旨:** W-R4/5/6/7 承認。L4 は WPMS 外・当面は検証ツール。W-F22 は二段構え(12bit)、W-F23 は案 B(シフト値レジスタ+モード3新命令)。W-F9(F-F14)をプロファイル側で先取り INHERIT する提案。上流修正は検証済み。

---

## 0. Master pin — RE-PINNED (W-R7) / 再釘付け

| Field | Value |
|---|---|
| Master | `dsohnaka/PTSG-CPU-Formation`, **2026-09-03 defect-fix revision** (Ch.2, Ch.3 amended; `isa_from_chapter3.py`, canon-derived `isa_table.json`, Layer 2 trace *first-profile-feedback*) |
| Commit | *to be filled when pushed*; predecessor `4bc722d…` |
| Verification by this profile | generator re-run: 18/18 agree; `exp_maclaurin.pfasm` CLEAN against the canon-derived contract; negative test E3; Ch.2 §2.2/§2.4/§2.6c and Ch.3 §3.7 amendments confirmed in text |
| Contract chain | **Ch.3 → `isa_from_chapter3.py` → `isa_table.json` (master) → profile fold → `isa_table_w`** — never hand-edited |

Path independence (v0.2 §0) stands: profile-side additions may be absorbed by the master later.

**要旨:** 釘付け先は 09-03 修正版(ハッシュは push 後に記入)。契約は章→マスター契約→プロファイル契約の生成鎖。

---

## 1. Conventions / 記帳規約

§1.1–1.3 as v0.2. **§1.4 layer vocabulary — Fixed (W-R4, 09-03)**: L1 pipeline (hardwired, one bin per clock, consumer of the active page) · **L2 Formation = this profile** (Stay = packet; Stay counter = k) · L4 Formation (outside WPMS; external controller; first a Layer 4 verification tool). Older labels ("Upper/Lower") are no longer used in this register or in inter-amanuensis correspondence.

---

## 2. Rulings / 裁定

### 2.1 Ruled (cumulative) / 裁定済み

| ID | Ruling | Date |
|---|---|---|
| W-R0 | pin (superseded by W-R7) | 09-01 |
| W-R1 | 16- and 32-bit integer external formats; ISA speaks integers; Q downstream | 09-01 |
| W-R2 | W-F1 RESTRICT F-F13 — Fixed | 09-01 |
| W-R3 | W-T1 OMIT | 09-01 |
| — | W-T3 RESTRICT Fixed; W-T5 EXTEND-at-need; W-D2 → deliverable 3; k = Stay counter; packet length = Stay value | 09-02 |
| W-R4 | Layer vocabulary — approved | 09-03 |
| W-R5 | exp placement: both options presented with deliverable 3 (likely L4) — approved | 09-03 |
| W-R6 | Ownership split: ISA-visible register map = profile; Q-interpretation, wiring, L1 internals = WPMS Ch.3 — approved | 09-03 |
| W-R7 | Re-pin to the 2026-09-03 master revision — approved | 09-04 |
| — | W-F22 two-stage design; W-F23 option B — approved | 09-04 |
| — | L4 Formation: outside WPMS; verification tool first | 09-04 |

### 2.2 Open / 裁定待ち

*(none at 2026-09-04 evening)*

### 2.3 Ruled 2026-09-04 (addendum) / 09-04 追加裁定

| ID | Ruling |
|---|---|
| **W-R8** | **Approved.** W-F9 (F-F14, post-commit shadow inheritance) is this profile's law now, profile-side. |
| **W-R9** | **Ruled with the Core's convention made explicit.** Core convention: the external Stay value is selected when the instruction's internal Stay operand is **0**; if the external value is *also* 0, the Core treats the pair as **4,096**. In this profile external values above the sweep length are not permitted, so the convention is never reached: **EW2 = WSV with value 0 or value > NMAX → Error HALT**, where **NMAX = 2,048 bins per module** is a profile configuration constant bound to DE10-nano (a design variable, not a constant of nature). EW3 (STM into the inbox) approved as proposed. |

**要旨:** 新規の裁定待ちは W-R8(F-F14 の先取り INHERIT——レジスタマップの差分コミット方式が依存)と W-R9(W-F22/W-F23 に伴うプロファイル E 行 EW1/EW2)。

---

## 3. The register proper — changed rows only / 台帳本体——変更行のみ

Unchanged rows: see v0.3 §3 (W-F2–W-F8, W-F10–W-F16, W-T2, W-T4).

| W-ID | Master hook | Disposition / content | Status |
|---|---|---|---|
| **W-F1** | F-F13 | RESTRICT | F 09-01 |
| **W-T1** | DSTK | OMIT | F 09-01 |
| **W-T3** | F-T5 | RESTRICT | F 09-02 |
| **W-T5** | F-T8 | EXTEND-at-need, profile-side | approved 09-02 |
| **W-F9** | F-F14 | **INHERIT now (proposed, W-R8)** — was TRACK | P |
| **W-F17** | Ch.5 §5.11 | L1 consumer interface | — (next) |
| **W-F18** | Ch.4 §4.3 | **PPM active-page layout → issued as deliverable 1 v0.1** | P (draft issued) |
| **W-F19** | Ch.2 §2.8 | Condition lanes — inside deliverable 3 | home F 09-02 |
| **W-F20** | Ch.1 §1.6 | Choreography (L1/L2/L3; L4 external) | — |
| **W-F21** | W-R1 | 16/32-bit integer formats — realized in deliverable 1 §2 | F 09-01 |
| **W-F22** | F-F4; INT-R1; Core external Stay-value input | **Two-stage Stay-value register.** *Stage 1 (staged)*: `StayVal.s`, written by WSV from Accm (master §3.5), any BG clock. *Stage 2 (presented)*: `StayVal.p`, the value wired to the Core's external Stay-value input; **loaded from `StayVal.s` exactly at Stay Set** and held until the trailing edge. The Core's live-change capability (change until trailing edge; wrap-around lap on decrease) is **never exercised** by this profile: from the Core's viewpoint the value is F-F4's "sample once, frozen". Width: 12-bit content (Core's Fmax request honored), carried in a 16-bit port. Loop-value sibling reserved with the same two-stage shape. This is **INT-R1's first implementation**, with the freeze realized Formation-side. | **F 09-04** (rows in deliverable 1 §3) |
| **W-F23** | F-T7 | **Program-specified MAC realignment — option B.** New register `SHV` (shift value, 0–31), written by new mode-3 instruction **WSH** (3·3; `SHV ← Accm[4:0]`), latched per F-F4 (takes effect for the next MAC issued). MAC semantics in this profile: `Accm ← ((Accm × Temp) >> SHV) + src`; MUL: `Accm ← (Accm × src) >> SHV`. Q-conventions remain program-owned: the master demo's Q4.28 is the program setting SHV = 28. (Option A — shift field in the MAC operand — recorded as the alternative, not adopted.) | **F 09-04** (rows in deliverable 1 §3) |

**要旨:** W-F22 は `StayVal.s`(WSV が書く)と `StayVal.p`(Stay Set でのみ差し替え、Core へ提示)の二段。Core のライブ変更は使わず、Core から見れば F-F4 の凍結そのもの。W-F23 は `SHV` レジスタと新命令 WSH(モード3 サブオペ3、Accm[4:0] を書く)、MAC/MUL は `>> SHV` で再整列。

---

## 4. E-taxonomy fold / E 分類

As v0.2, plus: mode-3 sub-op 3 (WSH) leaves E4's reserved set. Proposed profile rows EW1, EW2 (W-R9). Contract generation now chains from the canon-derived master contract.

---

## 5. Value formats / 値のフォーマット

As v0.2 (two tiers). Realization: deliverable 1 §2 declares every register/slot's integer width class (W32 / W16 / W12 / W5). Q-conventions per program (downstream).

---

## 6. Verification items / 検証項目

| W-V | Status | Note |
|---|---|---|
| W-V1 | closed by ruling | conditions → W-F20 |
| W-V2 | → W-R8 | profile adopts F-F14 now |
| **W-V3** | **Core answers recorded (09-03); residual closed (09-04)** | (a) width 12 bits — Core prefers 12 for Fmax; profile complies. (b) captured at Stay-opcode execution; the specifier knows the value, so no read-back is needed. (c) changeable until trailing edge; decrease below the counter → extra lap. **Profile response: two-stage W-F22 makes (c) unreachable.** (d) Loop value: same mechanism. **Residual closed**: the external-specification switch *is* the instruction's Stay operand = 0 (Core convention); INT-R1's "register-source operand bit" is realized as that zero operand. Both-zero → 4,096 convention is unreachable under EW2. |

---

## 7. Requirement lineage / 要件系譜

As v0.3 §7 (unchanged).

---

## 8. Discrepancy shelf / 食い違い棚

| W-D | Status |
|---|---|
| W-D1–D5, D13 | resolved (v0.2/0.3) |
| **W-D6** | **resolved**: Core confirms HALT is correct; §3.3a wording to be aligned Core-side |
| **W-D7, D8, D9, D12** | **resolved upstream 09-03; verified by this profile** |
| W-D10, D11 | profile-side Layer 3 work; to be offered upstream when stable ("inherit rather than fork") |
| W-D14–16, D18 | downstream, standing (D18 now in WPMS Ch.3's plan as candidates A/B/C) |
| W-D19 | resolved by W-R4 |
| W-D20 | → W-R5 (both options with deliverable 3) |

---

## 9. Replies — drafts / 返答草案

### 9.1 To the master amanuensis (upstream) / 上流祐筆宛

四件の修正、当方で再検証しました(生成器 18/18 一致、デモ CLEAN、負系 E3、章の修正箇所を本文確認)。ありがとうございます。釘付けは 09-03 修正版へ更新します(W-R7)。

**W-F22 について。** INT-R1 の最初の実装として引用していただいて結構です。ただし一点、Core の外部入力は「到達時に一度サンプルして凍結」ではなく後縁までライブに比較され、カウンタ値より小さく変えると周回遅れで延長されることが分かりました。そこで F-F4 の「凍結」は Formation 側で実現します: WSV が書く `StayVal.s` と、Stay Set の瞬間にだけ `StayVal.s` から差し替えられ Core へ提示される `StayVal.p` の二段構えです。Core から見れば F-F4 の振る舞いそのものになります。幅は Core の希望で 12bit。吸収の際の行としては「F-F4 の凍結は Formation 側の提示レジスタで実現してよい」旨を添えていただけると、他のプロファイルにも効きます。

**F-T7 について。** ご指摘の通りでした。プロファイル側で W-F23 を立てます: シフト値レジスタ `SHV`(0–31)と、それを Accm から書くモード3の新命令 WSH(サブオペ 3)。MAC/MUL は `>> SHV` で再整列し、Q 規約はプログラムが SHV を設定することで所有します。手土産の Q4.28 は SHV = 28 の一設定に過ぎなくなります。マスターが F-T7 を規範的パラメータ化へ裁定される場合の吸収候補としてお使いください。

W-T3 の「制限は常に安全」に同意します。オラクル拡張は安定次第、フォークではなく上流へお返しします。

### 9.2 To the WPMS / Spectrum Engine amanuensis (downstream) — minimal / 下流祐筆宛

第2章訂正の受け入れ、ありがとうございます。**ISA 可視レジスタマップの草案 v0.1 を別紙でお届けします**(PPM ページの番地と整数幅、Stay 値レジスタ、シフト値レジスタ、RT エントリ形式)。Q の解釈と配線はそちらの領分ですので、草案の各スロットには「幅クラス」のみ付け、Q は空欄にしてあります。f → φ の判断材料として一点だけ: 1/48000 は定数ですから、どの層で行っても除算ではなく逆数定数との一回の MAC で済み、コストは決定要因になりません。ページは位相領域の 32bit 整数を運ぶ形にしており、A でも C でも変わりません。

*(L4 の位置づけについては大中様から直接お伝えいただく前提で、本草案には含めていません。)*

---

## 10. Status board / 状況板

| # | Deliverable | Status |
|---|---|---|
| 1 | PPM active-page layout / ISA-visible register map | **v0.1 issued** (`L2_Formation_Register_Map_v0_1.md`) |
| 2 | L1 consumer interface — rows first | next; two candidates for block selection are set up in deliverable 1 §4 |
| 3 | Choreography (L1/L2/L3) | after 2; W-R5 both options |
| 4 | Rulings | W-R8, W-R9 open |
| 5 | R7 in `.pfasm` | after profile contract |
| 6 | Profile contract (`isa_table_w`) from the canon chain + oracle extensions (quartet; SHV-aware MAC/MUL) | ready to start |

*End of v0.5.*
