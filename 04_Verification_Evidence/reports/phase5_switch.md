# Phase 5 — Minimal input switch / 最小の入力スイッチ

*CC0 · 2026-09-30 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 5, with the rulings of 2026-09-30 (the host path: ISSP over JTAG). Stops here, as the brief asks.*

*Verdict: **done and green.** `hw/switch/` holds the minimal input switch of the customer's Ch.5 for one module:*

- *the host on port 0, reached through **ISSP over JTAG** as the architect ruled — the ISSP bits OR-connected with the deterministic controller the testbench uses;*
- *the built-in ROM on port 3, with the test origin after reset, on KEY[1] and on TEST_ORIGIN — N = 1,008 at 50 MHz (SD-17 (a)), 2,048 at 100 MHz;*
- *stage-arm-go with freezing, GO / GO_ALL / go-now / KEY[0], the checks of PR-1, PR-2 and the sum of N before a GO fires, an **atomic hand-over** to the Formation (RH004), APPLIED_SEQ and APPLIED_SAMPLE;*
- *the whole address map of Ch.5 §5.6 for one module, Ch.4's knobs included.*

*From the Quartus editor, inbox slots, masks, RT.OUT, the sweep word, ARM and GO can all be read and written by hand.*

*Where it was checked — fifteen system runs on the real 48 kHz grid at both clock budgets (RTL-SIM), with the host driven through the very bits the ISSP drives:*

- ***17,679 transactions** (1,630 refused), every answer equal to a model of Ch.5's semantics;*
- ***6,664 writes** to the Formation's inbox port, identical in clock, address and data;*
- ***4,209 bundles and 2,378 output samples**, bit-exact against `sweep_sim.Reference` and the customer's oracle;*
- ***960 GOs**, each playing from the second strobe after its acceptance (Ch.5 §5.4.3);*
- ***22/22 mutants** killed;*
- *the music script of the Phase 6 demo played in simulation, step for step.*

*Found and fixed on the way:*

- *a GO accepted in the clock before a strobe could miss it and play one period late (RH004; SD-21);*
- *a latent checker bug of Phase 4 (§4.2), which does not affect the RTL.*

*The ADV7513 table now agrees with the programming guide's pages: 0x0C[7] is set to the guide's default, and four fields remain for the board.*

*Evidence class: **RTL-SIM**; resources ESTIMATE. The vendor branches (ISSP, ISMCE) and the Tcl host script against Quartus run only in Phase 6; the Tcl already ran here under tclsh, against stand-ins of the ISSP commands.*

*判定: **完了・緑。** `hw/switch/` は顧客第 5 章の最小入力スイッチ（1 モジュール）である。*

- *ポート 0 はホストで、裁定どおり **JTAG 経由の ISSP**。ISSP のビットは試験台の決定論的コントローラと OR 接続している。*
- *ポート 3 は内蔵 ROM。リセット後・KEY[1]・TEST_ORIGIN でテスト原点を鳴らす（50 MHz は N = 1,008、100 MHz は 2,048）。*
- *置く・構える・放つ（凍結、GO／GO_ALL／go-now／KEY[0]、GO 前の PR-1・PR-2・Σ N 検査、Formation への**不可分な引渡し** RH004、APPLIED_SEQ／APPLIED_SAMPLE）を備える。*
- *第 5 章 §5.6 のアドレスマップを 1 モジュール分すべて持つ。*

*Quartus のエディタから、inbox スロット・マスク・RT.OUT・掃引語・ARM・GO を手で読み書きできる。*

*検証は、両クロック予算・実際の 48 kHz グリッドでのシステム実行 15 本（RTL-SIM）。ホストは ISSP と同じビットで駆動した。*

- *17,679 トランザクション（拒否 1,630）がすべて模型と一致。*
- *inbox 口への書込み 6,664 件がクロック・番地・データまで一致。*
- *バンドル 4,209・出力サンプル 2,378 がオラクルとビット一致。*
- *GO 960 件はすべて受理後 2 番目のストローブから鳴った。*
- *変異体は 22/22 捕捉。*
- *Phase 6 の演奏スクリプトもシミュレーションで一手ずつ再生した。*

*途中で見つけて直したもの:*

- *ストローブ直前に受理された GO が 1 周期遅れうる件（RH004、SD-21）。*
- *Phase 4 の検査器の潜在バグ（RTL には影響なし）。*

*ADV7513 の設定表はガイドの頁と一致した（0x0C[7] をガイドの初期値に、未確認は 4 フィールドのみ）。*

