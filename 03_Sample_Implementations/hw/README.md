# `hw/` — the silicon phase / シリコン化段階

**MIT.** Layer 3 hardware and generators written under `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md`. Illustrative, not normative; the law is `01_Architecture/`, the golden models are `../tools/` and the customer's `wpms_layer1_oracle.py`.

**MIT。** `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` に従って書く第3層のハードウェアと生成器。例示であって規範ではない。法は `01_Architecture/`、黄金モデルは `../tools/` と顧客の `wpms_layer1_oracle.py`。

## Status / 状況

| Phase | State | Report |
|---|---|---|
| 0 Baseline | done — all golden models and the frozen Core green | `04_Verification_Evidence/reports/phase0_baseline.md` |
| 1 Core copy (RH031 provisional, `stay_value` form B) | done — bit-identical with the pin silent; SV-0 … SV-7 pass; the anti-pattern is caught | `04_Verification_Evidence/reports/phase1_core.md` |
| 2 L2 Formation datapath | done — bit-identical to `pfasm_tools_w.Machine` on 3,914 cases (programs, 13 negatives, hardware-only E4, 3,000 random sequences), and since SD-22 step 2 on 9 directed cases more (group `late`); 20/20 mutants caught (29/29 since step 2); decode map, assemblers, score round trip | `04_Verification_Evidence/reports/phase2_datapath.md` |
| 3 Sequencer and integration | done — Core + Formation + sequencer run the R1 score in its dispatch form (g = 0, T_wake 1) and its branch form; every latched bundle, N, K sequence and `stay_value` equal the sweep oracle's over 36,000 sweeps per budget; 100 MHz and 50 MHz budgets; injected errors silence L1 at once | `04_Verification_Evidence/reports/phase3_integration.md` |
| 4 L1 pipeline and output path | done — the L1 pipeline bit-exact with the customer's oracle (phase, exp2, amplitude, MG glide) and with the published model of the parts the oracle does not model (sin core, product, accumulators, output stage) over 1,000,000 unit inputs, 3 × 400 module sweeps, the whole synthesizer under the sweep oracle's traffic and on the 48 kHz I2S grid; I2S wire = bank; 927 audible bins; test-origin peak −6.29 dBFS; D_L1 = 19; 16 DSP, 1 M10K per module (ESTIMATE) | `04_Verification_Evidence/reports/phase4_l1.md` |
| 5 Minimal input switch | done — ports 0 (host, ISSP over JTAG: ruling 2026-09-30) and 3 (the ROM: the test origin at reset, KEY[1], TEST_ORIGIN; N = 1,008 at 50 MHz, SD-17 (a)); stage-arm-go with an atomic hand-over (Formation RH004); PR-1, PR-2 and the sum of N checked before a GO; APPLIED_SEQ / APPLIED_SAMPLE; the whole Ch.5 §5.6 map for one module. Every transaction, every inbox write, every bundle and every sample agree with the models (switch model, sweep_sim.Reference, l1_model over the customer's oracle) in directed, timing and random runs at both budgets; mutants killed; the host script's steps played through the same bit protocol | `04_Verification_Evidence/reports/phase5_switch.md` |
| 6 DE10-nano | prepared, waiting for the board — the board top (three PLLs, resets, HDMI video carrier, ADV7513 configurator, I2S + MCLK, LEDs, ISSP BRD, SignalTap taps), the Quartus project (revisions 50 / 100 MHz) and its SDC; the board-level RTL-SIM of every capture (origin, first GO, full take-set, EW2–EW6, the sound) within the brief's bounds and bit-exact with the models at both budgets; the expected values and captures written before the board; the SILICON captures are the architect's. First fit (2026-10-03): resources recorded; clk_sys 50 MHz short by 14.3 ns (SD-22). **SD-22 step 1** (ruling 2026-10-03): Formation RH005 and switch RH002 restructure the long paths with behaviour unchanged — equal to the previous revision in every clock (lockstep), the restructured logic proved equal (SAT), Phases 2–6 repeated. Second fit: −7.0 ns in four groups. **SD-22 step 2** (the same ruling): Formation RH006 (E8 of MUL/MAC decided in the next clock, Accm restored, the next instruction squashed; the operand and EW5's sum computed one clock ahead) and switch RH003 (the GO check from the request's fields; its sum by carry-save adders); two errors are raised one clock later with the same code and SN, nothing else changes (lockstep, SAT, Phases 2–6). **SD-23**: clk_sys 30 % high in the 50 MHz revision for the Core's imem half-cycle path; waiting for the third fit | `04_Verification_Evidence/reports/phase6_silicon.md` |

## Layout / 構成

| Path | What |
|---|---|
| `core/ptsg_core_rh031p.v` | Working copy of PTSG-Core RH030 (module `ptsg_core`) + RH029/030 header patch + `stay_value` (C4-F15…F17, C5-F4; form B; `CNT_W` = 12) + draft RH031 entry. The frozen `PTSG-Core/…/ptsg_core.v` is never edited. |
| `core/ptsg_core_sv_tb.v` | SV-0 … SV-7 (+ SV-5b) of `stay_value_reference_sketch.md` §7; two tops (`ptsg_core_sv_tb`, `ptsg_core_sv0_tb`). |
| `core/run_phase1.sh` | Phase 1 recipe (RTL-SIM). |
| `core/sd15_insert_handshake_tb.v`, `core/run_sd15.sh` | SD-15 bug report to the Core's office: the insertion handshake reproduced on the frozen source and on the copy (one Core, a six-word program; RTL-SIM). |
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
| `tools/equiv_lockstep.py`, `tools/equiv_formal.py`, `tools/gate_depth.py`, `tools/compare_regression.py` | SD-22: a restructured module against its previous revision (from a git commit) — side by side in every clock on random stimulus, with step 2's late errors allowed for (RTL-SIM); the restructured logic proved equal (SAT: Yosys builds the problem, CaDiCaL from python-sat solves it in step 2); the gate or 6-LUT levels in front of each register group (ESTIMATE); a rerun of Phases 2–6 against a recorded run (logs, board runs, expected captures). |
| `tools/vcd_i2s_check.py` | Phase 6: a SignalTap capture of the I2S pins, decoded and matched bit for bit against the L1 model of the test origin. The sweeps since the GO and G are found first, by the closed form. When the Core's `timing_signals[0]` is captured, its sweeps are measured against the audio frames. |
| `l2/wpms_sequencer.v` | The sweep sequencer (Phase 3): packet index, CUR, lanes STROBE / NONEMPTY / MORE, StayVal.s / StayVal.p → `stay_value`, bundle prefetch, window label (SSS), the L1 face (one clock after the Core, SD-11), L1 silenced on error. |
| `l2/wpms_l2_top.v` | Core RH031p + Formation + sequencer; JumpVal / LoopVal on the Core's indirect-read bus; insertion to the trap word; parameters for the 100 MHz and 50 MHz budgets. |
| `l2/scores/wpms_r1d.*`, `l2/scores/wpms_r1b.*` | The Phase 3 score, R1 in dispatch form (queued Jumps, entry chosen in housekeeping; g = 0) and in branch form (lanes; g = 1). |
| `l2/programs/wpms_housekeeping_dispatch.pfasm` | Housekeeping window of the dispatch form: BCP, then JumpVal = TAIL_BASE + 16·P. |
| `l2/wpms_l2_tb.v`, `l2/run_phase3.sh` | The sweep-level testbench (switch and L1 stand-in) and the Phase 3 recipe. |
| `tools/sweep_dump.py`, `tools/cosim_sweep.py`, `tools/cosim_sweep_mutants.py`, `tools/r2_probe.py` | The oracle's GO stimulus and bundles (sweep_sim.py run unchanged); the sweep-level cosimulation; its mutants; the R2 probe (Hook A). |
| `l1/wpms_l1_module.v` | One module's L1 (Phase 4): bundle latch, phase and shape difference engines (54-bit, MG added), sin core, exp2 unit, product Q1.63 toward zero, accumulators Q12.63 closed on the strobe, overrun flag, SWEEP_CLOCKS, inspector. D_L1 = 19. |
| `l1/wpms_l1_sin.v`, `l1/wpms_l1_exp2.v` | The Maclaurin core (Ch.2: 16 clocks, 7 multipliers; the published realization of SD-16) and the exp2 unit (Ch.3 §3.5.4: the oracle's table and polynomial, 6 clocks, one M10K). |
| `l1/wpms_l1_consts.vh`, `l1/wpms_exp2_table.hex/.mif` | Generated by `tools/gen_l1_tables.py` from the customer's oracle (table, C1, C2) and from `tools/l1_model.py` (sin constants). Do not edit. |
| `l1/wpms_output_stage.v` | MG slew (step_toward), G, round to nearest, saturate, sticky clip, soft mute to exact zero, silence on error; the output bank (Ch.4 §4.4). |
| `l1/wpms_i2s_master.v`, `l1/wpms_strobe_sync.v` | I2S master on MCLK 12.288 MHz, origin of the L3 strobe (F_m − 1 SCLK), bank capture at F_m; the toggle synchronizer and the strobe-interval counter (Ch.4 §4.3, §4.5, §4.6.1). |
| `l1/wpms_video_720p.v`, `l1/wpms_adv7513_cfg.v` | The video carrier (720p60, VIC 4) and the ADV7513 configurator (I2C, HPD poll, rewrite on hot-plug; table entries marked by basis) for the board top of Phase 6 (Ch.4 §4.2, §4.6.2, §4.7). |
| `l1/wpms_synth_top.v` | One WPMS module end to end: I2S master → strobe sync → `wpms_l2_top` → `wpms_l1_module` → output stage → I2S. |
| `l1/wpms_l1_units_tb.v`, `l1/wpms_l1_tb.v`, `l1/wpms_synth_tb.v`, `l1/wpms_video_tb.v`, `l1/wpms_adv7513_tb.v` | Benches: sin/exp2 streams; module bin by bin; the whole synthesizer (bench strobe under the oracle's traffic, or the real grid, with an I2S receiver); video timing; I2C slave model of the ADV7513. |
| `l1/run_phase4.sh` | Phase 4 recipe (RTL-SIM; resource ESTIMATE if `yowasp-yosys` is installed). |
| `tools/l1_model.py` | The bit-level model of the L1 and the output stage over the customer's oracle (golden parts imported unchanged; sin core, product, accumulators, output stage published here). |
| `tools/gen_l1_tables.py`, `tools/cosim_l1.py`, `tools/cosim_synth.py`, `tools/cosim_l1_mutants.py` | Table generator; unit / module / MG-fade cosimulation; system cosimulation (oracle traffic and grid cases); the L1 mutants. |
| `switch/wpms_switch.v` | The minimal input switch (Phase 5, customer Ch.5 §5.4–§5.8): the §5.6 map for one module, ports 0 and 3, stage-arm-go (freeze while armed, GO / GO_ALL / go-now, the check of PR-1, PR-2 and the sum of N), the atomic hand-over to the Formation, APPLIED_SEQ / APPLIED_SAMPLE, REJECT, the ROM player. |
| `switch/wpms_host_bridge.v`, `switch/wpms_issp.v` | The host path of the ruling of 2026-09-30: ISSP source bits {RD, WR, ADDR, WDATA} → one port-0 transaction per flipped toggle (synchronized, settled, acknowledged on the probe); the ISSP instance (Intel `altsource_probe`, or 0 in simulation). |
| `switch/wpms_rom.v`, `switch/wpms_rom_origin_{1008,2048}.{hex,mif}` | The built-in ROM (ISMCE instance TORG in Quartus) and its images, generated by `tools/gen_switch_rom.py` from Ch.3 §3.10 and Ch.5 §5.8 (do not edit). |
| `switch/wpms_key_pulse.v`, `switch/wpms_system.v` | KEY[1:0] debounced to pulses; the system: switch + bridge + ISSP instances HOST, STAT, INSP + `l1/wpms_synth_top.v`. **The OR**: the bridge sees `ISSP HOST | host_src_ext` (the testbench's deterministic controller; 0 on the board). |
| `switch/wpms_system_tb.v`, `switch/run_phase5.sh` | The system bench with the deterministic controller (the ISSP bit protocol, with skew), and the Phase 5 recipe. |
| `tools/switch_model.py`, `tools/cosim_switch.py`, `tools/cosim_switch_mutants.py`, `tools/gen_switch_rom.py` | The switch's semantics from Ch.5's text; the system cosimulation (origin, music, reject, timing, bridge, random); its mutants; the ROM generator. |
| `de10_nano/DE10_Nano_wpms_top.v`, `de10_nano/wpms_pll.v`, `de10_nano/DE10_Nano_wpms.sdc` | The board top (Phase 6): pins of the Terasic golden top, three PLLs, resets, the HDMI carrier and its control, I2S + MCLK, LEDs, ISSP BRD, the SignalTap taps; one parameter `SYS_MHZ`; the constraints of both revisions. |
| `de10_nano/make_quartus_project.py`, `de10_nano/run_phase6.sh`, `de10_nano/README.md` | The Quartus project (flat, git-ignored; `--check` without Quartus); the Phase 6 recipe; the bring-up procedure and the SignalTap captures C1–C5. |
| `de10_nano/inject/`, `tools/gen_inject_scores.py` | The EW2–EW5 injection images for the In-System Memory Content Editor (instance PTSG). |
| `de10_nano/sim/` | The board-level bench, the behavioural PLL, stand-ins of the Intel primitives (never given to Quartus). |
| `tools/cosim_board.py`, `tools/phase6_evidence.py`, `tools/phase6_templates.py`, `tools/resource_ledger.py` | The board-level cosimulation and the dry run of each SignalTap capture; the evidence reader (bench VCD or SignalTap export); the observation templates; the resource ledger from the Fitter report. |
| `tools/host/` | **Outside WPMS** — a stand-in for the Layer 4 controller: the quartus_stp Tcl for the ISSP instance HOST and the Phase 6 music demo (the same steps are checked in RTL-SIM), and `check_host_tcl.py`, which runs both scripts under tclsh against stand-ins of the Quartus ISSP commands. |

## Running / 実行

The scripts expect the workspace of the brief: four repositories side by side (`PTSG-Core`, `PTSG-CPU-Formation`, `PTSG-WPMS-Formation`, `FPGA_Spectrum_Engine_OpenPrompt`). Icarus Verilog ≥ 12 (`-g2012`) and Python 3.

```sh
03_Sample_Implementations/hw/tools/run_phase0_baseline.sh    # logs -> 04_Verification_Evidence/reports/logs/phase0
03_Sample_Implementations/hw/core/run_phase1.sh [EVIDENCE_DIR]   # build -> hw/core/build (git-ignored)
03_Sample_Implementations/hw/l2/run_phase2.sh [EVIDENCE_DIR]     # build -> hw/l2/build (git-ignored)
03_Sample_Implementations/hw/l2/run_phase3.sh [EVIDENCE_DIR]     # about 40 min; SAMPLES=<n> per seed (default 12000)
03_Sample_Implementations/hw/l1/run_phase4.sh [EVIDENCE_DIR]     # about 60 min with the Phase 3 regression (REGRESSION=0 skips it)
03_Sample_Implementations/hw/switch/run_phase5.sh [EVIDENCE_DIR] # the Phase 4 regression, then the switch (REGRESSION=0 skips it)
03_Sample_Implementations/hw/de10_nano/run_phase6.sh [EVIDENCE_DIR] # the Phase 5 regression, then the board (REGRESSION=0 skips it)
```

Each script prints its checks and ends with a one-line verdict; `run_phase1.sh` … `run_phase5.sh` exit non-zero if any expectation fails. Phase 4 needs numpy (the exhaustive sin check; the customer oracle's CH4-CREST). Phase 2's optional resource estimate needs `pip install yowasp-yosys`. Phase 5's check of the host scripts needs a tclsh (for example `apt install tcl8.6`); without one it is skipped. Phase 6's project check uses the same tclsh; the board itself needs Quartus Prime Lite 23.1std.1 (`de10_nano/README.md`). The SD-22 tools (`tools/equiv_formal.py`, `tools/gate_depth.py`) need `yowasp-yosys` (or `yosys`); `equiv_formal.py`'s step 2 also needs `python-sat` (`pip install python-sat`, for CaDiCaL). / 各スクリプトは検査を表示し、一行の判定で終わる。
