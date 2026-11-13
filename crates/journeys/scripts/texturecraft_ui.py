#!/usr/bin/env python3
"""One-shot TextureCraft desktop journey driven through its documented control channel."""
import base64
import hashlib
import json
import os
import platform
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from desktop_startup import ensure_display, mac_window_watch_binary


binary, project, action, output = sys.argv[1:]
if os.path.exists(output):
    shutil.rmtree(output) if os.path.isdir(output) else os.unlink(output)
port_base = 41000 + os.getpid() % 20000
port = port_base
token = "craft-journey-texturecraft-291-token"
env = os.environ.copy()
cache = tempfile.TemporaryDirectory(prefix="texturecraft-journey-cache-")
env.update(TEXTURECRAFT_NO_PREFS="1", TEXTURECRAFT_CONTROL_TOKEN=token, XDG_CACHE_HOME=cache.name)
if platform.system() == "Linux":
    env["WGPU_BACKEND"] = "vulkan"
    env["__EGL_VENDOR_LIBRARY_FILENAMES"] = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
elif platform.system() == "Darwin":
    env["WGPU_BACKEND"] = "metal"
display_process = ensure_display()
if os.environ.get("DISPLAY"):
    env["DISPLAY"] = os.environ["DISPLAY"]
proc = None
launch_index = 0
watcher = None
watcher_dir = None
watcher_pid_path = None

def launch():
    global launch_index, port
    launch_index += 1
    port = port_base + launch_index - 1
    cmd = [binary, "--control", str(port)]
    if platform.system() == "Linux" and os.environ.get("DISPLAY") is None:
        cmd = ["xvfb-run", "-a", "--server-args=-extension GLX", *cmd]
    process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if platform.system() == "Darwin" and watcher_pid_path is not None:
        watcher_pid_path.write_text(f"{process.pid}\n")
    return process

def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

def wait_for_server(process):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("TextureCraft exited before the control server started")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("TextureCraft control server did not start")

def request(method, params=None, request_id=1):
    with socket.create_connection(("127.0.0.1", port), timeout=30) as conn:
        f = conn.makefile("rwb", buffering=0)
        f.write((json.dumps({"id": 0, "method": "auth", "params": {"token": token}}) + "\n").encode())
        f.readline()
        f.write((json.dumps({"id": request_id, "method": method, "params": params or {}}) + "\n").encode())
        response = json.loads(f.readline())
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "control request failed"))
    return response.get("result")

def request_until_ready(process, method):
    deadline = time.monotonic() + 15
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("TextureCraft exited before its first frame")
        try:
            return request(method)
        except (ConnectionError, OSError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.05)
    raise RuntimeError(f"TextureCraft did not answer {method} within 15 seconds: {last_error}")

def start_map_watch(directory):
    global watcher_pid_path
    if platform.system() == "Darwin":
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        ready = directory / "mac-window-watch.ready"
        mapped = directory / "window-mapped.monotonic-ns"
        watcher_pid_path = directory / "mac-window-pid"
        ready.unlink(missing_ok=True)
        mapped.unlink(missing_ok=True)
        watcher_pid_path.unlink(missing_ok=True)
        watcher = subprocess.Popen(
            [str(mac_window_watch_binary()), str(ready), str(watcher_pid_path), str(mapped)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while not ready.is_file() and watcher.poll() is None and time.monotonic() < deadline:
            time.sleep(0.001)
        if not ready.is_file():
            watcher.terminate()
            watcher.wait(timeout=2)
            raise RuntimeError("Cocoa window observer did not attach before TextureCraft launch")
        return watcher, mapped
    if platform.system() != "Linux" or not os.environ.get("DISPLAY"):
        return None, None
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ready = directory / "x11-map-watch.ready"
    mapped = directory / "window-mapped.monotonic-ns"
    ready.unlink(missing_ok=True)
    mapped.unlink(missing_ok=True)
    watcher = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("x11_map_watch.py")), "TextureCraft", str(ready), str(mapped)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 2
    while not ready.is_file() and watcher.poll() is None and time.monotonic() < deadline:
        time.sleep(0.001)
    if not ready.is_file():
        watcher.terminate()
        watcher.wait(timeout=2)
        raise RuntimeError("X11 map observer did not attach before TextureCraft launch")
    return watcher, mapped

def wait_for_map(process, mapped):
    deadline = time.monotonic() + 60
    while not mapped.is_file() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.001)
    if not mapped.is_file():
        raise RuntimeError("TextureCraft window did not map before its startup deadline")
    return int(mapped.read_text().strip())

def screenshot_frame(process):
    result = request_until_ready(process, "ui.screenshot")
    encoded = result.get("png") if isinstance(result, dict) else None
    if not isinstance(encoded, str):
        raise RuntimeError("TextureCraft screenshot reply did not contain PNG bytes")
    try:
        png = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise RuntimeError(f"TextureCraft screenshot reply had invalid base64: {error}") from error
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("TextureCraft screenshot reply did not have a PNG signature")
    return png

def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in sorted(value.items()) if k not in {"id", "uuid", "path", "filePath", "timestamp"}}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def stable_session():
    state = request("session.inspect", request_id=8)
    selected = state.get("selectedLayer")
    def layer_name(layers):
        for layer in layers or []:
            if layer.get("id") == selected:
                return layer.get("name")
            nested = layer_name(layer.get("children", []))
            if nested is not None:
                return nested
        return None
    state["selectedLayer"] = layer_name(state.get("layers"))
    if isinstance(state.get("target"), int):
        state["target"] = "effect"
    for key in ("memoryBytes", "pendingTiles"):
        state.pop(key, None)
    return stable(state)


