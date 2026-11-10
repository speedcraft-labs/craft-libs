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

Variance diagnostics; log SD ×100 is approximate relative SD (%). First use is excluded. No trimming. Old run includes the second warm-up because only one measured repetition exists; switch scene varies, so the old within/session split is descriptive and order-confounded. New run uses measured repeats only.

| Dataset / action | Sessions | Repeats/session | Between-session log SD % | Within-session log SD % |
|---|---:|---:|---:|---:|
| paired-typical-50-resilient-v2 / import | 10 | 2 | 23.31 | 8.53 |
| paired-typical-50-resilient-v2 / preview | 10 | 2 | 13.97 | 25.45 |
| paired-typical-50-resilient-v2 / exposure | 10 | 61 | 30.76 | 24.06 |
| paired-typical-50-resilient-v2 / switch | 10 | 2 | 30.28 | 9.76 |
| paired-typical-50-resilient-v2 / export | 10 | 2 | 21.08 | 9.95 |
| paired-typical-50-resilient-v2 / startup | 10 | 1 | 29.32 | not identifiable |
| paired-typical-50-resilient-v2 / quit | 10 | 1 | 33.79 | not identifiable |

Fast/slow retained measured action, fork main. lastRenderMs is the last render only, not the entire action.

| Action | Fast ms / lastRenderMs | Slow ms / lastRenderMs |
|---|---:|---:|
| preview | 160.94 / 9.159813 | 470.60 / 9.782168 |
| exposure | 109.63 / 3.4216390000000003 | 659.79 / 4.151873999999999 |
| switch | 732.37 / 108.52449 | 2057.86 / 306.512499 |
| export | 319.09 / 108.52449 | 651.41 / 217.239949 |


Warm-up/order effects confound this old split; startup/quit have no repeats. A
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

The full required local workspace run now passes: **3,835 passed, 127 ignored,
zero failures** across 295 reported suites including doctests. Targeted journeys
tests pass (3 Rust tests including 33 Python tests). Both HEVC tests pass on clean integration. This branch's
`cargo test -p craft-hevc conformance:: -- --nocapture` passes 43 tests, ignores 2.
The old HEVC failures are currently **not reproducible**, not established baseline
failures. Clippy reproduces the two shader assign-op errors (lines 58/78) and the
AV1 `fuzz_hostile.rs:184` unnecessary-sort error on clean integration. These files
are identical to integration and untouched by this PR. Full logs live under the
single ticket keep directory's `sensitivity/` subdirectory.

## Payloads and pins

50 distinct RawNIND A7C 24 MP files remain the typical tier (**CC BY-SA 4.0**).
The import-heavy tier has 1,262 distinct, SHA-verified **CC0** camera originals,
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

A/A, deliberate-slowdown and replacement comparison results are pending; this
file currently makes no new latency or sensitivity claim.


## Frozen v4 acceptance protocol

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
