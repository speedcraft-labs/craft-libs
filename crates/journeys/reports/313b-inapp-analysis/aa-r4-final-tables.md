Exposure and export now support an approximate5% effect at80% power on Agentbox in this fixed experiment (MDE4.64%,3.79%). The A/A precision gates pass4/6 app rows. Preview and switch still miss the5% half-width gate; there is no blanket5% claim.

HANDOFF 313b — fixed20pair A/A complete. Ratios are A/B; unity must be inside the95%CI, with unrounded half-width≤5% (import/startup≤10%). Thresholds are unchanged; failed gates retained. MDE is a separate approximate80%-power estimate, not the half-width. Quit is external process exit and does not validate app-clock precision.
| Warm action | A/B ratio | 95% CI | Half-width | MDE | Gate |
|---|---:|---:|---:|---:|---|
| import | 0.9989 | 0.9001–1.0603 | 8.02% | 12.42% | PASS |
| preview | 1.0067 | 0.8535–1.1039 | 12.43% | 20.18% | FAIL |
| exposure | 1.0214 | 0.9904–1.0554 | 3.18% | 4.64% | PASS |
| switch | 1.0142 | 0.9049–1.0911 | 9.18% | 14.31% | FAIL |
| export | 1.0010 | 0.9761–1.0282 | 2.60% | 3.79% | PASS |
| startup | 1.0041 | 0.8742–1.0192 | 7.22% | 11.59% | PASS |
| quit (external) | 0.9970 | 0.8676–1.0285 | 8.07% | 12.93% | FAIL |

| Warm action (B) | Driver upper bound ms | App first-response ms | App completion ms | Control wait in app clock |
|---|---:|---:|---:|---:|
| import | 126.31 | 22.51 | 29.88 | 0% |
| preview | 121.53 | 3.50 | 99.85 | 0% |
| exposure | 27.54 | 7.22 | 7.22 | 0% |
| switch | 250.69 | 6.48 | 71.19 | 0% |
| export | 370.67 | 346.88 | 346.88 | 0% |

Raw cumulative report `/jobs/work/speedcraft-labs/keep/313b-inapp-timing/aa-inapp-r4-19-primary-attempt0/report.json`. First/complete app stamps are UI acceptance→same-frame GPU work confirmed complete, prior to any socket reply; all record control_wait_ns=0. External medians are retained upper bounds, not an isolated RPC-overhead estimate. Same additive patch and byte-identical recorder source on both clean builds;31 allocated ELF sections match except build-id. Cold/warm whole-session bootstrap and all per-action evidence retained. Earlier12-repeat and incomplete acquisitions are diagnostic only, never pooled. Next phases remain predeclared in operators/post-r4.py.

Residual variation is inside app work: warm session preview medians span80.54–199.18ms and switch54.80–169.14ms. Switch session medians correlate with the app last-render timer at r=.9987/.9991 (A/B); preview correlates with its independent app loupe sharp-frame timer (exact values in aa-r4-action-diagnostics.json). Completion pending-work lists are empty for every preview/exposure/switch observation; GPU path, RAW source/settings, preview-cache hit/miss counts and geometry match. Reserved-CPU steal session medians have median.252%, range.168–4.600%; observed UI/worker runnable-wait shares median9.13%/19.44%. These contextual counters include untimed work, so they do not prove a hardware cause or decompose action time. The remaining preview/switch variance is not timed control polling; its underlying app/render scheduling cause is not isolated further. No app optimization or observation filtering was performed.

A pure report-only MDE count/current-CI correction and startup scope-label fix are drafted at operators/after-all-report-only.patch, tested in an isolated copy (49 Python tests pass). Production libs65838523 stays unchanged until ALL-PHASES.json closes every cohort; apply the patch only afterwards and prove both full AA analyses bit-identical. This avoids silently transferring20-pair calibration precision to10-pair comparisons.
