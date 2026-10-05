# PTSG-WPMS-Formation — Deliverable 3
# The Choreography: Sweep, Packets, Housekeeping / 振付——掃引・パケット・ハウスキーピング

*v0.2 DRAFT (as built) · WPMS-Formation amanuensis · 2026-10-05 · CC0.*
*Changes from v0.1: the **dispatch form** of the score is the standard (ruled 2026-09-29) and §3 describes it; R2 is not available in the Core as built (SD-04); the lane select, the error strobe and SSS as built (SD-14, SD-06, SD-03); the budget and the coherence evidence carry SILICON numbers (2026-10-04); §14 lists what comes next. Anchored in Decision Register W v0.8 as **W-F20** (choreography), **W-F19** (Condition lanes, ruled to live here), W-F22/W-F28 (Stay-value path, sequencer). Answers WPMS Ch.3 §3.7–3.8 (CR3-T1, T2, C1, M1) and Ch.5 §5.10 (CR5-I1…I3, S1, L1, R1), and PTSG-Core's trace 2026-09-26 Hook A. Register map: v0.3; consumer interface: Deliverable 2.*

*成果物 3。一サンプル周期の中で、Core・L2 Formation・シーケンサ・L1 が誰がいつ何をするかを定める。Core の符号化は Core の所有であり、本書は必要な振る舞いと、それを満たす素描を示す。*

---

## 1. Who acts in which period / 周期と担い手

| Period | Rate | Actor | What happens |
|---|---|---|---|
| L1 bin | 100 MHz, one bin per clock | L1 pipeline | difference engine on the latched bundle, indexed by K |
| L2 packet | one Stay | Core + L2 Formation + sequencer | Stay Set → bundle latch → packet window (advance) → Stay-timeup |
| L3 sample | 48 kHz, one sweep | Core score + sequencer | strobe wake → packets → housekeeping (GO landing) → sleep |
| L4 control | ≈ 1 kHz, external | outside WPMS (L4 Formation, first a verification tool) | writes the inbox, arms, fires GO |

---

## 2. One sweep / 一掃引

```
strobe S_m ─► wake ─► [P > 0 ?] ─► PKT(order[0]) ─► PKT(order[1]) ─► … ─► PKT(order[P-1]) ─► HK ─► sleep
               │                     │ Stay Set: L1 latches bundle; K = 0                     │ BCP: take-set lands
               │                     │ window: advance CUR block (25 instr.)                  │ inbox-taken
               │                     │ sequencer prefetches order[q+1]                        │ prefetch order'[0]
               └─ take-set latched   └ Stay-timeup = next Stay Set (g = 0)                    └ Stay T_HK, then sleep
```

Only two kinds of Stay exist: **packet Stays** (Formation-timed, N clocks) and one **housekeeping Stay** per sweep (literal length T_HK). An empty sweep goes straight from wake to housekeeping.

---

## 3. The Core score — the dispatch form, as built / Core の楽譜——ディスパッチ形（as built）

Encodings belong to PTSG-Core; the score below is the profile's, written in Phase 3 (`hw/tools/gen_scores.py`, `wpms_r1d`) and played on silicon on 2026-10-04 (C1–C5). Of the two realizations of v0.1, **R2 (one body re-entered by data) does not exist gap-free in the Core as built**: a queued Loop never performs the indirect read, so its count is a literal (SD-04, `r2_probe.py`). The **branch form** (R1-B: a foreground Branch after each Stay) costs one clock per packet (SD-05). The standard is the **dispatch form** (R1-D):

