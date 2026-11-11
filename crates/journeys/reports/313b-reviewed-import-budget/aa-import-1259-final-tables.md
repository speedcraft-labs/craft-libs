HANDOFF 313b — fixed 20-pair A/A complete. Ratios are A/B; unity must be inside the 95% CI, with unrounded half-width≤5% (import/startup≤10%). Thresholds are unchanged; failed gates retained. MDE is a separate approximate 80%-power estimate, not the half-width. Quit is external process exit and does not validate app-clock precision.
| Warm action | A/B ratio | 95% CI | Half-width | MDE | Gate |
|---|---:|---:|---:|---:|---|
| import | 0.9852 | 0.8908–1.1158 | 11.42% | 17.46% | FAIL |

| Warm action (B) | Driver upper bound ms | App first-response ms | App completion ms | Control wait in app clock |
|---|---:|---:|---:|---:|
| import | 1029.76 | 54.90 | 568.84 | 0% |

Raw cumulative report `/jobs/work/speedcraft-labs/keep/313b-inapp-timing/aa-import-1259-fixed-19-primary-attempt0/report.json`. First/complete app stamps are UI acceptance→same-frame GPU work confirmed complete, prior to any socket reply; all record control_wait_ns=0. External medians are retained upper bounds, not an isolated RPC-overhead estimate. Same additive patch and byte-identical recorder source on both clean builds;31 allocated ELF sections match except build-id. Cold/warm whole-session bootstrap and all per-action evidence retained. Earlier 12-repeat and incomplete acquisitions are diagnostic only, never pooled. Next phases remain predeclared in operators/post-recovery.py.
