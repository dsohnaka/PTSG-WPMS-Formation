# Observation — SD-22 step 1: the restructure changes nothing / 観測——SD-22 段階 1：再構成で何も変わらないこと

*CC0 · 2026-10-03 · RTL-SIM (Icarus Verilog 12.0, `-g2012`), formal (Yosys 0.69 `sat -prove`), ESTIMATE (Yosys gate depth).*

*Formation RH005 against RH004, and switch RH002 against RH001. The previous revisions are taken from commit e3d4985, the RTL of the first fit. Ruling 2026-10-03: step 1 now.*

*Step 1 is defined as "behaviour unchanged", so the expected values are those recorded before the change: the 2026-10-01 run in `rtl_sim/2026-10-01_phase6_board/` and the Phase 2 record. The new runs are compared with them.*

*段階 1 の定義は「動作不変」なので、期待値は変更前に記録された値そのものである。新しい実行をそれと比べる。*

## Expected (written first) / 期待値（先に記す）

| # | Expected | From |
|---|---|---|
| S1 | Each module equal to its previous revision in every clock, on random stimulus over the whole input space: illegal encodings, errors, resets, strobes, prefetches, inbox writes, GOs. Equal means every output, every register and the restructured signals | the ruling's "behaviour unchanged" |
| S2 | The restructured logic proved equal for every input: the switch's GO check; the Formation's EW5 sum and repeat check; the Formation's split enables against RH004's single commit | the same |
| S3 | Phase 2: 3,914/3,914 bit-identical, with the summary equal to the record (traced clocks included). M1–M20 caught at their recorded counts; the new mutants M21–M23 caught | `rtl_sim/2026-09-27_phase2_l2_datapath/logs/`, the 2026-10-01 regression |
| S4 | Phases 3, 4 and 5: their logs repeat the record line for line, dates and durations aside | `rtl_sim/2026-10-01_phase6_board/logs/phase{3,4,5}_regression.txt` |
| S5 | Phase 6: the 18 board runs repeat; the 18 JSON and the 16 expected captures are identical, the captures byte for byte (cycle for cycle at the board's taps) | `rtl_sim/2026-10-01_phase6_board/` |
| S6 | Shorter chains in front of the store, the pending masks and `inbox_taken`; the longest left is MUL/MAC @PPM into the error registers and Accm | SD-22's reading |

## Observed / 観測値

| # | Observed | Verdict |
|---|---|---|
| S1 | `equiv_lockstep.py`: 8 runs (two modules, NMAX 1,008 and 2,048, seeds 1 and 2), 400,000 clocks each, **0 differences**. A Formation run executes about 318,000 instructions: every op; errors E4 ≈ 560, E5 ≈ 1,300, E8 ≈ 1,670, EW2 ≈ 390, EW3 ≈ 770, EW4 ≈ 730, EW5 ≈ 230, EW6 ≈ 280; about 24,000 store writes, 1,500 BCPs that copy, 2,000 copy clocks, 3,700 rises of `inbox_taken`. A switch run makes about 71,000 transactions, 8,700 GOs and 1,870 go-nows; refusals for each cause. Coverage per run in `logs/equiv_lockstep.txt` | as expected |
| S2 | `equiv_formal.py`: **5/5 proved** — the GO check at NMAX 1,008 and 2,048, the EW5 sum, the repeat check, the split enables (`logs/equiv_formal.txt`) | as expected |
| S3 | 3,914/3,914 bit-identical; the summary equals the record apart from the line with the durations. **23/23** mutants caught; M1–M20 with the recorded counts by group | as expected |
| S4 | `run_phase6.sh` (REGRESSION=1) from 2026-10-03T07:20:59Z: **ALL PHASE 2, 3, 4, 5 and 6 CHECKS PASSED**. Against the record (`logs/compare_regression.txt`): Phase 3's log is identical. The other logs differ only where explained: the resource ESTIMATE lines (Formation, switch, board top; the configurator's from RH003, before step 1); Phase 2's 23/23 mutants (20/20 recorded); the five regression lines of run_phase6.txt (the record ran REGRESSION=0); the line numbers of Icarus's 11 notes on wpms_formation.v (the same notes) | as expected |
| S5 | The 18 board runs: `cosim_board.txt` **identical** to the record. Every value of the eight items repeats at both budgets: g 0, T_wake 2, window 28, BCP 10, full-load sweep 1,023 / 2,063, EW2–EW6, 534 + 531 bundles, 1,320 + 1,316 banks. `expected/`: **34 of 34 identical** — the 18 JSON by value (the simulator's run time aside) and the 16 expected captures byte for byte: cycle for cycle at the board's taps | as expected |
| S6 | `gate_depth.py`: the store 136 → 33 levels; the pending masks 136 → 56; `inbox_taken` and `taken_due` 145–146 → 65–66; ADRS, Temp, SHV, LoopVal, JumpVal 127 → 23–27. Longest left: the error registers 112 and Accm 106 (was 146); the switch 99 → 77 (`logs/gate_depth.txt`) | as expected |

## How to repeat / 再現

```sh
python3 03_Sample_Implementations/hw/tools/equiv_lockstep.py --clocks 400000 --seeds 1,2
python3 03_Sample_Implementations/hw/tools/equiv_formal.py
python3 03_Sample_Implementations/hw/tools/gate_depth.py
BUILD=/tmp/r 03_Sample_Implementations/hw/de10_nano/run_phase6.sh          # Phases 2-6
python3 03_Sample_Implementations/hw/tools/compare_regression.py --build /tmp/r \
        --record 04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board
```

The tools take the previous revisions from git (`--ref`, default e3d4985). `equiv_formal.py` and `gate_depth.py` need `yowasp-yosys` (or `yosys`).

和文：段階 1 の変更（Formation RH005、スイッチ RH002）について、次のことを確かめた。
- 旧版との毎クロック比較で差はなかった。
- 書き換えた論理の等価を SAT で証明した。
- Phase 2 の結果が記録と同一だった。
- ゲート段数（概算）で、ストアと保留論理の前の連鎖が縮んだことを確かめた。

Phase 2〜6 の回帰も記録と同一だった。ボード 18 本の結果と期待キャプチャ 16 本はバイト単位で一致し、差は概算資源量などの説明済みの行だけだった。
