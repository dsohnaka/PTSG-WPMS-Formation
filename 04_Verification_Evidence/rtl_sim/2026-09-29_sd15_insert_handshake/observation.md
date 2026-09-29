# observation — SD-15: the Core takes a still-held insertion request twice
# 観測判決 — SD-15: Core は保持されたままの挿入要求を二度受け付ける

**Verdict / 判決: REPRODUCED on the frozen PTSG-Core source (RH030 as built, sha256 `fb995687…60e0`, PTSG-Core `1b58ebc`) and on the RH031p copy.** A requester that follows Core Ch.5 §5.9 literally, dropping `insert_req` at the clock edge where it samples `insert_ack` = 1, has its request accepted **twice**. The second acceptance auto-saves over an occupied holding register. With no external stack (as WPMS runs) the Core waits in S_PUSH for ever and never executes the target; with a stack it pushes a spurious context and pulses `insert_ack` twice. A requester that withdraws the request **within** the ack clock gets exactly one acceptance in every scene. This is recorded as a bug report to the Core's office, by the architect's ruling of 2026-09-29. No Core source was changed.

**再現（凍結 Core RH030 と写し RH031p の両方）。** Ch.5 §5.9 の文言どおり、`insert_ack` = 1 を標本化したクロック端で `insert_req` を下げる要求元は、要求を**二度**受け付けられる。二度目は埋まった保持レジスタへの自動退避となり、外部スタックがなければ（WPMS の構成）S_PUSH で永久に待ち、ターゲットを実行しない。スタックがあれば余分な文脈を積み、`insert_ack` が二度出る。ack のクロック**内**で要求を取り下げる要求元は、どの場面でも一度だけ受け付けられる。2026-09-29 の裁定により、Core 事務所への不具合報告として記録する。Core のソースは一切変更していない。

**Evidence class / 証拠クラス:** RTL-SIM (Icarus Verilog 12.0, `-g2012`). **License:** CC0 1.0 Universal.

---

## 1. Setup / 環境

| Item | Value |
|---|---|
| RTL under test | `PTSG-Core/03_Sample_Implementations/ptsg_core_verilog/ptsg_core.v` (frozen, **read only**) and `03_Sample_Implementations/hw/core/ptsg_core_rh031p.v`; each with the Core's `ptsg_imem` wrapper (SIM branch), PRESCALE 1, IMEM_DEPTH 32 |
| Bench | `03_Sample_Implementations/hw/core/sd15_insert_handshake_tb.v` — one Core, a program of at most six words, one insertion request to word 10, which holds a foreground Prog End (C3-F23 → C3-F24: the Core must HALT there) |
| Scenes | **S_RUN**: `NOP · NOP · Jump 1` (honoured at once); **bare-Stay**: `NOP · Stay 40 · Jump 1` (deferred to timeup); **window**: `NOP · Stay Set · NOP · Prog End · Stay 40 · Jump 1` (the WPMS packet shape; deferred to timeup, C3-F20) |
| Requester | `req` set by a one-clock `fire`, cleared by `if (insert_ack) req <= 0` (a registered drop). **registered**: `insert_req = req` — the text's literal reading. **in-ack-clock**: `insert_req = req & ~insert_ack` — what the Core's own conformance bench does (T5a, T23: blocking `insert_req = 0` one delta after the edge that raised `insert_ack`) and the WPMS workaround (`wpms_formation.v` RH002) |
| Stack | **none**: `stack_ack` tied 0 (as the WPMS L2 top); **1-clock**: the conformance bench's responder |
| Recipe | `03_Sample_Implementations/hw/core/run_sd15.sh <this directory>` — 2 sources × 3 scenes × 2 requesters × 2 stacks = 24 runs, seconds; `logs/run_sd15.txt` |

## 2. Expected — from the text, and from the Phase 3 finding (SD-15, filed 2026-09-28, before this bench existed) / 期待値

| Item | By the text (Ch.5 §5.9) | By the Phase 3 finding |
|---|---|---|
| `insert_ack` pulses per request | 1 | registered requester: 2 with a stack; 1 and a stall without |
| Stack push | none (the holding register is free) | registered requester: one spurious push request |
| End state | S_HALT at word 10, `error_flag` = 1 | registered requester: S_PUSH at word 10 with no stack |
| First ack after the request | S_RUN: at once; Stay scenes: at the Stay's timeup | same |

## 3. Observed / 観測 (`logs/run_sd15.txt`)

Identical on the frozen source and on the copy (24 of 24 lines as tabulated):

| Scene | Requester | Stack | First ack after the request | `insert_ack` pulses | Pushes | End |
|---|---|---|---|---|---|---|
| S_RUN | registered | none | 3 clocks | 1 | **1** | **S_PUSH at 0x00A**, `error_flag` 0 |
| S_RUN | registered | 1-clock | 3 clocks | **2** | **1** | S_HALT at 0x00A |
| S_RUN | in-ack-clock | none / 1-clock | 3 clocks | 1 | 0 | S_HALT at 0x00A, `error_flag` 1 |
| bare-Stay | registered | none | 30 clocks (timeup) | 1 | **1** | **S_PUSH at 0x00A** |
| bare-Stay | registered | 1-clock | 30 clocks | **2** | **1** | S_HALT at 0x00A |
| bare-Stay | in-ack-clock | none / 1-clock | 30 clocks | 1 | 0 | S_HALT at 0x00A |
| window | registered | none | 30 clocks (timeup) | 1 | **1** | **S_PUSH at 0x00A** |
| window | registered | 1-clock | 30 clocks | **2** | **1** | S_HALT at 0x00A |
| window | in-ack-clock | none / 1-clock | 30 clocks | 1 | 0 | S_HALT at 0x00A |

