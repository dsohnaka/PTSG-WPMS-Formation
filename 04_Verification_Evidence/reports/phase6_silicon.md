# Phase 6 — DE10-nano and Layer 4 evidence / 実機と第 4 層の証拠 — part 1: before the board / その 1：実機の前まで

*CC0 · 2026-10-01 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 6, with the rulings of 2026-10-01. This part ends where the board begins: Quartus, the bitstream and the SignalTap captures are the architect's. It stops here for the architect's compile and captures.*

*Verdict: **prepared — every check that can run without the board is green.***

*What is built:*

- *the **board top** (`hw/de10_nano/`):*
  - *three PLLs: `clk_sys` 50 or 100 MHz, MCLK 12.288 MHz, the pixel clock at 0° and at 180°;*
  - *resets from power-on, PLL lock, SW[2] and JTAG;*
  - *the 720p60 video carrier and the ADV7513 configurator, I2S with MCLK;*
  - *eight LEDs, the ISSP instance BRD, and two tap registers for SignalTap;*
- *its **Quartus project**, generated with two revisions (50 MHz: the effective target; 100 MHz), and the **SDC**;*
- *the **injection images** for EW2–EW5 (ISMCE) and the **host scripts** for the captures (EW6, the full take-set, the first GO);*
- *an **evidence reader** that measures the eight items from a SignalTap export.*

*Where it was checked:*

- ***Board-level RTL-SIM** of the top with every capture of the bring-up recipe, at both clock budgets.*
  - *All eight evidence items are within the brief's bounds.*
  - *Every bundle and every bank is bit-exact with the models.*
  - *Each run was also cut as its SignalTap capture, written in the layout of a SignalTap export and read back by the same reader: the silicon path, dry-run.*
- *The **regression** of Phases 2–5.*
- ***Stand-in checks** of what only Quartus can really judge (plain tclsh, Icarus with stand-in primitives).*

*Evidence class: **RTL-SIM** (stand-in checks marked). No SILICON number exists yet: each one gets its own row, with its expected value written before the capture.*

*判定: **準備完了。実機なしで走らせられる検査はすべて緑。***

*作ったもの:*

- *ボードのトップ（PLL 3 基、リセット、映像キャリア、ADV7513 設定器、I2S と MCLK、LED、ISSP BRD、SignalTap 用タップ）。*
- *その Quartus プロジェクト（50 MHz と 100 MHz の 2 リビジョン）と SDC。*
- *EW2〜EW5 の注入イメージと、取得用のホストスクリプト。*
- *SignalTap のエクスポートから証拠 8 項目を測る読取りツール。*

*検査したこと:*

- *両予算での基板レベル RTL-SIM で、8 項目すべてが指示書の上限内に収まり、バンドルと出力はモデルとビット一致した。*
- *各実行を SignalTap の取得どおりに切り出し、エクスポート形式で書き出して同じツールで読み戻した（シリコン経路の予行演習）。*
- *Phase 2〜5 の回帰。*
- *Quartus でしか本当は判定できない部分の代役検査。*

*SILICON の数値はまだない。各数値には、取得の前に期待値を記した行を用意してある。*

---

## 0. Rulings applied (2026-10-01) / 適用した裁定

