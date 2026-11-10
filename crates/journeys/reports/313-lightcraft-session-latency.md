# LightCraft session latency — hyper #291 / ticket 313

**Completed scope:** the typical 50-RAW comparison below is final. The coordinator stopped optional heavy-500 stress at 7/30 sessions to release the queue; it supplies no published latency table or speed claim.

The old launch-per-task rows mixed interaction with process startup and shutdown. This additive mode keeps a desktop session alive for import, full-quality preview, exposure dragging, filmstrip selection and JPEG export. Populated-library startup and idle quit are separate rows. Existing journeys and published reports are unchanged.

## Method

Agentbox only: AMD Ryzen 9 5900XT, reserved logical CPUs 22–27, NVIDIA GeForce RTX 2080 Ti / Vulkan, driver 550.163.01, private 1920×1080 X display `:118`, 1600×1000 app window. All binaries were built before acquiring `bench.lock`, then exclusive `gpu.lock`, then `scripts/bench-run`. Each app uses its own Cargo.lock.

Pinned app revisions (frozen from the initial fetched comparison setup, not later moving main tips):

- Fork point: `fc97c728644d399843d8201f83d25ccf81b89669` (merge-base after fetching both remotes).
- Fork main: `09eb4c56accd9dc0e405510d099fee10d6a68f55`.
- Upstream main: `f6b57b0b59f45f3cfae1fb8d26a834e336be5a11`.

Ten sessions per revision for the completed typical tier, in ABC/CBA blocks; two warm-ups and one measured repetition of import/preview/switch/export per session. The exposure gesture has two warm-up moves and 60 measured backpressured moves. Thus each action has 10 measured observations per side, except exposure with 600. Every warm-up and measured sample is retained. This is not a 60 Hz drag.

Action clocks start immediately before sending the control request. Their endpoints are observed visible X11 frames whose complete RGB pixels match a successful native screenshot; failed native captures are retained/retried without resetting the action clock. Without an earlier exact match, native capture completion supplies a labeled upper bound. These instrumented observations include control, ready-state polling and capture overhead; they do not measure OS input delivery or scanout, and do not establish the unobserved first presentation time. Launch and exit never enter an action clock. The lifecycle test rejects both overlaps and fabricated durations.

Import includes visiting every grid page, checking the exact imported filename set, resident textures and non-placeholder photo crops. Wheel-point scrolling clamps at the grid boundary. Preview opens the first photo at 100% after warm-ups; it is a warm preview, not a first-open measurement. Filmstrip selection uses the same engine command as the UI and visits a different photo for the measured switch. JPEG export requests a 2048-pixel long edge at quality 90 and verifies its output against the source/settings render. Startup reopens the populated library to a finished first-photo frame. Quit starts only after background and render work is drained, and ends at a pidfd-observed successful process exit.

Per paired session, the cross-revision gate compares one fixed-state source-render PNG and the JPEG export. Imported thumbnails are checked for presence, texture residency and non-placeholder pixels. Fixed-state PNG parity requires max RGB error ≤1 and identical alpha; cross-revision JPEG parity requires max RGB ≤16 and channel MAE ≤0.5. Own JPEG/source MAE ≤8 allows lossy encoding. New runs use an 8-bit sRGB lossless PNG export at exactly the JPEG geometry. The completed typical report retains its original preview-based reference and documented one-pixel rounding allowance; it passed that original fixed bound. The noisy heavy source exposed why a stretched preview cannot serve as a general codec oracle. Every measured exposure frame must change actual photo-region pixels, and all revisions must execute the same exposure sequence. Bounds were fixed before the final comparison and were not widened. Upstream RAW colors exceed parity, so its medians are descriptive only.

Median, linear p95 and maximum are retained. Ratio = fork-point median / fork-main median. The 2,000-resample paired-session bootstrap (seed 313) resamples whole sessions, keeping the 60 slider steps clustered. “Faster”/“slower” requires the 95% CI to exclude 1; otherwise the verdict is “no measurable change.”

