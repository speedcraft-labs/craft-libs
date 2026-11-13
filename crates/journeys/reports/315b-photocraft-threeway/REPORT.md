# PhotoCraft brush three-build report

Ticket 315b compares the fork merge-base (A), fork tip (B), and upstream tip (C). A/B measures our changes since the fork point; A/C measures upstream changes since then.

## Validity verdict

The earlier point-frame comparison is withdrawn. On upstream, the first reflected frame could show the cursor before paint pixels arrived, so its 8–9 ms value did not consistently measure the stroke. The corrected recorder captures the stroke region at that frame and again after the release-frame GPU fence.

| Brush action | Dabs | Changed pixels at first frame, A/B/C | Added by release fence, A/B/C |
|---|---:|---:|---:|
| 30 px | 763 | 0 / 5,207 / 0 | 5,207 / 0 / 5,207 |
| 500 px soft | 46 | 0 / 0 / 0 | 79,895 / 79,895 / 79,895 |
| Canvas-width soft | 6 | 78,573 / 78,573 / 78,573 | 72,868 / 72,868 / 72,868 |

All builds had equal dab counts and matching settled RGB crop hashes for each action. The captured pixels at the release fence match the settled result. This confirms asynchronous stamping: the upstream frame can precede the stroke, especially for 30 px and 500 px actions. One proof run per build establishes recorder validity; these values are not matrix statistics.

## Three-build matrix

At 09:08 UTC on 2026-11-13, typical-document A/A had 18 of 20 valid pairs; pair 18 is queued for the shared bench/GPU locks. No three-build conclusion or cause attribution is reported until the A/A gate and paired comparisons complete.

## Pins and evidence

- A merge-base: `74330157cb601573ae4523a95bb9132822fc3918`
- B fork tip: `629049f550e5cad1c483fe800a66047cd02bf150`
- C upstream tip: `e052eabf4be74612725400955d184f85d208c0f0`
- Recorder source SHA-256: `0c5c15480a8ea911b24707a7001a743412d548b3f7fa93f503364ef7aec59653`
- Harness SHA-256: `00d2ccf8a292aa54e4c1a697b9cf6317f29e595ce2e057ffc56deab0311aed2a`
- Driver SHA-256: `ff8429f223ff214f2217986bd5ff9c94872f60dccd8cd4ca228800e55358f47c`
- Pixel-proof report: `/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/reports/proof-typical/pair-00-try-08/report.json`
- NAS checkpoints are stored under `wormhole:/mnt/bulk/backups/speedcraft-labs/tickets/315b-photocraft-threeway/`.
