HANDOFF 313b — the predeclared physical slowdown test PASSES: the native-clock switch row is **slower**. Ten independent interleaved pairs; the two-pair dose pilot is excluded. No threshold, interval, or timing value was changed.

| Warm switch | Untreated median ms | Delayed median ms | A/B ratio (95% CI) | Half-width | Conservative MDE | Verdict |
|---|---:|---:|---:|---:|---:|---|
| UI acceptance → full-quality frame GPU completion | 61.687 | 68.634 | 0.9039 (0.8371–0.9126) | 4.18% | 20.83% | **slower** |

Requested physical sleep was 5.837823 ms, 10% of the independent pilot median. Actual median sleep was 5.911450 ms, **9.58%** of the contemporaneous untreated median. The A/B estimate is a median of paired session ratios, so it need not equal the ratio of the displayed pooled medians. The numerical MDE is the conservative A/A floor adjusted from 20 to 10 pairs (larger than this test's own CI-derived 6.37%); it is an approximate power estimate, not a condition forbidding a smaller effect from being significant.

All 80 main-side switch records, including warmups, contain requested and actual **app-side** sleep inside accepted→completion time. No other action/side has injected delay. The legacy external-driver delay is zero throughout. Both binaries contain identical code; no arithmetic duration adjustment is substituted. Complete guarded report `/jobs/work/speedcraft-labs/keep/313b-inapp-timing/switch-delay-10pct-9-primary-attempt0/report.json`; `physical-slowdown-proof.json` contains the dose and conservative report-only analysis. Production app62b1627c/libs65838523 remain frozen and clean. The real50RAW 10-pair point/main comparison plus separately acquired upstream samples is now running, followed by the predeclared1259-import A/A and real cohorts. Final report-only MDE correction/49 tests, final tables, passing-image pruning, one NAS snapshot and merge queues remain.

The complete slowdown proof and table are pushed on craft-libs `wip/313b-inapp-analysis` fba27f5b under `crates/journeys/reports/313b-inapp-analysis`; production source heads stay unchanged.

Negative controls: all six other warm rows (import, preview, exposure, export, startup and external quit) have 95% CIs containing 1. Only the deliberately delayed switch is reported slower in this fixed cohort. These rows are included in physical-slowdown-proof.json.
