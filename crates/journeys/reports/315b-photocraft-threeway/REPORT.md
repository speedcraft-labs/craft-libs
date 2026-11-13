# PhotoCraft brush three-build report

Ticket 315b compares the fork merge-base (A), fork tip (B), and upstream tip (C). A/B isolates changes made in our fork since the split; A/C measures upstream changes since that point.

## Validity verdict

The earlier fork-vs-upstream point-frame comparison is **withdrawn**. Upstream's first reflected frame sometimes showed the cursor before paint pixels arrived, so the old 8–9 ms reading did not consistently measure a completed stroke. The corrected recorder captures the stroke region at that frame and again after the release-frame GPU fence. Pixel captures show stamping can be deferred beyond the recorded point frame.

The table gives changed crop pixels from the same pre-stroke image at the first reflected frame and after the release-frame GPU fence. Dab counts match across A/B/C for each document/action; release-fence crops have matching RGB hashes across builds and match the settled image.

| Document | Action | Dabs per build | Point-frame changed pixels, A/B/C | Release-frame changed pixels, A/B/C |
|---|---|---:|---:|---:|
| 12 MP typical | 30 px | 763 | 0 / 5,207 / 0 | 5,207 / 5,207 / 5,207 |
| 12 MP typical | 500 px soft | 46 | 0 / 0 / 0 | 79,895 / 79,895 / 79,895 |
| 12 MP typical | Canvas-width soft | 6 | 78,573 / 78,573 / 78,573 | 79,992 / 79,992 / 79,992 |
| 24 MP heavy | 30 px | 1,220 | 0 / 0 / 0 | 3,489 / 3,489 / 3,489 |
| 24 MP heavy | 500 px soft | 74 | 0 / 0 / 0 | 50,681 / 50,681 / 50,681 |
| 24 MP heavy | Canvas-width soft | 8 | 97,022 / 97,022 / 97,022 | 98,803 / 98,803 / 98,803 |

On the heavy proof, immediate-release and settled crop hashes match for all builds/actions (MAE 0). The captured 97,022 canvas-width pixels are present in all three builds. Pixel proof is a validity check, not a latency sample. Earlier point-frame values must not be compared as stroke latency.

## Three-build matrix

The matrix has 10 valid interleaved A/B/C pairs per document tier. A/A uses 20 fork-tip pairs per tier; all six stroke-total gates pass in both tiers. The table reports completed stroke totals from first accepted input through the release-frame GPU fence. Ratios are paired bootstrap medians with 95% intervals: a/b is merge-base divided by fork tip; a/c is merge-base divided by upstream tip. A ratio below 1 means the right-hand build took longer.


### Typical document

Ratio a/b compares merge-base with fork tip; a/c compares merge-base with upstream tip. Both are left-side latency divided by right-side latency, so a ratio above 1 means the right-side build was faster. Ratios use per-pair session medians and 10,000 bootstrap resamples. Stroke total runs from first accepted input through the release-frame GPU fence. Point-frame values are excluded from this stroke table because RGB proof showed upstream can present the cursor before the stroke pixels.

| Tier | Brush action | State | A median/p95 ms | B median/p95 ms | C median/p95 ms | a/b (95% CI) | a/c (95% CI) | A/A gate |
|---|---|---|---:|---:|---:|---:|---:|---|
| typical | brush-30px | cold | 111.20/114.47 | 110.04/116.07 | 108.46/126.38 | 0.986 (0.953–1.014) | 1.018 (0.931–1.049) | PASS |
| typical | brush-30px | warm | 109.12/119.21 | 109.23/116.23 | 109.99/119.97 | 1.013 (0.986–1.030) | 0.999 (0.985–1.041) | PASS |
| typical | brush-500px-soft | cold | 147.55/164.23 | 162.38/181.49 | 150.01/200.52 | 0.924 (0.877–0.984) | 1.019 (0.902–1.048) | PASS |
| typical | brush-500px-soft | warm | 153.41/165.36 | 151.07/164.90 | 149.68/233.06 | 0.974 (0.954–1.036) | 1.021 (0.976–1.061) | PASS |
| typical | brush-canvas-width-soft | cold | 1432.22/1581.72 | 1483.37/1679.66 | 1498.92/1892.30 | 0.971 (0.871–1.018) | 0.975 (0.875–1.015) | PASS |
| typical | brush-canvas-width-soft | warm | 1332.58/1484.00 | 1385.09/1549.34 | 1387.91/1556.31 | 0.971 (0.877–1.025) | 0.968 (0.909–1.002) | PASS |

A/A gate uses 20 identical fork-tip pairs per tier. PASS requires the 95% interval to include 1.00 and relative half-width at most 5%. Contrasts failing that row gate remain descriptive.


### Heavy document

