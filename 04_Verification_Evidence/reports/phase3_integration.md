# Phase 3 — Sequencer and integration / シーケンサと統合

*CC0 · 2026-09-28 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 3, with the rulings of 2026-09-28. Stops here, as the brief asks.*
*Verdict: **done and green.** `hw/l2/wpms_l2_top.v` runs the Core copy (RH031p), the Formation datapath and the new sweep sequencer under a score. In the score's **dispatch form** the packets follow each other with **g = 0** and the first packet starts **1 clock** after the strobe. Against the sweep oracle `sweep_sim.py` — run unchanged, 3 seeds × 12,000 samples per clock budget — every bundle L1 latches, every packet length N, every K sequence and the `stay_value` pin at every Stay are **identical**. That holds for 36,000 sweeps and 128,321 packets at the 100 MHz budget, and likewise at the 50 MHz budget (NMAX 1024), where every sweep fits its 1,041 clocks. Five injected errors (EW2–EW6) silence L1 in the clock the flag rises, and the Core halts at the trap word. R2 is not achievable data-driven on the Core as built (SD-04, now RTL-SIM); the Hook A answer is in §5. Evidence class of every number: **RTL-SIM** (resources: ESTIMATE).*

*判定: **完了・緑。** `hw/l2/wpms_l2_top.v` は Core の写し（RH031p）・Formation データパス・新しいスイープ・シーケンサを楽譜で動かす。楽譜の**ディスパッチ形**ではパケット間 **g = 0**、ストローブから最初のパケットまで **1 クロック**。スイープ・オラクル `sweep_sim.py`（無改変、各クロック予算で 3 シード × 12,000 サンプル）と比べ、L1 がラッチするバンドル・パケット長 N・K の列・各 Stay の `stay_value` はすべて**一致**した。100 MHz 予算で 36,000 スイープ・128,321 パケット、50 MHz 予算（NMAX 1024）でも同様で、全スイープが 1,041 クロックに収まる。注入した 5 種のエラー（EW2–EW6）は、フラグの立つクロックで L1 を無音にし、Core はトラップ語で停止する。R2 は現状の Core ではデータ駆動で実現できない（SD-04、RTL-SIM で確認）。Hook A の答えは §5。数値はすべて **RTL-SIM**（資源は ESTIMATE）。*

---

## 0. Rulings applied (2026-09-28) / 適用した裁定

