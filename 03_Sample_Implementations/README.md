# Layer 3 — Sample Implementations / 第3層——リファレンス実装

**MIT.** Illustrative, not normative. / 例示であって規範ではない。

## The contract chain / 契約の生成鎖

```
PTSG-CPU-Formation Layer 1 Ch.3  ──isa_from_chapter3.py──▶  isa_table.json  (master, canon-derived)
                                                                  │
                                                          isa_fold_w.py  (applies Decision Register W; every fold cites a W-ID)
                                                                  ▼
                                                           isa_table_w.json  (this profile's translation contract)
```

Nothing in the chain is hand-edited. Re-run both steps whenever the master's Ch.3 or this profile's register changes.

## Inventory / 目録

| Path | What it is | Origin |
|---|---|---|
| `tools/isa_from_chapter3.py` | Master's canon-derived contract generator | inherited (2026-09-03) |
| `tools/isa_table_master_2026-09-03.json` | Master contract at the pinned revision (18 instructions; identical to master `ad43cc2`) | inherited |
| `tools/isa_fold_w.py` v0.2 | **Profile fold**: PSH/POP out (W-T1), CMT/RTW out (W-F25), WSV out (W-F28), dest ADRS out (W-F1); WSH (W-F23), **STP 4·0** (W-F26), **BCP 4·1** (W-F27) in; records the 9-bit map, profile registers, EW2–EW6 | this profile |
| `tools/isa_table_w.json` | **Profile contract** (16 instructions) with a fold log | generated |
| `tools/pfasm_tools_master.py` | Master's validator + Q4.28 oracle (kept verbatim for diffing) | inherited |
| `tools/pfasm_tools_w.py` v0.2 | **Profile validator + machine**: single block store, inbox view, CUR alias, COMMIT view, write windows (EW3/EW4), STP, BCP with take-set and EW5, modular ADD/SUB (W-F30) | this profile |
| `tools/sweep_sim.py` | **Sweep oracle**: runs the window programs under a model of the sweep sequencer with random GO traffic; compares every bundle L1 latches with a reference built from WPMS Ch.3/Ch.5 (glide law imported from the customer's oracle) | this profile |
| `tools/negative_tests.py` | Every profile rule rejects what it should; a mutant window is caught | this profile |
| `instruction_lists/wpms_packet.pfasm` | Packet window (25 instructions): level glide by STP, three phase advances, through the CUR alias | this profile |
| `instruction_lists/wpms_housekeeping.pfasm` | Housekeeping window: `BCP` | this profile |
| `instruction_lists/exp_maclaurin_master.pfasm` | The master's first program (26 instructions) | inherited |
| `instruction_lists/exp_maclaurin_w.pfasm` v0.2 | The same program on the profile, owning its Q (`WSH`), without CMT, in a non-packet window (27 instructions) | this profile |
| `hw/` | **Silicon phase** (SILICON_BRIEF_2026-09-27): `hw/core/ptsg_core_rh031p.v` — working copy of PTSG-Core RH030 with `stay_value` (RH031, provisional) — its testbench `ptsg_core_sv_tb.v` (SV-0 … SV-7); `hw/l2/wpms_formation.v` — the L2 Formation datapath, its decode map (`hw/tools/decode_map.json` → RTL table, assemblers, `decode_map.md`), assemblers `pfasm_as.py` / `score_as.py`, and the cosimulation against `pfasm_tools_w.Machine`; recipes per phase; see `hw/README.md` | this profile, 2026-09-27 |

## Evidence (2026-09-26, oracle runs — not silicon) / 証拠

```
$ python3 isa_fold_w.py                         # 16 instructions; fold log cites every W-ID
$ python3 sweep_sim.py <path/to/wpms_layer1_oracle.py> 20000 <seed>     # seeds 2026, 7, 42
sweep_sim: 20000 samples, 71341 packet plays, 1403 GOs (...; 416 full-load GOs); glide law from customer oracle
  L1 bundle mismatches vs reference: 0   machine/sequencer errors: none
  per-packet window: 25 instructions -> N_MIN = 25 + 4 = 29 (profile constant 32)
  BCP worst case: 10 clocks;  worst sweep (Core nominals included): 2064 of 2083 clocks
$ python3 negative_tests.py                     # 13/13 negative tests behave as specified
$ python3 pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json
validate: 27 instructions; CLEAN ... max |err| over sweep = 7.39e-09 at x=+0.40
```

Totals over the three seeds: 60,000 samples, 215,627 packet plays, 4,174 GOs (1,175 at full load), **0 mismatches**.

The sweep oracle's Core timings (wake 2, 4 control clocks per packet, 3 in housekeeping) are nominal stand-ins for the Core's commitments; Layer 4 replaces them with measurements.

## Next / 次

- Layer 4 on DE10-nano: g, T_wake, N_MIN, BCP duration.
- The Core score in Core syntax once the Core chooses R1 or R2 (Deliverable 3 §3).
- Offer `pfasm_tools_w.py`'s machine and the sweep oracle upstream once stable — inherit, not fork.
