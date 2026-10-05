# PTSG-WPMS-Formation — Verification Scenario V-K
# Kuramoto Mode: Rotor State Memory and Packet Views / 検証シナリオ V-K：回転子状態メモリとパケットの眺め

*v0.1 DRAFT · WPMS-Formation amanuensis · 2026-10-02 · CC0 · rows first (F-F8).*
*Status: **profile-initiated extension, found during verification.** Not a customer requirement; the customer is notified (PR-6). Public name: **Kuramoto Mode.** Proposed Register W rows W-F31 … W-F36 (to be ruled).*

*要旨：プロファイルの機能検証——回転子ごとの状態メモリと、パケットを「回転子集合に対する眺め」として番地付けする仕組み——を進めると、平均場型の蔵本模型がそのまま成立する。本章はそのために足す行だけを定める。既存のパケットの振る舞いは一ビットも変わらない。*

---

## 0. What this scenario adds, in one paragraph / 一段落で

Today every bin's phase is generated each sample from its packet's closed form. This scenario lets a packet declare that its rotors **keep their own phase** in a memory (STATEFUL), and lets another packet **look at the same rotors** through a fixed phase offset without touching them (VIEW). A view offset by +π/2 turns the one sine core into a cosine source. Two accumulators sum the sines and the cosines; the L2 Formation's housekeeping program multiplies the closed sums by K and hands two coefficients back; each stateful rotor then adds `K·S/N·cos θ − K·C/N·sin θ` to its phase every sample. That is the Kuramoto model in its mean-field form, at one sample delay, on **R = NMAX/2 rotors** (504 at 50 MHz, 1,024 at 100 MHz). Packets that do not declare a mode behave exactly as before.

---

## 1. Rows / 行

### VK-1 Rotor state memory (W-F31)

| Item | Law |
|---|---|
| Entries | `θ[r]` (32-bit, modular Q0.32) and `ω[r]` (32-bit, per-sample increment, modular), r = 0 … R−1, R = NMAX/2 |
| Writers | the **stateful pass** of the packet that owns rotor r (VK-3); the **seeding pass** (VK-6). No one else — not the datapath, not the switch |
| Write window | a rotor is written only after its read in sweep n and before its read in sweep n+1 — the write-window law of Register Map v0.3 §5 at rotor granularity |
| Reset | undefined; a stateful packet is unusable until seeded (VK-6) |

### VK-2 Packet modes — RT.OUT bits 2–15 (W-F32)

RT.OUT (+0xE, W16) keeps bits 0–1 as routing (L, R). The upper bits are mode:

| Bit(s) | Name | Meaning |
|---|---|---|
| 2 | **ACC_C** | this packet's raw sine outputs are summed into the **C accumulator** instead of L/R (bits 0–1 ignored) |
| 3 | **STATEFUL** | the packet's bins are rotors `base + k`; phase comes from `θ[]`, is advanced by `ω[]` and the coupling, and is written back |
| 4 | **VIEW** | the packet's bins read rotors `base + k` **without write-back**; the presented phase is `θ[base+k] + phase_cf(k)`, where `phase_cf` is the packet's own closed form (PH0, PHD1, PHD2) — i.e. the closed form becomes a per-bin **offset** |
| 5 | reserved | 0 |
| 6–15 | **BASE** | rotor base index (10 bits, 0 … 1,023) |

Bits 3 and 4 both set is EW7 (rejected at BCP). Mode 0 (bits 2–15 clear) is the legacy packet: unchanged behaviour, bit-exact to WPMS Ch.3.

### VK-3 The stateful pass (W-F33)

For each bin k of a STATEFUL packet, in bin order:

```
θ      ← θ[base+k]                      ; read
s      ← sin(θ)                          ; the sine core, as today (Q1.31)
out    ← s × amplitude(k)               ; amplitude path unchanged (log domain)
S      += s                              ; mean-field accumulator S (raw sine, unit amplitude)
c      ← scratch[base+k]                 ; cos θ of this sample, stored by the C-view pass (VK-4)
Δ      ← (KS.p × c − KC.p × s) >> 31     ; coupling, in increment units (VK-5)
θ[base+k] ← θ + ω[base+k] + Δ            ; write back (mod 2^32)
```

`out` is routed by bits 0–2 as for any packet. The accumulator S sums the raw sine (before amplitude) so that the mean field does not depend on the level; it is closed on the strobe with the same latency law as the audio accumulators (WPMS Ch.4).

### VK-4 The view pass

For each bin k of a VIEW packet: `θ ← θ[base+k] + phase_cf(k)`; `s ← sin(θ)`; `out ← s × amplitude(k)`; routed by bits 0–2. If ACC_C is set, additionally `C += s` and `scratch[base+k] ← s`. Nothing is written to `θ[]` or `ω[]`.

**Cosine view.** A VIEW packet with PH0 = +π/2 (0x4000_0000), PHD1 = PHD2 = 0, ACC_C set and the same BASE as a stateful packet presents `sin(θ + π/2) = cos θ`: its outputs are the cosines of the stateful rotors, its accumulator is C, and its scratch is the per-rotor `cos θ` the stateful pass consumes.

**Order rule.** In the sweep word, a C-view of a rotor set precedes the stateful pass of the same rotor set. (Checked by the oracle; the hardware does not enforce it — a wrong order yields a one-sample-stale cosine, not a fault.)

