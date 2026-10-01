# Observation — Phase 6, the board top before the board / 観測——Phase 6 実機の前の基板トップ

*CC0 · 2026-10-01 · RTL-SIM (Icarus Verilog 12.0, `-g2012`) · `03_Sample_Implementations/hw/de10_nano/run_phase6.sh`. The expectations below were written before the recorded run was read; the observed values follow them. The checks marked stand-in run the project's Tcl and Verilog without Quartus.*

*期待値は記録実行の結果を読む前に書いた。観測値はその後に記す。「代役」と記した検査は Quartus なしで Tcl と Verilog を走らせたもの。*

## Expected (written first) / 期待値（先に記す）

| # | Expected | From |
|---|---|---|
| E1 | g = 0 between the packets of every sweep with more than one packet | brief Phase 6, item 1; Core commitment |
| E2 | T_wake (strobe → first packet_start) ≤ 4 clocks, nominally 2, in every sweep | item 2 |
| E3 | The packet window (Stay Set → the Stay word) + 2 ≤ N_MIN = 32 | item 3 |
| E4 | BCP (the BCP word → inbox_taken) ≤ 10 clocks with the full take-set: eight blocks, the full mask, the sweep word | item 4 |
| E5 | A full-load sweep (sum of bins = NMAX): strobe → asleep ≤ T_min (1,041 / 2,083), housekeeping included | item 5 |
| E6 | Each of EW2–EW6, injected: exactly one rise of error_flag, with its code; from it on no packet_start, no bin_valid, and every bank written zero; the Core halts | item 6 |
| E7 | Every bundle latched at packet_start equals the model's (`switch_model.py` → `sweep_sim.Reference` → `l1_model.py`) | item 7 |
| E8 | Every bank equals the model's; the I2S wire carries the bank; after the first GO, the spectrum of the captured banks equals the model's (C5 + E5 left, E5 + G5 right) | item 8 |
| E9 | Board: the ADV7513 table written (29 writes), no NACK; video lines of 1,650 pixels with 1,280 active; HDMI_TX_CLK 6.0–7.5 ns after each pixel edge; strobe intervals T_min / T_min + 1; no overrun; LEDs as the README says (error and halt only in the injection runs); no simulator WARNING or ERROR line | `hw/de10_nano/README.md` §2 |
| E10 | Every run, cut as its SignalTap capture (C1–C5: depth 4,096, 12 % before the trigger, the qualifier where enabled) and written as a SignalTap export, is read back unchanged by `phase6_evidence.py` and agrees with the full run | the silicon path, dry-run |
| E11 | The Quartus project (stand-in): the pins equal the golden top's, every file present, five clock groups covering every clock, `hdmi_tx_clk` from the 180° counter, the pixel bus at −max 2.0 / −min −1.5 ns; the INTEL branches elaborate with the expected PLL, memory and ISSP parameters; 7/7 broken copies caught | `make_quartus_project.py --check --mutants` |
| E12 | The host scripts (stand-in): the six Phase 6 scripts make exactly the transactions of their steps, one GO each applied; 8/8 broken copies of the host procedures caught | `check_host_tcl.py` |
| E13 | The injection images regenerate identically | `gen_inject_scores.py --check` |
| E14 | The Phase 2, 3, 4 and 5 recipes green on wpms_system RH002 | regression |
| E15 | The board top and its bench compile with `-Wall`, with no line from `hw/de10_nano` | — |

## Observed (the recorded run) / 観測値（記録実行）

The recorded run: `run_phase6.sh` at 2026-10-01T14:45:10Z (REGRESSION=0). The regression: the same recipe with REGRESSION=1 on the same RTL, at 13:43:18Z; its board part gave the same 18 verdicts.

Eighteen board-level runs:
- 50 MHz budget (NMAX 1,008, T_min 1,041) and 100 MHz budget (NMAX 2,048, T_min 2,083);
- cases origin, first_go, full8, ew6, ew2, ew3, ew4, ew5, pcm;
- logs: `logs/cosim_board.txt`; per case: `expected/<case>_<budget>.json`.

