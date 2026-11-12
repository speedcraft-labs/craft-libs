On Agentbox, this 20-pair experiment supports detecting a 5% change at the stated approximate 80% power for exposure, export. The specified A/A precision gate passes 5/7 current app/tier rows; failed gates are retained. Control wait is 0% of every in-app interval by construction. The retired confirmation-import cohort is reported separately and is never pooled with folder-drop imports.

HANDOFF 313b — final fixed cohorts. App times run from UI-thread acceptance through confirmation that GPU work for the first qualifying content frame is complete. A callback attaches to the actual egui frame encoder without forking eframe. Its timestamp is an upper bound affected by enabled poll-worker scheduling; it is not scanout or swapchain-present return. Pending-work snapshots describe the qualifying frame when assembled, before that callback. Startup begins at native entry and ends with an active full-quality photo frame (or the explicitly empty grid); quit is external process exit.

Each current A/A cohort has 20 independent-build primary pairs, interleaved AB/BA, with two warmups. Typical50 has six measured repetitions/action and four measured exposure steps/repetition. Import1,259 has two measured repetitions and import-only scope. Each current real comparison has ten contiguous primary pairs plus ten separately acquired upstream sessions. Bootstrap resamples whole paired sessions, stratified by fixed order; 4,000 resamples, seed313. Cold means first use within a session, without flushing OS/shader caches.

| Warm action | A/B ratio [95% CI] | Half-width | MDE¹ | Gate |
|---|---:|---:|---:|---|
| import | 0.9989 [0.9001, 1.0603] | 8.02% | 12.42% | PASS |
| preview | 1.0067 [0.8535, 1.1039] | 12.43% | 20.18% | FAIL |
| exposure | 1.0214 [0.9904, 1.0554] | 3.18% | 4.64% | PASS |
| switch | 1.0142 [0.9049, 1.0911] | 9.18% | 14.31% | FAIL |
| export | 1.0010 [0.9761, 1.0282] | 2.60% | 3.79% | PASS |
| startup | 1.0041 [0.8742, 1.0192] | 7.22% | 11.59% | PASS |
| quit (external) | 0.9970 [0.8676, 1.0285] | 8.07% | 12.93% | FAIL |
| 1259 import (folder drop) | 0.9504 [0.8177, 1.0033] | 9.77% | 15.75% | PASS |

¹ MDE is the approximate detectable change at two-sided alpha=.05 and 80% power on log latency. Comparisons use the larger of their current CI-derived floor and the accepted A/A floor scaled by sqrt(A/A pairs/comparison pairs). A narrow interval alone does not prove 5% power. Power is a repeated-experiment probability: a smaller effect can still be significant in one particular experiment. If the A/A CI excludes1, comparison verdicts are rejected and a numerical CI-width MDE is diagnostic only. Gates require unity in the CI and half-width ≤5%, or ≤10% for import/startup; thresholds are unchanged and gates use unrounded values.

Same-run external and native medians:

| Warm action | External driver upper bound ms³ | App first response ms | App completion ms | Control wait in app clock |
|---|---:|---:|---:|---:|
| import | 126.31 | 22.51 | 29.88 | 0% |
| preview | 121.53 | 3.50 | 99.85 | 0% |
| exposure | 27.54 | 7.22 | 7.22 | 0% |
| switch | 250.69 | 6.48 | 71.19 | 0% |
| export | 370.67 | 346.88 | 346.88 | 0% |
| 1259 import (folder drop) | 18674.55 | 109.09 | 18237.69 | 0% |
| 1259 import (confirmation, legacy) | 1029.76 | 54.90 | 568.84 | 0% |
| startup | 1145.71 | 424.44 | 1109.53 | 0% |

³ External time retains driver send/capture boundaries. Excess over native time includes transport, verification and boundary differences; it is not isolated RPC overhead. After a tagged command the driver makes one native record wait on the socket thread, without dispatching to the UI or repainting. No inspect-poll result enters an app interval. Idle gates require empty task/queue/activity state for one second plus the authoritative native idle check; timeout fails the sample.

There are two explicitly different import protocols. Typical50 and the retired heavy cohort start at confirmation after review preparation. The current1,259 cohort starts at folder-drop acceptance with the existing importDroppedDirectly setting, so directory expansion/preparation is inside its clock. Both end after import/scan complete and every visible thumbnail is shown; exact catalogue names and all virtualized pages are verified outside timing. Empty-grid checks before direct drops prevent prior thumbnails satisfying completion. These durations must not be compared as an app optimization. Switch records both first photo response and full-quality completion; export ends with its completed task/result frame.

