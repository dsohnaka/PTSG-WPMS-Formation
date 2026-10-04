# Observation — the SignalTap build: clk_sys still closes / 観測——SignalTap 入りビルド：clk_sys は収束したまま

*CC0 · 2026-10-04 · STA (TimeQuest) · Quartus Prime Lite 23.1std.1 · revision `DE10_Nano_wpms` (50 MHz, clk_sys 30 % high) with the SignalTap instance of `wpms_tap.stp` · 5CSEBA6U23I7.*

*The architect sent this report later on 2026-10-04 as the timing of the SignalTap build on which the captures C2–C5 were taken (`signaltap/2026-10-04_phase6_C2_full8/` … `_C5_ew5/`). The report itself is dated 22:55:41, after the captures. The RTL is the third fit's (`quartus/2026-10-04_DE10_Nano_wpms_fit3/`), unchanged since fe38260; the build adds the SignalTap instance: 405 taps of clk_sys, depth 4,096.*

*アーキテクトが、C2〜C5 を取ったビルドのタイミング報告として送ったもの。RTL は第 3 回フィットと同じで、SignalTap のインスタンスだけが加わっている。*

## Input / 入力

- `DE10_Nano_wpms-Multicorner_Timing_Analysis_Summary.rpt`, kept as received.

## Expected / 期待値

No figure was predicted. The third fit's note (2026-10-04) said only that a build with `wpms_tap.stp` is a new fit, and that its timing should be read again. What the captures need: every clock meets.

## Observed / 観測値

Multicorner worst-case slack in ns; the third fit's values (without SignalTap) for comparison.

| Clock | Setup | Hold | Min. pulse width | Third fit: setup / hold / MPW |
|---|---|---|---|---|
| clk_sys (`u_pll_sys` divclk) | **+0.557** | +0.076 | +4.540 | +0.978 / +0.042 / +4.544 |
| FPGA_CLK1_50 | +13.567 | +0.145 | +9.064 | +13.522 / +0.162 / +9.064 |
| altera_reserved_tck (JTAG; recovery +31.761, removal +0.429) | +3.084 | +0.168 | +18.136 | +3.530 / +0.169 / +18.220 |
| hdmi_tx_clk | +2.975 | +2.968 | — | +2.975 / +2.972 / — |
| pixel (`u_pll_pix` general[0]) | +7.422 | +0.195 | +5.787 | +7.081 / +0.176 / +5.787 |
| MCLK (`u_pll_aud`) | +74.015 | +0.175 | +39.885 | +75.685 / +0.175 / +39.883 |

The design-wide TNS is 0.0 for every clock and every analysis.

## Verdict / 判定

- **Every clock meets with the SignalTap instance in.** clk_sys keeps +0.557 ns of setup slack at the worst corner, 0.421 ns less than without SignalTap; its hold slack rose to +0.076 ns. The JTAG clock of the instance meets with +3.084 ns.
- **The captures C2–C5 were taken on a timing-closed build,** which this report shows, as the architect gives it for that build.
- **C1** was taken earlier the same day, on the build of the architect's previous session. Its timing summary has not been sent. The RTL is the same.
- The paths behind the 0.557 ns are not in this summary. Without SignalTap, the worst was MAC into `w_hi`; the taps' own registers and the buffer's write path now share clk_sys with it.

**和文.**
- SignalTap 入りでも全クロックがタイミングを満たす。TNS はすべて 0。
  - clk_sys のセットアップ余裕は +0.557 ns で、SignalTap なしより 0.421 ns 減った。ホールドは +0.076 ns。
  - JTAG クロックは +3.084 ns。
- C2〜C5 は、タイミングの閉じたビルドで取られた。C1 は前のセッションのビルドで、そのタイミング報告は未着（RTL は同じ）。
