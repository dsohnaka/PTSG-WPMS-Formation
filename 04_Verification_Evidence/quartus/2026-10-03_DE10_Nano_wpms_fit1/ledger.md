## Resource ledger / 資源台帳 (Fitter "Resource Utilization by Entity"; class SILICON)

Core's format / Core の書式:

| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs | Notes |
|---|---|---|---|---|---|
| 2026-10-03 | DE10_Nano_wpms (50 MHz): Core RH031p, Formation RH004, cfg RH003 | 457.7 | 414.3 | 773 (725) | inside WPMS (wpms_l2_top), score wpms_r1d, ISMCE port included |

Per entity / 実体ごと — total (entity-only):

| Entity | ALMs needed | Comb. ALUTs | Registers | M10K | DSP | Block memory bits |
|---|---|---|---|---|---|---|
| board top (all) | 11052.8 (121.4) | 14312 (118) | 15318 (521) | 22 | 23 | 59013 |
| wpms_system | 10618.7 (0.5) | 13708 (1) | 14431 (6) | 22 | 23 | 59013 |
| synthesizer (L2 + L1 + out) | 8661.6 (0.0) | 10706 (0) | 12335 (0) | 18 | 23 | 43653 |
| L2: Core + Formation + seq. | 7431.6 (3.8) | 8716 (12) | 10383 (0) | 13 | 3 | 35072 |
| PTSG-Core (RH031p) | 457.7 (414.3) | 773 (725) | 303 (231) | 4 | 0 | 32768 |
|   its instruction memory | 43.3 (0.0) | 48 (0) | 72 (0) | 4 | 0 | 32768 |
| Formation | 6788.7 (6788.7) | 7865 (7865) | 9716 (9716) | 9 | 3 | 2304 |
| sequencer | 181.3 (181.3) | 66 (66) | 364 (364) | 0 | 0 | 0 |
| L1 module | 831.7 (582.4) | 1410 (968) | 1552 (998) | 5 | 20 | 8581 |
|   its sine | 91.0 (84.0) | 170 (156) | 387 (376) | 1 | 7 | 286 |
|   its exp2 | 144.0 (136.6) | 243 (229) | 144 (136) | 2 | 9 | 7971 |
| output stage | 336.7 (336.7) | 492 (492) | 283 (283) | 0 | 0 | 0 |
| I2S master | 28.3 (28.3) | 31 (31) | 60 (60) | 0 | 0 | 0 |
| strobe sync | 33.2 (33.2) | 57 (57) | 57 (57) | 0 | 0 | 0 |
| input switch | 1692.2 (1644.2) | 2818 (2772) | 1493 (1410) | 4 | 0 | 15360 |
|   its ROM (TORG) | 48.0 (0.0) | 46 (0) | 83 (0) | 3 | 0 | 11264 |
| host bridge | 35.5 (35.5) | 26 (26) | 187 (187) | 0 | 0 | 0 |
| ISSP HOST | 62.1 (0.0) | 58 (0) | 110 (0) | 0 | 0 | 0 |
| ISSP STAT | 76.0 (0.0) | 23 (0) | 138 (0) | 0 | 0 | 0 |
| ISSP INSP | 60.3 (0.0) | 20 (0) | 106 (0) | 0 | 0 | 0 |
| ISSP BRD | 24.0 (0.0) | 23 (0) | 33 (0) | 0 | 0 | 0 |
| video carrier | 20.2 (20.2) | 38 (38) | 24 (24) | 0 | 0 | 0 |
| ADV7513 configurator | 140.5 (140.5) | 236 (236) | 145 (145) | 0 | 0 | 0 |
| PLL clk_sys | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| PLL MCLK | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| PLL pixel | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| SignalTap | absent | | | | | |
| JTAG hub | 128.0 (0.5) | 189 (1) | 164 (0) | 0 | 0 | 0 |
