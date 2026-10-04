# C2 full8 discrepancies / 差異・検証範囲

No discrepancy was found in required items 1–5, the 28 compared bundles, or the 3 compared PCM banks.

Coverage difference: the template lists 4/4 PCM comparisons for its reset-based RTL-SIM capture. This hardware acquisition was armed and triggered after the origin had already run for many samples, so the analyzer uses the complete full8 take as the model starting point and compares 3/3 post-take banks. The first captured bank is unverified against the model, not a detected mismatch. See observation.md and observed.json.