Ratio a/b compares merge-base with fork tip; a/c compares merge-base with upstream tip. Both are left-side latency divided by right-side latency, so a ratio above 1 means the right-side build was faster. Ratios use per-pair session medians and 10,000 bootstrap resamples. Stroke total runs from first accepted input through the release-frame GPU fence. Point-frame values are excluded from this stroke table because RGB proof showed upstream can present the cursor before the stroke pixels.

| Tier | Brush action | State | A median/p95 ms | B median/p95 ms | C median/p95 ms | a/b (95% CI) | a/c (95% CI) | A/A gate |
|---|---|---|---:|---:|---:|---:|---:|---|
| heavy | brush-30px | cold | 120.00/123.18 | 117.61/124.75 | 116.78/120.34 | 0.996 (0.979–1.053) | 1.021 (0.991–1.060) | PASS |
| heavy | brush-30px | warm | 117.31/124.35 | 113.73/121.35 | 113.37/120.88 | 1.011 (0.993–1.034) | 1.013 (1.001–1.050) | PASS |
| heavy | brush-500px-soft | cold | 211.86/232.09 | 207.67/222.50 | 208.12/224.45 | 1.003 (0.972–1.062) | 1.027 (0.980–1.080) | PASS |
| heavy | brush-500px-soft | warm | 203.61/222.54 | 202.24/219.84 | 201.82/210.34 | 1.001 (0.962–1.034) | 1.005 (0.970–1.050) | PASS |
| heavy | brush-canvas-width-soft | cold | 2676.08/2811.43 | 2694.61/2841.96 | 2696.55/2823.02 | 1.001 (0.961–1.011) | 0.980 (0.970–1.004) | PASS |
| heavy | brush-canvas-width-soft | warm | 2506.06/2686.65 | 2520.05/2587.49 | 2528.83/2679.80 | 0.997 (0.990–1.026) | 0.992 (0.985–1.009) | PASS |

A/A gate uses 20 identical fork-tip pairs per tier. PASS requires the 95% interval to include 1.00 and relative half-width at most 5%. Contrasts failing that row gate remain descriptive.


## Cause

The only resolved fork-side difference is typical 12 MP, 500 px soft, cold: A 147.55 ms vs B 162.38 ms; a/b 0.924 (95% CI 0.877–0.984), so fork tip is about 8–10% slower on this row. Other A/B rows do not resolve a difference. Upstream C is not broadly faster in the corrected matrix: most a/c intervals include 1; the only interval narrowly above 1 is heavy 30 px warm (1.013, 1.001–1.050), about a 1% change and one of 12 comparisons.

The minimum own-side check removes fork commit `64d38ba373af6927665e78649fd1880af162a657` (`perf(compose): skip idle layer effect allocations`, `crates/compose/src/effects/composite.rs`) from B. The first attempt (pair 00 try 03) is retained but excluded because a foreign EffectCraft process appeared during A's GPU session (PID 2741580). A clean leave-out pair (pair 00 try 04) passed every gate: for the flagged typical 500 px soft cold stroke, A measured 147.96 ms, the B build with this commit reverted measured 147.31 ms, and C measured 148.88 ms (46 dabs each). The leave-out result is within 0.5% of A, below the 3.18% A/A interval half-width for this row, while the original 10-pair A/B result showed B about 8–10% slower. This minimum one-pair cause screen points to `64d38ba` as the cause of the only resolved fork-side regression; it is not a new 10-pair estimate of the leave-out build. The raw valid pair is `reports/own-bisect-64d/pair-00-try-04/report.json`.

Upstream PR #11152 (`a2067ab4566d1c2901b661b5e31de99b64029beb`) adds out-of-canvas dab clipping and a dab-area budget. A single heavy control pair was exploratory; it does not establish that PR as the cause of a current three-build difference. Its change arrives by syncing, but the corrected matrix does not show a broad upstream brush-latency win.

## Pins and evidence

- A merge-base: `74330157cb601573ae4523a95bb9132822fc3918`
- B fork tip: `629049f550e5cad1c483fe800a66047cd02bf150`
- C upstream tip: `e052eabf4be74612725400955d184f85d208c0f0`
- Recorder SHA-256: `0c5c15480a8ea911b24707a7001a743412d548b3f7fa93f503364ef7aec59653`
- Harness SHA-256: `00d2ccf8a292aa54e4c1a697b9cf6317f29e595ce2e057ffc56deab0311aed2a`
- Driver SHA-256: `ff8429f223ff214f2217986bd5ff9c94872f60dccd8cd4ca228800e55358f47c`
- Typical pixel proof: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/proof-typical/pair-00-try-08/report.json`
- Heavy pixel proof: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/proof-heavy/pair-00-try-03/report.json`
- Typical matrix summary: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/threeway-typical-summary-current.json`
- Heavy matrix summary: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/threeway-heavy-summary-current.json`
- NAS snapshots: `wormhole:/mnt/bulk/backups/speedcraft-labs/tickets/315b-photocraft-threeway/`