Physical10% slowdown: switch 0.9039 [0.8371, 0.9126], **slower**. App-side requested delay 5.838ms was10% of an independent two-pair untreated pilot. Actual median delay 5.911ms was 9.58% of contemporaneous test control latency. Pilot excluded; inference uses ten fresh interleaved pairs. Both binaries contain identical delay code; timestamps were never adjusted arithmetically.

| Physical slowdown | Control ms | Delayed ms | Actual dose | A/B ratio [95% CI] | Verdict | MDE¹ |
|---|---:|---:|---:|---:|---|---:|
| switch | 61.69 | 68.63 | 9.58% | 0.9039 [0.8371, 0.9126] | slower | 20.83% |

| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio [95% CI] | Verdict; MDE¹ |
|---|---:|---:|---:|---:|---|
| import | 220.60 | 28.44 | 29.14 | 8.0084 [7.6049, 8.2922] | outputs differ; descriptive only; 18.01% |
| preview | 36.84 | 98.72 | 102.72 | 0.3976 [0.3367, 0.5255] | outputs differ; descriptive only; 37.47% |
| exposure | 7.87 | 7.38 | 7.68 | 1.0430 [0.9645, 1.1124] | outputs differ; descriptive only; 10.74% |
| switch | 401.95 | 79.43 | 69.36 | 5.4606 [3.9245, 6.6799] | outputs differ; descriptive only; 46.25% |
| export | 339.96 | 332.96 | 330.80 | 1.0390 [1.0011, 1.0929] | outputs differ; descriptive only; 6.47% |
| startup | 926.71 | 1205.49 | 1078.53 | 0.7531 [0.7203, 1.0177] | outputs differ; descriptive only; 28.02% |
| quit (external) | 127.07 | 145.32 | 134.80 | 0.8517 [0.7788, 1.0678] | outputs differ; descriptive only; 25.30% |
| 1259 import (folder drop) | 22244.83 | 17328.41 | 16994.56 | 1.3563 [0.8634, 1.4440] | no measurable change; 44.42% |

² The50-RAW defaults use processV4 at fork point andV7 at main/upstream. Their strict developed-pixel gate FAILED; publishable remains false and all those rows are descriptive only. Their numerical MDEs describe width and do not authorize a speed claim. Aliased acquisition roles were mapped to actual revision names only after timing; no durations changed. Import1,259 checks exact catalogue membership and every non-placeholder thumbnail, without asserting developed-pixel equality. Upstream is a descriptive column acquired separately, with no upstream speed verdict. Every “no measurable change” has a count-adjusted A/A/current-CI MDE; rejected controls stay descriptive.

Retired reviewed-import protocol — all results retained separately:

| Warm action | A/B ratio [95% CI] | Half-width | MDE¹ | Gate |
|---|---:|---:|---:|---|
| 1259 import (confirmation, legacy) | 0.9852 [0.8908, 1.1158] | 11.42% | 17.46% | FAIL |

| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio [95% CI] | Verdict; MDE¹ |
|---|---:|---:|---:|---:|---|
| 1259 import (confirmation, legacy) | 1944.59 | 509.58 | 526.74 | 3.7829 [3.5681, 3.7829] | insufficient paired sessions; uncalibrated |

The legacy real comparison has only five complete primary pairs and five upstream sessions, not the required ten. All fifteen complete sessions and all incomplete attempts remain archived. Its insufficient-session rows support no speed verdict. Repeated primary-pair840s budget expiries led to retiring that workflow at an acquisition boundary, without stopping a running process. A completed fork-point session lasted511.67s and included36,872 inspect calls,27,555 widget reads and181 screenshots. Those untimed lifecycle intervals include app waiting and transport, not an isolated cost decomposition. The fresh direct cohort starts from zero and is not pooled with any legacy observation.

Matrix revisions were frozen at experiment start. Fork main in these tables is d97557e0 and the upstream descriptive column is c2e9c456. During collection, origin/main advanced to59cc810d through a later upstream sync; those later changes require a fresh calibrated comparison. Both production PRs remain cleanly mergeable, and the measured pins have not moved.