| Ruling | How Phase 3 applies it |
|---|---|
| SD-13 (a): E8 on SFT overflow stands | nothing to change (hardware follows the model); recorded in `discrepancies.md` |
| SD-14 (a): the lane's CSEL on the word before a foreground Branch; T_wake 3 accepted | the **branch form** of the score does exactly this (`NOP CSEL=NONEMPTY`, Stay words carry `CSEL=MORE`): T_wake measured **3**. The **dispatch form** needs no foreground conditional at all: T_wake **1** |
| SD-06: insertion approved; L1 silenced at once by the Formation's `error_flag` | `l1_mute` = `error_flag`; `bin_valid` and `packet_start` fall in the first clock the flag is high; five injected errors verified (§3.5). The integration also found and fixed a handshake subtlety (SD-15) |
| Clock target: 50 MHz if 100 MHz is at all difficult; budgets halved; no pipelining now | every RTL parameter needed is in `wpms_l2_top.v` (NMAX); both budgets are cosimulated: **100 MHz** (NMAX 2048, T_min 2,083) and **50 MHz** (NMAX 1024, T_min 1,041). No datapath pipelining was done |

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `03_Sample_Implementations/hw/l2/wpms_sequencer.v` | The sweep sequencer (208 lines, MIT). Detects each Stay Set from K (0 → 1), takes TS_PKT and TS_CSEL from the timing-signal bus; packet index q, CUR = order[q], P from SWEEP.a; lanes STROBE / NONEMPTY / MORE; StayVal.s ← N at prefetch, StayVal.p ← TS_PKT ? StayVal.s : 0 at every Stay Set → `stay_value`; prefetch of order[q+1] one clock after packet q's latch, and of the next sweep's first block once BCP's copy has landed (`inbox_taken`); the window label for SSS; the L1 face one clock after the Core (SD-11); `l1_mute` = `error_flag`. |
| `03_Sample_Implementations/hw/l2/wpms_l2_top.v` | Core copy (IMEM 1024, PRESCALE 1) + Formation + sequencer (144 lines). JumpVal / LoopVal drive the Core's indirect-read bus (purpose 00 / 01), always ready; insertion to `TRAP_ADDR` 0x3FF; no external stack (a spill is exported). Parameters NMAX, N_MIN, SCORE_HEX / SCORE_MIF, IMEM_VENDOR. |
| `03_Sample_Implementations/hw/l2/scores/wpms_r1d.{score,hex,mif}` | **The Phase 3 score: R1 in dispatch form** (§3.1). 899-word span + trap. |
| `03_Sample_Implementations/hw/l2/scores/wpms_r1b.{score,hex,mif}` | R1 in branch form (§3.1), the lanes as the sketch drew them, within the Core's Branch law. |
| `03_Sample_Implementations/hw/l2/programs/wpms_housekeeping_dispatch.pfasm` | The dispatch form's housekeeping window: BCP, then JumpVal = TAIL_BASE + 16·P from the status view (5 instructions, CLEAN). A Layer 3 program of this build; the oracle keeps running the one-instruction `wpms_housekeeping.pfasm`. |
| `03_Sample_Implementations/hw/l2/wpms_l2_tb.v` | Sweep-level testbench: the switch and L1 stand-in; event log (latches, bins and K, Stay Sets, the pin at each Stay, BCP, errors, HALT, stack requests, the return to SLEEP). |
| `03_Sample_Implementations/hw/tools/sweep_dump.py` | Runs `sweep_sim.py` **unchanged** with a recording subclass of its Sequencer: the GO stimulus per sample and the expected (block, bundle, N) per packet. |
| `03_Sample_Implementations/hw/tools/cosim_sweep.py` | Drives the testbench from the dump, compares, measures; `--directed` adds the packet floor and the five error injections. |
| `03_Sample_Implementations/hw/tools/cosim_sweep_mutants.py` | 11 defects in scratch copies of the sequencer / Formation; each must be caught. |
| `03_Sample_Implementations/hw/tools/r2_probe.py` | Hook A: the queued Base Set + Loop on the Core copy. |
| `03_Sample_Implementations/hw/l2/run_phase3.sh` | The recipe (§2). |
| changed: `hw/l2/wpms_formation.v` (RH002) | `insert_req` withdrawn while `insert_ack` is up (SD-15). Phase 2 regression re-run: green. |
| changed: `hw/tools/score_as.py` (RH002) | `.org` and `JumpInd` (the indirect Jump). |
| changed: `hw/l2/score_rt_tb.v` (RH002) | logs indirect reads (for the R2 probe). |
| `04_Verification_Evidence/rtl_sim/2026-09-28_phase3_l2_integration/` | `observation.md` (expected before observed) and every log. |
| `04_Verification_Evidence/reports/discrepancies.md` | the rulings; SD-15 new; SD-03, SD-04, SD-05, SD-11, SD-12 updated. |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

`03_Sample_Implementations/hw/l2/run_phase3.sh 04_Verification_Evidence/rtl_sim/2026-09-28_phase3_l2_integration` (Icarus Verilog 12.0 `-g2012`, Python 3.11; 28 min):

