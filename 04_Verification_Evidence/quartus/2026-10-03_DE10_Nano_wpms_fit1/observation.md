# Observation — Phase 6, the first fit / 観測——Phase 6 初回フィット

*CC0 · 2026-10-03 · SILICON (the Fitter's resource numbers) and STA (TimeQuest) · Quartus Prime Lite 23.1std.1 · revision `DE10_Nano_wpms` (50 MHz) · 5CSEBA6U23I7.*

*The architect compiled it after `wpms_adv7513_cfg.v` RH003 (commit 6fa3c93).*

*The expectations below are the ones written before the compile, quoted from where they were written. Nothing was added to them afterwards.*

*期待値は、コンパイル前に書かれたものを出典から引用した。後から書き足したものはない。*

## Inputs / 入力

- `DE10_Nano_wpms-Multicorner_Timing_Analysis_Summary.rpt` — TimeQuest, 2026-10-03 15:22:12.
- `DE10_Nano_wpms-Resource_Utilization_by_Entity.rpt` — the Fitter.
- `ledger.md` — generated from the second report by `hw/tools/resource_ledger.py`, with `--revision "DE10_Nano_wpms (50 MHz): Core RH031p, Formation RH004, cfg RH003" --date 2026-10-03`.
- Also received: *Timing Closure Recommendations*, exported as plain text. It is empty, because Quartus writes that report in HTML only, so it is not kept.

## Expected (written before the compile) / 期待値（コンパイル前の記述）

| # | Expected | Written in |
|---|---|---|
| F1 | The first compile shows whether Quartus accepts the PLL strings and places three PLLs, two of them fractional, on these clock pins ("not judged here") | `hw/de10_nano/README.md` §1; `phase6_silicon.md` §3.4 |
| F2 | The SDC finds every clock; `hdmi_tx_clk` is generated from the 180° counter. If it were not found, a critical warning would say so | README §1 |
| F3 | The HDMI pixel bus is checked against `hdmi_tx_clk`: t_VSU 1.8 ns, t_VHLD 1.3 ns, +0.2 ns for the board | README §1; the SDC header |
| F4 | "At 100 MHz the expected critical path is the imem half-cycle path." Nothing said that 50 MHz might fail | README §1; `phase6_silicon.md` §3.4 |
| F5 | Three Formation paths are "long for one clock" at 100 MHz: MUL @PPM, BCP's EW5, and the commit fan-out | `phase2_datapath.md` §6 Q4 |
| F6 | The ESTIMATE (Yosys, not Quartus): 10,245 LUTs + 4,019 arithmetic ALUTs; 6,479 flip-flops; 1,538 MLAB cells; DSP 16 + 6; M10K 2 inferred + 6 in black boxes | `phase6_silicon.md` §7 |

## Observed / 観測値

| # | Observed | Verdict |
|---|---|---|
| F1 | Analysis & Synthesis, the Fitter and TimeQuest all completed, in about ten minutes. The three PLLs appear in the clock list with their slacks: `u_pll_sys`, `u_pll_aud`, and `u_pll_pix` with two output counters | as expected |
| F2 | `hdmi_tx_clk` appears with setup and hold slacks, so the 180° counter was found. (The SDC's info line was not sent.) | as expected |
| F3 | `hdmi_tx_clk`: setup +2.975 ns, hold +2.968 ns | as expected |
| F4 | At 50 MHz **clk_sys fails**: setup −14.307 ns, TNS −65,525.293 ns; hold +0.033 ns. Every other clock meets (setup / hold, ns): FPGA_CLK1_50 +12.962 / +0.167; tck +3.395 / +0.167, with recovery +35.228 and removal +0.423; pixel +6.516 / +0.195; MCLK +74.428 / +0.298. Minimum pulse width is met everywhere | **not as expected** — SD-22 |
| F5 | The worst clk_sys path takes about 34 ns, so the named paths are too long even for 20 ns. By reading and gate depth (Formation 146, switch 99): the chain runs through the multiplier, the error priority and the one `x_commit` into the store's write enables and the background copy. The part after the multiplier is structural only (SD-22) | the paths as named; their length underrated |
| F6 | The Fitter: 11,052.8 ALMs; 14,312 combinational ALUTs; 15,318 registers; 22 M10K (59,013 bits); 23 DSP. Yosys's LUTs plus arithmetic ALUTs (14,264) are within 0.4 % of Quartus's combinational ALUTs; DSP went from 22 to 23. Where Yosys had used MLABs, Quartus used registers, plus M10K for the nine store banks the prefetch reads (its address register absorbed) | the estimate held for logic and DSP; memory was mapped differently |

## Resource ledger / 資源台帳 (SILICON)

The Core's format:

| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs |
|---|---|---|---|---|
| 2026-10-03 | DE10_Nano_wpms (50 MHz): Core RH031p, Formation RH004, cfg RH003 | 457.7 | 414.3 | 773 (725) |

Every WPMS entity is listed in `ledger.md`. SignalTap is not in this fit.

## What follows / 次に

- **The failing-path report.** Run `hw/de10_nano/report_setup_paths.tcl` RH002 on this database. Its `setup_clk_sys_groups.txt` will confirm or correct SD-22's reading.
- **The architect's ruling on SD-22:**
  - step 1, restructuring with behaviour unchanged;
  - step 2, a write-back clock, only if step 1 does not close.
- After each step: the Phases 2–6 recipes, then the next fit (`quartus/<date>_DE10_Nano_wpms_fit2/`).

和文：
- 初回フィットは最後まで通った。PLL 3 基は配置され、HDMI 画素バスのタイミングも満たした。
- clk_sys だけが 50 MHz で −14.3 ns 不足した。コンパイル前の見込み（100 MHz で imem 半周期パスが決め手）は外れ、SD-22 として記録した。
- 資源の概算は、論理と DSP ではよく当たった。メモリは Quartus が別の割付け（レジスタと M10K）をした。