Pinned app revisions: fork point fc97c728644d399843d8201f83d25ccf81b89669; fork main d97557e02188f6466c448773d98127222e702daf; upstream c2e9c456c9bfdcd4d56d8b88b8a5b546b69a3223. Common recorder patch SHA25644fe9373aab994e3db26f2e3f95683bcc827fe84e3717709036426430bfbc8c9 applies forward on all three pristine sources. Both recorder files are byte-identical across builds. A/A executables are separate clean builds with identical allocated sections except the build-id. A patch/provenance mismatch fails; update the single adapter and rebuild every side before comparing. Timing driver hashes: {"direct_import": "191b35b1fbff2ce9db087093ccd9b8434f32df612c47abf4c3ef3802d9c185cd", "typical": "0e5419347a4661c3cf465c8c40f2c5a25ee15b13726df8696081274851c961e3"}.

Each primary pair acquired bench.lock then exclusive gpu.lock then scripts/bench-run on reserved CPUs22–27, with an840s hard work lease and cleanup inside15minutes. Binaries were built beforehand and copied outside targets. GPU graphics1350MHz/memory7000MHz mode1 checked before actions; foreign processes, wrong clocks, idle timeouts or resource failures reject samples. Heavy-tier acquisition defers when benchmark waiters exist. Resource forecasts became advisory; a fixed30s allowance admits a new side and the unchanged hard lease is authoritative. No successful complete pair was trimmed. Superseded12-repeat runs, forecasts and incomplete attempts remain diagnostic; final-incomplete-attempt-index.json lists the retained resource failures. No foreign process was stopped.

Residual typical A/A variation: preview session medians80.54–199.18ms; switch54.80–169.14ms. Within-side latency tracks app sharp-preview/render observations at approximately0.999 correlation despite matching photo, geometry, exposure sequence and cache paths, with empty completion pending lists. This places substantial variation inside app work rather than timed control polling, but does not isolate its cause. Warm MDE floors are20.18% and14.31%. Whole-session scheduling diagnostics include untimed work and supply context, not a causal partition.

Legacy confirmation1,259 A/A failed:11.42% half-width,17.46% MDE. Session completion medians range517.55–1137.15ms onA and522.39–911.80ms onB, with30–32 completion frames and empty pending lists. First-response-to-completion gap is about516ms. Source allows four prepared batches to commit per host frame; six available CPUs give12files/batch, so1259files require at least27commitframes. This is consistent with a frame-paced app pipeline. Per-frame timestamps were not recorded, so varying frame stalls remain unresolved. See aa-import-1259-residual-variation.json; this evidence concerns the legacy boundary only.

The fresh direct1,259 A/A passes its10% half-width gate at9.77%, with estimated MDE15.75%. Native completion medians are15.89/18.24s onA/B, while first-photo medians are0.103/0.109s. Session completion medians span15.35–79.41s onA and15.44–72.83s onB, with478–1265/479–1340 frames; all first-photo snapshots still show import work and all completion snapshots are empty. The spread lies after the first photo while the app continues expansion/probing/preparation and frame-paced commits. Source caps commits at4prepared batches per host frame. These observations locate the stage but do not causally partition CPU, disk, GPU, frame pacing or callback scheduling. All20pairs were retained with zero incomplete acquisitions. See aa-import-1259-direct-residual-variation.json, action-diagnostics.json and clock-isolation-proof.json; this broader folder-drop clock is never pooled with legacy confirmation.

Full cold/warm current A/A tables:

Ratio = exp(median log paired-session median(point)/median(main)); >1 favors main. Displayed medians/p95 pool all samples. Times in ms. Order-stratified paired-session bootstrap (ordinary CI also retained in JSON); cold = first use in a session, warm = post-warm-up. OS/shader caches are not flushed.
MDE: A/A-derived approximate two-sided 5% significance, 80% power detectable change on log scale. Uncalibrated comparisons cannot say "no measurable change". An A/A interval excluding 1 rejects comparison verdicts; its width alone is not valid sensitivity.
Action/startup times use in-app GPU completion; quit is explicitly external process exit. Driver/capture medians are secondary in timing_comparison JSON.

Payload: import-1259

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 26082.54/66502.29 | 22290.95/79530.35 | 1.069 (0.984–1.149) | 7.70 | 11.69 | — | PASS |
| import / warm | 15890.49/35036.97 | 18237.69/45221.95 | 0.950 (0.818–1.003) | 9.77 | 15.75 | — | PASS |