The real-file tiers and licenses are documented in [the README](../README.md#lightcraft-session-latency-hyper-291-correction), with 568 URL/SHA-256/provenance pins in [craft-corpus](../../corpus/manifests/lightcraft-session-2026.toml) and exact [tier membership](../fixtures/lightcraft-session-tiers.json). Typical: 50 distinct Sony A7C 24 MP RAWs from RawNIND v1.0, one low-ISO exposure per scene, CC BY-SA 4.0, Benoit Brummer and Christophe De Vleeschouwer. Heavy: 500 distinct nominal 24–45 MP files from CC0 raw.pixls.us and Signature Edits originals. It is a camera/encoding mix, not a measured population percentile. The heavy preview/exposure source is a 24 MP Canon EOS M3 CR2; the 500-file import is mixed. These local SSD tiers do not reproduce CF/NFS, 22,000/58,000-file, or mask-correctness complaints.

## Results

Ratio = fork point / fork main; >1 favors fork main. Times in ms. CI resamples whole paired sessions, not individual slider steps.

Payload: typical-50

| Action | Fork point median/p95 | Fork main median/p95 | Ratio (95% CI) | Upstream median | Verdict |
|---|---:|---:|---:|---:|---|
| import | 3772.69/5093.97 | 3513.17/5537.78 | 1.074 (0.889–1.242) | 3665.56† | no measurable change |
| preview | 217.79/357.30 | 218.66/419.42 | 0.996 (0.741–1.045) | 309.08† | no measurable change |
| exposure | 126.99/374.87 | 121.30/336.89 | 1.047 (0.883–1.177) | 123.96† | no measurable change |
| switch | 984.67/1677.23 | 1074.17/1812.27 | 0.917 (0.685–1.444) | 1873.65† | no measurable change |
| export | 404.55/596.08 | 368.42/587.13 | 1.098 (0.762–1.400) | 592.54† | no measurable change |
| startup | 1828.79/2543.86 | 1869.51/3032.13 | 0.978 (0.667–1.362) | 2812.49† | no measurable change |
| quit | 231.87/328.80 | 216.19/410.42 | 1.073 (0.743–1.324) | 253.24† | no measurable change |

† Upstream output exceeded the pixel-parity bound. Its medians are descriptive observations only; no upstream-relative speed claim is made.

Supplementary first-import / first-full-preview observations use the first retained setup sample in each fresh session (10 per revision). GPU initialization was already warmed; OS and shader caches were not flushed. These are separate from the planned post-warm-up table:

Ratio = fork point / fork main; >1 favors fork main. Times in ms. CI resamples whole paired sessions, not individual slider steps.

Payload: typical-50

| Action | Fork point median/p95 | Fork main median/p95 | Ratio (95% CI) | Upstream median | Verdict |
|---|---:|---:|---:|---:|---|
| import (first pass) | 3283.65/7388.26 | 3580.98/4931.02 | 0.917 (0.853–1.089) | 3464.00† | no measurable change |
| preview (first pass) | 2795.81/3909.39 | 2940.16/3889.82 | 0.951 (0.808–1.247) | 5579.20† | no measurable change |

† Upstream output exceeded the pixel-parity bound. Its medians are descriptive observations only; no upstream-relative speed claim is made.

Maximum observed latency (ms):

| Payload | Action | Fork point max ms | Fork main max ms | Upstream max ms |
|---|---|---:|---:|---:|
| typical-50 | import | 5300.57 | 5897.97 | 6752.59 |
| typical-50 | preview | 386.72 | 470.60 | 411.17 |
| typical-50 | exposure | 707.85 | 659.79 | 652.72 |
| typical-50 | switch | 1803.48 | 2057.86 | 2646.90 |
| typical-50 | export | 642.83 | 651.41 | 1031.11 |
| typical-50 | startup | 2563.85 | 3101.04 | 4004.72 |
| typical-50 | quit | 339.40 | 477.04 | 382.20 |

## Isolation and output evidence

- typical-50: {'point': 10, 'main': 10, 'upstream': 10}; publication gate `True`; CPU guard contended `False`; harness `9211b81aad19766dc1ff2af1fb956b8af3b79cb8`; 1325 before/after/during process snapshots; 0 discarded attempts; 0 admission waits; 1800 measured photo changes; 0 measured native-completion upper bounds. Provisional tiers/offenders: `{}`.

The GPU lock is advisory. Admission polls the exact NVIDIA PID/name CSV every 30 seconds if a foreign process exists; a two-second watcher covers each attempt, with before/after snapshots retained. Observed contention discards and repeats the attempt. A 30-minute clean-session budget labels the whole tier provisional with offender names, and prevents publication. The supplemental five-second ledger is audited over accepted session windows. Sampling cannot observe a process that starts and exits entirely between polls. Shared-GPU and failed pilots remain excluded and retained with status sidecars; see [failed approaches](313-capture-failures.md).

Full reports, native PNGs, candidate hashes/timestamps, GPU CSVs, logs, profiles and analysis scripts: `wormhole:/mnt/bulk/backups/speedcraft-labs/tickets/313-session-latency/20261110T060949Z/313-session-latency/`. No build output or reproducible pinned RAW download cache is stored there. The [summary JSON](313-lightcraft-summary.json) records original report SHA-256, binary SHA-256, fingerprints, guards, parity metrics, p95/max and CIs. The [per-session timing projection](313-lightcraft-sessions.jsonl) retains every action sample and warm-up; full pixel proofs remain in the NAS source reports.

## Quit-time hypothesis

**Confirmed for the old cold launch-per-task method.** Ten interleaved attempts per revision per task (120 complete attempts) under both locks, all zero exits, clean before/after GPU checks and supplemental ledger. Fork main adds 2.078–2.112 s quit time versus the fork point, accounting for the 1.889–2.005 s net process regression. No task has a measurable positive residual outside quit. The previously published upstream comparison similarly decomposes into 1.945–2.054 s extra quit versus 1.789–1.879 s net process regression. Medians of components need not add, but the decomposition is exact for each pair.

Cold legacy-path diagnostic, ms. Deltas are paired fork-main minus fork-point observations, bootstrap 95% CI. All primary pixel checks pass.

| Task | Point quit median/p95 | Main quit median/p95 | Process delta | Quit delta | Residual outside quit (95% CI) |
|---|---:|---:|---:|---:|---:|
| open | 122.9/289.6 | 2221.7/2331.0 | 1985.5 | 2080.3 | -86.7 (-167.0–31.4) |
| edit | 120.7/356.3 | 2228.9/2489.8 | 1889.2 | 2077.8 | -182.7 (-264.4–-116.5) |
| save | 142.1/244.8 | 2249.8/2470.8 | 2005.2 | 2112.0 | -76.0 (-155.1–-0.6) |
| export | 110.1/347.9 | 2212.7/2616.3 | 1997.8 | 2096.5 | -123.9 (-194.1–-41.6) |

The two seconds are a timeout while `lc-gpu-window` / `lc-gpu-kernels` remain inside NVIDIA shader compilation. Fork main eagerly builds 48 unused radius-specific median pipelines (87 kernels total versus 38 at the fork point). One cold profiled initialization took 111,952 ms; a warm shader cache reduced it to 853 ms. These are separate diagnostic observations, not session action statistics. The host shutdown deadline is two seconds; the last-resort atexit guard is installed only after GPU initialization completes. Deferring unused compilation or improving cancellation is fixable but exceeds a few lines. Removing exit protection risks the crash it prevents. No app code is changed here. See [hyper #317](https://github.com/speedcraft-labs/hyper/issues/317) and the existing #309 fix work. As of the final report, #309 has a separate proposed exit-drain fix (`0218fd9d`) and both tracker issues remain open; this report evaluates only the frozen revisions above.

A separate clean-GPU cold attempt observed SIGSEGV; its exact exit time was unavailable in the old controller and is explicitly retained as such. The complete 120-attempt rerun had zero failures; that does not erase the earlier crash. Diagnostic records now retain all exit statuses and never substitute forced termination for quit. Cold fork-main rendering may use CPU fallback while GPU initialization is pending, so no interactive GPU-speed claim follows from the cold process diagnostic. All 40 primary diagnostic output comparisons pass; upstream JPEG MAE 0.629 exceeds its preset 0.5 bound, so that secondary export observation is descriptive.

## Optional stress and lock scheduling

Heavy-500 v4 retained seven completed sessions: fork point 3, fork main 2, upstream 2. There are only two complete pairs, no final acquisition CPU guard, and no ten-pair inference. Its raw report and 510 supplemental GPU snapshots are retained; no foreign process was observed in those accepted windows. The coordinator stopped the almost-90-minute acquisition with 13 benchmarks waiting. The first upstream untimed background drain took 801 seconds. No heavy ratio or verdict is published.

Future commands run one pair per acquisition, resume through `resume_report` into a fresh directory, and retain every acquisition guard. Missing or contended guards prevent publication. Use the README timeout inside both locks to cap each acquisition at 15 minutes; release between pairs. Heavy stress is optional and runs only without queued workers. The interrupted monolithic approach is preserved on `failed/313-monolithic-stress-lock`.

## Follow-ups and validation


`cargo test -p craft-journeys` passes (three Rust tests including 23 Python evidence/statistics tests); formatting and targeted journeys clippy pass. Required workspace validation is not green: the latest full run fails unchanged HEVC conformance::bframes and conformance::draft_mode_changes_only_flagged_non_reference_pictures; both reproduce in isolation (Y mismatch 151 versus 147, max 66, 20460 samples in bframes). Workspace clippy reports two unchanged GPU-blur shader assign-op lints and an unchanged AV1 test sort lint. Earlier H.264 rapid-reset runs exceeded 300 seconds, but that test passed in the latest full run. An initial low-priority craft-diff timing test failed at 38 s; its isolated normal-priority retry passed at 16.9 s. Those results and failed cleanup experiments are retained. No unrelated codec/shader edits are included. The PR must remain open unless the required checks and reviews become green.

Pushed branches: `algo/313-session-latency`, `wip/313-session-latency`, and `failed/313-{shared-target-cache,corpus-layout,native-capture-pilot,retry-frame-bound,shared-gpu-matrix,gpu-lock-rejections,workspace-lint-attempt,cold-quit-segv,grid-overscroll,upstream-prep-timeout,preview-geometry-oracle,monolithic-stress-lock}`. [Build failures](313-build-notes.md) and [capture/traversal failures](313-capture-failures.md) explain why those approaches were dropped.

Reproduce every timing statistic from the committed projection (full pixel proofs
remain in NAS):

```sh
PYTHONPATH=crates/journeys/scripts python3 - <<'PY'
import json
from lightcraft_session_report import summarize
path = "crates/journeys/reports/313-lightcraft-sessions.jsonl"
sessions = [json.loads(line) for line in open(path)]
rows = summarize(sessions)
expected = json.load(open("crates/journeys/reports/313-lightcraft-summary.json"))["rows"]
assert [(r["speedup"], r["ci95"], r["sides"]) for r in rows] == [
    (r["speedup"], r["ci95"], r["sides"]) for r in expected
]
PY
```
