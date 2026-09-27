# Layer 4 — Verification Evidence / 第4層——検証エビデンス

**CC0.** Where this profile's claims meet DE10-nano (Cyclone V SoC 5CSEBA6U23I7). The profile's numbers so far are instruction counts derived from the master's rows, oracle runs (Layer 3), and — since 2026-09-27 — RTL simulation of the Core the profile runs on. Every number carries its class: **ORACLE** (Python model), **RTL-SIM** (Icarus/ModelSim), **SILICON** (DE10-nano, SignalTap → VCD). No SILICON entry exists yet.

**CC0。** 本プロファイルの主張が DE10-nano と出会う場所。これまでの数値は、マスターの行から導いた命令数、オラクル実行（第3層）、そして 2026-09-27 からはプロファイルが載る Core の RTL シミュレーション。数値はすべて証拠クラスを伴う: **ORACLE**・**RTL-SIM**・**SILICON**。SILICON の記載はまだない。

## Entries / 記載

| Date | Entry | Class | Verdict |
|---|---|---|---|
| 2026-09-27 | `SILICON_BRIEF_2026-09-27.md` — the plan for the silicon phase (Layer 4 plan, not evidence) | — | — |
| 2026-09-27 | `reports/phase0_baseline.md` (+ `reports/logs/phase0/`) — golden models and the frozen Core re-run unchanged | ORACLE, RTL-SIM | green |
| 2026-09-27 | `reports/phase1_core.md` + `rtl_sim/2026-09-27_phase1_core_rh031p/` (`observation.md`, VCDs) — PTSG-Core RH031 (provisional) on a copy: bit-identical with the pin silent; SV-0 … SV-7 pass; the anti-pattern caught (8192-clock Stay); packet floor 30 for a 25-instruction window | RTL-SIM | PASS |
| 2026-09-27 | `reports/phase2_datapath.md` + `rtl_sim/2026-09-27_phase2_l2_datapath/` (`observation.md`, logs) — the L2 Formation datapath bit-identical to `pfasm_tools_w.Machine` on 3,914 cases (105,519 instructions); `exp_maclaurin_w` 7.39e-09; 13 negatives; 20/20 mutants caught; the score round trip on the Core copy; SD-13, SD-14 filed; resources by Yosys (ESTIMATE) | RTL-SIM | PASS |
| 2026-09-27 | `reports/discrepancies.md` — SD-01 … SD-12, filed, not fixed | — | open |

## Layout / 構成

```
04_Verification_Evidence/
├── SILICON_BRIEF_2026-09-27.md      the plan (Layer 4 plan, not evidence)
├── reports/                          one report per phase, bilingual; discrepancies.md; logs/
├── rtl_sim/<date>_<feature>/         RTL-SIM evidence: observation.md + small VCDs + logs
└── signaltap/<date>_<feature>/       SILICON evidence: VCD + observation.md (Phase 6)
```

*Measured, not promised.* / *約束せず、測って刻む。*