Payload: typical-50

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 210.98/296.19 | 206.14/397.72 | 0.934 (0.816–1.050) | 12.52 | 19.73 | — | FAIL |
| import / warm | 29.51/48.81 | 29.88/56.15 | 0.999 (0.900–1.060) | 8.02 | 12.42 | — | PASS |
| preview / cold | 1857.94/3151.14 | 1779.05/3223.90 | 1.001 (0.873–1.126) | 12.64 | 19.95 | — | FAIL |
| preview / warm | 102.46/166.93 | 99.85/180.62 | 1.007 (0.854–1.104) | 12.43 | 20.18 | — | FAIL |
| exposure / cold | 11.12/17.97 | 11.30/26.01 | 0.921 (0.834–1.090) | 13.90 | 21.09 | — | FAIL |
| exposure / warm | 7.63/13.84 | 7.22/14.69 | 1.021 (0.990–1.055) | 3.18 | 4.64 | — | PASS |
| switch / cold | 655.75/1082.06 | 576.04/1218.81 | 1.020 (0.906–1.142) | 11.57 | 17.99 | — | FAIL |
| switch / warm | 69.94/172.80 | 71.19/170.60 | 1.014 (0.905–1.091) | 9.18 | 14.31 | — | FAIL |
| export / cold | 351.90/609.33 | 349.80/614.41 | 1.028 (0.949–1.073) | 6.01 | 9.14 | — | FAIL |
| export / warm | 346.82/562.06 | 346.88/548.67 | 1.001 (0.976–1.028) | 2.60 | 3.79 | — | PASS |
| startup / cold | 1086.98/2247.06 | 1112.01/2095.84 | 1.022 (0.929–1.095) | 8.11 | 12.45 | — | PASS |
| startup / warm | 1065.14/2167.56 | 1109.53/2262.70 | 1.004 (0.874–1.019) | 7.22 | 11.59 | — | PASS |
| quit / cold | 230.27/501.53 | 263.67/410.78 | 0.977 (0.849–1.079) | 11.78 | 18.70 | — | FAIL |
| quit / warm | 135.14/246.09 | 140.40/273.13 | 0.997 (0.868–1.029) | 8.07 | 12.93 | — | FAIL |


Full cold/warm current real tables:

Ratio = exp(median log paired-session median(point)/median(main)); >1 favors main. Displayed medians/p95 pool all samples. Times in ms. Order-stratified paired-session bootstrap (ordinary CI also retained in JSON); cold = first use in a session, warm = post-warm-up. OS/shader caches are not flushed.
MDE: A/A-derived approximate two-sided 5% significance, 80% power detectable change on log scale. Uncalibrated comparisons cannot say "no measurable change". An A/A interval excluding 1 rejects comparison verdicts; its width alone is not valid sensitivity.
Action/startup times use in-app GPU completion; quit is explicitly external process exit. Driver/capture medians are secondary in timing_comparison JSON.

Payload: import-1259

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 22110.67/35306.59 | 22337.15/29860.19 | 1.008 (0.970–1.150) | 8.91 | 16.93 | 22117.71/28200.17 | no measurable change |
| import / warm | 22244.83/34620.23 | 17328.41/46217.38 | 1.356 (0.863–1.444) | 21.40 | 44.42 | 16994.56/29231.33 | no measurable change |

Payload: typical-50

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 226.66/309.19 | 204.11/343.19 | 1.047 (0.981–1.197) | 10.32 | 29.01 | 218.24/288.95 | outputs differ; descriptive only |
| import / warm | 220.60/319.37 | 28.44/44.98 | 8.008 (7.605–8.292) | 4.29 | 18.01 | 29.14/51.67 | outputs differ; descriptive only |
| preview / cold | 1522.18/2127.51 | 1761.76/3653.35 | 0.847 (0.702–0.867) | 9.73 | 29.34 | 1751.21/2582.29 | outputs differ; descriptive only |
| preview / warm | 36.84/75.00 | 98.72/141.80 | 0.398 (0.337–0.526) | 23.75 | 37.47 | 102.72/132.60 | outputs differ; descriptive only |
| exposure / cold | 7.72/13.06 | 11.80/17.28 | 0.747 (0.603–0.844) | 16.12 | 31.08 | 12.01/17.04 | outputs differ; descriptive only |
| exposure / warm | 7.87/14.28 | 7.38/14.70 | 1.043 (0.964–1.112) | 7.09 | 10.74 | 7.68/13.61 | outputs differ; descriptive only |
| switch / cold | 538.77/893.26 | 641.05/1298.19 | 0.838 (0.694–0.999) | 18.14 | 29.64 | 624.74/1049.64 | outputs differ; descriptive only |
| switch / warm | 401.95/757.21 | 79.43/151.18 | 5.461 (3.924–6.680) | 25.23 | 46.25 | 69.36/188.48 | outputs differ; descriptive only |
| export / cold | 342.87/395.08 | 342.97/418.18 | 1.004 (0.982–1.074) | 4.60 | 13.16 | 330.55/534.88 | outputs differ; descriptive only |
| export / warm | 339.96/398.96 | 332.96/480.29 | 1.039 (1.001–1.093) | 4.42 | 6.47 | 330.80/486.91 | outputs differ; descriptive only |
| startup / cold | 1010.76/1456.71 | 1193.63/1536.19 | 0.782 (0.766–1.096) | 21.13 | 29.22 | 1121.73/2278.55 | outputs differ; descriptive only |
| startup / warm | 926.71/1646.50 | 1205.49/1794.02 | 0.753 (0.720–1.018) | 19.74 | 28.02 | 1078.53/1838.98 | outputs differ; descriptive only |
| quit / cold | 223.67/312.64 | 242.14/357.56 | 0.852 (0.722–1.031) | 18.15 | 29.02 | 270.51/483.16 | outputs differ; descriptive only |
| quit / warm | 127.07/278.53 | 145.32/223.26 | 0.852 (0.779–1.068) | 16.97 | 25.30 | 134.80/224.04 | outputs differ; descriptive only |


