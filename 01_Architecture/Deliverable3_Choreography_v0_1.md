# PTSG-WPMS-Formation — Deliverable 3
# The Choreography: Sweep, Packets, Housekeeping / 振付——掃引・パケット・ハウスキーピング

*v0.1 DRAFT · WPMS-Formation amanuensis · 2026-09-26 · CC0.*
*Anchored in Decision Register W v0.6 as **W-F20** (choreography), **W-F19** (Condition lanes, ruled to live here), W-F22/W-F28 (Stay-value path, sequencer). Answers WPMS Ch.3 §3.7–3.8 (CR3-T1, T2, C1, M1) and Ch.5 §5.10 (CR5-I1…I3, S1, L1, R1), and PTSG-Core's trace 2026-09-26 Hook A. Register map: v0.3; consumer interface: Deliverable 2.*

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

## 3. The Core score — a sketch / Core の楽譜——素描

Encodings belong to PTSG-Core. The sketch states the behaviour the profile needs; two realizations of the packet repetition are given, and the Core chooses (its g = 0 commitment of 2026-09-26 applies to either).

```
; header: packet Stays in this score are Formation-timed — stay_value supersedes their operands (C5-V8)
SLEEP: Branch 0                 ; lane STROBE (TS_CSEL); self-loop until the synchronized strobe
       Branch +→HK              ; lane NONEMPTY; false (P = 0) → forward to HK            [1 clock]
PKTq:  Global  Stay Set         ; TS_PKT = 1 · K := 0 · packet_start · L1 latches the bundle
       Global  wpms_packet      ; 25 Formation instructions, immediate band
       Global  Prog End
       <queued transfer>        ; at Stay-timeup: MORE → next packet's Stay Set, else → HK
       Stay    32               ; TS_PKT = 1 · TS_CSEL = MORE · operand not authoritative (N_MIN as a safe default)
HK:    Global  Stay Set         ; TS_PKT = 0
       Global  wpms_housekeeping; BCP
       Global  Prog End
       Stay    T_HK             ; stay_value = 0 here, so the literal applies (IND-reverse)
       Jump    SLEEP
```

**Realization R1 — unrolled positions.** Eight copies of PKTq (q = 0…7) in instruction memory; the queued transfer at each timeup is a forward conditional: MORE → PKT(q+1), else → HK. Needs only forward transfers; costs ≈ 8 × 30 words of the 4,096.
**Realization R2 — one packet body.** A queued re-entry to Base (= Stay Start State) while MORE holds. Needs a conditional backward transfer at timeup, or a loop count supplied as data (P).

Either way the profile issues **no Q-band command** at a packet boundary (it has no Q citizen), so the Core's single reservation slot (C3-F26) is free for this transfer. Under the retracted Mode T every packet would have queued a CMT *and* needed a transfer — the E7 conflict would have forced a gap.

---

## 4. Condition lanes and timing-signal bits (W-F19) / Condition レーンとタイミング信号

The Core has one Condition input. The profile drives it from three lanes, selected by two timing-signal bits of the word being executed (or held):

| TS_CSEL | Lane | Source | Used by |
|---|---|---|---|
| 0 | **STROBE** | synchronized audio strobe S_m (WPMS Ch.4 §4.3) | SLEEP's Branch 0 (CR3-T2) |
| 1 | **NONEMPTY** | P of SWEEP.a > 0 | the empty-sweep check after wake |
| 2 | **MORE** | q + 1 < P (sequencer) | the queued transfer at each packet timeup |
| 3 | — | reserved | — |

Profile-assigned timing-signal bits: **TS_PKT** (Deliverable 2: `bin_valid`, `packet_start`) and **TS_CSEL[1:0]**. As in Deliverable 2, bits that must be valid during a window are written in both the Stay Set word and the Stay word, so the held value is right under every option of Core Tie C3-T1. The other thirteen timing signals are free.

**No inbox-ready lane.** The take-set is latched by the sequencer on the strobe, and BCP is a no-op for an empty take-set, so the program never branches on GO traffic. **inbox-taken** is an output lane, raised by BCP (CR5-I3).

---

## 5. The Stay-value path / Stay 値の経路

PTSG-Core (CHANGES 2026-09-26, PROVISIONAL): optional input `stay_value`, IND-reverse — pin ≠ 0 → pin; pin = 0 → operand; operand 0 → 4096 (C4-F15); read once, at the Stay instruction's execute clock, and held for the Stay (C4-F16).

The profile drives the pin from **StayVal.p** (W-F22):

- The sequencer loads **StayVal.s ← N of the next packet's block** when it prefetches that block's bundle (during the previous packet, or after HK for the first packet). EW2 refuses N outside [N_MIN, NMAX].
- At every Stay Set, **StayVal.p ← StayVal.s if TS_PKT = 1, else 0**. The value is therefore stable from the packet's Stay Set to the next Stay Set, which covers the Stay's execute clock under either sampling path of Core Tie C4-T5.
- WSV is RESTRICTED in this profile (W-F28): the sequencer is the only writer, so the pin can never disagree with the block L1 is playing.

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

**N_MIN.** The Stay reads N after the window; if the window plus Prog End, the queued transfer and the Stay's own execute clock reach N, the Stay times out on its first tick and the packet grows. With 25 window clocks and 4 Core clocks, N ≥ 29; the profile constant is **N_MIN = 32**. Oracle-counted; measured in Layer 4.

