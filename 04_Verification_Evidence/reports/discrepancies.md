# Discrepancies — silicon phase / 食い違い台帳——シリコン化段階

*CC0 · Layer 4 register of disagreements found while executing `SILICON_BRIEF_2026-09-27.md`. Opened in Phase 0 (2026-09-27).*
*Rule (brief §6, CLAUDE.md): every row records what the texts say, what was found, and a proposed disposition — **filed, not fixed**. No Layer 1 document, golden model or frozen Core source has been edited to resolve any row. The architect rules.*

*規則（指示書 §6）: 各行は「文書が言うこと・見つけたこと・処置案」を記す——**記録のみ、修正なし**。いずれの行についても、第1層文書・黄金モデル・凍結 Core は一切編集していない。裁定はアーキテクト。*

Evidence classes: **ORACLE** (Python model) · **RTL-SIM** (Icarus) · **SILICON** (DE10-nano). "Reading" = found by reading the RTL/texts, not yet exercised.

---

## Summary / 一覧

| ID | Item | Texts say | Found | Proposed disposition | Class · state |
|---|---|---|---|---|---|
| **SD-01** | Band on the issue port (brief known #1) | master Ch.5 §5.2 lane 1, §5.3: the issue carries {mode, sub-op, operand, **band**} | `ptsg_core.v` RH030 exports `ext_op_valid`, `ext_op_subopcode[3:0]`, `ext_op_sub_operand[7:0]`, `ext_op_data[15:0]`, `ext_op_ready`; **no band** (`window_open`, `in_queued_band` internal) | E2 stays validator-only in the silicon phase (brief, Phase 2); band export is a Core-office item at its checkpoint; no Core change | Reading · open |
| **SD-02** | FG silence of the issue port (IF-3) | master Ch.5 §5.3 **IF-3**: C3-F23 halts any Global in FG, so the issue port never fires with band = FG and E1 is enforced by the Core | The RTL's FG trap covers only internal Base Set / Return / Call / Loop / Prog End. An **external-mode Global in FG is issued** (`ext_op_valid` has no window term) and advances at full clock, no HALT | Architect to rule: C3-F23 covers mode ≥ 1 (Core halts them at a checkpoint) **or** IF-3 is amended (E1 validator-only, like E2) | Reading · open |
| **SD-03** | SSS source (brief known #2) | master Ch.2 §2.6b, §2.9 (source ID 6); Ch.5 §5.2 lane 4, §5.4, **INT-R4**: Stay Start State + window-start event observable; Map v0.3 §2 | `stay_start_state` is internal ("no Core-level external visibility", C3-F25); **no port, no window-start event**; internal Globals (incl. Stay Set) are not issued on the ext bus | Phase 2 records a documented substitute for source ID 6; INT-R4 stays open with the Core's office. No WPMS program reads SSS today | Reading · open |
| **SD-04** | Gap-free data-driven re-entry, R2 (brief known #3) | W v0.7 **W-R17** (R2 preferred); D3 §3 (backward transfer at timeup, or a loop count as data); Core commitment g = 0 | A queued Loop never performs the indirect read (`need_ind_loop` excludes the Q band; queued Loop(0) = zero iterations, C4-V1); the Q band admits one SN reservation (C3-F26; a second HALTs, T21). A queued Base Set + Loop gives a gap-free backward re-entry **with a literal count only** | Preliminary: no data-driven gap-free R2 in the Core as built. Phase 3 confirms by simulation, reports the Hook A options, proceeds with R1 (brief). No Core change | Reading · preliminary |
| **SD-05** | Forward conditional at timeup (R1) and the NONEMPTY check vs Core Branch law | D3 §3: R1 "forward conditional: MORE → PKT(q+1), else → HK; needs only forward transfers"; sketch "Branch +→HK, lane NONEMPTY, false → HK [1 clock]" | Core Branch: Condition true → no branch (C2-F5); **taken → auto-save** into the holding register (C2-F6); a second save while it is occupied goes through **S_PUSH and waits for `stack_ack`** (C3-T6). Queued Branch **not taken resumes at Branch + 1** (T16), inside the Q region, not at Stay + 1 | Phase 3 designs the score around these laws and measures g; architect ruling may be needed on the queued-Branch not-taken resume address (§3.4b Branch Q row). Not a Core change | Reading · preliminary |
| **SD-06** | Formation error strobe (lane 8, INT-R2) | master Ch.5 §5.2 lane 8, §5.8: the strobe "rides the Core's external error/halt input" (**INT-R2**); Map v0.3 §8: EW2–EW6, E4, E5 → Error HALT | `ptsg_core.v` has `error_flag` (output) only; **no external error/halt input** | Phase 2 picks insertion or Condition per C3-F24 and documents it (brief); INT-R2 stays open | Reading · open |
| **SD-07** | Width of I | Map v0.3 §1, §2: quartet K / I / SN / SSS is **W12** | Core `LOOP_W` = **16** (architect ruling 2026-07-07); `loop_counter[15:0]`; master Ch.2 §2.2 "I … loop-counter width" | Phase 2 reads I as 16 bits, zero-extended; Map to be aligned by ruling | Reading · open |
| **SD-08** | Register W v0.7 §2.2 editorial | §2.2 "Open: None." | A stray table fragment (file lines 80–86) repeats W-R12…W-R17 in their v0.6 "open" form; its W-R17 row ("R1 or R2 — the Core's choice") contradicts §2.1 | Editorial cleanup at the next version; no effect on the build | Reading · open |
| **SD-09** | Customer Appendix 5.B mask presets | Ch.5 §5.4.2 "bit 16 = RT.OUT"; §5.6.2 COMMIT[b] [16]; App. 5.B "RETUNE 0x9E3B … + RT.OUT", "RESEED 0x9FFF … + RT.OUT" | Neither value has bit 16 set (with it: 0x19E3B, 0x19FFF) | Customer to correct value or wording (via the architect, PR-5 style); the Phase 5 host script sets bit 16 explicitly | Reading · open |
| **SD-10** | Stale header comments in `ptsg_core.v` not covered by the RH029/030 patch | Core Ch.3 §3.2 (C4-F10 corrected: counter counts On-Tick from Stay Set through the window); Core README tie table | Header Tie line "C4-T4 … the stay counter ticks only during the wait" contradicts C4-F10; "Deliberate simplifications" still says post-Prog-End commands other than Loop execute immediately (superseded by RH014–RH019) and that imem is an asynchronous read (superseded by `ptsg_imem` NEG) | For the Core's office at its checkpoint (comments only). **Not** changed in the working copy — outside the brief's patch list | Reading · open |
| **SD-11** | Registered timing signals vs "packet_start = Stay Set ∧ TS_PKT" | D2 §2–§3: `packet_start` = Core Stay Set ∧ TS_PKT, K = 0 **on that clock**; `bin_valid` = TS_PKT held through the Stay | `timing_signals` is a registered Core output: a word's D16–D31 appears **one clock after** the word executes (FG Stay Set: `timing_signals <= tsig`). During the Stay Set clock the bus still shows the previous word's bits; TS_PKT alone therefore rises one clock late at the first packet and falls one clock late after the last (the housekeeping Stay Set clock) | Phase 3 derives `packet_start`/`bin_valid` so that they align with K = 0 on the Stay Set clock (e.g. from `state_number` against the score's packet addresses, or a documented one-clock shift of L1) and states the choice | Reading · preliminary |
| **SD-12** | Packet floor on the Core: 29 (nominal) vs 30 (RTL-SIM) — *Phase 1* | D3 §6.1, Map v0.3 §9, `wpms_packet.pfasm` header, `sweep_sim.py` output: 25 window instructions + **4** Core clocks = 29, rounded up to N_MIN = 32 | On the Core copy, a windowed Stay never times up in its execute clock (RH028's same-clock timeup is for bare Stays only), so Stay Set · 25 · Prog End · queued transfer · Stay needs **one S_WAIT clock more**: period = max(N, **30**), K = 0…N−1, g = 0 (SV-5b) | The RTL number replaces the nominal in the reports (not in Layer 1, which changes by ruling); N_MIN = 32 still holds with 2 clocks of margin. Phase 3 re-measures with the real window and score (an R2 body with Base Set(Q) + Loop(Q) would add one more clock: 31, by reading) | RTL-SIM · open |

Rows added in later phases are appended below the Phase 0 set (SD-12 from Phase 1). / 以降の段階で見つかった行は Phase 0 の組の下に追記する（SD-12 は Phase 1）。

---

## Details / 詳細

### SD-01 — Band on the issue port / 発行ポートの帯域

- **Texts.** Master Ch.5 §5.2 (lane 1 "Issue port {mode, sub-op, operand, band} + valid"), §5.3 ("the Core presents {mode, sub-op, operand D16–D31, current band}"), §5.8 (E2 is Formation-detected).
- **Found.** Frozen `ptsg_core.v` (sha256 `fb995687…60e0`), port list: `ext_op_valid`, `ext_op_subopcode` (= D4–D7), `ext_op_sub_operand` (= D8–D15), `ext_op_data` (= D16–D31), `ext_op_ready` (captured, never stalled on). The band exists only as internal `window_open` / `in_queued_band`.
- **Consequence.** E2 (Formation instruction in the Q band) cannot be detected by the Formation from the bus.
- **Disposition (proposed).** As the brief directs: E2 remains the validator's (`pfasm_tools_w.py`) in the silicon phase. Exporting a two-bit band is a Core-office item. No Core change.
- **和文.** マスター第5章は発行に帯域を含めるが、凍結 Core の外部演算バスには帯域がない。Formation はバスだけでは E2 を検出できない。指示書どおり E2 は検証器に委ね、Core は変更しない。

### SD-02 — Foreground silence of the issue port (IF-3) / 発行ポートの前景沈黙

- **Texts.** Master Ch.5 §5.3 IF-3; Core Ch.3 §3.4b C3-F23 ("Global commands do not execute in the foreground, with exactly three justified exceptions" — the listed window-only commands are internal sub-ops).
- **Found.** `ext_op_valid = (fsm == S_RUN) && is_external_global && !insert_pending` — no window term. In `S_RUN`, `OP_GLOBAL` with `g_mode != 0` executes `state_num <= state_num + 1` in every band, untick-gated. Only internal Base Set / Return / Call / Loop / Prog End reach `halt` in FG.
- **Consequence.** A Formation instruction placed in the foreground is issued and executed; E1 is enforced by neither side.
- **Disposition (proposed).** Architect to rule on the reading of C3-F23 for mode ≥ 1. Until then E1 is validator-only in the silicon phase, like E2.
- **和文.** IF-3 は「C3-F23 が前景の Global を止めるので発行ポートは FG では発火しない」とするが、RTL は内部サブオペ5種のみを止め、前景の外部モード Global は発行・前進する。E1 はどちらの側でも執行されない。C3-F23 の適用範囲の裁定を求める。

### SD-03 — SSS source / SSS ソース

- **Texts.** Master Ch.2 §2.6b ("a Formation-latched copy taken at window start"), §2.9 (source ID 6); Ch.5 §5.4 and INT-R4; Register Map v0.3 §2.
- **Found.** `stay_start_state` is an internal register; README and Core Ch.3 C3-F25: "no Core-level external visibility; a Formation may copy it to a general register". No port carries it, and no window-start (Stay Set) event leaves the Core (internal Globals are not issued).
- **Consequence.** Source ID 6 cannot be the Core's register latched at window start. `wpms_packet.pfasm`, `wpms_housekeeping.pfasm` and `exp_maclaurin_w.pfasm` do not read SSS.
- **Disposition (proposed).** Phase 2 implements source ID 6 with a documented substitute and says exactly what it returns; INT-R4 remains open.
- **和文.** Core は Stay Start State を外へ出さず、窓開始イベントもない。ソース ID 6 は仕様どおりには実現できない。Phase 2 で代替を明記して実装し、INT-R4 は Core 事務所に残す。

### SD-04 — R2 without a gap / R2 の無間隙再入

- **Texts.** Register W v0.7 W-R17; Deliverable 3 §3 (R2: "a conditional backward transfer at timeup, or a loop count supplied as data (P)"); Core commitment g = 0 (D2 §3; W §2.1).
- **Found (reading).** `need_ind_loop = … && !in_queued_band && window_open`: a queued Loop is never resolved through `indirect_purpose` 01; its literal D16–D31 is its count, and 0 means zero iterations (C4-V1; README "Deliberate simplifications"). One SN reservation per Q band (C3-F26, RH023, T21). A queued Base Set loads Base := Stay Start State (C3-F25, T28/T32), so `Stay Set … Prog End · Base Set(Q) · Loop(Q) · Stay` re-enters its own Stay Set at timeup without a gap — with a **literal** count.
- **Preliminary conclusion.** No data-driven, gap-free R2 in the Core as built. To be confirmed in Phase 3 by simulation; options reported against Hook A of the 2026-09-27 trace; R1 used for bring-up.
- **和文.** キュー帯域の Loop は間接読みを行わず（直値のみ）、Q 帯域の予約は一つ。Base Set(Q)+Loop(Q) で無間隙の後方再入はできるが回数は直値。データ駆動の無間隙 R2 は現行 Core にはない見込み。Phase 3 で模擬して確定し、選択肢を報告、R1 で進む。

### SD-05 — R1's forward conditional and the NONEMPTY check / R1 の前方条件遷移と NONEMPTY 判定

- **Texts.** Deliverable 3 §3 (sketch and R1); Deliverable 2 §3 (g = 0).
- **Found (reading, and the Core's own conformance tests).** `branch_decide`: Condition true → `state_num + 1`; operand 0 → self-loop, no save; otherwise `save_or_set(state_num, …)`, i.e. an **auto-save** (C2-F6). With the holding register already occupied, `save_or_set` enters `S_PUSH` and waits for `stack_ack` (C3-T6 lean A). Queued Branch (RH017): not taken → `resume_addr = queued_save_state + 1` (T16: the word after the Branch, inside the Q region); taken → auto-save (T15).
- **Consequences if the sketch is encoded literally.** (a) The NONEMPTY Branch is *taken* on every empty sweep — the reset state (CR5-R1) — so the second empty sweep enters `S_PUSH`; with `stack_ack` tied 0 the Core would wait forever. (b) A queued Branch on MORE cannot land on PKT(q+1) without a gap: not taken resumes at the Q-region tail, taken auto-saves every packet and stalls from the second.
- **Disposition (proposed).** Phase 3 builds the score around these laws (e.g. discharging the holding register once per sweep, lane polarity, placement) and measures g, T_wake and the per-sweep overhead. If the intended semantics of a queued Branch not taken is "advance past the Stay" rather than "Branch + 1", that is a Core ruling (§3.4b Branch Q row: the relative State Number is computed when the queued target executes).
- **和文.** Core の Branch は taken で自動退避し、保持レジスタが埋まっていれば S_PUSH で `stack_ack` を待つ。キュー帯域 Branch の not-taken は Branch+1（Q 領域内）に再開する。素描をそのまま符号化すると、(a) 空掃引（リセット状態）の2回目で S_PUSH 待ち、(b) MORE による無間隙の前方遷移が成立しない。Phase 3 でこの法に沿った楽譜を設計・実測する。not-taken の再開番地の意図は Core の裁定事項となり得る。

### SD-06 — Error strobe into the Core / Core へのエラーストローブ

- **Texts.** Master Ch.5 §5.2 lane 8, §5.8, INT-R2; Register Map v0.3 §8.
- **Found.** `error_flag` is an output; the Core enters `S_HALT` only through its own traps. No external error or halt input exists.
- **Disposition (proposed).** Phase 2 halts the Formation datapath locally, exposes `error_flag`/`error_code`, and drives the Core through the insertion bus or the Condition input as the brief allows — one of the two, documented. INT-R2 remains open.
- **和文.** Core には外部エラー入力がない。Phase 2 で挿入バスか Condition のいずれかを選び、文書化する。INT-R2 は未決のまま。

### SD-07 — Width of I / I の幅

- **Texts.** Register Map v0.3 §1 (W12 class includes K / I / SN / SSS) and §2.
- **Found.** Core `LOOP_W` = 16 since the ruling of 2026-07-07 (RH009); `loop_counter[15:0]`. Master Ch.2 §2.2 gives I the loop-counter width.
- **Disposition (proposed).** Phase 2 zero-extends a 16-bit I. The Map's class to be aligned by ruling.
- **和文.** マップは I を 12 ビット級とするが、Core のループカウンタは 16 ビット。Phase 2 は 16 ビットをゼロ拡張して読む。

### SD-08 — Register W v0.7 editorial / 台帳 W v0.7 の体裁

- **Found.** Lines 80–86 of `PTSG_WPMS_Formation_Decision_Register_W_v0_7.md`: after "None." a headerless table repeats W-R12…W-R17 as open questions; the W-R17 row ("R1 or R2 — the Core's choice, via the architect") predates the ruling in §2.1.
- **Disposition (proposed).** Remove at the next version. The build follows §2.1.
- **和文.** §2.2「なし」の後に v0.6 の未決表の断片が残る。次版で削除。構築は §2.1 に従う。

### SD-09 — Customer mask presets / 顧客のマスク既定値

- **Found.** Appendix 5.B: RETUNE 0x9E3B and RESEED 0x9FFF are described "+ RT.OUT", but RT.OUT is mask bit 16 (§5.4.2, §5.6.2), absent from both values.
- **Disposition (proposed).** Customer correction via the architect. Non-normative; the Phase 5 host script will set bit 16 explicitly.
- **和文.** 付録 5.B の RETUNE/RESEED は「+ RT.OUT」とあるが、値にビット 16 がない。顧客側で訂正を。

### SD-10 — Stale comments in the frozen Core header / 凍結 Core ヘッダの古い注記

- **Found.** Header Tie list (line 46–48 of the frozen file): "C4-T4 Stay Set role … the stay counter ticks only during the wait". Deliberate-simplifications block (lines 51–64): queued band "supports the canonical queued Loop. Other internal-mode commands placed after Prog End execute immediately"; "Instruction memory is modelled with single-cycle (asynchronous) read". All three predate RH011–RH028 and the `ptsg_imem` wrapper; the Core README states the current behaviour.
- **Disposition (proposed).** Comments-only correction at the Core's checkpoint. The working copy `hw/core/ptsg_core_rh031p.v` leaves them as they are, so that its diff against RH030 contains only the brief's items.
- **和文.** 凍結 Core のヘッダに、C4-F10 訂正前・RH014〜RH019 以前・`ptsg_imem` 以前の記述が残る。Core 事務所のチェックポイントでの注記修正を提案。写しでは触れない（差分を指示書の項目に限るため）。

### SD-11 — Registered timing signals and the packet-start clock / 登録型タイミング信号とパケット開始クロック

- **Texts.** Deliverable 2 §2 (`packet_start` = Core Stay Set ∧ TS_PKT, K = 0 on that clock; `bin_valid` = TS_PKT held through the Stay), §3 timing diagram.
- **Found.** `timing_signals` is `output reg`; every word that drives it does so with a non-blocking assignment in its execute clock, so the bits are visible from the next clock (C3-T1 lean A holds the Stay word's bits during the wait). K (`stay_counter`) reads 0 in the Stay Set clock and 1 in the next (RH028 at P = 1).
- **Consequence.** TS_PKT taken straight from the bus rises one clock after the first packet's Stay Set (bin 0, K = 0, would be missed) and falls one clock after the housekeeping Stay Set (one extra clock flagged valid, with K = 0).
- **Disposition (proposed).** Phase 3 derives `packet_start` and `bin_valid` so that the latch clock is the Stay Set clock with K = 0 (or documents a uniform one-clock shift into L1) and proves it against the sweep oracle's bundles.
- **和文.** `timing_signals` は登録出力で、語の D16–D31 は実行の次クロックから見える。TS_PKT をそのまま使うと、パケット列の両端で K と 1 クロックずれる。Phase 3 で K = 0 の Stay Set クロックに揃える導出を決め、オラクルで確かめる。

### SD-12 — Packet floor: 29 nominal, 30 on the Core / パケット下限: 名目 29、Core 上 30 *(Phase 1)*

- **Texts.** Deliverable 3 §6.1 ("With 25 window clocks and 4 Core clocks, N ≥ 29; the profile constant is N_MIN = 32. Oracle-counted; measured in Layer 4"); Register Map v0.3 §9; the header of `wpms_packet.pfasm`; `sweep_sim.py` ("N_MIN = 25 + 4 = 29"), whose Core clocks are declared nominal (brief §2).
- **Found (RTL-SIM, `hw/core/run_phase1.sh`, test SV-5b).** Program Stay Set · 25 BG NOPs · Prog End · queued Jump → Stay Set · Stay, `stay_value` = N, P = 1, on `ptsg_core_rh031p.v`: Stay Set to Stay Set = 30 for N = 29 and 30, and exactly N for N = 31, 32, 33, 64, 2048, 4095; K runs 0 … period − 1 with no error; no idle clock between packets. Cause, by reading: `OP_STAY` times up in its own clock only when `!window_open`; a windowed Stay always enters `S_WAIT`, whose first clock is the earliest timeup. The count is Stay Set (1) + window (25) + Prog End (1) + queued transfer (1) + Stay execute (1) + first S_WAIT clock (1) = 30.
- **Consequence.** None for the constant: N_MIN = 32 ≥ 30. The oracle's "4 control clocks per packet" is one short as a floor; it does not enter the sweep budget, because a packet's time is N whatever its window.
- **Disposition (proposed).** Reports carry 30 (RTL-SIM) beside 29 (ORACLE nominal); Layer 1 unchanged unless ruled. Phase 3 re-measures with the Formation's real window and the chosen score; Phase 6 on silicon.
- **和文.** 25 命令の窓をもつパケット Stay は、この Core では N ≥ 30 で厳密（名目は 25 + 4 = 29）。窓つき Stay は実行クロックでは満了せず必ず S_WAIT に一クロック入るため。定数 N_MIN = 32 は余裕 2 で成立。報告では 30（RTL-SIM）を名目値 29（ORACLE）と並記し、第1層は裁定なしに変えない。
