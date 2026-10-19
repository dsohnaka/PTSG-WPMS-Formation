# WPMS Lab — Phase A: expected first, then results / WPMS Lab——Phase A：期待値を先に、結果を後に

*CC0 · opened 2026-10-19 by Claude Code for the architect, per `LAB_BRIEF_WPMS_Sound_Design_2026-10-19` §5. **OUTSIDE WPMS** (Layer 3 tooling, a stand-in for the Layer 4 controller). Before it: `gui_v1_v3.md`, `gui_board.md`.*

*State (2026-10-19): **Phase A built; V-L1 … V-L4 PASS; the board session (B-L) waits for the architect.** The expected column of §1 was written before any Lab code ran (brief §5) and is left as written; deviations are in §5. The architect's rulings of the same day are in §0.*

*状態（2026-10-19）：**Phase A 完成。V-L1〜V-L4 合格。実機（B-L）はアーキテクト待ち。** §1 の期待値は Lab のコードを走らせる前に書いたまま残し、逸脱は §5 に、同日の裁定は §0 に記す。*

---

## 0. Rulings and readings / 裁定と読み方

1. **Lab is a free, own-risk tool** (the architect, 2026-10-19: "the user sets things by hand as freely as possible, at their own risk; no safety measures are needed"). Read as:
   - the headroom guard of brief §3.4 and the range check of §3.1 **show** their values (red above −1 dBFS, red outside 0 … Fs/2) but **never refuse**;
   - the window has no γ limit; every slot takes any 32-bit value the knobs produce;
   - kept, because they are not safety but the switch's own rules: the coalescing law and the switch's GO check (P ≤ 8, no block twice, N in [32, NMAX], Σ N ≤ NMAX). A GO that breaks them is refused by the switch, counted in REJECT[0], and blocks the sender. Brief §4: "REJECT[0] must stay 0 in every Lab session".
   - **Confirmed by the architect** (2026-10-19, Q3), with one change: **LE0 < 0 (EW6) is refused**, because the Formation would silence the sound until a reset; glide 0 (LE0 = 0, a held level) is allowed.
