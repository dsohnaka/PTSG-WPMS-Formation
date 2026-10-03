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
| **Phases 3–6.** The recipes rerun and their logs compared with the 2026-10-01 record (the 18 board runs, the 16 expected captures) | RTL-SIM | *running when this was committed; the result follows in the next commit* |

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
  - SAT で書き換えた論理の等価を 5 件すべて証明した。
  - Phase 2 は記録と同一（ミュータント 20 件の検出数も同じ、新規 3 件も検出）。
- **長い連鎖の終点（概算）。** ストア約 4,100 FF の前の連鎖は 136 段から 33 段に縮んだ。残る最長は実在の MUL/MAC @PPM 経路（エラー登録 112 段、Accm 106 段）。
- **次。** 第 2 回フィットで判定する。収束しなければ段階 2（E8 判定を次クロックへ、Accm は投機的に書いて控えから復元、後続命令を打ち消す）へ直ちに進む。
