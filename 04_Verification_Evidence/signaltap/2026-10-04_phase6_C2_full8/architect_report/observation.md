# C2 full8 — SILICON observation / 実機試験結果

**結果: 指定された主要項目1～5はすべて合格。** 実機エラーなし。バンドル28/28、比較可能なPCMバンク3/3がモデルと一致。

## Acquisition / 取得条件

- Date/time: 2026-10-04 21:15:28 JST (SignalTap trigger).
- Board: DE10-nano, JTAG `DE-SoC [USB-1]`, FPGA `@2: 5CSEBA6(.|ES)/5CSEMA6/.. (0x02D020DD)`.
- Target: `DE10_Nano_wpms`, 50 MHz, NMAX=1008, SYS_DUTY=30. Quartus Prime Lite 23.1std.1.
- Local build: Fitter successful 2026-10-04 20:56:46; SOF updated 20:57. The existing running design was used; no programming was performed in this test. The local SOF SHA-256 is in `bitstream_sha256.txt`; it is a local-file identifier, not a silicon readback hash.
- Repository HEAD: `804023829a90fa25c46bee7247d03304c605edd3` (working files may contain uncommitted changes).
- BRD readback: source=0, probe=002FCF. SW=3: SW[1:0]=11 (G=12), SW[2]=0, SW[3]=0. All three PLL lock bits=1.
- SignalTap: clk_sys posedge, 4,096 samples, 405 data bits. Trigger: `tap_ctl[43:40] = 1000`, Basic AND. Storage qualifier disabled.
- Pre-trigger: 512 samples = 12.5% (the SignalTap Pre setting described as 12% in the instruction). Saved log confirms P=1 immediately before trigger and P=8 at trigger sample 512.
- Acquisition length: 81.92 us. Native Quartus VCD export uses 1 ps units and 20,000 ps clock period (50 MHz).

## Action / 実施手順

1. Stopped the previously waiting acquisition and preserved its snapshot separately.
2. Reset through BRD source[0] 1 -> 0; both values were read back (`reset.log`).
3. Armed SignalTap once with Run Analysis and verified Waiting for trigger.
4. Ran `quartus_stp -t host/wpms_phase6_full8_1008.tcl` in the project directory, saving stdout/stderr to `full8.log`.
5. SignalTap triggered at 21:15:28 and completed. Saved `C2_full8.stp`; exported the captured log natively to `C2_full8.vcd`, then gzip-compressed it without changing the contents.

Host result: GO 2 applied; logged APPLIED_SAMPLE=1,541,413. No refused writes, no host error. `SWEEP_CLOCKS_MAX=0x404` (1028); `STROBE_INTERVAL=0x412` (1042). The sweep counter register has its own definition; the requested tap-measured strobe-to-asleep duration is 1023 clocks. The RTL-SIM expected JSON also records the bench maximum register as 1028.

## Expected vs observed / 期待値との比較

| Item | Quantity | Requirement / RTL-SIM | Observed SILICON | Verdict |
|---|---|---|---|---|
| 1 | Packet gap g | 0 clocks | 0 | PASS |
| 2 | Strobe -> first packet_start | <=4; expected 2 | 2 | PASS |
| 3 | Window / floor | 28 / 30; floor <=32 | 28 / 30 | PASS |
| 4 | Full take-set BCP -> inbox_taken | <=10; expected 10 | 10 | PASS |
| 5 | Full-load sweep, sum N=1008 | <=1041; expected 1023 | 1023 (3 complete full-load sweeps) | PASS |
| 7 | Bundles equal to model | All compared | 28/28 | PASS |
| 7/8 | PCM banks equal to model | All compared | 3/3 | PASS within compared coverage |
| — | Error flags | None | None | PASS |
| — | Strobe intervals | 1041 or 1042 | 1041, 1042 | PASS |
| — | K counts within packets | Sequential | k_ok=true | PASS |

There are 28 packets and 4 strobes in 4,096 unqualified samples. The measurement of the full take-set is `bcp_full_take=10`; `bcp=[2,2]` describes the other observed housekeeping cases and must not be substituted for the full take-set measurement.

## Analysis provenance and coverage / 解析方法と範囲

`observed.json` is produced by the repository's unchanged `phase6_evidence.py` with budget 50 and the actual `full8.log`. `analysis.log` contains the same output. `expected_full8_50.json` is copied from the pre-board RTL-SIM evidence; its `observed.capture` section is the comparable 4,096-sample capture.

The expected directory layout for the customer's oracle was absent on this PC. The local adapter `analyze_local_oracle.py` only supplies the existing oracle's path (`sys.path` and `cosim_sweep.ORACLE`); no model or RTL calculations were changed. Oracle source: `<local>\FPGA_Spectrum_Engine\04_Verification\oracle\wpms_layer1_oracle.py`, SHA-256 `68AFAC62FDDF6685533530D09A8CA29CE2BCDBE094CB4F75001BD923DA05AB20`.

The model starts at the complete take of strobe 1,541,412, as selected by the analyzer from the host log and capture. Thus three post-take PCM banks are comparable, all equal. The first captured bank depends on prior origin history and is excluded by the analyzer. The template's 4/4 PCM coverage from a reset-based simulation is therefore not claimed for this acquisition. No model problems or value mismatches were reported. Three PCM samples are insufficient for a spectrum judgment; spectrum fields are null.

`capture_validation.json` independently checks the saved STP's sample count, trigger position and P=1 -> 8 transition. The board remains in the full8 state after this test. No C3–C5 test or injection was performed.
