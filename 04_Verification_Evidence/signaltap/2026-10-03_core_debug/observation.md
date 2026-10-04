# Observation — the architect's SignalTap capture `ptsg_core_debug`: the wire equals the model / 観測——SignalTap 取得 ptsg_core_debug：線上の値がモデルと一致

*CC0 · 2026-10-03 · SILICON (SignalTap, the architect's capture), compared with the model (`hw/tools/l1_model.py`, bit-exact with the RTL since Phase 4). This is not one of the planned captures C1–C5 (`signaltap/phase6_pending/`), which stay pending.*

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7, `DE10_Nano_wpms` (50 MHz; the sweep period confirms it) |
| Bitstream | a build with the architect's SignalTap instance `ptsg_core_debug`; as I understand it, the second fit's RTL — to be confirmed. Timing is not closed |
| Capture | 8,192 samples of clk_sys (163.84 µs), exported 2026-10-03 21:24:52 (local time) |
| Signals | the Core's `state_num[11:0]`, `timing_signals[15:0]`, `stay_cnt[12:0]` and `stay_cnt_match`; the pins `HDMI_I2S`, `HDMI_LRCLK`, `HDMI_MCLK` and `HDMI_SCLK` |
| Files | `ptsg_core_debug.vcd.gz` (the export, compressed), `vcd_i2s_check.txt` (the analysis) |
| Analysis | `python3 03_Sample_Implementations/hw/tools/vcd_i2s_check.py ptsg_core_debug.vcd.gz --hours 2` |

## Expected (written before this capture, where named) / 期待値

| Item | Expected | From |
|---|---|---|
| Packet Stay | N = 1,008 clocks; Stay Set to next Stay Set = N (g = 0) | the test origin's N (`gen_switch_rom.py`); Phase 3 (g = 0) |
| Sweep period | 50 MHz / 48 kHz = 1,041.67 clocks, so 1,041 or 1,042 | one strobe per I2S frame (`wpms_i2s_master.v`) |
| Sweep against the frame | a constant offset, within ±1 clock (the 1,041.67-clock beat) | the strobe S_m = F_m − 1 SCLK |
| I2S words | Philips I2S, 24 bits; L = R (RT.OUT = 0b11) | `wpms_i2s_master.v`; the ROM's list |
| Sample values | the model's samples of the test origin, at G = DIP[1:0] × 4, so many sweeps after the GO | `l1_model.py` (bit-exact with the RTL, Phase 4) |

## Observed / 観測値

| Item | Observed | Verdict |
|---|---|---|
| Packet Stay | 1,008 clocks in each of 7 sweeps | as expected |
| Sweep period | 1,042, 1,041, 1,042, 1,042, 1,041, 1,042, 1,042 (mean 1,041.71) | as expected |
| Sweep against the frame | the packet's Stay Set 12 or 13 clocks before F_m, in all 8 frames | as expected (constant within ±1); the value itself was not predicted |
| I2S words | 8 frames decoded (the first with its right word only); L = R in all 7 complete frames | as expected |
| Sample values | **all 8 frames equal the model bit for bit**, 39,684,738 sweeps after the GO (826.77 s = 13 min 46.8 s), at G = 0 | as expected. G = 0 means DIP[1:0] = 00 |

The two unknowns were found from the closed form. The test origin is a sum of 1,008 equally spaced partials, so its value at any sweep has a closed form. A search over 2 hours of audio and the four G values fits the 8 samples at one point, with 2.0 LSB rms; the next best fit has 1,005 LSB rms. At that point the bit-exact model gives all 8 samples exactly. One sweep earlier or later, it is off by up to 760,000 LSB.

## What it shows / 示すこと

- **The wire is bit-exact.** The 24-bit words on the I2S pins equal the model's. The whole chain does this on silicon: the Core, the Formation, the sequencer, L1, the output stage and the I2S transmitter.
- **13 min 47 s of phase updates, none wrong.**
  - Every packet's window program updates PH0, PHD1 and PHD2 in the store (LDM, ADD @PPM, STM; `wpms_packet.pfasm`), each sweep building on the last. The match at sweep 39,684,738 means none of those updates failed.
  - These are the store read and the adder into Accm, of the kind the second fit's timing report lists. The worst path, MUL/MAC @PPM, is not used by the test origin.
- **The sweeps are locked to the audio frames:** 1,008 clocks of packet, one sweep per frame.
- **G = 0 on this board.**
  - DIP[1:0] = 00 is the loudest setting, 72 dB above G = 12, which the RTL-SIM figures assume. The board README of 2026-10-01 said 00 by mistake; it says 11 since 2026-10-04. At G = 0, a single partial of the test origin is near full scale.
  - The output therefore clips wherever the envelope exceeds about 1.03 partials. That is the top of every beat over about 85 % of each 255.65 s cycle.
  - This capture lies where the envelope was 0.84 partials, 59.8 s into the fourth cycle.
  - SW[1:0] = 11 (both up) gives G = 12, the designed level: −12.44 dBFS at the peak right after the GO, never clipping.
- **What it does not show:** timing margin. The build is not timing-closed; it ran at room temperature on this board.

## 和文

- 取得したのは Core の信号と I2S のピンで、50 MHz で 8,192 標本（163.84 µs）。
- パケットの Stay は毎回 1,008 クロック。掃引の周期は 1,041 または 1,042 クロック（平均 1,041.71、50 MHz ÷ 48 kHz）で、オーディオのフレームにロックしている。
- I2S の 8 フレームを復号した。L と R は一致する。
- **値はモデルとビット単位で一致した。** GO から 39,684,738 掃引目（13 分 46.8 秒）、G = 0 の位置である。
  - 位相は、パケットごとに Formation のストアで累積する（LDM、ADD @PPM、STM）。よって、この約 4,000 万掃引のあいだ、更新は一度も誤っていない。
  - これらは、第 2 回フィットの報告で違反した経路と同じ系統である。最悪の MUL/MAC は、試験原点では使われない。
- DIP[1:0] = 00（G = 0）は G = 12 より 72 dB 大きく、周期の約 85 % で波形の山がフルスケールでクリップする。設計どおりの音量は SW[1:0] = 11（両方上）。
- タイミングの余裕は示さない。
