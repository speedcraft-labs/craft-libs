# craft-journeys

`craft-journeys` connects application journey adapters to `craft-bench`. It keeps the paired
ABBA schedule, bootstrap confidence interval, machine fingerprint, output check and load guard
from that crate. The app adapter is a one-shot command configured in `journeys/catalog.json` (or
`CRAFT_JOURNEYS_CONFIG`).

Each adapter command receives `CRAFT_JOURNEY_REV`, `ARTCRAFT_CORPUS`, and these expanded
arguments: `{rev}`, `{app}`, `{input}`, `{input_name}`. The build command must build the app at
the requested craft-libs revision. The run command exercises the app's existing perf/control
channel on one pinned corpus input or deterministic generated workload. Marker-protocol adapters
print these lines to stdout:

```text
CRAFT_JOURNEY_NS=1234567
CRAFT_OUTPUT_SHA256=0123456789abcdef...
```

The duration is the journey channel's duration in nanoseconds. The digest is the resulting
render/document/output identity; it must not include timing fields. The native parsers below read
those values from app output instead of marker lines. Missing measurements or identities invalidate
the output check. Commands must be one-shot and leave the app's measured operation outside process
startup when the app channel reports a more precise duration.

`run.wall_time` defaults to `app`, which uses the duration reported by the application's existing
performance channel. Set it to `process` when the journey should use the runner's monotonic clock
from just before process launch through command exit. The app's timing marker is still required for
the adapter protocol and output identity check; process mode makes externally measured wall time the
primary paired metric and includes process startup plus the command's work.

Cargo adapters may add `cargo_config_overrides` after the selected craft-libs revision's Cargo
patch config. The `{app_repo}` placeholder resolves to the app's isolated worktree. This lets an
app use a newer app-local vendored dependency when its API is ahead of the craft-libs workspace
copy.

The checked-in catalog includes native parsers for CADCraft `perf FILE`, WordCraft's
`perf_probe` JSON, DeckCraft `bench FILE --json`, LightCraft's slider latency table, PdfCraft's
`export_bench` summary, VectorCraft's `export_bench` summary, and DesignCraft's deterministic
synthetic `perf` channel, EffectCraft's generated-project operation benchmark, PhotoCraft's
deterministic generated-image benchmark, FigCraft's synthetic viewport benchmark, and GridCraft's
generated-workbook benchmark, SoundCraft's synthetic mix-throughput benchmark, and FilmCraft's
generated-project open benchmark. These adapters extract the native measurement and a stable
document or workload identity. A journey with no external inputs supplies one app-generated
synthetic case.
`compare` treats `--base` and `--head` as craft-libs revisions. App revisions can be selected with
`CRAFT_JOURNEYS_APP_BASE_REV` and `CRAFT_JOURNEYS_APP_HEAD_REV`; these default to `HEAD` and the
base app revision. The runner checks each input against its `.craft-corpus.json` manifest and
SHA-256 before building. It keeps revision worktrees and Cargo patch files under the configured
target root so prepared builds can be reused.

### Available journeys

