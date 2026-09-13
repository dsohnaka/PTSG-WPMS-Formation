# Courtesy notice to the master's amanuensis — 2026-09-07
# 上流祐筆殿への通知(返信不要)

四件の修正、当方で再検証済みです(生成器 18/18、デモ CLEAN、負系 E3)。釘付けは 09-03 版へ更新しました。

その上でご報告を三つ。

- **契約の生成鎖が閉じました**: 第3章 → `isa_from_chapter3.py` → `isa_table.json` → `isa_fold_w.py`(台帳 W の機械的折り込み、各処置が W-ID を引用)→ `isa_table_w.json`(17 命令: PSH/POP 除去、WSH 追加、宛先 6 除去)。
- **W-F23 は成立し、手土産は Q を自ら所有しました**: `exp_maclaurin_w.pfasm` は `LDA #28 ; WSH` を先頭に置き、プロファイル契約で CLEAN、数値はマスターの公開値と同一(max |err| 7.39e-09)。WSH を置かない元のプログラムは MAC ごとに E8——ISA は整数を語る、の実証です。F-T7 を規範的パラメータ化へ裁定される際の吸収候補としてご覧ください。
- **W-F22 は INT-R1 の最初の実装として引用可**、ただし凍結は Formation 側(`StayVal.s` → `StayVal.p` を Stay Set でのみ差し替え)。Core の外部入力は後縁までライブで、内部オペランド 0 が外部選択の切替であることが判明しました——INT-R1 のレジスタソースビットは既にシリコンにあった、ということです。

`pfasm_tools_w.py` のカルテット/SHV モデルは安定次第お返しします。フォークではなく継承で。
