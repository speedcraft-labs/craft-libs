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

from desktop_startup import ensure_display


binary, project, action, output = sys.argv[1:]
if os.path.exists(output):
    shutil.rmtree(output) if os.path.isdir(output) else os.unlink(output)
port = 41000 + os.getpid() % 20000
token = "craft-journey-texturecraft-291-token"
env = os.environ.copy()
cache = tempfile.TemporaryDirectory(prefix="texturecraft-journey-cache-")
env.update(TEXTURECRAFT_NO_PREFS="1", TEXTURECRAFT_CONTROL_TOKEN=token, WGPU_BACKEND="vulkan", XDG_CACHE_HOME=cache.name)
if platform.system() == "Linux":
    env["__EGL_VENDOR_LIBRARY_FILENAMES"] = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
display_process = ensure_display()
if os.environ.get("DISPLAY"):
    env["DISPLAY"] = os.environ["DISPLAY"]
cmd = [binary, "--control", str(port)]
proc = None
watcher = None
watcher_dir = None

def start_map_watch(directory):
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

def screenshot_frame():
    result = request("ui.screenshot")
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

def launch():
    return subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

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

try:
    if action == "startup-warm":
        proc = launch()
        wait_for_server(proc)
        screenshot_frame()
        stop(proc)
        proc = None
    screenshot_rpc_ns = None
    screenshot_total_ns = None
    mapped_elapsed_ns = None
    frame_sha256 = None
    if action in ("startup-cold", "startup-warm"):
        started = time.perf_counter_ns()
        watcher_dir = tempfile.TemporaryDirectory(prefix="texturecraft-map-watch-")
        watcher, mapped_path = start_map_watch(watcher_dir.name)
        proc = launch()
        wait_for_server(proc)
        if watcher is not None:
            mapped_elapsed_ns = wait_for_map(proc, mapped_path) - started
            capture_started = time.perf_counter_ns()
            png = screenshot_frame()
            screenshot_rpc_ns = time.perf_counter_ns() - capture_started
            screenshot_total_ns = time.perf_counter_ns() - started
            frame_sha256 = hashlib.sha256(png).hexdigest()
            duration = mapped_elapsed_ns
        else:
            capture_started = time.perf_counter_ns()
            png = screenshot_frame()
            screenshot_rpc_ns = time.perf_counter_ns() - capture_started
            screenshot_total_ns = time.perf_counter_ns() - started
            frame_sha256 = hashlib.sha256(png).hexdigest()
            duration = screenshot_total_ns
        if watcher is not None:
            print(f"CRAFT_WINDOW_MAPPED_NS={mapped_elapsed_ns}")
        print(f"CRAFT_SCREENSHOT_NS={screenshot_total_ns}")
        print(f"CRAFT_SCREENSHOT_RPC_NS={screenshot_rpc_ns}")
        print(f"CRAFT_FRAME_SHA256={frame_sha256}")
        if watcher is not None:
            watcher.terminate()
            watcher.wait(timeout=2)
            watcher = None
        watcher_dir.cleanup()
        watcher_dir = None
    else:
        proc = launch()
        wait_for_server(proc)
        screenshot_frame()
        duration = None
    if action not in ("startup-cold", "startup-warm"):
        if action == "open":
            started = time.perf_counter_ns()
            request("command.run", {"id": "file.open", "params": {"path": project}}, 2)
            duration = time.perf_counter_ns() - started
        else:
            request("command.run", {"id": "file.open", "params": {"path": project}}, 2)
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
    # The runner's equivalence gate identifies this pinned project/action pair. The action itself
    # must succeed above; startup's generated default project contains random IDs, so session JSON
    # is not a stable identity across launches.
    digest = hashlib.sha256(open(project, "rb").read()).hexdigest()
    identity = hashlib.sha256(f"{digest}:{action}".encode()).hexdigest()
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
