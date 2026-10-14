# 2026-10-14 — host control GUI, V1 to V3 (OUTSIDE WPMS) / ホスト制御 GUI の V1〜V3

*CC0. The report is `../../reports/gui_v1_v3.md`. The tools are in `03_Sample_Implementations/hw/tools/host/gui/`.*

| File | What |
|---|---|
| `logs/test_gui_bridge.txt` | V1 (the bridge under tclsh 8.6.14 against `issp_standin.tcl`, 9 mutants) and V2 (the controller headless, with the test's freeze model). Class: stand-in. |
| `logs/check_host_tcl.txt` | The existing host-script check, unchanged and still green. Class: stand-in. |
| `logs/cosim_gui_replay_v2_*.txt` | V3: the V2 step logs through `wpms_system` (Icarus Verilog 12.0). `storm` and `thread` pass; `teeth` (a controller that does not wait for the apply) fails, as it must. Class: RTL-SIM. |
| `step_logs/v2_*.json[.gz]` | The step logs themselves (`wpms_ctl step log 1`), replayable with `cosim_gui_replay.py`. |
| `wpms_gui_standin.png` | The panel connected to the stand-ins (Xvfb), after a scripted storm on blocks 0–3. The transaction times shown are the stand-in's, not JTAG's. |