| Ruling | How Phase 6 applies it |
|---|---|
| (1) RH004 (SD-21) approved; Map v0.3's "armed" wording at the next version | Recorded (`discrepancies.md`, SD-21 closed). The board runs Formation RH004. |
| (2) SD-19: ISSP addressable transactions adopted; the customer may be told C5-D8 is overridden | Recorded; `reports/customer_note_sd19_host_path.md` prepared. The board's host path is exactly that. |
| (3) SD-20: the ROM is exempt from the ownership rules | Recorded (SD-20 closed). |
| (4) All fail-safe choices C-1 … C-15 approved | Recorded; nothing changes. |
| (5) Proceed to Phase 6 | This report. With the rulings of 2026-09-28/29, the 50 MHz revision (NMAX 1,008) is the effective target if 100 MHz does not close. |

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `hw/de10_nano/DE10_Nano_wpms_top.v` | **The board top.** Pins: the Terasic golden top's names, the locations of the Core's `.qsf`. **Clocks:** FPGA_CLK1_50 → PLL `clk_sys` (one parameter, `SYS_MHZ`: 50 → NMAX 1,008, the ROM's origin N = 1,008; 100 → 2,048); FPGA_CLK2_50 → fractional PLL MCLK 12.288 MHz; FPGA_CLK3_50 → fractional PLL 74.25 MHz at 0° (pixel) and 180° (forwarded as HDMI_TX_CLK, the ADV7513's sampling edge in the middle of each pixel). FPGA_CLK1_50 itself runs the configurator. **Resets:** power-on counter, PLL lock, SW[2], ISSP BRD source[0] — each a 2-FF level into its domain; video and configurator do not follow SW[2] (the link stays up while the sound restarts). **HDMI:** the 720p60 carrier (colour bars), the configurator (open-drain I2C, 2-FF inputs), I2S + MCLK. **LEDs** (README §2). **ISSP BRD:** 21 probes of the board's state, one source = the JTAG reset. **Taps:** `tap_ctl` (101 used bits: the strobe, packets, bins, take, error and code, halt, idle, bank write, K, the Core's state, q, SWEEP.a, strobes since reset, a storage-qualifier bit) and `tap_dat` (the bundle, the bank), registered, `noprune` |
| `hw/de10_nano/wpms_pll.v` | One Cyclone V PLL: `altera_pll` instantiated directly, as the Core's 100 MHz top does; `SIM` branch for the bench |
| `hw/de10_nano/DE10_Nano_wpms.sdc` | Started from the Core's SDC (base clocks, `derive_pll_clocks`, JTAG, human I/O). Added: the five clock domains as asynchronous groups, found by the PLL instance names inside the clock names (no full name `derive_pll_clocks` invents is written down); HDMI_TX_CLK as a clock generated on its pin from the 180° output; the pixel bus constrained against it from the ADV7513 data sheet (t_VSU 1.8 ns, t_VHLD 1.3 ns, + 0.2 ns board); I2C, I2S, KEY, SW, LED, TX_INT cut with the reason written next to each. **The imem half-cycle path is not relaxed** (the brief) |
| `hw/de10_nano/make_quartus_project.py` | Writes the project (flat directory, git-ignored, as the Core keeps its files side by side): 22 Verilog files, 2 includes, the memory images, the SDC, `DE10_Nano_wpms.qpf` with revisions `DE10_Nano_wpms` (50 MHz) and `DE10_Nano_wpms100` (100 MHz), which differ in `set_parameter -name SYS_MHZ` only; the injection images and the host scripts beside them; `MANIFEST.txt` (source, SHA-256, commit). `--check`: §3.4 |
| `hw/de10_nano/README.md` | Build, first light, LEDs, the ISSP instances, the SignalTap set-up (one instance), the captures C1–C5 of the eight items, the analysis, the ledger |
| `hw/de10_nano/run_phase6.sh` | The Phase 6 recipe |
| `hw/de10_nano/inject/` | EW2, EW3, EW4, EW5 (NMAX 1,008 and 2,048) as whole score images: `wpms_r1d.score` with its packet window replaced, the window source, `.hex` and `.mif` (ISMCE instance PTSG). Generated by `hw/tools/gen_inject_scores.py` |
| `hw/de10_nano/sim/` | The board-level bench `DE10_Nano_wpms_tb.v` (three oscillators, KEY/SW, an ADV7513 I2C model, an I2S receiver, the video timing check, the host through the ISSP bit protocol, LED tracking); the behavioural PLL; stand-ins of the Intel primitives (`vendor_stubs.v`, for the elaboration check). Never given to Quartus |
| `hw/switch/wpms_system.v` **RH002** | Three tap ports (error code, the Core's state, sequencer idle) for the board's tap bus. Behaviour unchanged |
| `hw/tools/cosim_board.py` | The board-level cosimulation: cases origin, first_go, full8, ew6, ew2–ew5, pcm, at both budgets; the brief's bounds (`EXPECT`, written before any run) checked; each run cut as its SignalTap capture and read back (§3.2) |
| `hw/tools/phase6_evidence.py` | The evidence reader. It takes a bench VCD or a SignalTap export (bits one by one, with or without the clock signal, X at time 0), continuous or storage-qualified. It measures g, T_wake, the window, BCP (the full take-set's included), sweep length, errors (code, packets/bins after, non-zero banks after, halt), and every bundle and bank against the model (the host log replayed through `switch_model.py`, `sweep_sim.Reference` unchanged, `l1_model.py` over the customer's oracle). A capture taken long after reset starts the model from the last complete GO before it (every slot of every block it plays, and the sweep word). It also gives the spectrum of the captured PCM beside the model's |
| `hw/tools/phase6_templates.py` | The observation templates of the captures, from the RTL-SIM values (§3.6) |
| `hw/tools/resource_ledger.py` | The resource ledger from the Fitter's *Resource Utilization by Entity*: the Core's row in the Core's format, and ALMs, ALUTs, registers, M10K, DSP for every WPMS entity (`--selftest`) |
| `hw/tools/gen_inject_scores.py` | The injection images (`--check`) |
| `hw/tools/host/wpms_phase6_steps.py`, `wpms_phase6_{first_go,full8,ew6}_{1008,2048}.tcl` | **Outside WPMS.** The host's part of captures C2, C3, C4, written once and played two ways: Tcl for `quartus_stp` on the board, and commands for the board-level bench |
| `hw/tools/host/check_host_tcl.py` **RH002** | Adds the six Phase 6 scripts to the tclsh check (§3.5) |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

```
# the recorded Phase 6 run (Icarus Verilog 12.0, Python 3.11.15, tclsh 8.6.14, Yosys 0.69), 2026-10-01T14:45:10Z
REGRESSION=0 03_Sample_Implementations/hw/de10_nano/run_phase6.sh 04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board
  [PASS] injection images wpms_r1d_ew{2,3,4,5_1008,5_2048}.{score,pfasm,hex,mif} regenerate identically
    phase6  PASS: 6 scripts: 370 writes and 38 reads, each script's in the order of its wpms_phase6_steps.py steps; one GO each, applied
  check_host_tcl: PASS
    mutants 7/7 broken copies of the project caught
  make_quartus_project --check: PASS (stand-ins, not Quartus)
  iverilog -Wall: 16 lines, 0 from hw/de10_nano
  cosim_board: PASS (18 runs, 0 failed checks, 275 s)
  [PASS] resource_ledger.py reads the Fitter's 'Resource Utilization by Entity' table (self-test)
  ESTIMATE DE10_Nano_wpms_top: $lut 10245; MISTRAL_ALUT_ARITH 4019; MISTRAL_FF 6479; MISTRAL_M10K 2; MISTRAL_MLAB 1538; ...
  [PASS] observation templates of captures C1-C5 written from the expected values (before any capture)
run_phase6: ALL PHASE 6 CHECKS PASSED (RTL-SIM; the board is next)

# the same recipe with its regression, on the same RTL, started 2026-10-01T13:43:18Z
# (before the project mutants, the estimate and the templates were added: its board part gave the same
#  18 verdicts, cosim_board 18 runs, 0 failed checks)
03_Sample_Implementations/hw/de10_nano/run_phase6.sh     (REGRESSION=1: Phase 5's recipe, which runs Phase 4's, 3's, 2's)
  run_phase5: ALL PHASE 5 CHECKS PASSED
  run_phase4: ALL PHASE 4 CHECKS PASSED
  run_phase3: ALL PHASE 3 CHECKS PASSED
  run_phase2: ALL PHASE 2 CHECKS PASSED
  [PASS] regression: Phases 2-5 on wpms_system RH002
run_phase6: ALL PHASE 6 CHECKS PASSED (RTL-SIM; the board is next)
```

Logs: `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/logs/`:
- `run_phase6.txt`, `cosim_board.txt` (all 18 runs in full), `check_host_tcl.txt`, `make_quartus_project.log`, `compile6.log`, `gen_inject_scores.log`, `resource_ledger_selftest.log`, `yosys_stat.txt`, `phase6_templates.log`;
- the regression's `phase{2,3,4,5}_regression.txt`.

Expected values per case and budget, and the expected SignalTap captures: `expected/`.

ログは `rtl_sim/2026-10-01_phase6_board/logs/`、期待値と期待キャプチャは `expected/` にある。

## 3. Results, with evidence classes / 結果と証拠クラス

All numbers are **RTL-SIM** unless marked: the board top, with its PLLs and ISSP instances in their simulation branches, on the board-level bench.
- 18 runs: nine cases at the 50 MHz budget (NMAX 1,008, T_min 1,041) and the same nine at 100 MHz (NMAX 2,048, T_min 2,083).
- Host steps through the ISSP bit protocol.
- The tap bus dumped as SignalTap holds it.

### 3.1 The eight evidence items / 証拠 8 項目

Each bound was written in `cosim_board.py` (`EXPECT`) before any run; the values are the runs'.

| # | Evidence item (brief) | Bound | 50 MHz (NMAX 1,008) | 100 MHz (NMAX 2,048) | Capture | SILICON |
|---|---|---|---|---|---|---|
| 1 | g between consecutive packet Stays | 0 | **0** in every sweep with more than one packet (full8: 8 packets, 47 sweeps; first_go: 3) | **0** (45 and 44 sweeps) | C2 | pending |
| 2 | T_wake: strobe → first packet_start | ≤ 4 (nominal 2) | **2** in every sweep of every run | **2** | C1, C2 | pending |
| 3 | packet window → N_MIN | 25 + Core clocks; 32 must hold | window **28** (Stay Set → the Stay word) → floor **30** ≤ 32 | **28 → 30** | C1, C2 | pending |
| 4 | BCP, full take-set | ≤ 10 | **10** with eight blocks, the full mask and the sweep word — at the bound; 2–3 without a take, up to 5 for the triad's | **10** | C2 | pending |
| 5 | full-load sweep fits with the housekeeping window | ≤ T_min | strobe → asleep **1,023** of 1,041 (47 sweeps of full8, 62 of the origin) | **2,063** of 2,083 (the brief's oracle estimate: 19 spare; here 20) | C1, C2 | pending |
| 6 | each EW2–EW6 injected | the right code; L1 silent | EW2, EW3, EW4, EW5, EW6: **each its code, exactly once**; after the flag **0 packets, 0 bins**, the following 59–62 banks **all zero**; the Core halts (9 clocks after EW2, 11 after EW5; at the end of the packet's Stay, 1,000–1,005 clocks, after EW3, EW4, EW6) | the same codes; 0, 0, all zero; halts after 9 / 11 / 2,040–2,045 clocks | C4, C5 | pending |
| 7 | bundle at packet_start vs prediction | equal | **534 / 534** equal (every bundle of every run) | **531 / 531** | C1–C3 | pending |
| 8 | first sound: test origin, then one GO | audible; the oracle's spectrum | banks **1,320 / 1,320** equal (the I2S wire = the bank, 1,629 frames); after the GO, 1,147 samples: left 524.4 + 659.2 Hz, right 660.6 + 782.2 Hz — C5, E5, G5 as routed, the model's spectrum identical | **1,316 / 1,316** (1,625 frames); 1,146 samples, the same peaks | C3 (and by ear) | pending |

**Item 6's injections.**
- EW6 is the host's: LE0 = −1 into the playing block. The switch has no check on LE0, so the next packet window's STP raises it.
- EW2–EW5 are score images for the In-System Memory Content Editor (`hw/de10_nano/inject/`), each loaded and followed by a reset. The switch refuses what would raise EW2 and EW5 from the inbox (PR-1, PR-2), so their windows make the condition themselves:
  - **EW2**: the window writes N = 16 into its own block (CUR slot 0); the prefetch after housekeeping finds N < N_MIN.
  - **EW3**: the window stores into the inbox view.
  - **EW4**: the window writes the store directly.
  - **EW5**: the window writes N = NMAX + 1. Housekeeping's BCP re-checks the sum of N of the sweep in effect **every sweep**, not only with a take. That was open in the Phase 5 notes; it is now shown.

**Item 7 needs the host's log.** The reader replays the log through `switch_model.py` (the ROM's list after the reset, each write, each GO at the sample the switch reported). It then plays the takes with `sweep_sim.Reference` (golden, unchanged) and `l1_model.py` over the customer's oracle.

**On the board the GO lands seconds after reset**, so the model must not start at reset. A capture far from reset starts the model from the last complete take before it: a GO that sets every slot of every block it plays, and the sweep word. All three host captures' GOs are complete. `cosim_board.py` checks this on the first_go and full8 runs at both budgets: it cuts each run from the first sweep that plays the GO, and starts the model from the GO alone. Results: first_go 121/121 bundles and 41/41 banks, full8 321/321 and 41/41, at each budget — all equal (the model starting from strobe 5 or 7 at 50 MHz, 4 or 5 at 100 MHz).

**Board-level checks (every run):**
- The ADV7513 table: 29 writes, done, no NACK.
- The video carrier: every line 1,650 pixels with 1,280 of active video; HDMI_TX_CLK 6.0–7.5 ns after each pixel edge. Frame timing was checked by Phase 4's video bench; these runs are shorter than a frame.
- I2S: every frame decoded equal to the bank captured.
- Strobe intervals 1,041/1,042 (2,083/2,084).
- No overrun; LEDs as `README` §2; simulator warnings 0.

**Other readings.**
- SWEEP_CLOCKS_MAX, the L1's own count read by the host at 0x299 (strobe → the last product accumulated, D_L1 after the last bin): 1,028 and 2,068 — also within T_min.
- PCM peaks: origin −12.44 dBFS (N = 1,008) and −6.29 dBFS (N = 2,048), as in Phases 4 and 5; the triad, after its GO, −26.4 dBFS at both budgets (N = 240 per note).

### 3.2 The silicon path, dry-run / シリコン経路の予行演習

Each run was also cut as its SignalTap capture in the recipe (`hw/de10_nano/README.md` §4, `cosim_board.py` `TRIGGERS`): depth 4,096, "pre trigger position" (12 %), the case's trigger, the storage qualifier where the recipe enables it. The cut was then:
1. written in the layout of a SignalTap export (QUARTUS_VCD_EXPORT 1.0: 1 ps, one variable per bit, X at time 0, the acquisition clock as a signal; the qualified capture without it);
2. read back by `phase6_evidence.py`;
3. measured and compared with the model like the board's export will be.

All 16 cuts read back unchanged and agree with the full runs. In them:
- C1 shows a full-load sweep (1,023 / 2,063) and T_wake 2.
- C2 shows the full take-set's BCP (10) from its pre-trigger samples, and g = 0.
- C3 (storage-qualified: 175 / 173 events) has 128/128 and 127/127 bundles and 47/47 and 46/46 banks equal.
- C4/C5 show each code with silence after it.

These cuts are the **expected captures** (`rtl_sim/2026-10-01_phase6_board/expected/expected_<case>_<budget>.vcd.gz`). The board's exports can be opened beside them.

### 3.3 Regression / 回帰

Phases 2–5 rerun on this tree (wpms_system RH002), 2026-10-01T13:43:18Z: **ALL PHASE 2, 3, 4 and 5 CHECKS PASSED** (§2; `logs/phase{2,3,4,5}_regression.txt`). Phase 5's check of the host scripts now includes the six Phase 6 scripts.

### 3.4 What only Quartus can judge, checked with stand-ins / Quartus でしか判定できないもの（代役で検査）

`make_quartus_project.py --check` (**stand-in**, not Quartus):
- **Under a plain tclsh against stand-ins of the Quartus commands:**
  - both `.qsf` files: 52 pins equal to the Terasic golden top's (the Core's `.qsf`), each with an I/O standard, none twice; every file named present; `SYS_MHZ` set;
  - the `.sdc`, under the clock names `derive_pll_clocks` gives an `altera_pll` on Cyclone V (VCO phase clock and output counters): twelve clocks in five asynchronous groups, each clock in exactly one; `hdmi_tx_clk` generated from the 180° counter; the pixel bus at −max 2.0 / −min −1.5 ns.
- `--mutants`: seven broken copies of the project (a pin moved, the pixel PLL not found, a source missing, the forwarded clock taken from the 0° output, the hold sign, the audio group lost, an I/O standard missing) — each caught.
- **Elaboration:** Icarus elaborated the project's own Verilog files, the INTEL branches taken, with stand-in primitives that print what they receive. At both revisions each of the nine primitives received the expected parameters:
  - the PLLs: `clk_sys` "50.0000000 MHz" (equal-length strings: no NUL padding) or "100.000000 MHz"; 12.288 MHz fractional; 74.25 MHz at 0 and 6,734 ps, fractional;
  - the ROM's image `wpms_rom_origin_1008.mif` or `_2048.mif` (ISMCE TORG), the score `wpms_r1d.mif` (ISMCE PTSG);
  - the ISSP instances HOST, STAT, INSP and BRD.
- **Not judged here:** whether Quartus accepts the PLL strings, the placement of three fractional PLLs on these clock pins, and timing. The imem half-cycle path at 100 MHz is the expected critical path.

### 3.5 Host scripts / ホストスクリプト

`check_host_tcl.py` (tclsh 8.6.14 against the ISSP stand-ins; **stand-in**, not Quartus):
- the Phase 5 cases still pass;
- the six Phase 6 scripts make exactly the transactions of their steps — 370 writes and 38 reads in all — and each one GO is applied;
- the files on disk are what `wpms_phase6_steps.py` writes;
- 8/8 broken copies of `wpms_issp_host.tcl` are caught (H4, H7 and H8 also by the Phase 6 scripts).

The same steps run in the board-level RTL-SIM (§3.1).

### 3.6 Expected before observed / 取得前の期待値

`hw/tools/phase6_templates.py` writes `04_Verification_Evidence/signaltap/phase6_pending/<capture>/observation.md` for C1_origin, C2_full8, C3_first_go, C4_ew6 and C5_ew2–ew5. Each holds:
- the capture's set-up and action;
- the brief's bound and the RTL-SIM value at both budgets, per quantity;
- an empty Observed column.

When a capture is made, the folder is renamed `signaltap/<date>_phase6_<capture>/` and filled.

## 4. Deviations and findings / 逸脱と発見

**4.1 No deviation from the golden models.**
- Every bundle and bank the board top produced equals the models.
- Nothing in `../tools/`, the oracle, the frozen Core or Layer 1 was touched.

**4.2 Findings.**
1. **BCP with the full take-set takes exactly the bound, 10 clocks.** The BCP word → inbox_taken spans the background copy of eight blocks, one block per clock. The brief's ≤ 10 holds with no margin; a ninth block would not fit, but M = 1 has eight.
2. **The Core's halt after an in-window error waits for the packet's Stay to end** (C3-F24's trap is inserted at the next instruction boundary): 1,000–1,005 clocks at 50 MHz, about N. L1 is silent from the flag on in every case — 0 packets, 0 bins, every bank zero — which is what the item asks. Errors raised in housekeeping or the prefetch (EW5, EW2) halt within 9–11 clocks.
3. **74.25 MHz needs a fractional VCO.** From 50 MHz, an integer M/N/C needs M = 297, N = 10 (the phase detector at 5 MHz, its minimum) and a 1,485 MHz VCO, at the edge of the device's ranges. The pixel PLL is fractional (742.5 MHz, C = 10). The 180° shift is 40 VCO eighths, exactly 6,734 ps.
4. **Two definitions of "the sweep's length".** The tap's strobe → asleep (1,023 / 2,063) is the brief's "with the housekeeping window". The L1's SWEEP_CLOCKS (1,028 / 2,068) counts to the last product accumulated. Both fit in T_min. The brief's oracle estimate is 19 spare at 100 MHz; here 20 (strobe → asleep) or 15 (the L1's view).
5. **The Core copy uses `tri0` ports**, which Yosys does not read. For the ESTIMATE only (§7), the copy was read with `tri0` → `wire`: both ports are driven in `wpms_l2_top`, so nothing differs. The Core copy itself is unchanged.

## 5. Discrepancies filed / 記録した食い違い

None new in this part; SD-01 … SD-21 stand as ruled. The board run may add some: each goes in as its own row, with no fix applied.

本パートで新たな食い違いはない。SD-01〜SD-21 は裁定どおり。実機で見つかれば、修正せず 1 行ずつ追加する。

**Added 2026-10-03:** **SD-22**, clk_sys does not close at 50 MHz (§9). It is open, for the architect's ruling; no fix is applied until then.

**2026-10-03 追加:** **SD-22**（clk_sys が 50 MHz で収束しない、§9）。アーキテクトの裁定待ちで、それまで修正はしない。

## 6. Questions for the architect / アーキテクトへの質問

1. **Compile.**
   - Please compile both revisions (`DE10_Nano_wpms` first) and send the TimeQuest summary.
   - Please include the SDC's info line that lists the clocks found. A critical warning about the forwarded pixel clock is also worth sending.
   - At 100 MHz the imem half-cycle path decides; if it fails, the 50 MHz revision is the target (rulings 2026-09-28/29).
2. **SignalTap.** One instance (4 K deep, about 203 M10K), set up in the GUI from README §3; I did not write an `.stp` by hand. Shall your `wpms_tap.stp` be committed once it exists, as the Core's harness keeps its own?
3. **Captures.**
   - The plan is C1–C5 at the 50 MHz revision, and at 100 MHz if it closes.
   - First sound needs an HDMI sink with speakers.
   - Please put each export, with its host log, in `signaltap/<date>_phase6_<capture>/`; I will fill the observations from them.
4. **The resource ledger** comes from your Fitter report (`resource_ledger.py`, README §5). The ESTIMATE below is only for context.

1. 両リビジョン（まず `DE10_Nano_wpms`）をコンパイルし、TimeQuest の要約と SDC の情報行（見つかったクロック）をお送りください。100 MHz では imem 半周期パスが決め手で、通らなければ 50 MHz 版が目標です。
2. SignalTap は README §3 の 1 インスタンス（深さ 4 K、M10K 約 203）を GUI で作る想定で、`.stp` は手書きしていません。作成後に `wpms_tap.stp` をコミットしてよいでしょうか。
3. 取得はまず 50 MHz 版で C1〜C5、通れば 100 MHz 版でも行います。初音にはスピーカー付き HDMI 機器が要ります。エクスポートとホストのログを `signaltap/<日付>_phase6_<取得名>/` に置いていただければ、観測値を記入します。
4. 資源台帳は Fitter 報告から作ります（README §5）。下の概算は参考です。

## 7. Resource numbers / 資源数

**ESTIMATE** (Yosys 0.69 `synth_intel_alm -family cyclonev` + `abc -lut 6`; not Quartus): the whole board top at 50 MHz, flattened, with the Intel primitives as black boxes.

| | Count |
|---|---|
| LUTs (`$lut`) | 10,245 |
| arithmetic ALUTs | 4,019 |
| flip-flops | 6,479 (the taps' 432 included) |
| MLAB cells (32 × 1 LUT-RAM) | 1,538 |
| DSP: MUL27X27 / MUL18X18 | 16 / 6 |
| M10K (inferred) | 2 |
| black boxes | 3 PLLs; 2 altsyncram — the score memory (1,024 × 32: 4 M10K) and the ROM (256 × 44: 2 M10K); 2 ISSP (STAT and INSP, whose sources are unused, were dropped by Yosys; Quartus keeps all four) |

For scale: the 5CSEBA6 has about 41,500 ALMs, 112 DSP blocks and some 500 M10K (the Fitter's summary states the exact totals). The SILICON ledger replaces this table once the Fitter has run.

**概算**（Yosys、Quartus ではない）：ボード全体で LUT 10,245、算術 ALUT 4,019、FF 6,479、MLAB 1,538、DSP 22、M10K 2（ブラックボックスの M10K 6 を除く）。Fitter の結果が出れば SILICON の台帳に置き換える。

## 8. After the first Quartus compile (2026-10-03) / 初回 Quartus コンパイル後

The architect's first compile (Quartus Prime Lite 23.1std.1, revision `DE10_Nano_wpms`) stopped in Analysis & Synthesis with 3 errors:
- 10028 "Can't resolve multiple constant drivers for net `nack`" at `wpms_adv7513_cfg.v`(186);
- 10029 "Constant driver" at (149);
- 12152 "Can't elaborate user hierarchy `wpms_adv7513_cfg:u_cfg`".

**Cause.** In the configurator (Phase 4), the sticky `nack` was cleared at reset by the top FSM's always block and set by the transaction engine's. Icarus accepts two procedural drivers of a `reg`; Quartus does not. No other register of the design has two drivers (a scan of every always block of the RTL given to Quartus).

**Fix: `wpms_adv7513_cfg.v` RH003.** The engine raises a one-clock `nack_ev`; the top FSM alone owns `nack` and sets it one clock later. Checked:
- Phase 4's ADV7513 bench: PASS (29 writes, then 58 after the hot-plug, nack 0);
- a bench with no I2C slave: `nack` rises at the first unacknowledged byte, stays, and clears on reset;
- the board-level bench, origin at both budgets: PASS (table done, NACK 0);
- `make_quartus_project.py --check --mutants`: PASS.

The other messages in the screenshot are warnings, not errors:
- 10230 at `wpms_exp2_table.hex`: each value is written with 8 hex digits for a 31-bit word. Every value is below 2^31, so nothing is lost.
- 10030 "rom.data_a/waddr_a/we_a … no driver": the exp2 table inferred as a ROM.
- 10036 "`cur` assigned a value but never read".

初回コンパイルの 3 エラーは、ADV7513 設定器（Phase 4）の `nack` を 2 つの always ブロックが駆動していたことによる（Icarus は許すが Quartus は許さない）。RH003 で駆動元を 1 つにし、単体試験・スレーブ不在試験・基板ベンチ・プロジェクト検査で確認した。ほかに二重駆動のレジスタはない。残りの表示は警告で、exp2 表の値はすべて 31 ビットに収まる。

## 9. The first fit (2026-10-03): resources and timing / 初回フィット：資源とタイミング

After RH003 the compile went through:
- Quartus Prime Lite 23.1std.1, revision `DE10_Nano_wpms` (50 MHz), about ten minutes;
- Analysis & Synthesis, the Fitter and TimeQuest all completed;
- the three PLLs (two of them fractional) were accepted and placed.

The architect's two reports are kept with the ledger and an observation in `quartus/2026-10-03_DE10_Nano_wpms_fit1/`. They are *Multicorner Timing Analysis Summary* and *Resource Utilization by Entity*.

### 9.1 Resource ledger (SILICON, the Fitter) / 資源台帳

The Core's format (`resource_ledger.py`):

| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs |
|---|---|---|---|---|
| 2026-10-03 | DE10_Nano_wpms (50 MHz): Core RH031p, Formation RH004, cfg RH003 | 457.7 | 414.3 | 773 (725) |

The WPMS entities (total, entity-only in parentheses where it differs; the full table is in `ledger.md`):

| Entity | ALMs | Registers | M10K | DSP |
|---|---|---|---|---|
| board top (all) | 11,052.8 | 15,318 | 22 | 23 |
| Formation | 6,788.7 | 9,716 | 9 | 3 |
| input switch | 1,692.2 (1,644.2) | 1,493 | 4 (its ROM 3) | 0 |
| L1 module | 831.7 (582.4) | 1,552 | 5 | 20 |
| PTSG-Core RH031p | 457.7 (414.3) | 303 | 4 (imem) | 0 |
| output stage | 336.7 | 283 | 0 | 0 |
| sequencer | 181.3 | 364 | 0 | 0 |
| ADV7513 configurator | 140.5 | 145 | 0 | 0 |
| ISSP ×4, host bridge, JTAG hub | 385.9 | 738 | 0 | 0 |

**Readings.**
- **The whole design is about a quarter of the device's ALMs**, a fifth of its DSP blocks and a few percent of its M10K. SignalTap is not in yet: its 4 K-deep instance (about 203 M10K, §6) fits beside it.
- **The Formation is 61 % of the design.** Its store, inbox and their forwarding muxes are registers. The datapath reads the store asynchronously, in the X clock, and an M10K cannot do that.
- **The nine M10K under the Formation are the prefetch's copies** of the nine banks it reads: N, LP, LAD1, LAD2, PH0, PHD1, PHD2, RT and LS0. Their read address, `pf_block`, is a register, and Quartus absorbed it. The datapath's own port stays in registers.
- **Against the ESTIMATE (§7):**
  - Yosys's 10,245 LUTs + 4,019 arithmetic ALUTs = 14,264, against the Fitter's 14,312 combinational ALUTs;
  - DSP 22 against 23;
  - Yosys had put memories in MLABs, where Quartus used registers and M10K.

### 9.2 Timing (STA, slow corner 1100 mV 85 °C) / タイミング

| Clock | Setup slack (ns) | Hold slack (ns) |
|---|---|---|
| **clk_sys** (`u_pll_sys` output counter, 50 MHz) | **−14.307** (TNS −65,525.293) | +0.033 |
| FPGA_CLK1_50 | +12.962 | +0.167 |
| hdmi_tx_clk (the forwarded pixel clock) | +2.975 | +2.968 |
| pixel (`u_pll_pix` counter 0) | +6.516 | +0.195 |
| MCLK (`u_pll_aud`) | +74.428 | +0.298 |
| altera_reserved_tck | +3.395 | +0.167 |

Recovery +35.228 and removal +0.423 (tck only); minimum pulse width met everywhere.
- **What meets:** the SDC's work.
  - hdmi_tx_clk exists, so the 180° counter was found.
  - The HDMI pixel bus meets t_VSU / t_VHLD with about 3 ns each way.
  - MCLK and the pixel clock are far from their limits.
- **What fails:** clk_sys alone, by 14.3 ns in a 20 ns period. The worst path is about 34 ns.

### 9.3 Why clk_sys fails / clk_sys が満たさない理由

By reading the RTL, with the gate depth of each module: Yosys 0.69, `synth -flatten -noabc; ltp -noff`, gates before LUT mapping, a multiplier as one cell. The details are in `discrepancies.md`, SD-22.

- **The Formation's X clock is one long chain (depth 146).**
  - It runs: address decode → forwarded store read → 32 × 32 MUL/MAC → shift by SHV → add → overflow → error priority → the one `x_commit`.
  - From there it fans out to the store's write enables (≈ 4,100 flip-flops), the background copy and its pending masks, and on to `inbox_taken`.
  - The Phase 2 clock table puts all of it in one clock, and the 2026-09-28 ruling deferred pipelining.
- **The tail from the multiplier into the store, the copy and the masks is structural only.** STM, STA @PPM and BCP are the only instructions that reach those registers, and none of their errors depends on the multiplier. A single `x_commit` serves every instruction, so the netlist makes them wait anyway.
- **What is long for real:**
  - MUL @PPM into Accm;
  - BCP's EW5, whose sum of eight N is written as a chain;
  - the switch's GO check (depth 99), also a chained sum of N.
- **Everything else is short:** L1 42, output stage 52, sequencer 12.

### 9.4 What was expected / 事前の見込み

- **Written before the compile:**
  - README §1 and §3.4: "at 100 MHz the expected critical path is the imem half-cycle path";
  - Phase 2 §6 Q4: three Formation paths are long for one clock "at 100 MHz".
- **Neither said that 50 MHz might fail. It does, by 14 ns.** The Phase 2 reading named the right paths, but did not see that they exceed even 20 ns. Phase 6's README then carried the wrong one (the imem) forward.
- The observation of this fit records that as a miss.

### 9.5 Proposed disposition and what I need / 提案と必要なもの

SD-22's two steps, each followed by Phases 2–6 and a new fit:
1. **Behaviour unchanged** (no clock added; the recorded runs must repeat cycle for cycle):
   - per-register enables;
   - the address decode registered with ADRS;
   - adder trees for the sums of N (Formation RH005, switch RH002).
2. **Only if 1 does not close:** a write-back clock for Accm, Temp and the store, E8 checked there, with forwarding. BCP and the copy keep their clocks. It is a pipeline, so the 2026-09-28 ruling must be lifted.

What I need from the architect:
- **(a) The failing-path report.**
  - Copy `hw/de10_nano/report_setup_paths.tcl` into `build/quartus/`. Rerunning `make_quartus_project.py` also copies it and leaves the compiled database alone.
  - Run `quartus_sta -t report_setup_paths.tcl` there. It also works from the Timing Analyzer's Tcl console with the project open: `source report_setup_paths.tcl`.
  - Send `output_files/setup_clk_sys_groups.txt` first (small). `setup_clk_sys_keys.rpt` and `setup_clk_sys_worst10.rpt` show the cells.
- **(b) A ruling.** Step 1 now? And step 2, if needed, without a new round?

The 100 MHz revision need not be compiled: it is not expected to close even after step 2 (SD-22).

**和文.**
- **コンパイル。** RH003 の後、コンパイルは約 10 分で最後まで通った。PLL 3 基（うち 2 基は分数モード）も受理・配置された。
- **資源（SILICON）。**
  - 全体で 11,053 ALM（デバイスの約 4 分の 1）、DSP 23、M10K 22。
  - Formation が 6,789 ALM で全体の 61 %。データパスのストア読出しが非同期のため、ストアとインボックスはレジスタで実装される。
  - Core（RH031p）は 457.7（本体 414.3）ALM。
- **タイミング。** clk_sys だけが −14.3 ns で満たさない。HDMI 画素バス、MCLK、画素クロック、JTAG は満たす。
- **原因。**
  - Formation の X クロックが、アドレス解読から乗算・桁あふれ・コミットを経て、ストア書込み許可と背景コピーまでの一本の長い連鎖になっている。
  - そのうち乗算器からストア側への部分は構造上だけのもの。
  - 実在する長経路は MUL @PPM、BCP の EW5、スイッチの GO 検査。
- **事前の見込み。** 50 MHz が通らないとは予想しておらず、見込み違いとして記録する。
- **提案。**
  - まず動作不変の再構成。足りなければ書戻しクロック（パイプライン化。2026-09-28 の裁定の解除が必要）。
  - 失敗経路の集計（`report_setup_paths.tcl`）の実行と、提案への裁定をお願いしたい。

## 10. SD-22 step 1 (2026-10-03): the long paths restructured, behaviour unchanged / 段階 1：動作不変の再構成

**Ruling 2026-10-03 (architect):** step 1 now. If step 1 does not close timing, step 2 follows without a new round of questions.

### 10.1 What changed / 変更点

**Formation RH005** (`hw/l2/wpms_formation.v`). No clock is added to anything.
- **(a) Each register's enable comes from the errors its own instructions can raise.** RH004 derived every enable from one commit, `x_go && x_err == 0`, computed for every instruction.
  - The store's write enable now comes from STM's and STA @PPM's errors: E4, E5, EW3, EW4.
  - BCP's effects (the pending masks, `inbox_taken`, copied, SWEEP.a) come from E4, EW4 and EW5.
  - ADRS (SAD, LDM, STM) and Accm, Temp, SHV, LoopVal and JumpVal each use their own op's conditions.
  - The error path (`error_flag`, code, SN, the trap) keeps the full priority.
  - In simulation, a check compares in every clock the enable each op uses with RH004's commit.
- **(b) The address decode is registered.** `region` and `a_block` are registers, loaded at the edge that loads ADRS (from `adrs_nx`) and x_cur (from `seq_cur`). The X clock starts from them, not from ADRS.
- **(c) EW5's sum of N is a balanced tree,** three adder levels instead of eight. Its repeat check is pairwise instead of a running mask.

**Switch RH002** (`hw/switch/wpms_switch.v`): the GO check's sum of N is a tree, and PR-1's repeat check is pairwise.

**Tests that followed the text** (same intent):
- `wpms_formation_tb.v` RH002: the backdoor that sets ADRS also sets its registered decode.
- `cosim_mutants.py` RH002:
  - M3, M6, M11 and M20 are the same defects in the new text;
  - M21–M23 are new: the registered region missing ADRS's post-increment, BCP's enable ignoring EW5, and MUL's Accm enable ignoring E8.
- `cosim_switch_mutants.py` RH002: W5 follows the pairwise PR-1.

**New tools:**
- `equiv_lockstep.py` — the previous revision beside the current one, compared in every clock (RTL-SIM);
- `equiv_formal.py` — the restructured logic proved equal (SAT, Yosys);
- `gate_depth.py` — the gate levels in front of each register group (ESTIMATE).

### 10.2 Nothing changed: the evidence / 動作が変わらないことの証拠

| Check | Class | Result |
|---|---|---|
| **Lockstep.** Formation RH005 beside RH004, and switch RH002 beside RH001, both taken from commit e3d4985. NMAX 1,008 and 2,048, seeds 1 and 2, 400,000 clocks per run. Compared in every clock: every output, every register (the Formation's 128 store words, 104 inbox words, the masks; the switch's whole state) and the restructured signals | RTL-SIM | **0 differences in 8 runs** (3.2 M clocks). Each Formation run executed about 318,000 instructions — all 16 ops, every error code (E4, E5, E8, EW2–EW6, about 230 EW5) — with about 1,500 BCPs that copy and 2,000 copy clocks. Each switch run made about 8,700 GOs and 1,870 go-nows, refused for every cause (P > 8, a block twice, N out of range, sum > NMAX) |
| **Formal.** The switch's GO check (`go_bad`, `go_sum`) at both NMAX; the Formation's EW5 sum (tree against chain) and repeat check; the Formation's split enables equal to RH004's commit for every state and input (the overflow flags and EW5 cut free) | formal (SAT) | **5/5 proved** (`logs/equiv_formal.txt`) |
| **Phase 2.** `cosim_l2` against the golden model | RTL-SIM | **3,914/3,914** bit-identical; the summary equals the recorded one, traced clocks included (durations aside). Mutants **23/23**; M1–M20 caught at exactly the recorded counts |
| **Phases 3–6.** The recipes rerun (`run_phase6.sh`, REGRESSION=1) and compared with the 2026-10-01 record (`compare_regression.py`) | RTL-SIM | **ALL CHECKS PASSED.** Phase 3's log and the 18 board runs (`cosim_board.txt`) are identical to the record. All 34 expected files are identical: the 18 JSON by value, the 16 captures byte for byte. The only other differences are explained: the resource ESTIMATE lines, the new mutants, and the moved line numbers of the same compiler notes |

### 10.3 Where the long chains end now (ESTIMATE) / 長い連鎖の終点

`gate_depth.py` (Yosys `synth -flatten -noabc`). Gate levels in front of each register group, RH004 → RH005:

| Register group | Bits | RH004 | RH005 |
|---|---|---|---|
| `taken_due`, `inbox_taken` | 2 | 146, 145 | 66, 65 |
| the store (`g_store`, `st_n`) | 4,096 | 136 | **33** |
| the pending masks | 128 | 136 | 56 |
| `error_flag`, `error_code`, `error_sn`, the trap | 19 | 129 | **112** |
| Accm | 32 | 127 | **106** |
| ADRS, Temp, SHV, LoopVal, JumpVal | 71 | 127 | 23–27 |
| SWEEP.a, copied | 37 | 127 | 54 |
| switch: `arm` … `ibx_*` (the GO check's results) | ≈ 400 | 99 | 77 |

In RH004, the chain more than 125 levels deep reached about 4,400 registers. Now the chains deeper than 100 levels reach about 50: the real MUL/MAC @PPM path through the overflow, in front of the error registers and Accm.

A gate level is not a nanosecond, so the second fit is the measure. My estimate is that MUL/MAC @PPM is close to 20 ns on this speed grade; if it does not close, that path is what step 2 removes.

### 10.4 Next / 次に

- **The second fit.** Please compile `DE10_Nano_wpms` as before (`make_quartus_project.py`, then Quartus). Send the *Multicorner Timing Analysis Summary*, and, if clk_sys still fails, `setup_clk_sys_groups.txt` from `report_setup_paths.tcl`.
- **If clk_sys closes:** Phase 6 continues with SignalTap and the captures.
- **If not:** step 2 at once, as ruled. Planned in its smallest form:
  - the E8 check of MUL and MAC moves to the next clock;
  - Accm is written in X and restored from a one-clock copy if that check fails, and the instruction behind is squashed;
  - the store, Temp, BCP and the copy keep their clocks, because MUL and MAC write only Accm;
  - EW2 keeps its clock. Only E8 is raised one clock later (and, when a prefetch's EW2 falls in the same clock, EW2 is the code reported).

**和文.**
- **変更（2026-10-03 の裁定どおり段階 1）。**
  - Formation RH005：各レジスタの書込み許可をその命令自身のエラー条件から作り、アドレス解読をレジスタ化し、EW5 の N の和を加算木に、重複検査を総当たりの並列比較にした。
  - スイッチ RH002：GO 検査の和を加算木に、PR-1 の重複検査を並列比較にした。
- **動作が変わらないことの証拠。**
  - 旧版と並べた毎クロック比較（320 万クロック、全出力・全レジスタ）で差は 0。
  - Phase 2〜6 の回帰も記録と同一（ボード 18 本と期待キャプチャ 16 本はバイト単位で一致）。
  - SAT で書き換えた論理の等価を 5 件すべて証明した。
  - Phase 2 は記録と同一（ミュータント 20 件の検出数も同じ、新規 3 件も検出）。
- **長い連鎖の終点（概算）。** ストア約 4,100 FF の前の連鎖は 136 段から 33 段に縮んだ。残る最長は実在の MUL/MAC @PPM 経路（エラー登録 112 段、Accm 106 段）。
- **次。** 第 2 回フィットで判定する。収束しなければ段階 2（E8 判定を次クロックへ、Accm は投機的に書いて控えから復元、後続命令を打ち消す）へ直ちに進む。

## 11. SD-22 step 2 and SD-23 (2026-10-03): the third fit's RTL / 段階 2 と SD-23：第 3 回フィットの RTL

**Ruling 2026-10-03:** if step 1 does not close timing, step 2 follows without a new round of questions. The second fit did not close: clk_sys −6.976 ns, TNS −1,509 ns (`quartus/2026-10-03_DE10_Nano_wpms_fit2/`).

### 11.1 What the second fit showed / 第 2 回フィットの結果

STA, slow 1100 mV 85 °C. `report_setup_paths.tcl`: 799 failing endpoints, TNS −1,398 ns. They fall into four groups by where their worst paths start:

| Group | Endpoints | Worst | Path |
|---|---|---|---|
| The switch's GO check | 469 | −2.605 ns | `x_a → xb → frozen[xb] →` the items fired `→ n_nx_v →` the entry mux `→` the sum (three adders) `→ go_bad → fire_now →` enables of `n_fu_v`, `cmask_v`, `reject0/3`, `go_seq`, `sw_fu`, `ibx_*` (fan-out 173) |
| MUL/MAC @PPM | 49 | −6.805 ns | the forwarded store read → 32 × 32 product (DSP and carry chain) → shift → add → overflow compare → Accm's enable, the error registers |
| BCP's EW5 | 168 | −4.812 ns | the take-set → `n_post` → the sum of N (three adders) → the compare → `bcp_commit` (fan-out 131) → the pending masks → `inbox_taken` |
| The Core's imem half-cycle path | 113 | −2.028 ns | the M10K, on clk_sys's falling edge → 10 LUT levels of the Core's next-state logic → `state_num` at the next rising edge: 10.70 ns in a 10 ns half period (**SD-23**) |

The first three are what step 2 was planned for (§10.4). The fourth is new.

### 11.2 What changed / 変更点

**Formation RH006** (`hw/l2/wpms_formation.v`):
- **(a) E8 of MUL and MAC in the clock after X (stage W).**
  - MUL and MAC write Accm in X. In W, the product's high bits (`w_hi`, registered) are checked. On E8, Accm is restored from a one-clock copy (`w_bk`), E8 is raised with the violator's SN, and the instruction then in X is squashed (`w_kill`).
  - A prefetch's EW2 met in a MUL's or MAC's X clock is held back one clock (`pf_w`). So the MUL's own E8, decided in W, keeps its priority, as in the model's order. Every error keeps its code and its SN.
- **(b) The operand read one clock ahead.** The store word as the program sees it (a pending slot reads what it will receive) and the inbox view are read at the next ADRS, from the next pending masks and this clock's writes, into `store_q` and `inbox_q`. The X clock starts from them.
  - The instruction in X is taken to complete (`sx_*`), so no error check stands in front of the read. When it does not complete, the Formation halts at that very edge and the value is never read.
- **(c) EW5's sum reduced one clock ahead.**
  - The nine terms (the eight N of the next sweep word, as BCP will see them, and −(NMAX + 1)) go through four levels of carry-save adders (`csa9`) into `ew5_s` and `ew5_c`. In X, one add gives the sign.
  - The pending masks' idle test takes BCP's commit at the last gate.

**Switch RH003** (`hw/switch/wpms_switch.v`):
- The items a GO fires and the blocks whose N it lands are read from `x_a[9]`, `x_a[4]`, `x_a[2:0]`, `x_d[1:0]` and `x_p3` directly. They no longer pass through the address decode and the frozen bits: the three places that use them (a GO; a go-now of a block; a go-now of the sweep word) check those conditions first.
- The sum of N against NMAX uses carry-save adders and one sign.

**The board (SD-23):** clk_sys is 30 % high in the 50 MHz revision (`SYS_DUTY`; `wpms_pll` RH002, the board top RH002, `make_quartus_project.py` RH003). The imem's read gets 14 ns; the address side, `state_num` straight into the M10K's address register, gets 6 ns. The Core and its wrapper are untouched; TimeQuest analyzes the real waveform. `--sys-duty 50` restores the clock of the first two fits. The architect's ruling is requested (`discrepancies.md`, SD-23).

**Tests that followed:**
- `wpms_formation_tb.v` RH003: the error index of the late E8; command J, an issue with the strobe in the same clock.
- `cosim_l2.py` RH003: group `late`, nine directed cases. They cover the instruction behind an overflowing MUL/MAC, EW2 in a MUL's X clock with and without its E8, a read of a slot right after BCP made it pending, and a strobe in the clock BCP is issued (both ways).
- `cosim_mutants.py` RH003: M1, M6, M12, M19 and M23 follow the new text; M24–M29 are new.
- `cosim_switch_mutants.py` RH003: W2, W4 and W5 follow the new text; W23 is new.
- `equiv_lockstep.py` RH002, `equiv_formal.py` RH002, `gate_depth.py` RH002 (`--lut`).

### 11.3 What the program and the system see / プログラムとシステムから見えるもの

- **Unchanged:** every value, every store word, and the clock of every instruction that completes.
- **Changed on purpose, two cases:**
  - an E8 of MUL or MAC;
  - an EW2 met in a MUL's or MAC's X clock.

  Each is raised one clock later, with the same code and SN. Accm ends as before the violator, and nothing after the violator executes.
- **What follows from that, in those two cases only:**
  - The trap request and L1's silence come one clock later.
  - The Core never stalls on the issue port (`ext_op_ready` = 1), so it may issue one more instruction before it takes the insertion. The Formation drops that instruction: it is squashed, or the Formation is already halted.
  - In Phase 2's clock table these two rows move by one clock.
- In the Phases 3–6 runs no E8 occurs, so their records repeat (§11.4).

### 11.4 How it was checked / 検証

| Check | Class | Result |
|---|---|---|
| **Lockstep.** Formation RH006 beside RH005, and switch RH003 beside RH002, both from commit 8815e35. NMAX 1,008 and 2,048, seeds 1 and 2, 400,000 clocks per run. Compared in every clock: every output, every register and the touched signals. The Formation's two late errors are allowed for: the same code and SN, one clock later | RTL-SIM | **0 differences in 8 runs** (3.2 M clocks). Each Formation run had 1,101–1,188 late E8s of MUL/MAC and 768–854 held-back EW2s, each with the reference's code and SN, in about 317,000 instructions covering every op and every error code. Each switch run made about 8,700 GOs and 1,870 go-nows, refused for every cause |
| **Formal.** The switch's GO path and check (NMAX 1,008 and 2,048). The Formation's pre-read, late E8 and EW5 lookahead (four claims), one clock from any state; its idle test and split enables, for every state and input. Three negative controls | formal (SAT) | **13/13 proved**; the controls come back SAT, as they must (`logs/equiv_formal.txt`) |
| **Phase 2.** `cosim_l2` against the golden model, with the new group `late` | RTL-SIM | **3,923/3,923** bit-identical; the summary equals the record but for `late` (9 cases). Mutants **29/29**. M1–M20 are caught at the recorded counts except M6, which is now split into M6 (the read ahead) and M29 (the registered decode) |
| **Phases 3–6.** The recipes rerun (`run_phase6.sh`, REGRESSION=1) and compared with the 2026-10-01 record | RTL-SIM | **ALL CHECKS PASSED.** The 18 board runs (`cosim_board.txt`) and all 34 expected files are identical to the record, the 16 captures byte for byte. The other differences are explained: the group `late` and the new mutants, the resource ESTIMATE lines, the count of one Icarus note, and the 30 % in the project's summary |

**What the checks found along the way** (each run below is the final one, after the change it prompted):
1. The first lockstep runs differed in `x_err`, `rd_val` and `ew5` in clocks where nothing executes. Those are values computed from inputs that are never used: a halted Formation, or the squashed clock. They are now compared only while an instruction executes.
2. The first mutant run: M27 survived. No Phase 2 case put a strobe in the clock a BCP is issued; the testbench could not. M24 and M26 were caught only by the RTL's self-checks. Hence command J and group `late`. Now every one of M24–M28 fails a case of `late`.
3. As first written, an EW2 in an overflowing MUL's X clock was reported instead of the MUL's E8. That is not the model's order (the model has the MUL execute first). Hence the held-back EW2 (`pf_w`): every error keeps its code and SN.
4. The first pre-read had the error checks of the instruction in X in front of its address: 24 LUT levels (ESTIMATE). It now takes that instruction as completing, which is exact because one that does not complete halts the Formation at that edge.
5. Yosys's own SAT solver did not finish a carry-save sum against an adder tree: 10 minutes on 5,500 variables, a known hard case. The problems are now written as CNF and solved by CaDiCaL. The EW5 claim is split into four smaller claims.

### 11.5 Where the chains end now (ESTIMATE) / 長い連鎖の終点（概算）

Gate levels (`gate_depth.py`, Yosys `synth -noabc`) and 6-input LUT levels (`gate_depth.py --lut`, Yosys's ABC) in front of each register group, step 1 (Formation RH005, switch RH002) → step 2 (RH006, RH003). The multiplier counts here as gates or LUTs; Quartus puts it in DSP blocks and a carry chain, so Accm and `w_hi`, which lie behind the product, read deeper than they are.

| Register group | Bits | Gates | 6-LUT levels |
|---|---|---|---|
| `error_flag`, `error_code`, `error_sn`, `insert_req_r` | 19 | 112 → **50** | 44 → **14–16** |
| Accm | 32 | 106 → 81 | 43 → 34 |
| `w_hi` (new: the product's high bits, checked in W) | 34 | – → 82 | – → 40 |
| `taken_due`, `inbox_taken` | 2 | 65–66 → **42–43** | 35–36 → **15–16** |
| the pending masks | 128 | 56 → **40** | 30 → **13** |
| SWEEP.a, copied | 37 | 54 → **38** | 28 → **11** |
| `ew5_s`, `ew5_c` (new: EW5's sum, one clock ahead) | 67 | – → 43–44 | – → 23 |
| `store_q`, `inbox_q` (new: the operand, one clock ahead) | 64 | – → 34–39 | – → 21–22 |
| the store (`g_store`, `st_n`) | 4,096 | 33 → 34 | 12 → 11 |
| switch: `arm` … `ibx_*` (the GO check's results) | ≈ 400 | 77 → **67** | 16 → **13** |

- What the second fit measured, against step 1's counts:
  - the EW5 path into `inbox_taken`, 35 LUT levels by this count, was 16 logic levels for Quartus, 24.2 ns. Its three adders are LUT chains here and carry chains there;
  - the switch's path, 16 LUT levels by this count, was 16 logic levels for Quartus too, at 21.9 ns, with a fan-out of 173 at its end;
  - the store read with forwarding: 7 logic levels, 7.9 ns.
- So the count does not translate into nanoseconds, least of all for the new paths, which have no adder. ABC maps the whole design deeper than its parts: the carry-save tree, 3 LUT levels when mapped alone, ends 8–9 levels after its terms in the design.
- Counted as the Fitter builds them, with the second fit's delays (1.1–1.4 ns per logic level with its routing; about 19.4 ns of data delay allowed):
  - `store_q`: the opcode (2 levels), the next block (2, with ADRS + 1 on a carry chain), the read (4), the forwarding (2). About 10 levels, 12.5 ns, slack about +7 ns.
  - The EW5 lookahead: the next take-set, pending bits and N (about 6 levels), the term mux (2), four carry-save levels. About 12 levels, 15 ns, slack about +4.5 ns.
  - The EW5 check in X: one add on a carry chain, the sign, `bcp_commit`, then the second fit's 6.3 ns from `bcp_commit` to `inbox_taken`. About 13.5 ns, slack about +6 ns.
- The lookahead has the least margin. If it fails, the fallback is to register after the second carry-save level (four words). That gives the lookahead about +6.5 ns and the check in X about +3.4 ns. It is not done now, because it would lower the worst of the three.
- Resources (ESTIMATE, Yosys `synth_intel_alm`, the Formation alone): 4,535 → 6,565 LUTs, 1,214 → 1,420 registers; M10K/MLAB and DSP unchanged. Synthesizing RH006 without each part shows where the +2,030 LUTs go:
  - the EW5 lookahead, about 1,800: N of all eight blocks after this clock's writes (about 1,350), the term muxes and the carry-save adders;
  - the pre-read, about 250.


### 11.6 The third fit: expected before the compile / 第 3 回フィット：コンパイル前の期待値

| # | Expected | Basis |
|---|---|---|
| H1 | **clk_sys closes** at the slow corner. The four groups of the second fit leave the failing list | the paths below |
| H2 | MUL/MAC into Accm: `store_q` (a register) → `m_b` → DSP → carry chain → shift → add → Accm, about 15 ns. The overflow compare, the store read and Accm's enable are no longer on it (the second fit's components: 7.9 + 1.9 + 3.3 ns) | fit 2's path, `observation.md` G2 |
| H3 | The switch's GO check: about 4 ns shorter at the front (the decode, the frozen bits and the items fired: 6.5 ns in the second fit, now about 2.5) and about 2 ns in the sum. Slack about +3 ns | fit 2's path, G4 |
| H4 | BCP's EW5: the sum is two registers and one add: `bcp_commit` about 9 ns after the clock instead of 22 | fit 2's path |
| H5 | The Core's imem path: 14 ns for the read side. With the second fit's 10.70 ns of data and −1.25 ns of skew, about +2 ns | SD-23 |
| H6 | The new paths, each below 20 ns: the operand read ahead (`store_q`, about 10 logic levels, 12.5 ns) and the EW5 lookahead (`ew5_s`, `ew5_c`: about 12 levels, 15 ns, the least margin, about +4.5 ns); the EW5 check in X about 13.5 ns. Yosys's LUT count (21–23 levels) overstates them | §11.5 |
| H7 | Hold met. The Formation about 1,000–2,000 ALMs larger than in the second fit (Yosys: +2,030 LUTs, +206 registers, about 1,800 of the LUTs in the EW5 lookahead); the whole design about 12,000–13,000 ALMs, under a third of the device | estimate, §11.5 |

### 11.7 What I need / お願い

- **The third fit.** Rerun `make_quartus_project.py` (it writes `SYS_DUTY 30` into `DE10_Nano_wpms.qsf`) and compile `DE10_Nano_wpms`. Please send:
  - the *Multicorner Timing Analysis Summary*;
  - if clk_sys still fails, `setup_clk_sys_groups.txt` and `setup_clk_sys_keys.rpt` from `report_setup_paths.tcl`;
  - the Fitter's *Resource Utilization by Entity*, for the ledger;
  - the duty cycle the Fitter set for clk_sys, from its PLL report (30 % expected; SD-23).
- **A ruling on SD-23:** keep clk_sys at 30 % high, or the Core's documented migration (EDGE "POS" + a fetch stage, Layer 1).
- **If clk_sys closes:** Phase 6 continues with SignalTap and the captures.

**和文.**
- **第 2 回フィットの結果。** 失敗 799 端点は四群に分かれた。
  - スイッチの GO 検査（−2.6 ns）
  - MUL/MAC @PPM（−6.8 ns）
  - BCP の EW5（−4.8 ns）
  - Core の imem 半周期経路（−2.0 ns、新しい項目 SD-23）
- **段階 2（2026-10-03 の裁定どおり、改めて伺わずに実施）。**
  - Formation RH006：
    - MUL/MAC の E8 を次のクロック（W）で判定する。Accm は控えから戻し、後続の命令は打ち消す。その X クロックに重なったプリフェッチの EW2 も 1 クロック待たせ、どのエラーもコードと SN は従来どおりにした。
    - 次の ADRS のオペランドを 1 クロック先に読む。X の命令は完了するとみなす。完了しなければ同じエッジで停止するので、厳密に同じになる。
    - EW5 の N の和を 1 クロック先にキャリーセーブ加算で 2 語にまとめる。
  - スイッチ RH003：GO 検査の入口をアドレス解読と凍結ビットを通さずにレジスタから作り、和をキャリーセーブ加算と符号判定にした。
- **SD-23。** Core と imem には触れず、50 MHz 版の clk_sys をデューティ 30 % にする。読出し側は 14 ns、アドレス側は 6 ns になる。裁定をお願いしたい（`--sys-duty 50` で元に戻る）。
- **意図した変更は 2 つだけ。**
  - MUL/MAC の E8
  - その X クロックの EW2

  どちらも 1 クロック遅れて、同じコードと SN で上がる。ほかは段階 1 の記録と同じ（§11.4）。
- **お願い。** 第 3 回フィットのタイミング要約（収束しなければ集計とキー経路）、資源の Entity 別報告、Fitter が clk_sys に設定したデューティ比（PLL の報告、30 % の見込み）、SD-23 の裁定。

## 12. The first sound (2026-10-03) / 初音

The architect programmed the board with the second fit's bitstream (to be confirmed). They connected an HDMI audio extractor, an oscilloscope and a loudspeaker, and reported "a waveform based on a 1 kHz sine, amplitude-modulated with a period of 250 ms, with slow changes, very stable". The record is in `signaltap/2026-10-03_first_sound/observation.md`. Evidence class: SILICON, qualitative.

- **Expected** (derived after the report from the ROM's integers, Ch.3 §3.10).
  - The test origin is 1,008 partials, equal in amplitude and in phase at the GO, from 996.000 to 999.939 Hz, 3.912 mHz apart.
  - Their sum is a 997.97 Hz carrier times the envelope \|sin(πN·df·t) / sin(π·df·t)\|. The envelope has nulls every 253.62 ms and a 255.65 s cycle.
  - It is loudest right after the GO; about 60 dB lower at 2 min 8 s; loud again at 4 min 15.7 s.
- **Verdict:** consistent, qualitatively.
- **What it shows.** The whole chain plays the test origin from the ROM on silicon: the Core, the Formation, the sequencer, L1, I2S and the ADV7513's HDMI audio. The ADV7513's configuration had been checked only against its data sheet until now.
- **What it does not show:** timing margin. This bitstream misses clk_sys by 6.976 ns at the slow corner. This board runs it at room temperature, but nothing is guaranteed at 85 °C or on a slower part. SD-22 continues, and the SignalTap captures C1–C5 wait for a timing-closed build.

**The SignalTap capture `ptsg_core_debug` (the same day).** The architect captured the Core's `state_num`, `timing_signals`, `stay_cnt` and the I2S pins: 8,192 samples of clk_sys (`signaltap/2026-10-03_core_debug/`, analysed by the new `hw/tools/vcd_i2s_check.py`). SILICON, compared with the model:
- **The packet Stay** is 1,008 clocks in every sweep. **The sweep period** is 1,041 or 1,042 clocks (mean 1,041.71 = 50 MHz / 48 kHz), and the packet's Stay Set comes 12–13 clocks before the left channel begins: the sweeps are locked to the audio frames.
- **The I2S words equal the model bit for bit:** 8 frames, L = R. The point was found by the closed form: 39,684,738 sweeps after the GO (13 min 46.8 s), G = 0 (2.0 LSB rms; the next best fit 1,005).
- **The phases are right after 40 million sweeps.** The packet's window program updates PH0, PHD1 and PHD2 in the store every sweep (LDM, ADD @PPM, STM). None of those updates failed on this not-timing-closed build at room temperature. The worst path, MUL/MAC @PPM, is not used by the test origin.
- **G = 0 means DIP[1:0] = 00:** 72 dB above G = 12, so the output clips at the top of every beat over about 85 % of each cycle. SW[1:0] = 11 gives the designed level.

**和文.**
- 第 2 回フィットのビットストリーム（要確認）で、試験原点の音が HDMI 経由で出た。報告は「約 1 kHz、250 ms 周期の振幅変調、ゆっくりした変化、きわめて安定」。
- 期待値（ROM の整数から報告後に導出）：997.97 Hz の搬送波、包絡の零点は 253.62 ms ごと、255.65 s 周期。定性的に一致する。
- Core から HDMI 音声までの全経路がシリコン上で動くことを示す。タイミングの余裕は示さない。
- 同日の SignalTap 取得（`ptsg_core_debug`）では、I2S の 8 フレームがモデルとビット単位で一致した（GO から 39,684,738 掃引目、G = 0）。位相の更新は約 4,000 万掃引のあいだ一度も誤っていない。掃引はオーディオのフレームにロックしている。DIP[1:0] は 00 で、設計の音量は SW[1:0] = 11。

## 13. The third fit (2026-10-04): clk_sys closes at 50 MHz / 第 3 回フィット：50 MHz で clk_sys が収束

The architect compiled `DE10_Nano_wpms` after PR #7: Formation RH006, switch RH003, clk_sys 30 % high. The records are in `quartus/2026-10-04_DE10_Nano_wpms_fit3/`: `observation.md`, the reports and `ledger.md`.

### 13.1 Timing (STA) against §11.6 / タイミング

| # | Expected (§11.6) | Observed | Verdict |
|---|---|---|---|
| H1 | clk_sys closes | **setup +0.978 ns, TNS 0** (Slow 1100 mV 0 °C model); hold +0.042 ns; every clock meets | as expected |
| H2 | MUL/MAC about 15 ns | MAC into `w_hi`, 18.8 ns of data delay; all 10 worst endpoints are `w_hi`. The estimate left out the opcode decode in front of the operand select (3.5 ns) | not as estimated; closes nevertheless |
| H3–H6 | the switch about +3 ns, `bcp_commit` about 9 ns, the Core about +2 ns, the new paths below 20 ns | none of them is among the 10 worst: each slack ≥ +1.547 ns | met (a lower bound) |
| H5, the clock | 30 % high | clk_sys's minimum pulse width slack fell by 4.0 ns (8.541 → 4.544): 6 ns high, as set | as set |
| H7 | hold met; the Formation +1,000–2,000 ALMs | hold met (+0.042 ns, thin); the Formation +259 ALMs over the first fit | resources far below the estimate |

Worst setup slack of clk_sys by fit: −14.307 ns (first), −6.976 ns (second), **+0.978 ns** (third).

### 13.2 Resource ledger (SILICON, the Fitter) / 資源台帳

In the Core's format:

| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs |
|---|---|---|---|---|
| 2026-10-04 | DE10_Nano_wpms (50 MHz, clk_sys 30 % high): Core RH031p, Formation RH006, switch RH003 | 500.9 | 454.3 | 800 (751) |

Per entity, total with entity-only in brackets; first fit in the last column:

| Entity | ALMs | Registers | M10K | DSP | First fit (ALMs) |
|---|---|---|---|---|---|
| board top (all) | 11,321.7 (100.7) | 14,835 | 22 | 23 | 11,052.8 |
| Formation | 7,048.0 | 9,267 | 9 | 3 | 6,788.7 |
| input switch | 1,659.7 (1,611.2) | 1,481 | 4 | 0 | 1,692.2 |
| L1 module | 827.4 (578.1) | 1,532 | 5 | 20 | 831.7 |
| PTSG-Core (RH031p) | 500.9 (454.3) | 308 | 4 | 0 | 457.7 |

The whole design uses about 27 % of the device's ALMs. SignalTap is not in this build. The full table is `ledger.md`.

### 13.3 The architect's answers to §6 (2026-10-04) / §6 への回答

1. **Compile:** the 100 MHz revision follows once 50 MHz operation is established.
2. **SignalTap:** `wpms_tap.stp` may be committed once it exists.
3. **Captures:** the architect takes them and sends each VCD export with its host log. The HDMI sink with speakers already works (§12).
4. **The resource ledger** comes from the Fitter report (§13.2); the Yosys figures are for reference only.

### 13.4 A correction: SW[1:0] / 訂正

The board README (§2, 2026-10-01) said to set SW[1:0] = 00. That is wrong. G = DIP[1:0] × 4, so 00 gives G = 0. Every expected value, the board bench (`sw = 4'b0111`) and the capture analysis (`phase6_evidence.py`, G = 12) assume G = 12, which is SW[1:0] = 11.
- This is why the first sound and the capture `ptsg_core_debug` ran at G = 0 (§12).
- Corrected on 2026-10-04: the README now says SW[1:0] = 11, and each capture template (`signaltap/phase6_pending/`) gets a row for the switches. Only that row changed (`phase6_templates.py` RH002); the expected values are as written on 2026-10-01.
- **Before the captures C1–C5, please set SW[1:0] = 11** (both up). With 00, the banks on the I2S pins cannot equal the expected ones.

和文：ボードの README §2（2026-10-01）は SW[1:0] = 00 と書いていたが、これは誤りだった。00 は G = 0 になる。期待値、ベンチ、取得の解析はすべて G = 12、すなわち SW[1:0] = 11 を前提とする。初音と ptsg_core_debug が G = 0 だったのはこのため。README を 11 に直し、取得テンプレートにスイッチの行を加えた（期待値は変えていない）。**C1〜C5 の取得の前に SW[1:0] = 11（両方上）にしてください。**

### 13.5 Next / 次に

- **The captures C1–C5 at 50 MHz**, on a build with `wpms_tap.stp`. That is a new fit, so its timing must be read again: this fit's margin is +0.98 ns.
- **The SD-23 ruling** (`discrepancies.md`).
- **The 100 MHz revision**, after that.

**和文.**
- 第 3 回フィットで clk_sys は **+0.978 ns、TNS 0** となり、50 MHz で収束した（推移：−14.307 → −6.976 → +0.978 ns）。ホールドは +0.042 ns。
- 最悪 10 端点はすべて MAC → `w_hi`（18.8 ns）。見込み（約 15 ns）は、乗数選択の前のデコード 3.5 ns を落としていた。スイッチ、EW5、Core の imem 経路、新しい経路は最悪 10 本に入らない。
- デューティ比 30 % は設定どおり入った（最小パルス幅のスラックが 4.0 ns 減）。
- 資源は全体 11,321.7 ALM（デバイスの約 27 %）、Formation 7,048.0 ALM（第 1 回比 +259）。
- §6 への回答（2026-10-04）：
  - 100 MHz は 50 MHz の動作確立後。
  - `.stp` はコミット可。
  - 取得物は VCD とホストのログで受け渡す。
  - 台帳は Fitter 報告から作る。
- 次は、SignalTap を入れたビルドで C1〜C5 を取得する。新しいフィットなので、タイミングを読み直す。あわせて SD-23 の裁定をお願いしたい。
