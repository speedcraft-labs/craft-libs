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


### LightCraft session latency (hyper #291 correction)

Run `craft-journeys session --config session.json --out REPORT_DIRECTORY`.
Install Python 3 with Pillow for pixel verification. Build all three app revisions before locking. Config keys: `revisions` with `point`,
`main`, `upstream` (each has `revision`, absolute `binary`); `payloads` maps one tier
name to an absolute RAW folder; `sessions` (10), `warmups` (2), `repetitions` (3),
`pair` (zero-based, defaults to 0). **Each invocation runs only that one pair.**
For the next pair, set `resume_report` to the previous acquisition's `report.json`
and use a new output directory. Completed sessions are retained without rerunning;
workload settings and binary hashes must match. Each previous report's SHA-256,
machine fingerprint and CPU guard are retained. Publication requires all ten
distinct pairs and passing guards from every acquisition. A report interrupted
before its CPU guard was written remains unpublishable: resume from the last
successfully completed acquisition and retain the interrupted raw directory.
The CLI exits 1 for an incomplete/unpublishable comparison even after a successful
pair; inspect `report.json` before selecting it as the next resume checkpoint.
The existing desktop driver launches once per session. Action clocks run from
control-request send to native frame capture after finished-render state; they
include polling, capture and IPC overhead, not OS input delivery or scanout.
No action includes launch or exit; the lifecycle validator rejects that mistake.
Import visits every thumbnail grid page and checks resident textures and pixels;
repeat imports remove catalog records only, keeping originals. Exposure is a held
slider with 60 backpressured moves, each verified and captured, not a 60 Hz gesture.
JPEG export is checked independently. Populated-library startup and quit have
separate clocks. Warm-ups and all samples are retained; bootstrap resamples paired
sessions, keeping slider steps in their original clusters. craft-bench's guard and
a nonempty observed GPU adapter gate publication. Headless capture fallback is retained and retried; no such image is accepted as a result frame.

Agentbox: use a private NVIDIA X display large enough for the window (for this run,
`DISPLAY=:118` at 1920×1080, `WGPU_BACKEND=vulkan`). Build in the one ticket target directory, retain reports outside
it, then run through `flock /jobs/work/speedcraft-labs/bench.lock
flock -x /jobs/work/speedcraft-labs/gpu.lock
/jobs/work/speedcraft-labs/scripts/bench-run ...`. Existing launch-per-task journeys
and their reports are unchanged.

Release both locks between pairs. Enforce the Agentbox 15-minute acquisition cap
with the timeout **inside** the locks, so queue waiting does not consume it:

```sh
flock /jobs/work/speedcraft-labs/bench.lock \
  flock -x /jobs/work/speedcraft-labs/gpu.lock \
  timeout --signal=TERM --kill-after=5s 895s \
  /jobs/work/speedcraft-labs/scripts/bench-run \
  craft-journeys session --config pair-0.json --out reports/pair-0
# Release, then prepare pair-1.json with pair=1 and resume_report pointing above.
```

Measure the typical tens-of-photos library first. The 500-photo matrix is optional
stress work, only when `sudo lslocks` shows no waiters for `bench.lock`; inspect
the queue again before every acquisition. Do not launch a multi-pair command
under either lock. Background preparation can make a stress pair exceed the cap;
retain that interrupted acquisition and defer it rather than extending the lease.
The hard cap takes precedence over the driver's longer GPU-admission/drain limits.

Payload acquisition is pinned in `crates/corpus/manifests/lightcraft-session-2026.toml`.
Fetch it with craft-corpus, then materialize hard-linked tier folders:

```sh
craft-corpus fetch crates/corpus/manifests/lightcraft-session-2026.toml "$ARTCRAFT_CORPUS/lightcraft-session-2026"
python3 crates/journeys/scripts/lightcraft_session_corpus.py \
  crates/corpus/manifests/lightcraft-session-2026.toml \
  "$ARTCRAFT_CORPUS/lightcraft-session-2026" \
  crates/journeys/fixtures/lightcraft-session-tiers.json \
  --out "$ARTCRAFT_CORPUS/lightcraft-session-tiers-2026"
```

