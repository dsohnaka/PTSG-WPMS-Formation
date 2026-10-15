# hw/tools/host/gui — OUTSIDE WPMS: the host control GUI / WPMS の外：ホスト制御 GUI

**Nothing in this folder is part of the WPMS design.** Like everything in `hw/tools/host/`, it stands in for the Layer 4 controller (customer Ch.5 §5.7). It talks to the input switch through the address map of Ch.5 §5.6, integers only (C3-D1). It changes no RTL, no Layer 1 document and no golden model. Brief: `GUI_BRIEF_WPMS_Host_Control_2026-10-14`. License: MIT.

**このフォルダの中身は WPMS の設計の一部ではない。** `hw/tools/host/` のほかのファイルと同じく第 4 層制御器の代役で、第 5 章 §5.6 のアドレスマップを通して整数だけで話す。RTL・第 1 層文書・黄金モデルには手を入れていない。

```
 wpms_gui.py (Tkinter)  ──calls──▶  wpms_ctl.py (no Tk: conversions, coalescing, step log)
                                         │  TCP, 127.0.0.1, one line per command
                                         ▼
                         wpms_bridge.tcl  (quartus_stp -t; or tclsh + ../issp_standin.tcl)
                                         │  source ../wpms_issp_host.tcl; wpms_open once
                                         ▼
                                  ISSP instance HOST ──▶ wpms_host_bridge.v ──▶ switch
```

