#!/usr/bin/env python3
"""Create a deterministic four-page editorial layout for the DesignCraft journey."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    binary, output = Path(sys.argv[1]), Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        {
            "command": "file.new",
            "params": {
                "title": "Neighborhood Arts Festival Program",
                "pages": 4,
                "facingPages": False,
                "columns": 3,
                "gutter": 14,
                "margins": 36,
            },
        }
    ]
    # Four 612×792 point pages, each with a restrained 5×12 grid of story and image frames.
    # The result has 240 editable page items, representative of a dense short program.
    for spread in range(4):
        for index in range(60):
            column, row = index % 5, index // 5
            x, y = 36 + column * 108, 54 + row * 56
            rect = [x, y, x + 100, y + 50]
            if index % 3 == 0:
                params = {"spread": spread, "rect": rect, "content": "graphic"}
            else:
                params = {
                    "spread": spread,
                    "rect": rect,
                    "content": "text",
                    "caret": False,
                    "text": f"Program {spread + 1}.{index + 1}  ·  Community Arts Festival  ·  Performances, workshops and local artists.",
                }
            steps.append({"command": "frame.create", "params": params})

    with tempfile.TemporaryDirectory(prefix="designcraft-journey-") as temp:
        script = Path(temp) / "layout.json"
        script.write_text(json.dumps(steps, ensure_ascii=False), encoding="utf-8")
        subprocess.run([str(binary), "script", str(script), "--save", str(output)], check=True, stdout=subprocess.DEVNULL)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("DesignCraft did not save the generated program")
    print(f"saved {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