`typical-50` contains 50 distinct Sony ILCE-7C (A7C) RAWs at 6000×4000 (24 MP),
one low-ISO ground-truth exposure per scene from the [Raw Natural Image Noise
Dataset](https://doi.org/10.14428/DVN/DEQCIM), version 1.0 (2025-01-15), by Benoit
Brummer and Christophe De Vleeschouwer, Université catholique de Louvain. The
Dataverse metadata explicitly licenses the dataset [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
including commercial use, with attribution and ShareAlike for adapted material.
That license also applies to derived photographic outputs; it does not change the
software's license. The manifest pins each immutable Dataverse file URL and SHA-256.
The selection takes the first 50 distinct scenes in filename order among full-size
45–55 MB ARWs with `_GT_` in the name; every downloaded EXIF identifies ILCE-7C and
6000×4000, and all 50 SHA-256 values differ. These real low-ISO scenes include
household objects, textures and plants; they are not a measured user percentile.

`typical-31` remains as the **abandoned, undersized pilot**: 31 distinct Sony A7 III
RAWs, including photographer DNG conversions (28 Signature Edits plus three
raw.pixls.us). Further Signature Edits galleries returned a CAPTCHA. The pilot
was stopped after its first complete three-revision block once the 50-file source
was validated; no photo is duplicated or relabeled to inflate its size.
`heavy-500` contains 470 CC0 raw.pixls.us files plus 30 Signature Edits RAWs, with
active-sensor sizes in the 23–46 MP window (nominally 24–45 MP). It includes camera
compression/crop variants and is an engineering workload, not a measured user
population percentile. The manifest excludes entries licensed BY-NC-SA and samples
attributed to Adobe DNG Converter. DNGs contributed by photographers remain eligible;
DNG wrappers identifying their source as JPEG/TIFF are excluded. RAW decoding may
still be unsupported in an app revision; that is a reported failure, never silently
replaced by synthetic files or a smaller payload.

[raw.pixls.us](https://raw.pixls.us/) records each selected entry as CC0-1.0; its
repository also has non-CC0 entries, which are **not** selected. Signature Edits'
[free RAW license](https://www.signatureedits.com/free-raw-license-terms/) permits
use, modification and distribution including commercial use, with restrictions on
competing photo-sharing services. The manifest records per-file URLs, SHA-256 and
provenance; no RAW media is committed. Tier membership is explicit in the JSON
fixture. Selection provenance and download logs belong with the raw reports.

The actions are motivated by upstream issues #3786 (320 CR2s from CF, thumbnails),
#1372 (high-quality previews), #1709 (exposure/preview lag), #3767 (22,763-photo NAS
startup lens scan) and #1011 (57,947-photo sidebar). These local-SSD, smaller-library
tiers do not reproduce CF/NFS storage, a 22k-photo scan or a 58k-photo sidebar.
Preview opens 100% zoom with automatic source quality. Exposure remains a global
slider exercise, not a mask correctness test for #1709. There is no blended score.
The fixed +0.7 oracle outside timing requires at most one RGB code of difference
and identical alpha between revisions, the bound declared before collection.

The initial heavy tier's scanner returned 494 candidates from 500 files: ARQ,
GPR and STI extensions were ignored. Those six source pins and the rejection
reason are retained in `fixtures/lightcraft-session-excluded.json`; six other
licensed RAWs replace them before collecting comparisons. Tier folders live
**outside** the stamped download root because craft-corpus prunes unlisted files.

Session profiles pin their app via a private `CRAFT_VERSIONS_FILE`, suppressing
asynchronous update prompts/network checks. Optional lens-profile onboarding is
dismissed before timing; no lens database is downloaded. A slider gesture crosses
egui's drag threshold before two warm-up moves and 60 measured moves. Each session
in the initial matrix uses one measured import/preview/switch/export after two
warm-ups; the ten sessions supply ten independent observations per side. Linux
pidfd readiness observes quit without Popen's 50 ms timeout-poll quantization.
JPEGs must reproduce a separate 2048px render of the same photo/settings within
lossy MAE 8; cross-revision JPEG differences must stay within RGB max 16/MAE 0.5.
These output gates are outside every action clock and declared before the matrix.


For Agentbox, use a private NVIDIA Xorg display at 1920×1080 (the 1600×1000 app
window must fit entirely on screen). `session_frame` samples the **actual visible
X11 window belonging to the app PID**, via Pillow XCB readback, every 5 ms while
the existing native control screenshot is pending. It uses the first candidate
whose complete RGB pixels hash identically to that later native PNG. All candidate
timestamps/hashes and the reference PNG are retained. This verifies that the
*earlier displayed frame* already showed the result, instead of including the
screenshot API's mandatory 120 ms / three-frame settle delay. The validator rejects
an early timestamp without a matching pixel proof. No delay is subtracted.

If no earlier candidate matches exactly (or X11 capture is unavailable/occluded),
the sample explicitly falls back to the later native-capture **upper bound**.
The method and verification timestamp are recorded per sample. These are sampled
input-to-result-frame observations, including readback/IPC/polling overhead, not
hardware scanout timestamps. Prerequisites are Pillow with XCB, `xwininfo`, `xprop`,
and the GPU-backed X display; no OS synthetic input is sent.

GPU initialization is fully warmed before actions, with `gpu_ready_ns` recorded
separately. Runs share an explicit NVIDIA shader cache under the one ticket target,
like a returning user; its path is recorded and compiled cache contents are not
backed up. Idle quit waits for background preview preparation to finish **before**
its clock; the separate cold legacy diagnostic deliberately quits during setup.

The preview oracle gate is strict for the primary fork-point→fork-main comparison.
Current upstream's color output exceeds that bound on the Sony RAW, so its median
column is marked **descriptive only / not pixel-equivalent**, with all measured
differences retained. No upstream-relative speedup is claimed. `publishable` in
this session schema refers to the primary comparison (`publish_scope` records it).
The retained typical report's original JPEG/source-render check allowed a one-pixel
short-edge rounding mismatch, aligned before its fixed MAE 8 check. New runs use
the exact-geometry lossless export reference described below.


If the compositor capture times out and falls back to headless, that PNG and its
candidate timestamps/hashes are retained as a failed attempt. The driver retries
(up to three attempts) with the **original action clock still running**; it does
not subtract any assumed delay. A successful native PNG can verify an earlier
real X11 frame sampled during **any** attempt; the earliest exact RGB match
supplies the endpoint. Without a matching X11 frame, the successful native
capture completion supplies the explicit upper bound. Three failures reject the session. The first 31-file pilot exposed
three such upstream timeouts and was rejected by the earlier fail-on-any-fallback
policy; its report/logs remain retained. The replacement matrix uses this explicit
retry policy for all three revisions, declared before collection.

A rejected first block of the 50-file matrix exposed why retry candidates must be
combined: a fork-main exposure request took 6315.13 ms through capture retry, but
an earlier X11 frame matched the successful native PNG 5571.34 ms before that
endpoint (input-to-proven-frame 743.79 ms). That block was stopped and retained;
the final matrix uses the earliest exact pixel proof across all attempts for every
revision. Tests cover both this case and the conservative no-match upper bound.


GPU isolation is mandatory on Agentbox: acquire `bench.lock`, then **exclusive**
`gpu.lock`, then invoke `bench-run`. Other GPU tests take the GPU lock shared.
Before launch and after the populated-library startup process has exited, every
session records the complete `nvidia-smi --query-compute-apps=pid,name --format=csv`
result with a monotonic timestamp. A watcher also records it every two seconds
throughout each session, including populated-library startup. Before each attempt,
a foreign process causes a 30-second admission poll. A contaminated attempt is
retained under `discarded_sessions` with process names and repeated in a fresh
directory. Waiting and discarded attempts share a 30-minute budget per requested
session. If that budget expires, the next fresh attempt proceeds and the entire
tier is labeled **provisional**, with offending process names. Remaining sessions
in that tier retain the same label. Such a report cannot pass the publication
gate; its table is explicitly a shared-GPU observation. Clean accepted attempts
alone enter the primary table; discarded attempts never enter its bootstrap.
This fallback implements the benchmark operator's explicit shared-GPU policy.
The initial GPU-sharing pilots remain excluded. The cold quit diagnostic records
the same process snapshots outside its clocks. Polling detects observed foreign
processes; a process that starts and exits entirely between polls can escape it.


Before accepting the completed matrix, the output verifier also hashes the inner
60% of the actual displayed photo rectangle in every measured exposure frame and
requires it to differ from the preceding warm-up/step frame. The slider sits
outside this region. The report retains each crop box and current/previous photo
hash; a changing control label alone cannot pass this output check. This is an
untimed verification of retained native PNGs and changes no input or frame clock.
At least one exposure warm-up supplies the initial photo frame.

The legacy cold-quit diagnostic retains nonzero process exits with `exit_code`,
`success` and `forced_termination: false`; it continues through all planned
attempts and reports the failure list. Its time-to-exit statistics include crashes
and must be read with those failure counts, rather than as graceful-quit timings.
The mature session mode still rejects an abnormal process exit. An early clean-GPU
cold diagnostic observed SIGSEGV in fork main while quitting during initialization;
that failure is retained and linked to the shutdown follow-up.


Background preparation may outlive the measured actions. In particular, upstream
can prepare all 500 library previews by default. Preserve that default work and
wait outside every action/quit/startup clock for up to 30 minutes before idle
quit, and after the populated-library startup frame before untimed cleanup.
`background_drains` retains timestamps and 30-second progress snapshots. The
progress wait neither cancels work nor contributes to a measured action; a
remaining task at the deadline rejects the attempt.


For new session exports, the untimed reference is an 8-bit sRGB PNG exported
through the same geometry/source/settings path as JPEG. Dimensions must match
exactly, and the lossy channel-MAE 8 bound remains fixed. A UI-render preview can
round the short edge differently (1366 versus 1365 at long edge 2048); stretching
it misaligns high-ISO noise and is not a valid JPEG-codec reference. The retained
typical 50 legacy report passed its original preview-based check; its method stays
explicitly identified. New validation runs immediately after the untimed PNG,
before potentially long background draining. Cross-revision bounds are unchanged.

Idle must remain observed for one second: `ui.inspect` omits activity rows younger
than 0.5 seconds, so one empty snapshot cannot establish that preparation stopped.
This settling interval is outside every measured clock.
