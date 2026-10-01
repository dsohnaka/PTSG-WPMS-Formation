# Note to the customer team — the host path: ISSP carries port 0 / 顧客チームへの報告——ホスト経路：ポート 0 を ISSP が運ぶ

*CC0 · Layer 4 note from the PTSG-WPMS-Formation silicon phase to the WPMS / FPGA Spectrum Engine amanuensis (customer side), conveyed by the architect. Prepared 2026-10-01 on the architect's ruling of that day (discrepancy register SD-19). Not sent from this session: the customer's repository is outside its scope.*

*PTSG-WPMS-Formation シリコン化段階から WPMS／FPGA Spectrum Engine 祐筆殿（顧客側）への報告。アーキテクト経由で伝達。2026-10-01 の裁定（食い違い台帳 SD-19）に基づき準備した。本セッションからは送付していない（顧客リポジトリは本セッションの範囲外）。*

---

## 1. What was decided / 決まったこと

For the silicon sample, the profile's host path to port 0 of the input switch is Intel's **In-System Sources and Probes (ISSP) over JTAG**, carrying **addressable transactions** of Ch.5 §5.6's map. The architect ruled it on 2026-09-30 for sure manual operation on the board, and adopted it formally on 2026-10-01. In this respect the profile **overrides C5-D8** (Fixed), which names a JTAG-to-Avalon master as the write path and says "ISSP is no longer the parameter write path".

シリコン試作では、入力スイッチのポート 0 へのホスト経路を **JTAG 経由の ISSP** とし、第 5 章 §5.6 のマップに対する**アドレス付きトランザクション**を運ぶ。2026-09-30 にアーキテクトが実機での確実な手動操作のために裁定し、2026-10-01 に正式採用した。この点でプロファイルは **C5-D8（Fixed）を上書きする**。C5-D8 は書込み経路を JTAG-to-Avalon マスターとし、「ISSP はもはやパラメータ書込み経路ではない」としている。

## 2. What does not change / 変わらないもの

- The address map of §5.6, the ports, the ownership rules as written for ports 1 and 2, stage-arm-go (§5.4), the checks of PR-1 and PR-2, APPLIED_SEQ / APPLIED_SAMPLE, and the ROM port (§5.8).
- The chapter's objection to ISSP — "with hundreds of slots, addressable writes are the right tool" — does not arise, because the ISSP path **is** addressable: one transaction reaches any word of the map.
- ISSP keeps its role of §5.7 for probes as well (live status; the inspector).

§5.6 のアドレスマップ、ポート、置く・構える・放つ、PR-1・PR-2 の検査、APPLIED_SEQ／APPLIED_SAMPLE、ROM ポートは変わらない。章の懸念（「数百のスロットにはアドレス付き書込みが適する」）は生じない。ISSP 経路そのものがアドレス付きだからである。

## 3. The realization / 実現

One ISSP instance, **HOST**: 48 source bits and 36 probe bits.

| Field | Bits | Meaning |
|---|---|---|
| source `[31:0]` | WDATA | the word to write |
| source `[43:32]` | ADDR | the word address of §5.6 |
| source `[44]` | WR | write toggle |
| source `[45]` | RD | read toggle |
| probe `[31:0]` | RDATA | the word read (after a write, the word read back) |
| probe `[32]`, `[33]` | WR_ACK, RD_ACK | equal to WR, RD when the transaction is done |
| probe `[34]` | REJ | the switch refused the write (frozen item, failed GO check, read-only or unmapped word) |

- A flipped toggle makes exactly one port-0 transaction; nothing happens while the toggles equal their acknowledges, so the fields can be edited freely.
- Every bit passes two flip-flops and the fields settle before they are taken; at a design reset the acknowledges take the toggles' values, so no stale toggle replays a transaction.
- A deterministic controller used for white-box verification drives the same bits through an OR with the ISSP sources (0 on the board).

Evidence (RTL-SIM, the silicon phase's Phase 5): 17,679 transactions over fifteen system runs, every answer equal to a transaction-level model of Ch.5's semantics; 16,229 of them on port 0 through this bit protocol, with skewed fields and design resets in the middle of transactions. Report: `04_Verification_Evidence/reports/phase5_switch.md` (PTSG-WPMS-Formation).

## 4. Proposed for Ch.5's next version / 第 5 章 次版への提案

1. **§5.7 / C5-D8:** admit ISSP as a transport of port 0 when it carries addressable transactions (address, data, write and read toggles; data and acknowledges on the probe), beside the JTAG-to-Avalon master; or list it with §5.11's Arena alternatives.
2. Keep the sentence on ISSP's probe role as it is.

§5.7／C5-D8 に、アドレス付きトランザクションを運ぶ ISSP をポート 0 の伝送路として JTAG-to-Avalon マスターと並べて認める（または §5.11 のアリーナ代替に加える）ことを提案する。ISSP のプローブとしての役割の記述はそのまま。

## 5. Where to look / 参照

- The register of discrepancies: `04_Verification_Evidence/reports/discrepancies.md`, SD-19.
- The RTL: `03_Sample_Implementations/hw/switch/wpms_host_bridge.v`, `wpms_system.v` (the OR), `wpms_issp.v`.
- The by-hand protocol for the Quartus editor and the host scripts: `03_Sample_Implementations/hw/tools/host/README.md`.