### 6.2 Housekeeping window — `wpms_housekeeping.pfasm` (1 instruction)

`BCP` — lands the take-set (≤ 10 clocks in the slot-parallel reference), then the sequencer prefetches the next sweep's first bundle and Stay value from the (possibly new) SWEEP.a.

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

| Seeds | Samples | Packet plays | GOs (of which full-load) | Mismatches | Worst sweep |
|---|---|---|---|---|---|
| 2026, 7, 42 | 60,000 | 215,627 | 4,174 (1,175) | **0** | 2,064 of 2,083 clocks |

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
| T_wake | 2 nominal (Branch-0 wake + NONEMPTY), ≤ 4 | Core | Core commitment; Layer 4 |
| g | 0 | Core | Core commitment; Layer 4 |
| Σ N_p | ≤ NMAX = 2,048 | program / switch | EW5 backstop |
| T_HK | Stay Set + BCP (≤ 10) + Prog End + Stay ≈ 13 | profile | oracle-counted |
| T_pf | 1 (slot-parallel) | profile | Arena |
| D_L1 | ≤ 24 | WPMS Ch.3 | Layer 4 |

At full load: L2 side 2 + 2,048 + 13 + 1 = **2,064** (19 spare, as in the oracle); L1 side 2 + 2,048 + 24 = **2,074** (9 spare). A word-serial BCP (≈ 17 clocks per block) would need T_HK ≈ 142 and bring NMAX down to about 1,920 — the design variable the architect has kept for exactly this kind of trade.

---

## 10. W-R5 — where exp() lives / exp の置き場所

Moot on the WPMS hot path: with log-domain amplitude (W-F29, ruled 2026-09-26), exp exists only as L1's feed-forward exp2 unit; neither L2 nor L4 evaluates it. The two options the architect asked to keep are recorded for other programs: (a) the W1 gift `exp_maclaurin_w.pfasm` runs in a non-packet window (27 instructions, CLEAN, same numerics) when a light sweep leaves the time; (b) the external controller computes it.

---

## 11. Answers to PTSG-Core, trace 2026-09-26, Hook A / Core への回答

| Question | Answer |
|---|---|
| (1) One Formation-timed length per program, or per packet? | **Per packet.** Each packet Stay has the N of the block it plays; the same score position plays different blocks as the sweep word changes. |
| (2) Fixed-length Stays mixed with Formation-timed ones? | **Yes:** one housekeeping Stay per sweep with a literal length. The profile drives `stay_value` = 0 there, so IND-reverse leaves the literal in force. |
| (3) Driver: constant, `len_lut[state_number]`, or a sequencer? | **A sequencer** (idiom iii), paced by the profile's own packet starts: it knows the next packet's N one packet ahead. It does not need `stay_cnt_match`. |
| (4) Longest Stay at the intended P? | P = 1; longest packet NMAX = **2,048** ticks, shortest N_MIN = 32, housekeeping ≈ 13. **12 bits suffice → C5-T2 (A) `CNT_W`** fits WPMS. |
| (5) Clock domain of the source? | **clk_sys**, the Core's own clock; no synchronizer (C5-F1). |
| Starting question: does every Formation-timed Stay find its length from `state_number` alone? | **No.** Even with unrolled positions (R1), a position's length depends on the sweep word, which is data. |
| C4-T5 sampling path | WPMS works under **(A) and (B)**: StayVal.p is stable from the packet's Stay Set to the next Stay Set, and the Stay executes after the window. No preference from this profile. |
| DP-2 (IND-reverse vs IND) | IND-reverse is workable (the profile drives 0 outside packet Stays). IND would let the score document itself (Stay(0) marks Formation-timed Stays) — a readability gain, not a need. **No request to reopen.** |

---

## 12. Open items and Layer 4 measurements / 未決事項と実測項目

| Item | Path |
|---|---|
| g = 0 across packet Stays; T_wake ≤ 4 | Core; Layer 4 |
| Realization R1 or R2 of the packet repetition | Core (via the architect) |
| N_MIN (window clocks + Core clocks) on silicon | Layer 4 |
| BCP duration in the chosen store organization | Layer 4; NMAX follows (§9) |
| Paused-block reading of CR3-C1 | customer confirmation |

---

## 13. Customer requirements answered / 顧客要求への回答

| CR | Answer |
|---|---|
| CR3-A1 | Adopted (W-F29): slots and advance laws per Appendix 5.A.2; four-term advance = three ADD + one STP. |
| CR3-T1 | Profile side met (§3, §9); Core commitment. |
| CR3-T2 | Nominal 2, ≤ 4 (§9); Core commitment. |
| CR3-C1 | By construction (§8); oracle evidence; paused-block reading to confirm. |
| CR3-M1 | One Core + one L2 Formation per module, same score and windows in every module; sharing instruction memory between modules is Arena. |
| CR5-I1 | BCP (§7); mask and staged RT.OUT readable at 0x110–0x117 and inbox +0xE. |
| CR5-I2 | Bound **one sweep** (§7, §9). |
| CR5-I3 | inbox-taken raised by BCP (§4, §7). |
| CR5-S1 | SWEEP.a, landed by BCP, exactly once; EW5 checks. |
| CR5-L1 | STP in every packet window (§6.1). |
| CR5-R1 | Reset = empty sweeps; no test-origin logic in the profile (§7). |

---

*End of Deliverable 3 v0.1.*
