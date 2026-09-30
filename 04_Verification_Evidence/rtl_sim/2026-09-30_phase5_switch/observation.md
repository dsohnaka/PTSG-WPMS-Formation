# Observation — Phase 5, the minimal input switch / 観測——Phase 5 最小の入力スイッチ

*CC0 · 2026-09-30 · RTL-SIM (Icarus Verilog 12.0, `-g2012`) · `03_Sample_Implementations/hw/switch/run_phase5.sh`. The expectations below were written before the recorded run was read; the observed values follow them.*

*期待値は記録実行の結果を読む前に書いた。観測値はその後に記す。*

## Expected (written first) / 期待値（先に記す）

| # | Expected | From |
|---|---|---|
| E1 | Every transaction's answer (data read, refused or not) equals `switch_model.py`'s | Ch.5 §5.4-§5.6 as realized; phase5_switch.md §4.4 |
| E2 | Every write the switch presents on the Formation's inbox port — clock, address, data — equals the model's list, in order | the switch's contract (EXEC, then the registered write) |
| E3 | Each command of the deterministic controller becomes exactly one port-0 transaction (a write and its read-back, or a read) with the same fields; its probe returns that transaction's answer; each KEY[0] press becomes one GO_ALL; nothing else reaches port 0, also after a design reset with the toggles set | `wpms_host_bridge.v` protocol |
| E4 | Port 3 plays the ROM's list (21 writes; 22 with the test image) after each reset, each KEY[1] and each accepted TEST_ORIGIN; the test image's own TEST_ORIGIN write is refused | Ch.5 §5.8, CR5-R1; choice C-13 |
| E5 | Every latched bundle and every output sample equal `sweep_sim.Reference` → `l1_model.py` (the customer's oracle) fed with the model's takes and knobs: bit-exact | Phases 3-4; Ch.5 §5.2 (exactly once, one sample boundary) |
| E6 | Every GO plays from the second strobe after its acceptance: 2 × T_max = 2,084 clocks (50 MHz) / 4,168 (100 MHz) at most | Ch.5 §5.4.3; Formation RH004 |
| E7 | In the timing case, hand-overs are presented at strobe offsets −1, 0 and +1, and every take is heard | the case's purpose |
| E8 | The apply step executes 2 clocks after inbox_taken rises; its write lands before the next strobe | CR5-I3; the switch's timing assumption |
| E9 | The test origin played from the ROM: PCM peak −12.44 dBFS (N = 1,008, 50 MHz) and −6.29 dBFS (N = 2,048, 100 MHz) at G = 12 | phase4_l1.md; SD-17 (a) |
| E10 | Strobe interval 1,041/1,042 (50 MHz) and 2,083/2,084 (100 MHz); SWEEP_CLOCKS_MAX < T_min; no overrun | Phase 4 |
| E11 | No Formation error, no Core halt, no simulator WARNING or ERROR line | — |
| E12 | Every mutant of `cosim_switch_mutants.py` killed | — |
| E13 | The Phase 2, 3 and 4 recipes green on the Formation's RH004 and the ADV7513 table's RH002 | regression |
| E14 | Under tclsh, against stand-ins of the Quartus ISSP commands, `wpms_music_demo.tcl` makes exactly the transactions of `wpms_music.py`'s steps — the list the music case plays in RTL-SIM — also with late acknowledges, hex without leading zeros and toggles left set by an earlier session; a refused write is reported; a missing acknowledge ends in an error, not a hang. *Not Quartus, not the RTL: a check of the scripts* | `hw/tools/host/check_host_tcl.py` (E14 added before the second recorded run, when a tclsh became available) |

## Observed (the recorded run) / 観測値（記録実行）

Fifteen system runs of `cosim_switch.py`, recorded by `run_phase5.sh`:
- 50 MHz budget (NMAX 1,008, T_min 1,041): origin, music, reject, timing, bridge, and random seeds 1–3;
- 100 MHz budget (NMAX 2,048, T_min 2,083): the same cases, and random seed 4;
- the test ROM image.

Logs: `logs/cosim_switch.txt`.

| # | Observed | Verdict |
|---|---|---|
| E1 | 17,679 transactions (16,229 on port 0, 1,450 on port 3), 1,630 of them refused: **17,679 answers equal** to the model's | as expected |
| E2 | 6,664 writes presented on the inbox port, **identical** to the model's list in clock, address and data. Among them, 966 hand-overs whose GO_SEQ side band is identical too | as expected |
| E3 | 7,348 host writes (each followed by its read-back), 1,430 host reads and 103 KEY[0] presses became exactly **16,229 port-0 transactions**, all as commanded; every probe answer equal. This held with skew of 1, 2 and 3 clocks and through 3 design resets with WR, RD and both toggles set: no transaction replayed | as expected |
| E4 | **69 complete plays** of the ROM's list, after resets, KEY[1] and TEST_ORIGIN. In the random runs, 178 ROM writes were refused while the host held block 0 or the sweep word armed (choice C-8). The test image's own TEST_ORIGIN write was refused | as expected |
| E5 | **4,209 bundles** of closed sweeps and **2,378 output samples**, bit-exact against `sweep_sim.Reference` → `l1_model.py` (customer's oracle), in all fifteen runs | as expected |
| E6 | **960 GOs**, every one played from the **second** strobe after its acceptance. 50 MHz: 1,043 … 2,084 clocks (1.0013 … 2.0006 periods), over 704 GOs; 100 MHz: 2,084 … 4,167 clocks (1.0003 … 2.0002 periods), over 256 GOs. The excess over 2.000 is the strobe's quantization: intervals of 1,041/1,042 clocks for a period of 1,041.67 | as expected |
| E7 | Timing case: hand-overs at offsets −2 … +3 (50 MHz) and −3 … +3 (100 MHz), including −1, 0 and +1. **62 of 62** takes heard at each budget; 1,188 and 1,195 bundles equal | as expected |
| E8 | The apply step always ran **2 clocks** after inbox_taken rose; its write landed **22 clocks or more** before the next strobe | as expected |
| E9 | The test origin played from the ROM: PCM peak 2,002,439 = **−12.44 dBFS** (N = 1,008, 50 MHz) and 4,068,448 = **−6.29 dBFS** (N = 2,048, 100 MHz). After reset: GO_SEQ = APPLIED_SEQ = 1 and APPLIED_SAMPLE = 2 (sweep 2 is the first to play it); CONFIG = 0x0003F081 | as expected |
| E10 | Strobe interval 1,041 … 1,042 and 2,083 … 2,084; SWEEP_CLOCKS_MAX 1,028 and 2,068; no overrun | as expected |
| E11 | No Formation error, no Core halt, no simulator WARNING or ERROR line in any run | as expected |
| E12 | **22 of 22** mutants killed (`logs/cosim_switch_mutants.log`): the switch (W1–W9, W13–W22, including RH004's mirror in the strobe clock, W9), the Formation's RH004 undone (W10), the bridge (W11 no settling, W12 replay after a design reset). Each is caught by a named check: a transaction answer, the inbox-port list, a sweep's bundles or a Formation error | as expected |
