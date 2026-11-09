#!/usr/bin/env python3
"""Run one GridCraft UI journey against the pinned monthly budget workbook."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: gridcraft_budget_journey.py WORKBOOK ACTION", file=sys.stderr)
        return 2
    workbook, action = sys.argv[1:]
    snapshot = Path(os.environ["CARGO_TARGET_DIR"]) / "release/examples/snapshot"
    if not snapshot.is_file():
        print(f"missing GridCraft snapshot binary: {snapshot}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gridcraft-budget-journey-") as tmp:
        root = Path(tmp)
        png = root / "screen.png"
        args = [str(snapshot), "--in", workbook, "--size", "1440x900", "--scale", "1"]
        saved = None
        if action == "open":
            commands = [("edit.goTo", {"reference": "Dashboard!A1"})]
        elif action == "edit-recalc":
            commands = [
                ("edit.goTo", {"reference": "Entries!E779"}),
                ("cell.set", {"cell": "E779", "input": "99.99"}),
                ("edit.goTo", {"reference": "Monthly Summary!A2"}),
            ]
        elif action == "scroll":
            commands = [("edit.goTo", {"reference": "Entries!A779"})]
        elif action == "save":
            saved = root / "saved.xlsx"
            commands = [
                ("edit.goTo", {"reference": "Dashboard!A1"}),
                ("file.saveAs", {"path": str(saved)}),
            ]
        else:
            print(f"unknown GridCraft journey action: {action}", file=sys.stderr)
            return 2
        for command, params in commands:
            args.extend(("--cmd", f"{command}={json.dumps(params, separators=(',', ':'))}"))
        args.append(str(png))

        started = time.monotonic_ns()
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        elapsed = time.monotonic_ns() - started
        if result.returncode:
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        if not png.is_file():
            print("GridCraft snapshot completed without a PNG", file=sys.stderr)
            return 1
        identity = hashlib.sha256(png.read_bytes())
        if saved is not None:
            if not saved.is_file():
                print("GridCraft save journey completed without an XLSX", file=sys.stderr)
                return 1
            identity.update(saved.read_bytes())
        print(f"CRAFT_JOURNEY_NS={elapsed}")
        print(f"CRAFT_OUTPUT_SHA256={identity.hexdigest()}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
