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
jobs.
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

The PdfCraft real edit journeys use a public-domain corpus pinned in
`crates/corpus/manifests/pdfcraft-public-domain.toml`: the IRS 2025 Form 990 (1,075 widgets,
including hierarchical field names and embedded JavaScript), IRS 2025 Form 1040 (199 widgets),
and the 2023 U.S. Code Title 26 (4,211 pages). They time one PdfCraft `Session` edit after open.

PdfCraft's `pdfcraft-public-domain` journeys cover an IRS Form 990 with 1,075
hierarchical AcroForm fields, an IRS Form 1040 with 199 fields, the 4,211-page
2023 U.S. Code Title 26, and OPM's 95-page SF 85P with 4,128 hierarchical
fields and embedded XFA JavaScript.