```
run_phase3: 2026-09-28T12:54:03Z — Icarus Verilog version 12.0 (stable) (); Python 3.11.15; 12000 samples per seed
  run_phase2: ALL PHASE 2 CHECKS PASSED
  [PASS] Phase 2 regression (datapath cosimulation, mutants, score round trip) on the current RTL
  score_as: 899 words (+ trap at 0x3FF) -> wpms_r1d.hex, wpms_r1d.mif;score_as: 240 words (+ trap at 0x3FF) -> wpms_r1b.hex, wpms_r1b.mif;
  [PASS] score_as.py: wpms_r1d and wpms_r1b equal the committed .hex/.mif
  validate CLEAN ; JumpVal for P = 0..8: 0x300 0x310 0x320 0x330 0x340 0x350 0x360 0x370 0x380
  [PASS] wpms_housekeeping_dispatch.pfasm: CLEAN; the model computes TAIL_BASE + 16 P (ORACLE)
  iverilog -Wall: 11 '@* sensitive' notes, 1 tri0-port note(s), 0 other lines
  [PASS] wpms_l2_top + Core copy + Formation + sequencer + testbench compile
  R2-lit: Loop 3: body Stay Sets before housekeeping at clocks [151, 183, 215] -> periods [32, 32, 32]; indirect reads requested: 0
  R2-ind: Loop 0: body Stay Sets before housekeeping at clocks [151] -> periods [32]; indirect reads requested: 0
  [PASS] R2 probe: queued Base Set + Loop re-enters gap-free with a literal count; no data-driven count (SD-04)
  [cs_r1d_100]   total: 36000 sweeps, 128321 packets, 54205714 bins, 16740 full-load sweeps, 164321 Stays with the pin checked; sweeps longer than T_min: 0
  [cs_r1d_100]   T_wake (strobe clock -> first packet Stay Set): 1..1 clocks; L1 packet_start one clock later
  [cs_r1d_100]   g (Stay Set to next Stay Set minus N): 0..0
  [cs_r1d_100]   housekeeping Stay Set -> first SLEEP clock: 13..13; BCP commit -> copy landed: 2..9 clocks
  [cs_r1d_100]   sweep length (strobe -> first SLEEP clock): 14..2062; full-load sweeps: 2062..2062 of T_min 2083 (21 spare at worst)
  [cs_r1d_100]   floor (N_MIN lowered to 16 for this case only): N = 28 29 30 31 32 33 -> Stay Set to next Stay Set 30 30 30 31 32 33
  [PASS] R1 dispatch form, 100 MHz budget: every bundle, N, K sequence and stay_value as the oracle; errors silence L1
  [cs_r1d_50]   total: 36000 sweeps, 126763 packets, 27954068 bins, 17730 full-load sweeps, 162763 Stays with the pin checked; sweeps longer than T_min: 0
  [cs_r1d_50]   T_wake (strobe clock -> first packet Stay Set): 1..1 clocks; L1 packet_start one clock later
  [cs_r1d_50]   g (Stay Set to next Stay Set minus N): 0..0
  [cs_r1d_50]   housekeeping Stay Set -> first SLEEP clock: 13..13; BCP commit -> copy landed: 2..9 clocks
  [cs_r1d_50]   sweep length (strobe -> first SLEEP clock): 14..1038; full-load sweeps: 1038..1038 of T_min 1041 (3 spare at worst)
  [cs_r1d_50]   floor (N_MIN lowered to 16 for this case only): N = 28 29 30 31 32 33 -> Stay Set to next Stay Set 30 30 30 31 32 33
  [PASS] R1 dispatch form, 50 MHz budget (NMAX 1024, T_min 1041): as above, every sweep fits
  [cs_r1b_100]   total: 12000 sweeps, 42056 packets, 17732862 bins, 5595 full-load sweeps, 54056 Stays with the pin checked; sweeps longer than T_min: 0
  [cs_r1b_100]   T_wake (strobe clock -> first packet Stay Set): 3..3 clocks; L1 packet_start one clock later
  [cs_r1b_100]   g (Stay Set to next Stay Set minus N): 1..1
  [cs_r1b_100]   housekeeping Stay Set -> first SLEEP clock: 14..14; BCP commit -> copy landed: 2..9 clocks
  [cs_r1b_100]   sweep length (strobe -> first SLEEP clock): 17..2073; full-load sweeps: 2066..2073 of T_min 2083 (10 spare at worst)
  [cs_r1b_100]   floor (N_MIN lowered to 16 for this case only): N = 28 29 30 31 32 33 -> Stay Set to next Stay Set 30 30 31 32 33 34
  [PASS] R1 branch form, 100 MHz budget: as above (T_wake 3, g 1)
  [cs_r1b_50]   total: 3000 sweeps, 9798 packets, 2178264 bins, 1362 full-load sweeps, 12798 Stays with the pin checked; sweeps longer than T_min: 1362
  [cs_r1b_50]   T_wake (strobe clock -> first packet Stay Set): 3..3 clocks; L1 packet_start one clock later
  [cs_r1b_50]   g (Stay Set to next Stay Set minus N): 1..1
  [cs_r1b_50]   housekeeping Stay Set -> first SLEEP clock: 14..14; BCP commit -> copy landed: 2..9 clocks
  [cs_r1b_50]   sweep length (strobe -> first SLEEP clock): 17..1049; full-load sweeps: 1042..1049 of T_min 1041 (-8 spare at worst)
  [cs_r1b_50] sweeps longer than T_min: 1362 (informative: the branch form does not fit 50 MHz at NMAX 1024)
  [PASS] R1 branch form, 50 MHz budget: bundles as the oracle (overruns reported, not failed)
  cosim_sweep_mutants: 11/11 mutants killed
  [PASS] cosim_sweep_mutants.py: every deliberate defect in the sequencer / Formation is caught
run_phase3: ALL PHASE 3 CHECKS PASSED
```

