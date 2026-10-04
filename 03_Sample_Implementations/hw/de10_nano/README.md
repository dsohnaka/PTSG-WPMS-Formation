# hw/de10_nano — the WPMS silicon sample on the Terasic DE10-nano / DE10-nano 上の WPMS シリコン試作

> **License: MIT.** SILICON_BRIEF_2026-09-27 Phase 6. The board top, its Quartus project, the bring-up procedure and the SignalTap captures of the eight evidence items. Everything of the sound and its control is `hw/switch/wpms_system.v` (Phases 2–5); this folder adds only what depends on the board.
>
> **ライセンス: MIT。** SILICON_BRIEF Phase 6。ボードのトップ、Quartus プロジェクト、立ち上げ手順、証拠 8 項目の SignalTap 取得手順。音とその制御はすべて `hw/switch/wpms_system.v`（Phase 2〜5）にあり、ここにはボードに依存するものだけを置く。

## Files / ファイル

| File | What it is |
|---|---|
| `DE10_Nano_wpms_top.v` | The board top. Pins of the Terasic golden top; three PLLs (`clk_sys` 50 or 100 MHz, MCLK 12.288 MHz, pixel 74.25 MHz at 0° and 180°); resets (power-on, PLL lock, SW[2], JTAG); the ADV7513 configurator, the 720p60 video carrier, I2S + MCLK; the LEDs; ISSP instance **BRD**; the tap registers `tap_ctl` / `tap_dat` for SignalTap. Two parameters, set by the revision: `SYS_MHZ` (50 or 100) and `SYS_DUTY`, clk_sys's time high in percent (SD-23). |
| `wpms_pll.v` | One Cyclone V PLL, `altera_pll` instantiated directly (as the Core's 100 MHz top); `DUTY0`, the first output's duty cycle. |
| `DE10_Nano_wpms.sdc` | The constraints of both revisions (header: what is constrained and why). |
| `make_quartus_project.py` | Writes the Quartus project (flat, git-ignored) to `build/quartus/`; `--check` tests it without Quartus. |
| `wpms_tap.stp` | The SignalTap file, the architect's (2026-10-04; §3): the setup only, with no stored acquisition. `make_quartus_project.py` copies it into `build/quartus/` when none is there and enables it in the 50 MHz revision. |
| `report_setup_paths.tcl` | After a compile: every failing clk_sys setup endpoint, grouped by register, and the worst path into each register class (`quartus_sta -t`; SD-22). |
| `run_phase6.sh` | Every check that can run before the board (regression, images, scripts, project, board-level RTL-SIM). |
| `inject/` | The EW2–EW5 injection images (score + window source + `.hex` + `.mif`), from `hw/tools/gen_inject_scores.py`. |
| `sim/` | The board-level bench (`DE10_Nano_wpms_tb.v`), the behavioural PLL (`wpms_pll_sim.v`), stand-ins of the Intel primitives for the elaboration check (`vendor_stubs.v`). Never given to Quartus. |

Tools elsewhere: `hw/tools/cosim_board.py` (board-level RTL-SIM of every capture below), `hw/tools/phase6_evidence.py` (reads a SignalTap export and measures the evidence items), `hw/tools/resource_ledger.py` (the ledger from the Fitter report), `hw/tools/host/wpms_phase6_*.tcl` (the host steps of the captures).

## 1. Build / ビルド

```
python3 hw/de10_nano/make_quartus_project.py            # -> hw/de10_nano/build/quartus/
```

Open `build/quartus/DE10_Nano_wpms.qpf` in Quartus Prime Lite 23.1std.1. Two revisions (Project ▸ Revisions, or the toolbar's list):

| Revision | `SYS_MHZ` | `SYS_DUTY` | clk_sys | NMAX | Test origin N | T_min (clocks per 48 kHz sample) |
|---|---|---|---|---|---|---|
| `DE10_Nano_wpms` (first) | 50 | 30 | 50 MHz, high 6 ns | 1,008 | 1,008 | 1,041 |
| `DE10_Nano_wpms100` | 100 | 50 | 100 MHz | 2,048 | 2,048 | 2,083 |

**clk_sys's duty cycle (SD-23).** The Core's imem (`ptsg_imem`, EDGE "NEG") reads on clk_sys's falling edge, and the Core's registers take the word at the next rising edge. At 50 % that is 10 ns, which the second fit missed by 2.0 ns. From the third fit on, the 50 MHz revision runs clk_sys 30 % high: the read side gets 14 ns, the address side (`state_num`, a register straight into the M10K) 6 ns. The Core and its wrapper are untouched, and TimeQuest analyzes the real waveform. `make_quartus_project.py --sys-duty 50` builds the 50 MHz revision as the first two fits had it. Adopted by the architect's ruling of 2026-10-04 (`reports/discrepancies.md`, SD-23); the third fit closed with it.

Command line: `quartus_sh --flow compile DE10_Nano_wpms -c DE10_Nano_wpms` (or `-c DE10_Nano_wpms100`).

**Timing (TimeQuest):** the SDC prints one info message listing the clocks it found (clk_sys, clk_aud, the pixel clocks, the forwarded one). A critical warning means it did not find the 180° pixel clock and the HDMI pixel bus is unconstrained — please send me the message. At 100 MHz the expected critical path is the imem half-cycle path (EDGE "NEG", 5 ns each way). It is not waived; if it fails, the 50 MHz revision is the effective target (rulings 2026-09-28/29). The HDMI pixel bus is checked against `hdmi_tx_clk` (t_VSU 1.8 ns, t_VHLD 1.3 ns, +0.2 ns board); the I2S lines are cut (162.8 ns of margin by construction, SDC header).

**After a compile, if clk_sys fails (SD-22):** copy `report_setup_paths.tcl` into `build/quartus/` (`make_quartus_project.py` also copies it) and run `quartus_sta -t report_setup_paths.tcl` there, or `source` it from the Timing Analyzer's Tcl console with the project open. It writes `output_files/setup_clk_sys_groups.txt`: every failing endpoint, grouped by register, with the worst slack, TNS, logic levels and start point of each group. Send that file first. `setup_clk_sys_keys.rpt` (the worst path into each register class) and `setup_clk_sys_worst10.rpt` show the cells.

clk_sys が満たさないときは、`report_setup_paths.tcl` を `build/quartus/` で `quartus_sta -t` で実行してください。失敗した終点をレジスタ別に集計した `setup_clk_sys_groups.txt` を、まずお送りください。

**What was checked here without Quartus:** `make_quartus_project.py --check` runs both `.qsf` files and the `.sdc` under a plain tclsh against stand-ins. It checks: 52 pins equal to the golden top's, every file present, five clock groups covering all twelve clocks, `hdmi_tx_clk` taken from the 180° counter. It also elaborates the project's Verilog with Icarus, the INTEL branches taken and the primitives stood in, and checks every PLL, memory and ISSP parameter; `--mutants` breaks the project seven ways and requires each to be caught. **Not checked:** Quartus itself. The first compile will say whether `altera_pll` accepts the strings, whether the fitter places three fractional PLLs on these clock pins, and what timing closes.

Quartus がないため、ここでは `--check` で代役（tclsh と Icarus）による検査だけを行った。ピン 52 本が golden top と一致し、ファイルはすべてそろっている。クロックは 12 本が 5 群に収まり、`hdmi_tx_clk` は 180° 出力から作られている。INTEL 分岐をエラボレーションし、PLL・メモリ・ISSP のパラメータも確認した。Quartus そのもの（PLL 文字列の受理、分数 PLL 3 基の配置、タイミング収束）は初回コンパイルで判明する。100 MHz で imem 半周期パスが通らなければ、裁定どおり 50 MHz 版が実効目標となる。

## 2. Board settings and first light / ボード設定と初点灯

**Switches before power-up:**
- SW[1:0] = 11, both up: G = 12, which the models and the expected captures assume. With 00, G = 0: 72 dB louder, and the test origin clips at full scale;
- SW[2] = 0 (run; 1 holds the sound in reset, Ch.5 §5.8);
- SW[3] = 0 (no soft mute).

An HDMI monitor with speakers on the HDMI connector.

**Keys:** KEY[0] = GO_ALL, KEY[1] = the test origin again.

**Program** `output_files/<revision>.sof` (USB-Blaster II, DE-SoC chain: the FPGA is the second device). Within a second:

| LED | Meaning | First light |
|---|---|---|
| LED[0] | heartbeat: toggles every 24,000 strobes | blinks at 1 Hz (the 48 kHz grid runs) |
| LED[1] | the three PLLs locked | on |
| LED[2] | the ADV7513 table written | on once a sink is connected |
| LED[3] | HPD (a sink is connected) | on |
| LED[4] | Formation error_flag | **off** |
| LED[5] | the Core halted (C3-F24) | **off** |
| LED[6] | packets played in the last 0.5 s | on (the test origin plays) |
| LED[7] | I2C not acknowledged (sticky) | **off** |

**Expected on the monitor:**
- **Picture:** 1280×720 at 60 Hz, eight colour bars (the carrier).
- **Sound:** the test origin, a steady tone near 996 Hz at the level of Ch.3 §3.10. It is block 0: N = NMAX bins from 996 Hz, spaced 1/256 Hz.

**Status without SignalTap:** Tools ▸ In-System Sources and Probes Editor shows four instances:
- **HOST:** the host path; use the scripts.
- **STAT, INSP:** live probes; layout in `hw/switch/wpms_system.v`.
- **BRD:** 21 probes `{ADV7513 tables[7:0], NACK, HPD, done, HDMI_TX_INT, lock pix, lock aud, lock sys, SW[3:0], KEY[1:0]}`. Its source[0] holds the whole sound in reset while 1 (the JTAG reset of the Core's harness).

From `quartus_stp -s` in `build/quartus`, `source host/wpms_issp_host.tcl; wpms_open; wpms_status; wpms_close` prints eleven words: GO_SEQ, APPLIED_SEQ/SAMPLE, MG, G_EFF, CLIP, STROBE_INTERVAL (1,041/1,042 at 50 MHz), REJECT, SWEEP_ACTIVE, SWEEP_CLOCKS.

電源投入前：SW[1:0]=11（両方上、G = 12。モデルと期待値の前提。00 は G = 0 で 72 dB 大きく、クリップする）、SW[2]=0（1 で音系をリセット保持）、SW[3]=0。HDMI はスピーカー付きモニタへ。初点灯では LED[0] が 1 Hz で点滅し、LED[1]・[2]・[3]・[6] が点灯、LED[4]・[5]・[7] は消灯。画面は 720p60 のカラーバー、音は試験原点（約 996 Hz の定常音）。ISSP エディタには HOST・STAT・INSP・BRD の 4 インスタンスが見える。BRD の source[0] を 1 にすると音系全体がリセット保持される。

## 3. SignalTap (one instance, set up once) / SignalTap（1 インスタンス、一度だけ設定）

| Setting | Value |
|---|---|
| Clock | `clk_sys` (Node Finder, filter *SignalTap: pre-synthesis*, top level) |
| Nodes | `tap_ctl[100:0]` (trigger + data); `tap_dat[303:0]` (data only: clear *Trigger Enable*) |
| Sample depth | 4 K (4,096): 405 bits × 4 K ≈ 1.66 Mbit — about 203 M10K in the 4 K × 2 mode, of the device's roughly 500 (the design itself needs about ten; the Fitter states both) |
| Trigger position | **Pre trigger position** (12 % before the trigger) for every capture |
| Storage qualifier | type **Input port**; the port is the **node** `tap_ctl[100]` (= packet_start or bank_we), chosen with the Node Finder (*…*), not typed in. After the compile, the Fitter's input pins must not include one named `tap_ctl[100]`. On 2026-10-04 the `.stp` held the port as a pin (`storage_qualifier_port_is_pin="true"`), and C3's qualifier did not follow `tap_ctl[100]`. **Disable storage qualifier** (a run-time switch) for the continuous captures C1, C2, C4, C5 |
| Trigger | basic AND, per capture below |

The architect's `wpms_tap.stp` is committed (2026-10-04). `make_quartus_project.py` copies it into `build/quartus/` when none is there and enables it in the 50 MHz revision. A `.stp` already there, with your edits and acquisitions, is kept. `--no-signaltap` leaves SignalTap out. A SignalTap build is a new fit: read its timing again. Each capture: run the analysis once, do the capture's action, then **File ▸ Export ▸ VCD** into the evidence folder.

**If the export fails**, save the `.stp` (**File ▸ Save**) right after the acquisition and send it instead: the acquisition is stored in it. `python3 hw/tools/stp_log_to_vcd.py FILE.stp C5_ew5.vcd.gz` writes the same VCD (`--list` shows the stored acquisitions, `--log N` picks one). It checks each one against its own trigger. The saved `.stp` also keeps what the export drops: the marks where a storage-qualified record skipped clocks.

The tap layout (one clock late, all alike; decoded by `phase6_evidence.py`):
- `tap_ctl[7:0]`: strobe, packet_start, bin_valid, inbox_taken, error_flag, Core halted, seq_idle, bank_we;
- `[12:8]`: error code; `[24:13]`: K; `[36:25]`: the Core's state; `[39:37]`: the packet's index q;
- `[67:40]`: SWEEP.a (`[43:40]` = P); `[99:68]`: strobes since reset;
- `[100]`: the qualifier.
- `tap_dat`: `[255:0]` the bundle, `[279:256]` bank L, `[303:280]` bank R.

SignalTap は 1 インスタンスを一度だけ設定する。クロックは clk_sys、深さは 4 K、トリガ位置は全取得で「pre」（トリガ前 12 %）。`tap_dat` はデータ専用でトリガ不要。ストレージ・クオリファイアは入力ポート `tap_ctl[100]` とし、連続取得（C1・C2・C4・C5）では実行時に「無効化」する。ポートはノード `tap_ctl[100]` を Node Finder で選ぶ（名前を打ち込むとピン扱いになりうる。2026-10-04 の C3 はこれで期待どおりに絞られなかった）。

VCD のエクスポートが失敗したときは、取得の直後に `.stp` を保存（File ▸ Save）し、VCD の代わりに送ってほしい。取得データは `.stp` の中に保存されており、`stp_log_to_vcd.py` で同じ VCD に変換できる。

## 4. The captures / 取得

Expected values: `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/<case>_<budget>.json` (RTL-SIM, written before the board). The same captures cut from RTL-SIM are there as `expected_<case>_<budget>.vcd.gz`, in the layout of a SignalTap export. Each observation template is in `04_Verification_Evidence/signaltap/phase6_pending/`.

| Capture | Items | Action | Trigger (12 % pre) | Qualifier |
|---|---|---|---|---|
| **C1** origin | 2, 3, 4 (small take), 5 | BRD source[0] → 1 (the sound held in reset); **arm**; source[0] → 0 | `tap_ctl[1]` = 1 (first packet_start) | disabled |
| **C2** full8 | 1, 2, 3, 4 (full take-set), 5 | reset; **arm**; `quartus_stp -t host/wpms_phase6_full8_<NMAX>.tcl > full8.log` | `tap_ctl[43:40]` = 1000 (P = 8) | disabled |
| **C3** first_go | 7, 8 | reset; listen to the origin; **arm**; `quartus_stp -t host/wpms_phase6_first_go_<NMAX>.tcl > first_go.log`; **listen** | `tap_ctl[43:40]` = 0011 (P = 3) | **enabled** |
| **C4** EW6 | 6 | reset; **arm**; `quartus_stp -t host/wpms_phase6_ew6_<NMAX>.tcl > ew6.log` | `tap_ctl[4]` rising (error_flag) | disabled |
| **C5** EW2–EW5 | 6 | BRD source[0] → 1; ISMCE: instance **PTSG** ▸ load `inject/wpms_r1d_ew<k>.mif` (EW5: `_ew5_<NMAX>.mif`) ▸ write; **arm**; source[0] → 0 | `tap_ctl[4]` rising | disabled |

**Arm** = Run Analysis once in SignalTap. **Reset** = BRD source[0] 1 → 0 (or SW[2] up → down): the switch starts again from the ROM's test origin (P = 1), so no trigger of C2–C4 can fire before its script runs. For C1 and C5 the sound is held in reset while SignalTap is armed — the origin plays packets all the time, and an injection image written while the Core runs may raise its error at once — and released only then. After C5, restore the score: ISMCE ▸ PTSG ▸ `wpms_r1d.mif` ▸ write (or program the `.sof` again).

**If a script stops in `wpms_open` with "There is already an active In-System Sources and Probes session started"**, that was the host script's own defect, fixed on 2026-10-04 (`wpms_issp_host.tcl` RH002). Update `build/quartus/host/`: rerun `make_quartus_project.py`, or copy `hw/tools/host/wpms_issp_host.tcl` there. If the message still appears, another program holds the session. Close the In-System Sources and Probes Editor, and use SW[2] for the reset.

スクリプトが `wpms_open` で「There is already an active In-System Sources and Probes session started」と止まる場合、これはホストスクリプト自身の不具合で、2026-10-04 に修正した（RH002）。`build/quartus/host/` を更新してほしい（`make_quartus_project.py` の再実行か、`hw/tools/host/wpms_issp_host.tcl` の複写）。それでも出る場合は、ほかのプログラムがセッションを持っている。In-System Sources and Probes Editor を閉じ、リセットには SW[2] を使ってほしい。

**Listening (item 8, C3):**
- **First:** the test origin, near 996 Hz.
- **After the GO:** a C-major triad. Left: C5 + E5. Right: E5 + G5 (RT of blocks 1/2/3 = left / both / right).
- **Expected spectrum (RTL-SIM, `pcm` case):** left peaks 524.4 and 659.2 Hz; right 660.6 and 782.2 Hz (the model's identical).

**Analysis of each export** (in the evidence folder):
```
python3 hw/tools/phase6_evidence.py C2_full8.vcd --budget 50 --log full8.log --json observed.json
python3 hw/tools/phase6_evidence.py C5_ew3.vcd --budget 50 --log reset.log --score hw/de10_nano/inject/wpms_r1d_ew3.score
```
For C1 and C5, which have no script, `reset.log` holds the one line `RESET`: the model then starts from reset. Without a log the tool does not compare with the model. Give each run of a script its own log name (`> first_go_1.log`, `> first_go_2.log`): a second run into the same name overwrites the first, as happened to C3's log on 2026-10-04. A log written by PowerShell's `>` is UTF-16; the tool reads it.
`--budget 100` for the 100 MHz revision. The log is what the Tcl printed. The tool understands `W aaa dddddddd -> rrrrrrrr`, `R aaa -> rrrrrrrr` and `applied GO g at sweep s`; add a line `RESET` where the board was reset. For a capture long after reset (C3), the model starts from the GO itself: it is complete (every slot of every block it plays, and the sweep word). If SignalTap exports without the clock signal, the tool samples once per period of the time stamps (`--period-ps` overrides).

取得は C1〜C5 の 5 種類。C1 と C5 では、音系をリセット保持したまま SignalTap を待機させ、その後に解除する（試験原点は常にパケットを出しており、実行中に書いた注入像はその場でエラーを起こしうるため）。各取得の期待値（RTL-SIM、実機より先に記録）と、同じ手順で RTL-SIM から切り出した VCD（SignalTap エクスポート形式）は `04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board/expected/` にある。C5 のあとは ISMCE で `wpms_r1d.mif` を書き戻す。C3 では耳でも確認する：試験原点（約 996 Hz）のあと C メジャー三和音（左 C5+E5、右 E5+G5）。C1 と C5 の解析には、`RESET` の 1 行だけのログ（`reset.log`）を与える。スクリプトを何度か実行するときは、実行ごとにログ名を変える（同じ名前だと上書きされる）。

## 5. Resource ledger / 資源台帳

```
python3 hw/tools/resource_ledger.py build/quartus/output_files/DE10_Nano_wpms.fit.rpt --revision <RH> --md ledger.md
```
It prints the Core's ledger row (ALMs needed, entity-only, Comb. ALUTs) and the same columns plus M10K and DSP for every WPMS entity, read from *Fitter Resource Utilization by Entity*. It works with or without SignalTap; the SignalTap and JTAG-hub rows show its cost.

`resource_ledger.py` は Fitter の「Resource Utilization by Entity」表から、Core 形式の台帳行と、WPMS 各実体の ALM・M10K・DSP を書き出す。

## Revision history / 改訂履歴
- 2026-10-01 — first version (Phase 6). / 初版。
- 2026-10-03 — `report_setup_paths.tcl` and how to run it (§1; SD-22). / 失敗経路の集計スクリプトと実行方法（§1、SD-22）。
- 2026-10-03 — clk_sys's duty cycle per revision, `SYS_DUTY` and `--sys-duty` (§1; SD-23). / リビジョンごとの clk_sys デューティ比（§1、SD-23）。
- 2026-10-04 — §2: SW[1:0] = 11 (G = 12). The first version said 00, which is wrong: every expected value assumes G = 12. / §2：SW[1:0] は 11（G = 12）。初版の 00 は誤りで、期待値はすべて G = 12 を前提とする。
- 2026-10-04 — `wpms_tap.stp` committed and enabled by the generator (§3); SD-23 adopted (§1); the host script's session defect and its fix (§4). / `wpms_tap.stp` を収め、生成器で有効化（§3）。SD-23 正式採用（§1）。ホストスクリプトのセッションの不具合と修正（§4）。
- 2026-10-04 — `wpms_tap.stp`: the stored acquisition (a C5 trial) removed at the architect's word; the setup is unchanged. §3: if the VCD export fails, send the saved `.stp` (`stp_log_to_vcd.py`). / `wpms_tap.stp` から取得データ（C5 の試行）を削除。設定は不変。§3：VCD エクスポートが失敗したら、保存した `.stp` を送る。
- 2026-10-04 — §4: `reset.log` for C1 and C5; a log name per run; PowerShell's UTF-16 logs (after the first captures). / §4：C1・C5 の `reset.log`、実行ごとのログ名、PowerShell の UTF-16 ログ。
- 2026-10-04 — §3: the storage qualifier's port is the node `tap_ctl[100]`, chosen with the Node Finder; C3's `.stp` held it as a pin. / §3：ストレージ・クオリファイアのポートは Node Finder で選ぶノード `tap_ctl[100]`（C3 ではピン扱いだった）。