### VK-5 The mean field and its coefficients (W-F34)

| Word (L2 space) | Width | Writer | Reader | Meaning |
|---|---|---|---|---|
| `0x11B K` | 32 | **external pin** (the knob: L4) | datapath (read-only) | coupling strength, program-tier units |
| `0x11C S`, `0x11D C` | 32 | hardware: the accumulators closed at the last strobe, exposed as a program-selectable 32-bit window (Arena) | datapath (read-only) | Σ sin, Σ cos of the previous sample |
| `0x11E KS.s`, `0x11F KC.s` | 32 | datapath (STM, housekeeping window only; else EW4) | — | staged coefficients |
| `KS.p`, `KC.p` | 32 | hardware: `← KS.s, KC.s` at the strobe | L1 (VK-3) | presented coefficients (W-F22's staged/presented pair, again) |

The housekeeping program computes `KS.s ← (K × S) >> SHV`, `KC.s ← (K × C) >> SHV` (two MULs; the program owns the Q, W-F23). The factor 1/N and the sine's Q1.31 are folded into K by the controller. **Delay: one sample** — Δ at sample n uses S and C of sample n−1. For the housekeeping window to see closed sums, the score places a wait Stay of D_L1 clocks before it (Deliverable 3 §9 budget: at R = NMAX/2 the sweep has room).

### VK-6 Seeding (W-F35)

When BCP lands a GO whose mask touches any of PH0, PHD1, PHD2, OM0, OMD1, OMD2 of a STATEFUL block, the sequencer marks that block **seed-pending**. In the next sweep the block's stateful pass runs as a **seeding pass**: for each k, `θ[base+k] ← phase_cf(k) + ω_cf(k)` and `ω[base+k] ← ω_cf(k)`, with `out ← sin(phase_cf(k))`, no coupling, where `ω_cf(k) = OM0 + k·OMD1 + k(k−1)/2·OMD2` is the closed-form per-bin increment (the same engine as `phase_cf`, run on the OM slots; for that sweep the bundle also carries OM0, OMD1, OMD2). The pending mark clears after the sweep. A writer therefore seeds rotors exactly as it re-seeds a legacy packet: by writing phases and increments and firing a GO.

### VK-7 Order parameter readout (W-F36)

`r² = (S² + C²)` of the last sample, computed at the strobe (two multipliers) and presented for the video page and the inspector; `r = √(S²+C²)/R` is the controller's to display. The same word is readable at `0x120` (program-tier window).

### VK-8 Errors

| Row | Cause |
|---|---|
| EW7 | STATEFUL and VIEW both set; BASE + N > R; a C-view with a different BASE from every stateful packet (no partner) — rejected at BCP |
| EW4 (extended) | STM to `0x11E–0x11F` outside the housekeeping window |

---

## 2. Budget / 予算

| Term | Value |
|---|---|
| Rotors per module | R = NMAX/2 (each rotor costs two bins: its sine pass and its cosine view) |
| Memories | `θ`, `ω`: 2 × 32 × R; scratch: 32 × R (Q1.31 can be narrowed to 16 bits — Arena) — about 6 M10K at R = 512, 12 at R = 1,024 |
| DSP | +2 (coupling), +2 (r²) — no second sine core |
| Housekeeping | wait D_L1, then 2 MUL + 4 LDM/STM + SAD ≈ 12 instructions |

---

## 3. The experiment, and its expectations written first / 実験と、先に書く期待

**Setup (one module, 50 MHz build):** packet A = STATEFUL, BASE 0, N = 504, OM0/OMD1 laying the rotors' natural frequencies uniformly on [400, 600] Hz (2γ = 200 Hz), LP constant; packet B = VIEW + ACC_C, BASE 0, N = 504, PH0 = +π/2; sweep word (B, A). K from the knob, swept slowly.

**Expectation.** For a uniform distribution of half-width γ, mean-field theory gives the critical coupling `K_c = 4γ/π` (in increment units, γ = 2π·100/48,000 rad per sample ≈ 0.01309 → K_c ≈ 0.01667 rad per sample ≈ 0x00AD_D6F3 in Q0.32 turns at unit amplitude). Below K_c, r stays near `1/√R ≈ 0.045`; above it, r rises and the sum collapses from a noise-like band at amplitude ∼√R to a single tone near 500 Hz at amplitude ∼ R·r. The transition is audible, visible on the r² bar, and measurable as the r(K) curve.

**Acceptance (ORACLE → RTL-SIM → SILICON).** The integer Kuramoto reference and the RTL agree bit for bit on `θ[]`, S, C, KS, KC over ≥ 2,000 samples with K stepped across K_c; the float Kuramoto model agrees with the integer one on r(t) within the quantization; mutants — wrong sweep order, missing scratch, two-sample delay, write-back from the view — are each caught; on silicon, r(K) reproduces the oracle's curve and K_c lies within the step of the sweep.

---

## 4. What the customer is told (PR-6) / 顧客への通知

Not a requirement, a notice: (1) RT.OUT bits 2–15 are used as mode bits by this profile; (2) `+0xD` stays reserved; (3) Ch.4's accumulator section gains a note that a profile may route raw sine sums into non-audio accumulators; (4) a future chapter may adopt the rotor-view vocabulary. Nothing in Ch.3–5 needs to change for legacy packets.

---

*End of V-K v0.1. The upper-level naming of this family of mechanisms is not part of this document.*