## 3. Results, with evidence classes / 結果と証拠クラス

### 3.1 The score / 楽譜

**Why not the sketch.** Deliverable 3 §3 closes each packet with a *queued conditional* transfer (MORE → next packet, else → HK). On the Core as built a queued Branch not taken resumes at Branch + 1 — the packet's own Stay, played again — and a taken one auto-saves (SD-05, reproduced in Phase 2). Encoded literally, the sweep either doubles its packets or stalls.

**The dispatch form (`wpms_r1d.score`) — gap-free, no conditional transfer anywhere.**

```
SLEEP_0: Branch 0            HK: StaySet · BCP · SAD 0x11A · LDA @PPM · ADD #512 · WJV · JumpInd
SLEEP_8: Branch 0 ─┐         TAIL_P (0x300 + 16·P): ProgEnd · Q:Jump SLEEP_P · Stay T_HK
POS0:  StaySet PKT ◄┘ · window(25) · ProgEnd · Q:Jump POS1 · Stay N
SLEEP_7: Branch 0 ─┐
POS1:  StaySet PKT ◄┘ · window(25) · ProgEnd · Q:Jump POS2 · Stay N
   …                                         POS7: … · Q:Jump HK · Stay N
```

- Eight unrolled positions, each closed by a **queued Jump** to the next (POS7 → HK): a queued Jump fires at Stay-timeup with no clock lost (g = 0, as Phase 1 SV-5b showed).
- P decides **where the chain is entered** — position 8 − P — so exactly P packets play. The entry is chosen one sweep ahead: in housekeeping, after BCP has landed the new SWEEP.a, the window reads the status view ([7:4] = P) and writes **JumpVal = TAIL_BASE + 16·P**; the score's background indirect Jump lands on TAIL_P, whose queued Jump takes the Core, at the housekeeping timeup, to **SLEEP_P** — the Branch-0 wait placed immediately before POS(8 − P). At the strobe SLEEP_P falls through into its position: **T_wake = 1 clock**.
- Nothing is taken conditionally, so the holding register is never used: no auto-save, no stack, neither consequence of SD-05 arises. The only lane consulted is STROBE.
- Law: the computed dispatch is a **background** one — W-T3 restricts register-source transfers only in the foreground, and Register Map v0.3 §2 gives JumpVal exactly this use ("BG computed dispatch only"). JumpVal reaches the Core through its indirect-read bus, i.e. lane 5. No instruction, register, lane or region was added; the housekeeping window is longer (5 instructions instead of 1) — a Layer 3 program of this build, while the golden oracle keeps its one-instruction window (the extra four write only Accm, ADRS and JumpVal).

**The branch form (`wpms_r1b.score`) — the sketch's lanes, within the Branch law.** SLEEP on STROBE; the lane word `NOP CSEL=NONEMPTY` and `Branch HK` (SD-14 as ruled); each position closes with its Stay (`CSEL=MORE`) and, after the timeup, a **foreground** Branch HK: MORE → falls through to the next position, else → HK. Exactly one Branch per sweep is taken (and auto-saves); housekeeping ends with a foreground **Reset**, which clears the holding register and returns to SLEEP. Costs: T_wake 3, **g = 1** per packet, housekeeping 14. It exercises all three lanes and fits the 100 MHz budget; it does **not** fit 50 MHz at NMAX 1024 (§3.4).

### 3.2 The sequencer and the L1 face / シーケンサと L1 の顔

