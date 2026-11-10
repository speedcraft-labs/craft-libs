#!/usr/bin/env python3
"""Open, select, drag and export one real FigCraft design through its headless MCP surface."""

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
                raise RuntimeError("FigCraft MCP server exited before replying")
            response = json.loads(line)
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(response["error"].get("message", str(response["error"])))
                return response["result"]

    def tool(name: str, arguments: dict) -> dict:
        response = rpc("tools/call", {"name": name, "arguments": arguments})
        if response.get("isError"):
            raise RuntimeError(response["content"][0].get("text", f"{name} failed"))
        text = next((block.get("text") for block in response.get("content", []) if block.get("type") == "text"), "{}")
        return json.loads(text)

    def visit(node: dict):
        yield node
        for child_node in node.get("children", []):
            yield from visit(child_node)

    digest = None
    select_elapsed = 0
    drag_elapsed = 0
    try:
        rpc(
            "initialize",
            {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "craft-journeys", "version": "1"}},
        )
        child.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        child.stdin.flush()
        tool("open_file", {"path": str(input_file)})

        # The 349-layer public app design has eight siblings in its Home Light content frame.
        # A second click enters that frame and selects the Featured trail instance itself.
        doc = tool("inspect_document", {"depth": 12, "fields": ["name", "type", "absoluteBounds"]})
        nodes = [n for page in doc.get("pages", []) for n in visit(page)]
        named = {n.get("name"): n for n in nodes if n.get("name")}
        featured = named.get("Featured")
        screen = named.get("Home — Light")
        if not featured or not screen:
            raise RuntimeError("FigCraft did not expose the Featured instance and Home — Light frame")
        bounds = featured.get("absoluteBounds")
        if not bounds or not all(k in bounds for k in ("x", "y", "width", "height")):
            raise RuntimeError("FigCraft did not expose absolute bounds for the Featured instance")
        node_id = featured["id"]
        screen_id = screen["id"]
        x = bounds["x"] + bounds["width"] / 2
        y = bounds["y"] + bounds["height"] / 2

        select_started = time.perf_counter_ns()
        tool("pointer", {"tool": "move", "kind": "click", "x": x, "y": y})
        result = tool("pointer", {"kind": "click", "x": x, "y": y})
        select_elapsed = time.perf_counter_ns() - select_started
        if node_id not in result.get("selection", []):
            raise RuntimeError(f"click-through did not select Featured {node_id}: {result.get('selection')}")

        drag_started = time.perf_counter_ns()
        result = tool("pointer", {"kind": "drag", "x": x, "y": y, "to": [x + 12, y + 4], "steps": 4})
        drag_elapsed = time.perf_counter_ns() - drag_started
        if node_id not in result.get("selection", []):
            raise RuntimeError(f"drag lost Featured selection {node_id}: {result.get('selection')}")

        tool("export", {"ids": [screen_id], "format": "svg", "path": str(output_file)})
        if not output_file.is_file() or output_file.stat().st_size == 0:
            raise RuntimeError("FigCraft did not write the SVG export")
        digest = hashlib.sha256(output_file.read_bytes()).hexdigest()
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
    print(f"SMART_GUIDE_DRAG_ROUNDTRIP_NS={drag_elapsed}")
    with output_file.with_suffix(".metrics.jsonl").open("a", encoding="utf-8") as metrics:
        metrics.write(json.dumps({"pointer_select_roundtrip_ns": select_elapsed, "smart_guide_drag_roundtrip_ns": drag_elapsed}) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"figcraft journey: {exc}", file=sys.stderr)
        raise SystemExit(1)
