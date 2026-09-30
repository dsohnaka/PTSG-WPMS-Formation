# Note to the customer team — the L1 sine: Ch.2 v1.1's Maclaurin core as built / 顧客チームへの報告——L1 の sin：第 2 章 v1.1 マクローリン・コアの実現

*CC0 · Layer 4 note from the PTSG-WPMS-Formation silicon phase to the WPMS / FPGA Spectrum Engine amanuensis (customer side), conveyed by the architect. Prepared 2026-09-30 on the architect's ruling of that day (discrepancy register SD-16). Not sent from this session: the customer's repository is outside its scope.*

*PTSG-WPMS-Formation シリコン化段階から WPMS／FPGA Spectrum Engine 祐筆殿（顧客側）への報告。アーキテクト経由で伝達。2026-09-30 の裁定（食い違い台帳 SD-16）に基づき準備した。本セッションからは送付していない（顧客リポジトリは本セッションの範囲外）。*

---

## 1. What was decided / 決まったこと

The architect ruled on 2026-09-30 that the sine realization published by the silicon phase is the **official specification of the L1's sine**, until the customer's next Ch.2 says otherwise. It keeps Ch.2 v1.1's architecture and its **seven multipliers**:
- Approach B (Horner), with (2π)^(2j+1)/(2j+1)! folded into the constants ("constant absorption", §2.2.4);
- reflection into the first quadrant (§2.3.3);
- truncation toward zero (C2-D11).

What it changes is the **formats**: each Horner stage gets its own power-of-two scale ("pre-scaled", §2.5.1). With that, the core meets the chapter's error budget. Read literally, the chapter's format table does not.

2026-09-30 のアーキテクト裁定により、シリコン化段階が公開した sin の実現を、顧客の次版第 2 章が別に定めるまで **L1 の sin の正式仕様**とした。第 2 章 v1.1 の構成と **7 乗算器**はそのまま保っている（Approach B の Horner、定数への (2π)^(2j+1)/(2j+1)! の吸収、第 1 象限への反射、0 方向への切り捨て）。変えたのは**書式**で、Horner の各段に固有の 2 冪スケールを持たせた（§2.5.1 の「pre-scaled」）。これで章自身の誤差予算に収まる。書式表を字義どおりに読むと収まらない。

## 2. Findings / 見つけたこと

| # | Ch.2 v1.1 says | Found | Class |
|---|---|---|---|
| F1 | §2.4.1: x′ Q2.25, X Q4.23, every Horner intermediate and every constant C₃…C₁₁ in Q1.26; §2.8.2: aggregate error ≈ 1.3×10⁻⁷ | Taken literally, C₁₁ = 1/11! is **2 LSB** of Q1.26 (1.68 rounded, +19 %) and C₉ has 8 significant bits. The maximum \|error\| over 200,000 phases is **3.97×10⁻⁷ = 2⁻²¹·²⁶**, three times the budget. | ORACLE |
| F2 | §2.3.3: reflection by "bit-inversion of the 30-bit field, equivalent to two's complement negation modulo 2⁻²" | **Bit inversion is right; two's complement is not equivalent at the quadrant boundary.** Negation maps ξ = 0 of Q2 to ξ′ = 0, i.e. sin(π/2) = 0. The mutant that uses negation is caught by the cosimulation (Phase 4 mutant S1). | ORACLE, RTL-SIM |
| F3 | §2.2.1: the 11th-order truncation error ≈ 4×10⁻⁸ | (π/2)¹³/13! = **5.69×10⁻⁸** | arithmetic |
| F4 | The oracle (`wpms_layer1_oracle.py`) fixes exp2, amplitude, phase and the glide bit for bit | It has **no sine**, so half of the L1 product is not golden-checked. The silicon phase checks its sine against its own published model. | reading |

## 3. The realization (exact) / 実現（厳密）

Input: phase φ as Q0.32 (cycles). Output: sin(2πφ) as Q0.40 signed (41 bits). `tz(v, s)` truncates v/2ˢ toward zero.