| Journey | App | Measured operation |
| --- | --- | --- |
| `cadcraft.edit-hatched-drawing.12k` | CADCraft | Edit one entity in a deterministic generated 12,000-hatch drawing |
| `cadcraft.open-dxf.large-map` | CADCraft | Open the pinned Graz map DXF |
| `cadcraft.open-dxf.usa` | CADCraft | Open the pinned USA DXF |
| `cadcraft.open-dxf.us-main` | CADCraft | Open the pinned US-main DXF |
| `wordcraft.startup-cold-first-frame`, `wordcraft.startup-warm-first-frame` | WordCraft | Cold and warm start through the first interactive document frame |
| `wordcraft.open-typical-docx`, `wordcraft.scroll-typical-docx`, `wordcraft.edit-typical-docx`, `wordcraft.save-typical-docx` | WordCraft | Open, scroll, edit and save a public median-sized DOCX; save output is reopened and checked outside the timed process |
| `deckcraft.startup-cold-first-frame`, `deckcraft.startup-warm-first-frame` | DeckCraft | Cold and warm start through the first interactive presentation frame |
| `deckcraft.open-typical-pptx`, `deckcraft.navigate-typical-pptx`, `deckcraft.edit-title-typical-pptx`, `deckcraft.save-typical-pptx`, `deckcraft.export-typical-pptx` | DeckCraft | Open, navigate, edit text, save and export a public median-sized 26-slide PPTX |
| `lightcraft.startup-cold-first-frame`, `lightcraft.startup-warm-first-frame` | LightCraft | Cold and warm desktop start with a prepared photo library through the first photo frame |
| `lightcraft.open-typical-photo`, `lightcraft.edit-exposure-typical-photo`, `lightcraft.save-typical-photo`, `lightcraft.export-typical-photo` | LightCraft | Open, adjust exposure, save, and export a representative public-domain photograph |
| `deckcraft.open-office-pptx` | DeckCraft | Open the pinned chart PPTX |
| `deckcraft.drag-shape.heavy-slide` | DeckCraft | Drag a picture shape across the pinned, picture-rich 24th slide of the Apache-2.0 licensed HowWeRefactor deck through the editor canvas texture path; records every CPU frame |
| `lightcraft.slider-exposure-latency` | LightCraft | Apply exposure while dragging the slider |
| `pdfcraft.edit-100k-pages` | PdfCraft | Add text to a generated 100,000-page document |
| `pdfcraft.edit-acroform-3129` | PdfCraft | Edit one field in a generated 3,129-field AcroForm |
| `pdfcraft.export-pdf.form-fixture` | PdfCraft | Export the pinned one-page form PDF to PNG |
| `vectorcraft.export-svg.still-life` | VectorCraft | Export the pinned Still Life document to SVG |
| `designcraft.synthetic-performance` | DesignCraft | Compose a deterministic synthetic document |
| `effectcraft.synthetic-project-open` | EffectCraft | Open a generated project sized toward the surveyed 125 MB |
| `effectcraft.first-frame-heavy-comp` | EffectCraft | Render a cold full-resolution (1,920×1,080) first frame of a generated 5,000-layer composition |
| `photocraft.synthetic-image-open` | PhotoCraft | Open a generated 4096×2731 image on CPU |
| `photocraft.layer-opacity-fill-move-styled` | PhotoCraft | Change opacity/fill and move a styled layer on a 20 MP document |
| `photocraft.move-layer-16bit-15000x10000` | PhotoCraft | Move a layer on a 15000×10000 16-bit canvas |
| `photocraft.content-aware-scale.24mp` | PhotoCraft | Remove 10% of a generated 6000×4000 photo-like image by seam carving |
| `figcraft.synthetic-viewport-render` | FigCraft | Render a 100-layer synthetic document |
| `gridcraft.synthetic-workbook-open` | GridCraft | Open and recalculate a generated 1,000-row workbook |
| `soundcraft.synthetic-mix-throughput` | SoundCraft | Mix 32 generated tracks over 4 seconds |
| `filmcraft.synthetic-project-open` | FilmCraft | Open a generated project with the 360p clip fixture |

Run and compare:

```sh
cargo run --release -p craft-journeys -- run --journey cadcraft.open-dxf.large-map --out baselines/cadcraft-open.json
cargo run --release -p craft-journeys -- compare --base app-locked --head app-locked --journey wordcraft.open-typical-docx --out baselines/wordcraft-open.json
cargo run --release -p craft-journeys -- prepare --base app-locked --head app-locked --journey wordcraft.open-typical-docx
```