2. **Verified before any code** (the customer's oracle `wpms_layer1_oracle.py`, read 2026-10-19):
   - bin k's frequency word is OM0 + k·OMD1 + C(k,2)·OMD2, and its phase is PH0 + k·PHD1 + C(k,2)·PHD2 (`l1_phase`, check at its line 249);
   - its log₂ window is LS0 + k·LAD1 + C(k,2)·LAD2 by forward differences (`l1_amplitude`), in Q12.20, Q8.24 and Q2.30;
   - the brief's window formulas (LAD2 = −2a, LAD1 = a(2k_c − 1), LS0 = S_p − a·k_c²) follow from that recurrence;
   - **but** `gaussian_slots(consistent=True)` keeps "the apex at N/2" (its docstring). The brief's acceptance "k_c = (N − 1)/2 equals `gaussian()` bit for bit" is therefore expected to **fail**, and k_c = N/2 to pass. **Ruling (Q2): the peak position p maps to k_c = p·N, so p = 0.5 is the GUI's window.**
3. **A seam in `gui/wpms_ctl.py` is needed** (brief §2.2). The sender computes a block's slots with the module function `block_slots()` in `_block_mask` and `_send_item`. A subclass cannot change that without copying those two methods (a fork) or patching the module, and the brief forbids both. **Ruling (Q1): the seam goes into the Lab's PR** — `slots_of(b)`, `gui/wpms_ctl.py` RH003 (§4.2).
4. **Ruling (Q4): the *Dirichlet scale* preset** has N = 126 in each of its eight blocks; every N is then free, and Σ N > 1,008 is shown in red and refused, as in the GUI (the switch's GO check).

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

## 2. The board session (B-L): procedure / 実機の手順

*Expected (SILICON) as in §1 B-L; the measured column is filled after the run.*

**P0.**
- The Phase 6 image is loaded; SW[1:0] = 11, SW[2] = 0, SW[3] = 0.
- **The GUI is closed**: the bridge serves one client.
- The In-System Sources and Probes Editor is closed.

**P1.** Double-click `hw/tools/host/lab/start_lab.bat`. It starts the bridge or reuses one, then opens WPMS Lab connected. By hand instead:

```
quartus_stp -t ../gui/wpms_bridge.tcl
python wpms_lab.py --connect
```

**P2.** Press **Test origin** first: the log must start at the origin to be replayed (ruling 2026-10-14).

**P3.** Load each starter in turn: **Load preset…** → `presets/dirichlet_scale.json`, `schroeder_pad.json`, `chirp_bloom.json`. Listen for about 20 s each; record a short take of each, if convenient.

**P4.** On one block, by hand:

| # | Action | Measured |
|---|---|---|
| B-L1 | **Chirp c**: 0 → ±0.0005 … ±0.002 Hz per bin (slider or entry) | — |
| B-L2 | **Phases**: Preset Zero → Schroeder; note "pending seed" and that nothing changes; then **Seed phases** | — |
| B-L3 | **Lobe offset τ**: e.g. 4 s, then **Seed phases**; the block's pulse moves by τ within its 16 s period | — |
| B-L4 | **Window**: peak position p 0 → 1; peak offset; Raw mode with a slope and a positive curvature (an inverted window) | — |
| B-L5 | The headroom line (top of the tabs) against CLIP (Status) | — |
| B-L6 | At the end: REJECT[0] "+0 since connect"; **Save log** → `python ../gui/cosim_gui_replay.py <log>.json` here | — |

**P5. Send back:**
- the saved log and its times (CSV);
- a screenshot;
- one line per B-L row;
- the recordings, if any.

## 3. Commands and their last lines / コマンドと最後の行

Run 2026-10-19 (Python 3.13, tclsh 8.6.14, Icarus Verilog 12.0), with `gui/wpms_ctl.py` RH003 committed. Logs: `04_Verification_Evidence/rtl_sim/2026-10-19_lab_phase_a/`.

```
python3 hw/tools/host/lab/test_lab.py --v2 --logs ... --report .../test_lab.txt
test_lab: PASS
python3 hw/tools/host/gui/cosim_gui_replay.py .../v_l2_lab.json --report .../cosim_gui_replay_v_l2_lab.txt
cosim_gui_replay v_l2_lab: PASS (47 s)
python3 hw/tools/host/gui/test_gui_bridge.py --report .../gui_test_with_seam.txt
  mutants 9/9 broken copies of wpms_bridge.tcl caught
test_gui_bridge: PASS
python3 hw/tools/host/check_host_tcl.py --report .../check_host_tcl.txt
check_host_tcl: PASS
python3 hw/tools/host/gui/cosim_gui_replay.py .../wpms_gui_20261015_195411.json.gz      (board_gui_replay_l4_3.txt)
cosim_gui_replay wpms_gui_20261015_195411: PASS (824 s)
```

## 4. Results / 結果

### 4.1 V-L1 — `lab_shapes.py` (ORACLE): 11 / 11 PASS

| # | Result |
|---|---|
| L1.1 | Schroeder identity exact for every k, N in {32, 48, 240, 1008, 2048}: 0 exceptions |
| L1.2 | N = 2,048: PHD1 = 0x100000 = 2²⁰, PHD2 = 0x200000 = 2²¹, as the oracle's CH4-CREST |
| L1.3 | Bin phase, closed form = `l1_phase`: 300 / 300 |
| L1.4 | Lobe offset: the packet peaks **at** τ (0 samples off), 4 cases |
| L1.5 | Crest, N = 240: zero phase 26.81 dB (= 10·log₁₀ 2N), Half-Schroeder 7.53 dB, **Schroeder 5.60 dB** |
| L1.6 | Window vs `gaussian()`: **k_c = N/2 equal 228 / 228; k_c = (N − 1)/2 equal 0 / 228** (LAD2 equal in all; LAD1 and LS0 off by half a bin) — D1 |
| L1.7 | Window closed form vs `l1_amplitude`: worst 2^−24.0 relative (bound 2^−23.9) |
| L1.8 | Lab defaults = the GUI's `block_slots()`: 300 / 300 blocks, all 16 slots |
| L1.9 | OMD2 ↔ c within 5.6 × 10⁻⁶ Hz (half an LSB); PHD1 ↔ τ within 1.2 × 10⁻¹⁰ cycle (half an LSB) |
| L1.10 | Band indicator flags both ends, quiet inside |
| L1.11 | Worst-case peak estimate vs the oracle's `l1_amplitude` sum × 2^−G: worst 9.6 × 10⁻⁶ dB over 60 cases |

### 4.2 The seam, `gui/wpms_ctl.py` RH003 (ruling Q1) / 継ぎ目

`slots_of(self, b)` returns `block_slots(self.params[b])`, and the sender's two calls (`_block_mask`, `_send_item`) go through it: 9 lines added, 2 changed (`seam_wpms_ctl_rh003.patch`). The Lab overrides `slots_of` and nothing else in the sender.

### 4.3 V-L2 — the Lab controller headless (ORACLE): 3 / 3 PASS

Bridge under tclsh, the stand-ins, the GUI test's freeze model, starting at the test origin (block 0, N = 1,008):

| # | Result |
|---|---|
| L2.3 | *Dirichlet scale* from the origin: 8 full re-seeds (blocks 0–7) and 1 sweep GO, through the sender. The sender found the order itself: block 0 shrank first, then the sweep. The sent slots equal the preset's stored slots; the recomputed slots equal them too (no note) |
| L2.2 | Schroeder phases on block 5: no transaction, "pending seed"; **Seed phases**: exactly 1 full re-seed carrying PHD1 / PHD2 = the Schroeder words; no longer pending |
| L2.1 | 500 random Lab moves (chirp, window Gaussian and raw, phase presets, τ, Seed, level, pitch, N, glide 0, play, preset loads, master) → 175 GOs: **REJECT[0] 0, refused 0, errors 0**; sent = desired; each GO applied before the next |

### 4.4 V-L3 — the Lab's log through the switch RTL (RTL-SIM): PASS

`v_l2_lab.json` (2,440 steps) replayed with `gui/cosim_gui_replay.py`, unchanged:
- started at the test origin;
- 4,351 transactions equal to `switch_model.py`'s;
- **0 host writes refused** of 1,715;
- APPLY with APPLIED_SEQ = GO_SEQ: 175 / 175, each GO playing from strobe 2;
- **533 / 533 samples** and 2,608 bundles equal to `sweep_sim.Reference` → `l1_model` over the customer's oracle.

The replay covers chirped, Schroeder-phased and raw or inverted windows.

### 4.5 V-L4 — the GUI unchanged (RTL-SIM): 3 / 3 PASS

| # | Result |
|---|---|
| L4.1 | `test_gui_bridge.py` with RH003 committed: PASS, 9 / 9 mutants killed. Before the commit the deterministic V2 storm log was identical with and without the seam (1,460 steps, same replies) |
| L4.2 | `check_host_tcl.py`: PASS, 9 / 9 |
| L4.3 | `board_gui.json` (2026-10-15) replayed: PASS with the numbers of 2026-10-15 — 2,808 GOs, 0 refused, 2,809 / 2,809 APPLY, 9,571 / 9,571 samples. A replay does not import `wpms_ctl.py`; it shows the RTL path unchanged |

### 4.6 The panel / 画面

`wpms_lab_standin.png`: WPMS Lab connected to the stand-ins (Xvfb), after loading *Dirichlet scale*. On block 3:
- chirp 0.0008 Hz per bin;
- Schroeder phases selected and "pending seed" shown;
- window peak at p = 0.3 with a +3 dB offset;
- the slot view marks PHD1 / PHD2 as differing from the sent words.

The headroom line reads +3.3 dBFS in red for all eight blocks in phase at G = 8, an upper bound the separate lobes never reach. In that session: REJECT[0] 0, and Seed cleared "pending seed" with one GO.

## 5. Deviations / 逸脱

- **D1 — the window's centre.**
  - The brief's acceptance at k_c = (N − 1)/2 does not hold (0 / 228). `gaussian()` puts its apex at N/2 (228 / 228).
  - Ruled (Q2): p = 0.5 ↔ k_c = N/2.
- **D2 — the headroom and band guards are indicators** (ruling 2026-10-19, own risk). The brief's §3.4 refusal above +6 dBFS and §3.1 refusal outside 0 … Fs/2 are not built. The estimate itself is built and checked (L1.11).
- **D3 — the worst-case peak is conservative.** It assumes every bin of every playing block in phase at once.
  - Dirichlet blocks reach it only when their lobes coincide; Schroeder phases never come close (crest 5.6 dB, not 26.8).
  - *Dirichlet scale* and *Schroeder pad* therefore read +3.0 and +2.0 dBFS in red at G = 8, yet play without clipping as long as the lobes stay apart.
  - Recorded so the red line is read correctly at the board (B-L5).

## 6. Questions — answered 2026-10-19 / 質問（2026-10-19 回答済み）

- **Q1:** the seam goes into the Lab's PR.
- **Q2:** p = 0.5 ↔ k_c = N/2.
- **Q3:** indicators only; the switch's rules are kept; LE0 < 0 (EW6) is refused.
- **Q4:** *Dirichlet scale* with N = 126 per block; N free; Σ N > 1,008 in red.

No question is open.

---

**和文要約。**

WPMS Lab の Phase A ができた。置き場所は `hw/tools/host/lab/` で、中身は次のとおり。
- `lab_shapes.py`：変換関数
- `wpms_lab_ctl.py`：GUI の制御器を継承した Lab の制御器
- `wpms_lab.py`：GUI の画面を継承した Tk の画面
- プリセット三種と `start_lab.bat`

GUI 側への変更は、裁定どおり `gui/wpms_ctl.py` の継ぎ目（`slots_of`）だけである。

裁定（2026-10-19）：
- 窓の中心は p = 0.5 ↔ k_c = N/2 とした（GUI の窓とビット一致）。
- 安全策は表示だけにした。ただし LE0 < 0（EW6）は禁止し、スイッチの規則（凍結・GO 検査）は残した。
- Dirichlet scale は各 N = 126 で、合計が 1,008 を超えると赤字で示す。

検証結果：
- V-L1（oracle との照合）11/11。
- V-L2（代役上の Lab 制御器）3/3。プリセット読込み・位相の Seed 待ち・500 手の random 操作で、拒否 0。
- V-L3（Lab の記録の RTL 再生）PASS。拒否 0、533/533 サンプル一致。
- V-L4（GUI の回帰）3/3。

実機（B-L）の手順は §2 にある。
