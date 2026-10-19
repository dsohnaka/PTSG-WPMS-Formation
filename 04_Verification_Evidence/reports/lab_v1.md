# WPMS Lab — Phase A: expected first, then results / WPMS Lab——Phase A：期待値を先に、結果を後に

*CC0 · opened 2026-10-19 by Claude Code for the architect, per `LAB_BRIEF_WPMS_Sound_Design_2026-10-19` §5. **OUTSIDE WPMS** (Layer 3 tooling, a stand-in for the Layer 4 controller). Before it: `gui_v1_v3.md`, `gui_board.md`.*

*State (2026-10-19): **V-L1 PASS (11 / 11); stopped for the architect** (brief §7) on three questions (§5): the seam in `gui/wpms_ctl.py`, the window's centre, and the reading of "no safety measures". The expected column below was written before any Lab code ran (brief §5) and is left as written; deviations are in §4.*

*状態（2026-10-19）：**V-L1 合格（11/11）。指示書 §7 に従い、三つの質問（§5）でアーキテクトの判断を待つ。** 期待値は Lab のコードを走らせる前に書いたまま残し、逸脱は §4 に記す。*

---

## 0. Rulings and readings / 裁定と読み方

1. **Lab is a free, own-risk tool** (the architect, 2026-10-19: "the user sets things by hand as freely as possible, at their own risk; no safety measures are needed"). Read as:
   - the headroom guard of brief §3.4 and the range check of §3.1 **show** their values (red above −1 dBFS, red outside 0 … Fs/2) but **never refuse**;
   - the window has no γ limit; every slot takes any 32-bit value the knobs produce;
   - kept, because they are not safety but the switch's own rules: the coalescing law and the switch's GO check (P ≤ 8, no block twice, N in [32, NMAX], Σ N ≤ NMAX). A GO that breaks them is refused by the switch, counted in REJECT[0], and blocks the sender. Brief §4: "REJECT[0] must stay 0 in every Lab session".
   - **This reading is put to the architect** (§5, Q3).