`run` pairs the current craft-libs working tree against itself to produce a baseline report.
`compare` builds and runs both requested craft-libs revisions and prints the speed verdict.
`prepare` verifies the selected inputs and builds both app/library revisions without collecting
measurements. Use it before acquiring the shared benchmark lock so Cargo compilation stays outside
the locked measurement window. After preparation, `run` and `compare` accept `--no-build` to skip
their build phase; adapters configured with `{app_binary}` then execute the prepared binary
directly, without invoking Cargo during samples.
Set `CRAFT_JOURNEYS_APP_BASE_REV` and `CRAFT_JOURNEYS_APP_HEAD_REV` to compare app revisions;
they default to `HEAD` and the same revision. Raw report revision labels record both app and
craft-libs revisions. Each app build and run gets a target directory keyed by both revisions,
and revision worktrees plus Cargo patch files keep stable paths under the selected target root,
so paired runs reuse their warmed binaries instead of rebuilding one side over the other.
The PhotoCraft layer journeys run the prepared `perf_scenarios` executable by its `{target_dir}`
path, so a locked measurement never invokes Cargo. Adapter builds use `nice -n 19` and eight Cargo
jobs, outside CPUs 22–27 reserved for measurement.
Run `prepare` before acquiring the shared benchmark lock, then use `--no-build` with `run` or
`compare` while the lock is held. Both commands return exit code 1 for a non-publishable report;
errors return 2.

For the shipped catalog, set the hyper checkout, corpus and build directory first. App builds
are isolated by app and both revisions under the selected target root, so ABBA samples
don't replace each other's executable:

```sh
export ARTCRAFT_HYPER_ROOT=/jobs/work/speedcraft-labs/hyper
export ARTCRAFT_CORPUS="$ARTCRAFT_HYPER_ROOT/corpus"
export CRAFT_JOURNEYS_TARGET_DIR=/jobs/work/speedcraft-labs/targets/phase0-craft-journeys
cargo run -p craft-corpus -- fetch crates/corpus/manifests/pngsuite.toml "$ARTCRAFT_CORPUS/pngsuite"
cargo run -p craft-corpus -- fetch crates/corpus/manifests/pdfcraft-fixtures.toml "$ARTCRAFT_CORPUS/pdfcraft-fixtures"
cargo run -p craft-corpus -- fetch crates/corpus/manifests/vectorcraft-fixtures.toml "$ARTCRAFT_CORPUS/vectorcraft-fixtures"
cargo run --release -p craft-journeys -- run --journey cadcraft.open-dxf.large-map --out cadcraft-open.json
cargo run --release -p craft-journeys -- compare --base BASE_LIBS_REV --head HEAD_LIBS_REV --journey wordcraft.open-office-docx --out wordcraft-open.json
cargo run --release -p craft-journeys -- run --journey lightcraft.slider-exposure-latency --out lightcraft-exposure.json
```

PdfCraft's `pdfcraft-public-domain` journeys cover an IRS Form 990 with 1,075
hierarchical AcroForm fields, an IRS Form 1040 with 199 fields, the 4,211-page
2023 U.S. Code Title 26, and OPM's 95-page SF 85P with 4,128 hierarchical
fields and embedded XFA JavaScript, and OSHA's 12-page recordkeeping package with
300 AcroForm widgets and 110 widgets carrying `/AA` actions. OSHA's real actions
exercise format, validate, and calculate behavior. The IRS forms carry
document-level scripts; their AcroForm fields have no `/AA` actions or `/CO`
calculations. Every corpus entry pins its source URL and SHA-256 in the manifest.
Each journey times one PdfCraft `Session` edit after open.

### Real-world app journeys

The end-to-end set covers PhotoCraft, PdfCraft, GridCraft, CADCraft and WordCraft. Each app has fresh-profile
(`startup-cold-first-frame`) and primed-profile (`startup-warm-first-frame`) starts. Startup timing
comes from the external Python driver, from process launch until a screenshot request completes on
the UI thread; a follow-up inspection confirms that the window accepts control requests. Cold
means an empty app profile, not a flushed operating-system file cache. Task journeys use
`wall_time: "process"`, so their primary time is measured outside the process through exit.

| App | Typical payload | Tasks |
| --- | --- | --- |
| PhotoCraft | `quote-card-misty-beach.psd`, 5,919,438 bytes; 1000×1000, 4 layers | open, Gaussian Blur, save PSD |
| PdfCraft | IRS 2023 Form 990, 800,253 bytes; 12 pages, 1,075 fields | open, edit a form field, save edited PDF |
| GridCraft | 2024 AIES estimates workbook, 14,050 bytes; plus MIT Monthly Budget Tracker, 346,412 bytes, 8 sheets and 25,524 formulas | AIES: open, edit A3, save; budget: open, edit/recalc, scroll, save |
| CADCraft | State Open Band DWG, 7,777,818 bytes; about 22k entities | open, edit entity color, save DWG |
| WordCraft | Autism Commission 2019 DOCX, 302,427 bytes; 316 paragraphs and 1 table | open, scroll, edit text, save DOCX |
| DeckCraft | MDAR Unit 3 Spanish PPTX, 8,541,624 bytes; 26 slides | open, navigate, edit title, save, export PDF |
| LightCraft | Tetons and Snake River JPEG, 1,865,607 bytes; 3,000×2,402, 7.2 MP | open, adjust exposure, save, export JPEG |

