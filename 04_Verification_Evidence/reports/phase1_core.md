# Phase 1 — The Core, patched on a copy / Core の写しへの適用

*CC0 · 2026-09-27 · Claude Code for the architect, per `04_Verification_Evidence/SILICON_BRIEF_2026-09-27.md` §4 Phase 1. Stops here, as the architect asked.*
*Verdict: **done and green.** The frozen `ptsg_core.v` is untouched. Its working copy `hw/core/ptsg_core_rh031p.v` carries the RH029/030 header corrections, `stay_value` in form B (C4-T5 lean) at width `CNT_W` = 12 (C5-T2 lean), and a draft RH031 entry (number provisional). With the pin silent the copy is **bit-identical** to RH030; SV-0 … SV-7 pass; the anti-pattern, built in the testbench only, makes SV-4 **fail with an 8192-clock Stay** — the test bites. Evidence class of every number: **RTL-SIM**.*

*判定: **完了・緑。** 凍結 `ptsg_core.v` は無変更。写し `hw/core/ptsg_core_rh031p.v` に RH029/030 のヘッダ修正、B 形・幅 12 の `stay_value`、RH031 の下書き記帳（番号は仮）を適用した。ピンが黙っていれば RH030 と**ビット同一**。SV-0〜SV-7 は合格。テストベンチ内だけで作った反パターンでは SV-4 が **8192 クロックの Stay で不合格**になる——試験は噛む。数値はすべて **RTL-SIM**。*

---

## 1. What was built / 作ったもの

