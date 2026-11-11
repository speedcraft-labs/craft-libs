HANDOFF 313b — all 10 real 50-RAW pairs plus 10 separately acquired upstream runs are COMPLETE. These are default-workload **descriptive** timings: fork point imports process V4, main/upstream V7; the strict developed-pixel gate stays FAILED, publishable=false. There is no equivalent-output speed verdict. Native timing source/recorder and every raw duration stay unchanged; exact raw aliases/provenance retained.

| Warm action | Fork point ms | Fork main ms | Upstream ms | Point/main ratio (95% CI) | MDE width diagnostic | Scope |
|---|---:|---:|---:|---:|---:|---|
| import | 220.60 | 28.44 | 29.14 | 8.0084 (7.6049–8.2922) | 18.01% | outputs differ; descriptive only |
| preview | 36.84 | 98.72 | 102.72 | 0.3976 (0.3367–0.5255) | 37.47% | outputs differ; descriptive only |
| exposure | 7.87 | 7.38 | 7.68 | 1.0430 (0.9645–1.1124) | 10.74% | outputs differ; descriptive only |
| switch | 401.95 | 79.43 | 69.36 | 5.4606 (3.9245–6.6799) | 46.25% | outputs differ; descriptive only |
| export | 339.96 | 332.96 | 330.80 | 1.0390 (1.0011–1.0929) | 6.47% | outputs differ; descriptive only |
| startup | 926.71 | 1205.49 | 1078.53 | 0.7531 (0.7203–1.0177) | 28.02% | outputs differ; descriptive only |
| quit (external) | 127.07 | 145.32 | 134.80 | 0.8517 (0.7788–1.0678) | 25.30% | outputs differ; descriptive only |

Raw derived report `/jobs/work/speedcraft-labs/keep/313b-inapp-timing/real-50-descriptive-9-derived-report.json` links immutable raw single-side acquisitions; all 30 retain strict native photo-change/JPEG checks. Actual point/main stay contiguous AB/BA inside one ≤840 s lease; upstream has a separate acquisition. MDE width diagnostics are max(current CI estimate, A/A floor adjusted 20→10 pairs); they do not validate unequal-output speed claims. Cold/warm tables and guards remain in JSON. The 1,259-RAW A/A continues (6/20 complete); post-recovery.py then runs its strict 10-pair real comparison+upstream. After ALL: apply staged report-only corrections/metadata, required cargo tests and both AA identity proofs, final tables/plots, passing-image hashes, one NAS snapshot and merge queues. Source clock remains0e541934…, app62b1627c; post-clock validator88e6735f.