Full cold/warm retired confirmation A/A:

Ratio = exp(median log paired-session median(point)/median(main)); >1 favors main. Displayed medians/p95 pool all samples. Times in ms. Order-stratified paired-session bootstrap (ordinary CI also retained in JSON); cold = first use in a session, warm = post-warm-up. OS/shader caches are not flushed.
MDE: A/A-derived approximate two-sided 5% significance, 80% power detectable change on log scale. Uncalibrated comparisons cannot say "no measurable change". An A/A interval excluding 1 rejects comparison verdicts; its width alone is not valid sensitivity.
Action/startup times use in-app GPU completion; quit is explicitly external process exit. Driver/capture medians are secondary in timing_comparison JSON.

Payload: import-1259

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 2165.10/2892.96 | 2259.26/3138.69 | 0.934 (0.850–1.032) | 9.73 | 14.86 | — | PASS |
| import / warm | 564.49/1039.62 | 568.84/975.01 | 0.985 (0.891–1.116) | 11.42 | 17.46 | — | FAIL |


Full cold/warm retired partial real:

Ratio = exp(median log paired-session median(point)/median(main)); >1 favors main. Displayed medians/p95 pool all samples. Times in ms. Order-stratified paired-session bootstrap (ordinary CI also retained in JSON); cold = first use in a session, warm = post-warm-up. OS/shader caches are not flushed.
MDE: A/A-derived approximate two-sided 5% significance, 80% power detectable change on log scale. Uncalibrated comparisons cannot say "no measurable change". An A/A interval excluding 1 rejects comparison verdicts; its width alone is not valid sensitivity.
Action/startup times use in-app GPU completion; quit is explicitly external process exit. Driver/capture medians are secondary in timing_comparison JSON.

Payload: import-1259

| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |
|---|---:|---:|---:|---:|---:|---:|---|
| import / cold | 2149.50/2467.11 | 2162.66/2239.38 | 1.029 (0.836–1.737) | 43.77 | uncalibrated | 2094.90/2305.81 | insufficient paired sessions |
| import / warm | 1944.59/2323.63 | 509.58/550.94 | 3.783 (3.568–3.783) | 2.84 | uncalibrated | 526.74/719.00 | insufficient paired sessions |


Candidate craft-journeys:3Rust/55Python checks pass, including report-count sensitivity and direct-import boundary tests. Full craft-libs workspace baseline3835passed,0failed,127ignored. Three recorder CPU tests plus socket no-dispatch/no-repaint regression pass; app/UI strict clippy passes. Local app workspace6365passed with four denoise GPU failures reproduced on matching-feature clean main (65pass,4fail,11ignored). Targeted UI32/32 passes; an earlier full UI executable exited SIGSEGV after32passes, not reproduced by targeted clean-main UI. Unchanged full-libs shader clippy errors are separately recorded. Final source validation and PR states are appended after integration.

Immutable reports/provenance: ALL-PHASES.json, EVIDENCE-INDEX.json, final-analysis-identity-proof.json, build-provenance-r3.json, patch-pristine-proof-r3.json, recorder-source-parity.json, aa-code-sections.json and acquisition logs. Passing image artifacts become hashes after final review; failing/disputed images are retained. Final NAS path and PR heads/checks/reviews are appended by the operator.
