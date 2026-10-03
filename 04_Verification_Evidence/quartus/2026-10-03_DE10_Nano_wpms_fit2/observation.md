# Observation — Phase 6, the second fit (SD-22 step 1) / 観測——Phase 6 第 2 回フィット（SD-22 段階 1）

*CC0 · 2026-10-03 · STA (TimeQuest) · Quartus Prime Lite 23.1std.1 · revision `DE10_Nano_wpms` (50 MHz) · 5CSEBA6U23I7.*

*Compiled by the architect from main 8815e35: Formation RH005 and switch RH002 (SD-22 step 1, ruling 2026-10-03). The expectations quoted below were written before the compile (`reports/phase6_silicon.md` §10.3–§10.4).*

*期待値はコンパイル前に書かれたもの（§10.3–§10.4）を引用した。*

## Inputs / 入力

- `DE10_Nano_wpms-Multicorner_Timing_Analysis_Summary.rpt` (2026-10-03 17:29:38).
- `DE10_Nano_wpms-Slow_1100mV_85C_worst_path.rpt`: the architect's `report_timing -setup -multi_corner -npaths 1 -detail full_path` from and to clk_sys (18:13:44). The output path in its command line, a folder on the architect's computer, is masked as `<local>/`; nothing else is changed.
- `setup_clk_sys_groups.txt` and `setup_clk_sys_keys.rpt`: `hw/de10_nano/report_setup_paths.tcl` (RH002) run by the architect on this compile, unchanged. The first groups every failing clk_sys endpoint (slow 1100 mV 85 °C model) by register and by the start of its worst path; the second gives the worst full path into each register class (Accm, Temp, ADRS, the store, the pending masks, `inbox_taken`, `taken_due`, SWEEP.a, the error registers, the switch, the sequencer, the Core, L1).

## Expected (written before the compile) / 期待値

| # | Expected | Written in |
|---|---|---|
| G1 | The store leaves the critical path; what remains longest is MUL/MAC @PPM into Accm and the error registers | `phase6_silicon.md` §10.3 |
| G2 | "My estimate is that MUL/MAC @PPM is close to 20 ns on this speed grade; if it does not close, that path is what step 2 removes" | §10.3 |
| G3 | The first fit's worst path, `sweep_staged → … sum_n … → inbox_taken`, more than halved in gate levels (131 → 61) | the reply of 2026-10-03 on the architect's TimeQuest path |

## Observed / 観測値

| # | Observed | Verdict |
|---|---|---|
| G1 | The worst path is `pmask[1][0] → Mux1729 … Mux1836 → m_b[10] → Mult0 (DSP, then the fabric carry chain) → ShiftRight1 → Add0 → Equal26 → always41~28 → accm[8]~16 → accm[8].ena`. That is the forwarded store read, the 32 × 32 product, the shift, MAC's add, the overflow compare, and Accm's enable. The store's write enables are no longer on it | as expected |
| G2 | clk_sys setup **−6.976 ns** (multicorner; −6.805 ns in the slow 1100 mV 85 °C report), **TNS −1,509.093 ns** (first fit: −14.307, −65,525.293). Hold +0.011 ns, met but thin. The path takes **26.179 ns**, not close to 20: store read with forwarding 7.86 ns; DSP 0.79 + 4.26 ns; the product's carry chain 3.37 ns; shift 2.84 ns; Add0 1.79 ns; compare 1.92 ns; enable 3.34 ns. Every other clock meets: FPGA_CLK1_50 +13.759, tck +3.392, hdmi_tx_clk +2.966 / +2.972, pixel +7.248, MCLK +74.823 | **not as expected** — short by 7 ns; step 2 |
| G3 | The first fit's worst path is no longer the worst. The grouped report: **799 failing endpoints, TNS −1,398 ns** (slow model), in four groups by where their worst paths start (G4) | the BCP/EW5 path more than halved, as expected; but three other groups fail (G4) |
| G4 | (not expected before the compile; read from the grouped report) **(1) The switch's GO check**, 469 endpoints, worst −2.605 ns, TNS −805 ns: `x_a → xb → frozen[xb] → the items fired → n_nx_v → the entry mux → the sum (three adders) → go_bad → fire_now →` the enables of `n_fu_v`, `cmask_v`, `reject0/3`, `go_seq`, `sw_fu`, `ibx_*` (fan-out 173), 21.9 ns. **(2) MUL/MAC @PPM**, 49 endpoints (Accm, the error registers, `insert_req_r`), worst −6.805 ns (G2). **(3) BCP's EW5**, 168 endpoints (the pending masks, `inbox_taken`, `taken_due`, SWEEP.a, copied), worst −4.812 ns: the switch's take mirror `ft` (merged by Quartus with the Formation's `take`) → `new_list` → `n_post` → the EW5 adder tree (three adders) → the compare → `bcp_commit` (fan-out 131) → `pm_next` → `inbox_taken`, 24.2 ns. **(4) The Core's imem half-cycle path**, 113 endpoints (`state_num`, `loop_cnt`, `stay_cnt`, `queued_target`, `hr_*`, `fsm`), worst −2.028 ns: the M10K, clocked on clk_sys's falling edge (`ptsg_imem`, EDGE "NEG"), → `Decoder0 → WideOr7` ×4 `→ state_num` next-state logic, 10 levels, 10.703 ns of data delay against the 10 ns half period, with −1.245 ns of clock skew (the M10K's own clock delay, 1.518 ns, lies on the launch side) | (1)–(3) are SD-22 step 2's; (4) is new: **SD-23** |

**A note on the path.** The path STA reports is structural. It enters through MUL's operand (the store read into `m_b`) and leaves through MAC's add and overflow. As an instruction, MUL never uses Add0, and MAC's `m_b` is Temp, not the store. Without Add0, the real MUL path is about 1.8 ns shorter — still about 5 ns short.

和文：
- 段階 1 で最悪スラックは −14.3 → −7.0 ns、TNS は −65,525 → −1,509 ns に改善した。
- 残る最悪経路は MUL/MAC @PPM の実経路で、内訳はストア読出しと転送 7.9 ns、DSP と部分積加算 8.4 ns、シフト 2.8 ns、桁あふれ比較と書込み許可 5.3 ns。
- 20 ns には 7 ns 足りないので、裁定どおり段階 2 へ進む。
- 集計（`report_setup_paths.tcl`）では、失敗 799 端点が四群に分かれた。スイッチの GO 検査（−2.6 ns、469 端点）、MUL/MAC（−6.8 ns）、BCP の EW5（−4.8 ns）、そして Core の imem 半周期経路（−2.0 ns、113 端点）。最後の一つは新しい項目で、SD-23 として記録する。
