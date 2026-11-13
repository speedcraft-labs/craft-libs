# PhotoCraft brush three-build report

Ticket 315b compares the fork merge-base (A), fork tip (B), and upstream tip (C). A/B measures our changes since the fork point; A/C measures upstream changes since then.

## Validity verdict

The earlier point-frame comparison is withdrawn. On upstream, the first reflected frame could show the cursor before paint pixels arrived, so its 8–9 ms value did not consistently measure the stroke. The corrected recorder captures the stroke region at that frame and again after the release-frame GPU fence.

| Brush action | Dabs | Changed pixels at first frame, A/B/C | Added by release fence, A/B/C |
|---|---:|---:|---:|
| 30 px | 763 | 0 / 5,207 / 0 | 5,207 / 0 / 5,207 |
| 500 px soft | 46 | 0 / 0 / 0 | 79,895 / 79,895 / 79,895 |
| Canvas-width soft | 6 | 78,573 / 78,573 / 78,573 | 72,868 / 72,868 / 72,868 |

All builds had equal dab counts and matching settled RGB crop hashes for each action. The captured pixels at the release fence match the settled result. This confirms asynchronous stamping: the upstream frame can precede the stroke, especially for 30 px and 500 px actions. One proof run per build on each document size establishes recorder validity; these values are not matrix statistics.

The 24 MP heavy-document proof (pair 00 try 03) repeats the result: A/B/C dab counts were 1,220 / 74 / 8 for the three actions; point-frame changed-pixel counts were 0 / 0 / 97,022; every release-frame hash matched both the immediate and settled RGB crop, and immediate-to-settled MAE was 0. The point frame therefore omitted pixels for the first two heavy-document strokes as well. The failed try 02 is retained; its canvas-width screenshot capture timed out and it is excluded.

## Three-build matrix

The exact-pin typical matrix has 10 of 10 valid A/B/C pairs. The independent fork-tip A/A gate has 20 pairs per action and phase; all six stroke-total gates pass, with the widest 95% interval half-width at 4.94%. The first three-build files (pairs 00–09, try 01) used different build commits and are excluded.

Table values are completed stroke totals from first accepted input through the release-frame GPU fence. Ratios use per-pair session medians and 10,000 bootstrap resamples: a/b compares merge-base with fork tip; a/c compares merge-base with upstream tip. Point-frame values are excluded because RGB proof showed upstream can present the cursor before stroke pixels.

| Tier | Brush action | State | A median/p95 ms | B median/p95 ms | C median/p95 ms | a/b (95% CI) | a/c (95% CI) | A/A gate |
|---|---|---|---:|---:|---:|---:|---:|---|
| typical | brush-30px | cold | 123.54/126.32 | 123.73/130.86 | 113.11/117.66 | 0.993 (0.971–1.007) | 1.106 (1.071–1.118) | PASS |
| typical | brush-30px | warm | 124.09/128.53 | 124.30/128.24 | 111.31/118.55 | 0.999 (0.989–1.019) | 1.119 (1.084–1.133) | PASS |
| typical | brush-500px-soft | cold | 221.12/230.06 | 220.58/223.05 | 200.03/202.92 | 1.011 (0.995–1.041) | 1.124 (1.104–1.133) | PASS |
| typical | brush-500px-soft | warm | 223.62/231.34 | 219.37/235.21 | 197.65/210.56 | 1.017 (0.999–1.034) | 1.140 (1.105–1.161) | PASS |
| typical | brush-canvas-width-soft | cold | 2022.59/2046.40 | 2020.94/2049.26 | 1782.66/1847.84 | 0.998 (0.982–1.019) | 1.123 (1.109–1.146) | PASS |
| typical | brush-canvas-width-soft | warm | 2114.24/2154.91 | 2107.08/2182.72 | 1748.95/1780.83 | 1.000 (0.989–1.006) | 1.204 (1.193–1.219) | PASS |

A/A gate uses 20 identical fork-tip pairs per tier. PASS requires the 95% interval to include 1.00 and relative half-width at most 5%. Contrasts failing that row gate remain descriptive.

Typical result: fork-tip vs merge-base has no resolved stroke-total difference in these six rows. Upstream tip is faster than merge-base in all six; its paired median stroke total is about 10–20% lower. This attributes the observed improvement to changes since the fork point, but source attribution still needs the minimal #11152 stroke-budget control after the heavy matrix.

The refresh scheduler is running the heavy-document proof, A/A gate, and exact-pin three-build matrix as one pair per lock acquisition. No application changes were made.

## Pins and evidence

- A merge-base: `74330157cb601573ae4523a95bb9132822fc3918`
- B fork tip: `629049f550e5cad1c483fe800a66047cd02bf150`
- C upstream tip: `e052eabf4be74612725400955d184f85d208c0f0`
- Recorder source SHA-256: `0c5c15480a8ea911b24707a7001a743412d548b3f7fa93f503364ef7aec59653`
- Harness SHA-256: `00d2ccf8a292aa54e4c1a697b9cf6317f29e595ce2e057ffc56deab0311aed2a`
- Driver SHA-256: `ff8429f223ff214f2217986bd5ff9c94872f60dccd8cd4ca228800e55358f47c`
- Typical pixel-proof report: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/proof-typical/pair-00-try-08/report.json`
- Heavy pixel-proof report: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/proof-heavy/pair-00-try-03/report.json`
- NAS checkpoints are stored under `wormhole:/mnt/bulk/backups/speedcraft-labs/tickets/315b-photocraft-threeway/`.