| File | What it is |
|---|---|
| `03_Sample_Implementations/hw/core/ptsg_core_rh031p.v` | The working copy (module name kept `ptsg_core`, so the Core's own testbenches run on it unchanged). Diff against RH030 in §6: +64 / −8 lines, of which the logic is **one port and two wires**; the rest is the approved RH029/030 header patch and the RH031 draft entry (comments). MIT, Core header format. |
| `03_Sample_Implementations/hw/core/ptsg_core_sv_tb.v` | New testbench: `ptsg_core_sv_tb` (SV-1 … SV-7, plus SV-5b, supplementary, at P = 1) and `ptsg_core_sv0_tb` (SV-0: frozen RH030 and the copy in lockstep — random structured programs at P = 1 and 5, and the Live Session #1 Scene 4 program at 6250 → 20). The anti-pattern (sketch §4) and form A (sketch §3) exist **only here**, as a `force` on the copy's internal `stay_dur`, selected by `+define+SV_FORM_ANTIPATTERN` / `+define+SV_FORM_A`. |
| `03_Sample_Implementations/hw/core/run_phase1.sh` | The reproducible recipe; exits non-zero on any failed expectation (§2). |
| `03_Sample_Implementations/hw/tools/vcd_compare.py` | Signal-by-signal VCD comparison by hierarchical name, with an allow-list for one-sided nets. |
| `03_Sample_Implementations/hw/tools/vcd_dump.v` | A second top-level module that dumps an unchanged testbench to VCD. |
| `04_Verification_Evidence/rtl_sim/2026-09-27_phase1_core_rh031p/` | `observation.md` (expected before observed), the diff, both VCD comparisons, the SV-4 waveforms (gzip: form B ≈ 0.8 KB, anti-pattern ≈ 73 KB), every log. |
| `04_Verification_Evidence/reports/discrepancies.md` | SD-12 added (the packet floor, §5). |

## 2. Commands run and their last lines / 実行したコマンドと末尾行

`03_Sample_Implementations/hw/core/run_phase1.sh 04_Verification_Evidence/rtl_sim/2026-09-27_phase1_core_rh031p` (Icarus Verilog 12.0, `-g2012`; 40 s):

```
== 1. frozen source
  ptsg_core.v sha256 fb9956877bd24981541bbdd3e9316df168782c69b0b2d6a0633dccfbe13060e0 (PTSG-Core 1b58ebc)
  [ok]   frozen ptsg_core.v equals the committed RH030 blob
  diff: +64 / -8 lines
== 2. unchanged Core testbenches, stay_value unconnected (tri0 = 0)
  [ok]   ptsg_core_tb: pass logs identical (ALL TESTS PASSED)
  [ok]   ptsg_core_tb: VCDs identical on the common set (signals in both: 174; value changes compared: 8376)
  [ok]   ptsg_core_conformance_tb: pass logs identical (ALL CONFORMANCE TESTS PASSED)
  [ok]   ptsg_core_conformance_tb: VCDs identical on the common set (signals in both: 192; value changes compared: 579164)
== 3. SV-0 lockstep, frozen RH030 vs RH031p with stay_value tied 0
  [ok]   PASS SV-0 random, PRESCALE=1: 300 epochs x 2000 clocks = 600000 clocks in lockstep, 0 mismatching clocks
  [ok]   PASS SV-0 random, PRESCALE=5: 200 epochs x 3000 clocks = 600000 clocks in lockstep, 0 mismatching clocks
  [ok]   PASS SV-0 Scene 4: RH030 and RH031p (pin 0) in lockstep for 290538 clocks, 0 mismatching clocks; half-periods as observed on silicon
== 4. SV-1 … SV-7 (+SV-5b) on form B
  [ok]   SV SUMMARY: 8 passed, 0 failed (build: FORM B (the RTL as written))
== 5. the tests bite: anti-pattern (sketch §4) and form A (sketch §3) forced in the testbench
  [ok]   anti-pattern: SV-4 FAILS with an 8192-clock Stay (the test bites); SV-7 fails too; the rest pass
  [ok]   form A (informative): SV-4 and SV-7 fail — form A needs the length one clock ahead (the C4-T5 fork is real)
== 6. SV-4 waveforms
  73049 bytes  sv4_antipattern.vcd.gz
  756 bytes  sv4_formB.vcd.gz
  evidence copied to 04_Verification_Evidence/rtl_sim/2026-09-27_phase1_core_rh031p

PHASE 1: ALL CHECKS PASSED
```

## 3. Results, with evidence classes / 結果と証拠クラス

All **RTL-SIM**. Expected values were fixed before the runs (`observation.md` §2 lists them with their Layer 1 basis).

| Check | Expected | Observed |
|---|---|---|
| Frozen source untouched | sha256 = blob at `PTSG-Core@1b58ebc` | `fb995687…60e0`, equal |
| A..G (P = 1), pin unconnected | pass log and every shared signal identical to RH030 | log identical; 174 signals, 8,376 changes, 0 mismatching |
| T1..T34 (P = 5), pin unconnected | same | log identical; 192 signals, 579,164 changes, 0 mismatching |
| SV-0 lockstep, pin tied 0, P = 1 | 0 mismatching clocks | 600,000 clocks, 0; 17,587 Stays executed (12,268 windowed, 5 Stay(0)) |
| SV-0 lockstep, pin tied 0, P = 5 | 0 | 600,000 clocks, 0; 6,794 Stays (4,790 windowed, 4 Stay(0)) |
| SV-0 Scene 4, 6250 → 20 live | 0; half-periods 25,000 / 25,000 (the SILICON capture of 2026-08-29) | 290,538 clocks, 0; 25,000 / 25,000 twice |
| SV-1 | Stay = N clocks | N = 2, 3, 7, 100, 2048, 4095 → exactly N |
| SV-2 | 1 clock | 1 (loop period 3) |
| SV-3 | 20 then 9 | 20 then 9 |
| SV-4, form B | 37 | 37 |
| SV-4, anti-pattern | 8192 (must fail) | **8192 — fails**, as it must |
| SV-5 | timeup at the first S_WAIT tick | Stay visible 2 clocks, 1 S_WAIT clock; silent-pin contrast: Stay Set → resume 100 |
| SV-5b (supplementary) | Stay Set → Stay Set = max(N, 30), K = 0 … N−1, g = 0 | 29 → 30, 30 → 30, then exactly N for 31, 32, 33, 64, 2048, 4095; K without error |
| SV-6 | 4096 | 4096 (first exercise of C2-F3) |
| SV-7 | 7 / 11 and 7 / 5 | 7 / 11 and 7 / 5 |
| Form A, informative | SV-4, SV-7 fall back to the operands | SV-4 5, SV-7 3 / 5 |

## 4. Deviations from the golden models / 黄金モデルからの逸脱

**None against a golden model.** The Core's own testbenches are the reference for this phase and they are reproduced exactly. One **nominal** is replaced by an RTL-SIM number — the packet floor, §5. / 黄金モデルからの逸脱はない。名目値を一つ RTL-SIM 値で置き換える（§5）。

## 5. Discrepancies filed / 記録した食い違い

- **SD-12 (new).** The profile's documents and the sweep oracle count a 25-instruction packet window as 25 + 4 Core clocks = 29. On this Core a windowed Stay never times up in its own execute clock (RH028's same-clock timeup applies to bare Stays only), so one S_WAIT clock is added: the floor is **30** (SV-5b; reproduction: `run_phase1.sh`, or after one run `vvp 03_Sample_Implementations/hw/core/build/sv_formB +only=55`). N_MIN = 32 holds with two clocks to spare. Reports carry both numbers; Layer 1 is unchanged.
- SD-01 … SD-11 from Phase 0 stand; none is touched by this phase.

## 6. The diff of the copy against the frozen source / 写しと凍結ソースの差分

Summary by kind: RH029/030 header patch as approved (28 history lines, the Tie line, the parameter comment, three inline tags, the two RH tags in the prescaler `always` block — comments and whitespace only) · RH031 draft history entry (17 lines) · Tie list: C4-T5 = form B, C5-T2 = `CNT_W` (2 lines, comments) · **logic: the `stay_value` port, `stay_dur_lit`, and the redefined `stay_dur`** (plus their 5 comment lines).

<details>
<summary>rh030_vs_rh031p.diff (unified, full)</summary>

```diff
--- ptsg_core.v@RH030
+++ ptsg_core_rh031p.v
@@ -42,7 +42,10 @@
 //    C3-T7 insertion flag bit ..... Core carries the "saved-by-insertion" flag
 //    C3-F20 insertion timing ...... deferred to Stay-timeup inside a Stay window
 //    C4-T1 indirect handshake ..... Core stalls until indirect_ready (covers B and C)
-//    C4-T2 prescaler config ....... compile-time fixed (PRESCALE parameter)
+//    C4-T2 prescaler config ....... pin-level prescaler_value with PRESCALE parameter
+//                                   fallback (reference form "B'", RH029, PROVISIONAL)
+//    C4-T5 stay_value sampling .... read in the execute clock (form B; RH031, PROVISIONAL)
+//    C5-T2 stay_value width ....... CNT_W (12 bits; both zero = 4096 stays the maximum)
 //    C4-T4 Stay Set role .......... clear/sync only — the stay counter ticks only
 //                                   during the wait, so background-band length adds
 //                                   no jitter to the wait duration (lean B)
@@ -257,6 +260,51 @@
 //                                          bare Stay-2/Stay-1 loops 5/4 -> exact 4/3 clocks; idiom-D
 //                                          duty @P=1 6:6 -> written 5:5; over-constrained window @P=5
 //                                          runaway -> earliest-tick resume. T1-T33 unaffected.
+// 029 2026-07-16       Arch. Ohnaka  Add : Externally settable prescaler (C4-T2, reference form "B'": pin-level
+//                                          value with parameter fallback, PROVISIONAL). New ports prescaler_value
+//                                          (tri0 input; 0/unconnected => PRESCALE parameter, i.e. option-A
+//                                          behaviour at zero cost) and prescaler_output (reserved, see note).
+//                                          presc_valueM registers (prescaler_value - 1) so the "-1" is off the
+//                                          compare path; presc_tickP compares presc_cnt against presc_valueM
+//                                          (or PRESCALE-1 at zero). Premise (architect, 2026-08-27): the
+//                                          prescaler counter value is not for external use; the prescaler is a
+//                                          base-frequency generator only. Trace: 2026-08-27_ptsg-free-running-
+//                                          fruits (closes 2026-06-23 reset-command-bands Hook E).
+// 030 2026-07-16       Arch. Ohnaka  Mod : One-clock registered tick (Fmax) + raw-tick export (sync).
+//                                          presc_tick <= presc_tickP: the internal tick is now a registered
+//                                          one-clock pulse; every in-core consumer uses it, so the whole tick
+//                                          grid shifts by exactly one clock and all intervals / C4-F9 phase-lock
+//                                          / RH028 collision rules are unchanged (silicon re-confirmation:
+//                                          Hook A). presc_cnt rolls over on the raw presc_tickP. prescaler_match
+//                                          now exports the RAW (pre-register) tick, one clock ahead of the
+//                                          internal tick; consumers must register it — a slave that does so
+//                                          lands coincident with this core's internal tick. Sync delivered =
+//                                          period-sharing (same prescaler_value + common rst + C3-F21);
+//                                          tick-following slave NOT provided (Chapter 6).
+//                                          RULING (architect, 2026-08-27): presc_tickP deliberately uses ==,
+//                                          NOT >=. A prescaler that runs past its terminal is a fatal fault;
+//                                          a loud 2^16-wrap is preferred to a quiet small error (fail-loud).
+//                                          This is the intended asymmetry with RH028's >= on the stay counter.
+//                                          OPEN (architect): prescaler_value==0 test is combinational while presc_valueM is
+//                                          registered (1-clk mismatch at 0<->non-0); prescaler_output is
+//                                          declared but undriven; presc_tick/presc_valueM have no rst.
+// 031 2026-09-27       Arch. Ohnaka  Add : Formation-supplied Stay duration (PROVISIONAL; C4-F15..F17, C5-F4).
+//                                          New optional port stay_value (tri0 [CNT_W-1:0]). IND-reverse, the
+//                                          RH029 pattern applied to Stay: stay_value != 0 => that value;
+//                                          0/unconnected => the operand (0 => 4096, C2-F3). stay_dur is the
+//                                          single substitution point, so the duration is read ONCE, at the
+//                                          Stay's execute clock, and held in stay_target for the whole Stay
+//                                          (a pin change mid-Stay affects later Stays only). RH028 >= applies
+//                                          unchanged. Zero test and value are one sample (never a raw-pin zero
+//                                          test beside a registered value: 0->N would latch 0 => 8192-tick
+//                                          runaway). Requirement: WPMS packet length = Stay length.
+//                                          Trace: 2026-09-26_ptsg-stay-value-from-formation.
+//                                          Header Tie list: C4-T5 = form B (execute clock), C5-T2 = CNT_W.
+//                                          NUMBER PROVISIONAL: applied by Claude Code on a working copy
+//                                          (PTSG-WPMS-Formation 03_Sample_Implementations/hw/core/
+//                                          ptsg_core_rh031p.v, SILICON_BRIEF_2026-09-27 Phase 1); the Core's
+//                                          office assigns the RH number and date at its checkpoint. The
+//                                          frozen RH030 source is untouched.
 //
 // ============================================================================
 
@@ -270,7 +318,7 @@
                                                   // extended operand (architect ruling 2026-07-07;
                                                   // supersedes the 12-bit C3-V2 reading)
     parameter integer IMEM_DEPTH  = 256,          // Instruction-memory depth (<= 4096)
-    // ---- Prescaler (C4-T2 option A: compile-time fixed) ---------------------
+    // ---- Prescaler (C4-T2 form B': pin-level value, PRESCALE = fallback) -----
     parameter integer PRESCALE    = 6250,         // System-clock divider for the time axis (>=1)
     parameter integer PRESC_W     = 16,           // Prescaler counter width
     // ---- External stack data layout ----------------------------------------
@@ -321,6 +369,9 @@
     input  tri0 [PRESC_W-1:0]   prescaler_value             , // RH029
     output wire [PRESC_W-1:0]   prescaler_output            , // RH029
 
+    // ---- Formation-supplied Stay duration (§5.12a, RH031 PROVISIONAL) --------
+    input  tri0 [CNT_W-1:0]     stay_value                  , // RH031: 0/unconnected => Stays as written
+
     // ---- Indirect-read bus (§5.11) ------------------------------------------
     output wire                 indirect_req,
     output wire [1:0]           indirect_purpose, // 00 = Jump, 01 = Loop target
@@ -454,8 +505,8 @@
     // Prescaler (free-running) -----------------------------------------------
     reg [PRESC_W-1:0] presc_cnt;
     reg [PRESC_W-1:0] presc_valueM;
-    wire              presc_tickP = (presc_cnt == ((prescaler_value == 0) ? (PRESCALE-1) : presc_valueM));  //RH029: prescaler_value override (C4-T2 option B, PROVISIONAL)
-    reg               presc_tick;  // RH030    -cycle pulse, synchronous to clk, at every prescaler tick
+    wire              presc_tickP = (presc_cnt == ((prescaler_value == 0) ? (PRESCALE-1) : presc_valueM));  //RH029: prescaler_value override (C4-T2 form B', PROVISIONAL); raw tick
+    reg               presc_tick;  // RH030: registered one-clock pulse, one clk after presc_tickP; the only tick the FSM uses
 
     // Indirect-read latch ----------------------------------------------------
     reg               ind_is_loop;      // 0 = indirect Jump, 1 = indirect Loop target
@@ -576,12 +627,17 @@
     assign loop_counter       = loop_cnt;
     assign stay_counter       = stay_cnt[CNT_W-1:0];
     assign prescaler_counter  = presc_cnt;
-    assign prescaler_match    = presc_tickP;    // RH030: prescaler_value override (C4-T2 option B, PROVISIONAL)
+    assign prescaler_match    = presc_tickP;    // RH030: RAW tick export (1 clk ahead of presc_tick; consumer registers)
 
     // ========================================================================
     //  Resolved Stay duration: literal-zero-as-escape => 4096 (C2-F3)
+    //  RH031 (PROVISIONAL): IND-reverse, the RH029 pattern applied to Stay (C4-F15):
+    //    stay_value != 0 => stay_value ; else operand ; operand 0 => 4096 (C2-F3).
+    //    Read in the execute clock (C4-T5 form B) and latched by OP_STAY into
+    //    stay_target (C4-F16). The zero test and the value are ONE sample (C5-F4).
     // ========================================================================
-    wire [CNT_W:0] stay_dur = (operand == 12'd0) ? (1'b1 << CNT_W) : {1'b0, operand};
+    wire [CNT_W:0] stay_dur_lit = (operand == 12'd0) ? (1'b1 << CNT_W) : {1'b0, operand};
+    wire [CNT_W:0] stay_dur     = (stay_value != {CNT_W{1'b0}}) ? {1'b0, stay_value} : stay_dur_lit;
 
     // Loop "increment-then-compare" helper (combinational) -------------------
     //   target == 0           -> exit immediately, 0 iterations (C4-V1)
@@ -630,8 +686,9 @@
         (state_num + 1'b1);
 
     always @(posedge clk) begin
-        // RH030: prescaler tick pulse, synchronous to clk, at every prescaler tick
-        presc_tick <= presc_tickP;
+        // RH030: registered one-clock tick, one clk after presc_tickP
+        presc_tick   <= presc_tickP;
+        // RH029: pre-decremented compare value, registered off the compare path
         presc_valueM <= prescaler_value - 1;
     end
 
```

</details>

## 7. Questions for the architect / アーキテクトへの質問

1. **The RH031 draft entry.** It follows sketch §8 (author "Arch. Ohnaka", as the sketch drafts it) and adds a provenance note; the header's Tie list gains two lines (C4-T5 form B, C5-T2 `CNT_W`). Keep these for the Core's office, or leave the Tie list to the office? / RH031 下書きと Tie 一覧の2行はこのままでよいか。
2. **SD-12.** Accept 30 (RTL-SIM) as the floor to be re-measured in Phase 3 and on silicon, with N_MIN = 32 unchanged? / 下限 30 を Phase 3 と実機で再測定する前提で受け入れてよいか。
3. **The Phase 0 questions** (E1/E2 validator-only; SSS substitute; the queued-Branch not-taken address; the width of I) remain open and are needed before Phases 2–3. / Phase 0 の4問は Phase 2–3 の前に要る。

## 8. Resource numbers / 資源数

Not measured: no Quartus in this container. By construction the change adds a 12-bit zero test and a 13-bit 2:1 multiplexer in front of the existing `stay_dur − 1` compare and `stay_target` latch; no register. The Core's ledger (RH028: 441.8 ALMs full trim) is to be re-read at the Phase 6 compile, together with timing on the new path `stay_value → mux → −1 → compare` (the bare same-clock timeup). / Quartus がないため未測定。変更は 12 ビットのゼロ判定と 13 ビット 2:1 選択器のみでレジスタは増えない。Phase 6 で台帳とタイミングを再読する。

---

*Stopped at the end of Phase 1, as instructed. / 指示どおり Phase 1 の終わりで停止する。*
