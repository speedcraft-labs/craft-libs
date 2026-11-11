# LightCraft session latency — sensitivity revision, hyper #291

The original 10-pair comparison could not resolve useful action changes. Its
historical reports and timing projection are preserved at
`wormhole:/mnt/bulk/backups/speedcraft-labs/tickets/313-session-latency/20261110T060949Z/313-session-latency/`.
Do not interpret its unchanged verdicts as evidence of equivalence.

The replacement driver observes X11 frames before dispatch, requires an untimed
idle interval before actions, fixes the switch photo pair and repeats actions and
populated-library lifecycles within each session. See the README for state resets,
first-use definitions, clock limits, fixed output gates and A/A/MDE definitions.
No LightCraft performance code, other app journeys, launch-per-task reports or
status-site files change.

## Original variance diagnosis

Only measured repetitions are used. The original single measured samples cannot
identify within-session variance for import, preview, switch, export or lifecycle
rows; their across-session dispersion includes that unknown component. Exposure
has 60 measured updates. The old warmup-plus-measurement proxy is retained in the
raw diagnostic history but is not used as a variance-component estimate here.

| Original action | Sessions | Measured repeats/session | Across-session log SD % | Within-session log SD % |
|---|---:|---:|---:|---:|
| import | 10 | 1 | 21.11 | not identifiable |
| preview | 10 | 1 | 30.99 | not identifiable |
| exposure | 10 | 60 | 30.98 | 23.96 |
| switch | 10 | 1 | 33.16 | not identifiable |
| export | 10 | 1 | 22.90 | not identifiable |
| startup | 10 | 1 | 29.32 | not identifiable |
| quit | 10 | 1 | 33.79 | not identifiable |

A separate frozen-driver three-repeat diagnostic pilot estimates within-session
log SD at 4.93/20.52/11.06/32.05/9.23% for import/preview/exposure/switch/export.
It has only one main session, no identifiable between-session component and no
Rust publication guard; it is diagnostic, not A/A or performance evidence.

Fast/slow retained measured action, fork main. lastRenderMs is the last render only, not the entire action.

| Action | Fast ms / lastRenderMs | Slow ms / lastRenderMs |
|---|---:|---:|
| preview | 160.94 / 9.159813 | 470.60 / 9.782168 |
| exposure | 109.63 / 3.4216390000000003 | 659.79 / 4.151873999999999 |
| switch | 732.37 / 108.52449 | 2057.86 / 306.512499 |
| export | 319.09 / 108.52449 | 651.41 / 217.239949 |


The original one-sample actions cannot identify both variance components. A
frozen-driver repeated pilot and the new interleaved A/A run are required to
separate within-session noise without those assumptions. Shader initialization
already finishes before these action clocks. Neither disk nor shader caches were
flushed, so this data cannot identify their independent causal contributions.
The slow preview/exposure samples have almost unchanged last-render times;
the switch also varies the selected scene. Readiness polling, IPC, frame pacing,
readback and background work were not separately timestamped in that method.
The new pre-dispatch observer records presentation candidates independently of
readiness polling, but still measures sampled displayed frames, not scanout.

## Transport pilot: a measured instrumentation floor

One diagnostic session with the pre-dispatch observer but original TCP transport
completed on reserved CPUs with a clean guard/GPU. It is not an A/A acceptance run:
its queued counterpart was stopped before launch after the trace exposed this
problem. All raw data and 40 verified exposure photo changes remain retained.

| Call | Count | Median RTT ms | p95 RTT ms | Fraction at 38–60 ms |
|---|---:|---:|---:|---:|
| ui.inspect | 3960 | 42.77 | 63.30 | 91.2% |
| engine.execute | 314 | 43.93 | 75.57 | 59.9% |
| ui.pointer | 90 | 65.07 | 88.60 | 30.0% |

Preview varied 127.84–356.13 ms while the corresponding last renders were
13.97/8.41 ms. Exposure varied 50.29–154.76 ms with 3.98/4.53 ms last renders.
Switch varied 444.22–609.12 ms with 405.17/572.17 ms renders: this action also
contains substantial real rendering variance and must not be corrected by
subtracting a constant. The export lastRenderMs field describes the preceding
switch, not JPEG encoding, so it cannot attribute export variance.

The production server token-streams JSON with `writeln!(out, "{r}")` and leaves
Nagle enabled; its own test connection disables Nagle on both sockets. This plus
the 40 ms RTT concentration makes delayed ACK a concrete transport hypothesis.
The session-only client now uses NODELAY and re-enables QUICKACK before and after
each receive, including partial JSON. Protocol tests cover fragmented UTF-8 and
buffered lines. The new A/A must verify the resulting precision; no fixed delay
is subtracted and the launch-per-task transport is unchanged.

The old X11 sampler also had median 20–28 ms / p95 78–187 ms observation gaps,
despite a nominal 5 ms sleep. Its display server ran on CPUs 0–21. New acquisitions
launch a private NVIDIA Xorg on the same reserved CPUs 22–27 as the app, record
its affinity, and stop only that owned server before releasing the locks.

