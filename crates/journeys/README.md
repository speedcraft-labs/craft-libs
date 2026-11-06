# craft-journeys

`craft-journeys` connects application journey adapters to `craft-bench`. It keeps the paired
ABBA schedule, bootstrap confidence interval, machine fingerprint, output check and load guard
from that crate. The app adapter is a one-shot command configured in `journeys/catalog.json` (or
`CRAFT_JOURNEYS_CONFIG`).

Each adapter command receives `CRAFT_JOURNEY_REV`, `ARTCRAFT_CORPUS`, and these expanded
arguments: `{rev}`, `{app}`, `{input}`, `{input_name}`. The build command must build the app at
the requested craft-libs revision. The run command exercises the app's existing perf/control
channel on one pinned corpus input, then prints these lines to stdout:

```text
CRAFT_JOURNEY_NS=1234567
CRAFT_OUTPUT_SHA256=0123456789abcdef...
```

The duration is the journey channel's duration in nanoseconds. The digest is the resulting
render/document/output identity; it must not include timing fields. Errors and missing duration
markers invalidate the output check. Commands must be one-shot and leave the app's measured
operation outside process startup when the app channel reports a more precise duration.

Run and compare:

```sh
cargo run --release -p craft-journeys -- run --journey pdfcraft.scroll --out baselines/pdfcraft-scroll.json
cargo run --release -p craft-journeys -- compare --base BASE_REV --head HEAD_REV --journey pdfcraft.scroll
```

`run` pairs the current `CRAFT_JOURNEY_REV` (or `working-tree`) against itself to produce a
baseline report. `compare` builds and runs both requested revisions and prints the speed verdict.
Both commands return exit code 1 for a non-publishable report; errors return 2.
