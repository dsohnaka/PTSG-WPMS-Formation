# WPMS host control GUI — V1 to V3, before the board / ホスト制御 GUI——実機前の検証 V1〜V3

*CC0 · 2026-10-14 · Claude Code for the architect, per `GUI_BRIEF_WPMS_Host_Control_2026-10-14` §5, §6 and §9. **OUTSIDE WPMS**: Layer 3 tooling, a stand-in for the Layer 4 controller. No RTL, no Layer 1 document, no golden model, and none of `wpms_issp_host.tcl`, `issp_standin.tcl`, `check_host_tcl.py`, `cosim_switch.py` was changed.*

*Verdict: **V1, V2 and V3 pass.** The bridge, the controller and the panel are built. Every expectation written below held. The board's part (§7: transaction times, update rates, REJECT[0] after a minute of knob turning, the sound) waits for the architect. **Stopped here for the architect**, as the brief says.*

*Evidence classes: **stand-in** (tclsh 8.6.14 against `issp_standin.tcl` and this test's freeze model: a check of the scripts, not of Quartus and not of the RTL) and **RTL-SIM** (Icarus Verilog 12.0, `-g2012`; the switch, the ISSP bridge and the synthesizer of `hw/switch/wpms_system.v`). No number here is SILICON. No ORACLE number is new.*

*判定：**V1・V2・V3 合格。** 橋・制御ロジック・パネルを作り、先に書いた期待値はすべて満たした。実機の部分（§7：トランザクション時間、更新速度、1 分間つまみを回した後の REJECT[0]、音）はアーキテクトを待つ。指示書どおり**ここで止まる**。証拠区分は stand-in（tclsh＋代役）と RTL-SIM（Icarus）。SILICON の数値はまだない。*

---

## 1. Files built / 作ったもの

All in `03_Sample_Implementations/hw/tools/host/gui/` (MIT; "OUTSIDE WPMS" and a revision history in every header):

| File | Lines | What |
|---|---|---|
| `wpms_bridge.tcl` | 209 | The resident bridge. `wpms_open` once; `socket -server` on 127.0.0.1 (default port 50707, `0` = any); one client at a time; `W` / `R` / `B n` / `PING` / `QUIT` / `SHUTDOWN`. It survives an ISSP error and sets its toggles back to the probe's acknowledges. It keeps the session open across clients. `--standin` sources `../issp_standin.tcl`. |
| `wpms_ctl.py` | 791 | The controller, standard library only. It holds the bridge client and the state (desired and sent), and uses the conversions of `wpms_music.py` (imported). It implements the coalescing law of §4 with the switch's GO check made locally, keeps the step log (JSON) and the times (CSV), and runs a sender thread. Command line: `ping`, `status`, `storm`, `measure` (the §7 measurements). |
| `wpms_gui.py` | 461 | The Tkinter panel of §3: Master, one tab per block, Status, Step log. |
| `test_gui_bridge.py` | 673 | V1 and V2, with nine mutants of the bridge. |
| `cosim_gui_replay.py` | 159 | V3: a step log through `wpms_system_tb.v` with `cosim_switch.py`'s `build`, `simulate` and `check`. |
| `README.md` | — | How to run (board, stand-in), the protocol, the panels, the law, the numbers; English first, then Japanese. |

Also changed: one row in `hw/tools/host/README.md` and in `hw/README.md` (pointing to `gui/`). Evidence: `04_Verification_Evidence/rtl_sim/2026-10-14_gui_v1_v3/` holds:

- `logs/`: the runs' outputs;
- `step_logs/`: the V2 step logs replayed in V3;
- `wpms_gui_standin.png`: the panel connected to the stand-ins, after a scripted knob storm under Xvfb.

## 2. Expected, written before the runs / 期待値（先に記す）

| # | Expected | From |
|---|---|---|
| X1 | Every request type answers as the protocol table of the brief §2 says; `<us>` is an integer | brief §2 |
| X2 | A batch with a refusal answers the refusal, then `SKIP` for the rest, and the stand-in never sees the skipped transactions | brief §2 |
| X3 | An ISSP error answers `ERR`; the next transaction is answered correctly | brief §2 |
| X4 | A lost client, a refused second client and a `QUIT` leave the session open: the stand-in's session is started once; `SHUTDOWN` closes it and the bridge exits 0 | brief §2 |
| X5 | The socket listens on 127.0.0.1 only | brief §2 |
| X6 | Each mutant of the bridge fails at least one case | brief §5 V1 |
| X7 | Knob storms on the controller: 0 refusals, REJECT[0] = 0, sent = desired at the end, every block served, each GO applied before the next one is sent | brief §4, §5 V2 |
| X8 | One knob moved at every step does not starve another block: it is served within two GOs of its change | brief §4 rule 4 |
| X9 | A controller that sends without waiting for the apply is refused (the check has teeth); its log fails V3 too | — |
| X10 | The V2 storm's step log replayed in RTL-SIM: every host write accepted, every GO applied within the bound (APPLIED_SEQ = GO_SEQ three strobes later), the switch's answers and the samples equal to the models | brief §5 V3; `cosim_switch.py --case music` |

## 3. Commands and their last lines / コマンドと最後の行

Run on 2026-10-14 (Python 3.13, tclsh 8.6.14, Icarus Verilog 12.0), from `hw/tools/host/gui/`:

```
python3 test_gui_bridge.py --report .../logs/test_gui_bridge.txt --logs .../step_logs
  mutants 9/9 broken copies of wpms_bridge.tcl caught
test_gui_bridge: PASS
python3 ../check_host_tcl.py --report .../logs/check_host_tcl.txt          (unchanged; still green)
check_host_tcl: PASS
python3 cosim_gui_replay.py .../step_logs/v2_storm.json --report .../logs/cosim_gui_replay_v2_storm.txt
cosim_gui_replay v2_storm: PASS (35 s)
python3 cosim_gui_replay.py .../step_logs/v2_thread.json --report .../logs/cosim_gui_replay_v2_thread.txt   (gzipped afterwards; the .gz replays as is)
cosim_gui_replay v2_thread: PASS (612 s)
python3 cosim_gui_replay.py .../step_logs/v2_teeth.json --report .../logs/cosim_gui_replay_v2_teeth.txt
cosim_gui_replay v2_teeth: FAIL (1 s)            (expected: FAIL)
```

### V1 — the bridge under tclsh (stand-in) / 橋（代役）

| Case | Result |
|---|---|
| ping | `PING` → `OK WPMS 57504D53 0003F081` |
| wr | `W 010 FFFFF000` → `OK FFFFF000 0 <us>`; `R 10` (hex without leading zeros) → `OK FFFFF000 <us>` |
| refuse | a write to a refused word → `OK … 1 <us>`; the next write goes on |
| batch | `B 4` with a refusal second → `OK`, `OK … 1`, `SKIP`, `SKIP`, `END <us>`; the stand-in's log at shutdown has neither skipped write; `B 3` executes all |
| errors | `HELLO`, `W 1234 5`, `R`, `B 0` → `ERR …`; then `PING` answers |
| issp | a transaction never acknowledged (the test's hook on word 0xFFE) → `ERR wpms: no acknowledge (addr 0xFFE)` after the timeout; then `R 000` → the ID, and a write goes on |
| clients | a client lost without `QUIT`, a second client while one is served (`ERR busy`), a `QUIT`: each next client is served; the stand-in's session started **once**, never ended |
| bind | listening on 127.0.0.1; a connection to this host's other address is refused |
| shutdown | `SHUTDOWN` → `BYE`, `end_insystem_source_probe` called, exit 0 |

**Mutants of `wpms_bridge.tcl`: 9 of 9 killed.**

| # | Mutant | Killed by |
|---|---|---|
| B1 | reply before the transaction (the previous answer) | wr, refuse, errors, issp |
| B2 | batch not stopped at a refusal | batch, shutdown |
| B3 | session re-opened per client | clients |
| B4 | port bound to 0.0.0.0 | bind |
| B5 | no resync after an ISSP error | issp |
| B6 | SHUTDOWN without `wpms_close` | shutdown |
| B7 | QUIT closes the session | clients |
| B8 | a lost client not forgotten | clients, bind, shutdown |
| B9 | an ISSP error not caught | issp, clients, bind, shutdown |

B1–B4 are the brief's four; B5–B9 are mine.

### V2 — the controller headless (stand-in + freeze model) / 制御ロジック（代役＋凍結モデル）

The stand-in's register file does not model freezing, so the test adds a **freeze model** in its own copy of the driver. It redefines the stand-in's `do_write` / `do_read` after sourcing it; `issp_standin.tcl` is not edited. The model follows `switch_model.py`'s rules for port 0:

- an armed or fired item refuses writes to its INBOX slots, its RTOUT and its COMMIT, or to SWEEP / SWEEP_COMMIT, until APPLIED_SEQ reaches its GO;
- slots 13 and 14 are always refused;
- GO, go-now and SWEEP_COMMIT go-now are checked as the switch checks them;
- a refused GO disarms its items;
- REJECT[0] counts.

The state starts as the ROM's test origin leaves it: block 0 with N = NMAX = 1,008 alone in the sweep. So the first ticks are refused by the panel until block 0's N shrinks: the panel had to find that order itself.

| Case | Result |
|---|---|
| storm | 400 random knob moves on blocks 0–3 (level, centre, spacing, width, glide, route, N, play, master), the sender stepping once between moves → **133 GOs** (15 sweep words), every block served, sent = desired at the end, each GO applied before the next; **REJECT[0] 0, refused 0, errors 0** |
| thread | the sender thread running; a "hand" moving knobs on blocks 0–5 every 0.5 ms for 3 s: 4,011 moves → 2,124 GOs; every block served; sent = desired; law kept; **REJECT[0] 0** |
| fair | block 1's level moved at every step; block 2 changed once → block 2 was the **next** GO (≤ 2 expected) |
| origin | `Test origin` in the middle: its GO (the ROM's GO_ALL) applied; the controller re-read the switch: sweep [0], N0 = 1,008; REJECT[0] 0 |
| teeth | a controller subclass that forgets the pending GO: refused by the freeze model (1 refusal before the controller's back-off); its log is kept for V3 |

### V3 — the step logs through the switch RTL (RTL-SIM) / ステップ記録を RTL で再生

`cosim_gui_replay.py` starts from a reset (the ROM's test origin) and turns each step into a command of the deterministic controller (`wpms_music.to_stim`: `APPLY` = 3 strobes, the bound + 1). It adds two reads after each `APPLY` (GO_SEQ, APPLIED_SEQ). `cosim_switch.check` then compares every transaction with `switch_model.py`, every inbox write, the ROM's plays, and every bundle and output sample with `sweep_sim.Reference` → `l1_model.py` over the customer's oracle.

| Log | Steps (W / R; APPLY) | Switch transactions = model's | Host writes refused by the RTL | APPLY with APPLIED_SEQ = GO_SEQ | GO → first sweep playing it | Samples = models | Verdict |
|---|---|---|---|---|---|---|---|
| `v2_storm.json` | 1,460 (909 / 684; 133) | 2,523 / 2,523 | **0** | 133 / 133 | strobe 2 (1.38 … 1.93 periods), 134 GOs | 407 / 407; 384 bundles | **PASS** |
| `v2_thread.json.gz` | 17,103 (8,530 / 10,697; 2,124) | 27,778 / 27,778 | **0** | 2,124 / 2,124 | strobe 2 (1.38 … 1.93 periods), 2,125 GOs | 6,380 / 6,380; 19,649 bundles | **PASS** |
| `v2_teeth.json` (must fail) | 93 (70 / 23; 0) | 184 / 184 | **1** (`W 23A` into block 3, frozen by its own go-now) | — | — | 10 / 10 | **FAIL, as expected** |

In each run the ROM played its 21 writes once after the reset, the inbox-port writes equalled the model's (clock, address, data), and the apply step came 2 clocks after inbox_taken. Each GO count includes the ROM's GO_ALL. The read counts include the two checks added after each APPLY.

Both storm logs replay clean: **every one of its writes is accepted by the switch RTL**, every GO plays from the second strobe after its acceptance, and the sound equals the models sample for sample. The teeth log fails exactly where it should: a write to a block still frozen by its own go-now, refused by the RTL (and by `switch_model.py`, whose answers equal the RTL's).

## 4. Evidence class per number / 数値の証拠区分

| Number | Class |
|---|---|
| V1 cases, the 9 mutants | stand-in (tclsh against `issp_standin.tcl`) |
| V2 GO counts, REJECT[0] = 0, fairness | stand-in + this test's freeze model |
| V3: refusals 0, APPLIED_SEQ = GO_SEQ after every APPLY, GO → play ≤ 2 strobes, samples equal | RTL-SIM |
| Transaction times under the stand-in (0.02 … 0.5 ms, shown in the GUI) | stand-in: this PC's TCP path and tclsh, **not** JTAG; not a measurement of anything on the board |
| §7 table (5 … 30 ms, 33 … 200 /s, 6 … 100 /s) | ESTIMATE, unchanged: waits for the board |

## 5. Deviations from the brief and from expectations / 指示書・期待値からの逸脱

1. **Batches also stop at an ISSP error**, not only at a refusal; the rest answer `SKIP`. A transaction after an unacknowledged one would run on toggles of unknown state.
2. **After an ISSP error the bridge sets its toggles back to the probe's acknowledges.** It does this with `wpms_probe` and one `write_source_data`, inside the bridge, not in `wpms_issp_host.tcl`. Without it, the next transaction answered stale data under the stand-in. Mutant B5 is that case.
3. **The bridge's replies leave in one write per request** (full buffering, one flush). With line buffering, a batch's reply lines waited behind the client's delayed acknowledge (Nagle): about 40 ms per batch, even under the stand-in. Measured in V2's thread case: 65 GOs in 3 s before the change, 2,124 after. On the board the JTAG time dominates; this would have added ≈ 40 ms to every knob GO.
4. **The sender holds no lock during a transaction.** A first version did. The panel's knob callbacks waited for the bridge: 74 moves in 3 s under the stand-in, and it would have been worse on the board. Fixed before the evidence run; the evidence is from the fixed version.
5. **G_CTRL is not written at connect.** The panel shows what the switch holds and writes G only when it is changed. `wpms_music.demo()` writes override, G = 8 first, while the test origin (N = 1,008) still plays: about 24 dB louder than its −12.44 dBFS at G = 12, i.e. clipping until the demo's own GO lands. That is a property of the demo, not a WPMS discrepancy. The panel defaults to that setting (override, G = 8) as soon as the user touches it.
6. **A block whose switch state is unknown** (at connect, after the test origin) is not written until the user moves one of its knobs or presses Seed. Its first GO is then a full re-seed from the panel's values. Otherwise connecting would have replaced the test origin's block 0 with the panel's defaults.
7. **Level is relative to amplitude 1.0** (LPT = `q26(dB / 6.0206)`, as `note_block()`'s LP = log2 A0). After the seed, a level change writes LPT and LE0 only (mask LEVEL), never LP. The STP glide then carries every step. Glide ≥ 1 dB/s is enforced: LE0 = 0 would freeze the level, and LE0 < 0 is EW6.
8. **Envelope changes use the mask {LAD1, LAD2, LS0} = 0x8018**, so the phases continue. γ is limited per N, so that LAD1 and LS0 fit in 32 bits (`gamma_max(N)`).
9. **The controller checks the GO itself before sending** (P ≤ 8, no block twice, N ∈ [32, NMAX], Σ N ≤ NMAX) on the state the switch holds after that GO. An item that would fail waits. This is what lets "shrink block 0, then tick block 1" happen in the right order without a refusal. The brief's law does not name it; it follows from "a refusal is a defect of the controller".

None of these needs a change to the switch. **No discrepancy was filed**: the switch offers everything the panels need.

## 6. Questions settled from the model and the RTL / §4 の前に確かめたこと

Read in `hw/tools/switch_model.py` and `hw/switch/wpms_switch.v` (RH001–RH003); neither changed.

1. **go-now (COMMIT bit 31) advances GO_SEQ and is applied like a GO.** In the RTL, `x_commit && x_d[31]` sets `fire_now`, which does `go_seq <= seq_nx`, the hand-over with `ibx_seq <= seq_nx`, and `fired |= go_items`. The model's `fire()` does the same. APPLIED_SEQ publishes it when the Formation has copied the take. So the law waits for APPLIED_SEQ ≥ the GO_SEQ read right after the COMMIT (wrap-safe comparison). It is checked like any GO, against the state earlier GOs leave, and fires that block alone. **V3 confirms it:** every APPLY found APPLIED_SEQ = GO_SEQ.
2. **While an item is frozen** — from arm (bit 30) to apply, or from go-now to apply — the switch refuses:
   - writes to its INBOX words (slots 13 and 14 are refused always);
   - its RTOUT;
   - its COMMIT (arm and go-now alike);
   - for the sweep item, SWEEP (0x290) and SWEEP_COMMIT (0x291).
   It does **not** refuse the other blocks, the global words (MG_TARGET, MG_RATE, G_CTRL, TEST_ORIGIN, …), GO itself, or any read. A refused write changes nothing but REJECT[port]. A GO that fails its check also disarms its items.
3. **A GO with nothing armed is counted and advances GO_SEQ**, if the state it checks is valid. The RTL header says: "GO_SEQ counts the GOs that pass, empty ones included". The model's `check(set())` checks the sweep then in effect, and `fire()` increments `go_seq`. The controller never sends one (it uses go-now only).
4. **MG_TARGET** (0x010) is Q6.26 in log2 units, signed. The output stage uses `min(MG_TARGET, 0)`, so a positive value acts as 0 dB. The floor is 0x8000_0000 = −32 log2 = −192.7 dB, also the soft-mute target. dB = value / 2²⁶ × 6.0206, so `q26(-8)` = 0xE000_0000 = −48.16 dB. "−48 dB" in `wpms_music.demo()` is that, rounded. **MG_RATE** (0x011) is in the same units per strobe (one per sample): 13,933 = 60.0 dB/s at 48 kHz. The panel converts with exactly these formulas.

## 7. Questions for the architect / アーキテクトへの質問

1. **The board run (§7).** It needs the Phase 6 image, `quartus_stp -t wpms_bridge.tcl`, and `python wpms_gui.py --connect` (or `python wpms_ctl.py measure --csv times.csv --log board.json` for the numbers alone). After it, the session's log is replayed with `python cosim_gui_replay.py board.json`. Shall I prepare `gui_board.md` with the expected column already filled, as in Phase 6?
2. **SignalTap open during the run.** The brief asks to record whether it stays open. Nothing here depends on it, but quartus_stp and the SignalTap GUI share the JTAG server. If the bridge's transaction time doubles with SignalTap open, that alone is worth a row.
3. **Board sessions that do not start at the test origin.** A board session replays faithfully in V3 only if it started there. That means connecting right after loading the image, or pressing Test origin first. The replay reports when a log did not start there. Is that rule acceptable, or should the replay reconstruct the state read at connect (the sweep and N only are recorded)?

---

**和文要約。** `hw/tools/host/gui/` に、ISSP セッションを一度だけ開いて TCP で一行一命令を受ける常駐の**橋**（`wpms_bridge.tcl`）、Tk に依存しない**制御ロジック**（`wpms_ctl.py`）、その上の **GUI**（`wpms_gui.py`、Tkinter）を作った。

**V1（橋、代役上）**：全命令型、拒否で止まるバッチ（残りは SKIP で実行されない）、ISSP 誤り後の復帰、クライアント断・二重接続・QUIT 後もセッションは一度だけ開く、127.0.0.1 のみで待受け、SHUTDOWN で閉じる——すべて合格。壊した橋 9 種もすべて検出した。

**V2（制御ロジック、代役＋凍結モデル）**：
- 400 手のストームで 133 GO、スレッド版 3 秒 4,011 手で 2,124 GO。いずれも拒否 0、終了時に送った状態＝望む状態。
- 忙しいつまみがあっても他のブロックは次の GO で処理された。
- テスト原点後は再同期した。
- apply を待たない制御器は拒否される（検査に歯がある）。

**V3（RTL-SIM 再生）**：ストームのログはスイッチ RTL で書込み拒否 0、全 GO が上限内に適用（APPLIED_SEQ = GO_SEQ）、音もモデルとサンプル単位で一致。歯のログは期待どおり FAIL した。

§6 の四問：
1. go-now は GO_SEQ を進め、GO と同じく APPLIED_SEQ で適用される。
2. 凍結中に拒否されるのは、そのブロックの INBOX・RTOUT・COMMIT と、掃引項目の SWEEP・SWEEP_COMMIT。大域語と読出しは拒否されない。
3. 何も構えていない GO も数えられ、GO_SEQ を進める。
4. MG_TARGET は Q6.26 の log2 単位で、≤ 0 として使われ、床は −32（−192.7 dB）。`q26(-8)` は −48.16 dB。

逸脱は §5 の 9 点で、いずれもスイッチの変更は要らない。食い違いは登録していない。実機の数値はアーキテクトを待つ。
