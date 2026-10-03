# Observation — SD-22 step 2: what changed on purpose, and nothing else / 観測——SD-22 段階 2：意図した変更だけが起きたこと

*CC0 · 2026-10-03 · RTL-SIM (Icarus Verilog 12.0, `-g2012`), formal (Yosys 0.69 builds each problem; CaDiCaL 1.9.5, python-sat, solves it), ESTIMATE (Yosys gate and LUT depth).*

*Formation RH006 against RH005, and switch RH003 against RH002, the previous revisions taken from commit 8815e35 (the second fit's RTL). Ruling 2026-10-03: step 2 without a new round of questions. The board top's clk_sys duty cycle (SD-23) changes no simulation (`SYS_DUTY` reaches only the Intel PLL).*

*段階 2 で意図して変えたのは、MUL/MAC の E8（と、その X クロックに重なったプリフェッチの EW2）を 1 クロック遅れて上げることだけである。ほかはすべて段階 1 の記録と同じでなければならない。*

## Expected (written before the recorded runs) / 期待値（記録する実行の前に記す）

| # | Expected | From |
|---|---|---|
| T1 | Switch RH003 equal to RH002 in every clock, every register and output. Formation RH006 equal to RH005 in every clock, except: an E8 of MUL/MAC, and an EW2 met in a MUL's or MAC's X clock, are raised one clock later with **the same code and SN**; in that one clock Accm holds the product (restored at the next edge) and the instruction then in X does nothing | RH006's header; `phase6_silicon.md` §10.4 (step 2 as planned) |
| T2 | Proved (UNSAT) for every input and state: the switch's GO path where it is used, and its check; the Formation's pre-read, late E8, idle test, split enables and EW5 lookahead (one clock from any state). Each negative control comes back SAT | the same; `tools/equiv_formal.py` RH002 |
| T3 | Phase 2: the 3,914 recorded cases bit-identical to the golden model, the summary equal to the record but for the new group `late` (9 directed cases, all passing). Every mutant killed, M1–M23 with the recorded counts in the recorded groups | `rtl_sim/2026-09-27_phase2_l2_datapath/logs/`, step 1's run |
| T4 | Phases 3, 4, 5: the logs repeat the record, dates and durations aside — no E8 occurs in their runs, and the switch's behaviour is unchanged | `rtl_sim/2026-10-01_phase6_board/logs/phase{3,4,5}_regression.txt` |
| T5 | Phase 6: the 18 board runs and the 34 expected files identical to the record; the project check passes with the 50 MHz revision at 30 % high | `rtl_sim/2026-10-01_phase6_board/` |
| T6 | Shorter chains in front of Accm and the error registers (no store read, no overflow compare), the pending masks and `inbox_taken` (no sum of N), and the switch's results (no address decode, no frozen bits, no adder tree) | SD-22's reading of the second fit |

## Observed / 観測値

| # | Observed | Verdict |
|---|---|---|
| T1 | `equiv_lockstep.py`: 8 runs (two modules, NMAX 1,008 and 2,048, seeds 1 and 2), 400,000 clocks each, **0 differences** (`logs/equiv_lockstep.txt`). The switch: every output, register and touched signal equal in every clock. The Formation: equal in every clock outside the two cases of T1. In them the new revision raised the reference's error, with the same code and SN, one clock later, every time: per run 1,101–1,188 late E8s of MUL/MAC (359–396 with an EW2 in the same clock) and 768–854 held-back EW2s. A Formation run executes about 317,000 instructions, all 16 ops, and raises every code (E4 562–638, E5 1,226–1,316, E8 1,569–1,634, EW2 1,112–1,233, EW3 744–809, EW4 713–772, EW5 181–224, EW6 234–266). It also has 7,325–8,273 BCPs (1,357–1,447 that copy) and 3,607–3,974 rises of `inbox_taken`. A switch run makes about 71,000 transactions, 8,600–8,700 GOs and 1,860–1,880 go-nows, refused for every cause | as expected |
| T2 | `equiv_formal.py --step 2`: **13/13 proved** (UNSAT), CaDiCaL 1.9.5 taking 1–791 s each (`logs/equiv_formal.txt`). The switch: the GO path where it is used, and its check, at NMAX 1,008 and 2,048 (4 proofs). The Formation, one clock from any state: the pre-read and the late E8 (2). EW5 in four claims: the terms, the registers, the direct tree, and the arithmetic at NMAX 1,008 and 2,048 (5). For every state and input: the idle test and the split enables (2). The three negative controls come back SAT, as they must: the bound off by one, and the texts of M26 and M27 | as expected |
| T3 | `cosim_l2`: **3,923/3,923** bit-identical (`logs/phase2_regression.txt`). Against the record the summary differs only by the new group `late`: 9/9, 47 instructions, first errors E8 3, EW2 1, EW5 1. Hence 105,519 → 105,566 instructions, 920 → 925 error cases, and the mnemonic counts by `late`'s 47. Mutants **29/29** (`logs/cosim_mutants.txt`). M1–M20 fail as many cases in every recorded group as recorded, but M6 (random 86 → 68): M6 now breaks the CUR alias of the read ahead, and the new M29 that of the registered decode (writes; random 63). Two columns are new: `late`, and the RTL's own checks, now counted with the bench's under invariant/protocol (`cosim_l2.py` RH002) | as expected |
| T4 | `run_phase6.sh` (REGRESSION=1) from 2026-10-03T11:49:53Z: **ALL PHASE 2, 3, 4, 5 and 6 CHECKS PASSED** (`logs/run_phase6.txt`). Against the record (`logs/compare_regression.txt`), Phases 3, 4 and 5 differ only where explained. In each, Icarus gives more of the same note ("@* is sensitive to all words" in an array, 11 → 20) for RH006's new always blocks. Phase 4 also differs in the configurator's ESTIMATE (its RH003, before step 1). Phase 5 also differs in its switch mutants, 23/23 with the new W23 (22/22 recorded; `logs/cosim_switch_mutants.txt`), and in the switch's ESTIMATE ($lut 2,938 → 2,695) | as expected |
| T5 | The 18 board runs: `cosim_board.txt` **identical** to the record. `expected/`: **34 of 34 identical**, the 18 JSON by value and the 16 expected captures byte for byte, so the board's taps are the same cycle for cycle. The project check passes with the 50 MHz revision at 30 % high, 7/7 mutants (`logs/make_quartus_project.txt`). Also different from the record: the five regression lines of `run_phase6.txt` (the record ran REGRESSION=0), the board top's ESTIMATE, and the same Icarus notes | as expected |
| T6 | `gate_depth.py`, gates and 6-LUT levels (`--lut`), step 1 → step 2 (`logs/gate_depth.txt`, `logs/gate_depth_lut.txt`): the error registers 112 → **50** gates, 44 → **14–16** LUT levels; Accm 106 → 81, 43 → 34; `taken_due`, `inbox_taken` 65–66 → 42–43, 35–36 → 15–16; the pending masks 56 → 40, 30 → 13; SWEEP.a, copied 54 → 38, 28 → 11; the switch's results 77 → 67, 16 → 13. The new registers: `w_hi` 82 / 40 (behind the multiplier, which Quartus puts in DSP blocks); `ew5_s`, `ew5_c` 43–44 / 23; `store_q`, `inbox_q` 34–39 / 21–22. These last counts overstate the new paths, which have no adder (`phase6_silicon.md` §11.5). Resources (`logs/resource_split.txt`): the Formation +2,030 LUTs, about 1,800 of them the EW5 lookahead | as expected; the new paths are the ones to watch in the third fit |

## How to repeat / 再現

```sh
python3 03_Sample_Implementations/hw/tools/equiv_lockstep.py --clocks 400000 --seeds 1,2
python3 03_Sample_Implementations/hw/tools/equiv_formal.py --step 2       # pip install python-sat
python3 03_Sample_Implementations/hw/tools/gate_depth.py --ref 8815e35
python3 03_Sample_Implementations/hw/tools/gate_depth.py --ref 8815e35 --lut
BUILD=/tmp/r 03_Sample_Implementations/hw/de10_nano/run_phase6.sh          # Phases 2-6
python3 03_Sample_Implementations/hw/tools/compare_regression.py --build /tmp/r \
        --record 04_Verification_Evidence/rtl_sim/2026-10-01_phase6_board
```

`equiv_lockstep.py` and `equiv_formal.py --step 2` take the previous revisions from commit 8815e35 (`--ref`). `equiv_formal.py` and `gate_depth.py` need `yowasp-yosys` (or `yosys`); `equiv_formal.py` also needs CaDiCaL from `python-sat`. `logs/resource_split.txt` says how its variants were made.

和文：段階 2 の変更（Formation RH006、スイッチ RH003）について、次のことを確かめた。
- 旧版との毎クロック比較で、意図した 2 つの遅れ（MUL/MAC の E8 と、その X クロックの EW2。同じコードと SN）のほかに差はなかった。
- 書き換えた論理と先読みの正しさを SAT で証明した（13/13）。
- Phase 2 の結果は記録と同じで、新しい群 late を含めモデルとビット一致した。変異体は 29/29 を検出した。

Phase 2〜6 の回帰もすべて PASS した。記録との差は説明済みの行（注意の件数、変異体の追加、概算資源量、プロジェクトのデューティ表記）だけで、ボード 18 本の結果と期待キャプチャ 16 本はバイト単位で一致した。
