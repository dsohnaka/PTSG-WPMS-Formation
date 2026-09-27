# `hw/` — the silicon phase / シリコン化段階

**MIT.** Layer 3 hardware and generators written under `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md`. Illustrative, not normative; the law is `01_Architecture/`, the golden models are `../tools/` and the customer's `wpms_layer1_oracle.py`.

**MIT。** `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` に従って書く第3層のハードウェアと生成器。例示であって規範ではない。法は `01_Architecture/`、黄金モデルは `../tools/` と顧客の `wpms_layer1_oracle.py`。

## Status / 状況

| Phase | State | Report |
|---|---|---|
| 0 Baseline | done — all golden models and the frozen Core green | `04_Verification_Evidence/reports/phase0_baseline.md` |
| 1 Core copy (RH031 provisional, `stay_value` form B) | done — bit-identical with the pin silent; SV-0 … SV-7 pass; the anti-pattern is caught | `04_Verification_Evidence/reports/phase1_core.md` |
| 2 L2 Formation datapath | done — bit-identical to `pfasm_tools_w.Machine` on 3,914 cases (programs, 13 negatives, hardware-only E4, 3,000 random sequences); 20/20 mutants caught; decode map, assemblers, score round trip | `04_Verification_Evidence/reports/phase2_datapath.md` |
| 3 sequencer · 4 L1 · 5 switch · 6 DE10-nano | not started (stopped after Phase 2 for the architect's reading) | — |

## Layout / 構成

| Path | What |
|---|---|
| `core/ptsg_core_rh031p.v` | Working copy of PTSG-Core RH030 (module `ptsg_core`) + RH029/030 header patch + `stay_value` (C4-F15…F17, C5-F4; form B; `CNT_W` = 12) + draft RH031 entry. The frozen `PTSG-Core/…/ptsg_core.v` is never edited. |
| `core/ptsg_core_sv_tb.v` | SV-0 … SV-7 (+ SV-5b) of `stay_value_reference_sketch.md` §7; two tops (`ptsg_core_sv_tb`, `ptsg_core_sv0_tb`). |
| `core/run_phase1.sh` | Phase 1 recipe (RTL-SIM). |
| `tools/run_phase0_baseline.sh` | Phase 0 recipe (golden models + frozen Core testbenches). |
| `tools/vcd_compare.py`, `tools/vcd_dump.v` | VCD comparison by signal name; a dump root for unchanged testbenches. |
| `l2/wpms_formation.v` | The L2 Formation datapath (Phase 2): issue register + execute, slot-major store and inbox, CUR alias, STP, BCP with background copy and forwarding, errors → insertion. |
| `l2/wpms_decode.vh`, `l2/decode_map.md` | Generated from `tools/decode_map.json` by `tools/gen_decode.py` (do not edit). |
| `l2/programs/*.hex` | The three window programs, assembled by `tools/pfasm_as.py`. |
| `l2/scores/d3_sketch_r1_fixture.*` | Test fixture for `tools/score_as.py`: the D3 §3 sketch, literal — **not** the Phase 3 score (SD-05, SD-14). |
| `l2/wpms_formation_tb.v`, `l2/score_rt_tb.v` | The cosimulation testbench (stands where the Core stands); the score round trip on the Core copy. |
| `l2/run_phase2.sh` | Phase 2 recipe (RTL-SIM; resource ESTIMATE if `yowasp-yosys` is installed). |
| `tools/decode_map.json` | The one source of the encoding: RTL table, assemblers, published map. |
| `tools/pfasm_as.py`, `tools/score_as.py` | Window-program assembler (`.pfasm` → Global words); score assembler (Core words + TS_PKT/TS_CSEL + window splices → `.hex`/`.mif`). |
| `tools/cosim_l2.py`, `tools/cosim_mutants.py`, `tools/score_rt.py` | Cosimulation against the golden model; the mutant check; the score round trip. |
| `l1/`, `switch/` | (later phases) |

## Running / 実行

The scripts expect the workspace of the brief: four repositories side by side (`PTSG-Core`, `PTSG-CPU-Formation`, `PTSG-WPMS-Formation`, `FPGA_Spectrum_Engine_OpenPrompt`). Icarus Verilog ≥ 12 (`-g2012`) and Python 3.

```sh
03_Sample_Implementations/hw/tools/run_phase0_baseline.sh    # logs -> 04_Verification_Evidence/reports/logs/phase0
03_Sample_Implementations/hw/core/run_phase1.sh [EVIDENCE_DIR]   # build -> hw/core/build (git-ignored)
03_Sample_Implementations/hw/l2/run_phase2.sh [EVIDENCE_DIR]     # build -> hw/l2/build (git-ignored)
```

Each script prints its checks and ends with a one-line verdict; `run_phase1.sh` and `run_phase2.sh` exit non-zero if any expectation fails. Phase 2's optional resource estimate needs `pip install yowasp-yosys`. / 各スクリプトは検査を表示し、一行の判定で終わる。