| # | Observed | Verdict |
|---|---|---|
| E1 | g = **0** in every sweep with more than one packet: full8 (8 packets; 47 sweeps at 50 MHz, 45 at 100) and first_go (3 packets; 45 and 44 sweeps) | as expected |
| E2 | T_wake = **2** clocks in every sweep of every run, both budgets | as expected |
| E3 | window **28** clocks (Stay Set → the Stay word) → floor **30** ≤ 32, in every packet of origin, first_go and full8, both budgets | as expected |
| E4 | BCP with the full take-set **10** clocks, both budgets — **at the bound**; 2–3 without a take, up to 5 with the triad's three blocks | as expected (no margin: phase6_silicon.md §4.2) |
| E5 | strobe → asleep **1,023** (50 MHz; 47 full-load sweeps of full8, 62 of the origin) and **2,063** (100 MHz; 45 and 62) — within 1,041 and 2,083. The L1's own SWEEP_CLOCKS_MAX (0x299): 1,028 and 2,068 | as expected |
| E6 | EW2, EW3, EW4, EW5, EW6 each raised **exactly once, with its code**, at both budgets. After the flag: **0 packets, 0 bins**, and the 59–62 banks written later all **zero**. The Core halted 9 clocks after EW2 and 11 after EW5; at the end of the packet's Stay after EW3, EW4 and EW6 (1,005, 1,001, 1,000 clocks at 50 MHz; 2,045, 2,041, 2,040 at 100) | as expected |
| E7 | **534 / 534** bundles at 50 MHz and **531 / 531** at 100 MHz equal to the model. Started from the GO alone on a capture after it: first_go 121/121 and full8 321/321 (with 41/41 banks), at each budget | as expected |
| E8 | **1,320 / 1,320** banks (50 MHz) and **1,316 / 1,316** (100 MHz) equal to the model; I2S frames decoded 1,629 and 1,625, **0 mismatches** with the bank. After the GO (pcm case, 1,147 / 1,146 samples), peaks: left 524.4 and 659.2 Hz, right 660.6 and 782.2 Hz — the model's identical. The triad's peak −26.4 dBFS | as expected |
| E9 | In every run: ADV7513 table done (29 writes), no NACK; HS, VS, DE and TX_CLK-phase faults 0; strobe intervals 1,041/1,042 and 2,083/2,084; no overrun; no host time-out; no simulator WARNING or ERROR line. Error and halt LEDs in the five injection runs only | as expected |
| E10 | 16 cuts (8 cases × 2 budgets: C1 origin, C2 full8, C3 first_go qualified — 175 / 173 events — C4 ew6, C5 ew2–ew5) written as SignalTap exports and **read back unchanged**. In them: T_wake, window and g as in the full runs; C1 and C2 each hold a full-load sweep (1,023 / 2,063); C2 the full take-set's BCP (10); C3 128/128 and 127/127 bundles, 47/47 and 46/46 banks; C4 and C5 each code with silence after it. Kept as `expected/expected_<case>_<budget>.vcd.gz` | as expected |
| E11 | Both revisions under tclsh: 52 pins equal to the golden top's; 29 files present; 12 clocks in 5 groups; `hdmi_tx_clk` from the 180° counter; pixel bus −max 2.0 / −min −1.5 ns. Elaborated with the INTEL branches: 9 primitives, each with the expected parameters. **7/7** broken copies caught (`logs/make_quartus_project.log`) | as expected (stand-in) |
| E12 | The six Phase 6 scripts: 370 writes and 38 reads, each script's steps in order, one GO each applied; the Phase 5 cases still pass; **8/8** broken copies caught (`logs/check_host_tcl.txt`) | as expected (stand-in) |
| E13 | The 20 files of the five injection images regenerate identically (`logs/gen_inject_scores.log`) | as expected |
| E14 | ALL PHASE 2, 3, 4 and 5 CHECKS PASSED (`logs/phase{2,3,4,5}_regression.txt`) | as expected |
| E15 | `iverilog -Wall`: 16 lines, all Icarus's notes on the Core copy, the imem wrapper and the L2 sources (inherited timescale, the tri0 port, `@*` over arrays), as in Phases 3–5; **0 from hw/de10_nano** (`logs/compile6.log`) | as expected |

Resources: ESTIMATE only (`logs/yosys_stat.txt`, Yosys, not Quartus). The ledger is the Fitter's, after the architect's compile.

資源は概算のみ（Quartus ではない）。台帳はアーキテクトのコンパイル後に Fitter の結果から作る。