## Validation of prior failures

Clean integration: `c67c32c6`. Commands, with one shared target directory and builds
on CPUs 0–21:

```sh
cargo test -p craft-hevc conformance::bframes -- --nocapture
cargo test -p craft-hevc conformance::draft_mode_changes_only_flagged_non_reference_pictures -- --nocapture
cargo clippy --workspace --all-targets -- -D warnings
cargo clippy -p craft-av1 --all-targets -- -D warnings
```

An earlier full required local workspace run passed: **3,835 passed, 127 ignored,
zero failures** across 295 reported suites including doctests. After rebasing on
`cd0f22bc`, the repeated full run hit two untouched timing assertions: H.264
rapid reset exceeded 300 s and proof long-TRY took 11.281 s against a 10 s limit.
Both fail on clean integration `cd0f22bc`: H.264 at 300.04 s; proof takes
14.266 s against the same 10 s assertion. Neither file differs from integration.
The reporting-guard workspace run passes again: 3,835 passed, 127 ignored,
zero failures. The corpus-selection rerun has 3,834 passed, one failed,
127 ignored: the font watcher times out after 10.01 s at tests.rs:359. The exact
isolated font test fails identically on clean integration (10.00 s); that crate
also has no PR changes. The latest physical-proof documentation run passes
again: 3,835 passed, 127 ignored, zero failures, including 38 Python checks.
All outputs remain retained. Targeted journeys
tests pass (3 Rust tests including 38 Python tests). Both HEVC tests pass on clean integration. This branch's
`cargo test -p craft-hevc conformance:: -- --nocapture` passes 43 tests, ignores 2.
The old HEVC failures are currently **not reproducible**, not established baseline
failures. Clippy reproduces the two shader assign-op errors (lines 58/78) and the
AV1 `fuzz_hostile.rs:184` unnecessary-sort error on clean integration. These files
are identical to integration and untouched by this PR. Full logs live under the
single ticket keep directory's `sensitivity/` subdirectory.

## Payloads and pins

50 distinct RawNIND A7C 24 MP files remain the typical tier (**CC BY-SA 4.0**).
The import-heavy tier has 1,259 distinct, SHA-verified **CC0** camera originals,
about the 1,300-photo count in upstream #367. Add-in-place checks `by_hash` when
`!opts.local` in `engine/src/import/job.rs:330–367`, so renamed content repeats
would be invalid. This tier uses no repeated contents. It mixes cameras, formats
and resolutions rather than pretending to represent a 1,300-shot wedding.
The 38,545-photo/~25-minute report in #832 is out of scope.

New pins: fork point `fc97c728644d399843d8201f83d25ccf81b89669`, fork main
`5f816e195b9b23febef83f6c3687e7c049f9c93d`, upstream
`e9c29e2c5c5dd1f86cc98677b5dc389f6612fcac` (descriptive column).
Two separate clean builds of fork main have identical SHA-256
`a2141392356df24930fb04877d9c99be639153224b867790b9d90ec973e6185d`.
Build recipes, logs and hashes are retained with the raw reports. Corpus URL/hash
pins are committed; generated reports, per-run JSON and media stay off git.

The completed replacement A/A passes 0/14 requested gates. Valid warm-action
approximate MDEs span 12.79–44.36%; cold switch, warm startup and both quit
controls exclude unity and cannot validate later comparison verdicts. The
independent physical 10% check passes; real comparisons remain pending. No 5%
sensitivity or new LightCraft performance claim is made.


## Retained v4 diagnostic protocol

All v1–v3 trials are diagnostic and retained; they are not silently pooled into
the acceptance gate. Before collecting the fixed v4 campaign:

* Each bounded AB/BA acquisition resets a private NVIDIA display **per build**,
  on reserved CPUs 22–27. Ten complete independent pairs are required.
* Import ends at the first proven usable viewport after all requested files enter
  the catalog. Full thumbnail-page coverage remains mandatory outside timing.
  Scripted scrolling and repeated native screenshots are not a user import action.
* The ratio is exp(median log paired-session median(point)/median(main)). Whole
  paired sessions are resampled within the fixed even/odd order strata (4,000
  resamples, seed 313). Pooled medians/p95 remain descriptive latency columns.
  Ordinary paired and original pooled-median CIs are also retained, so this change
  of estimator/design is explicit and auditable. No observations are trimmed.
* The A/A half-width/unity gates and the independent real 10% queued-delay check
  remain mandatory. The latter must detect a changed action; a narrower formula
  alone cannot validate sensitivity.

The shared-display v3 diagnostic had warm startup 823/1,259 ms and quit 106/177 ms
for identical binaries in its first pair. Its next reversed pair had startup
1,186/1,621 ms (main first, point second). Those results exposed session/order
state; they do not establish that all of it came from the display. A read-only
check found no bench.slice quota/throttling (cpu.max unlimited, nr_throttled 0),
only the owned service on CPUs 22–27, and GPU temperature 51 C / P8 at that instant.
GPU clocks and host-frequency effects have not been independently identified.