- The packet body is unrolled eight times (positions 0 … 7), each position ending in an **unconditional queued Jump** to the next; the last leads to housekeeping. No conditional transfer anywhere, nothing saved on the Core's stack.
- In front of each entry into the chain stands a **sleep state** SLEEP_P (Branch 0 on the STROBE lane), one per P = 0 … 8: waking SLEEP_P enters the chain at position 8 − P, so exactly P bodies play; SLEEP_0 leads straight to housekeeping.
- The **housekeeping window** of sweep n ends by computing, from SWEEP.a, which sleep state the next sweep needs, and writes it with **WJV** — a background computed dispatch (W-T3 intact). The Core's background indirect Jump (operand 0, the indirect-read lane) takes it there, and the queued Jump of housekeeping's own Stay settles the Core in that SLEEP_P before the next strobe.
- Measured: the first packet's Stay Set is **1 clock** after the strobe (the L1 face sees it at 2, SD-11); **g = 0** between packets (SILICON C2, 8 packets).

```
SLEEP_8: Branch 0 (STROBE)                    ; wake → position 0
PKT0:    Stay Set · wpms_packet (25) · Prog End · Jump(Q) → PKT1 · Stay 32   ; TS_PKT = 1
PKT1 … PKT7: the same, chained
HK:      Stay Set · wpms_housekeeping (BCP, dispatch) · Prog End · Jump(Q) → SLEEP_P · Stay T_HK
SLEEP_7: Branch 0 (STROBE)                    ; wake → position 1
…
SLEEP_0: Branch 0 (STROBE)                    ; wake → HK
```

The profile issues **no Q-band command** of its own: the Core's single reservation slot (C3-F26) carries the chain's queued Jumps. The error strobe reaches the Core through the **insertion port** (SD-06): `insert_req` → TRAP, where the score places a foreground Prog End (C3-F23 → C3-F24 HALT); the Formation withdraws the request in the clock `insert_ack` is high (SD-15).

## 4. Condition lanes and timing-signal bits (W-F19) / Condition レーンとタイミング信号

The Core has one Condition input. The profile drives it from three lanes, selected by two timing-signal bits of the word being executed (or held):

| TS_CSEL | Lane | Source | Used by |
|---|---|---|---|
| 0 | **STROBE** | synchronized audio strobe S_m (WPMS Ch.4 §4.3) | SLEEP's Branch 0 (CR3-T2) |
| 1 | **NONEMPTY** | P of SWEEP.a > 0 | the branch form only (bring-up); unused by the dispatch form |
| 2 | **MORE** | q + 1 < P (sequencer) | the branch form only; unused by the dispatch form |
| 3 | — | reserved | — |

Profile-assigned timing-signal bits: **TS_PKT** (Deliverable 2: `bin_valid`, `packet_start`) and **TS_CSEL[1:0]**. The Core's `timing_signals` are registered, so a word's bits appear one clock after it executes: **the CSEL for a foreground Branch is carried by the word before it** (SD-14, ruled 2026-09-28 (a)); the Core as built resolves C3-T1 as (A), the Stay word's bits held during the wait. The other thirteen timing signals are free. **SSS** (source ID 6) is not exported by the Core as built; the sequencer substitutes the Stay Set's address, latched at every Stay Set (SD-03).

**No inbox-ready lane.** The take-set is latched by the sequencer on the strobe, and BCP is a no-op for an empty take-set, so the program never branches on GO traffic. **inbox-taken** is an output lane, raised by BCP (CR5-I3).

---

## 5. The Stay-value path / Stay 値の経路

PTSG-Core (CHANGES 2026-09-26, PROVISIONAL): optional input `stay_value`, IND-reverse — pin ≠ 0 → pin; pin = 0 → operand; operand 0 → 4096 (C4-F15); read once, at the Stay instruction's execute clock, and held for the Stay (C4-F16).

The profile drives the pin from **StayVal.p** (W-F22):

- The sequencer loads **StayVal.s ← N of the next packet's block** when it prefetches that block's bundle (during the previous packet, or after HK for the first packet). EW2 refuses N outside [N_MIN, NMAX].
- At every Stay Set, **StayVal.p ← StayVal.s if TS_PKT = 1, else 0**. The value is therefore stable from the packet's Stay Set to the next Stay Set, which covers the Stay's execute clock under either sampling path of Core Tie C4-T5.
- WSV is RESTRICTED in this profile (W-F28): the sequencer is the only writer, so the pin can never disagree with the block L1 is playing. As built: `stay_value` is the provisional RH031 on the Core copy (one port, two wires); the pin read 0 at every housekeeping Stay over 164,321 Stays (RTL-SIM).