try:
    if action == "startup-warm":
        proc = launch()
        wait_for_server(proc)
        if platform.system() == "Darwin":
            request("session.inspect", request_id=8)
        else:
            screenshot_frame(proc)
        stop(proc)
        proc = None
    screenshot_rpc_ns = None
    screenshot_total_ns = None
    mapped_elapsed_ns = None
    frame_sha256 = None
    if action in ("startup-cold", "startup-warm"):
        if platform.system() == "Darwin":
            mac_window_watch_binary()
        watcher_dir = tempfile.TemporaryDirectory(prefix="texturecraft-map-watch-")
        watcher, mapped_path = start_map_watch(watcher_dir.name)
        started = time.perf_counter_ns()
        # The Cocoa watcher timestamps CLOCK_MONOTONIC; macOS Python's perf counter uses a different origin.
        mapped_started = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        proc = launch()
        wait_for_server(proc)
        if watcher is not None:
            mapped_elapsed_ns = wait_for_map(proc, mapped_path) - mapped_started
        if platform.system() == "Darwin":
            # The WindowServer mark is independent of whether a locked display can render a
            # screenshot. session.inspect below provides a cheap post-mark readiness query.
            request("session.inspect", request_id=8)
            duration = mapped_elapsed_ns
        else:
            capture_started = time.perf_counter_ns()
            png = screenshot_frame(proc)
            screenshot_rpc_ns = time.perf_counter_ns() - capture_started
            screenshot_total_ns = time.perf_counter_ns() - started
            frame_sha256 = hashlib.sha256(png).hexdigest()
            duration = mapped_elapsed_ns if mapped_elapsed_ns is not None else screenshot_total_ns
        if mapped_elapsed_ns is not None:
            print(f"CRAFT_WINDOW_MAPPED_NS={mapped_elapsed_ns}")
        if screenshot_total_ns is not None:
            print(f"CRAFT_SCREENSHOT_NS={screenshot_total_ns}")
            print(f"CRAFT_SCREENSHOT_RPC_NS={screenshot_rpc_ns}")
            print(f"CRAFT_FRAME_SHA256={frame_sha256}")
        diagnostics = Path(output).parent / f"texturecraft-{action}.timing.jsonl"
        with diagnostics.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "window_mapped_ns": mapped_elapsed_ns,
                "library_ready_ns": None,
                "screenshot_complete_ns": screenshot_total_ns,
                "screenshot_rpc_ns": screenshot_rpc_ns,
            }, sort_keys=True) + "\n")
    else:
        proc = launch()
        wait_for_server(proc)
        screenshot_frame(proc)
    if action not in ("startup-cold", "startup-warm"):
        if action == "open":
            started = time.perf_counter_ns()
            request("command.run", {"id": "file.open", "params": {"path": project}}, 2)
            request("ui.screenshot", request_id=9)
            duration = time.perf_counter_ns() - started
        else:
            request("command.run", {"id": "file.open", "params": {"path": project}}, 2)
            request("ui.screenshot", request_id=9)
            started = time.perf_counter_ns()
        if action == "paint":
            layer = request("command.run", {"id": "layer.add.paint", "params": {}}, 3)
            if isinstance(layer, dict) and "layer" in layer:
                request("command.run", {"id": "layer.select", "params": {"layer": layer["layer"]}}, 4)
            request("command.run", {"id": "tool.select", "params": {"tool": "paint"}}, 5)
            request("debug.paintTest", {"from": [400, 400], "to": [900, 700], "frames": 120}, 6)
            deadline = time.monotonic() + 60
            while True:
                frames = request("debug.frames", request_id=7)
                if frames.get("strokeEnd"):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("paint stroke did not commit within 60 seconds")
                time.sleep(0.02)
        elif action == "layer":
            request("command.run", {"id": "layer.add.fill", "params": {"color": "#6f747b", "roughness": 0.42}}, 3)
        elif action == "save":
            save_path = output + ".tcraft"
            request("command.run", {"id": "file.saveAs", "params": {"path": save_path}}, 3)
            if not os.path.isfile(save_path):
                raise RuntimeError("Save As did not create the project file")
        elif action == "export":
            request("command.run", {"id": "file.exportTextures", "params": {"dir": output, "size": 2048, "ts": "all"}}, 3)
            exported = sorted(name for name in os.listdir(output) if name.lower().endswith(".png"))
            if len(exported) != 12:
                raise RuntimeError(f"expected 12 exported PNG maps, found {len(exported)}")
        duration = time.perf_counter_ns() - started
    if action == "save":
        identity = hashlib.sha256(open(output + ".tcraft", "rb").read()).hexdigest()
    elif action == "export":
        digest = hashlib.sha256()
        for name in sorted(os.listdir(output)):
            path = os.path.join(output, name)
            if os.path.isfile(path):
                digest.update(name.encode())
                with open(path, "rb") as exported_file:
                    for block in iter(lambda: exported_file.read(1024 * 1024), b""):
                        digest.update(block)
        identity = digest.hexdigest()
    else:
        state = stable_session()
        identity = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print(f"CRAFT_JOURNEY_NS={duration}")
    print(f"CRAFT_OUTPUT_SHA256={identity}")
finally:
    if proc is not None:
        stop(proc)
    if watcher is not None:
        watcher.terminate()
        watcher.wait(timeout=2)
    if watcher_dir is not None:
        watcher_dir.cleanup()
    if display_process is not None:
        display_process.terminate()
        display_process.wait(timeout=2)
    cache.cleanup()