*証拠クラスは RTL-SIM（資源は概算）。ベンダー分岐（ISSP・ISMCE）と Quartus に対する Tcl は Phase 6 で走らせる。Tcl はここで tclsh と ISSP コマンドの代役に対して走らせ済み。*

---

## 0. Rulings applied (2026-09-30) / 適用した裁定

| Ruling | How Phase 5 applies it |
|---|---|
| (1) SD-17 (a): the 50 MHz test origin with N = 1,008 | `hw/tools/gen_switch_rom.py` writes two ROM images from Ch.3 §3.10's integers (computed with the customer oracle's own formula and checked against the printed values): `wpms_rom_origin_1008` (50 MHz) and `wpms_rom_origin_2048` (100 MHz). Both play after reset (§3.3) |
| (2) SD-16: the published sin realization is the official specification; prepare the note for the customer | `reports/customer_note_sd16_sin.md` — findings, the exact realization, the proposed Ch.2 v1.2 edits, the offer of a bit-exact sine for the oracle. Prepared, not sent: the customer's repository is outside this session's scope |
| (3) ADV7513: the architect supplied the documents | the data sheet (Rev. B) and extracts of the Programming Guide Rev. B (pp. 14, 16–20, 25–27, 32–34, 56, 58–62, 69–101 and the contents). Every value of the table agrees with the pages. One field is corrected to the guide's default (0x0C[7], RH002 of the configurator), and four fields stay unconfirmed (§3.10) |
| (4) Phase 4 §4.4 choices all approved | recorded; nothing to change |
| (5) The second module after the Phase 6 silicon run succeeds | M = 1 throughout; the map's module region is module 0 only |
| (6) **The host path is ISSP over JTAG**, with a deterministic controller for white-box verification whose bits the ISSP bits are **OR-connected** to; inbox slots, masks, RT.OUT, the sweep word, ARM and GO read and written from the Quartus GUI; the simplest, most robust JTAG debug interface | `hw/switch/wpms_host_bridge.v` + the ISSP instance HOST (48 source bits, 36 probe bits): a flipped toggle makes one addressable transaction of Ch.5 §5.6's map. `wpms_system.v` ORs the HOST sources with `host_src_ext`, the port the testbench's deterministic controller drives with the same bit protocol (0 on the board). The whole map — every slot, mask, RT.OUT, SWEEP, SWEEP_COMMIT, GO, APPLIED_SEQ/SAMPLE and Ch.4's knobs — is reachable by hand (`hw/tools/host/README.md`). Discrepancy with Ch.5 §5.7's wording: SD-19 |

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `hw/switch/wpms_switch.v` | The switch of Ch.5 §5.4–§5.8 for one module (540 lines). **Port 0** is the host; **port 3** is the built-in ROM (ports 1 and 2 are not built). It carries the whole §5.6 map (global region; module 0 at 0x200). **Stage-arm-go:** frozen from arm until applied; GO, GO_ALL, go-now, KEY[0]. **The check before a GO fires** (PR-1, PR-2, §5.4.4) — the sweep word then in effect must have P ≤ 8, no block twice among its first P entries, every listed block's N in [N_MIN, NMAX], and the sum of those N ≤ NMAX. A refused GO disarms its items. **The hand-over** of the fired set to the Formation in one clock; a mirror of the Formation's flags and of its take; **the apply step** at inbox_taken (CR5-I3). APPLIED_SEQ, APPLIED_SAMPLE, the SAMPLE counter, REJECT[0/3], the ROM player |
| `hw/switch/wpms_host_bridge.v` | The ISSP host path (the ruling). Source {RD, WR, ADDR[11:0], WDATA[31:0]}, probe {REJ, RD_ACK, WR_ACK, RDATA[31:0]}. Every bit passes two flip-flops, and a toggle seen changed waits 4 more clocks before the fields are taken. A write is followed by a read-back. RDATA and REJ are stable 2 clocks before the acknowledge moves. At reset the acknowledges take the toggles' values (no replay) |
| `hw/switch/wpms_issp.v` | One ISSP instance: Intel `altsource_probe` (`VENDOR "INTEL"`; instance IDs HOST, STAT, INSP), or sources = 0 in simulation |
| `hw/switch/wpms_rom.v` | The ROM: 256 × 44 ({address, data}; address 0xFFF ends the list). `SIM` ($readmemh) or `M10K` (altsyncram, run-time modifiable: ISMCE instance TORG, Ch.5 §5.7) |
| `hw/switch/wpms_rom_origin_{1008,2048}.{hex,mif}` | Generated (`hw/tools/gen_switch_rom.py`). Do not edit |
| `hw/switch/wpms_key_pulse.v` | KEY[1:0]: two flip-flops, a debouncer (10 ms at 50 MHz), one pulse per press |
| `hw/switch/wpms_system.v` | Everything of the sound and its control that does not depend on the board. It holds the switch, the bridge, three ISSP instances (HOST; STAT, 128 live probe bits; INSP, the inspector) and `hw/l1/wpms_synth_top.v`. DIP[1:0] and DIP[3] come through two flip-flops. **The OR** of the ruling lives here |
| `hw/switch/wpms_system_tb.v` | The system bench and **the deterministic controller**. It drives `host_src_ext` with the ISSP bit protocol: set the fields, flip WR or RD, wait for the acknowledge. Skew *m* > 0 moves the toggle *m* clocks before the fields. Also: resets with the toggles set, KEY presses, DIP changes, waits placed against the strobe. It logs every switch transaction, apply step, inbox-port write, strobe, knob set, bundle and sample |
| `hw/switch/run_phase5.sh` | The Phase 5 recipe |
| `hw/l2/wpms_formation.v` **RH004** | **(a)** Inbox-port address 0x9F: the nine armed flags written in one clock (the atomic hand-over). **(b)** The take-set latched at the strobe includes an arm write presented in the strobe's own clock (§4.1, SD-21). The per-item arm bits of 0x88–0x8F and 0x91 are unchanged |
| `hw/l1/wpms_adv7513_cfg.v` **RH002** | 0x0C = 0x84: the guide's default for bit 7. Every entry is marked with the guide's page that confirms it, `[G nn]`; four fields stay `[R]` (§3.10) |
| `hw/tools/switch_model.py` | The switch's semantics, from Ch.5's text and the choices of §4.4, at transaction level (not from the RTL) |
| `hw/tools/cosim_switch.py` | The system cosimulation. Cases: origin, music (the host script's own steps), reject, timing, bridge, random, evidence. It checks every transaction and every inbox-port write against the model, the host path against the commands, the ROM's plays, the knobs at each strobe, every bundle and every sample against `sweep_sim.Reference` → `l1_model.py` (the customer's oracle), and the GO latency |
| `hw/tools/cosim_switch_mutants.py` | 22 mutants: one defect each, in the switch, the bridge, the system top or the Formation's RH004 |
| `hw/tools/gen_switch_rom.py` | The ROM images (`--check` regenerates and compares) |
| `hw/tools/cosim_synth.py` **RH002** | Fix of a latent checker bug found in Phase 5 (§4.2); no RTL is affected |
| `hw/tools/host/` (**outside WPMS**) | A stand-in for the Layer 4 controller. `wpms_issp_host.tcl` holds the quartus_stp procedures for the HOST instance. `wpms_music.py` writes `wpms_music_demo.tcl` (a C-major triad, a retune to F major, a decay, a bass, a fade, the test origin again); the same steps run in RTL-SIM (`--case music`). The README holds the by-hand protocol for the Quartus editor. `check_host_tcl.py` runs both Tcl scripts under tclsh against `issp_standin.tcl`, stand-ins of the Quartus ISSP commands that answer with the bridge's protocol (§3.7) |
| `reports/customer_note_sd16_sin.md` | The note for the customer team (ruling (2)) |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

```
# the recorded Phase 5 run (Icarus Verilog 12.0, Python 3.11.15, tclsh 8.6.14), 2026-09-30T14:16:21Z
REGRESSION=0 03_Sample_Implementations/hw/switch/run_phase5.sh 04_Verification_Evidence/rtl_sim/2026-09-30_phase5_switch
  [PASS] ROM images wpms_rom_origin_{1008,2048}.{hex,mif} regenerate identically (Ch.3 §3.10, Ch.5 §5.8)
  iverilog -Wall: 16 lines, 0 from hw/switch
  [PASS] cosim_switch: the switch, the host path, the ROM and the sound agree with the models in every run
  check_host_tcl: PASS
  cosim_switch_mutants: 22/22 mutants killed
  ESTIMATE wpms_switch: $lut 2938; MISTRAL_ALUT_ARITH 667; MISTRAL_FF 1275; MISTRAL_M10K 3;
  cosim_switch evidence: PASS (1 s)
run_phase5: ALL PHASE 5 CHECKS PASSED
# the third recording of the recipe: the first two (13:51:41Z and 14:11:45Z), before the check of the
# host scripts was added and then extended with its mutants, gave the same results line for line

# the regression, on the same tree (the Formation's RH004, the ADV7513 table's RH002, the checkers' fix),
# started 2026-09-30T13:40:36Z
03_Sample_Implementations/hw/l1/run_phase4.sh        (REGRESSION=1: Phase 3's recipe, which runs Phase 2's)
  run_phase2: ALL PHASE 2 CHECKS PASSED
  run_phase3: ALL PHASE 3 CHECKS PASSED
run_phase4: ALL PHASE 4 CHECKS PASSED
```

Logs: `04_Verification_Evidence/rtl_sim/2026-09-30_phase5_switch/logs/` (`run_phase5.txt`, `cosim_switch.txt` — fifteen runs in full, `check_host_tcl.txt`, `cosim_switch_mutants.log`, `yosys_stat.txt`, the regression's `phase{2,3,4}_regression.txt`); the VCD of a short run (reset, the ROM, one host GO): `phase5_host_go.vcd.gz`; `observation.md` (expected before observed).

## 3. Results, with evidence classes / 結果と証拠クラス

All numbers are **RTL-SIM** unless marked. The fifteen recorded runs:
- 50 MHz budget (NMAX 1,008, T_min 1,041): origin, music, reject, timing, bridge, random seeds 1–3;
- 100 MHz budget (NMAX 2,048, T_min 2,083): the same five cases and random seed 4;
- the origin with a test ROM image.

**3.1 The switch against its model.** Every transaction the RTL executed was replayed, in clock order, through `switch_model.py`: 17,679 transactions (16,229 on port 0, 1,450 on port 3), 1,630 of them refused. Every answer — the word read, refused or not — was **equal**. The writes the switch presented to the Formation's inbox port were **identical** to the model's list, in clock, address and data: 6,664 writes, including 966 hand-overs whose GO_SEQ side band is identical too. The knobs the output stage saw at every strobe (MG_TARGET, MG_RATE, G_CTRL, MUTE) were those the model holds.

**3.2 The host path.** Every command of the deterministic controller became exactly one port-0 transaction with the same fields, and every probe answer was that transaction's: 7,348 writes (each followed by its read-back), 1,430 reads and 103 KEY[0] presses, 16,229 transactions in all, nothing else on port 0. The bridge case adds:
- skew of 1, 2 and 3 clocks (the toggle before the fields: worse than the ISSP, which moves its bits together);
- three design resets with the WR toggle, the RD toggle and both set, after which nothing was replayed;
- writes and reads back to back without pauses.

**3.3 The ROM and the test origin.** 69 complete plays of the ROM's 21 writes: after 21 resets, 46 KEY[1] presses and 2 TEST_ORIGIN writes.
- Played from the ROM, the test origin sounds bit-exact. Its peak is 2,002,439 = **−12.44 dBFS** (N = 1,008, 50 MHz) and 4,068,448 = **−6.29 dBFS** (N = 2,048, 100 MHz), the Phase 4 figures.
- After reset the host reads GO_SEQ = APPLIED_SEQ = 1, **APPLIED_SAMPLE = 2** (the second sweep after reset is the first to play the ROM's GO), SWEEP_ACTIVE = {P = 1, order 0} and CONFIG = 0x0003F081.
- The test image's own TEST_ORIGIN write was refused (C-7).
- In the random runs, 178 ROM writes were refused because the host held block 0 or the sweep word armed (C-8).

**3.4 Stage-arm-go on the clock (Ch.5 §5.4.3; RH004).** Each of the **960 GOs** measured played from the **second strobe after its acceptance**:

| Budget | GOs | Acceptance → the first sweep playing it |
|---|---|---|
| 50 MHz | 704 | 1,043 … 2,084 clocks = 1.0013 … 2.0006 periods |
| 100 MHz | 256 | 2,084 … 4,167 clocks = 1.0003 … 2.0002 periods |

The excess over 2.000 periods is the strobe's own quantization: intervals of 1,041/1,042 clocks for a period of 1,041.67.

The timing case put hand-overs at every offset from −2 to +3 clocks around a strobe (50 MHz) and from −3 to +3 (100 MHz), in the strobe clock itself included. All 62 takes were **heard**, and 1,188 and 1,195 bundles were equal. So the one-sample landing and the exactly-once rule hold at the edge (§4.1 for what the edge found).

The apply step ran 2 clocks after inbox_taken rose, and its write landed **22 clocks or more** before the next strobe. That margin is the timing assumption of the apply path; the simulation-only assertion never fired.

**3.5 Refusals.** The refusal case makes 28 refusals, each answered as the model says:
- 6 frozen-while-armed writes: two slots, RTOUT, COMMIT, SWEEP, SWEEP_COMMIT;
- 4 PR-2 GOs: N = 31, NMAX + 1, 0 and 0x80000020;
- one GO whose sum of N exceeds NMAX;
- one PR-1 sweep word (a block twice);
- P = 9;
- a block whose N was never written (C-4);
- 14 writes to read-only, reserved or unmapped words.

Nothing refused reached the page (the sound stays bit-exact), and the legal GOs after them play. REJECT[0] counted them and cleared by write-1.

**3.6 Random traffic.** Four runs, with anything a writer may do in any order:
- slots with valid and invalid N;
- masks, arms and go-nows;
- sweep words with repeats and P up to 15;
- GO and GO_ALL;
- reads of the whole map;
- knob writes, skewed toggles, KEY[0] and KEY[1].

In all: 13,898 transactions, 1,573 refused, 807 GOs, 1,118 samples, all bit-exact. This is where the checker bug of §4.2 showed itself.

**3.7 The music script (outside WPMS).** `hw/tools/host/wpms_music.py`'s steps are the Phase 6 demo: 91 writes and 7 reads, 6 GOs (a triad, a retune, a go-now decay, a GO_ALL with a bass, the ROM again through TEST_ORIGIN). In RTL-SIM they played at both budgets without a refusal, and GO_SEQ = APPLIED_SEQ = 6 at the end.

The Tcl the script writes for the board also ran here, under tclsh 8.6 against stand-ins of the Quartus ISSP commands (`check_host_tcl.py`; a check of the scripts — not Quartus, not the RTL):
- it made exactly the transactions of those steps, in order: each write with its fields, each read, each wait as reads of GO_SEQ, polls of APPLIED_SEQ and a read of APPLIED_SAMPLE;
- the same held with acknowledges three probe reads late, answers in lower case without leading zeros, and a source left by an earlier session with both toggles set;
- a refused write is reported (REFUSED; `wpms_w` returns 1) and the script goes on; a missing acknowledge ends in an error, not a hang; `wpms_status` reads its eleven words.

Eight broken copies of `wpms_issp_host.tcl` (no wait for the acknowledge, a check of one acknowledge only, no padding of the probe, the HPS instead of the FPGA, REJ ignored, the source's state not read at open, a short address mask, no poll of APPLIED_SEQ) were each caught.

**3.8 Mutants.** **22/22 killed.**
- The switch (hand-over contents, GO scoping, freezing, the three checks, APPLIED, apply scope, reads, knobs, the ROM's end and self-restart).
- The bridge (no settling, a reset that forgets the toggles).
- The Formation's RH004 (undoing the strobe-clock take).

In the first mutant run five mutants survived. None of them pointed at the RTL: each showed a scenario that did not test what it meant to, and those scenarios were fixed (§4.3).

**3.9 Regression.** The Phase 4 recipe, which runs Phase 3's, which runs Phase 2's, was re-run on this tree — the Formation's RH004, the ADV7513 table's RH002 and the checkers' fix — with Phase 4's own sample count (3,000 per seed). All three passed (RTL-SIM): **ALL PHASE 2 CHECKS PASSED**, **ALL PHASE 3 CHECKS PASSED**, **ALL PHASE 4 CHECKS PASSED** (14 checks of Phase 4 itself, the first being the Phase 3 recipe). So everything Phases 2–4 check still holds with RH004: the datapath against the golden model with its mutants, the sweep-level cosimulation of the R1 score at both budgets with its error injection, the L1 and the output path bit-exact against the customer's oracle and the published model, and the ADV7513 configurator's bench with the corrected table. Logs: `phase{2,3,4}_regression.txt`, `phase4_adv7513_tb.log`, `phase4_cosim_synth_grid.txt`.

**3.10 The ADV7513 table against the guide (reading; the architect's extracts of the Programming Guide Rev. B).**

| Group | Entries |
|---|---|
| Checked against the guide's pages | Power-up and the fixed registers (0x41[6], 0x98, 0x9A, 0x9C, 0x9D[1:0], 0xA2, 0xA3, 0xE0, 0xF9: p. 14, 25). The video input and output (0x15[3:0], 0x16, 0x17[1], 0x18: p. 14, 27, 34, 56). HDMI mode and packets (0xAF[1], 0x40[7]: p. 18–19). The AVI InfoFrame (0x55, 0x56: p. 60–61). The interrupts (0x94, 0x96 [7:6]: p. 17). The whole audio half: N = 6144 (Table 60), 0x0A, 0x0C[6:0], 0x0D, 0x14, 0x15[7:4], 0x73, 0x76 (p. 69–88) |
| Relied on at their defaults, confirmed | 0x0B (I2S latched on SCLK's rising edge; MCLK made inside), 0x44[6,5,3], 0x4A[7], 0x0E, 0x12, 0x13 |
| **Corrected** | 0x0C = 0x84: bit 7 back to its default 1 — the sampling frequency for pixel repetition comes from 0x15. The recalled 0 selected the stream's, which standard I2S does not carry (p. 71–72) |
| Still unconfirmed `[R]` | 0x41[4], 0x9D[7:4], 0xAF[2], 0xBA[7:5] (video capture clock delay: the picture only). Phase 6 reads them back |
| From the data sheet | SCL ≤ 400 kHz: ours 97.6 kHz, with one 30 µs clock stretch honoured (RTL-SIM, the configurator's bench). Start/stop setup and hold ≥ 0.6 µs and SDA setup/hold ≥ 100 ns: ours are quarter periods of 2.5 µs (reading of the bit engine). I2S data is latched on the rising edge of SCLK, as our master drives it |

The configurator's bench passes with the new table (RTL-SIM).

## 4. Deviations and findings / 逸脱と発見

**4.1 Found and fixed: a GO accepted in the clock before a strobe missed it** (SD-21; Formation RH004 (b)).

- **How it was found.** The timing case places hand-overs at every offset from −3 to +3 clocks around a strobe. With the hand-over a registered write, presented in the clock after the GO's acceptance, a GO accepted in the last clock before a strobe had its hand-over presented *in* the strobe clock. The Formation latched its take from the flags as they stood at the start of that clock, so the GO waited for the next strobe and played from the third: 2 periods + 1 clock (2,085 clocks at 50 MHz). That is against Ch.5 §5.4.3's "≤ 2 sample periods".
- **The fix** (in the Formation, RH004 (b)). The take-set includes an arm write presented in the strobe's own clock. The switch's mirror follows the same rule. Now a GO is taken by the first strobe after its acceptance and plays from the second, whatever the clock (§3.4).
- **Collateral.** An apply step whose write lands in a strobe clock is also seen by that strobe.
- **Regression.** Phases 2–4 were re-run on RH004: green (§3.9).

**4.2 Found in a checker, not the RTL:** Phase 4's `cosim_synth.reference_packets` took N after `sweep_sim.Reference` had applied the strobe's GO.

- **Effect.** A GO that changes N of a block playing in that very sweep would be modelled with the new N.
- **Why it was latent.** No Phase 4 case changes N of a playing block, so the Phase 4 results stand.
- **How it was found.** Phase 5's random traffic does change N of playing blocks, and the RTL was right: one sample of seed 3 at 50 MHz disagreed with the checker until the checker was fixed.
- **Fixed** in both checkers (`cosim_synth.py` RH002; `cosim_switch.py` from the start of its recorded runs).

**4.3 Not as first expected (all found before the recorded run) / 事前の予想と異なった点**

- **Scenarios that did not test what they meant to.** At 50 MHz, block 0 of the test origin fills NMAX (1,008) by itself.
  - Three first drafts listed block 0 together with other blocks, so their GOs were rightly refused (Σ N > NMAX): the refusal case, the timing case and the bridge's KEY[0] test.
  - In the timing draft, every later retune then went to blocks that never played. The model and the RTL agreed, but the sound check could not see those GOs. The mutants exposed this (W10 survived).
  - The scenarios now list blocks 1–4. The checker reports how many takes are *heard* (a block of the take plays in the next sweep) and requires all of them in the timing case.
- **Other test-side defects the mutants found.**
  - A "frozen slot" write went to 0x201 (block 0's TAG) instead of 0x211 (W3).
  - A knob mutant was masked by the music script's order of writes (W21; now caught by the random case, which also reads the knob words).
- **The hazard assertion was too strict.** The model's (and the RTL's simulation-only) check "a strobe meets items already copied still armed" also fired when an item had been applied and then lawfully fired again, two clocks later. The check now applies only while the take's apply step is still pending.
- **The ROM hex file** first held only the list; Icarus warned about the short `$readmemh`. The generator now writes the whole depth.
- **Yosys found an inferred latch** (a loop variable of the GO check), harmless in simulation. It now has a default.

**4.4 Choices where the texts are silent (published in the model; please confirm) / 文書が沈黙する箇所の選択**

| # | Item | Choice | Texts |
|---|---|---|---|
| C-1 | A GO that fails its check | refused and counted; the items it would have fired are **disarmed** (back to staged), so the writer can correct and re-arm them; GO_SEQ unchanged | §5.4.4 "rejects", W v0.7 PR-1/PR-2 |
| C-2 | When the checks are made | when a GO fires (GO, GO_ALL, KEY[0], go-now), against the state every earlier GO leaves; arming is not checked | §5.4.4 "when it can compute it" |
| C-3 | PR-2's range | the build's [N_MIN, NMAX] (EW2's own): [32, 1,008] at 50 MHz — not PR-2's literal "[32, 2,048]" | W v0.7 PR-2; ruling of 2026-09-29 (NMAX) |
| C-4 | N after a design reset | unknown (0) until written through the switch: a sweep word may list a block only after its N has been written since reset (the store keeps its contents across a reset; the switch does not guess them) | Map v0.3 §9 ("contents undefined") |
| C-5 | Writes to read-only, reserved (+0xD, +0xE of a block) or unmapped words | refused and counted in REJECT[port], so a mis-aimed write is visible | §5.5.2 ("visible rather than silent") |
| C-6 | OWNER | stored and read back, **not enforced**; a change of owner disarms nothing (only the privileged ports 0 and 3 exist) | §5.5.2; SD-20 |
| C-7 | KEY[0], TEST_ORIGIN, KEY[1] | KEY[0] is a GO_ALL on port 0. TEST_ORIGIN is honoured from port 0 and refused from port 3 (the ROM cannot restart itself). KEY[1] or TEST_ORIGIN while the ROM plays is ignored | §5.8 |
| C-8 | The ROM against the host's arms | the ROM's writes follow the same rules as any writer's. If the host has armed block 0 or the sweep word, the ROM's writes to them are refused (REJECT[3]) and its GO_ALL also fires the host's armed items. After a reset nothing is armed, so the replay after reset is always whole | §5.8 |
| C-9 | The sample counter n | strobes since reset; the sweep a strobe starts bears its count (the first sweep after reset is n = 1). APPLIED_SAMPLE = n of the first sweep playing the GO. Reading SAMPLE_LO latches SAMPLE_HI | §5.6.1 |
| C-10 | A GO with nothing armed | accepted, counted in GO_SEQ, and published in APPLIED_SEQ at the next take like any other; a GO word with bits 1:0 = 00 does nothing | §5.4.2 |
| C-11 | COMMIT[b] and SWEEP_COMMIT as read | [16:0] the pending mask; [30] armed, from arm until applied | §5.6.2 "R: pending mask, armed" |
| C-12 | INSPECT_L | the L1's 54-bit Q.30 level >> 4, saturated to Q6.26 | §5.6.1 (format not given) |
| C-13 | CONFIG, VERSION | CONFIG [31:24] = 0 (N_MIN not exposed; PR-2's option left open); VERSION = 0x0001_0000 (Ch.5 v1.0) | §5.6.1 |
| C-14 | Clearing | REJECT[p] write-1-to-clear by bit; STROBE_MINMAX and SWEEP_CLOCKS_MAX cleared by any write; CLIP write-1-to-clear per bit | §5.6.1 |
| C-15 | INBOX[b][0xD], [0xE] | read 0; writes refused | §5.4.2 (mask bits 13 and 14 ignored) |

**4.5 What is not built or not run here / 作っていないもの・ここでは走らせていないもの**

- **Not built.** Ports 1 (camera) and 2 (HPS); ownership enforcement (SD-20); the second module.
- **Not run here — Quartus is absent.** These are checked in Phase 6:
  - the vendor branches: `altsource_probe` for ISSP, `altsyncram` with run-time modification for the ROM (compiled only by Quartus);
  - an ISMCE edit of the ROM;
  - the Tcl host script against Quartus itself (under tclsh against stand-ins it passed, §3.7).

  Until then the vendor branches are *reading*, and the Tcl's use of the Quartus commands is as the stand-ins model them. What the host sends is RTL-SIM-checked through the identical bit protocol.
- **Phase 6 notes.**
  - The ISSP sources change in the JTAG clock domain: the SDC must cut `altera_reserved_tck` from clk_sys (the bridge synchronizes).
  - The STAT/INSP probes are sampled asynchronously: display only.

## 5. Discrepancies filed / 記録した食い違い

Filed in `reports/discrepancies.md`, not fixed:

| ID | Item | State |
|---|---|---|
| SD-19 | The host path: Ch.5 §5.7 / C5-D8 say ISSP is not the write path; the ruling of 2026-09-30 makes ISSP the transport of port 0 (realized as addressable transactions, so the map is unchanged) | ruled (architect) · open with the customer (wording) |
| SD-20 | The ROM's list against the ownership rules of §5.5.2 (the ROM cannot write port 0's blocks, and setting "all owners = port 0" before its GO_ALL would disarm its own items) | open (customer); no effect with ports 0 and 3 |
| SD-21 | "Armed" means two things (Ch.5: before GO; Map v0.3 §7: handed over); the strobe-clock hand-over (RH004 (b)) | open (wording); realized |

Rulings of 2026-09-30 recorded on earlier rows: **SD-16** (the sin realization is the official specification; the customer note is prepared) and **SD-17 (a)** (N = 1,008 at 50 MHz; closed). / 2026-09-30 の裁定を SD-16・SD-17 に記録した。

## 6. Questions for the architect / アーキテクトへの質問

1. **RH004 in the Formation (SD-21).** Phase 5 changed the profile's L2 Formation in two ways: an arm-vector write (the atomic hand-over), and a take-set that includes an arm write presented in the strobe's own clock (without it a GO could play from the third strobe). May both stand? And may Map v0.3 §7's "armed at that moment" read "handed over (fired) at that moment, a hand-over in the strobe's own clock included" at its next version? / RH004（引渡しベクトルとストローブ同クロックの取込み）を認めてよいか。Map v0.3 §7 の文言を次版で改めてよいか。
2. **SD-19, the host path.** The ISSP instance HOST carries addressable port-0 transactions (ADDR, WDATA and two toggles), so every word of the map is reachable by hand. Is that the manual interface you intended, or would you prefer named fields (for example one ISSP instance per item)? And may the customer be told that §5.7 / C5-D8 should admit ISSP as a transport of port 0? / ISSP でアドレス付きトランザクションを運ぶ形でよいか。項目ごとの専用フィールドの方がよいか。顧客へ §5.7 の文言について伝えてよいか。
3. **SD-20, the ROM and ownership.** The proposal: port 3 is exempt from ownership for its own list. Until ports 1 or 2 exist, OWNER is stored but not enforced. / ROM（ポート 3）を所有規則の適用外とする案でよいか。
4. **§4.4's choices.** Please confirm them, or rule otherwise. Two may matter on the bench. C-1: a refused GO disarms its items. C-8: KEY[1] does not override the host's arms; the replay after a reset is always whole, but KEY[1] pressed while the host holds block 0 or the sweep word armed replays only in part (REJECT[3] shows it). Should KEY[1] first disarm everything that is armed and not yet fired? / §4.4 の選択の確認。特に C-1 と C-8（KEY[1] で先に構えを解くべきか）。
5. **Phase 6.** May Phase 6 begin? It covers: the board top from the Core's DE10-nano harness; PLLs for 50 MHz, MCLK 12.288 MHz and the 74.25 MHz video clock; the reset from DIP[2]; the SDC with the JTAG clock group; SignalTap captures; first sound from the ROM, then the music script. / Phase 6 に進んでよいか。

## 7. Resource numbers (ESTIMATE, Yosys `synth_intel_alm` for Cyclone V; not Quartus) / 資源数（概算）

| Entity | 6-LUT | ALUT arith | FF | M10K | DSP |
|---|---|---|---|---|---|
| `wpms_switch` (incl. the ROM and the inbox shadow) | 2,938 | 667 | 1,275 | 3 | 0 |
| `wpms_host_bridge` | 28 | 4 | 186 | 0 | 0 |
| `wpms_key_pulse` (× 2) | 9 | 19 | 23 | 0 | 0 |

Notes on the table:
- The ISSP instances (HOST 48 + 36 bits, STAT 128, INSP 96) and the JTAG hub are vendor IP, not estimated here: Quartus reports them in Phase 6.
- The switch's LUTs go mostly to the read multiplexer over the map, the GO check (eight N selected by the sweep word, summed and compared), and the 32- and 64-bit counters. Together with the Phase 4 synthesizer (about 8k ALMs, 19 DSP, 5 M10K, ESTIMATE), this stays a small part of the DE10-nano's Cyclone V SE A6 (41,910 ALMs, 112 DSP blocks).
- Nothing on the switch is in the audio path's timing.

スイッチは LUT 約 2,900・FF 約 1,300・M10K 3（ROM が 44 ビット幅で 2 個、inbox の写し 1 個）、DSP なし（概算）。ISSP と JTAG ハブはベンダー IP で、Phase 6 の Quartus で数える。