---

## 6. The BG windows / 裏の窓

### 6.1 Packet window — `wpms_packet.pfasm` (25 instructions)

```
SAD 0x105 · LDM · SWP · SAD 0x102 · LDM · SAD 0x109 · STP @PPM · SAD 0x102 · STM     ; LP glides toward LPT at rate LE0
SAD 0x106 · LDM · SAD 0x10A · ADD @PPM · SAD 0x106 · STM                            ; PH0  += OM0
LDM · SAD 0x10B · ADD @PPM · SAD 0x107 · STM                                        ; PHD1 += OMD1
LDM · SAD 0x10C · ADD @PPM · SAD 0x108 · STM                                        ; PHD2 += OMD2
```

Addresses `0x10x` are the CUR alias: the same program serves every packet, and the sweep word decides which block it touches — no pointer arithmetic (W-F1 kept) and no computed branch (W-T3 kept). No MUL, no SHV: the log-domain amplitude (W-F29) makes the whole advance additive except for the one STP.

**N_MIN.** The Stay reads N after the window; a windowed Stay never times up in its own execute clock, so it needs one S_WAIT clock more than the v0.1 count (SD-12): with 25 window clocks the Core's floor is **30** — measured RTL-SIM (SV-5b) and SILICON (C1, C2: window 28 → floor 30). The profile constant **N_MIN = 32** holds with 2 clocks of margin.

### 6.2 Housekeeping window — `wpms_housekeeping.pfasm` (1 instruction)

`BCP` lands the take-set (**10 clocks** for a full take-set, 2 for a small one — SILICON C1, C2), then the dispatch computation (P from SWEEP.a → the sleep state → WJV) closes the window; the sequencer prefetches the next sweep's first bundle and Stay value from the (possibly new) SWEEP.a.

---

## 7. The inbox protocol / inbox の手順 (CR5-I1…I3, S1, R1)

1. **Stage and arm** (writer, any time): values into the inbox, mask into COMMIT[b], RT.OUT into RTOUT[b]; the sweep item likewise (WPMS Ch.5 §5.4).
2. **Strobe** (sequencer): take-set ← everything armed now.
3. **Sweep n** plays with the old values; each listed block is advanced once, in its own window.
4. **HK of sweep n**: BCP copies the take-set — masked slots, RT.OUT on bit 16, the sweep item into SWEEP.a — and raises **inbox-taken**. The switch unfreezes and publishes APPLIED_SEQ, APPLIED_SAMPLE = n + 1.
5. **Sweep n + 1** is the first to play the new values, in every module on the same sample (one strobe, one HK per module).

**Bound (CR5-I2): one sweep**, for any take-set, because BCP fits HK at full load (§9). **Continuity (Ch.5 §5.3)** follows from the order of steps 3 and 4: a retune changes increments from the next sweep on and never touches [S]; a re-seed defines the [S] state of sweep n + 1 exactly. **Level glide (CR5-L1)**: STP in every packet window; LE0 = 0 freezes; LPT is reached exactly and never overshot. **Reset (CR5-R1)**: SWEEP.a = P = 0; the Formation runs empty sweeps and accepts the inbox from the first strobe; the switch's ROM port supplies the test origin.

---

## 8. The coherence invariant (CR3-C1) / 一貫性の不変量

