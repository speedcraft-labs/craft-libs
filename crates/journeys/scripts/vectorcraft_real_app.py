#!/usr/bin/env python3
"""Open, select, drag and export one real SVG through VectorCraft's MCP control surface."""

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
        [str(binary), "mcp", "--headless", "--automation-read-root", str(input_file.parent), "--automation-write-root", str(output_file.parent)],
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
                raise RuntimeError("VectorCraft MCP server exited before replying")
            response = json.loads(line)
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(response["error"].get("message", str(response["error"])))
                return response["result"]

    def tool(name: str, arguments: dict) -> dict:
        response = rpc("tools/call", {"name": name, "arguments": arguments})
        if response.get("isError"):
            raise RuntimeError(response["content"][0].get("text", f"{name} failed"))
        return json.loads(response["content"][0]["text"])

    try:
        rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "craft-journeys", "version": "1"}})
        child.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        child.stdin.flush()
        tool("command_run", {"id": "document.open", "params": {"path": str(input_file)}})

        # The SVG is a public-domain map with 347 paths. Its first path is an interior region;
        # take the point from the imported path bounds so pointer input stays in document space.
        summary = tool("doc_inspect", {"kind": "Path", "limit": 1})
        nodes = summary.get("nodes", [])
        if not nodes or "bounds" not in nodes[0]:
            raise RuntimeError("VectorCraft did not expose the first imported path bounds")
        node_id = nodes[0]["id"]
        bounds = nodes[0]["bounds"]
        x = bounds["x"] + bounds["width"] / 2
        y = bounds["y"] + bounds["height"] / 2

        hit_started = time.perf_counter_ns()
        tool("pointer_gesture", {"tool": "selection", "events": [{"kind": "down", "x": x, "y": y}, {"kind": "up", "x": x, "y": y}]})
        hit_elapsed = time.perf_counter_ns() - hit_started
        selected = tool("doc_inspect", {})
        selection = selected.get("selection", {})
        ids = selection if isinstance(selection, list) else selection.get("objects", []) if isinstance(selection, dict) else []
        if node_id not in ids:
            raise RuntimeError(f"pointer at imported path bounds did not select path {node_id}: {selection}")

        tool("pointer_gesture", {"tool": "selection", "events": [
            {"kind": "down", "x": x, "y": y},
            {"kind": "drag", "x": x + 2, "y": y + 2},
            {"kind": "up", "x": x + 2, "y": y + 2},
        ]})
        tool("command_run", {"id": "document.export", "params": {"path": str(output_file), "format": "svg"}})
        if not output_file.is_file() or output_file.stat().st_size == 0:
            raise RuntimeError("VectorCraft did not write the SVG export")
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
    print(f"HIT_TEST_NS={hit_elapsed}")
    with output_file.with_suffix(".metrics.jsonl").open("a", encoding="utf-8") as metrics:
        metrics.write(json.dumps({"pointer_select_roundtrip_ns": hit_elapsed}) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"vectorcraft journey: {exc}", file=sys.stderr)
        raise SystemExit(1)
