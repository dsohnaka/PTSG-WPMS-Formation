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
| `tools/isa_from_chapter3.py` | Master's canon-derived contract generator | inherited (PTSG-CPU-Formation Layer 3, 2026-09-03) |
| `tools/isa_table_master_2026-09-03.json` | Master contract at the pinned revision (18 instructions) | inherited |
| `tools/isa_fold_w.py` | **Profile fold**: W-T1 (PSH/POP out), W-F23 (WSH in), W-F1 (dest ID 6 out); records profile registers, NMAX, EW2/EW3 | this profile |
| `tools/isa_table_w.json` | **Profile contract** (17 instructions) with a fold log | generated |
| `tools/pfasm_tools_master.py` | Master's validator + Q4.28 oracle (kept verbatim for diffing) | inherited |
| `tools/pfasm_tools_w.py` | **Profile validator + oracle**: SHV/WSH realignment; StayVal.s with EW2; 256-word space with inbox (EW3); quartet sources modelled; STA destination checked | this profile |
| `instruction_lists/exp_maclaurin_master.pfasm` | The master's first program (26 instructions) | inherited |
| `instruction_lists/exp_maclaurin_w.pfasm` | **The same program re-issued on the profile contract**, owning its Q: `LDA #28 ; WSH` precede the Horner chain (28 instructions) | this profile |

## Evidence (2026-09-07, oracle runs — not silicon) / 証拠

Positive:

```
$ python3 pfasm_tools_w.py ../instruction_lists/exp_maclaurin_w.pfasm isa_table_w.json
validate: 28 instructions; CLEAN
sweep x in [-0.5, +0.5], program-owned Q4.28 (SHV=28), 10-term Horner:
  x=-0.50  exp=0.606530660  got=0.606530659  |err|=8.12e-10
  x=+0.00  exp=1.000000000  got=1.000000000  |err|=0.00e+00
  x=+0.50  exp=1.648721271  got=1.648721270  |err|=4.37e-10
max |err| over sweep = 7.39e-09 at x=+0.40 (Q4.28 LSB = 3.73e-09); SHV=28
```

Identical to the master's published run — the profile changed *who owns the shift*, not the arithmetic.

Negative (each keyed to a register row):

| Test | Change | Result |
|---|---|---|
| N1 | master program (no `WSH`) on the profile contract | validates CLEAN; **oracle: E8 overflow on every MAC** — the ISA speaks integers; a program that does not own its Q gets integers |
| N2 | `STA ADRS` | `E4` — destination ADRS not in contract (**W-F1**) |
| N3 | `PSH` | `E4` — not in the profile contract (**W-T1**) |
| N4 | `CMT` moved to `.bg` | `E3` (inherited) |
| N5 | `WSV` with 0 and with 2049; `STM` at 0x82 | `EW2`, `EW2`, `EW3` (**W-R9**) |

## Next / 次

- R7 scenario (multi-packet loop + base + stay + back-execution) on this toolchain.
- Per-packet preparation program (register map §7) validated and costed.
- Offer `pfasm_tools_w.py`'s quartet/SHV modelling upstream once stable — inherit, not fork.
