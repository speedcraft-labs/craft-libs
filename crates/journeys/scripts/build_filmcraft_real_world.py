#!/usr/bin/env python3
"""Build the two existing headless app paths used by the FilmCraft real-media journey."""

import os
import subprocess
import sys
from pathlib import Path


repo = Path(sys.argv[1])
for package, example in (
    ("filmcraft-ui-egui", "bench"),
    ("filmcraft-engine", "bench_export"),
):
    subprocess.run(
        ["cargo", "build", "--release", "-p", package, "--example", example],
        cwd=repo,
        env=os.environ.copy(),
        check=True,
    )
