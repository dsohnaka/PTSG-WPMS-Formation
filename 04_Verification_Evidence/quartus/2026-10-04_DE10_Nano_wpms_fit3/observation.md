# Observation — Phase 6, the third fit (SD-22 step 2, SD-23): clk_sys closes / 観測——Phase 6 第 3 回フィット：clk_sys が収束

*CC0 · 2026-10-04 · STA (TimeQuest) and SILICON (the Fitter's resource figures) · Quartus Prime Lite 23.1std.1 · revision `DE10_Nano_wpms` (50 MHz, clk_sys 30 % high) · 5CSEBA6U23I7.*

*Compiled by the architect after PR #7 (main fe38260): Formation RH006, switch RH003, `SYS_DUTY` 30 (SD-22 step 2, SD-23). The expectations quoted below were written before the compile (`reports/phase6_silicon.md` §11.6).*

*期待値はコンパイル前に書かれたもの（§11.6）を引用した。*

## Inputs / 入力

- `DE10_Nano_wpms-Multicorner_Timing_Analysis_Summary.rpt` (2026-10-04 09:23:09).
- `setup_clk_sys_worst10_0C.rpt`: the architect's `report_timing -setup -to_clock clk_sys -nworst 1 -npaths 10 -detail full_path`, Slow 1100 mV 0 °C model. The output path in its command line, a folder on the architect's computer, is masked as `<local>/`; nothing else is changed.
- `DE10_Nano_wpms-Resource_Utilization_by_Entity.rpt` (2026-10-04 09:22:08), and `ledger.md`, made from it by `hw/tools/resource_ledger.py`.

## Expected (written before the compile) / 期待値

| # | Expected | Written in |
|---|---|---|
| H1 | clk_sys closes at the slow corner; the four groups of the second fit leave the failing list | `phase6_silicon.md` §11.6 |
| H2 | MUL/MAC into Accm about 15 ns | §11.6 |
| H3 | The switch's GO check: slack about +3 ns | §11.6 |
| H4 | BCP's EW5: `bcp_commit` about 9 ns after the clock | §11.6 |
| H5 | The Core's imem path, with the 14 ns read side: about +2 ns | §11.6 |
| H6 | The new paths (`store_q`, the EW5 lookahead) each below 20 ns; the lookahead with the least margin, about +4.5 ns | §11.6, §11.5 |
| H7 | Hold met. The Formation about 1,000–2,000 ALMs larger than in the second fit. This was revised on 2026-10-03, before the compile, from Yosys's +2,030 LUTs; it was first written as 400–600 | §11.6 |

## Observed / 観測値

| # | Observed | Verdict |
|---|---|---|
| H1 | **clk_sys meets: setup +0.978 ns, TNS 0** (the multicorner worst, at the Slow 1100 mV 0 °C model). Hold +0.042 ns, minimum pulse width +4.544 ns. Every other clock meets: FPGA_CLK1_50 +13.522 ns, tck +3.530, hdmi_tx_clk +2.975 / +2.972, pixel +7.081, MCLK +75.685. No endpoint fails | as expected |
| H2 | All 10 worst endpoints are bits of `w_hi`, the product's high bits kept for the late E8. Each path starts at `x_mode[3]`; the worst has 18.821 ns of data delay and slack +0.978 ns, the 10th +1.547 ns. The worst path, piece by piece (ns): the opcode decode and MAC's operand select (`Decoder0 → WideOr3`, fan-out 91, `→ Equal54`, fan-out 46, `→ m_b`) 3.47; the route to the DSP 0.60; the DSP 4.40; the product's carry chain 2.73; the realign shift 2.25; MAC's add, up to bit 58, 3.93; into `w_hi` through the register's own load input 1.44 | **not as estimated**: 18.8 ns, not about 15. The estimate left out the opcode decode in front of the operand select. MAC's add also runs up to the product's high bits, not only to Accm's 32 |
| H3–H6 | None of these paths is among the 10 worst endpoints, so each has a slack of at least +1.547 ns at this corner: the switch, BCP's EW5, the Core's imem path, `store_q`, and the EW5 lookahead. Their own margins are not in these reports | met (a lower bound) |
| H5, the clock | clk_sys's minimum pulse width slack fell by 3.997 ns from the second fit (8.541 → 4.544). The time high went from 10 ns to 6 ns: the Fitter set the 30 % duty cycle exactly | as set (SD-23) |
| H7 | Hold met (+0.042 ns, thin). Resources (`ledger.md`, SILICON): the whole design 11,321.7 ALMs, 14,835 registers, 22 M10K and 23 DSP. The first fit had 11,052.8 ALMs; the second fit's ledger was not taken. The Formation: 7,048.0 ALMs (first fit 6,788.7: +259.3) and 9,267 registers (−449). The switch 1,659.7 ALMs (−32.5); the Core 500.9 (457.7) | resources **far below the estimate**: +259 ALMs, not 1,000–2,000. Yosys's LUT count was a poor measure of this logic in ALMs |

## What it means / 意味

- **SD-22 is resolved for the 50 MHz revision.** Step 2 and SD-23's duty cycle close clk_sys together. The first fit was −14.307 ns and the second −6.976 ns; this fit has +0.978 ns with TNS 0.
- **The margin left is MAC into `w_hi`: +0.98 ns at the 0 °C corner.** If more is wanted, the 3.5 ns at its front (the opcode decode into the operand select) can be registered with the issue, as step 1 did with the address decode. That is not needed for 50 MHz.
- **SignalTap is not in this build** (`ledger.md`: absent). A build with `wpms_tap.stp` is a new fit, and its timing should be read again. The captures C1–C5 come next, on that build.
- **100 MHz:** after 50 MHz operation is established (the architect, 2026-10-04).

## 和文

- 第 3 回フィットで、clk_sys のセットアップが **+0.978 ns、TNS 0** となり収束した（最悪は Slow 1100 mV 0 °C モデル）。ホールドは +0.042 ns、ほかのクロックもすべて満たす。
  - これまでの推移：第 1 回 −14.307 ns、第 2 回 −6.976 ns、第 3 回 +0.978 ns。
- 最悪 10 端点は、すべて `w_hi`（遅延 E8 用に取る積の上位）。経路は `x_mode[3]` から始まり、データ遅延は 18.82 ns。
  - 内訳：命令デコードと MAC の乗数選択 3.5 ns、DSP 4.4 ns、積の加算 2.7 ns、桁合わせ 2.3 ns、MAC の加算 3.9 ns、取り込み 1.4 ns。
  - 見込み（約 15 ns）は、乗数選択の前のデコードを落としていた。
- スイッチ、EW5、Core の imem 経路、先読み、EW5 の先行計算は、いずれも最悪 10 本に入らない（スラック +1.547 ns 以上）。
- clk_sys の最小パルス幅のスラックが 4.0 ns 減っており、デューティ比 30 %（ハイ 6 ns）が設定どおり入ったことがわかる。
- 資源は全体 11,321.7 ALM、Formation 7,048.0 ALM（第 1 回比 +259）。見込みの +1,000〜2,000 は過大だった。
- SignalTap を入れたビルドは別のフィットになるので、タイミングを改めて確認する。100 MHz は 50 MHz の動作確立後（2026-10-04、アーキテクト）。