```
quad = φ[31:30];   ξ = φ[29:0];   if quad is odd: ξ = (2^30 − 1) − ξ      (bit inversion)
u  = ξ >> 4                        26 bits, units 2^-28 cycle
U  = (u · u) >> 26                 26 bits, units 2^-30
S5 = c4 − tz(U · c5, 32)           c5 at 2^22, S5 at 2^20
S4 = c3 − tz(U · S5, 31)           S4 at 2^19
S3 = c2 − tz(U · S4, 30)           S3 at 2^19
S2 = c1 − tz(U · S3, 29)           S2 at 2^20
S1 = c0 − tz(U · S2, 27)           S1 at 2^23
v  = tz(u · S1, 11)                Q0.40
sin = (quad ≥ 2) ? −v : v
```

| Constant | Value | = (2π)^(2j+1)/(2j+1)! at scale |
|---|---|---|
| c0 | 52,707,179 | 2π · 2²³ |
| c1 | 43,349,917 | (2π)³/3! · 2²⁰ |
| c2 | 42,784,653 | (2π)⁵/5! · 2¹⁹ |
| c3 | 40,215,962 | (2π)⁷/7! · 2¹⁹ |
| c4 | 44,101,737 | (2π)⁹/9! · 2²⁰ |
| c5 | 63,311,520 | (2π)¹¹/11! · 2²² |

In hardware:
- seven multipliers, every operand ≤ 26 bits (27×27 DSP mode);
- 16 clocks (Phase 4, `hw/l1/wpms_l1_sin.v`, generated constants).

**Error:** maximum |sin − sin(2πφ)| = **5.96×10⁻⁸ = 2⁻²⁴·⁰⁰**, exhaustive over all 2²⁶ values of u (both ends of each u's 16 phases) — **ORACLE**. That is the 11th-order truncation itself; the arithmetic adds nothing measurable.

The RTL equals the model bit for bit:
- 1,000,000 random phases, 0 mismatches;
- every bin of 651,424 in the module test, 0 mismatches;
- all Phase 4 system runs (evidence `rtl_sim/2026-09-29_phase4_l1/`) — **RTL-SIM**.

The Ohnaka refactoring `x·(1 − x²/6·(1 − x²/20·(…)))` would need a second multiplier per stage for no gain here, because the per-stage scales already give every stage 25–26 significant bits.

## 4. Proposed for Ch.2 v1.2 and the oracle / 第 2 章 v1.2 とオラクルへの提案

1. **§2.4.1:** state the Horner formats as per-stage scales (these, or the customer's own), rather than one Q1.26 for all constants and intermediates.
2. **§2.3.3:** reflection by bit inversion (ξ′ = 2³⁰ − 1 − ξ). Delete "equivalent to two's complement negation".
3. **§2.2.1 / §2.8.2:** truncation error 5.7×10⁻⁸. The realized aggregate is 2⁻²⁴·⁰ = 5.96×10⁻⁸.
4. **The oracle:** add a bit-exact sine (the dozen lines of §3 above: `sin_trace` / `sin_q040` in `PTSG-WPMS-Formation/03_Sample_Implementations/hw/tools/l1_model.py`). Then the whole L1 product is golden-checked. The function can be contributed; its licence for the customer's CC0 oracle is for the architect to settle (the silicon phase's tools are MIT).

**提案。**
- §2.4.1 の書式を段ごとのスケールで述べる。
- §2.3.3 は「ビット反転」とし、「2 の補数と等価」を削る。
- 打ち切り誤差は 5.7×10⁻⁸ とする。
- オラクルにビット一致の sin を加える。関数は提供できる。顧客の CC0 オラクルに入れる場合のライセンスは、アーキテクトの判断による。

## 5. Where to look / 参照

- The register of discrepancies: `04_Verification_Evidence/reports/discrepancies.md`, SD-16 (texts, findings, ruling).
- `04_Verification_Evidence/reports/phase4_l1.md` §3–§4.
- The model: `03_Sample_Implementations/hw/tools/l1_model.py`. The RTL: `03_Sample_Implementations/hw/l1/wpms_l1_sin.v` and `wpms_l1_consts.vh` (generated by `hw/tools/gen_l1_tables.py`).
- Evidence: `04_Verification_Evidence/rtl_sim/2026-09-29_phase4_l1/` (`observation.md`, logs).
