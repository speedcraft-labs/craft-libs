#!/usr/bin/env python3
"""Run one DeckCraft command against a typical public presentation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


EDIT_MARKER = " [benchmark edit]"
SLIDE_INDEX = 12


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def run(binary: Path, input_path: Path, commands: list[tuple[str, object]], save: Path | None = None, export: Path | None = None) -> tuple[int, dict]:
    args = [str(binary), "run", "--in", str(input_path)]
    for command, params in commands:
        if params is None:
            args.extend(["--cmd", command])
        else:
            encoded = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
            args.extend(["--cmd", f"{command}={encoded}"])
    if save is not None:
        args.extend(["--save", str(save)])
    if export is not None:
        args.extend(["--export", str(export)])
    args.append("--print")

    started = time.perf_counter_ns()
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter_ns() - started
    if result.returncode:
        raise RuntimeError(f"deckcraft-cli failed ({result.returncode}): {result.stderr.strip()}")

    outputs = []
    for line in result.stdout.splitlines():
        if "→" not in line:
            continue
        _, encoded = line.split("→", 1)
        outputs.append(json.loads(encoded.strip()))
    if not outputs:
        raise RuntimeError(f"deckcraft-cli returned no command output: {result.stdout.strip()}")
    return elapsed, outputs[-1]


def inspect(binary: Path, path: Path) -> dict:
    _, state = run(binary, path, [("slide.go", {"index": SLIDE_INDEX}), ("slide.inspect", None)])
    return state


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: deckcraft_real_app.py BINARY TASK INPUT [OUTPUT]", file=sys.stderr)
        return 2
    binary = Path(sys.argv[1]).resolve()
    task = sys.argv[2]
    input_path = Path(sys.argv[3]).resolve() if len(sys.argv) >= 4 else None
    output_path = Path(sys.argv[4]).resolve() if len(sys.argv) >= 5 else None
    try:
        if task == "verify":
            if input_path is None:
                raise RuntimeError("verify needs the saved presentation path")
            state = inspect(binary, input_path)
            if state.get("index") != SLIDE_INDEX or not any(EDIT_MARKER in shape.get("text", "") for shape in state.get("shapes", [])):
                raise RuntimeError("saved PPTX is missing the edited slide title")
            print(f"CRAFT_OUTPUT_SHA256={digest(state)}")
            return 0

        if input_path is None:
            raise RuntimeError("task needs an input presentation")
        if task == "open":
            elapsed, state = run(binary, input_path, [("file.info", None)])
            identity = {"title": state.get("title"), "slides": state.get("slides"), "format": state.get("format")}
        elif task == "navigate":
            elapsed, state = run(binary, input_path, [("slide.go", {"index": SLIDE_INDEX}), ("slide.inspect", None)])
            identity = state
        elif task in {"edit", "save"}:
            output = output_path if task == "save" else None
            if task == "save" and output is None:
                raise RuntimeError("save needs an output path")
            commands = [
                ("slide.go", {"index": SLIDE_INDEX}),
                ("text.edit", {"id": 655, "end": True}),
                ("text.insert", {"text": EDIT_MARKER}),
                ("slide.inspect", None),
            ]
            elapsed, state = run(binary, input_path, commands, save=output)
            if not any(EDIT_MARKER in shape.get("text", "") for shape in state.get("shapes", [])):
                raise RuntimeError("text edit did not appear in the slide inspection")
            identity = state
        elif task == "export":
            if output_path is None:
                raise RuntimeError("export needs an output path")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            elapsed, state = run(binary, input_path, [("file.export", {"path": str(output_path), "format": "pdf", "all": True})])
            content = output_path.read_bytes()
            if not content.startswith(b"%PDF-") or len(content) < 1024:
                raise RuntimeError("PDF export is missing or too small")
            identity = {"export": hashlib.sha256(content).hexdigest(), "pages": 26}
        else:
            raise RuntimeError(f"unknown task {task!r}")

        print(f"CRAFT_JOURNEY_NS={elapsed}")
        print(f"CRAFT_OUTPUT_SHA256={digest(identity)}")
        return 0
    except Exception as error:
        print(f"DeckCraft {task} failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
