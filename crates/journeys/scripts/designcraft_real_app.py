#!/usr/bin/env python3
"""Open, select, drag and PDF-export a typical multi-page DesignCraft document."""

import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    binary, input_file, output_file = map(Path, sys.argv[1:4])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter_ns()
    child = subprocess.Popen(
        [
            str(binary),
            "mcp",
            "--automation-read-root",
            str(input_file.parent),
            "--automation-write-root",
            str(output_file.parent),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    next_id = 0

    def rpc(method: str, params: dict) -> dict:
        nonlocal next_id
        next_id += 1
        request_id = next_id
        child.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
        child.stdin.flush()
        while True:
            line = child.stdout.readline()
            if not line:
                raise RuntimeError("DesignCraft MCP server exited before replying")
            response = json.loads(line)
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(response["error"].get("message", str(response["error"])))
                return response["result"]

    def tool(name: str, arguments: dict) -> dict:
        response = rpc("tools/call", {"name": name, "arguments": arguments})
        if response.get("isError"):
            blocks = response.get("content", [])
            raise RuntimeError(blocks[0].get("text", f"{name} failed") if blocks else f"{name} failed")
        text = next((block.get("text") for block in response.get("content", []) if block.get("type") == "text"), "{}")
        return json.loads(text)

    select_elapsed = 0
    drag_elapsed = 0
    digest = None
    try:
        rpc(
            "initialize",
            {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "craft-journeys", "version": "1"}},
        )
        child.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        child.stdin.flush()
        tool("open_document", {"path": str(input_file)})

        # Page 1's upper-left graphic frame is 100×50 pt at [36,54,136,104].
        x, y = 86.0, 79.0
        select_started = time.perf_counter_ns()
        result = tool(
            "pointer",
            {"tool": "selection", "events": [{"kind": "down", "x": x, "y": y}, {"kind": "up", "x": x, "y": y}]},
        )
        select_elapsed = time.perf_counter_ns() - select_started
        if not result.get("selection"):
            raise RuntimeError(f"selection pointer did not select the graphic frame: {result}")

        drag_started = time.perf_counter_ns()
        result = tool(
            "pointer",
            {
                "tool": "selection",
                "events": [
                    {"kind": "down", "x": x, "y": y},
                    {"kind": "drag", "x": x + 12.0, "y": y + 4.0},
                    {"kind": "up", "x": x + 12.0, "y": y + 4.0},
                ],
            },
        )
        drag_elapsed = time.perf_counter_ns() - drag_started
        if not result.get("selection"):
            raise RuntimeError(f"drag lost the selected graphic frame: {result}")

        exported = tool("execute", {"command": "file.exportPdf", "params": {}})
        pdf = base64.b64decode(exported["base64"], validate=True)
        if not pdf.startswith(b"%PDF-"):
            raise RuntimeError("DesignCraft did not return a PDF export")
        output_file.write_bytes(pdf)
        digest = hashlib.sha256(pdf).hexdigest()
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    print(f"CRAFT_JOURNEY_NS={time.perf_counter_ns() - started}")
    print(f"CRAFT_OUTPUT_SHA256={digest}")
    print(f"POINTER_SELECT_ROUNDTRIP_NS={select_elapsed}")
    print(f"DRAG_ROUNDTRIP_NS={drag_elapsed}")
    with output_file.with_suffix(".metrics.jsonl").open("a", encoding="utf-8") as metrics:
        metrics.write(json.dumps({"pointer_select_roundtrip_ns": select_elapsed, "drag_roundtrip_ns": drag_elapsed}) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"DesignCraft journey: {exc}", file=sys.stderr)
        raise SystemExit(1)