| File | What it is |
|---|---|
| `wpms_bridge.tcl` | The resident bridge. Opens the ISSP session once (`wpms_open` of `../wpms_issp_host.tcl`, unchanged), listens on `127.0.0.1` (default port 50707), one client at a time, and makes one ISSP transaction per `W` / `R` line. Survives ISSP errors and lost clients. |
| `wpms_ctl.py` | The controller, Python standard library only: the bridge client, the GUI's state (desired and sent), the conversions (imported from `../wpms_music.py`), the **coalescing law**, the **step log**. Usable without Tk (`ping`, `status`, `storm`, `measure` on the command line). |
| `wpms_gui.py` | The Tkinter panel. Every action goes through `wpms_ctl.py`. |
| `test_gui_bridge.py` | V1 (the bridge under tclsh against the stand-ins, with 9 broken copies) and V2 (the controller headless, with a freeze model in the test's own copy of the stand-in). |
| `cosim_gui_replay.py` | V3: a recorded step log replayed through the switch RTL with `cosim_switch.py`'s build, simulate and check functions. |

## How to run / 走らせ方

**On the board (DE10-nano, Phase 6 image loaded).** Close the In-System Sources and Probes Editor first (one ISSP session at a time).

```
quartus_stp -t wpms_bridge.tcl            # terminal 1 (the bridge; prints "listening on 127.0.0.1:50707")
python wpms_gui.py --connect              # terminal 2 (Python 3 with Tkinter)
```

**Without the board (the stand-ins):**

```
tclsh wpms_bridge.tcl --standin           # terminal 1
python wpms_gui.py --connect              # terminal 2
```

Windows: do not redirect Python or Tcl output with PowerShell's `>` (it writes UTF-16); use `Out-File -Encoding utf8`, or the tools' own options (`wpms_ctl.py ... --log F.json --csv F.csv`, the GUI's **Save log** / **Save times**).

**Scripted (no GUI):**

```
python wpms_ctl.py ping                                   # ID, CONFIG, the sweep
python wpms_ctl.py status
python wpms_ctl.py storm --moves 400 --blocks 0,1,2,3 --log storm.json
python wpms_ctl.py measure --n 1000 --seconds 60 --csv times.csv --log board.json   # GUI brief §7
python cosim_gui_replay.py board.json                     # the session through the switch RTL (Icarus)
python test_gui_bridge.py --logs logs/                    # V1, V2 (tclsh needed)
```

## The bridge's line protocol / 橋の一行手順

| Request | Reply | Meaning |
|---|---|---|
| `W <addr hex> <data hex>` | `OK <rdata hex> <rej 0/1> <us>` | one `wpms_write`; `<us>` = the transaction's wall time (`clock microseconds`), JTAG only, no TCP |
| `R <addr hex>` | `OK <rdata hex> <us>` | one `wpms_read` |
| `B <n>` then n lines `W …` / `R …` | n reply lines, then `END <us>` | one TCP round trip, n ISSP transactions in order; stopped at the first refusal **or error** (the rest answer `SKIP` and are not executed) |
| `PING` | `OK WPMS <ID hex> <CONFIG hex>` | reads 0x000 and 0x002 |
| `QUIT` | `BYE` | the client leaves; the ISSP session stays open for the next |
| `SHUTDOWN` | `BYE` | `wpms_close`, then exit |
| anything else | `ERR <text>` | — |

An ISSP error (no acknowledge within `--timeout` ms, default 2,000; a Tcl error) answers `ERR <text>`. The bridge then sets its toggles back to the probe's acknowledges, so nothing is left pending and the next transaction starts clean; it keeps serving. A second client while one is served gets `ERR busy` and is closed. The replies of a request leave in one write (full buffering, one flush): a batch's lines do not wait behind the client's delayed acknowledge.

## The panels / パネル

- **Master.** MG_TARGET in dB, 0 … −72 (written as `q26(dB / 6.0206)`, Q6.26 log2 units; 0x010 takes `min(MG_TARGET, 0)`); MG_RATE in dB/s (`q26(dB/s / 6.0206 / 48,000)`: 60 dB/s = 13,933 = `MG_RATE_DEFAULT`); **PANIC** (MG_TARGET ← 0x8000_0000, the floor −32 log2 = −192.7 dB: silent after MG_RATE's slew); **Test origin** (0x01C ← 1; the ROM's list, ending in GO_ALL; afterwards the controller re-reads the switch and the panel follows); **G** (G_CTRL: override and G = 0 … 15, as `wpms_music.demo()`'s 0x18 = override, G = 8). G is written only when changed in the panel: at connect the panel shows what the switch holds.
- **Block b** (tab; ♪ = playing). **Play** (the sweep order is the order of ticking); **Centre** and **Spacing** (log sliders, 20 Hz … 20 kHz and 1/256 … 64 Hz per bin) → OM0, OMD1 (OMD2 = 0) by `note_block()`, written with mask **PITCH** (phase-continuous); **Level** (0 … −72 dB) → LPT, **Glide** (1 … 10,000 dB/s) → LE0, written with mask **LEVEL** (LP is never written after the seed, so the STP glide carries every level step); **Width γ** → LAD1, LAD2, LS0 by `gaussian()`, written with the envelope mask (bits 3, 4, 15: the phases stay); **N** (a change of N is a full re-seed); **Route L / R** → RTOUT[b] with mask bit 16; **Seed** (`RESEED | RT_BIT` from the panel's values). The band of the bins is shown, flagged when it leaves 0 … 24 kHz. The panel refuses — and says why — a sweep with Σ N > NMAX, an N outside [32, NMAX], an envelope too wide for 32-bit slots, a glide rate ≤ 0 (LE0 = 0 freezes the level, LE0 < 0 is EW6). NMAX is read from CONFIG (0x002) at connect.
- **Status** (polled every 250 ms, at most once between knob GOs): GO_SEQ, APPLIED_SEQ, APPLIED_SAMPLE, REJECT[0] (and how many since connect), CLIP, MG, the sweep the switch holds, GOs and master writes sent, the GO pending, the last ISSP transaction time and the mean / max.
- **Step log.** The knobs' transactions as they go (status polls hidden unless asked); **Save log** writes every transaction as JSON for `cosim_gui_replay.py`; **Save times** writes every transaction time as CSV.

A block whose switch state is unknown (at connect, after the test origin) is not written until one of its knobs moves or Seed is pressed; then its first GO is a full re-seed from the panel.

## The coalescing law / 間引きの法 (GUI brief §4)

An item handed over by a GO is frozen until it is applied; writes to it in between are refused. In `wpms_ctl.py`:

1. a knob writes only the **desired** state (latest value wins);
2. one sender (a thread) compares desired with **sent**; when they differ and no GO of this controller is pending, it sends the difference of **one** item in one batch — the changed slots (by group: PITCH, LEVEL, envelope; a full re-seed when N changes), RTOUT if the route changed, then `COMMIT[b]` with that mask and **go-now**, then a read of GO_SEQ — or, for the play order, `SWEEP` then `SWEEP_COMMIT` go-now;
3. that GO is pending until APPLIED_SEQ reaches it (one read per transaction slot);
4. items with differences are served round-robin (blocks 0 … 7, then the sweep);
5. MG_TARGET, MG_RATE and G_CTRL need no GO and are sent directly, latest value wins;
6. before sending, the switch's GO check (P ≤ 8, no block twice, N in [32, NMAX], Σ N ≤ NMAX) is made on the state the switch holds after this GO, and an item that would fail waits (e.g. N of a playing block grows only after the sweep that makes room for it).

go-now fires one item alone, so the controller never leaves an item armed, and the ROM's GO_ALL (test origin) never takes one of its items. The answers of customer Ch.5 behind this law are in `04_Verification_Evidence/reports/gui_v1_v3.md` §6.

## The step log / ステップ記録

Every transaction is appended as a step of `wpms_music.py`'s format — `("W", addr, data, note)`, `("Q", addr, note)` — and `("APPLY", note)` when a GO is seen applied; each with its time (µs since the controller started) and its reply. The JSON (`"format": "wpms_ctl step log 1"`) also records what the switch held at connect (`origin`). `cosim_gui_replay.py` starts from a reset, so **a board session counts as evidence only if it started at the test origin**: connect right after the image is loaded (or after SW[2] up → down), or press **Test origin** first (architect's ruling, 2026-10-14).

## Numbers / 数値

| Item | Expected (ESTIMATE, GUI brief §7) | Measured |
|---|---|---|
| One ISSP transaction (`<us>`), mean and max over ≥ 1,000 | 5 … 30 ms | **0.41 ms mean, 3.5 ms max** (1,000 reads; 0.43 / 4.2 ms over 132,831) — SILICON, 2026-10-15 |
| Master gain update rate | 33 … 200 /s | **1,826 /s** — SILICON |
| Block level update rate (INBOX + COMMIT + apply polling) | ≈ 6 … 100 /s | **374 GOs/s** on four blocks, 0.99 APPLIED_SEQ polls per GO — SILICON |
| REJECT[0] after a minute of fast knob turning on four blocks | unchanged | **0 → 0** (22,445 GOs in 60 s) — SILICON; 0 in RTL-SIM (V3) |

The board procedure, the expected values and the measured ones are in `04_Verification_Evidence/reports/gui_board.md`; the logs in `04_Verification_Evidence/host_gui/2026-10-15_board/`.

Under the stand-ins (not the board; a plain tclsh, no JTAG) a transaction takes 0.02 … 0.5 ms: that measures this PC and the TCP path only.

---

**和文要約。** `wpms_bridge.tcl` は ISSP セッションを一度だけ開いて 127.0.0.1 の TCP で一行一命令を受ける常駐の橋（ISSP の誤りや接続断でも止まらない）。`wpms_ctl.py` は Tk に依存しない制御ロジックで、つまみは「望む状態」だけを書き換え、送信スレッドが「送った状態」との差を一項目ずつ（変更スロット → COMMIT go-now → GO_SEQ 読出し）送り、APPLIED_SEQ がその GO に届くまで次を送らない（間引きの法）。項目は順繰りに扱い、マスター利得は GO 不要で直送。送る前にスイッチの GO 検査（P ≤ 8、重複なし、N ∈ [32, NMAX]、Σ N ≤ NMAX）を手元で行う。全トランザクションは `wpms_music.py` の形式のステップとして時刻・応答つきで記録し、JSON に保存して `cosim_gui_replay.py` でスイッチ RTL に再生できる。`wpms_gui.py` はその上の Tkinter パネル。検証は `test_gui_bridge.py`（V1・V2）と `cosim_gui_replay.py`（V3）、結果は `04_Verification_Evidence/reports/gui_v1_v3.md`。実機の数値はまだない。
