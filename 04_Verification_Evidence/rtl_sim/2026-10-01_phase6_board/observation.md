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

(filled from the recorded run)
