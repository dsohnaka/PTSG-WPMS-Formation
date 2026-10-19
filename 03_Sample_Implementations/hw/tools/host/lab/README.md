# hw/tools/host/lab — OUTSIDE WPMS: WPMS Lab, sound design / WPMS の外：WPMS Lab（サウンドデザイン）

**Nothing in this folder is part of the WPMS design.** Like the GUI (`../gui/`), WPMS Lab stands in for the Layer 4 controller (customer Ch.5 §5.7). It talks to the input switch through the address map of Ch.5 §5.6, integers only (C3-D1). Brief: `LAB_BRIEF_WPMS_Sound_Design_2026-10-19`. Report: `04_Verification_Evidence/reports/lab_v1.md`. License: MIT.

The GUI plays WPMS safely and keeps some axes fixed. **The Lab opens those axes** — chirp, phase shape, window asymmetry — for exploring sound. It is an **own-risk tool** (the architect, 2026-10-19):

- its indicators show, but never refuse;
- what is refused is only what the switch or the Formation itself would stop on:
  - N outside [32, NMAX];
  - Σ N > NMAX, or a block twice in the play order;
  - a glide below 0 (LE0 < 0 is the Formation's EW6, which silences the sound until a reset).

**このフォルダの中身は WPMS の設計の一部ではない。** GUI と同じく第 4 層制御器の代役で、GUI が意図して固定している軸（チャープ、位相の形、窓の非対称）を開いて音を探る。**自己責任の道具**であり、表示はするが拒否はしない。拒否するのは、スイッチや Formation 自身が止まってしまうものだけである（N の範囲、Σ N > NMAX、グライド < 0 = EW6）。

| File | What it is |
|---|---|
| `wpms_lab.py` | The Tkinter panel. It is the GUI's panel (`../gui/wpms_gui.py`, imported) — Master with PANIC, Status with CLIP and REJECT[0], the step log — with Lab block tabs, a headroom line and Load / Save preset. |
| `wpms_lab_ctl.py` | The controller, no Tk: a subclass of the GUI's `Controller` (`../gui/wpms_ctl.py`, imported, not copied). It overrides `slots_of(b)` (the one seam, `wpms_ctl.py` RH003), the checks of a desired state, phase seeding and presets. The coalescing law and the switch's GO check are the GUI's. |
| `lab_shapes.py` | The conversions, pure functions: knobs → slot words, the indicators. Checked against the customer's oracle. |
| `test_lab.py` | V-L1 (`lab_shapes.py` against the oracle and the GUI's `gaussian()`), V-L2 (`--v2`: the controller headless against the bridge, the stand-ins and the GUI test's freeze model; `--logs DIR` keeps its step log for the V-L3 replay). |
| `presets/` | `dirichlet_scale.json`, `schroeder_pad.json`, `chirp_bloom.json` — the three starters. |
| `start_lab.bat` | One-click start on Windows, made from the architect's `../gui/start_wpms.bat`. |

## How to run / 走らせ方

**The bridge serves one client at a time: close the GUI before starting the Lab** (and the other way round). Close the In-System Sources and Probes Editor too.

- **Windows, one click:** double-click `start_lab.bat`. It starts the bridge (`../gui/wpms_bridge.tcl`) or reuses one that answers PING, then opens WPMS Lab connected. Logs go to `wpms_logs\` beside the BAT (ignored by git).
- **By hand:**

  ```
  quartus_stp -t ../gui/wpms_bridge.tcl                 (or: tclsh ../gui/wpms_bridge.tcl --standin)
  python wpms_lab.py --connect [--preset presets/dirichlet_scale.json]
  ```

- **Scripted:** `python wpms_lab_ctl.py load presets/schroeder_pad.json --log lab.json`.
- **Checks:**

  ```
  python test_lab.py --v2 --logs logs/                  (V-L1, V-L2)
  python ../gui/cosim_gui_replay.py logs/v_l2_lab.json   (V-L3: the same replay as the GUI's)
  ```

Press **Test origin** first in a board session: only a log that starts at the origin replays in RTL-SIM (ruling 2026-10-14).

## The knobs and their slots / つまみとスロット

Bin k (k = 0 … N − 1) is made from the block's slots as the customer's oracle does it (`l1_phase`, `l1_amplitude`), with C(k,2) = k(k − 1)/2:

- frequency f_k = OM0 + k·OMD1 + C(k,2)·OMD2;
- phase Φ_k = PH0 + k·PHD1 + C(k,2)·PHD2;
- log₂ window S_k = LS0 + k·LAD1 + C(k,2)·LAD2;
- amplitude 2^(LP + MG + S_k), clamped per bin to [0, 1).

| Panel | Knob | Slots | Sent with |
|---|---|---|---|
| (the GUI's) | Centre, Spacing; Level, Glide; Width γ; N; Route | OM0, OMD1; LPT, LE0; LAD1, LAD2, LS0; N (full re-seed); RTOUT | PITCH; LEVEL; ENV; RESEED; RT.OUT |
| | Glide **hold** | LE0 = 0: the level stays where it is | LEVEL |
| Chirp | **c** [Hz per bin] — the bin spacing drifts by (N − 2)·c across the packet | OMD2 = round(c·2³²/Fs) | PITCH (phase-continuous) |
| Phases [S] | **Preset** Zero / Schroeder / Half-Schroeder / Custom | PHD1, PHD2 = 0, 0 / 1/(2N), 1/N / 1/(4N), 1/(2N) cycles: Schroeder gives the phase k²/(2N), crest about 5.6 dB | **only by Seed phases** (a full re-seed); until then "pending seed" |
| | **PH0** [cycles] | PH0 | Seed |
| | **Lobe offset τ** [s] — the bins line up at t = τ within the period 1/Δf | PHD1 = −τ·Δf | Seed |
| | **Curvature** [cycles/bin²] | PHD2 | Seed |
| Window, Gaussian | **Peak position p** — k_c = p·N; p = 0.5 is the GUI's window bit for bit (ruling 2026-10-19) | LAD2 = −2a, LAD1 = a(2k_c − 1), LS0 = S_p − a·k_c², with a = γ/ln 2 taken back from the rounded LAD2 | ENV |
| | **Width** = the γ row (no limit); **Peak offset** S_p [dB] | | ENV |
| Window, Raw | **Start** S_0 [dB], **slope** [dB/bin], **curvature** [dB/bin²] (> 0: an inverted window) | LS0, LAD1, LAD2 directly | ENV |

The **slot view** shows the block's 16 words, desired and sent, in hex and signed decimal. A `*` marks a word the next GO will send; phase words go only with Seed.

**Indicators** (red, never a refusal):
- the band of the bins outside 0 … Fs/2;
- a slot clamped to 32 bits;
- the **worst-case peak** of the playing set in dBFS (above −1 dBFS: red). It assumes every bin of every playing block in phase, through MG and G, and is ORACLE-checked to 10⁻⁵ dB. It is an upper bound: Dirichlet blocks reach it only if their lobes coincide, and Schroeder phases never come near it.

PANIC, the MG slider and CLIP stay in view in every tab.

## Presets / プリセット

Each preset is a JSON file:

```
{"version": 1, "name": …, "nmax": …,
 "master": {"mg_target", "mg_rate", "g_ctrl"},
 "sweep": [...],
 "blocks": [{"b", "knobs": {...}, "slots": [16 ints], "rtout"}, …]}
```

It keeps both the knobs and the resolved slots. On load, the slots are recomputed from the knobs. If they differ, the stored slots are loaded and the difference is reported. A load is desired state only: every block is re-seeded and the sweep word follows, through the normal sender (the coalescing law, the switch's GO check).

| Starter | What |
|---|---|
| *Dirichlet scale* | The 2026-10-18 screenshot state: eight blocks C3 … C6, N = 126 each (Σ 1,008), 1/16 Hz, −6 dB, γ = 3 × 10⁻⁴, zero phase, G override 8. Each main lobe returns every 16 s. |
| *Schroeder pad* | A C-major pad: four blocks, N = 240 at 1/8 Hz, Schroeder phases. The 8 s pulses become a sustained tone with the same spectrum. |
| *Chirp bloom* | Three blocks, N = 240 at 1/16 Hz, chirped by +0.0005, −0.0005, +0.001 Hz per bin. Each 16 s pulse blooms into a sweep. |

## The laws kept / 守る法

The Lab keeps the GUI's coalescing law unchanged (`../gui/README.md`):

- the desired and the sent state are kept apart;
- one item per GO, with go-now, and no armed item is left;
- each GO waits for APPLIED_SEQ;
- before a GO, the switch's check runs on the post-GO state: P ≤ 8, no block twice, N in [32, NMAX], Σ N ≤ NMAX.

**REJECT[0] stays 0**: a refusal is a bug in the Lab. Every Lab session's step log replays through the switch RTL with `../gui/cosim_gui_replay.py`, unchanged (V-L3).

---

**和文要約。** WPMS Lab は GUI の制御器と画面を継承し（コピーはしない）、チャープ（OMD2）・位相（PH0/PHD1/PHD2、Seed で送る）・窓（ピーク位置・幅・オフセット、raw モード）を開いた。プリセットはつまみとスロットの両方を JSON に保存し、読み込みは通常の送信者を通る。表示（帯域、最悪ピーク、32 ビット丸め）は赤字で示すだけで、拒否はスイッチや Formation が止まるもの（N の範囲、Σ N > NMAX、LE0 < 0）に限る。橋は同時に一つのクライアントしか受けないので、GUI と Lab は同時に接続できない。起動は `start_lab.bat`。