**Statement (profile's reading).** For every block b listed in sweep n, the bundle L1 latches equals b's state after exactly one advance per earlier sweep in which b was listed since its last re-seed, with [P] slots as last landed by BCP. A block not listed does not advance (it pauses and resumes from where it stopped) — the customer is asked to confirm this reading for paused blocks.

**Proof sketch.**
(i) In a packet window only the CUR block is writable (EW4), and a sweep lists a block once (EW5): each listed block is advanced exactly once per sweep, unlisted blocks never.
(ii) That advance follows the block's latch in sweep n (the window follows the Stay Set) and precedes its latch in sweep n + 1.
(iii) BCP writes happen in HK, after every latch and advance of sweep n and before any latch of sweep n + 1.
(iv) Every prefetch reads a block that no remaining window of the sweep can write — order[q+1] ≠ order[q], or it is read after HK.
Hence each latch sees one consistent state per sample: never zero advances for a listed block, never two.

**Evidence (oracle, not silicon).** `sweep_sim.py` runs the real window programs on the profile machine under a model of the sequencer and compares every latched bundle with a reference written from WPMS Ch.3 §3.4.3 and Ch.5 §5.3–5.4, taking the glide law from the customer's own `step_toward` (wpms_layer1_oracle.py):

| Class | Run | Result |
|---|---|---|
| ORACLE | `sweep_sim.py`, seeds 2026, 7, 42 | 60,000 samples · 215,627 packet plays · 4,174 GOs (1,175 full-load) · **0 mismatches** · worst sweep 2,064 of 2,083 |
| RTL-SIM | Core + Formation + sequencer (Phase 3) | 36,000 sweeps · 128,321 packets · 54 million bins at each budget · every bundle, N, K sequence and `stay_value` identical · 11/11 mutants caught |
| SILICON | C1–C3 (2026-10-04) | **45 bundles and 12 banks equal to the model**; g = 0; a C-major chord after one GO, as expected |

A mutant window that advances PH0 twice is caught at once (2,798 mismatches in 3,000 samples); `negative_tests.py` shows every profile rule rejecting what it should (13/13).

---

## 9. The timing budget / 時間予算

Per module, per sample period (T_min = 2,083 clocks):

```
L2 side:  T_wake + Σ N_p + T_HK + T_pf  ≤  T_min        (packets back to back, g = 0)
L1 side:  T_wake + Σ N_p + D_L1        ≤  T_min        (WPMS Ch.3 §3.7; L1 drains while HK runs)
```

| Term | Value | Owner | Status |
|---|---|---|---|
| T_wake | **2** (Core Stay Set 1, the face 2) | Core / profile | **SILICON** (C1, C2) |
| g | **0** | Core | **SILICON** (C2) |
| Σ N_p | ≤ NMAX (1,008 at 50 MHz; 2,048 at 100 MHz L1) | program / switch | EW5 backstop |
| T_HK | BCP **10** + dispatch + Stay — inside the 1,023 total | profile | **SILICON** |
| T_pf | 1 (slot-parallel) | profile | as built |
| D_L1 | 19 bins | WPMS Ch.3 | RTL-SIM (Phase 4) |

**As built at 50 MHz (NMAX 1,008):** the full-load sweep takes **1,023 of 1,041** clocks (SILICON C1, C2; 18 spare on the short sweeps of the 1,041/1,042 alternation). At the 100 MHz budget the RTL-SIM worst sweep is 2,062 of 2,083. **Under the proposed half-rate Stay (W-F37)** — L1 at 100 MHz, L2 at 50 MHz, NMAX 2,048 bins = 1,024 L2 clocks — the same overhead leaves **2 L2 clocks** on 1,041-clock sweeps: housekeeping must not grow, which is why V-K's per-packet coefficients are proposed to come through the packet output table (W-F38) rather than through extra housekeeping instructions.

---

## 10. W-R5 — where exp() lives / exp の置き場所

Moot on the WPMS hot path: with log-domain amplitude (W-F29, ruled 2026-09-26), exp exists only as L1's feed-forward exp2 unit; neither L2 nor L4 evaluates it. The two options the architect asked to keep are recorded for other programs: (a) the W1 gift `exp_maclaurin_w.pfasm` runs in a non-packet window (27 instructions, CLEAN, same numerics) when a light sweep leaves the time; (b) the external controller computes it.

---

## 11. Answers to PTSG-Core, trace 2026-09-26, Hook A / Core への回答

| Question | Answer |
|---|---|
| (1) One Formation-timed length per program, or per packet? | **Per packet.** Each packet Stay has the N of the block it plays; the same score position plays different blocks as the sweep word changes. (Confirmed on silicon: C2, eight different N.) |
| (2) Fixed-length Stays mixed with Formation-timed ones? | **Yes:** one housekeeping Stay per sweep with a literal length. The profile drives `stay_value` = 0 there, so IND-reverse leaves the literal in force. |
| (3) Driver: constant, `len_lut[state_number]`, or a sequencer? | **A sequencer** (idiom iii), paced by the profile's own packet starts: it knows the next packet's N one packet ahead. It does not need `stay_cnt_match`. |
| (4) Longest Stay at the intended P? | P = 1; longest packet NMAX = **2,048** ticks, shortest N_MIN = 32, housekeeping ≈ 13. **12 bits suffice → C5-T2 (A) `CNT_W`** fits WPMS. |
| (5) Clock domain of the source? | **clk_sys**, the Core's own clock; no synchronizer (C5-F1). |
| Starting question: does every Formation-timed Stay find its length from `state_number` alone? | **No.** Even with unrolled positions, a position's length depends on the sweep word, which is data. |
| R2 (v0.1 §3) | **Not available as built**: a queued Loop takes a literal count and never reads the indirect lane (SD-04). No INT-R1 request for now (ruled 2026-09-29); the dispatch form gives g = 0 without it. |
| C4-T5 sampling path | WPMS works under **(A) and (B)**: StayVal.p is stable from the packet's Stay Set to the next Stay Set, and the Stay executes after the window. No preference from this profile. |
| DP-2 (IND-reverse vs IND) | IND-reverse is workable (the profile drives 0 outside packet Stays). IND would let the score document itself (Stay(0) marks Formation-timed Stays) — a readability gain, not a need. **No request to reopen.** |

---

## 12. Open items / 未決事項

| Item | Path |
|---|---|
| SD-02: external Globals in FG not halted by the Core | Core office (W-R21) |
| SD-01, SD-03: band on the issue port; SSS export | Core office |
| Paused-block reading of CR3-C1 | customer (PR-4) |
| The 100 MHz L1 under a 50 MHz L2 (W-F37) | Layer 4 after W-R18 |

## 13. Customer requirements answered / 顧客要求への回答

| CR | Answer |
|---|---|
| CR3-A1 | Adopted (W-F29): slots and advance laws per Appendix 5.A.2; four-term advance = three ADD + one STP. |
| CR3-T1 | **Met on silicon**: g = 0 (C2). |
| CR3-T2 | **Met on silicon**: T_wake 2 (C1, C2). |
| CR3-C1 | By construction (§8); ORACLE, RTL-SIM and SILICON evidence; paused-block reading to confirm. |
| CR3-M1 | One Core + one L2 Formation per module, same score and windows in every module; sharing instruction memory between modules is Arena. |
| CR5-I1 | BCP (§7); mask and staged RT.OUT readable at 0x110–0x117 and inbox +0xE. |
| CR5-I2 | Bound **one sweep** (§7, §9); BCP 10 clocks on silicon. |
| CR5-I3 | inbox-taken raised by BCP (§4, §7). |
| CR5-S1 | SWEEP.a, landed by BCP, exactly once; EW5 checks. |
| CR5-L1 | STP in every packet window (§6.1). |
| CR5-R1 | Reset = empty sweeps; no test-origin logic in the profile (§7). |

---

## 14. Next / 次

| Proposed | Row | Effect on this choreography |
|---|---|---|
| W-R18 | half-rate Stay (W-F37) | N even and ≥ 64; StayVal = N/2; the face gains bit −1; margin 2 L2 clocks at NMAX 2,048 |
| W-R19 | packet output table (W-F38) | per-packet sums of two samples ago readable in any window; the first ISA-level modulation routing |
| W-R20 | Kuramoto Mode (V-K) | a cosine view before each stateful packet in the sweep word; coefficients per packet through W-F38 |

*End of Deliverable 3 v0.2.*
