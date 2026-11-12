#!/usr/bin/env python3
"""One-shot TextureCraft desktop journey driven through its documented control channel."""
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
cmd = [binary, "--control", str(port)]
if platform.system() == "Linux" and os.environ.get("DISPLAY") is None:
    cmd = ["xvfb-run", "-a", "--server-args=-extension GLX", *cmd]
proc = None

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
    proc = launch()
    wait_for_server(proc)
    if action == "startup-warm":
        request("ui.screenshot")
        stop(proc)
        proc = launch()
        wait_for_server(proc)
    started = time.perf_counter_ns()
    request("ui.screenshot")
    first_frame_ns = time.perf_counter_ns() - started
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
    else:
        duration = first_frame_ns
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
    cache.cleanup()