- **The Stay Set, seen from outside the Core.** K (`stay_counter`) is 0 in a Stay Set's clock and 1 in the next, and nothing else makes it step from 0 to 1; the sequencer acts in that next clock — the clock the Stay Set's own D16–D31 first appear on the registered bus (SD-11) and the clock the window's first instruction is issued. Its context (phase, CUR, q) is presented combinationally in that clock, so the Formation captures it with the first issue.
- **The L1 face is one clock late, uniformly** — SD-11's proposed disposition, now built: `bin_valid(c) = TS_PKT(c)`, `l1_k(c) = K(c−1)`, `packet_start` the clock after the Stay Set. Bin 0 of every packet, its last bin and the housekeeping edge land where they should; L1 sees the Core's timeline delayed by one clock. Every packet of every run has exactly N bins with K = 0 … N−1.
- **StayVal (W-F22).** Two stages: StayVal.s ← N at prefetch; StayVal.p ← (TS_PKT ? StayVal.s : 0) at each Stay Set; the pin = StayVal.p. Checked at every Stay's execute clock (C4-F16): N for every packet Stay, **0 for every housekeeping Stay** (164,321 Stays in the 100 MHz run alone).
- **Prefetch.** order[q+1] one clock after packet q's latch; the next sweep's first block as soon as BCP's copy has landed (`inbox_taken`), never while `bcp_busy` (mutant S6 shows the ordering matters).
- **SSS (SD-03).** The Stay Set's address, latched at every Stay Set — the value the Core's own `stay_start_state` takes (C3-F25).
- **Error → L1 silent (ruling).** `l1_mute` = `error_flag`; `bin_valid` and `packet_start` are gated combinationally.

### 3.3 Sweep-level cosimulation / スイープ水準の協調シミュレーション

RTL-SIM against `sweep_sim.py` (ORACLE, 0 mismatches against its own reference in every run). "Identical" = the block and the eight bundle words at every latch, N bins per packet, K = 0 … N−1, and the pin at every Stay.

| Score · budget | Seeds × samples | Sweeps | Packets | Bins | Full-load sweeps | Result |
|---|---|---|---|---|---|---|
| dispatch · 100 MHz (NMAX 2048, T_min 2,083) | 3 × 12,000 | 36,000 | 128,321 | 54,205,714 | 16,740 | **identical**, 0 overruns |
| dispatch · 50 MHz (NMAX 1024, T_min 1,041) | 3 × 12,000 | 36,000 | 126,763 | 27,954,068 | 17,730 | **identical**, 0 overruns |
| branch · 100 MHz | 1 × 12,000 | 12,000 | 42,056 | 17,732,862 | 5,595 | **identical**, 0 overruns |
| branch · 50 MHz (informative) | 1 × 3,000 | 3,000 | 9,798 | 2,178,264 | 1,362 | identical; **1,362 sweeps longer than T_min** |

### 3.4 Measurements that replace the nominals / 名目値に代わる実測

RTL-SIM. "Clock" = the Core clock (100 MHz or 50 MHz: the numbers are clocks).

| Term | D3 §9 / oracle (nominal) | Dispatch form | Branch form |
|---|---|---|---|
| T_wake: strobe clock → first packet Stay Set | 2 (≤ 4) | **1** | 3 |
| … → L1 `packet_start` | — | 2 | 4 |
| g between packet Stays | 0 | **0** | 1 |
| Packet floor (25-instruction window) | 29 (N_MIN 32) | **30** (N = 28, 29, 30 → 30) | max(N, 29) + 1 |
| Housekeeping: HK Stay Set → first SLEEP clock | T_HK ≈ 13 | **13** | 14 |
| BCP: commit → copy landed | ≤ 10 | 2 … 9 | 2 … 9 |
| Worst full-load sweep, 100 MHz | 2,064 of 2,083 (19 spare) | **2,062** (21 spare) | 2,073 (10 spare) |
| Worst full-load sweep, 50 MHz (NMAX 1024) | — | **1,038** of 1,041 (3 spare) | 1,049 (does not fit) |

**The 50 MHz budget, L1 side (arithmetic, for Phase 4).** D3 §9's second line — T_wake + Σ N + D_L1 ≤ T_min — plus the one-clock L1 face: 1 + 1 + NMAX + D_L1 ≤ 1,041. With the customer's D_L1 ≤ 24 this gives **NMAX ≤ 1,015** at 50 MHz; NMAX = 1024 overruns the L1 side by 9 clocks (at 100 MHz: 1 + 1 + 2,048 + 24 = 2,074, 9 spare). See question 2.