2. **Verified before any code** (the customer's oracle `wpms_layer1_oracle.py`, read 2026-10-19):
   - bin k's frequency word is OM0 + k·OMD1 + C(k,2)·OMD2, and its phase is PH0 + k·PHD1 + C(k,2)·PHD2 (`l1_phase`, check at its line 249);
   - its log₂ window is LS0 + k·LAD1 + C(k,2)·LAD2 by forward differences (`l1_amplitude`), in Q12.20, Q8.24 and Q2.30;
   - the brief's window formulas (LAD2 = −2a, LAD1 = a(2k_c − 1), LS0 = S_p − a·k_c²) follow from that recurrence;
   - **but** `gaussian_slots(consistent=True)` keeps "the apex at N/2" (its docstring). The brief's acceptance "k_c = (N − 1)/2 equals `gaussian()` bit for bit" is therefore expected to **fail**, and k_c = N/2 to pass. Put to the architect (§5, Q2).
3. **A seam in `gui/wpms_ctl.py` is needed** (brief §2.2). The sender computes a block's slots with the module function `block_slots()` in `_block_mask` and `_send_item`. A subclass cannot change that without copying those two methods (a fork) or patching the module, and the brief forbids both. Proposed seam and its regression: §3.2; ruling asked (§5, Q1).

## 1. Expected / 期待値

### V-L1 — `lab_shapes.py` (ORACLE)

| # | Check | Expected |
|---|---|---|
| L1.1 | Schroeder identity C(k,2)/N + k/(2N) = k²/(2N), exact (rationals), k = 0 … N − 1, N in {32, 48, 240, 1008, 2048} | holds for every k |
| L1.2 | Schroeder words for N = 2,048 | PHD1 = 2²⁰, PHD2 = 2²¹ (the oracle's own CH4-CREST line) |
| L1.3 | Phase of bin k from the Lab's closed form vs the oracle's `l1_phase` (forward differences, mod 2³²), random words | equal for every k |
| L1.4 | Lobe offset: PHD1 = −τ·Δf; the Dirichlet sum of the seeded phases peaks at t = τ (mod 1/Δf) | peak within one sample of τ |
| L1.5 | Crest factor of one packet, N = 240: zero phase / Half-Schroeder / Schroeder | 10·log₁₀(2N) = 26.8 dB / in between / ≈ 5 … 7 dB |
| L1.6 | Window = `gaussian()` at the centre, bit for bit, over N in 32 … 2,048 and γ in 10⁻⁶ … 10⁻² | **k_c = N/2: equal; k_c = (N − 1)/2 (the brief's wording): not equal** (LAD1 and LS0 differ by half a bin); LAD2 equal in both |
| L1.7 | Window closed form vs the oracle's `l1_amplitude` (log₂ of each bin) | equal within the exp2 unit's error, 2^−23.9 relative |
| L1.8 | Lab defaults (chirp 0, phases 0, window centred with the GUI's γ, peak 0 dB) vs the GUI's `block_slots()` | all 16 slots equal |
| L1.9 | OMD2 ↔ c round trip; PHD1 ↔ τ round trip | within one LSB (Fs / 2³² = 1.1 × 10⁻⁵ Hz; 2⁻³² cycle) |
| L1.10 | f_k range indicator: a chirp that sends the last bin above Fs/2 or the first below 0 | flagged (shown red, not refused) |
| L1.11 | Worst-case peak estimate vs the oracle (Σ of `l1_amplitude` bins, × 2^−G), random windows, levels, N, G | within 0.01 dB; the per-bin clamp at 2⁰ included |

### V-L2 — the Lab controller headless, stand-ins + freeze model (ORACLE)

| # | Check | Expected |
|---|---|---|
| L2.1 | Random Lab traffic on four blocks: chirp, window (Gaussian and raw), phase seeds, preset loads, N, play | 0 refusals, 0 errors, REJECT[0] 0; sent = desired at the end; every GO applied before the next |
| L2.2 | A phase knob moved without Seed | no transaction for it; "pending seed" shown; Seed makes one full re-seed carrying the phase words |
| L2.3 | Preset load | one full re-seed per block plus one sweep GO, through the sender; the slots recomputed from the knobs equal the stored ones |

### V-L3 — a Lab step log through the switch RTL (RTL-SIM)

| # | Check | Expected |
|---|---|---|
| L3.1 | The V-L2 log, replayed with `gui/cosim_gui_replay.py` unchanged | **PASS**: started at the test origin; 0 host writes refused; every APPLY with APPLIED_SEQ = GO_SEQ; every sample equal to the models (chirped, phase-shaped and asymmetric windows included) |

### V-L4 — the GUI unchanged (RTL-SIM)

| # | Check | Expected |
|---|---|---|
| L4.1 | `gui/test_gui_bridge.py` with the seam | PASS, 9 / 9 mutants |
| L4.2 | `gui/check_host_tcl.py` | PASS, 9 / 9 |
| L4.3 | `board_gui.json` (2026-10-15) replayed with the seam | PASS, the same numbers as before: 2,808 GOs, 0 refused, 9,571 / 9,571 samples |

### B-L — the architect's board session (SILICON): procedure written when Phase A is built

| # | Action | Expected by ear |
|---|---|---|
| B-L1 | Chirp c from 0 to ± a few mHz per bin on one block | the 16 s pulse smears into a sweep; the spectrum's comb spacing drifts across the packet |
| B-L2 | Phase: Zero → Schroeder → Seed | the periodic Dirichlet pulse becomes a sustained tone with the same spectrum; the RMS rises by about the crest-factor difference |
| B-L3 | Lobe offset τ, then Seed | the pulse of that block moves in time by τ within its 16 s period |
| B-L4 | Window peak position 0 → 1 | the spectral envelope's peak moves across the band; the timbre tilts |
| B-L5 | Headroom indicator vs CLIP (0x016) | CLIP stays 0 while the indicator stays below 0 dBFS; it may set above (own risk) |
| B-L6 | REJECT[0] after the session; Save log → `cosim_gui_replay.py` | 0; PASS |

## 2. Commands and results / コマンドと結果

Run 2026-10-19 (Python 3.13, tclsh 8.6.14, Icarus Verilog 12.0). Logs: `04_Verification_Evidence/host_lab/2026-10-19_v_l1/`.

```
python3 hw/tools/host/lab/test_lab.py --report .../test_lab_v_l1.txt
test_lab: PASS
```

With the proposed seam applied **locally only** (not committed; `proposed_seam_wpms_ctl.patch`):

```
python3 hw/tools/host/gui/test_gui_bridge.py --logs ...        (gui_test_with_seam.txt)
  mutants 9/9 broken copies of wpms_bridge.tcl caught
test_gui_bridge: PASS
python3 hw/tools/host/check_host_tcl.py
check_host_tcl: PASS
python3 hw/tools/host/gui/cosim_gui_replay.py .../wpms_gui_20261015_195411.json.gz
(running when this was committed; the result is added below when it ends)
```

## 3. Results / 結果

### 3.1 V-L1 — `lab_shapes.py` (ORACLE): 11 / 11 PASS

| # | Result |
|---|---|
| L1.1 | Schroeder identity exact for every k, N in {32, 48, 240, 1008, 2048}: 0 exceptions |
| L1.2 | N = 2,048: PHD1 = 0x100000 = 2²⁰, PHD2 = 0x200000 = 2²¹, as the oracle's CH4-CREST |
| L1.3 | Bin phase, closed form = `l1_phase`: 300 / 300 |
| L1.4 | Lobe offset: the packet peaks **at** τ (0 samples off), 4 cases |
| L1.5 | Crest, N = 240: zero phase 26.81 dB (= 10·log₁₀ 2N), Half-Schroeder 7.53 dB, **Schroeder 5.60 dB** |
| L1.6 | Window vs `gaussian()`: **k_c = N/2 equal 228 / 228; k_c = (N − 1)/2 equal 0 / 228** (LAD2 equal in all; LAD1 and LS0 off by half a bin) — deviation D1 |
| L1.7 | Window closed form vs `l1_amplitude`: worst 2^−24.0 relative (bound 2^−23.9) |
| L1.8 | Lab defaults = the GUI's `block_slots()`: 300 / 300 blocks, all 16 slots |
| L1.9 | OMD2 ↔ c within 5.6 × 10⁻⁶ Hz (half an LSB); PHD1 ↔ τ within 1.2 × 10⁻¹⁰ cycle (half an LSB) |
| L1.10 | Band indicator flags both ends, quiet inside |
| L1.11 | Worst-case peak estimate vs the oracle's `l1_amplitude` sum × 2^−G: worst 9.6 × 10⁻⁶ dB over 60 cases |

### 3.2 The seam the Lab needs (proposed, not committed) / 継ぎ目の提案（未コミット）

`gui/wpms_ctl.py`'s sender calls the module function `block_slots(self.params[b])` in two places (`_block_mask`, `_send_item`). The smallest seam is one method, `slots_of(self, b)`, which returns `block_slots(self.params[b])`, and those two calls go through it. That is 8 lines added and 2 changed, plus RH003 (`proposed_seam_wpms_ctl.patch`). The Lab's subclass overrides `slots_of` and nothing else in the sender.

Evidence that the GUI is unchanged with it:

- **V1:** PASS with 9 / 9 mutants killed.
- **V2:** all cases PASS.
- **`check_host_tcl.py`:** PASS.
- **The deterministic V2 storm (seed 1):** its step log is **identical** before and after the seam: 1,460 steps, the same transactions in the same order, the same replies (rdata, rej).
- **The board session `board_gui.json` replayed:** see §2. A replay plays the recorded steps and does not import `wpms_ctl.py`, so it shows the RTL path unchanged; the identical storm is the evidence about the controller.

## 4. Deviations / 逸脱

- **D1 — the window's centre.** The brief's acceptance "with k_c = (N − 1)/2 and the GUI's γ, the three words equal `gaussian()`'s bit for bit" does not hold: 0 / 228.
  - `gaussian()` (the oracle's `gaussian_slots`, consistent form) puts the apex at **N/2**, as its docstring says, and k_c = N/2 matches 228 / 228.
  - The brief's derivation itself is right (L1.6 uses it).
  - The Lab maps its peak position p to k_c = p·N, so p = 0.5 is the GUI's window bit for bit. Asked (Q2).

## 5. Questions for the architect / 質問

- **Q1 — the seam (brief §2.2).** May `gui/wpms_ctl.py` take the seam of §3.2 (RH003), committed in the Lab's PR? Without it, the Lab would have to copy `_block_mask` and `_send_item` (a fork) or patch the module, and the brief forbids both. Until the ruling nothing in `gui/` is changed; the patch was applied only locally for the regression.
- **Q2 — the window's centre (D1).** p = 0.5 ↔ k_c = N/2 (equal to the GUI's window, recommended), or k_c = p·(N − 1) (symmetric over the bins 0 … N − 1, half a bin from the GUI's)?
- **Q3 — "no safety measures".** Reading of §0.1:
  - the headroom and band indicators show but never refuse; no γ limit; 32-bit slots are clamped with a note;
  - kept: the coalescing law and the switch's GO check (the switch would refuse otherwise, and the sender would stall);
  - LE0 = 0 (glide 0, a frozen level) is allowed;
  - LE0 < 0 is the Formation's EW6: the sound stops until a reset. Allow it with a red note, or keep it out?
- **Q4 — the *Dirichlet scale* preset** ("the 2026-10-18 screenshot state"). The screenshot shows eight blocks, Σ N = 1,008, block 7 with N = 48, Δf = 1/16 Hz, −6 dB, γ = 3 × 10⁻⁴, G override 8, but not N of blocks 0–6. Their values, or 126 each (8 × 126 = 1,008)?

---

**和文要約。**

Lab は自己責任で自由に設定する道具（2026-10-19、アーキテクト）である。そこで、ヘッドルームと周波数範囲は**表示するだけで拒否しない**。スイッチ自身の規則（凍結・GO 検査）だけは、REJECT 0 を保つために残す。

oracle を読んだ時点（何も走らせる前）で、二つの見込みを持っている。
- 窓の中心は N/2 なら `gaussian()` とビット一致する。指示書の (N−1)/2 では一致しない見込み。
- `gui/wpms_ctl.py` には小さな継ぎ目が必要。

期待値は V-L1〜V-L4 と、実機手順 B-L の表に記した。

2026-10-19：
- V-L1 は 11/11 合格。
- 窓の中心は、N/2 で `gaussian()` と 228/228 一致し、指示書の (N−1)/2 では 0/228（D1）だった。
- `gui/wpms_ctl.py` に入れる継ぎ目（`slots_of`、8 行追加・2 行変更）は手元でだけ当てた。GUI の V1・V2・host 検査はすべて合格し、決定的ストームの記録は前後で完全に一致した。
- 質問は四つ（継ぎ目の可否、窓の中心、安全策の読み方、Dirichlet scale の各 N）で、判断を待つ。
