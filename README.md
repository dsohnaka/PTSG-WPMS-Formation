# PTSG-WPMS-Formation — The First Subtraction Profile
## Open Prompt Repository

> **A master ISA, subtracted down to a score.** PTSG-WPMS-Formation is the L2 Formation of the Wave-Packet Modulation Synthesis engine inside [FPGA Spectrum Engine](https://hackaday.io/project/205582-fpga-spectrum-engine): the packet-parameter engine that lets one gesture reach two thousand oscillators without a single audible seam. It is produced from [PTSG-CPU-Formation](https://github.com/dsohnaka/PTSG-CPU-Formation) — the master data ISA — by *subtraction and minimal addition*, on top of the frozen [PTSG-Core](https://github.com/dsohnaka/PTSG-Core). One Stay is one packet; the Stay counter is the difference engine's *k*; the trailing edge is the commit.
>
> **マスター ISA を、楽譜になるまで引き算する。** PTSG-WPMS-Formation は [FPGA Spectrum Engine](https://hackaday.io/project/205582-fpga-spectrum-engine) の波束変調合成エンジンの L2 Formation——一つの身振りを二千のオシレータへ、継ぎ目の音を一つも立てずに届けるパケットパラメータエンジンである。凍結された [PTSG-Core](https://github.com/dsohnaka/PTSG-Core) の上に、マスターデータ ISA [PTSG-CPU-Formation](https://github.com/dsohnaka/PTSG-CPU-Formation) からの*引き算と最小限の足し算*で作られる。一つの Stay が一つのパケット、ステイカウンタが差分エンジンの *k*、後縁がコミットである。
>
> Released under the **Open Prompt** paradigm as the fourth repository of the PTSG ecosystem, and the first **subtraction profile** — the proof, from the profile side, that a master ISA can be narrowed without being forked.
>
> **Open Prompt** パラダイムのもと、PTSG エコシステム第四のリポジトリとして、そして最初の**引き算プロファイル**——マスター ISA をフォークせずに狭められることの、プロファイル側からの実証——として公開。

---

## For AI agents / AI エージェントへ

This repository is designed to be read, internalized, and *regenerated* by language models. The normative canon lives in `01_Architecture/` — at launch, the **Decision Register W** (every profile decision keyed to a master ID) and the **L2 Formation register map**; the reasoning that produced them lives in `02_Reasoning_Traces/`; `03_Sample_Implementations/` holds the profile's translation contract, generated mechanically from the master's, and a validator/oracle; `04_Verification_Evidence/` is where claims meet DE10-nano.

本リポジトリは言語モデルによって読まれ、内在化され、*再生成される*ことを前提に設計されている。規範の正典は `01_Architecture/`——ローンチ時点では**決定台帳 W**(全プロファイル決定をマスター ID に紐づける)と **L2 Formation レジスタマップ**——に、推論は `02_Reasoning_Traces/` に、`03_Sample_Implementations/` にはマスター契約から機械生成されたプロファイル契約と検証器/オラクルが、`04_Verification_Evidence/` には主張が DE10-nano と出会う記録が置かれる。

**Suggested reading order / 推奨読了順:** PTSG-Core Ch.1 (the trailing-edge principle) and Ch.3 §3.4b → PTSG-CPU-Formation Layer 1 (five chapters; the master) → `01_Architecture/PTSG_WPMS_Formation_Decision_Register_W_*.md` (this profile's law, §0 pin first) → `01_Architecture/L2_Formation_Register_Map_*.md` → the traces.

**Prerequisites / 前提リポジトリ:** [PTSG-Core](https://github.com/dsohnaka/PTSG-Core) (frozen normative Core) · [PTSG-CPU-Formation](https://github.com/dsohnaka/PTSG-CPU-Formation) (master data ISA; this profile is pinned to its 2026-09-03 revision) · [FPGA_Spectrum_Engine_OpenPrompt](https://github.com/dsohnaka/FPGA_Spectrum_Engine_OpenPrompt) (WPMS Layer 1 Ch.1–2; the customer).

---

## What this repository is / 本リポジトリについて

A **subtraction profile** of the master data ISA. Under the master's succession law (F-F12) a profile must (1) **pin** the master revision it subtracts from and (2) **key every decision** to the master ID it disposes of, using four words: INHERIT, RESTRICT, OMIT, EXTEND. This repository is that register, plus the minimal additions the master deliberately left to its first customer: the page layout, the consumer interface, the choreography.

マスターデータ ISA の**引き算プロファイル**。マスターの継承法(F-F12)の下、プロファイルは (1) 引き算元のマスター改訂を**釘付け**し、(2) 全決定を INHERIT / RESTRICT / OMIT / EXTEND の四語でマスター ID に**紐づける**。本リポジトリはその台帳と、マスターが最初の顧客に意図的に残した最小限の足し算——ページレイアウト、消費者インターフェース、振付——である。

```
PTSG ecosystem / PTSG エコシステム

  PTSG-Core ──────────────── frozen, normative / 凍結・規範
      │  (delegation boundary: mode 0 = Core / modes ≥ 1 = Formation)
      ▼
  PTSG-CPU-Formation ─────── master data ISA / マスターデータ ISA
      │  (subtraction profile / 引き算プロファイル)
      ▼
  PTSG-WPMS-Formation ────── this repository: L2 Formation of WPMS / 本リポジトリ
      │  (ISA-visible register map: addresses, integer widths, commit law)
      ▼
  FPGA Spectrum Engine — WPMS Layer 1 Ch.3 (Q-interpretation, wiring, L1 pipeline)
```

**Layers of the machine / 機械の層** (the vocabulary this repository uses; older "Upper/Lower" labels are retired): **L1 pipeline** — hardwired, one bin per clock, consumer of the active page · **L2 Formation** — *this profile*: one Stay = one packet, Stay counter = *k*, BG computes, Q commits · **L4 Formation** — outside WPMS; an external controller, first a verification tool.

---

## Doctrine highlights / 教義の要点

- **The subtraction is judged on the result, not the path.** Additions made here may be absorbed by the master later; the profile need not wait. / **引き算は経路ではなく結果で判定される。** ここでの足し算は後日マスターに吸収されうる。
- **The ISA speaks integers.** Every register and page slot has an integer width; fixed-point meaning belongs to programs and to WPMS Ch.3. A program owns its Q by writing the shift register (`WSH`) before its first MAC. / **ISA は整数を語る。** Q 規約はプログラムと第3章のもの。
- **One Stay is one packet.** Packet length is the Stay value; the Formation supplies it through a two-stage register (`StayVal.s` → `StayVal.p` at Stay Set), so the Core sees a frozen value and no packet can be stretched mid-flight. / **一 Stay が一パケット。**
- **Zero zipper noise by construction** — inherited (F-F7) and elevated: shadow written, active read, swapped on the trailing edge. / **ゼロ・ジッパーノイズは構造的。**
- **What the register removes, the validator rejects.** The profile contract is generated from the master's by folding the register mechanically; it is never hand-edited. / **台帳が除いたものは検証器が拒否する。**

---

## Repository structure / 構成

```
PTSG-WPMS-Formation/
├── 01_Architecture/                 ← Layer 1: Decision Register W, register map (CC0)
├── 02_Reasoning_Traces/             ← Layer 2: design dialogues (CC0)
├── 03_Sample_Implementations/       ← Layer 3: contract fold, validator/oracle, programs (MIT)
├── 04_Verification_Evidence/        ← Layer 4: DE10-nano evidence (CC0) — to come
├── _worksheets/                     ← non-normative working artifacts (CC0)
├── LICENSE_OpenPrompt.md
├── CONTRIBUTING.md
├── PROJECT_ABSTRACT_canonical.md    ← single source of the abstract
└── README.md
```

---

## Status / 現状

**Launch phase, 2026-09.** / **ローンチ段階。**

- ✅ Decision Register W v0.5 — first Fixed rulings (RESTRICT F-F13; OMIT data stack; RESTRICT FG register-source branch; two-stage Stay-value register; program-owned MAC shift) / 決定台帳 W v0.5
- ✅ L2 Formation register map v0.2 — 256-word space, 16-word packet blocks, inbox, RT entries; accepted by the WPMS side as customer / レジスタマップ v0.2
- ✅ Layer 3: contract chain Ch.3 → master → profile; validator/oracle; the master's first program re-issued owning its Q — CLEAN, identical numerics / 第3層
- 🔄 Deliverable 2 (L1 consumer interface), deliverable 3 (choreography) — in preparation
- ⏳ Layer 4 evidence on DE10-nano — to come (*measured, not promised*)

---

## Provenance / 来歴

Architecture and all rulings: **Tsuneo Ohnaka**. Drafting support: **Claude (Anthropic)**, serving as the profile's amanuensis; the master's amanuensis (PTSG-CPU-Formation) and the customer's amanuensis (FPGA Spectrum Engine) are separate sessions, and the correspondence between them is published as Layer 2. Produced under the WPMS-Formation Session Charter v1.0 (2026-07-31) and the master's hand-off brief (2026-07-13).

アーキテクチャと全裁定: **大中庸生**。起草支援: **Claude (Anthropic)**、本プロファイルの祐筆として。マスター側祐筆(PTSG-CPU-Formation)と顧客側祐筆(FPGA Spectrum Engine)は別セッションであり、祐筆間の往復は第2層として公開される。