### 3.5 Errors: L1 silent at once, the Core halted / エラー: L1 即時無音、Core 停止

RTL-SIM, dispatch form (the branch form alike, see below). Each case starts from a normal empty sweep and a three-packet sweep.

| Injected | How | `error_flag` | After the flag | Core |
|---|---|---|---|---|
| EW6 | LE0 = −1 lands in a listed block; its next packet window's STP | EW6 | 0 latches, 0 bins | HALT at the trap 0x3FF, 56 clocks later (the packet's timeup) |
| EW5 | a sweep item repeating a block, taken at the strobe; BCP | EW5 | 0, 0 | HALT, 11 clocks later (housekeeping timeup) |
| EW2 | N = 16 lands for the sweep's first block; the post-housekeeping prefetch | EW2 | 0, 0 | HALT, 8 clocks later |
| EW4 | the packet window replaced by negative_tests N1 (store written in a packet window) | EW4 | 0, 0 | HALT, 57 clocks later |
| EW3 | the packet window replaced by negative_tests N4 (STM into the inbox view) | EW3 | 0, 0 | HALT, 61 clocks later |

The first run of these cases did **not** reach the HALT: the Core took the insertion a second time at the trap word, the second auto-save spilled, and the Core waited in S_PUSH (SD-15). Cause: the Formation dropped its request one clock after `insert_ack` — as Core Ch.5 §5.9 allows — but the Core looks at `insert_req` again in the ack clock. Fixed on the Formation side (`insert_req` withdrawn while `insert_ack` is up, RH002); mutant S10 undoes the fix and is caught. In the **branch form**, an error in housekeeping (EW5, EW2) meets the holding register already taken by the sweep's one Branch: the insertion spills and the Core waits in S_PUSH instead of halting; L1 is silent all the same. This is that form's known limit (no external stack in this profile).

### 3.6 Does the test bite? / 試験は噛むか

RTL-SIM. **11 of 11** single defects in the sequencer / Formation are caught (`logs/cosim_sweep_mutants.log`): prefetching the packet's own block (S1); the pin following StayVal.s (S2); K not delayed on the L1 face (S3); MORE off by one (S4); q ≠ 0 in housekeeping (S5, breaks the dispatch); prefetch before BCP has landed (S6); no L1 silencing (S7); StayVal.p not cleared for housekeeping (S8); NONEMPTY inverted (S9); the SD-15 fix undone (S10); housekeeping counted as a packet (S11).

## 4. Deviations / 逸脱

- **From the golden model: none.** Every compared value equals the oracle's; `sweep_sim.py` ran unchanged (the dump is taken by a recording subclass; the 50 MHz runs override NMAX for the run only).
- **From Deliverable 2 §3 (absolute clock alignment):** the L1 face is one clock after the Core — packet_start the clock after the Stay Set, K delayed — a uniform shift, as SD-11 proposed. Relative timing (zero gap, N bins, K = 0 … N−1, the latch) is exactly D2's.
- **From Deliverable 3 §3 (the sketch):** the score is R1 in dispatch form, not the sketch's conditional transfers (SD-05); the housekeeping window has four more instructions (JumpVal); T_wake is 1, not 2. The branch form keeps the sketch's lanes at g = 1.
- **Formation RTL:** RH002 (SD-15). The Phase 2 regression (3,914 cases, 20 mutants, score round trip) is green on it.

## 5. Hook A — "Which Core primitive carries R2's conditional re-entry without a clock?" / Hook A への答え

RTL-SIM (`r2_probe.py`) and reading:

