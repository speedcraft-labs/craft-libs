#!/usr/bin/env python3
"""Build the drag-preview example, restoring it in isolated upstream app worktrees."""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    app_repo = Path(sys.argv[1]).resolve()
    example = app_repo / "apps/designcraft-cli/examples/issue237_drag_preview.rs"
    if not example.exists():
        example.parent.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).with_name("issue237_drag_preview.rs")
        shutil.copyfile(source, example)
    manifest = example.parent.parent / "Cargo.toml"
    manifest_text = manifest.read_text(encoding="utf-8")
    locked = True
    if "[dev-dependencies]" not in manifest_text:
        manifest_text += (
            "\n[dev-dependencies]\n"
            "egui = { workspace = true }\n"
            'egui-wgpu = { git = "https://github.com/storytold/egui.git", rev = "6d518fc799681571963842f95b55a6b68431b15a" }\n'
            'pollster = "0.4"\n'
            'sha2 = "0.10"\n'
        )
        locked = False
    elif "egui-wgpu = { workspace = true }" in manifest_text:
        manifest_text = manifest_text.replace(
            "egui-wgpu = { workspace = true }",
            'egui-wgpu = { git = "https://github.com/storytold/egui.git", rev = "6d518fc799681571963842f95b55a6b68431b15a" }',
        )
        locked = False
    if not locked:
        manifest.write_text(manifest_text, encoding="utf-8")
    cargo_args = ["--locked"] if locked else []
    subprocess.run(["cargo", "build", "--release", *cargo_args, "-p", "designcraft-cli", "--example", "issue237_drag_preview"], cwd=app_repo, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
