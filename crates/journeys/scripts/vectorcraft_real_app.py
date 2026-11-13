#!/usr/bin/env python3
"""Measure VectorCraft's desktop workflows on a real public SVG map."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_startup import ensure_display, vectorcraft_adapter  # noqa: E402


EDIT_COLOR = "#f26d3d"


class Control:
    def __init__(self, stream):
        self.stream = stream
        self.reader = stream.makefile("r", encoding="utf-8")
        self.ident = 0

    def call(self, method: str, params: dict | None = None):
        self.ident += 1
        request = {"id": self.ident, "method": method, "params": params or {}}
        self.stream.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        line = self.reader.readline()
        if not line:
            raise RuntimeError(f"VectorCraft control closed during {method}")
        reply = json.loads(line)
        if reply.get("id") != self.ident:
            raise RuntimeError(f"VectorCraft control id mismatch during {method}: {reply}")
        if not reply.get("ok"):
            raise RuntimeError(f"VectorCraft {method}: {reply.get('error', 'request failed')}")
        return reply.get("result")


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def spawn(binary: Path, profile: Path):
    profile.mkdir(parents=True, exist_ok=True)
    port = free_port()
    env = os.environ.copy()
    env.update({
        "HOME": str(profile),
        "XDG_CONFIG_HOME": str(profile / ".config"),
        "XDG_DATA_HOME": str(profile / ".local/share"),
        "XDG_CACHE_HOME": str(profile / ".cache"),
        "VECTORCRAFT_CONFIG_DIR": str(profile / "vectorcraft-config"),
    })
    if sys.platform == "linux":
        env["WGPU_BACKEND"] = "vulkan"
    env.pop("VECTORCRAFT_NO_PREFS", None)
    process = subprocess.Popen(
        [str(binary), "--control", str(port), "--new-instance"],
        cwd=profile,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"VectorCraft exited during startup with status {process.returncode}")
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.25)
            sock.settimeout(max(1.0, deadline - time.monotonic()))
            control = Control(sock)
            control.call("ui.inspect")
            return process, control
        except (OSError, RuntimeError, json.JSONDecodeError):
            try:
                sock.close()
            except (UnboundLocalError, OSError):
                pass
            time.sleep(0.02)
    process.terminate()
    process.wait(timeout=5)
    raise TimeoutError("VectorCraft control channel did not become ready")


def stop(process: subprocess.Popen, control: Control) -> None:
    control.stream.close()
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def open_document(control: Control, path: Path) -> int:
    control.call("app.open", {"path": str(path)})
    result = control.call("engine.execute", {"command": "document.find", "params": {"kind": "path", "limit": 0}})
    count = result.get("total", 0) if isinstance(result, dict) else 0
    if count < 100:
        raise RuntimeError(f"VectorCraft imported too few paths from {path.name}: {count}")
    return int(count)


def wait_for_canvas(control: Control, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = control.call("ui.inspect")
        rect = state.get("canvasRect") if isinstance(state, dict) else None
        view = state.get("view") if isinstance(state, dict) else None
        if (
            isinstance(rect, list)
            and len(rect) >= 4
            and all(isinstance(value, (int, float)) for value in rect[:4])
            and rect[2] > 0
            and rect[3] > 0
            and view is not None
        ):
            return state
        time.sleep(0.02)
    raise TimeoutError("VectorCraft canvas did not become ready")


def selected_path(control: Control) -> tuple[int, dict]:
    result = control.call("engine.execute", {
        "command": "document.find",
        "params": {"kind": "path", "limit": 250},
    })
    matches = result.get("matches", []) if isinstance(result, dict) else []
    if not matches:
        raise RuntimeError(f"VectorCraft could not find a path for the edit: {result}")
    ids = [int(item["id"]) for item in matches]
    inspect = control.call("document.inspect", {"ids": ids})
    nodes = inspect.get("nodes", []) if isinstance(inspect, dict) else []
    candidate = next(
        (node for node in nodes if node.get("closed") and node.get("fill") not in (None, "", "none")),
        None,
    )
    if candidate is None:
        raise RuntimeError(f"VectorCraft did not find a filled closed path in the first {len(nodes)} SVG paths")
    node_id = int(candidate["id"])
    selection = control.call("engine.execute", {
        "command": "select.set",
        "params": {"ids": [node_id]},
    })
    if not isinstance(selection, dict) or selection.get("count") != 1:
        raise RuntimeError(f"VectorCraft could not select one filled path for the edit: {selection}")
    return node_id, candidate


def edit_fill(control: Control) -> dict:
    node_id, _ = selected_path(control)
    control.call("engine.execute", {"command": "paint.setFill", "params": {"color": EDIT_COLOR}})
    inspect = control.call("document.inspect", {"ids": [node_id]})
    nodes = inspect.get("nodes", []) if isinstance(inspect, dict) else []
    if not nodes or nodes[0].get("fill", "").lower() != EDIT_COLOR:
        raise RuntimeError(f"VectorCraft fill edit did not stick: {nodes[:1]}")
    return nodes[0]


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or not header.startswith(b"\x89PNG\r\n\x1a\n") or header[12:16] != b"IHDR":
        raise RuntimeError("VectorCraft export is not a valid PNG")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def export_png(control: Control, output: Path) -> tuple[int, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    control.call("app.export", {"path": str(output), "format": "png", "scale": 1.0, "wait": True})
    if not output.is_file() or output.stat().st_size < 1024:
        raise RuntimeError("VectorCraft did not write a usable PNG export")
    size = png_size(output)
    if size[0] < 100 or size[1] < 100:
        raise RuntimeError(f"VectorCraft export has unexpected dimensions: {size}")
    return size


def run_task(binary: Path, task: str, input_path: Path, target_dir: Path) -> int:
    start = time.perf_counter_ns()
    state_dir = target_dir / "vectorcraft-real-world-task"
    shutil.rmtree(state_dir, ignore_errors=True)
    profile = state_dir / "profile"
    process, control = spawn(binary, profile)
    source_hash = file_digest(input_path)
    action_elapsed = None
    try:
        path_count = open_document(control, input_path)
        identity = {"source": source_hash, "task": task}
        if task == "open":
            identity["paths"] = path_count
            action_elapsed = time.perf_counter_ns() - start
        elif task == "zoom":
            before = wait_for_canvas(control)
            before_view = before.get("view")
            control.call("engine.execute", {"command": "view.zoomIn", "params": {}})
            changed = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                after = control.call("ui.inspect")
                if after.get("view") != before_view:
                    changed = True
                    break
                time.sleep(0.02)
            if not changed:
                raise RuntimeError("VectorCraft canvas zoom did not change the view")
            action_elapsed = time.perf_counter_ns() - start
            identity["zoom"] = "zoom-in"
        elif task in {"edit", "save"}:
            node = edit_fill(control)
            identity.update({"fill": EDIT_COLOR, "paths": path_count})
            if task == "edit":
                action_elapsed = time.perf_counter_ns() - start
            else:
                output = target_dir / "outputs" / f"{input_path.stem}-saved.svg"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.unlink(missing_ok=True)
                control.call("app.save", {"path": str(output), "format": "svg", "wait": True})
                if not output.is_file() or output.stat().st_size < 1024 or b"<svg" not in output.read_bytes()[:4096]:
                    raise RuntimeError("VectorCraft did not save an SVG document")
                identity["saved"] = "valid-svg"
                action_elapsed = time.perf_counter_ns() - start
        elif task == "export":
            output = target_dir / "outputs" / f"{input_path.stem}.png"
            width, height = export_png(control, output)
            identity.update({"format": "png", "width": width, "height": height})
            action_elapsed = time.perf_counter_ns() - start
        else:
            raise ValueError(f"unknown VectorCraft task {task!r}")
    finally:
        stop(process, control)
    elapsed = action_elapsed or (time.perf_counter_ns() - start)
    adapter = vectorcraft_adapter(profile)
    if not adapter:
        raise RuntimeError("VectorCraft did not log its selected graphics adapter")
    print(f"CRAFT_GPU_ADAPTER={adapter}")
    print(f"CRAFT_JOURNEY_NS={elapsed}")
    print(f"CRAFT_OUTPUT_SHA256={digest(identity)}")
    return 0


def verify_save(binary: Path, saved_path: Path, source_path: Path) -> int:
    process, control = spawn(binary, saved_path.parent / "verify-profile")
    try:
        count = open_document(control, saved_path)
        _, node = selected_path(control)
        if node.get("fill", "").lower() != EDIT_COLOR:
            raise RuntimeError(f"saved SVG did not preserve edited fill: {node.get('fill')!r}")
        if count < 100:
            raise RuntimeError("saved SVG lost most of its paths")
        identity = digest({"source": file_digest(source_path), "task": "save", "fill": EDIT_COLOR, "paths": count, "saved": "valid-svg"})
        print(f"CRAFT_OUTPUT_SHA256={identity}")
        return 0
    finally:
        stop(process, control)


def verify_export(input_path: Path, output: Path) -> int:
    width, height = png_size(output)
    if width < 100 or height < 100 or output.stat().st_size < 1024:
        raise RuntimeError("VectorCraft PNG export is invalid")
    print(f"CRAFT_OUTPUT_SHA256={digest({'source': file_digest(input_path), 'task': 'export', 'format': 'png', 'width': width, 'height': height})}")
    return 0


def verify_action(binary: Path, task: str, input_path: Path, target_dir: Path) -> int:
    state_dir = target_dir / "vectorcraft-real-world-verify" / task
    shutil.rmtree(state_dir, ignore_errors=True)
    process, control = spawn(binary, state_dir / "profile")
    try:
        count = open_document(control, input_path)
        identity = {"source": file_digest(input_path), "task": task}
        if task == "edit":
            edit_fill(control)
            identity.update({"fill": EDIT_COLOR, "paths": count})
        elif task == "zoom":
            before = wait_for_canvas(control)
            control.call("engine.execute", {"command": "view.zoomIn", "params": {}})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                after = control.call("ui.inspect")
                if after.get("view") != before.get("view"):
                    break
                time.sleep(0.02)
            else:
                raise RuntimeError("VectorCraft zoom verification did not change the view")
            identity["zoom"] = "zoom-in"
        else:
            identity["paths"] = count
        print(f"CRAFT_OUTPUT_SHA256={digest(identity)}")
        return 0
    finally:
        stop(process, control)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: vectorcraft_real_app.py BINARY TASK INPUT [OUTPUT]", file=sys.stderr)
        return 2
    binary = Path(sys.argv[1]).resolve()
    task = sys.argv[2]
    input_path = Path(sys.argv[3]).resolve() if len(sys.argv) >= 4 else None
    output_path = Path(sys.argv[4]).resolve() if len(sys.argv) >= 5 else None
    try:
        display = ensure_display()
        if task == "verify-save":
            if input_path is None or output_path is None:
                raise RuntimeError("verify-save requires the original and saved SVG paths")
            return verify_save(binary, output_path, input_path)
        if task == "verify-export":
            if input_path is None or output_path is None:
                raise RuntimeError("verify-export requires the source and PNG paths")
            return verify_export(input_path, output_path)
        if task.startswith("verify-"):
            if input_path is None:
                raise RuntimeError(f"{task} requires an input SVG")
            return verify_action(binary, task.removeprefix("verify-"), input_path, Path(os.environ["CARGO_TARGET_DIR"]))
        if input_path is None:
            raise RuntimeError("task requires an input SVG")
        return run_task(binary, task, input_path, Path(os.environ["CARGO_TARGET_DIR"]))
    except Exception as error:
        print(f"VectorCraft {task} failed: {error}", file=sys.stderr)
        return 1
    finally:
        if "display" in locals() and display is not None:
            display.terminate()
            display.wait(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
