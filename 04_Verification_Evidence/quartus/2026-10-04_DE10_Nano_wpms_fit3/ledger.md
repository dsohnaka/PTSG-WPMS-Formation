## Resource ledger / 資源台帳 (Fitter "Resource Utilization by Entity"; class SILICON)

Core's format / Core の書式:

| Date | Revision | ALMs needed (full trim) | Core proper (entity-only) | Comb. ALUTs | Notes |
|---|---|---|---|---|---|
| 2026-10-04 | DE10_Nano_wpms (50 MHz, clk_sys 30 % high): Core RH031p, Formation RH006, switch RH003, cfg RH003 | 500.9 | 454.3 | 800 (751) | inside WPMS (wpms_l2_top), score wpms_r1d, ISMCE port included |

Per entity / 実体ごと — total (entity-only):

| Entity | ALMs needed | Comb. ALUTs | Registers | M10K | DSP | Block memory bits |
|---|---|---|---|---|---|---|
| board top (all) | 11321.7 (100.7) | 14346 (118) | 14835 (527) | 22 | 23 | 59013 |
| wpms_system | 10909.5 (1.7) | 13742 (1) | 13956 (6) | 22 | 23 | 59013 |
| synthesizer (L2 + L1 + out) | 8988.8 (0.0) | 11032 (0) | 11865 (0) | 18 | 23 | 43653 |
| L2: Core + Formation + seq. | 7733.0 (2.8) | 8999 (12) | 9931 (0) | 13 | 3 | 35072 |
| PTSG-Core (RH031p) | 500.9 (454.3) | 800 (751) | 308 (236) | 4 | 0 | 32768 |
|   its instruction memory | 46.7 (0.0) | 49 (0) | 72 (0) | 4 | 0 | 32768 |
| Formation | 7048.0 (7048.0) | 8130 (8130) | 9267 (9267) | 9 | 3 | 2304 |
| sequencer | 181.2 (181.2) | 57 (57) | 356 (356) | 0 | 0 | 0 |
| L1 module | 827.4 (578.1) | 1411 (969) | 1532 (982) | 5 | 20 | 8581 |
|   its sine | 96.4 (89.4) | 170 (156) | 388 (379) | 1 | 7 | 286 |
|   its exp2 | 137.9 (130.9) | 243 (229) | 142 (134) | 2 | 9 | 7971 |
| output stage | 361.6 (361.6) | 534 (534) | 280 (280) | 0 | 0 | 0 |
| I2S master | 29.7 (29.7) | 31 (31) | 61 (61) | 0 | 0 | 0 |
| strobe sync | 37.2 (37.2) | 57 (57) | 61 (61) | 0 | 0 | 0 |
| input switch | 1659.7 (1611.2) | 2526 (2480) | 1481 (1400) | 4 | 0 | 15360 |
|   its ROM (TORG) | 48.5 (0.0) | 46 (0) | 81 (0) | 3 | 0 | 11264 |
| host bridge | 32.1 (32.1) | 26 (26) | 193 (193) | 0 | 0 | 0 |
| ISSP HOST | 61.1 (0.0) | 58 (0) | 112 (0) | 0 | 0 | 0 |
| ISSP STAT | 75.8 (0.0) | 23 (0) | 138 (0) | 0 | 0 | 0 |
| ISSP INSP | 59.3 (0.0) | 20 (0) | 106 (0) | 0 | 0 | 0 |
| ISSP BRD | 24.0 (0.0) | 23 (0) | 34 (0) | 0 | 0 | 0 |
| video carrier | 20.2 (20.2) | 38 (38) | 22 (22) | 0 | 0 | 0 |
| ADV7513 configurator | 139.8 (139.8) | 236 (236) | 139 (139) | 0 | 0 | 0 |
| PLL clk_sys | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| PLL MCLK | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| PLL pixel | 0.0 (0.0) | 0 (0) | 0 (0) | 0 | 0 | 0 |
| SignalTap | absent | | | | | |
| JTAG hub | 127.5 (0.5) | 189 (1) | 157 (0) | 0 | 0 | 0 |
