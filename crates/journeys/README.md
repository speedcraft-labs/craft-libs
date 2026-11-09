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
| `wordcraft.open-office-docx` | WordCraft | Open the pinned synthetic 1,096-page DOCX and measure from file open through the first painted page |
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
cargo run --release -p craft-journeys -- compare --base BASE_LIBS_REV --head HEAD_LIBS_REV --journey wordcraft.open-office-docx --out baselines/wordcraft-open.json
cargo run --release -p craft-journeys -- prepare --base BASE_LIBS_REV --head HEAD_LIBS_REV --journey wordcraft.open-office-docx
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

The first end-to-end set covers PhotoCraft, PdfCraft and GridCraft. Each app has fresh-profile
(`startup-cold-first-frame`) and primed-profile (`startup-warm-first-frame`) starts. Startup timing
comes from the external Python driver, from process launch until a screenshot request completes on
the UI thread; a follow-up inspection confirms that the window accepts control requests. Cold
means an empty app profile, not a flushed operating-system file cache. Task journeys use
`wall_time: "process"`, so their primary time is measured outside the process through exit.

| App | Typical payload | Tasks |
| --- | --- | --- |
| PhotoCraft | `quote-card-misty-beach.psd`, 5,919,438 bytes; 1000×1000, 4 layers | open, Gaussian Blur, save PSD |
| PdfCraft | IRS 2023 Form 990, 800,253 bytes; 12 pages, 1,075 fields | open, edit a form field, save edited PDF |
| GridCraft | 2024 AIES estimates workbook, 14,050 bytes; 1 sheet, 62 rows, 485 stored cells | open, edit A3, save XLSX |

The local corpus medians are 32,738 bytes for 431 PSD files, 11,256 bytes for 993 XLSX files, and
3,312,310 bytes for six PDFs; those sets are mostly compatibility fixtures. For the PSD payload,
six layered CC0 examples from Innerscene were measured by file size: the median is 5,879,306 bytes,
and the selected quote card is 0.7% above it. The five public-domain government PDF examples in
the existing journey corpus have a median of about 800 KB, matching the selected IRS form. The
official AIES workbook is 25% above the XLSX corpus median and is a real supporting spreadsheet,
not a test case. The manifest pins source URLs, licenses and SHA-256 hashes.

Startup journeys launch the real desktop app and stop at its first PNG frame, followed by a
successful UI control request. The open/edit/save journeys use one-shot adapters over each app's
real engine API; their primary duration is measured externally from process launch through exit.
This keeps the file and operation realistic while making the task repeatable on both runners.

The app-specific real-input adapters are part of the speedcraft-labs fork changes. `app_base_patch`
applies the additive adapter code only in the temporary upstream checkout used by `prepare` or
`compare`; it never changes or pushes to an upstream repository.

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