The local corpus medians are 32,738 bytes for 431 PSD files, 11,256 bytes for 993 XLSX files, and
3,312,310 bytes for six PDFs; those sets are mostly compatibility fixtures. For the PSD payload,
six layered CC0 examples from Innerscene were measured by file size: the median is 5,879,306 bytes,
and the selected quote card is 0.7% above it. The five public-domain government PDF examples in
the existing journey corpus have a median of about 800 KB, matching the selected IRS form. The
official AIES workbook is 25% above the XLSX corpus median and is a real supporting spreadsheet,
not a test case. The manifest pins source URLs, licenses and SHA-256 hashes.

The second GridCraft payload was chosen from the public formula-bearing workbooks: the MIT
Monthly Budget Tracker is a real budget workbook, not a regression fixture, and is 1.27× the
272,699-byte median of nine public NREL SAM finance-model workbooks. It has 9,290 SUMIFS formula
cells (9,582 calls), 938 COUNTIFS cells, 10 expression-based conditional-formatting ranges and
27 charts. The selected corpus was audited across 1,025 spreadsheet packages; 353 contained
worksheet formulas. The workbook therefore reaches the SUMIFS/COUNTIFS path (#22) and formula
conditional formatting (#114), while still representing ordinary budget-model work.

Startup journeys launch the real desktop app and stop at its first PNG frame, followed by a
successful UI control request. The open/edit/save journeys use one-shot adapters over each app's
real engine API; their primary duration is measured externally from process launch through exit.
This keeps the file and operation realistic while making the task repeatable on both runners.

The app-specific real-input adapters are part of the speedcraft-labs fork changes. `app_base_patch`
applies the additive adapter code only in the temporary upstream checkout used by `prepare` or
`compare`; it never changes or pushes to an upstream repository.

When an app pins different craft-libs commits per crate, set `app_locked_dependencies = true` on its
journeys and pass `app-locked` for both `--base` and `--head`. The build then uses each app revision's
own Cargo.lock instead of replacing all of its craft-libs dependencies with one shared revision.
Reports still record both app commit SHAs and mark the dependency mode as `craft-libs:app-locked`.

## Real-world CADCraft

The real-world catalog includes cold and warm desktop startup, opening a typical drawing, changing
one entity's color, and saving the edited drawing with semantic output verification. The startup
probe stops when the UI thread returns its first PNG frame and answers a follow-up control request.
Task wall time is measured outside the one-shot adapter process.

CADCraft uses the 7,777,818-byte State Open Band DWG, with 22k entities. It is the byte-size median
among seven real drawings in the local corpus (1,790,450; 3,142,134; 3,807,987; 7,777,818;
10,525,851; 39,931,761; and 47,844,432 bytes). The largest sample is a 985k-entity engineering
drawing and is not the representative payload. The selected and two other public SDDOT DWGs are
pinned in crates/corpus/manifests/cadcraft-real-drawings.toml; source-page terms do not explicitly
grant redistribution.

On the Agentbox, CADCraft startup needs a GPU-backed X11 display because its default Vulkan window
path cannot start on the GLX-disabled Xvfb server. Start the Agentbox's RTX-backed Xorg server once
before benchmarking, set DISPLAY for craft-journeys (for example DISPLAY=:116), and keep that server
outside the timed app process. On Mac, the native desktop display is used.

## Real-world WordCraft

The WordCraft extension measures cold and warm startup to the first interactive frame, then opens,
scrolls, edits text in, and saves one real DOCX. Its Massachusetts Autism Commission 2019 annual report
is 302,427 bytes, with 316 paragraphs, one table and 35,689 text characters. The [official report
page](https://www.mass.gov/lists/autism-commission-reports) lists seven DOCX annual reports sized
56.48, 61.46, 79.43, 295.34, 369.91, 9,830 and 9,830 KB. The selected report is the median by
published size (295.34 KB). The source does not state
redistribution terms, so the corpus entry is fetched on demand and marked non-redistributable. See
`crates/corpus/manifests/real-world-app-2026.toml`.

WordCraft startup uses its localhost control channel with a per-profile key. The open, scroll, edit and
save adapters run one `perf_probe --task` action per process; the external process clock covers launch,
document load, the action, and exit. Adapter parity for upstream `storytold/wordcraft@main` is provided
by an `app_base_patch` applied only in the temporary upstream checkout. WordCraft pins different
craft-libs revisions per crate, so its journeys use app-locked dependencies on both revisions.

## Real-world DeckCraft

The DeckCraft extension measures cold and warm startup to the first interactive frame, then opens a
presentation, navigates to a slide, edits its title text, saves the edited PPTX and exports a PDF.
Task wall time is measured outside the one-shot CLI process; startup is measured by the desktop
control driver through a returned screenshot and a successful UI inspection.

The payload is the 8,541,624-byte Unit 3 Spanish Language Course presentation from the official
[Massachusetts MDAR course page](https://www.mass.gov/lists/mdar-spanish-language-course). The page
lists six course presentations sized 9.93, 6.90, 8.15, 29.6, 6.60 and 7.81 MB; their byte-size
median is 7.98 MB. Unit 3 at 8.15 MB is the nearest listed file. It has 26 slides at 960×540 pt and
contains 4,140,408 bytes of embedded media. The source does not state redistribution terms, so the
corpus entry is fetched on demand and marked non-redistributable.

## Real-world LightCraft

The LightCraft extension measures cold and warm startup through the first rendered photo frame,
then opens a photo, adjusts exposure, saves the edit and exports a JPEG. The desktop app's localhost
control channel drives the actions; task wall time is measured by the outer journey runner from
adapter launch through app exit. Save is reopened and its rendered preview is checked outside the
timed process.

The payload is Ansel Adams' *The Tetons and the Snake River*, a 3,000 × 2,402, 1,865,607-byte JPEG.
It is selected from the four public-domain images LightCraft uses in its own showcase. Their sorted
sizes are 311,263, 1,865,607, 5,835,684 and 6,511,067 bytes; the byte-size median is 3,850,645.5
bytes. The selected image is the lower of the two central files and is a manageable 7.2 MP photo.
The companion NASA and Library of Congress images and all provenance are pinned in
`crates/corpus/manifests/lightcraft-showcase-2026.toml`; no regression fixture is used.
LightCraft's upstream and fork main pin different craft-libs revisions per crate, so each build
uses the Cargo.lock from its own app checkout.

Every task opens the source photo in a fresh one-shot app, so wall time includes launch and import.
Open, edit and save render a 1024-pixel preview; edit checks exposure at +0.7, and save reopens the
library to verify the edit persisted. Export verifies a JPEG with a 2048-pixel long edge. The
upstream and fork GPU paths produce non-identical pixels, so the output gate checks the requested
photo/edit state and valid rendered output instead of requiring identical encoded bytes. Across the
retained Agentbox renders, previews differed by at most one 8-bit RGB code value (alpha matched);
the 2048 × 1640 JPEGs differed by at most 11, with mean absolute channel error below 0.5.


### LightCraft session latency (hyper #291)

`craft-journeys session --config session.json --out REPORT_DIRECTORY` runs one
prebuilt revision/session per acquisition when `side` is set; otherwise one pair.
Binaries must be built before locking. Use at most one bounded primary AB/BA
pair per lease, resetting the owned display for each build. If a pair will not
fit, select one build per lease and use that same declared AB/BA cadence for
both A/A and the real comparison. `acquisition_sides` may select
point/main first and descriptive upstream in later single-session acquisitions;
`side` and `acquisition_sides` change acquisition selection, not the expected
complete comparison or workload. Use Python 3 with Pillow XCB, `xwininfo`,
`xprop`, and an NVIDIA Xorg display large enough for the 1600×1000 app window.
Existing launch-per-task journeys are unchanged.

Config fields: `revisions` (`point`, `main`, optional `upstream`, each with absolute
`binary` and pinned `revision`); `sides`; one `payloads` tier/folder; `sessions`
(at least 10); `pair` (zero-based); optional `side`; `warmups`, `repetitions`,
`exposure_steps` and `measurement_method`. The recorded typical protocol uses
20 pairs, two warmups, four repetitions, four exposure steps and
`measurement_method: "first-grid-quickack-fixed-gpu-v5"`, with the explicit GPU
condition below. These settings do not guarantee 5% sensitivity. Continue with
`resume_report` pointing to the preceding acquisition's report. Workloads and
binary hashes must match. Every acquisition retains its CPU guard and fingerprint;
incomplete or contaminated reports cannot be published. Reverse ABC/CBA or AB/BA
order on alternate pairs; release both locks between bounded acquisitions.

On Agentbox, use `WGPU_BACKEND=vulkan`, an owned NVIDIA Xorg display reset for
each build, and a shared explicit NVIDIA shader-cache path under this ticket's
one target directory. GPU initialization
finishes before actions. Shader and OS caches are never flushed: **cold means
first timed use after the documented setup within a fresh app/session**, not cold hardware or a cold disk.

Take `bench.lock`, then exclusive `gpu.lock`, then invoke `scripts/bench-run`.
The lease controller must run **outside** the transient bench service and stop
its owned systemd unit before unlocking on timeout or cancellation. A timeout
around the `bench-run` client alone can leave that service running. The retained
ticket recipe (`sensitivity/lease.py`, `acquire-pair.py`, `acquire-display.py` in
the raw-report archive) records the unit identity, caps work at 840 seconds,
reaps that unit and its private display before releasing the locks, and defers
a second build if the preceding build predicts an overrun. A forced-expiry
check verifies that the owned service is inactive after cleanup. Completed,
guarded sides may be resumed under a declared split-acquisition protocol; an
incomplete side contributes no samples. The recorded typical campaign requires
both builds in one lease and rejects the whole interrupted pair. The heavy
protocol uses ten pairs, two warmups, two repetitions and one build per lease: a
guarded pilot took 385.8 seconds per app. Its A/A and real primary comparison
use this same alternating AB/BA cadence; the pilot is not seeded into A/A.

Do not hold a lock for more than 15 minutes. Import-heavy stress runs only when
`sudo lslocks` shows no bench waiters. A timeout is a retained failure, never a
reason to extend the lease. Reports record NVIDIA PID/name snapshots before,
every two seconds during, and after each session. Foreign GPU processes discard
the attempt. The retained admission policy has a 30-minute budget; exhausted
budgets label the entire tier provisional and prohibit publication. The outer
840-second work budget takes precedence. Other workers' GPU tests take the lock shared.

Each action waits outside timing for one second of observed empty activity/task
and render queues (new activity rows can be hidden for 0.5 s). Input-to-result
clocks start at control dispatch. The X11 observer starts **before dispatch** and
runs independently of `ui.inspect` polling. A later successful native capture
must prove the earlier displayed pixels identical; otherwise the native capture
is an explicit upper bound. Readback intervals and all candidate hashes/timestamps
are retained. This observes displayed frames, not hardware scanout. Session TCP uses NODELAY and prompt QUICKACK receives (including partial JSON)
to avoid delayed-ACK quantization from the token-streaming server. The legacy
launch-per-task transport is unchanged. A private X server shares reserved CPUs
22–27 with the app; pinning only the app leaves readback at the mercy of other
workers. Record the server affinity with every acquisition. No fixed
latency is subtracted; no outliers are trimmed. Export additionally requires
observed export completion because an unchanged photo frame cannot prove that a
file finished writing.

Import removes catalog records, preserves originals, reimports the exact file set
and ends at the first proven usable thumbnail viewport after **all** catalog
entries are present. It then visits/checks every grid page outside timing. The
user's import clock excludes scripted scrolling and pixel verification; no file
is skipped. Rejected first-grid frames are retained without resetting the clock. Preview
resets to grid/fit then opens the same photo at 100%. Switch resets to the first
photo and selects the same second photo every time. Exposure is a backpressured
held slider, with threshold-crossing setup and warm-ups; its first timed step
is not a pristine first gesture. Export uses a unique JPEG path each time.
First timed action samples are separately labeled cold; measured repeats after
warm-ups are warm. Startup/quit repeat independently with a populated library;
the first reopen/idle quit is cold, later lifecycle repetitions are warm. Empty
library startup and the legacy cold-quit diagnostic are not these rows.

Statistics use whole paired sessions as bootstrap clusters (4,000 resamples,
seed 313), never individual slider steps as independent sessions. Compute one
point/main median ratio per paired session, then exponentiate the median log
ratio; this need not equal the ratio of the displayed pooled medians. Resampling
preserves the FIXED AB/BA counts by drawing within the two order strata. Ordinary
paired and original pooled-median CIs are retained for audit. CI excluding 1
determines faster/slower only after at least ten pairs. Calibration uses
`aa: true` with two separate clean builds of **the same commit**, interleaved
exactly as the real comparison. The A/A gate requires at least 10 pairs, a 95% CI
containing 1, and relative half-width ≤5% (≤10% for import/startup), per action and
state. The MDE column estimates the detectable multiplicative change at two-sided
alpha .05 and power .80 from log CI width; it is not the CI half-width. A real
comparison supplies `aa_report`; without it unchanged rows say "sensitivity
uncalibrated". The formatter rejects "no measurable change" without an A/A MDE.
Report failed gates and achieved MDE instead of claiming 5% sensitivity.
If a calibration interval excludes 1, its comparison row is descriptive only:
the interval width cannot establish sensitivity when identical builds differ.
A wide interval containing 1 still reports its measured, larger MDE floor.

Agentbox's automatic GPU power state is an additional measurement condition:
the diagnostic run saw 300–1,350 MHz graphics clocks and 405–7,000 MHz memory
clocks. Switching duration closely tracked render time (correlation 0.996 in
the first two pairs). The controlled protocol uses
`measurement_method: "first-grid-quickack-fixed-gpu-v5"` and
`gpu_state: {"graphics_mhz": 1350, "memory_mhz": 7000, "power_mizer_mode": 1}`.
The external lease controller locks graphics clocks only while holding both
locks; each owned display selects maximum-performance mode and restores its
original mode before exit. The controller restores default graphics-clock
management before unlocking, including on lease expiry. Direct memory locking
is unsupported on this GPU even though `nvidia-smi` returns zero: check its
output and the actual clocks. The tested PowerMizer condition holds memory at
7,000 MHz instead.

The driver observes actual graphics/memory clocks outside every action and
populated-library lifecycle timer. A mismatch rejects the session; observations
remain in the raw report. Calibration must match the hardware condition and
repeat settings. These are latencies at the stated controlled GPU condition;
automatic-power diagnostics remain separate. No latency is normalized by clock
speed, and no delay is subtracted from a measurement.

The test-only `CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS` adds a real dispatch delay to
main-side switch requests. Set it to 10% of the calibrated warm switch median,
record that absolute delay and run a separate interleaved matrix. It never changes
recorded elapsed time after the fact.

Output gates stay outside timing: exact imported filenames; non-placeholder,
resident thumbnail pixels; changed photo-region pixels on every measured slider
step; JPEG versus an independent 8-bit sRGB PNG export at identical geometry
(channel MAE ≤8). Cross-revision fixed-state previews require RGB max ≤1 and exact
alpha; JPEG requires RGB max ≤16 and channel MAE ≤0.5. Upstream exceeding parity
is descriptive only. Passing frame images are pruned after their hashes and
checks are recorded; failure captures remain. Fixed-state oracle files are kept
until the paired checks finish. Raw reports/logs belong in the one ticket keep
directory, backed up at milestones with `nas-keep`, not committed here.

Payloads: `crates/corpus/manifests/lightcraft-session-2026.toml` pins immutable
URLs/SHA-256/licences. `lightcraft_session_corpus.py MANIFEST DOWNLOAD_ROOT TIERS
--out TIER_ROOT` verifies downloads and materializes hardlinks. TIER_ROOT must be
outside DOWNLOAD_ROOT (craft-corpus prunes unlisted files).

* `typical-50`: 50 distinct Sony A7C 24 MP RAWs, RawNIND v1.0 (2025-01-15),
  Benoit Brummer and Christophe De Vleeschouwer, Université catholique de Louvain,
  https://doi.org/10.14428/DVN/DEQCIM, **CC BY-SA 4.0**, not CC0. One low-ISO
  ground-truth exposure per scene, first 50 full-size `_GT_` ARWs in filename order.
* `import-1259`: 1,259 distinct **CC0-1.0** camera originals from raw.pixls.us,
  frozen repository metadata, recognized CR2/NEF/ARW/ORF/RW2/PEF/SRW/RAF formats.
  This is an engineering camera/encoding/resolution mix, not 1,262 similar shots
  from one camera. DNG conversion/JPEG wrappers and non-CC0 entries are excluded.
  No repeated bytes inflate the count: Add-in-place deduplicates by content.
  The import validates all requested names, so unsupported or skipped inputs fail.

The heavy tier approximates the photo count in upstream #367; it cannot reproduce
CF/NFS conditions or #832's 38,545-photo/~25-minute report. Existing legacy
reports and unsuccessful approaches remain in ticket 313's NAS archive.

### LightCraft in-app session timing (313b)

Set `CRAFT_JOURNEYS_INAPP_TIMING=1` for the session driver. Only session processes
receive `LIGHTCRAFT_LATENCY=1`; ordinary app launches have no recorder. Each
measured request carries `_latency: {id, action}`. Acceptance is stamped on the
UI thread before dispatch. `ui.latency.wait {id}` returns the completed record
in one deferred response; the driver does not inspect readiness while that
record is running. Subsequent state/pixel checks stay outside the app clock.
Primary action statistics use the record's `duration_ns`; `driver_duration_ns`
and the legacy capture proof retain the external upper bound for comparison.
Startup additionally has an entry-point-to-photo-frame app clock; quit remains
explicitly an external process-exit measurement.

The endpoint is **GPU work for the reflecting frame confirmed complete**, not
scanout. An egui-wgpu callback registers `on_submitted_work_done` on egui's own
command encoder. An enabled-only worker polls that device independently of UI
and TCP traffic, sleeping 100 microseconds between polls. Callback delivery is
an upper bound affected by worker scheduling; precision must be validated by
A/A, never assumed from the polling period. No screenshot, RPC completion, or
readiness-poll timestamp enters the app duration. Disabled frames return before
state inspection, clocks, shape creation, device polling or thread creation.

Import starts at confirmation, excluding review-dialog scripting. It records
first non-placeholder response and completion of all **visible** thumbnails
after the import has finished. A virtualized grid cannot present offscreen
thumbnails; exact catalog membership and every page remain checked outside
timing. Detail plus zoom100 is dispatched atomically on the UI thread for the
recorded preview request. Switch completion requires the active photo's full
render, including a pending region render at 100%. Background work at each
endpoint is retained. The existing one-second empty-queue gate, plus
`ui.latency.idle`, runs before every action; failure rejects the sample.

Prepare **every** compared app revision with the same `app_base_patch`, using
`scripts/lightcraft_session_prepare.py --repo APP --revision REV --checkout WT
--target TARGET --binary BINARY --app-base-patch
crates/journeys/patches/lightcraft-session-latency.patch` (one shell line).
This uses the existing prepare mechanism's `git apply --check`, apply, and
reverse-check protocol for each side. An incompatible patch fails loudly:
update the one common patch, verify it against all revisions, and rebuild all
sides. Never use revision-specific recorder code or merge incompatible clocks.
The helper creates fresh detached worktrees and saves SHA-256 provenance beside
each binary. Keep binaries outside hourly-pruned targets and outside NAS report
roots. Compilation happens before lock acquisition. Existing reset, cold/warm,
whole-session bootstrap, AB/BA order and output gates are retained. Calibration
and real configs must use a new matching measurement_method; older polling
A/A reports cannot calibrate in-app results.
