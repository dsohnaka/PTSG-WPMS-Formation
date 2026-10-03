# Observation — the first sound: the test origin on the board / 観測——初音：基板上の試験原点

*CC0 · 2026-10-03 · SILICON, qualitative: the architect's oscilloscope and loudspeaker, through an HDMI audio extractor. No SignalTap capture was taken; the captures C1–C5 stay pending (`signaltap/phase6_pending/`).*

| | |
|---|---|
| Board, revision | DE10-nano 5CSEBA6U23I7, `DE10_Nano_wpms` (50 MHz) — to be confirmed |
| Bitstream | as I understand it, the second fit's (SD-22 step 1: Formation RH005, switch RH002; commit 8815e35) — to be confirmed. clk_sys 50 MHz at 50 % duty; setup slack at the slow corner −6.976 ns, so timing is not closed (`quartus/2026-10-03_DE10_Nano_wpms_fit2/`) |
| Signal path | ADV7513 HDMI TX (I2S, 48 kHz) → HDMI audio extractor → oscilloscope and loudspeaker |
| What plays | the test origin, written by the ROM (port 3) after reset: module 0, block 0, N = 1,008 |

## Expected / 期待値

These values were derived after the observation was reported. They come from the ROM's integers (`hw/tools/gen_switch_rom.py`, 2026-09-30; customer Ch.3 §3.10) by the arithmetic of a sum of equal partials. The RTL plays this score bit-exact with the model (`reports/phase5_switch.md` §3.3).

| Quantity | Expected | From |
|---|---|---|
| The partials | 1,008 partials from 996.000 to 999.939 Hz, 3.912 mHz apart, with equal amplitude and phase 0 at the GO | OM0 89,120,571, OMD1 350, LP = LPT = log2 0.97, phases 0 |
| The tone | one carrier at 997.97 Hz, the partials' centre | a sum of equally spaced partials is the centre frequency times an envelope |
| Amplitude modulation | envelope \|sin(πN·df·t) / sin(π·df·t)\|: nulls every **253.62 ms**, 100 % deep | 1 / (N·df) |
| Slow change | the beats' height follows 1 / \|sin(π·df·t)\|. Loudest right after the GO, when all partials are in phase (peak −12.44 dBFS in RTL-SIM, at G = 12). Relative to that peak: −22 dB after 1 s, −42 dB after 10 s, −51 dB after 30 s, −60 dB at about 2 min 8 s. Then rising again to a full burst at **4 min 15.7 s** | 1 / df = 255.65 s |
| Stability | the same waveform after every reset or KEY[1] | the ROM replays the same 21 writes |

## Observed (2026-10-03, reported by the architect) / 観測値

> シリコンに焼いて、HDMIオーディオ分離器に接続し、オシロスコープとスピーカーに接続しているのですが、おそらくあなたが意図されている通りのものと思われる、ゆっくりとした変化と250ｍS周期の振幅変調された１KHz正弦波を基調とする波形が、きわめて安定的に出力されています。

In English: a waveform based on a 1 kHz sine, amplitude-modulated with a period of 250 ms, with slow changes, very stable.

## Verdict / 判定

**Consistent with the expected values, qualitatively:**
- the carrier is about 1 kHz (expected 997.97 Hz);
- the modulation period is about 250 ms (253.62 ms);
- there is a slow change (the 255.65 s envelope);
- the output is stable.

Not yet measured: the carrier frequency and the null spacing to a few per mille, the return of the burst at 4 min 15.7 s, and the level.

**Later the same day: the SignalTap capture `ptsg_core_debug`** (`signaltap/2026-10-03_core_debug/`). Its 8 audio frames equal the model bit for bit, 13 min 46.8 s after the GO, at G = 0. So DIP[1:0] was 00: 72 dB above the RTL-SIM figures (G = 12), and the waveform clips at the top of every beat over about 85 % of each cycle. SW[1:0] = 11 gives the designed level.

- **What this shows.** The whole chain plays the test origin from the ROM after reset, on silicon: PTSG-Core RH031p, the Formation, the sequencer, L1, I2S and the ADV7513's HDMI audio. The ADV7513's configuration had been checked only against its data sheet until now.
- **What this does not show:** timing margin. This bitstream misses clk_sys by 6.976 ns at the slow corner (the slowest silicon at 85 °C). This board at room temperature runs it, but nothing is guaranteed at a higher temperature or on a slower part. Most failing endpoints lie on paths the test origin seldom sensitizes: the error registers, the GO check, EW5. The SILICON captures C1–C5 wait for a timing-closed build (SD-22).

**和文.**
- 試験原点は、1,008 本の等振幅・位相 0 の部分音（996.000〜999.939 Hz、間隔 3.912 mHz）でできている。その和は 997.97 Hz の搬送波に、ディリクレ核の包絡をかけた形になる。
  - 包絡の零点は 253.62 ms ごとに来る。
  - 全体は 255.65 s（約 4 分 16 秒）で繰り返す。リセット直後が最も大きく、約 2 分 8 秒で最小（最初の山から約 −60 dB）になり、4 分 16 秒で再び大きな山に戻る。
- 報告された「約 1 kHz、250 ms 周期の振幅変調、ゆっくりした変化、安定」は、この期待と定性的に一致する。
- この観測は、シリコン上で Core から HDMI 音声までの全経路が動くことを示す。タイミングの余裕は示さない。このビットストリームは遅いコーナーで −6.976 ns である。
- SignalTap の取得 C1〜C5 は、タイミングが閉じたビルドで行う。