1. **The primitive exists:** a **queued Base Set + queued Loop** closing the packet body. The queued Base Set takes Base := Stay Start State (the body's own Stay Set, C3-F25); at timeup a Loop not yet exhausted resumes at Base with no clock lost (probe: Loop 3 → three passes, Stay Set to Stay Set 32, 32, 32), and on exit resumes past the Stay.
2. **What is missing is the count as data.** A queued Loop uses its literal D16–D31 (C4-V1); Loop 0 means zero iterations, and the Core makes no indirect read in the Q band (`need_ind_loop` excludes it). A data-driven R2 therefore needs one Core change: **read a queued Loop's register-source target at scan time** (during the window, so nothing is spent at timeup) — which is the master's one requested amendment, INT-R1 (the register-source operand bit, Ch.5 §5.5), realized for Loop. LoopVal would carry P − 1 (or the sequencer could answer the read with P).
3. **Other routes, priced:** a window that computes its own exit (JumpVal from q and P) costs ≥ 8 more window instructions without compare instructions — N_MIN would rise past 32; a conditional re-entry through a queued Branch meets SD-05 (b).
4. **Meanwhile** the dispatch form of R1 already delivers what R2 was preferred for — data-driven P, g = 0 — at the cost of eight copies of the 29-word body (≈ 240 of 1,024 words).

No Core change was made.

## 6. Discrepancies filed / 記録した食い違い

| ID | In one line | State |
|---|---|---|
| **SD-15** (new) | The Core re-takes an insertion whose request is still high in the `insert_ack` clock; Core Ch.5 §5.9 allows dropping it then or later. Formation fixed (RH002); text or RTL clarification proposed to the Core's office | RTL-SIM · open |
| SD-03 | SSS substitute built (Stay Set address latched by the sequencer) | substitute in place |
| SD-04 | confirmed by the R2 probe | RTL-SIM · open |
| SD-05 | worked around by both score forms | RTL-SIM · open |
| SD-11 | resolved in the L2 top (uniform one-clock L1 face) | resolved |
| SD-12 | floor re-measured with the real window and score: 30 (dispatch), max(N, 29) + 1 (branch) | RTL-SIM · open |
| SD-06, SD-13, SD-14 | ruled 2026-09-28 and applied | ruled |

## 7. Questions for the architect / アーキテクトへの質問

1. **The score.** May the dispatch form (`wpms_r1d.score`: queued Jumps, entry chosen by a background computed dispatch through JumpVal in housekeeping) be the working score for Phases 4–6, with the branch form kept for lane checks? It needs the 5-instruction housekeeping window. / ディスパッチ形を以降の標準楽譜としてよいか。
2. **NMAX at 50 MHz.** NMAX = 1024 fits the L2 side (1,038 of 1,041) but the L1 side needs Σ N ≤ 1,041 − 1 (T_wake) − 1 (L1 face) − D_L1; with the customer's D_L1 ≤ 24 that is **1,015**. Proposal: **NMAX = 1,008** at 50 MHz (or decide after Phase 4 measures D_L1). / 50 MHz の NMAX は L1 側の式から 1,015 以下が必要。1,008 を提案（Phase 4 で D_L1 を測ってから決めても可）。
3. **R2.** Pursue INT-R1 for a queued Loop with the Core's office (register-source count read at scan time), or stay with the dispatch form? / R2 のため Core 事務所に INT-R1（キュー Loop のレジスタ源カウント）を依頼するか。
4. **SD-15.** Forward the insertion-handshake note to the Core's office? / 挿入ハンドシェイクの件を Core 事務所へ回してよいか。
5. **LoopVal on the Core's indirect bus.** Map v0.3 lists LoopVal as "no Core pin at present (TRACK)". The top connects it (purpose 01) beside JumpVal; no score uses it. Keep, or tie off until ruled? / LoopVal を間接読出しバスに接続したままでよいか。

## 8. Resource numbers / 資源数

**ESTIMATE** (Yosys 0.69, `synth_intel_alm -family cyclonev` + `abc -lut 6`; no Quartus here): the sequencer adds **61 LUTs, 14 arithmetic ALUTs, 339 flip-flops** (256 of them the staged bundle). With the Formation (after RH002: 4,583 LUTs, 931 arithmetic, 1,203 FFs, 1,568 MLAB bits, ≈ 3 DSP blocks — `logs/phase2_regression.txt`), the Core by its own Quartus ledger (RH028, 441.8 ALMs) and its instruction memory (1,024 × 32 = 4 M10K), the L2 is **≈ 5–6 k ALMs, 4 M10K, 3 DSP blocks** of the 5CSEBA6. A whole-top Yosys run did not give a usable number (the ROM image was not loaded, so the logic behind it was optimized away); Phase 6 replaces all of this with Quartus. / 概算で ALM 5〜6 千、M10K 4、DSP 3。Phase 6 で Quartus に置き換える。

---

*Stopped at the end of Phase 3, as instructed. / 指示どおり Phase 3 の終わりで停止する。*
