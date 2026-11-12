HANDOFF 313b — fixed 20-pair A/A complete. Ratios are A/B; unity must be inside the 95% CI, with unrounded half-width≤5% (import/startup≤10%). Thresholds are unchanged; failed gates retained. MDE is a separate approximate 80%-power estimate, not the half-width. Quit is external process exit and does not validate app-clock precision.

| Warm action | A/B ratio | 95% CI | Half-width | MDE | Gate |
|---|---:|---:|---:|---:|---|
| import | 0.9504 | 0.8177–1.0033 | 9.77% | 15.75% | PASS |

| Warm action (B) | Driver upper bound ms | App first-response ms | App completion ms | Control wait in app clock |
|---|---:|---:|---:|---:|
| import | 18674.55 | 109.09 | 18237.69 | 0% |

Raw cumulative report `/jobs/work/speedcraft-labs/keep/313b-inapp-timing/aa-import-1259-direct-19-primary-attempt0/report.json`. First/complete app stamps are UI acceptance→same-frame GPU work confirmed complete, prior to any socket reply; all record control_wait_ns=0. External medians are retained upper bounds, not an isolated RPC-overhead estimate. Same additive patch and byte-identical recorder source on both clean builds;31 allocated ELF sections match except build-id. Cold/warm whole-session bootstrap and all per-action evidence retained. Earlier 12-repeat and incomplete acquisitions are diagnostic only, never pooled. For active continuation use CURRENT-STATE.json and CONTINUATION.md; leave the existing coordinator running.

Timing driver SHA256: `191b35b1fbff2ce9db087093ccd9b8434f32df612c47abf4c3ef3802d9c185cd`. Import boundary: folder-drop acceptance through usable grid, including expansion/preparation; never pooled with retired confirmation timings.