The clocks that matter (`sd15_window_drop0.vcd.gz` and `sd15_window_drop1.vcd.gz`: frozen source, window scene, no stack; values just after each rising edge; edge +0 is the one at which the Core accepts):

```
registered drop                                              withdrawn within the ack clock
edge req insert_req insert_ack SN     fsm    push err        edge req insert_req insert_ack SN     fsm    push err
 -1   1     1          0      0x004  S_WAIT  0    0           -1   1     1          0      0x004  S_WAIT  0    0
 +0   1     1          1      0x00A  S_RUN   0    0           +0   1     0          1      0x00A  S_RUN   0    0
 +1   0     0          0      0x00A  S_PUSH  1    0           +1   0     0          0      0x00A  S_HALT  0    1
 +2   0     0          0      0x00A  S_PUSH  1    0           +2   0     0          0      0x00A  S_HALT  0    1
```

In the clock after edge +0 the Core is in S_RUN at the target with the window closed, so `insert_pending = (fsm == S_RUN) && insert_req && !window_open` is true again whenever the request is still high. At edge +1 the Core then takes the insertion instead of executing the target word; `save_or_set` finds `hr_occupied` set by the first acceptance and goes to S_PUSH.

ack が立つクロックの間、Core はターゲット上で S_RUN、窓は閉じている。そのため要求がまだ高ければ `insert_pending` が再び真になり、端 +1 でターゲット語を実行せず挿入を再び受け付ける。最初の受付で `hr_occupied` が立っているので S_PUSH へ入る。

## 4. Verdict / 判決

**REPRODUCED.** Every expectation of the Phase 3 finding holds; the text's expectation holds only for a requester that withdraws within the ack clock. / Phase 3 の所見どおり。文言どおりの期待は、ack のクロック内で取り下げる要求元でのみ成り立つ。

---

## 5. Bug report to the Core's office / Core 事務所への不具合報告

*Architect's ruling 2026-09-29: the WPMS workaround stands; the item is recorded and conveyed to the Core team as a bug report, for repair at a later checkpoint. / 2026-09-29 裁定: WPMS 側の回避策を承認。Core チームへは後日の改修のための不具合報告として記録・伝達する。*

- **Where.** `ptsg_core.v` RH030: `insert_pending` (S_RUN), the deferred acceptance at Stay-timeup (`else if (insert_req) save_or_set(resume_addr, …)`), and — by reading, not exercised here — the S_HALT rescue (`if (insert_req) … save_or_set(state_num, …)`). All three test the **level** `insert_req` while `insert_ack`, the registered report of the previous acceptance, is high.
- **Why it matters.** Ch.5 §5.9 permits, and an ordinary synchronous requester produces, a request that is still high in the ack clock. The result is a second acceptance: a spurious auto-save, a second `insert_ack`, and — with no external stack, a legal configuration — a Core that never reaches the target. In WPMS this is the error path (INT-R2 substitute, SD-06): the Core never halted until the Formation was changed.
- **Proposed dispositions (the Core's office chooses).**
  1. *Text only:* Ch.5 §5.9 to say "`insert_req` must be low at the clock edge that ends the clock in which `insert_ack` is high (withdraw combinationally on `insert_ack`)". This is what the Core's own conformance bench does.
  2. *RTL:* ignore `insert_req` while `insert_ack` is high at the three sites above, e.g. `insert_pending = (fsm == S_RUN) && insert_req && !insert_ack && !window_open`. A new request would then wait at most one clock; the literal reading of §5.9 becomes safe.
- **Workaround in use.** `insert_req = insert_req_r && !insert_ack` (`wpms_formation.v` RH002), guarded by the sweep-level mutant S10.
- **Reproduction.** `hw/core/sd15_insert_handshake_tb.v`, `hw/core/run_sd15.sh`; this directory.

- **場所.** `insert_pending`（S_RUN）、Stay 満了時の遅延受付、および（読解のみ）S_HALT からの救出。いずれも `insert_ack`（前回受付の登録済み報告）が高い間に `insert_req` の**レベル**を見ている。
- **影響.** §5.9 が許し、普通の同期式要求元が作る「ack のクロックでまだ高い要求」が二度目の受付を招く。外部スタックのない構成（合法）では Core がターゲットに到達しない。WPMS ではエラー経路が該当し、Formation を変えるまで Core は停止しなかった。
- **処置案（Core 事務所が選ぶ）.** (1) 文言のみ: ack の立つクロックの終わりの端で `insert_req` が低いこと（ack で組合せ的に取り下げる）と明記。(2) RTL: `insert_ack` が高い間は `insert_req` を無視する。
- **回避策.** `insert_req = insert_req_r && !insert_ack`（RH002、変異体 S10 で保護）。