## Controlled GPU condition

The six accepted v4 sessions (three A/A pairs) are diagnostic, not an acceptance
gate. Identical binaries had warm switch last-render medians A/B of 892/1,062,
474/856 and 532/749 ms. All deliberate-delay fields were zero. A read-only
observer saw graphics clocks 300–1,350 MHz and memory 405–7,000 MHz; sparse
observations during pair 2 switching were 585 MHz for A (one observation) and
442.5 MHz median for B (four observations). This suggests a power-state source
of variance, but is not an independent causal experiment.

A scoped capability probe confirmed graphics locking at 1,350 MHz. The memory
lock command printed “not supported” while returning zero. Setting the owned
X display's PowerMizer mode from its original 2 to 1 held P0 at 1,350/7,000 MHz.
The probe restored mode 2 and default clock management before releasing either
lock. Raw CLI output, initial support-flag parsing failure and corrected probe
are retained. No action samples were collected by these probes.

The new v5 campaign uses the same action clocks and statistics under that
controlled GPU condition, with explicit untimed clock observations before every
action and lifecycle timer. Wrong clocks reject a session; calibration also
requires matching clock/repeat settings. It starts fresh: no v4 observations
are pooled into v5. Absolute latencies are conditional on this stated GPU state.
The scoped controller must restore settings even when its owned unit expires.

## Contiguous-pair calibration

The completed ten-pair v5 A/A passed 3/14 action/state gates, but cold preview
falsely differed for identical binaries (ratio 1.100, CI 1.015–1.326). Its long
sessions split pairs across the queue, with between-build gaps up to 789 seconds.
That failed design is retained at `failed/313-split-session-pairing`.

An independently predeclared replacement uses 20 contiguous AB/BA pairs, four
repetitions, two warmups and four exposure moves per gesture. Each pair must fit
one 840-second lease. No split pair enters this calibration. The action clocks,
GPU condition, bootstrap and all successful numeric observations are unchanged.
An A/A CI excluding 1 now rejects that action's later comparison verdict; a narrow
interval alone cannot validate sensitivity. Wide unbiased controls retain their
explicit, larger MDE floor. The complete gate is retained at
`sensitivity/aa-v6-paired-attempt-37-19/report.json` in the ticket keep root.
Its 20 main sessions have between/within log SD (%): import 39.43/18.37, preview
19.24/21.80, exposure 22.74/22.59, switch 24.33/14.90, export 21.04/6.07,
startup 30.87/7.09 and quit 34.89/32.90. These commits and scenes differ from the
old trial, so this is not a causal harness-only comparison.

Median/max between-build gap fell from 465.30/1301.47 s to 27.72/181.94 s.
A foreign GPU admission wait still delayed one counterpart inside its lease.
Warm switch duration correlates 0.997 with the preview worker lastRenderMs.
Coarse two-second CPU-steal observations correlate 0.766 with switch and 0.799
with export; these are descriptive, not independent causal proof. Timed X11
capture-gap p95 is 38–68 ms across rendered actions. The remaining variation
cannot be reported as a proven 5% sensitivity.

The known-delay pilot exposed a separate reference problem: a 97.999 ms delay
from the hours-long A/A median would add 23.135% to its contemporaneous untreated
423.593 ms control. That whole pair is retained as diagnostic. A fresh fixed
20-pair physical check uses 42.35933825 ms (10% of that untreated pilot). It
passes both the slower verdict and predeclared 9–11% magnitude gate: actual
median delay 42.526 ms, 9.69% of the independent 438.944 ms control; ratio 0.875,
95% CI 0.833–0.923. All 80 measured treatment delays fall inside their action
clocks. Raw: `sensitivity/switch-slowdown-v6-calibrated-attempt-31-19/report.json`
and `switch-slowdown-validation.json`. This is a known-delay proof, not evidence
of universal 5% sensitivity. Treatment CIs
were not used to choose the dose or stop the pilot. No numeric sample is trimmed.

The initial heavy pilot offered 1,259 of 1,262 files for import and was rejected
before any accepted action sample. The three missing PowerShot CR2s have non-TIFF
headers; official source SHA-256 matches, and two source descriptions identify
CHDK. Their pins and failure evidence remain retained, while the measured tier
uses the other 1,259 distinct files. This is a declared payload-compatibility
exclusion before A/A, not latency trimming.


The successful 1,259-photo pilot passed every catalog/thumbnail/output check in
385.803 s per app. Import was 92.409 s first use, 41.755 s transitional warmup,
then 15.633/17.761 s measured warm. Keeping both warmups matters. Heavy A/A and
real primary use the same predeclared ten-pair alternating AB/BA cadence with
one build per bounded lease and empty-queue stress admission. They retain the
same action clocks, two warmups and two repetitions; the lone pilot is not
seeded into calibration. Actual between-build gaps and MDE floors are reported.
The real 50-RAW comparison uses the original binaries with zero test delay.
